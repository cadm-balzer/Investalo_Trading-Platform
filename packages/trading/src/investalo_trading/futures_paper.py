"""Injected-data Futures Paper runner. Every fill is a declared simulation."""
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from decimal import Decimal

from .allocation import identifier, revision
from .capital_digest import CapitalCanonical, digest
from .futures_capital_signals import (
    CapitalFundingBatch, CapitalH1SignalProfile, CapitalHour, CapitalSignalState,
    _entry_signal, _finish as finish_signal, _protected,
    assess_capital_signal, declare_signal_leverage, observe_capital_prices,
    record_signal_economic_event, record_signal_funding_batch, replay_capital_hour,
    replay_valued_capital_hour, simulate_signal_entry,
)
from .futures_ledger import ExitFill, FundingSettlement, LedgerMark, LiquidationSettlement, MarginPosting, number, timestamp
from .futures_paper_plan import CapitalPaperPoolPlan
from .identity_history import IdentityHistory
from .models import floor_step, precise

D = Decimal
ZERO = D(0)
VERSION = "isolated-usdt-futures-paper-runtime/1"


@dataclass(frozen=True)
class FuturesPaperConfig(CapitalCanonical):
    profile: CapitalH1SignalProfile
    trading_from: datetime
    liquidation_fee_rate: Decimal
    assume_insurance_credit: bool

    def __post_init__(self):
        if type(self.profile) is not CapitalH1SignalProfile or type(self.profile.plan) is not CapitalPaperPoolPlan:
            raise ValueError("own H1 Paper candidate profile required")
        timestamp(self.trading_from)
        number(self.liquidation_fee_rate, nonnegative=True)
        if self.liquidation_fee_rate >= 1 or type(self.assume_insurance_credit) is not bool:
            raise ValueError("explicit bounded Paper liquidation/insurance assumptions required")

    @property
    def config_digest(self):
        return digest((VERSION, self, "declared-full-fills", "not-broker-acceptance"))


@dataclass(frozen=True)
class PaperQuote:
    symbol: str
    bid: Decimal
    ask: Decimal
    mark: Decimal

    def __post_init__(self):
        identifier(self.symbol)
        for value in (self.bid, self.ask, self.mark):
            number(value, positive=True)
        if self.bid > self.ask:
            raise ValueError("crossed Paper quote")


@dataclass(frozen=True)
class PaperFunding:
    symbol: str
    native_id: str
    settled_at: datetime
    rate: Decimal

    def __post_init__(self):
        identifier(self.symbol)
        identifier(self.native_id)
        timestamp(self.settled_at)
        number(self.rate)
        if abs(self.rate) >= 1:
            raise ValueError("invalid native funding rate")


@dataclass(frozen=True)
class PaperBatch:
    input_id: str
    quoted_at: datetime
    quotes: tuple[PaperQuote, ...]
    hours: tuple[CapitalHour, ...] = ()
    funding: tuple[PaperFunding, ...] = ()

    def __post_init__(self):
        identifier(self.input_id)
        timestamp(self.quoted_at)
        for rows, kind, bound in ((self.quotes, PaperQuote, 7), (self.hours, CapitalHour, 72),
                                  (self.funding, PaperFunding, 7)):
            if type(rows) is not tuple or len(rows) > bound or any(type(r) is not kind for r in rows):
                raise ValueError("bounded typed immutable Paper input required")
        if len(self.quotes) < 3:
            raise ValueError("complete Paper candidate quotes required")
        symbols = tuple(f.symbol for f in self.funding)
        if symbols != tuple(sorted(set(symbols))):
            raise ValueError("unique canonical same-time native funding required")


@dataclass(frozen=True)
class PaperAttempt:
    symbol: str
    stage: int
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class FuturesPaperState(CapitalCanonical):
    config: FuturesPaperConfig
    signal: CapitalSignalState
    revision: int
    settings_revision: int
    observed_at: datetime
    warmed: bool
    inputs: IdentityHistory
    funding_ids: IdentityHistory
    attempts: tuple[PaperAttempt, ...]
    audit_head: str

    def __post_init__(self):
        revision(self.revision)
        revision(self.settings_revision)
        timestamp(self.observed_at)
        identifier(self.audit_head)
        if (type(self.config) is not FuturesPaperConfig or type(self.signal) is not CapitalSignalState
                or self.config.profile != self.signal.profile or type(self.warmed) is not bool
                or self.observed_at < self.signal.as_of
                or any(type(h) is not IdentityHistory for h in (self.inputs, self.funding_ids))
                or type(self.attempts) is not tuple or any(type(a) is not PaperAttempt for a in self.attempts)):
            raise ValueError("own coherent Paper state required")

    @property
    def state_digest(self):
        return digest((VERSION, self))

    @property
    def execution_enabled(self):
        return False


def start_paper(config, signal):
    if (signal.revision or signal.economic.revision or config.profile != signal.profile
            or config.trading_from < signal.as_of):
        raise ValueError("flat own Paper genesis required")
    return FuturesPaperState(config, signal, 0, 0, signal.as_of, False, IdentityHistory("event"),
                             IdentityHistory("event"), (), digest((VERSION, config.config_digest)))


def _check(state, expected_revision, at):
    revision(expected_revision)
    if type(state) is not FuturesPaperState or expected_revision != state.revision:
        raise ValueError("stale own Paper revision")
    if timestamp(at) < state.observed_at:
        raise ValueError("Paper clock regressed")


def _finish(state, body, **changes):
    candidate = replace(state, revision=state.revision + 1, **changes)
    return replace(candidate, audit_head=digest((VERSION, state.audit_head, body, candidate.state_digest)))


def warm_paper(state, hours, expected_revision, at):
    _check(state, expected_revision, at)
    at = timestamp(at)
    if (state.warmed or state.signal.revision or type(hours) is not tuple
            or not 16 <= len(hours) <= 72 or at < state.config.trading_from
            or hours[-1].close_time > state.config.trading_from):
        raise ValueError("once-only bounded closed Paper warmup before trading required")
    signal = state.signal
    for frame in hours:
        signal = replay_capital_hour(signal, frame, signal.revision, frame.close_time)
    if any(s.entry_indicator.rsi is None for s in signal.signals):
        raise ValueError("insufficient closed indicator warmup")
    return _finish(state, ("warmup", hours), signal=signal, warmed=True, observed_at=at)


def paper_settings(state, limit, settings_revision, expected_revision, at):
    _check(state, expected_revision, at)
    at = timestamp(at)
    if (type(limit) is not int or not 3 <= limit <= 7
            or type(settings_revision) is not int or settings_revision != state.settings_revision + 1
            or at < state.signal.as_of):
        raise ValueError("current contiguous own settings revision required")
    plan = replace(state.config.profile.plan, configured_limit=limit)
    profile = replace(state.config.profile, plan=plan)
    economic = replace(state.signal.economic, ledger=replace(state.signal.economic.ledger, plan=plan))
    signal = replace(state.signal, profile=profile, economic=economic)
    return _finish(state, ("settings", limit, settings_revision), config=replace(state.config, profile=profile),
                   signal=signal, settings_revision=settings_revision, observed_at=at)


def _event(input_id, kind, symbol=""):
    return "paper-" + digest((VERSION, input_id, kind, symbol))


@precise
def run_paper_batch(state, batch, expected_revision, at):
    """Validate and reduce the entire input before its single durable append."""
    _check(state, expected_revision, at)
    at = timestamp(at)
    if (not state.warmed or type(batch) is not PaperBatch
            or not timedelta(0) <= at - batch.quoted_at <= timedelta(seconds=30)
            or batch.quoted_at < state.config.trading_from or batch.quoted_at < state.signal.as_of):
        raise ValueError("warmed Paper with fresh causal quotes required")
    if batch.input_id in state.inputs:
        raise ValueError("Paper input already acknowledged; read back, never resend")
    signal, plan = state.signal, state.config.profile.plan
    if tuple(q.symbol for q in batch.quotes) != plan.symbols:
        raise ValueError("complete canonical own candidate quotes required")
    if (signal.economic.liquidation_required
            or any("liquidation_settlement_required" in s.exit_reasons for s in signal.signals)):
        raise ValueError("acknowledged liquidation requires reconciliation before newer quotes")
    # With open exposure, missing observations cannot become a fictitious execution path.
    if any(b.quantity for b in signal.economic.ledger.baskets) and len(batch.hours) > 1:
        raise ValueError("open Paper feed gap requires reconciliation")
    trade = tuple(LedgerMark(q.symbol, q.bid) for q in batch.quotes)
    marks = tuple(LedgerMark(q.symbol, q.mark) for q in batch.quotes)
    for frame in batch.hours:
        if frame.close_time > batch.quoted_at:
            raise ValueError("unfinished Paper hour")
        if frame.close_time == batch.quoted_at:
            signal = replay_valued_capital_hour(signal, frame, marks, digest(batch.quotes),
                                                signal.revision, frame.close_time)
        else:
            signal = replay_capital_hour(signal, frame, signal.revision, frame.close_time)
        if signal.economic.liquidation_required and frame.close_time < batch.quoted_at:
            raise ValueError("boundary liquidation requires reconciliation before newer quotes")
    boundary = batch.quoted_at.replace(minute=0, second=0, microsecond=0)
    if signal.last_hour is None or signal.last_hour.close_time != boundary:
        raise ValueError("latest closed H1 evidence missing")
    if signal.economic.ledger.as_of == batch.quoted_at and signal.economic.ledger.phase == 1:
        # Exact midnight: valuation already preceded DailyBasis. A second Mark
        # would reverse ledger phases. Bind trade quotes to that same valuation.
        if tuple(LedgerMark(b.symbol, b.mark) for b in signal.economic.ledger.baskets) != marks:
            raise ValueError("midnight quote differs from exact day valuation")
        signal = finish_signal(
            signal, batch.quoted_at, ("paper-midnight-trade", batch.input_id, trade),
            trade_prices=trade, trade_at=batch.quoted_at,
            signals=_protected(signal.profile, signal.economic, signal.signals, trade))
    else:
        signal = observe_capital_prices(signal, trade, marks, _event(batch.input_id, "quote"),
                                        signal.revision, batch.quoted_at)
    funding_ids = state.funding_ids
    for row in batch.funding:
        if row.symbol not in plan.symbols or row.settled_at != batch.quoted_at:
            raise ValueError("native funding requires exact settlement-time quotes")
        key = digest((row.symbol, row.native_id))
        funding_ids = funding_ids.append(key)  # Native identity, independent of packet identity.
    if batch.funding:
        batch_funding = CapitalFundingBatch(tuple(
            FundingSettlement(row.symbol, marks[plan.symbols.index(row.symbol)].price, row.rate)
            for row in batch.funding), digest(batch.funding))
        signal = record_signal_funding_batch(signal, batch_funding, _event(batch.input_id, "funding"),
                                             signal.revision, batch.quoted_at)
    exited = False
    for i, quote in enumerate(batch.quotes):
        basket, protection = signal.economic.ledger.baskets[i], signal.signals[i]
        if not basket.quantity or not protection.exit_reasons:
            continue
        plan.validate_exit_quantity(basket.symbol, basket.quantity)
        price = plan.adverse_price(basket.symbol, quote.bid * (1 - signal.profile.slippage), buy=False)
        if (basket.symbol in signal.economic.liquidation_required
                or "liquidation_settlement_required" in protection.exit_reasons):
            fee = basket.quantity * price * state.config.liquidation_fee_rate
            net = basket.isolated_balance + basket.quantity * (price - basket.average_entry) - fee
            credit = max(ZERO, -net)
            if credit and not state.config.assume_insurance_credit:
                raise ValueError("unbacked liquidation gap; explicit Paper insurance assumption required")
            payload = LiquidationSettlement(basket.symbol, basket.quantity, price, fee,
                                            net + credit, credit, digest((VERSION, batch, basket)))
        else:
            fee = basket.quantity * price * plan.contracts[i].protective_exit_fee_rate
            payload = ExitFill(basket.symbol, basket.quantity, price, fee)
        signal = record_signal_economic_event(signal, payload, _event(batch.input_id, "exit", basket.symbol),
                                              signal.revision, batch.quoted_at)
        exited = True
    attempts = []
    # An exit and a fresh buy cannot share a timestamp in the financial ledger.
    # Wait for another genuine quote; never manufacture +1s/+2s observations.
    if not exited and not signal.economic.ledger.halted and not signal.economic.liquidation_required:
        for i, basket in enumerate(signal.economic.ledger.baskets):
            if basket.quantity:
                deficit = max(ZERO, basket.margin_committed - basket.isolated_balance)
                amount = floor_step(min(deficit, plan.cost_restoration_capacity(basket)), plan.quantum)
                if amount:
                    signal = record_signal_economic_event(
                        signal, MarginPosting(basket.symbol, amount, True),
                        _event(batch.input_id, "restoration", basket.symbol), signal.revision, batch.quoted_at)
        # Existing funded ladders precede candidates competing for a free place.
        order = sorted(range(len(plan.symbols)),
                       key=lambda i: (not bool(signal.economic.ledger.baskets[i].quantity), plan.symbols[i]))
        for i in order:
            symbol, quote = plan.symbols[i], batch.quotes[i]
            basket = signal.economic.ledger.baskets[i]
            if any(s.symbol == symbol for s in signal.economic.stopped):
                continue
            price = plan.adverse_price(symbol, quote.ask * (1 + signal.profile.slippage), buy=True)
            try:
                _entry_signal(signal, symbol, price, batch.quoted_at)
            except ValueError:
                continue
            candidate = signal
            if not basket.quantity:
                candidate = declare_signal_leverage(
                    candidate, symbol, D(2), state.config.config_digest,
                    _event(batch.input_id, "2x", symbol), candidate.revision, batch.quoted_at)
            assessment = assess_capital_signal(candidate, symbol, price, batch.quoted_at)
            attempts.append(PaperAttempt(symbol, assessment.capital.stage, assessment.capital.reasons))
            if assessment.capital.allowed:
                signal = simulate_signal_entry(candidate, assessment, price, _event(batch.input_id, "buy", symbol),
                                                candidate.revision, batch.quoted_at)
    return _finish(state, ("batch", batch), signal=signal, inputs=state.inputs.append(batch.input_id),
                   funding_ids=funding_ids, attempts=tuple(attempts), observed_at=at)
