"""Funding-only Paper transition with explicit settlement-time valuation."""
from dataclasses import dataclass
from datetime import datetime, timedelta

from .allocation import identifier
from .capital_digest import digest
from .futures_capital_research import record_capital_event
from .futures_capital_signals import (
    CapitalFundingBatch, CapitalHour, _finish as finish_signal, _protected,
    record_signal_funding_batch, replay_valued_capital_hour,
)
from .futures_ledger import FundingSettlement, LedgerMark, MarkBatch, timestamp
from .futures_paper import PaperFunding, _check, _event, _finish
from .models import precise

VERSION = "isolated-usdt-futures-paper-settlement/1"


@dataclass(frozen=True)
class PaperSettlement:
    input_id: str
    settled_at: datetime
    marks: tuple[LedgerMark, ...]
    valuation_digest: str
    funding: tuple[PaperFunding, ...]
    hours: tuple[CapitalHour, ...] = ()

    def __post_init__(self):
        identifier(self.input_id)
        timestamp(self.settled_at)
        if (type(self.valuation_digest) is not str or len(self.valuation_digest) != 64
                or any(c not in "0123456789abcdef" for c in self.valuation_digest)):
            raise ValueError("settlement valuation SHA256 required")
        for rows, kind, low, high in ((self.marks, LedgerMark, 3, 7),
                                      (self.funding, PaperFunding, 1, 7),
                                      (self.hours, CapitalHour, 0, 1)):
            if (type(rows) is not tuple or not low <= len(rows) <= high
                    or any(type(row) is not kind for row in rows)):
                raise ValueError("bounded typed immutable settlement evidence required")
        symbols = tuple(row.symbol for row in self.funding)
        if symbols != tuple(sorted(set(symbols))) or any(
                row.settled_at != self.settled_at for row in self.funding):
            raise ValueError("canonical native funding at one exact settlement time required")

    @property
    def receipt_id(self):
        return "paper-settlement-" + digest((VERSION, self))


@precise
def settle_paper_funding(state, settlement, expected_revision, at):
    """Accept delayed rates without backdating knowledge or simulating orders.

    The caller must archive the native rates and independent exact-time marks.
    No current quote, forecast or candle approximation is substituted here.
    """
    if type(settlement) is not PaperSettlement:
        raise ValueError("exact Paper settlement contract required")
    return _settle_paper_funding(state, settlement, expected_revision, at)


@precise
def _settle_paper_funding(state, settlement, expected_revision, at, *, version=VERSION):
    """Shared arithmetic; public exact/model contracts validate before entering."""
    _check(state, expected_revision, at)
    at = timestamp(at)
    if (not state.warmed
            or not state.signal.as_of < settlement.settled_at <= at
            or not timedelta(0) <= at - settlement.settled_at <= timedelta(hours=1)):
        raise ValueError("causal warmed Paper settlement with bounded publication lag required")
    if settlement.input_id in state.inputs:
        raise ValueError("settlement already acknowledged; read back, never resend")
    signal, plan = state.signal, state.config.profile.plan
    if (tuple(mark.symbol for mark in settlement.marks) != plan.symbols
            or any(row.symbol not in plan.symbols for row in settlement.funding)):
        raise ValueError("complete canonical own settlement valuation required")
    if (signal.economic.liquidation_required
            or any("liquidation_settlement_required" in s.exit_reasons for s in signal.signals)):
        raise ValueError("prior liquidation requires reconciliation before newer valuation")
    funding_ids = state.funding_ids
    for row in settlement.funding:
        funding_ids = funding_ids.append(digest((row.symbol, row.native_id)))
    boundary = settlement.settled_at.replace(minute=0, second=0, microsecond=0)
    if settlement.hours:
        frame = settlement.hours[0]
        if frame.close_time != settlement.settled_at:
            raise ValueError("settlement hour must close at the exact valuation time")
        signal = replay_valued_capital_hour(
            signal, frame, settlement.marks, settlement.valuation_digest,
            signal.revision, settlement.settled_at)
    elif signal.last_hour is None or signal.last_hour.close_time != boundary:
        raise ValueError("latest closed H1 settlement evidence missing")
    else:
        # Marks affect collateral, never pretend to be executable Bid/Ask quotes.
        economic = record_capital_event(
            signal.economic, MarkBatch(settlement.marks),
            _event(settlement.input_id, "settlement-mark"), signal.economic.revision,
            settlement.settled_at)
        signal = finish_signal(
            signal, settlement.settled_at, (version, "valuation", settlement),
            economic=economic,
            signals=_protected(signal.profile, economic, signal.signals,
                               signal.trade_prices, evaluate_price=False))
    funding = CapitalFundingBatch(tuple(
        FundingSettlement(row.symbol, settlement.marks[plan.symbols.index(row.symbol)].price, row.rate)
        for row in settlement.funding), digest((version, settlement)))
    signal = record_signal_funding_batch(
        signal, funding, _event(settlement.input_id, "native-settlement"),
        signal.revision, settlement.settled_at)
    # A closed candle is indicator evidence, not a newly captured trading quote.
    signal = finish_signal(
        signal, settlement.settled_at, (version, "preserve-quote-clock"),
        trade_prices=state.signal.trade_prices, trade_at=state.signal.trade_at)
    return _finish(
        state, (version, settlement), signal=signal,
        inputs=state.inputs.append(settlement.input_id).append(settlement.receipt_id), funding_ids=funding_ids,
        attempts=(), observed_at=at)
