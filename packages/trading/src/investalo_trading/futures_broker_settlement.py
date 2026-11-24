"""One atomic original order plus concurrent funding; no reconstructed broker cash."""
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from decimal import Decimal

from .capital_digest import CapitalCanonical, digest
from .futures_broker_entries import (
    BrokerEntryOrder, BrokerEntryObservation, BrokerExitOrder, BrokerExitObservation,
    _check, _check_cumulative, _finish, observe_broker_entry, observe_broker_exit,
)
from .futures_broker_funding import BrokerFundingBill, milliseconds, TOLERANCE
from .futures_broker_margin import BrokerMarginBaseline
from .futures_capital_research import record_capital_event
from .futures_capital_signals import _finish as finish_signal, _protected, record_signal_economic_event
from .futures_ledger import BrokerFundingPayment, BrokerFundingCloseFill, timestamp
from .futures_replay_journal import _sha
from .models import precise

D = Decimal


@dataclass(frozen=True)
class BrokerOrderFundingSettlement(CapitalCanonical):
    book_digest: str
    baseline: BrokerMarginBaseline
    snapshot: BrokerMarginBaseline
    entry: BrokerEntryObservation | None
    exit: BrokerExitObservation | None
    bills: tuple[BrokerFundingBill, ...]
    observed_at: datetime
    evidence_digest: str

    def __post_init__(self):
        _sha(self.book_digest); _sha(self.evidence_digest); timestamp(self.observed_at)
        if (type(self.baseline) is not BrokerMarginBaseline or type(self.snapshot) is not BrokerMarginBaseline
                or (self.entry is None) == (self.exit is None)
                or self.entry is not None and type(self.entry) is not BrokerEntryObservation
                or self.exit is not None and type(self.exit) is not BrokerExitObservation
                or self.observation.order_digest != self.baseline.order_digest
                or self.baseline.order_digest != self.snapshot.order_digest
                or self.baseline.intent_digest != self.snapshot.intent_digest
                or not self.baseline.observed_ms <= self.snapshot.start_ms
                or self.observation.funding_through_ms != self.snapshot.observed_ms
                or not 0 <= milliseconds(self.observed_at) - self.snapshot.start_ms <= 5000
                or type(self.bills) is not tuple or not 1 <= len(self.bills) <= 800
                or any(type(b) is not BrokerFundingBill for b in self.bills)
                or len({b.id_digest for b in self.bills}) != len(self.bills)
                or self.bills != tuple(sorted(self.bills,key=lambda b:(b.settled_at,b.symbol,b.id_digest)))
                or any(not self.baseline.observed_ms < milliseconds(b.settled_at) <= self.snapshot.observed_ms
                       for b in self.bills)):
            raise ValueError("complete original atomic order/funding settlement required")

    @property
    def observation(self):
        return self.entry if self.entry is not None else self.exit


@precise
def record_order_funding(book, settlement, expected_revision, at):
    at = _check(book, expected_revision, at)
    if (type(settlement) is not BrokerOrderFundingSettlement or settlement.book_digest != book.state_digest
            or book.pending is None or settlement.observation.order_digest != book.pending.order_digest
            or not settlement.observed_at <= at or at-settlement.observed_at > timedelta(seconds=5)
            or not book.pending.prepared_at<=settlement.observation.observed_at<=settlement.observed_at
            or at-settlement.observation.observed_at>timedelta(seconds=5)
            or (settlement.entry is not None) != (type(book.pending) is BrokerEntryOrder)
            or not settlement.observation.reconcilable):
        raise ValueError("fresh reconciled original pending order required")
    order, obs = book.pending, settlement.observation
    _check_cumulative(order.request.quantity, book.observation, obs)
    ledger = book.signal.economic.ledger
    owned = {b.symbol:b for b in ledger.baskets if b.quantity}
    before = {p.symbol:p for p in settlement.baseline.positions}
    after = {p.symbol:p for p in settlement.snapshot.positions}
    if set(before) != set(owned):
        raise ValueError("original before-image has foreign quantities")
    if abs(settlement.baseline.collateral_without_upl-ledger.unposted_cash
           -sum((b.isolated_balance for b in ledger.baskets),D(0))) > TOLERANCE:
        raise ValueError("original before cash does not match owned ledger")
    for symbol,old in owned.items():
        p = before[symbol]
        tick = ledger.plan.grid_rules[ledger.plan.symbols.index(symbol)].price_tick
        if (p.quantity != old.quantity or abs(p.average_entry-old.average_entry) >
                min(D(1).scaleb(p.average_entry.as_tuple().exponent),tick)
                or abs(p.allocated_margin-old.isolated_balance)>TOLERANCE
                or abs(p.funding_total-old.funding_net)>TOLERANCE
                or abs(p.deducted_fees-old.entry_fees-old.exit_fees)>TOLERANCE
                or abs(p.realized_pnl-old.realized_price_pnl)>TOLERANCE):
            raise ValueError("original before position does not match owned ledger")
    target = order.request.symbol
    totals,paid,received,last = {},{},{},{}
    for bill in settlement.bills:
        old = owned.get(bill.symbol)
        if (old is None or (old.cycle,old.quantity) != (bill.cycle,bill.quantity)
                or old.last_funding_at is not None and bill.settled_at<=old.last_funding_at):
            raise ValueError("concurrent funding needs original owned cycle")
        totals[bill.symbol]=totals.get(bill.symbol,D(0))+bill.amount
        paid[bill.symbol]=paid.get(bill.symbol,D(0))+max(D(0),-bill.amount)
        received[bill.symbol]=received.get(bill.symbol,D(0))+max(D(0),bill.amount)
        last[bill.symbol]=bill.settled_at
    if target in totals and (type(order) is not BrokerExitOrder or obs.quantity!=order.before_quantity):
        raise ValueError("target funding needs complete close or independent margin allocation evidence")
    if target in last and milliseconds(last[target])>obs.native_updated_ms:
        raise ValueError("target funding follows terminal close")
    economic = book.signal.economic
    for symbol,old in owned.items():
        if symbol==target:
            continue
        new = after.get(symbol)
        if (new is None or (new.quantity,new.average_entry,new.deducted_fees,new.realized_pnl)
                != (before[symbol].quantity,before[symbol].average_entry,
                    before[symbol].deducted_fees,before[symbol].realized_pnl)
                or abs(new.funding_total-old.funding_net-totals.get(symbol,D(0)))>TOLERANCE):
            raise ValueError("other owned basket changed outside funding")
        isolated = new.allocated_margin-old.isolated_balance
        if not -paid.get(symbol,D(0))-TOLERANCE<=isolated<=received.get(symbol,D(0))+TOLERANCE:
            raise ValueError("unconfirmed other-basket margin allocation")
        if symbol in totals:
            economic=record_capital_event(economic,
                BrokerFundingPayment(symbol,old.cycle,old.quantity,totals[symbol],isolated,
                                     paid[symbol],last[symbol],settlement.evidence_digest),
                "joint-funding-"+digest((settlement.evidence_digest,symbol)),economic.revision,at)
        elif abs(isolated)>TOLERANCE:
            raise ValueError("unbilled other-basket margin change")
    signal = book.signal if economic is book.signal.economic else finish_signal(
        book.signal,at,("joint-other-funding",settlement.evidence_digest),economic=economic,
        signals=_protected(book.signal.profile,economic,book.signal.signals,
                           book.signal.trade_prices,evaluate_price=False))
    candidate=replace(book,signal=signal,as_of=at)
    if target in totals:
        old=owned[target]
        if (type(obs) is not BrokerExitObservation or target in after
                or (old.cycle,old.quantity,old.average_entry,old.isolated_balance)
                != (order.cycle,order.before_quantity,order.before_average,order.before_margin)
                or "liquidation_settlement_required" in signal.signals[ledger.plan.symbols.index(target)].exit_reasons
                or abs(obs.released_margin-old.isolated_balance)>TOLERANCE
                or abs(obs.realized_pnl-obs.quantity*(obs.average_price-old.average_entry))>TOLERANCE):
            raise ValueError("complete native close and terminal funding required")
        signal=record_signal_economic_event(signal,
            BrokerFundingCloseFill(target,obs.quantity,obs.average_price,-obs.signed_fee,
                totals[target],paid[target],last[target],settlement.evidence_digest),
            order.command_id,signal.revision,at)
        result=_finish(candidate,at,("joint-full-close",settlement),signal=signal,pending=None,observation=None,
                       notices=tuple(dict.fromkeys((*book.notices,"terminal_funding_debit_pool_unallocated"))))
    else:
        reducer=observe_broker_entry if settlement.entry is not None else observe_broker_exit
        result=reducer(candidate,obs,candidate.revision,at)
    final=result.signal.economic.ledger
    if (abs(settlement.snapshot.collateral_without_upl-final.unposted_cash
            -sum((b.isolated_balance for b in final.baskets),D(0)))>TOLERANCE
            or set(after)!={b.symbol for b in final.baskets if b.quantity}):
        raise ValueError("atomic final native cash and position set disagree")
    for old in final.baskets:
        if not old.quantity:
            continue
        new=after[old.symbol]
        tick=ledger.plan.grid_rules[ledger.plan.symbols.index(old.symbol)].price_tick
        if (new.quantity!=old.quantity or abs(new.average_entry-old.average_entry)>
                min(D(1).scaleb(new.average_entry.as_tuple().exponent),tick)
                or abs(new.allocated_margin-old.isolated_balance)>TOLERANCE
                or abs(new.funding_total-old.funding_net)>TOLERANCE
                or abs(new.deducted_fees-old.entry_fees-old.exit_fees)>TOLERANCE
                or abs(new.realized_pnl-old.realized_price_pnl)>TOLERANCE):
            raise ValueError("atomic final native position counters disagree")
    return _finish(book,at,("joint-settlement",settlement),signal=result.signal,pending=None,observation=None,
                   notices=result.notices)
