"""Atomic actual funding receipt; no rate estimate, clock renewal or order authority."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from .allocation import revision
from .capital_digest import CapitalCanonical, digest
from .futures_broker_entries import _check, _finish
from .futures_broker_margin import BrokerMarginBaseline
from .futures_capital_research import record_capital_event
from .futures_capital_signals import _finish as finish_signal, _protected
from .futures_ledger import BrokerFundingPayment, number, timestamp
from .futures_replay_journal import _sha
from .models import precise

D = Decimal
TOLERANCE = D(".00000004")
EPOCH = datetime.fromisoformat("1970-01-01T00:00:00+00:00")


def milliseconds(at):
    return (timestamp(at) - EPOCH) // timedelta(milliseconds=1)


@dataclass(frozen=True)
class BrokerFundingBill(CapitalCanonical):
    id_digest: str
    symbol: str
    cycle: int
    quantity: Decimal
    amount: Decimal
    settled_at: datetime

    def __post_init__(self):
        _sha(self.id_digest); revision(self.cycle); timestamp(self.settled_at)
        number(self.quantity, positive=True); number(self.amount)
        if type(self.symbol) is not str or not self.symbol or not self.cycle:
            raise ValueError("original owned funding bill required")


@dataclass(frozen=True)
class BrokerFundingBatch(CapitalCanonical):
    book_digest: str
    from_ms: int
    through_ms: int
    observed_at: datetime
    snapshot: BrokerMarginBaseline
    bills: tuple[BrokerFundingBill, ...]
    evidence_digest: str

    def __post_init__(self):
        _sha(self.book_digest); _sha(self.evidence_digest); timestamp(self.observed_at)
        if (type(self.from_ms) is not int or type(self.through_ms) is not int
                or not 0 <= self.from_ms < self.through_ms < 10**15
                or self.through_ms - self.from_ms > 30 * 86400000
                or type(self.snapshot) is not BrokerMarginBaseline
                or self.snapshot.order_digest != self.book_digest
                or self.snapshot.observed_ms != self.through_ms
                or not 0 <= milliseconds(self.observed_at) - self.snapshot.start_ms <= 5000
                or type(self.bills) is not tuple or len(self.bills) > 800
                or any(type(b) is not BrokerFundingBill for b in self.bills)
                or len({b.id_digest for b in self.bills}) != len(self.bills)
                or self.bills != tuple(sorted(self.bills, key=lambda b: (b.settled_at, b.symbol, b.id_digest)))
                or any(not self.from_ms < milliseconds(b.settled_at) <= self.through_ms for b in self.bills)):
            raise ValueError("complete canonical native funding window required")


@precise
def record_broker_funding(book, batch, expected_revision, at):
    at = _check(book, expected_revision, at)
    if (type(batch) is not BrokerFundingBatch or batch.book_digest != book.state_digest
            or book.pending is not None or not batch.observed_at <= at
            or at - batch.observed_at > timedelta(seconds=5)):
        raise ValueError("fresh original idle book and native funding batch required")
    ledger = book.signal.economic.ledger
    native = {p.symbol: p for p in batch.snapshot.positions}
    owned = {b.symbol: b for b in ledger.baskets if b.quantity}
    if set(native) != set(owned):
        raise ValueError("funding product quantity mismatch")
    totals, paid, received, last = {}, {}, {}, {}
    for bill in batch.bills:
        old = owned.get(bill.symbol)
        if (old is None or (old.cycle, old.quantity) != (bill.cycle, bill.quantity)
                or old.opened_at is None
                or old.last_funding_at is not None and bill.settled_at <= old.last_funding_at):
            raise ValueError("funding bill is outside original owned cycle")
        totals[bill.symbol] = totals.get(bill.symbol, D(0)) + bill.amount
        paid[bill.symbol] = paid.get(bill.symbol, D(0)) + max(D(0), -bill.amount)
        received[bill.symbol] = received.get(bill.symbol, D(0)) + max(D(0), bill.amount)
        last[bill.symbol] = bill.settled_at
    if abs(batch.snapshot.collateral_without_upl - ledger.unposted_cash
            - sum((b.isolated_balance for b in ledger.baskets), D(0))
            - sum(totals.values(), D(0))) > TOLERANCE:
        raise ValueError("native funding cash does not reconcile")
    economic = book.signal.economic
    for symbol, old in owned.items():
        new = native[symbol]
        index = ledger.plan.symbols.index(symbol)
        tick = ledger.plan.grid_rules[index].price_tick
        if (new.quantity != old.quantity or abs(new.average_entry - old.average_entry) >
                min(D(1).scaleb(new.average_entry.as_tuple().exponent), tick)
                or abs(new.deducted_fees - old.entry_fees - old.exit_fees) > TOLERANCE
                or abs(new.realized_pnl - old.realized_price_pnl) > TOLERANCE
                or abs(new.funding_total - old.funding_net - totals.get(symbol, D(0))) > TOLERANCE):
            raise ValueError("native funding position counters do not reconcile")
        isolated_change = new.allocated_margin - old.isolated_balance
        if not -paid.get(symbol, D(0)) - TOLERANCE <= isolated_change <= received.get(symbol, D(0)) + TOLERANCE:
            raise ValueError("native margin change exceeds actual funding")
        if symbol not in totals:
            if abs(isolated_change) > TOLERANCE:
                raise ValueError("unbilled isolated margin adjustment")
            continue
        payload = BrokerFundingPayment(symbol, old.cycle, old.quantity, totals[symbol],
            isolated_change, paid[symbol], last[symbol], batch.evidence_digest)
        economic = record_capital_event(economic, payload,
            "native-funding-" + digest((batch.evidence_digest, symbol)),
            economic.revision, at)
    signal = book.signal if not batch.bills else finish_signal(
        book.signal, at, ("native-funding", batch), economic=economic,
        signals=_protected(book.signal.profile, economic, book.signal.signals,
                           book.signal.trade_prices, evaluate_price=False))
    return _finish(book, at, ("native-funding", batch), signal=signal)
