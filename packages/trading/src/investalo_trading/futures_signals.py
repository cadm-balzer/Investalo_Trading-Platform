"""Bounded causal H4 research adapter; declared fills, no dispatch or performance job."""
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from decimal import Decimal

from .allocation import identifier, revision
from .futures_continuation import ContinuationScenario, assess_futures_continuation
from .futures_ledger import (
    DailyBasis, EntryFill, ExitFill, FundingSettlement, LedgerMark, MarginPosting,
    MarkBatch, number, timestamp,
)
from .futures_pending import (
    OrderResolution, PendingResearchState, cancel_unattempted, record_fill,
    record_ledger_event, record_order_attempt, reconcile_order, reserve_purchase,
)
from .futures_risk import FuturesPlan, FuturesPurchase
from .indicators import advance
from .models import Candle, IndicatorState, floor_step, precise
from .snapshot import digest

D = Decimal
ZERO = D("0")
VERSION = "isolated-usdt-long-signals/1"
FIRST_FILL_MODEL = "declared-full-intent-margin-with-first-fragment/research-only"


@dataclass(frozen=True)
class IndicatorParameters:
    rsi_period: int = 14
    atr_period: int = 10
    supertrend_factor: Decimal = D("3")


@dataclass(frozen=True)
class ReplayProfile:
    plan: FuturesPlan
    margin_buffers: tuple[tuple[str, Decimal], ...]
    slippage: Decimal
    assumptions_digest: str
    first_fill_model: str

    def __post_init__(self):
        if not isinstance(self.plan, FuturesPlan):
            raise ValueError("frozen futures plan required")
        identifier(self.assumptions_digest)
        number(self.slippage, nonnegative=True)
        if self.slippage >= 1 or self.first_fill_model != FIRST_FILL_MODEL:
            raise ValueError("explicit research-only first-fill model required")
        if (type(self.margin_buffers) is not tuple
                or any(type(row) is not tuple or len(row) != 2 for row in self.margin_buffers)
                or tuple(row[0] for row in self.margin_buffers) != self.plan.symbols):
            raise ValueError("canonical explicit own margin buffers required")
        for (_, amount), budget in zip(self.margin_buffers, self.plan.budgets, strict=True):
            number(amount, nonnegative=True)
            if amount >= budget.margin_capital or floor_step(amount, self.plan.quantum) != amount:
                raise ValueError("buffer must leave a separate six-stage pool on the money grid")

    @property
    def profile_digest(self):
        return digest((VERSION, self, IndicatorParameters(), D("2"), D("1.25"),
                       D(".95"), 5, 6, D("1.05"), D(".45"), 30))

    @precise
    def stage_margins(self, symbol):
        index = self.plan.symbols.index(symbol)
        pool = self.plan.budgets[index].margin_capital - self.margin_buffers[index][1]
        weights = tuple(D("1.25") ** n for n in range(6))
        return tuple(floor_step(pool * w / sum(weights), self.plan.quantum) for w in weights)


@dataclass(frozen=True)
class H4Frame:
    trade: tuple[Candle, ...]
    mark: tuple[Candle, ...]

    def __post_init__(self):
        if (type(self.trade) is not tuple or type(self.mark) is not tuple
                or not 3 <= len(self.trade) <= 7 or len(self.trade) != len(self.mark)
                or any(type(b) is not Candle for b in (*self.trade, *self.mark))):
            raise ValueError("complete immutable trade/mark H4 frame required")
        if len({(b.open_time, b.close_time) for b in (*self.trade, *self.mark)}) != 1:
            raise ValueError("trade and mark axes must match")

    @property
    def close_time(self):
        return self.trade[0].close_time

    @property
    def frame_digest(self):
        return digest((VERSION, self))


@dataclass(frozen=True)
class CompletedStage:
    stage: int
    quantity: Decimal
    notional: Decimal
    intent_id: str
    terminal_evidence: str

    @property
    @precise
    def vwap(self):
        return self.notional / self.quantity


@dataclass(frozen=True)
class SymbolSignals:
    symbol: str
    cycle: int
    indicator: IndicatorState = IndicatorState()
    below_count: int = 0
    rearmed: bool = False
    stages: tuple[CompletedStage, ...] = ()
    protected: bool = False
    stop: Decimal | None = None
    exit_reasons: tuple[str, ...] = ()
    manual_notice: bool = False


@dataclass(frozen=True)
class SignalBinding:
    profile_digest: str
    symbol: str
    cycle: int
    stage: int
    intent_id: str
    signal_digest: str
    signal_time: datetime
    stage_margin: Decimal
    buffer_margin: Decimal
    request: FuturesPurchase
    filled_quantity: Decimal = ZERO
    filled_notional: Decimal = ZERO


@dataclass(frozen=True)
class SignalReplayState:
    profile: ReplayProfile
    economic: PendingResearchState
    revision: int
    as_of: datetime
    signals: tuple[SymbolSignals, ...]
    last_frame: H4Frame | None
    binding: SignalBinding | None
    quarantine: tuple[str, ...]
    audit_head: str

    def __post_init__(self):
        revision(self.revision)
        timestamp(self.as_of)
        identifier(self.audit_head)
        if (not isinstance(self.profile, ReplayProfile)
                or not isinstance(self.economic, PendingResearchState)
                or self.profile.plan != self.economic.ledger.plan
                or self.as_of < self.economic.as_of):
            raise ValueError("own profile and causal economic state required")
        if (type(self.signals) is not tuple
                or tuple(s.symbol for s in self.signals) != self.profile.plan.symbols):
            raise ValueError("complete canonical signal state required")
        if type(self.quarantine) is not tuple or len(set(self.quarantine)) != len(self.quarantine):
            raise ValueError("immutable latched quarantine required")
        for reason in self.quarantine:
            identifier(reason)
        p = self.economic.pending
        if (p is None) != (self.binding is None):
            raise ValueError("every pending intent requires immutable signal binding")
        if p is not None and (self.binding.profile_digest != self.profile.profile_digest
                              or self.binding.intent_id != p.intent_id
                              or self.binding.request != p.request):
            raise ValueError("foreign or changed signal intent")

    @property
    def state_digest(self):
        return digest((VERSION, self))

    @property
    def execution_enabled(self):
        return False


def start_signal_replay(profile: ReplayProfile, economic: PendingResearchState):
    """Start only on a flat reconciled research ledger; not a restore API."""
    if (economic.pending is not None or any(b.quantity for b in economic.ledger.baskets)
            or economic.reconciliation_halts or economic.ledger.halt_reasons):
        raise ValueError("flat reconciled research start required")
    return SignalReplayState(
        profile, economic, 0, economic.as_of,
        tuple(SymbolSignals(b.symbol, b.cycle + 1) for b in economic.ledger.baskets),
        None, None, (), digest((VERSION, profile.profile_digest, economic.state_digest)),
    )


def _check(state, expected_revision, at):
    revision(expected_revision)
    at = timestamp(at)
    if expected_revision != state.revision or at < state.as_of:
        raise ValueError("stale revision or backdated signal event")
    return at


def _finish(state, at, body, **changes):
    candidate = replace(state, revision=state.revision + 1, as_of=at, **changes)
    return replace(candidate, audit_head=digest((
        VERSION, state.audit_head, body, at, candidate.state_digest,
    )))


@precise
def _protect(profile, signal, basket, trade_price, *, evaluate_price=True):
    if not basket.quantity:
        return signal
    # A fill or funding receipt is not a new trade-price observation. In
    # particular a cheap fill cannot turn its preceding close into +5% profit.
    if not evaluate_price and not signal.protected:
        return signal
    reasons = list(signal.exit_reasons)
    if evaluate_price and trade_price <= basket.first_fill * D(".45"):
        reasons.append("first_fill_emergency_exit")
    if evaluate_price and signal.stop is not None and trade_price <= signal.stop:
        reasons.append("protective_stop_crossed")
    if not signal.protected and trade_price < basket.average_entry * D("1.05"):
        return replace(signal, exit_reasons=tuple(dict.fromkeys(reasons)))
    contract = profile.plan.contracts[profile.plan.symbols.index(signal.symbol)]
    # Whole-cycle net floor, including already realized partial exits and signed funding.
    numerator = (basket.quantity * basket.average_entry + basket.entry_fees + basket.exit_fees
                 - basket.realized_price_pnl - basket.funding_net)
    floor = max(ZERO, numerator) / (
        basket.quantity * (1 - contract.protective_exit_fee_rate) * (1 - profile.slippage))
    candidates = [floor]
    if signal.stop is not None:
        candidates.append(signal.stop)
    indicator = signal.indicator
    if (indicator.bullish and indicator.supertrend is not None
            and ZERO < indicator.supertrend < trade_price):
        candidates.append(indicator.supertrend)
    stop = max(candidates)
    if evaluate_price and trade_price <= stop:
        reasons.append("net_breakeven_floor_crossed")
    return replace(signal, protected=True, rearmed=False, stop=stop,
                   exit_reasons=tuple(dict.fromkeys(reasons)))


@precise
def replay_frame(state: SignalReplayState, frame: H4Frame, expected_revision: int,
                 observed_at: datetime) -> SignalReplayState:
    observed_at = _check(state, expected_revision, observed_at)
    if not isinstance(frame, H4Frame):
        raise ValueError("typed futures frame required")
    symbols = state.profile.plan.symbols
    if (tuple(b.symbol for b in frame.trade) != tuple(f"{s}:USDT-M:trade" for s in symbols)
            or tuple(b.symbol for b in frame.mark) != tuple(f"{s}:USDT-M:mark" for s in symbols)):
        raise ValueError("complete canonical native futures price kinds required")
    if observed_at < frame.close_time:
        raise ValueError("unfinished H4 frame")
    if state.last_frame is not None:
        if frame == state.last_frame:
            return state
        if frame.close_time != state.last_frame.close_time + timedelta(hours=4):
            raise ValueError("revised, old or gapped H4 frame")
    if frame.close_time <= state.economic.as_of:
        raise ValueError("frame predates already booked evidence")
    economic = record_ledger_event(
        state.economic, MarkBatch(tuple(LedgerMark(s, b.close) for s, b in zip(
            symbols, frame.mark, strict=True))), "mark-" + frame.frame_digest,
        state.economic.revision, frame.close_time,
    ).state
    midnight = frame.close_time.replace(hour=0, minute=0, second=0, microsecond=0)
    if midnight > economic.ledger.day_started_at:
        # Never invent a missing midnight from a later intraday close.
        if frame.close_time != midnight:
            if not economic.ledger.halted:
                raise ValueError("missing exact midnight pre-fill valuation")
        elif economic.ledger.equity > 0:
            economic = record_ledger_event(
                economic, DailyBasis(economic.ledger.equity, frame.frame_digest),
                "day-" + frame.frame_digest, economic.revision, midnight,
            ).state
        # Nonpositive equity cannot supply the positive DailyBasis contract.
        # Keep known gap marks and latched halts without inventing a new basis.
    signals = []
    for signal, trade, basket in zip(state.signals, frame.trade, economic.ledger.baskets, strict=True):
        indicator = advance(signal.indicator, trade, IndicatorParameters())
        below = indicator.rsi is not None and indicator.rsi < 30
        signal = replace(signal, indicator=indicator,
                         below_count=signal.below_count + 1 if below else 0,
                         rearmed=signal.rearmed or bool(basket.quantity and indicator.rsi is not None
                                                       and indicator.rsi > 30))
        signal = _protect(state.profile, signal, basket, trade.close)
        if economic.ledger.halted and basket.quantity:
            signal = replace(signal, exit_reasons=tuple(dict.fromkeys((
                *signal.exit_reasons, "account_risk_exit_required",
            ))))
        signals.append(signal)
    return _finish(state, observed_at, ("frame", frame.frame_digest), economic=economic,
                   last_frame=frame, signals=tuple(signals))


@precise
def reserve_signal(state: SignalReplayState, symbol: str, intent_id: str,
                   expected_revision: int, at: datetime) -> SignalReplayState:
    at = _check(state, expected_revision, at)
    if state.quarantine or state.last_frame is None:
        raise ValueError("quarantined state or missing causal frame")
    if not timedelta(0) <= at - state.last_frame.close_time <= timedelta(seconds=30):
        raise ValueError("stale H4 signal")
    index = state.profile.plan.symbols.index(symbol)
    signal, basket = state.signals[index], state.economic.ledger.baskets[index]
    stage = len(signal.stages) + 1
    rsi = signal.indicator.rsi
    if signal.protected or signal.exit_reasons or stage > 5 or rsi is None or rsi >= 30:
        raise ValueError("no regular entry signal")
    if (stage == 1 and (signal.below_count < 2 or basket.quantity)
            or stage > 1 and (not signal.rearmed or not basket.quantity
                             or basket.cycle != signal.cycle)):
        raise ValueError("first-entry confirmation or actual-fill rearm missing")
    price = state.last_frame.trade[index].close * (1 + state.profile.slippage)
    if stage > 1 and price > signal.stages[-1].vwap * D(".95"):
        raise ValueError("next maximum fill price exceeds actual-stage five-percent drop")
    plan, contract = state.profile.plan, state.profile.plan.contracts[index]
    stage_margin = state.profile.stage_margins(symbol)[stage - 1]
    buffer = state.profile.margin_buffers[index][1] if stage == 1 else ZERO
    quantity = floor_step(stage_margin * 2 / price, contract.quantity_step)
    request = FuturesPurchase(plan.tenant_id, plan.account_id, plan.plan_digest,
                              state.economic.revision, symbol, quantity, price,
                              stage_margin + buffer, D("2"))
    economic = reserve_purchase(state.economic, request, intent_id, at).state
    binding = SignalBinding(
        state.profile.profile_digest, symbol, signal.cycle, stage, intent_id,
        digest((state.last_frame.frame_digest, signal)), state.last_frame.close_time,
        stage_margin, buffer, request,
    )
    return _finish(state, at, ("reserve-signal", binding), economic=economic, binding=binding)


def replay_attempt(state, intent_id, order_id, expected_revision, at):
    at = _check(state, expected_revision, at)
    if state.quarantine or state.binding is None:
        raise ValueError("own unquarantined signal intent required")
    # Reassess the frozen intent immediately before recording an unknown attempt.
    from .futures_pending import assess_ledger_purchase
    view = replace(state.economic, pending=None)
    request = replace(state.binding.request, expected_revision=view.revision)
    signal = state.signals[state.profile.plan.symbols.index(state.binding.symbol)]
    if (at - state.binding.signal_time > timedelta(seconds=30)
            or state.last_frame.close_time != state.binding.signal_time
            or signal.protected or signal.exit_reasons
            or not assess_ledger_purchase(view, request, at).allowed):
        raise ValueError("stale or no longer covered signal intent")
    economic = record_order_attempt(state.economic, intent_id, order_id,
                                    state.economic.revision, at).state
    return _finish(state, at, ("attempt", intent_id, order_id), economic=economic)


def replay_cancel_unattempted(state, intent_id, expected_revision, at):
    at = _check(state, expected_revision, at)
    economic = cancel_unattempted(state.economic, intent_id, state.economic.revision, at).state
    return _finish(state, at, ("cancel-unattempted", intent_id), economic=economic, binding=None)


@precise
def replay_fill(state, payload, order_id, fill_id, expected_revision, at):
    """Known outcomes always book; violations quarantine rather than erase real money."""
    at = _check(state, expected_revision, at)
    economic = record_fill(state.economic, payload, order_id, fill_id,
                           state.economic.revision, at).state
    binding, quarantine = state.binding, list(state.quarantine)
    signals = list(state.signals)
    index = state.profile.plan.symbols.index(payload.symbol)
    basket = economic.ledger.baskets[index]
    if isinstance(payload, EntryFill):
        p = state.economic.pending
        if (binding is None or p is None or p.order_id != order_id
                or binding.symbol != payload.symbol or binding.cycle != basket.cycle):
            quarantine.append("entry_outside_signal_cycle")
        else:
            if signals[index].protected or signals[index].exit_reasons:
                quarantine.append("entry_after_protection_or_exit")
            if binding.filled_quantity == 0 and payload.posted_margin != binding.request.posted_margin:
                quarantine.append("declared_first_fragment_margin_missing")
            binding = replace(binding, filled_quantity=binding.filled_quantity + payload.quantity,
                              filled_notional=binding.filled_notional + payload.quantity * payload.price)
            plan = state.profile.plan
            scenario = ContinuationScenario(
                plan.tenant_id, plan.account_id, plan.plan_digest, economic.revision,
                p.intent_id, order_id, tuple(LedgerMark(b.symbol, min(
                    b.mark, b.first_fill * D(".5") if b.quantity else b.mark,
                )) for b in economic.ledger.baskets),
            )
            coverage = assess_futures_continuation(economic, scenario, at)
            # A fully filled order has no continuation. Its actual-anchor stress
            # is still calculated by the same bounds; retain every economic failure.
            if any(reason != "no_remaining_quantity" for reason in coverage.reasons):
                quarantine.append("known_fill_continuation_not_covered")
        signals[index] = replace(signals[index], below_count=0, rearmed=False)
    if economic.reconciliation_halts:
        quarantine.extend(economic.reconciliation_halts)
    signals = _refresh_positions(state, economic, tuple(signals), binding)
    return _finish(state, at, ("fill", order_id, fill_id, payload), economic=economic,
                   binding=binding, signals=signals, quarantine=tuple(dict.fromkeys(quarantine)))


def _refresh_positions(state, economic, signals, binding):
    result = []
    for signal, basket in zip(signals, economic.ledger.baskets, strict=True):
        if not basket.quantity and signal.stages and (binding is None or binding.symbol != signal.symbol):
            signal = SymbolSignals(signal.symbol, basket.cycle + 1, signal.indicator,
                                   exit_reasons=signal.exit_reasons if economic.ledger.halted else ())
        elif basket.quantity:
            if state.last_frame is not None:
                signal = _protect(state.profile, signal, basket,
                                  state.last_frame.trade[state.profile.plan.symbols.index(signal.symbol)].close,
                                  evaluate_price=False)
            if economic.ledger.halted:
                signal = replace(signal, exit_reasons=tuple(dict.fromkeys((
                    *signal.exit_reasons, "account_risk_exit_required",
                ))))
        result.append(signal)
    return tuple(result)


@precise
def replay_terminal(state, resolution: OrderResolution, expected_revision, at):
    at = _check(state, expected_revision, at)
    economic = reconcile_order(state.economic, resolution, state.economic.revision, at).state
    binding, signals, quarantine = state.binding, list(state.signals), list(state.quarantine)
    index = state.profile.plan.symbols.index(binding.symbol)
    signal, basket = signals[index], economic.ledger.baskets[index]
    if resolution.filled_quantity:
        if (binding.cycle != signal.cycle or binding.cycle != basket.cycle
                or binding.stage != len(signal.stages) + 1
                or binding.filled_quantity != resolution.filled_quantity):
            quarantine.append("terminal_outside_signal_cycle")
        else:
            completed = CompletedStage(binding.stage, binding.filled_quantity,
                                       binding.filled_notional, binding.intent_id,
                                       resolution.evidence_digest)
            signals[index] = replace(signal, stages=(*signal.stages, completed),
                                     manual_notice=binding.stage == 5 or signal.manual_notice)
    signals = _refresh_positions(state, economic, tuple(signals), None)
    return _finish(state, at, ("terminal", resolution), economic=economic, binding=None,
                   signals=signals, quarantine=tuple(dict.fromkeys(quarantine)))


@precise
def replay_economic_event(state, payload, event_id, expected_revision, at):
    """Only explicitly supplied funding/postings; no invented zero funding or topups."""
    at = _check(state, expected_revision, at)
    if type(payload) not in (FundingSettlement, MarginPosting):
        raise ValueError("marks/day basis are exclusively bound to complete H4 frames")
    economic = record_ledger_event(state.economic, payload, event_id,
                                   state.economic.revision, at).state
    return _finish(state, at, ("economic-evidence", event_id, payload), economic=economic,
                   signals=_refresh_positions(state, economic, state.signals, state.binding))
