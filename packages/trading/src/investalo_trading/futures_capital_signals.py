"""Separate closed H4/H1 RSI identities with causal protection; research only."""
from dataclasses import dataclass, field, replace
from functools import cached_property
from datetime import datetime, timedelta
from decimal import Decimal

from .allocation import identifier, revision
from .futures_capital_research import (
    CapitalAssessment, CapitalPlan, CapitalCashPlan, CapitalRealizedCashPlan,
    CapitalResearchState, freeze_basket_leverage,
    prepare_capital_entry, record_capital_event, simulate_capital_fill,
)
from .futures_ledger import (
    DailyBasis, ExitFill, FundingSettlement, LedgerMark, LiquidationSettlement,
    MarginPosting, MarkBatch, number, timestamp,
)
from .futures_signals import IndicatorParameters
from .indicators import advance
from .models import IndicatorState, precise
from .capital_digest import CapitalCanonical, digest
from .timeframe_research import ResearchCandle, aggregate_h4

D = Decimal
ZERO = D("0")
VERSION = "isolated-usdt-capital-signals/1"
H1_VERSION = "isolated-usdt-capital-signals-h1/2"


@dataclass(frozen=True)
class CapitalSignalProfile(CapitalCanonical):
    plan: CapitalPlan
    protection_hours: int
    slippage: Decimal
    assumptions_digest: str

    def __post_init__(self):
        if type(self.plan) not in (CapitalPlan, CapitalCashPlan, CapitalRealizedCashPlan):
            raise ValueError("separate capital plan required")
        if type(self.protection_hours) is not int or self.protection_hours not in (1, 4):
            raise ValueError("closed H1 or H4 protection required")
        number(self.slippage, nonnegative=True)
        identifier(self.assumptions_digest)
        if self.slippage >= 1:
            raise ValueError("invalid declared slippage")

    @cached_property
    def profile_digest(self):
        return digest((VERSION, self, IndicatorParameters(), "H4-RSI", 30, 2,
                       D(".95"), D("1.05"), D(".45"), "no-automatic-sixth"))

    @property
    def entry_hours(self):
        return 4


@dataclass(frozen=True)
class CapitalH1SignalProfile(CapitalSignalProfile):
    """Separate research identity; existing H4 fields and hashes stay frozen."""
    signal_policy: str = field(default=H1_VERSION, init=False)

    def __post_init__(self):
        super().__post_init__()
        if type(self.plan) not in (CapitalCashPlan, CapitalRealizedCashPlan) or self.protection_hours != 1:
            raise ValueError("H1 entry comparison requires corrected cash and H1 protection")

    @property
    def entry_hours(self):
        return 1

    @cached_property
    def profile_digest(self):
        return digest((H1_VERSION, self, IndicatorParameters(), "H1-RSI", 30, 2,
                       D(".95"), D("1.05"), D(".45"), "no-automatic-sixth"))


def signal_version(profile):
    return H1_VERSION if type(profile) is CapitalH1SignalProfile else VERSION


@dataclass(frozen=True)
class CapitalHour(CapitalCanonical):
    trade: tuple[ResearchCandle, ...]
    mark: tuple[ResearchCandle, ...]

    def __post_init__(self):
        if (type(self.trade) is not tuple or type(self.mark) is not tuple
                or not 3 <= len(self.trade) <= 7 or len(self.trade) != len(self.mark)
                or any(type(b) is not ResearchCandle for b in (*self.trade, *self.mark))
                or any(b.close_time - b.open_time != timedelta(hours=1)
                       for b in (*self.trade, *self.mark))
                or len({(b.open_time, b.close_time) for b in (*self.trade, *self.mark)}) != 1):
            raise ValueError("complete matched native H1 trade/mark frame required")

    @property
    def close_time(self):
        return self.trade[0].close_time

    @cached_property
    def frame_digest(self):
        return digest((VERSION, self))


@dataclass(frozen=True)
class CapitalSymbol(CapitalCanonical):
    symbol: str
    cycle: int
    entry_indicator: IndicatorState = IndicatorState()
    protection_indicator: IndicatorState = IndicatorState()
    below_count: int = 0
    rearmed: bool = False
    protected: bool = False
    stop: Decimal | None = None
    exit_reasons: tuple[str, ...] = ()
    manual_notice: bool = False

    def __post_init__(self):
        identifier(self.symbol)
        revision(self.cycle)
        revision(self.below_count)
        if (not self.cycle or type(self.entry_indicator) is not IndicatorState
                or type(self.protection_indicator) is not IndicatorState
                or any(type(value) is not bool for value in (
                    self.rearmed, self.protected, self.manual_notice))
                or type(self.exit_reasons) is not tuple
                or len(set(self.exit_reasons)) != len(self.exit_reasons)):
            raise ValueError("immutable valid basket signals required")
        for reason in self.exit_reasons:
            identifier(reason)
        if self.stop is not None:
            number(self.stop, positive=True)
        if self.protected != (self.stop is not None):
            raise ValueError("protection must retain its stop")


@dataclass(frozen=True)
class CapitalSignalState(CapitalCanonical):
    profile: CapitalSignalProfile
    economic: CapitalResearchState
    revision: int
    as_of: datetime
    signals: tuple[CapitalSymbol, ...]
    trade_prices: tuple[LedgerMark, ...]
    trade_at: datetime
    h4_buffer: tuple[CapitalHour, ...]
    last_hour: CapitalHour | None
    last_entry_at: datetime | None
    audit_head: str

    def __post_init__(self):
        revision(self.revision)
        timestamp(self.as_of)
        timestamp(self.trade_at)
        identifier(self.audit_head)
        if (type(self.profile) not in (CapitalSignalProfile, CapitalH1SignalProfile)
                or type(self.economic) is not CapitalResearchState
                or self.profile.plan != self.economic.ledger.plan
                or self.as_of < self.economic.as_of or self.trade_at > self.as_of):
            raise ValueError("own profile and causal capital state required")
        symbols = self.profile.plan.symbols
        _prices(self.trade_prices, symbols)
        if (type(self.signals) is not tuple or len(self.signals) != len(symbols)
                or any(type(s) is not CapitalSymbol for s in self.signals)
                or tuple(s.symbol for s in self.signals) != symbols):
            raise ValueError("complete immutable symbol signals required")
        stopped = {s.symbol for s in self.economic.stopped}
        for signal, basket in zip(self.signals, self.economic.ledger.baskets, strict=True):
            cycle = basket.cycle if basket.quantity or basket.symbol in stopped else basket.cycle + 1
            if signal.cycle != cycle:
                raise ValueError("signal belongs to a different basket cycle")
        if (type(self.h4_buffer) is not tuple or len(self.h4_buffer) > 3
                or any(type(h) is not CapitalHour for h in self.h4_buffer)):
            raise ValueError("bounded H4 aggregation evidence required")
        if self.last_hour is not None:
            if type(self.last_hour) is not CapitalHour or self.last_hour.close_time > self.as_of:
                raise ValueError("unfinished last hour")
            if self.h4_buffer and self.h4_buffer[-1] != self.last_hour:
                raise ValueError("aggregation must end at the last closed hour")
        if self.last_entry_at is not None:
            timestamp(self.last_entry_at)
            if (self.last_entry_at > self.as_of or self.last_entry_at.hour % self.profile.entry_hours
                    or any((self.last_entry_at.minute, self.last_entry_at.second,
                            self.last_entry_at.microsecond))):
                raise ValueError("closed entry timeframe signal time required")

    @cached_property
    def state_digest(self):
        return digest((signal_version(self.profile), self))

    @property
    def execution_enabled(self):
        return False


@dataclass(frozen=True)
class CapitalSignalAssessment:
    state_digest: str
    profile_digest: str
    signal_time: datetime
    capital: CapitalAssessment

    def __post_init__(self):
        identifier(self.state_digest)
        identifier(self.profile_digest)
        timestamp(self.signal_time)
        if type(self.capital) is not CapitalAssessment:
            raise ValueError("typed own capital assessment required")


@dataclass(frozen=True)
class CapitalFundingBatch:
    settlements: tuple[FundingSettlement, ...]
    evidence_digest: str

    def __post_init__(self):
        identifier(self.evidence_digest)
        if (type(self.settlements) is not tuple or not 1 <= len(self.settlements) <= 7
                or any(type(p) is not FundingSettlement for p in self.settlements)):
            raise ValueError("bounded immutable simultaneous funding batch required")
        symbols = tuple(p.symbol for p in self.settlements)
        if symbols != tuple(sorted(set(symbols))):
            raise ValueError("canonical unique simultaneous funding symbols required")


def _prices(prices, symbols):
    if (type(prices) is not tuple or any(type(p) is not LedgerMark for p in prices)
            or tuple(p.symbol for p in prices) != symbols):
        raise ValueError("complete canonical price evidence required")


def start_capital_signals(profile, economic, initial_trade):
    """Genesis only. Full replay, not a fresh wrapper, is required for restore."""
    if (type(profile) not in (CapitalSignalProfile, CapitalH1SignalProfile)
            or type(economic) is not CapitalResearchState
            or profile.plan != economic.ledger.plan or economic.revision
            or economic.ledger.revision or economic.decisions or economic.stages
            or economic.stopped or economic.ledger.halted
            or any(b.quantity for b in economic.ledger.baskets)):
        raise ValueError("own flat genesis required; advanced state cannot restart")
    _prices(initial_trade, profile.plan.symbols)
    return CapitalSignalState(
        profile, economic, 0, economic.as_of,
        tuple(CapitalSymbol(s, 1) for s in profile.plan.symbols), initial_trade,
        economic.as_of, (), None, None,
        digest((signal_version(profile), profile.profile_digest, economic.state_digest, initial_trade)),
    )


def _check(state, expected_revision, at):
    revision(expected_revision)
    at = timestamp(at)
    if expected_revision != state.revision or at < state.as_of:
        raise ValueError("stale revision or backdated signal evidence")
    return at


def _finish(state, at, body, **changes):
    candidate = replace(state, revision=state.revision + 1, as_of=at, **changes)
    return replace(candidate, audit_head=digest((
        signal_version(state.profile), state.audit_head, body, at, candidate.state_digest,
    )))


@precise
def _protect(profile, economic, signal, basket, trade_price, *, evaluate_price=True):
    if not basket.quantity:
        return signal
    reasons = list(signal.exit_reasons)
    if basket.symbol in economic.liquidation_required:
        reasons.insert(0, "liquidation_settlement_required")
    if economic.ledger.halted:
        reasons.append("economic_integrity_exit_required")
    if evaluate_price and trade_price <= basket.first_fill * D(".45"):
        reasons.append("first_fill_emergency_exit")
    if evaluate_price and signal.stop is not None and trade_price <= signal.stop:
        reasons.append("protective_stop_crossed")
    if not signal.protected and (not evaluate_price or trade_price < basket.average_entry * D("1.05")):
        return replace(signal, exit_reasons=tuple(dict.fromkeys(reasons)))
    contract = profile.plan.contracts[profile.plan.symbols.index(basket.symbol)]
    numerator = (basket.quantity * basket.average_entry + basket.entry_fees + basket.exit_fees
                 - basket.realized_price_pnl - basket.funding_net)
    floor = max(ZERO, numerator) / (
        basket.quantity * (1 - contract.protective_exit_fee_rate) * (1 - profile.slippage))
    candidates = [floor]
    if signal.stop is not None:
        candidates.append(signal.stop)
    indicator = signal.protection_indicator
    if indicator.bullish and indicator.supertrend is not None and ZERO < indicator.supertrend < trade_price:
        candidates.append(indicator.supertrend)
    stop = max(candidates)
    if evaluate_price and trade_price <= stop:
        reasons.append("net_breakeven_floor_crossed")
    return replace(signal, protected=True, rearmed=False, stop=stop,
                   exit_reasons=tuple(dict.fromkeys(reasons)))


def _protected(profile, economic, signals, prices, *, evaluate_price=True):
    return tuple(_protect(profile, economic, s, b, p.price, evaluate_price=evaluate_price)
                 for s, b, p in zip(signals, economic.ledger.baskets, prices, strict=True))


@precise
def observe_capital_prices(state, trade, mark, event_id, expected_revision, at):
    """Declared finer execution axis; OHLC alone never invents an intrabar path."""
    at = _check(state, expected_revision, at)
    _prices(trade, state.profile.plan.symbols)
    _prices(mark, state.profile.plan.symbols)
    economic = record_capital_event(
        state.economic, MarkBatch(mark), event_id, state.economic.revision, at)
    return _finish(state, at, ("prices", event_id, trade, mark), economic=economic,
                   trade_prices=trade, trade_at=at,
                   signals=_protected(state.profile, economic, state.signals, trade))


@precise
def replay_capital_hour(state, frame, expected_revision, observed_at, *,
                        close_valuation=None, valuation_evidence=None):
    observed_at = _check(state, expected_revision, observed_at)
    if type(frame) is not CapitalHour:
        raise ValueError("typed capital H1 frame required")
    symbols = state.profile.plan.symbols
    if (tuple(b.symbol for b in frame.trade) != tuple(f"{s}:USDT-M:trade" for s in symbols)
            or tuple(b.symbol for b in frame.mark) != tuple(f"{s}:USDT-M:mark" for s in symbols)):
        raise ValueError("native futures trade/mark price kinds required")
    if observed_at < frame.close_time:
        raise ValueError("unfinished H1 frame")
    if close_valuation is not None:
        _prices(close_valuation, symbols)
        identifier(valuation_evidence)
    elif valuation_evidence is not None:
        raise ValueError("valuation evidence needs complete marks")
    if state.last_hour is not None and frame == state.last_hour:
        if close_valuation is not None:
            raise ValueError("duplicate or revised valued hour")
        return state
    previous_close = state.last_hour.close_time if state.last_hour else state.economic.ledger.day_started_at
    if frame.trade[0].open_time != previous_close or frame.close_time <= state.economic.as_of:
        raise ValueError("revised, old or gapped H1 evidence")
    trade = tuple(LedgerMark(s, b.close) for s, b in zip(symbols, frame.trade, strict=True))
    mark = close_valuation if close_valuation is not None else tuple(
        LedgerMark(s, b.close) for s, b in zip(symbols, frame.mark, strict=True))
    evidence = (digest((VERSION, "valued-hour", frame.frame_digest, mark, valuation_evidence))
                if close_valuation is not None else frame.frame_digest)
    economic = record_capital_event(
        state.economic, MarkBatch(mark), "hour-" + evidence,
        state.economic.revision, frame.close_time)
    midnight = frame.close_time.replace(hour=0, minute=0, second=0, microsecond=0)
    if midnight > economic.ledger.day_started_at:
        if frame.close_time != midnight:
            raise ValueError("missing exact midnight evidence")
        if economic.ledger.equity > 0:
            economic = record_capital_event(
                economic, DailyBasis(economic.ledger.equity, evidence),
                "day-" + evidence, economic.revision, midnight)
    # Evaluate the old stop before using the newly closed protection candle.
    signals = _protected(state.profile, economic, state.signals, trade)
    group = (*state.h4_buffer, frame)
    h4 = None
    if len(group) == 4:
        h4 = tuple(aggregate_h4(tuple(h.trade[i] for h in group))[0] for i in range(len(symbols)))
        group = ()
    updated = []
    for i, (signal, basket) in enumerate(zip(signals, economic.ledger.baskets, strict=True)):
        entry_bar = frame.trade[i] if state.profile.entry_hours == 1 else (
            h4[i] if h4 is not None else None)
        if entry_bar is not None:
            indicator = advance(signal.entry_indicator, entry_bar, IndicatorParameters())
            below = indicator.rsi is not None and indicator.rsi < 30
            signal = replace(signal, entry_indicator=indicator,
                             below_count=signal.below_count + 1 if below else 0,
                             rearmed=signal.rearmed or bool(basket.quantity and indicator.rsi is not None
                                                           and indicator.rsi > 30))
        protection_bar = frame.trade[i] if state.profile.protection_hours == 1 else (
            h4[i] if h4 is not None else None)
        if protection_bar is not None:
            signal = replace(signal, protection_indicator=advance(
                signal.protection_indicator, protection_bar, IndicatorParameters()))
        updated.append(signal)
    return _finish(
        state, observed_at, ("hour", frame.frame_digest) if close_valuation is None else (
            "valued-hour", frame.frame_digest, mark, valuation_evidence), economic=economic,
        trade_prices=trade, trade_at=frame.close_time, last_hour=frame, h4_buffer=group,
        last_entry_at=frame.close_time if state.profile.entry_hours == 1 or h4 is not None
        else state.last_entry_at,
        signals=_protected(state.profile, economic, tuple(updated), trade))


def replay_valued_capital_hour(state, frame, marks, evidence_digest, expected_revision, observed_at):
    """Exact boundary valuation before day basis/funding; candles remain native."""
    return replay_capital_hour(
        state, frame, expected_revision, observed_at,
        close_valuation=marks, valuation_evidence=evidence_digest)


def record_signal_funding_batch(state, batch, event_id, expected_revision, at):
    """One signal/journal transition: fresh valuation, then all same-time settlements."""
    at = _check(state, expected_revision, at)
    if type(batch) is not CapitalFundingBatch:
        raise ValueError("typed simultaneous funding evidence required")
    identifier(event_id)
    baskets = {b.symbol: b for b in state.economic.ledger.baskets}
    if (any(b.marked_at != at for b in baskets.values())
            or any(p.symbol not in baskets or p.mark != baskets[p.symbol].mark
                   for p in batch.settlements)):
        raise ValueError("simultaneous funding needs complete exact-time valuation")
    economic = state.economic
    for payload in batch.settlements:
        economic = record_capital_event(
            economic, payload, "fund-" + digest((VERSION, event_id, batch.evidence_digest, payload.symbol)),
            economic.revision, at)
    return _finish(
        state, at, ("funding-batch", event_id, batch), economic=economic,
        signals=_protected(state.profile, economic, state.signals, state.trade_prices,
                           evaluate_price=False))


@precise
def _entry_signal(state, symbol, maximum_price, at):
    at = _check(state, state.revision, at)
    if any("liquidation_settlement_required" in s.exit_reasons for s in state.signals):
        raise ValueError("unsettled liquidation blocks new entries")
    if state.last_entry_at is None or not timedelta(0) <= at - state.last_entry_at <= timedelta(seconds=30):
        raise ValueError(f"missing or stale closed H{state.profile.entry_hours} entry signal")
    index = state.profile.plan.symbols.index(symbol)
    signal, basket = state.signals[index], state.economic.ledger.baskets[index]
    stages = tuple(r for r in state.economic.stages if (r.symbol, r.cycle) == (symbol, signal.cycle))
    rsi = signal.entry_indicator.rsi
    if (signal.protected or signal.exit_reasons or len(stages) >= 5
            or rsi is None or rsi >= 30):
        raise ValueError("no regular entry signal; manual sixth has no automatic authority")
    if (not stages and (signal.below_count < 2 or basket.quantity)
            or stages and (not signal.rearmed or not basket.quantity)):
        raise ValueError("first confirmation or actual-fill rearm missing")
    number(maximum_price, positive=True)
    if stages and maximum_price > stages[-1].price * D(".95"):
        raise ValueError("maximum fill exceeds last actual stage five-percent drop")
    return signal


@precise
def declare_signal_leverage(state, symbol, leverage, evidence_digest, event_id, expected_revision, at):
    at = _check(state, expected_revision, at)
    index = state.profile.plan.symbols.index(symbol)
    _entry_signal(state, symbol, state.trade_prices[index].price * (1 + state.profile.slippage), at)
    economic = freeze_basket_leverage(
        state.economic, symbol, leverage, evidence_digest, event_id, state.economic.revision, at)
    return _finish(state, at, ("leverage", event_id), economic=economic)


@precise
def assess_capital_signal(state, symbol, maximum_price, at):
    _entry_signal(state, symbol, maximum_price, at)
    capital = prepare_capital_entry(state.economic, symbol, maximum_price, at)
    return CapitalSignalAssessment(
        state.state_digest, state.profile.profile_digest, state.last_entry_at, capital)


def simulate_signal_entry(state, assessment, price, event_id, expected_revision, at):
    at = _check(state, expected_revision, at)
    if (type(assessment) is not CapitalSignalAssessment or assessment.state_digest != state.state_digest
            or assessment.profile_digest != state.profile.profile_digest
            or assessment.signal_time != state.last_entry_at):
        raise ValueError("stale or foreign signal assessment")
    request = assessment.capital.request
    if assess_capital_signal(state, request.symbol, request.maximum_fill_price, at) != assessment:
        raise ValueError("signal admission changed")
    economic = simulate_capital_fill(
        state.economic, assessment.capital, price, event_id, state.economic.revision, at)
    index = state.profile.plan.symbols.index(request.symbol)
    cycle = economic.ledger.baskets[index].cycle
    count = sum((r.symbol, r.cycle) == (request.symbol, cycle) for r in economic.stages)
    signals = tuple(replace(s, rearmed=False, below_count=0, manual_notice=count == 5)
                    if i == index else s for i, s in enumerate(state.signals))
    # Fills are not price observations; never reuse the preceding close to activate protection.
    return _finish(state, at, ("entry", event_id), economic=economic, signals=signals)


def record_signal_economic_event(state, payload, event_id, expected_revision, at):
    """Valuation/funding/margin/exit evidence; marks are not trade observations."""
    at = _check(state, expected_revision, at)
    if type(payload) not in (MarkBatch, FundingSettlement, MarginPosting, ExitFill, LiquidationSettlement):
        raise ValueError("typed economic evidence required")
    if type(payload) is MarkBatch:
        economic = record_capital_event(
            state.economic, payload, event_id, state.economic.revision, at)
        return _finish(
            state, at, ("valuation", event_id, payload), economic=economic,
            signals=_protected(state.profile, economic, state.signals, state.trade_prices,
                               evaluate_price=False))
    index = state.profile.plan.symbols.index(payload.symbol)
    before = state.economic.ledger.baskets[index]
    if (type(payload) is ExitFill
            and "liquidation_settlement_required" in state.signals[index].exit_reasons):
        raise ValueError("liquidation requires its explicit terminal receipt")
    economic = record_capital_event(
        state.economic, payload, event_id, state.economic.revision, at)
    signals = list(state.signals)
    after = economic.ledger.baskets[index]
    if before.quantity and not after.quantity:
        s = signals[index]
        if type(payload) is LiquidationSettlement:
            signals[index] = replace(s, rearmed=False, below_count=0, manual_notice=False,
                                     exit_reasons=("liquidated",))
        else:
            signals[index] = CapitalSymbol(
                s.symbol, after.cycle + 1, s.entry_indicator, s.protection_indicator)
    signals = _protected(state.profile, economic, tuple(signals), state.trade_prices,
                         evaluate_price=False)
    return _finish(state, at, ("economic", event_id, payload), economic=economic, signals=signals)
