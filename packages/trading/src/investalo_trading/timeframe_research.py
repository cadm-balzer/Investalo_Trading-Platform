"""Offline H1/H4 comparison with the approved fixed-slot economics."""
from dataclasses import dataclass, fields, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from itertools import groupby, islice

from .identity_history import IdentityHistory
from .models import Candle, DomainEvent, IndicatorState, Side, positive, precise, utc
from .pool_research import (
    APPROVED_CANDIDATES, PoolConfig, PoolEngine, PoolInstrumentRules, PoolPlan,
    PoolState,
)
from .portfolio import PortfolioSimulator, _drawdown
from .simulator import EquityPoint, PaperSimulator, SimulationCosts
from .snapshot import digest, primitive

VERSION = "fixed-slot-timeframe-research/1"
MAX_BARS = 30_000
D = Decimal
GAP_START = datetime(2023, 3, 24, 12, tzinfo=timezone.utc)
GAP_END = GAP_START + timedelta(hours=4)


@dataclass(frozen=True)
class ResearchCandle(Candle):
    """Own research type; ordinary Candle continues to accept H4 only."""

    def __post_init__(self):
        opened, closed = utc(self.open_time), utc(self.close_time)
        hours = (closed - opened).total_seconds() / 3600
        if hours not in (1, 4) or opened.hour % int(hours) or any(
                (opened.minute, opened.second, opened.microsecond)):
            raise ValueError("aligned H1 or H4 research candle required")
        object.__setattr__(self, "open_time", opened)
        object.__setattr__(self, "close_time", closed)
        for name in ("open", "high", "low", "close"):
            positive(getattr(self, name), name)
        if self.high < max(self.open, self.close, self.low) or self.low > min(self.open, self.close):
            raise ValueError("inconsistent OHLC")


@dataclass(frozen=True, init=False)
class TimeframeConfig(PoolConfig):
    hours: int

    def __init__(self, plan, costs, hours):
        if type(hours) is not int or hours not in (1, 4):
            raise ValueError("H1 or H4 required")
        super().__init__(plan, costs)
        object.__setattr__(self, "version", VERSION)
        object.__setattr__(self, "hours", hours)


@dataclass(frozen=True)
class TimeframeState(PoolState):
    bar_evidence: tuple[IdentityHistory, ...] = ()


@dataclass(frozen=True)
class TimeframeEngine(PoolEngine):
    def __post_init__(self):
        super().__post_init__()
        if not isinstance(self.config, TimeframeConfig):
            raise ValueError("timeframe research configuration required")
        object.__setattr__(self, "_research_config_digest", digest((self.config, self.instrument_rules)))

    def _configuration_digest(self):
        # This engine, its config, plan and instrument tuple are immutable.
        # Keep the default engine's fingerprint calculation unchanged.
        return self._research_config_digest

    def start(self, tenant_id, account_id, at):
        base = super().start(tenant_id, account_id, at)
        return TimeframeState(
            **{f.name: getattr(base, f.name) for f in fields(PoolState)},
            bar_evidence=tuple(IdentityHistory("event", MAX_BARS) for _ in self.config.symbols),
        )

    def _validate(self, state, symbol=None):
        super()._validate(state, symbol)
        if (not isinstance(state, TimeframeState) or state.processed_bars
                or len(state.bar_evidence) != len(self.config.symbols)
                or any(not isinstance(h, IdentityHistory) or h.namespace != "event"
                       or h.capacity != MAX_BARS for h in state.bar_evidence)):
            raise ValueError("complete research bar evidence required")

    def _bar_interval(self):
        return timedelta(hours=self.config.hours)

    def _seen_bar(self, state, bar_id, bar_digest):
        symbol = bar_id.split(":", 1)[0]
        evidence = state.bar_evidence[self.config.symbols.index(symbol)]
        # A changed earlier candle falls through to the unchanged chronological
        # rejection in the core. Every exact earlier input remains idempotent.
        return f"{bar_id}:{bar_digest}" in evidence

    def _remember_bar(self, state, symbol, bar_id, bar_digest):
        index = self.config.symbols.index(symbol)
        return replace(state, bar_evidence=tuple(
            h.append(f"{bar_id}:{bar_digest}") if i == index else h
            for i, h in enumerate(state.bar_evidence)
        ))

    def restart_after_gap(self, state):
        """Only the declared shared source gap; retain positions and stops."""
        self._validate(state)
        for order in state.orders:
            if order.unresolved and order.intent.side == Side.BUY:
                state = self.reconcile_cancelled(state, order.intent.intent_id).state
        return replace(state, baskets=tuple(replace(
            b, indicators=IndicatorState(), sub30_count=0, rearmed=False,
            last_bar_open=None, last_bar_digest=None,
        ) for b in state.baskets))


def aggregate_h4(hourly):
    """Closed four-hour OHLC from exactly four complete UTC hourly candles."""
    hourly = tuple(hourly)
    if (not hourly or len(hourly) % 4 or hourly[0].open_time.hour % 4
            or len({b.symbol for b in hourly}) != 1
            or any(b.close_time - b.open_time != timedelta(hours=1) for b in hourly)
            or any(a.close_time != b.open_time for a, b in zip(hourly, hourly[1:]))):
        raise ValueError("complete contiguous hourly asset required")
    return tuple(ResearchCandle(
        group[0].symbol, group[0].open_time, group[-1].close_time,
        group[0].open, max(b.high for b in group), min(b.low for b in group), group[-1].close,
    ) for offset in range(0, len(hourly), 4) for group in (hourly[offset:offset + 4],))


@dataclass(frozen=True)
class TimeframeReplay:
    plan: PoolPlan
    hours: int
    costs: SimulationCosts = SimulationCosts()

    def engine(self):
        if any(s not in APPROVED_CANDIDATES for s in self.plan.symbols):
            raise ValueError("approved candidates required")
        return TimeframeEngine(
            TimeframeConfig(self.plan, self.costs, self.hours),
            tuple(PoolInstrumentRules(s) for s in self.plan.symbols),
            self.costs.fee_rate, self.costs.slippage_fraction,
        )

    def policy(self):
        engine = self.engine()
        return {
            "version": VERSION, "plan": primitive(self.plan), "hours": self.hours,
            "configuration_digest": digest((engine.config, engine.instrument_rules)),
            "costs": primitive(self.costs), "maximum_bars_per_asset": MAX_BARS,
            "execution": "next_open_buy; synchronized_open_low_high_close; low_at_quarter; high_at_half",
            "day": "previous_close_midnight_bid_then_reset_before_open",
            "signals": "RSI14_Wilder; two_below30_first; above30_rearm_then_below30_and_5pct_actual_fill",
            "protection": "same_timeframe_Supertrend_ATR10_Wilder_times3; net_floor; no_buys_after_activation",
            "capital": "fixed_reusable_slots; one_percent_cost_reserve; full_initial_capital; no_profit_etapes",
            "risk": "independent_6pct_daily_8pct_initial; correlated_minus50pct_first_fill_before_buy",
            "manual": "sixth_not_fabricated", "execution_enabled": False,
            "source_gap": {
                "start": GAP_START.isoformat(), "end_exclusive": GAP_END.isoformat(),
                "policy": "same_block_omitted_all_assets; cancel_pending_buys; restart_Wilder_and_RSI_confirmation; retain_positions_stops_and_evidence",
            },
        }

    def history(self, candles):
        engine = self.engine()
        limit = MAX_BARS * len(self.plan.symbols)
        bars = tuple(islice(candles, limit + 1))
        if (not bars or len(bars) > limit
                or any(not isinstance(b, ResearchCandle) for b in bars)
                or {b.symbol for b in bars} != set(self.plan.symbols)):
            raise ValueError("bounded complete research cohort required")
        if any(b.open_time < GAP_END and b.close_time > GAP_START for b in bars):
            raise ValueError("declared source interruption block must be omitted")
        order = {s: i for i, s in enumerate(self.plan.symbols)}
        bars = tuple(sorted(bars, key=lambda b: (b.open_time, order[b.symbol])))
        axes = None
        for symbol in self.plan.symbols:
            own = tuple(b for b in bars if b.symbol == symbol)
            if len(own) > MAX_BARS:
                raise ValueError("too many research bars")
            for bar in own:
                engine._validate_bar(bar)
            if any(a.close_time != b.open_time and
                   (a.close_time, b.open_time) != (GAP_START, GAP_END)
                   for a, b in zip(own, own[1:])):
                raise ValueError("duplicate or gapped history")
            axis = tuple(b.open_time for b in own)
            if axes is not None and axis != axes:
                raise ValueError("identical asset windows required")
            axes = axis
        return bars

    @precise
    def run(self, candles, observe=None):
        bars = self.history(candles)
        engine = self.engine()
        simulator = PaperSimulator(engine, self.costs)
        reference = PortfolioSimulator(simulator)
        state = engine.start(self.plan.tenant_id, self.plan.account_id, bars[0].open_time)
        curve, capital, fills, events = [], [], [], []
        step = timedelta(hours=self.hours)
        first_halt_at = None

        def record(at):
            nonlocal first_halt_at
            curve.append(EquityPoint(at, state.equity))
            capital.append(reference._capital(state, at))
            if state.account.halted and first_halt_at is None:
                first_halt_at = at

        record(bars[0].open_time)
        previous_close = None
        for number, (opened, grouping) in enumerate(groupby(bars, lambda b: b.open_time), 1):
            group = tuple(grouping)
            if previous_close is not None and opened != previous_close:
                state = engine.restart_after_gap(state)
                events.append(DomainEvent("research_source_gap", "", "",
                                          "declared_2023_03_24_block; indicators_restarted"))
            for at, field, buys in (
                (opened, "open", True), (opened + step / 4, "low", False),
                (opened + step / 2, "high", False), (opened + step, "close", False),
            ):
                batch = tuple(simulator.quote(b.symbol, at, getattr(b, field)) for b in group)
                transition = engine.on_quotes(
                    state, batch, closing_day=field == "close" and at.hour == 0
                    and not at.minute and state.account.trading_day != at.date(),
                )
                state = transition.state
                events.extend(transition.events)
                if at.hour == 0 and not at.minute:
                    state = engine.reset_day(state, at)
                state, new_fills, new_events = simulator.settle(state, at, buys=buys)
                fills.extend(new_fills)
                events.extend(new_events)
                if field == "close":
                    for bar in group:
                        transition = engine.on_bar(state, bar, observed_at=at)
                        state = transition.state
                        events.extend(transition.events)
                    state, new_fills, new_events = simulator.settle(state, at, buys=False)
                    fills.extend(new_fills)
                    events.extend(new_events)
                record(at)
            previous_close = opened + step
            if observe is not None and number % 1000 == 0:
                observe(number, state)
        for order in state.orders:
            if order.unresolved and order.intent.side == Side.BUY:
                state = engine.reconcile_cancelled(state, order.intent.intent_id).state
        capital[-1] = reference._capital(state, capital[-1].at)
        return {
            "state": state, "curve": tuple(curve), "capital": tuple(capital),
            "fills": tuple(fills), "events": tuple(events),
            "net_pnl": state.equity - state.account.initial_equity,
            "maximum_drawdown_fraction": _drawdown(tuple(curve)),
            "policy_digest": digest(self.policy()), "data_digest": digest(bars),
            "first_halt_at": first_halt_at,
        }
