"""Joint offline research reference, separate from frozen single-asset jobs."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from decimal import Decimal
from itertools import groupby, islice
from typing import Iterable

from .models import Candle, DomainEvent, EngineState, Fill, Side, floor_step, precise
from .simulator import BacktestResult, EquityPoint, PaperSimulator
from .snapshot import digest

D = Decimal
PORTFOLIO_VERSION = "portfolio-reference/1"
EXECUTION_POLICY = (
    "complete_aligned_h4; config_symbol_priority; atomic_quote_batch; "
    "previous_close_midnight_bid_baseline; next_open_buy; "
    "joint_low_then_high_then_close; no_terminal_flatten"
)
BENCHMARK_POLICY = (
    "first_open_maximum_basket_principal; same_entry_costs_and_rounding; "
    "passive_no_risk_exits; bid_marked_no_terminal_flatten"
)
MAX_BARS_PER_ASSET = 10000


@dataclass(frozen=True)
class CapitalPoint:
    at: datetime
    cash: Decimal
    position_principal: Decimal
    position_market_value: Decimal
    pending_buy_principal: Decimal
    active_baskets: int
    remaining_manual_principal: Decimal


@dataclass(frozen=True)
class BenchmarkResult:
    policy: str
    equity_curve: tuple[EquityPoint, ...]
    net_pnl: Decimal
    maximum_drawdown_fraction: Decimal
    entry_principal: Decimal
    entry_fees: Decimal
    cash: Decimal
    quantities: tuple[tuple[str, Decimal], ...]
    maximum_initial_loss_fraction: Decimal
    maximum_daily_loss_fraction: Decimal


@dataclass(frozen=True)
class PortfolioBacktestResult:
    schema_version: str
    policy_digest: str
    execution_policy: str
    symbols: tuple[str, ...]
    simulation: BacktestResult
    capital_curve: tuple[CapitalPoint, ...]
    net_return_fraction: Decimal
    planned_principal: Decimal
    planned_cost_reserve: Decimal
    initially_unassigned_capital: Decimal
    maximum_position_principal: Decimal
    time_weighted_position_principal: Decimal
    time_weighted_principal_fraction: Decimal
    peak_active_baskets: int
    total_entry_fees: Decimal
    total_exit_fees: Decimal
    benchmark: BenchmarkResult
    validation_status: str = "not_evaluated"


@precise
def _drawdown(curve: tuple[EquityPoint, ...]) -> Decimal:
    peak, maximum = curve[0].equity, D("0")
    for point in curve:
        peak = max(peak, point.equity)
        maximum = max(maximum, (peak - point.equity) / peak)
    return maximum


@precise
def _loss_limits(curve: tuple[EquityPoint, ...], initial: Decimal) -> tuple[Decimal, Decimal]:
    """Loss from start and each midnight baseline, distinct from peak drawdown."""
    minimum = min(p.equity for p in curve)
    initial_loss = max(D("0"), (initial - minimum) / initial)
    day, baseline, maximum = curve[0].at.date(), initial, D("0")
    for point in curve:
        # A midnight close belongs to the just-finished day for this check.
        # The following open (same timestamp) uses the newly frozen baseline.
        maximum = max(maximum, (baseline - point.equity) / baseline)
        if point.at.date() != day:
            day, baseline = point.at.date(), point.equity
    return initial_loss, maximum


@dataclass(frozen=True)
class PortfolioSimulator:
    """Requires every configured asset throughout one common complete window.

    Version one deliberately uses the existing BTC/ETH spot configuration.
    No allocator, additional assets, larger budgets or external caller is
    enabled by this reference. Its passive benchmark uses the maximum planned
    principal; it is NOT exposure-matched or governed by strategy risk exits.
    """

    simulator: PaperSimulator = PaperSimulator()

    def policy(self) -> dict:
        return {
            "version": PORTFOLIO_VERSION,
            "execution": EXECUTION_POLICY,
            "benchmark": BENCHMARK_POLICY,
            "symbol_priority": self.simulator.engine.config.symbols,
            "maximum_bars_per_asset": MAX_BARS_PER_ASSET,
            "configuration_digest": digest((
                self.simulator.engine.config, self.simulator.engine.instrument_rules,
            )),
            "cost_digest": digest(self.simulator.costs),
        }

    def _history(self, candles: Iterable[Candle]) -> tuple[Candle, ...]:
        symbols = self.simulator.engine.config.symbols
        if len(symbols) < 2:
            raise ValueError("joint reference requires at least two configured assets")
        limit = MAX_BARS_PER_ASSET * len(symbols)
        bars = tuple(islice(candles, limit + 1))
        if not bars or len(bars) > limit or any(not isinstance(b, Candle) for b in bars):
            raise ValueError("bounded H4 candles required")
        if {b.symbol for b in bars} != set(symbols):
            raise ValueError("history must contain exactly the configured assets")
        order = {symbol: index for index, symbol in enumerate(symbols)}
        bars = tuple(sorted(bars, key=lambda b: (b.open_time, order[b.symbol])))
        times: tuple[datetime, ...] | None = None
        for symbol in symbols:
            sequence = tuple(b for b in bars if b.symbol == symbol)
            if len(sequence) > MAX_BARS_PER_ASSET:
                raise ValueError("too many H4 candles per asset")
            if any(b.open_time != a.close_time for a, b in zip(sequence, sequence[1:])):
                raise ValueError("duplicate or gapped asset history")
            current = tuple(b.open_time for b in sequence)
            if times is not None and current != times:
                raise ValueError("asset histories must have identical H4 windows")
            times = current
        return bars

    @precise
    def _capital(self, state: EngineState, at: datetime) -> CapitalPoint:
        engine = self.simulator.engine
        active = tuple(b for b in state.baskets if b.quantity > 0)
        return CapitalPoint(
            at, state.account.cash,
            # Entries hold the acquisition cost; principal_spent is lifetime
            # turnover within a basket and is not reduced by a partial sale.
            sum((b.principal_spent * b.quantity
                 / sum((e.quantity for e in b.entries), D("0")) for b in active), D("0")),
            sum((b.quantity * state.quote(b.symbol).bid for b in active), D("0")),
            sum((max(D("0"), o.intent.maximum_quote - o.filled_principal)
                 for o in state.orders if o.unresolved and o.intent.side == Side.BUY), D("0")),
            len(active),
            sum((min(max(D("0"), engine._cycle_budget(state, b.symbol)[0] - b.principal_spent),
                     max(D("0"), engine._cycle_budget(state, b.symbol)[2][5] - sum(
                         (e.principal for e in b.entries if e.number == 6), D("0"))))
                 for b in active), D("0")),
        )

    @precise
    def run(self, candles: Iterable[Candle], *, tenant_id: str = "research",
            account_id: str = "portfolio-reference") -> PortfolioBacktestResult:
        bars = self._history(candles)
        simulator, engine = self.simulator, self.simulator.engine
        symbols = engine.config.symbols
        state = engine.start(tenant_id, account_id, bars[0].open_time)
        curve: list[EquityPoint] = []
        capital: list[CapitalPoint] = []
        fills: list[Fill] = []
        events: list[DomainEvent] = []
        benchmark_curve: list[EquityPoint] = []
        benchmark_cash = engine.config.initial_equity
        benchmark_quantities: dict[str, Decimal] = {}
        benchmark_principal, benchmark_fees = D("0"), D("0")
        initial = True

        def record(at: datetime) -> None:
            curve.append(EquityPoint(at, state.equity))
            capital.append(self._capital(state, at))
            marked = benchmark_cash + sum(
                (benchmark_quantities.get(symbol, D("0")) * state.quote(symbol).bid
                 for symbol in symbols), D("0"),
            )
            benchmark_curve.append(EquityPoint(at, marked))

        for opened, grouping in groupby(bars, lambda b: b.open_time):
            group = tuple(grouping)
            for at, field, buys in (
                (opened, "open", True),
                (opened + timedelta(hours=1), "low", False),
                (opened + timedelta(hours=2), "high", False),
                (opened + timedelta(hours=4), "close", False),
            ):
                batch = tuple(simulator.quote(b.symbol, at, getattr(b, field)) for b in group)
                closing_day = (
                    field == "close" and at.hour == 0
                    and state.account.trading_day != at.date()
                )
                transition = engine.on_quotes(state, batch, closing_day=closing_day)
                state = transition.state
                events.extend(transition.events)
                if at.hour == 0:
                    state = engine.reset_day(state, at)
                if initial:
                    # Record the common initial equity before benchmark costs.
                    record(at)
                    for symbol in symbols:
                        rules = engine.rules(symbol)
                        price = state.quote(symbol).ask * (1 + simulator.costs.slippage_fraction)
                        budget = floor_step(engine.config.basket_principal, rules.quote_step)
                        quantity = floor_step(budget / price, rules.quantity_step)
                        principal = quantity * price
                        if quantity <= 0 or principal < rules.minimum_quote:
                            raise ValueError("benchmark entry is below instrument minimum")
                        fees = principal * simulator.costs.fee_rate
                        if fees > engine.config.basket_cost_reserve:
                            raise ValueError("benchmark fees exceed planned cost reserve")
                        benchmark_quantities[symbol] = quantity
                        benchmark_principal += principal
                        benchmark_fees += fees
                        benchmark_cash -= principal + fees
                    initial = False
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
        for order in state.orders:
            if order.unresolved and order.intent.side == Side.BUY:
                state = engine.reconcile_cancelled(state, order.intent.intent_id).state
        # Terminal pending buys are cancelled, without inventing another price.
        capital[-1] = self._capital(state, capital[-1].at)
        gains = sum((b.net_pnl for b in state.closed_baskets if b.net_pnl > 0), D("0"))
        losses = -sum((b.net_pnl for b in state.closed_baskets if b.net_pnl < 0), D("0"))
        net = state.equity - state.account.initial_equity
        simulation = BacktestResult(
            engine.config.version, state.configuration_digest, digest(bars), digest(simulator.costs),
            state, tuple(curve), tuple(events), tuple(fills), net, _drawdown(tuple(curve)),
            gains / losses if losses else None, len(state.closed_baskets),
            execution_assumption=EXECUTION_POLICY,
        )
        # Left-continuous sampled acquisition principal over explicit synthetic
        # phase times; exact durations, never a mean of duplicated boundaries.
        seconds = D(str((capital[-1].at - capital[0].at).total_seconds()))
        weighted = sum(
            (a.position_principal * D(str((b.at - a.at).total_seconds()))
             for a, b in zip(capital, capital[1:])), D("0"),
        ) / seconds
        entry_ids = {o.intent.intent_id for o in state.orders if o.intent.side == Side.BUY}
        planned = engine.config.basket_principal * len(symbols)
        reserve = engine.config.basket_cost_reserve * len(symbols)
        return PortfolioBacktestResult(
            PORTFOLIO_VERSION, digest(self.policy()), EXECUTION_POLICY, symbols, simulation,
            tuple(capital), net / state.account.initial_equity, planned, reserve,
            state.account.initial_equity - planned - reserve,
            max(p.position_principal for p in capital), weighted,
            weighted / state.account.initial_equity,
            max(p.active_baskets for p in capital),
            sum((f.fee for f in fills if f.intent_id in entry_ids), D("0")),
            sum((f.fee for f in fills if f.intent_id not in entry_ids), D("0")),
            BenchmarkResult(
                BENCHMARK_POLICY, tuple(benchmark_curve),
                benchmark_curve[-1].equity - state.account.initial_equity,
                _drawdown(tuple(benchmark_curve)), benchmark_principal, benchmark_fees,
                benchmark_cash, tuple((s, benchmark_quantities[s]) for s in symbols),
                *_loss_limits(tuple(benchmark_curve), state.account.initial_equity),
            ),
        )
