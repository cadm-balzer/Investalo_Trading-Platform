"""Offline candidate pool, fixed reusable slots and the unchanged RSI core."""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from itertools import groupby
from typing import Iterable

from .allocation import (
    AllocationPlan, AllocationView, AssetUse, BuyReservation, PurchaseAssessment,
    PurchaseRequest, assess_purchase, identifier,
)
from .engine import CryptoEngine
from .models import (
    Candle, DomainEvent, EngineState, InstrumentRules, OrderIntent, OrderRecord,
    OrderStatus, Side, TradingRejected, Transition, floor_step, positive, precise, utc,
)
from .portfolio import (
    CapitalPoint, EXECUTION_POLICY, MAX_BARS_PER_ASSET, PortfolioSimulator, _drawdown,
)
from .simulator import BacktestResult, EquityPoint, PaperSimulator, SimulationCosts
from .snapshot import digest
from .staged_research import (
    ADMISSION_PREFIX, AllocatedResearchEngine, ResearchConfig, ResearchState,
)

D = Decimal
POOL_VERSION = "candidate-pool-rsi-research/1"
APPROVED_CANDIDATES = tuple(sorted(
    c + "USDT" for c in
    ("BTC", "ETH", "SOL", "BNB", "XRP", "ZEC", "HYPE", "XMR",
     "LINK", "XLM", "NEAR", "BCH", "LTC", "UNI")
))
NORMAL_EXITS = ("trailing_stop", "protective_floor_crossed")


@dataclass(frozen=True)
class PoolPlan:
    tenant_id: str
    account_id: str
    symbols: tuple[str, ...]
    initial_capital: Decimal
    cost_ratio: Decimal
    capacity: int = 5
    quantum: Decimal = D("0.00000001")

    def __post_init__(self) -> None:
        if type(self.capacity) is not int or not 3 <= self.capacity <= 5:
            raise ValueError("three to five funded slots required")
        if type(self.symbols) is not tuple or not self.capacity <= len(self.symbols) <= 32:
            raise ValueError("bounded candidate pool must cover funded capacity")
        for symbol in self.symbols:
            identifier(symbol)
        if len(set(self.symbols)) != len(self.symbols):
            raise ValueError("duplicate candidate")
        object.__setattr__(self, "symbols", tuple(sorted(self.symbols)))
        # Reuse the unchanged, independently versioned slot economics.
        self.slot_plan

    @property
    def slot_plan(self) -> AllocationPlan:
        return AllocationPlan(
            self.tenant_id, self.account_id, tuple(f"SLOT{i}" for i in range(self.capacity)),
            self.initial_capital, self.cost_ratio, self.quantum,
        )

    @property
    def slot_principal(self) -> Decimal:
        return self.slot_plan.slot_principal

    @property
    def slot_costs(self) -> Decimal:
        return self.slot_plan.slot_costs

    @property
    def remainder(self) -> Decimal:
        return self.slot_plan.remainder

    @property
    def stages(self) -> tuple[Decimal, ...]:
        return self.slot_plan.stages

    @property
    def plan_digest(self) -> str:
        return digest((POOL_VERSION, self, self.slot_plan.plan_digest, NORMAL_EXITS,
                       "fixed_budget; fresh_rsi; risk_quarantine; canonical_priority"))


@dataclass(frozen=True, init=False)
class PoolConfig(ResearchConfig):
    def __init__(self, plan: PoolPlan, costs: SimulationCosts):
        if not isinstance(plan, PoolPlan):
            raise ValueError("candidate pool plan required")
        super().__init__(plan, costs)
        object.__setattr__(self, "version", POOL_VERSION)


@dataclass(frozen=True)
class PoolInstrumentRules(InstrumentRules):
    """Separate contract; existing v1 digests and metadata remain unchanged."""

    minimum_quantity: Decimal = D("0")

    def __post_init__(self) -> None:
        super().__post_init__()
        positive(self.minimum_quantity, "minimum_quantity", zero=True)


@dataclass(frozen=True)
class Slot:
    index: int
    symbol: str | None = None
    basket_id: str | None = None
    exit_reason: str | None = None
    quarantined: bool = False


@dataclass(frozen=True)
class CycleReceipt:
    slot: int
    symbol: str
    basket_id: str
    principal: Decimal
    fees: Decimal
    net_pnl: Decimal
    exit_reason: str | None
    released: bool


@dataclass(frozen=True)
class PoolState(ResearchState):
    slots: tuple[Slot, ...] = ()
    cycles: tuple[CycleReceipt, ...] = ()


@dataclass(frozen=True)
class PoolEngine(AllocatedResearchEngine):
    def __post_init__(self) -> None:
        super().__post_init__()
        if not isinstance(self.config, PoolConfig):
            raise ValueError("pool configuration required")
        if (tuple(r.symbol for r in self.instrument_rules) != self.config.symbols
                or any(not isinstance(r, PoolInstrumentRules) for r in self.instrument_rules)):
            raise ValueError("complete canonical pool instrument rules required")

    def start(self, tenant_id: str, account_id: str, at: datetime) -> PoolState:
        base = super().start(tenant_id, account_id, at)
        return PoolState(**{f.name: getattr(base, f.name) for f in fields(ResearchState)},
                         slots=tuple(Slot(i) for i in range(self.config.plan.capacity)))

    def _validate(self, state: EngineState, symbol: str | None = None) -> None:
        super()._validate(state, symbol)
        if (not isinstance(state, PoolState) or type(state.slots) is not tuple
                or tuple(s.index for s in state.slots) != tuple(range(self._slot_capacity(state)))):
            raise ValueError("complete immutable slot registry required")
        assigned = set()
        for slot in state.slots:
            if type(slot.quarantined) is not bool:
                raise ValueError("invalid quarantine flag")
            if slot.symbol is None:
                if slot.basket_id is not None or slot.exit_reason is not None or slot.quarantined:
                    raise ValueError("empty slot contains cycle state")
            else:
                if slot.symbol not in self.config.symbols or slot.symbol in assigned:
                    raise ValueError("foreign or duplicate slot assignment")
                assigned.add(slot.symbol)
                if slot.basket_id != state.basket(slot.symbol).basket_id:
                    raise ValueError("stale slot cycle")
        for basket in state.baskets:
            if (basket.quantity or basket.entries or basket.exiting or self._active(state, basket)):
                if basket.symbol not in assigned:
                    raise ValueError("unassigned basket exposure")

    def _slot_capacity(self, state: PoolState) -> int:
        return self.config.plan.capacity

    def _vacant_slot(self, state: PoolState, index: int) -> Slot:
        return Slot(index)

    def _slot(self, state: PoolState, symbol: str) -> Slot | None:
        return next((s for s in state.slots if s.symbol == symbol), None)

    @precise
    def _assess(self, state: PoolState, intent: OrderIntent, now: datetime,
                *, dispatch: bool = False) -> PurchaseAssessment:
        self._validate(state)
        quotes = tuple(state.quote(s) for s in self.config.symbols)
        if any(q is None for q in quotes):
            raise TradingRejected("complete_allocation_quotes_required")
        at = quotes[0].observed_at
        if any(q.observed_at != at for q in quotes):
            raise TradingRejected("complete_allocation_mark_batch_required")
        if not timedelta(0) <= utc(now) - at <= timedelta(seconds=30):
            raise TradingRejected("stale_or_future_allocation_marks")
        slot = self._slot(state, intent.symbol)
        if slot is None or slot.quarantined:
            raise TradingRejected("funded_slot_required")
        plan = self.config.plan.slot_plan
        projected_names = plan.symbols
        assets = []
        for assigned in state.slots:
            if assigned.symbol is None:
                assets.append(AssetUse(projected_names[assigned.index], D("0"), D("0"),
                                       D("0"), D("1"), at))
            else:
                basket = state.basket(assigned.symbol)
                quote = state.quote(assigned.symbol)
                assets.append(AssetUse(
                    projected_names[assigned.index], basket.principal_spent, basket.costs_spent,
                    basket.quantity, quote.bid, at, basket.first_fill_price,
                ))

        def projected(order: OrderIntent, amount: Decimal, revision: int) -> PurchaseRequest:
            assigned = self._slot(state, order.symbol)
            if assigned is None:
                raise TradingRejected("unassigned_pending_order")
            original = self._request(state, order, amount, revision)
            return replace(original, plan_digest=plan.plan_digest,
                           symbol=projected_names[assigned.index])

        pending = []
        for index, order in enumerate(state.orders):
            if (not order.unresolved or order.intent.side != Side.BUY
                    or dispatch and order.intent.intent_id == intent.intent_id):
                continue
            remaining = order.intent.maximum_quote - order.filled_principal
            if remaining <= 0:
                raise TradingRejected("unresolved_filled_order_requires_reconciliation")
            status = "unknown" if order.filled_quantity else str(order.status)
            pending.append(BuyReservation(projected(order.intent, remaining, index), status))
        view = AllocationView(
            plan.tenant_id, plan.account_id, plan.plan_digest, len(state.orders), at,
            datetime.combine(state.account.trading_day, time(), timezone.utc),
            state.account.day_start_equity, state.account.cash, tuple(assets), tuple(pending),
            state.account.halted or any(
                o.unresolved and o.intent.side == Side.SELL and
                (o.status != OrderStatus.OPEN or o.filled_quantity > 0) for o in state.orders),
        )
        amount = intent.maximum_quote
        if dispatch:
            amount -= next(o.filled_principal for o in state.orders
                           if o.intent.intent_id == intent.intent_id)
        result = assess_purchase(plan, view, projected(intent, amount, view.revision), now)
        return replace(result, view_digest=digest((self.config.plan.plan_digest, state.slots, view)))

    def _buy(self, state: PoolState, symbol: str, stage: int, now: datetime,
             event: str, authorization: str | None = None) -> Transition:
        self._validate(state, symbol)
        slot = self._slot(state, symbol)
        if slot is not None and slot.quarantined:
            return Transition(state, events=(DomainEvent(
                "entry_blocked", symbol, "", "slot_requires_explicit_resume"),))
        candidate = state
        if slot is None:
            slot = next((s for s in state.slots if s.symbol is None), None)
            if slot is None or stage != 1:
                return Transition(state, events=(DomainEvent(
                    "entry_blocked", symbol, "", "no_free_funded_slot"),))
            assigned = replace(slot, symbol=symbol, basket_id=state.basket(symbol).basket_id)
            candidate = replace(state, slots=tuple(
                assigned if s.index == slot.index else s for s in state.slots))
        # Bypass the older adapter's intentional one-cycle restriction.
        proposed = CryptoEngine._buy(self, candidate, symbol, stage, now, event, authorization)
        if not proposed.intents:
            return replace(proposed, state=state)
        intent = proposed.intents[0]
        try:
            assessment = self._assess(candidate, intent, now)
        except TradingRejected as error:
            return Transition(state, events=(DomainEvent(
                "entry_blocked", symbol, intent.intent_id, str(error)),))
        evidence = DomainEvent("allocation_admission", symbol, intent.intent_id,
                               self._evidence(assessment, intent, now, "prepare"))
        if not assessment.allowed:
            return Transition(state, events=(evidence,))
        return replace(proposed, events=proposed.events + (evidence,))

    @precise
    def _buy_rejection_for_dispatch(self, state: PoolState, record: OrderRecord,
                                    now: datetime) -> str | None:
        reason = super()._buy_rejection_for_dispatch(state, record, now)
        if reason:
            return reason
        quote, rules = state.quote(record.intent.symbol), self.rules(record.intent.symbol)
        price = quote.ask * (1 + self.slippage_fraction)
        quantity = floor_step(
            (record.intent.maximum_quote - record.filled_principal) / price, rules.quantity_step)
        if quantity < rules.minimum_quantity or quantity * price < rules.minimum_quote:
            return "rounded_order_below_instrument_minimum"
        return None

    def _exit(self, state: PoolState, basket, now: datetime, reason: str) -> Transition:
        slot = self._slot(state, basket.symbol)
        if slot is not None and (slot.exit_reason is None or reason in
                                 ("account_risk", "first_fill_55pct_exit")):
            updated = replace(slot, exit_reason=reason)
            state = replace(state, slots=tuple(
                updated if s.index == slot.index else s for s in state.slots))
        return super()._exit(state, basket, now, reason)

    @precise
    def _finalize_closed(self, state: PoolState, symbol: str) -> PoolState:
        basket, slot = state.basket(symbol), self._slot(state, symbol)
        closed = super()._finalize_closed(state, symbol)
        if closed.basket(symbol).cycle == basket.cycle:
            return closed
        if slot is None:
            raise ValueError("closed cycle has no slot")
        principal_limit, cost_limit, _ = self._cycle_budget(state, symbol)
        normal = (slot.exit_reason in NORMAL_EXITS and not basket.risk_stopped
                  and not state.account.halted and
                  basket.costs_spent <= cost_limit and
                  basket.principal_spent <= principal_limit)
        # A final fee may cross an account limit before the base fill latches it.
        if basket.started_at is not None:
            at = closed.closed_baskets[-1].closed_at
            normal = normal and not self.risk_reasons(state, at)
        updated = self._vacant_slot(state, slot.index) if normal else replace(
            slot, basket_id=closed.basket(symbol).basket_id, quarantined=True)
        receipts = state.cycles
        if basket.started_at is not None:
            receipts += (CycleReceipt(
                slot.index, symbol, basket.basket_id, basket.principal_spent, basket.costs_spent,
                basket.exit_proceeds - basket.principal_spent - basket.costs_spent,
                slot.exit_reason, bool(normal),
            ),)
        return replace(closed, slots=tuple(updated if s.index == slot.index else s
                                          for s in state.slots), cycles=receipts)

    def reconcile_cancelled(self, state: PoolState, intent_id: str) -> Transition:
        result = super().reconcile_cancelled(state, intent_id)
        symbol = next(o.intent.symbol for o in state.orders if o.intent.intent_id == intent_id)
        basket, slot = result.state.basket(symbol), self._slot(result.state, symbol)
        if (slot is not None and not slot.quarantined and not basket.entries
                and not basket.quantity and not basket.exiting and not self._active(result.state, basket)):
            result = replace(result, state=replace(result.state, slots=tuple(
                self._vacant_slot(result.state, s.index) if s.index == slot.index else s
                for s in result.state.slots)))
        return result

    def resume_slot(self, state: PoolState, index: int, now: datetime, *,
                    authorization_reference: str) -> PoolState:
        """Explicit operator action; caller authenticates ownership and fresh MFA."""
        self._validate(state)
        if not isinstance(authorization_reference, str) or not authorization_reference.strip():
            raise TradingRejected("explicit_slot_resume_required")
        if type(index) is not int or not 0 <= index < len(state.slots):
            raise ValueError("invalid slot")
        slot = state.slots[index]
        if not slot.quarantined:
            return state
        if state.account.halted or self.risk_reasons(state, now) or any(o.unresolved for o in state.orders):
            raise TradingRejected("risk_or_orders_still_unresolved")
        basket = state.basket(slot.symbol)
        if basket.quantity or basket.entries or basket.exiting:
            raise TradingRejected("slot_not_flat")
        resumed = super().resume_basket(state, slot.symbol, now)
        basket = replace(resumed.basket(slot.symbol), sub30_count=0, rearmed=False)
        return replace(resumed,
                       baskets=tuple(basket if b.symbol == slot.symbol else b for b in resumed.baskets),
                       slots=tuple(self._vacant_slot(resumed, s.index) if s.index == index else s
                                   for s in resumed.slots))


@dataclass(frozen=True)
class OccupancyPoint:
    at: datetime
    occupied: int
    quarantined: int


@dataclass(frozen=True)
class PoolResearchResult:
    version: str
    policy_digest: str
    plan_digest: str
    symbols: tuple[str, ...]
    capacity: int
    simulation: BacktestResult
    capital_curve: tuple[CapitalPoint, ...]
    occupancy_curve: tuple[OccupancyPoint, ...]
    planned_principal: Decimal
    planned_cost_reserve: Decimal
    initially_unassigned_capital: Decimal
    admissions: tuple[DomainEvent, ...]
    benchmark_status: str = "not_computed"
    validation_status: str = "not_evaluated"


@dataclass(frozen=True)
class PoolResearchSimulator:
    plan: PoolPlan
    instrument_rules: tuple[PoolInstrumentRules, ...]
    costs: SimulationCosts = SimulationCosts()

    @precise
    def __post_init__(self) -> None:
        self.engine()
        if any(r.quote_step / self.plan.quantum !=
               (r.quote_step / self.plan.quantum).to_integral_value()
               for r in self.instrument_rules):
            raise ValueError("quote step must be a multiple of plan quantum")

    def engine(self) -> PoolEngine:
        return PoolEngine(PoolConfig(self.plan, self.costs), self.instrument_rules,
                          self.costs.fee_rate, self.costs.slippage_fraction)

    def policy(self) -> dict:
        return {
            "version": POOL_VERSION, "plan_digest": self.plan.plan_digest,
            "configuration_digest": digest((self.engine().config, self.instrument_rules)),
            "cost_digest": digest(self.costs), "symbol_priority": self.plan.symbols,
            "capacity": self.plan.capacity, "maximum_bars_per_asset": MAX_BARS_PER_ASSET,
            "execution": EXECUTION_POLICY,
            "admission": "prepare_and_dispatch; full_stage_or_reject; correlated_50pct",
            "cycles": "fixed_initial_budget; normal_flat_reconciled_exit_only; risk_quarantine",
            "manual": "five_regular_rsi_stages; sixth_explicit_never_fabricated",
            "benchmark": "not_computed",
        }

    @precise
    def run(self, candles: Iterable[Candle]) -> PoolResearchResult:
        simulator = PaperSimulator(self.engine(), self.costs)
        reference = PortfolioSimulator(simulator)
        bars = reference._history(candles)
        engine = simulator.engine
        state = engine.start(self.plan.tenant_id, self.plan.account_id, bars[0].open_time)
        curve, capital, occupancy, fills, events = [], [], [], [], []

        def record(at: datetime) -> None:
            curve.append(EquityPoint(at, state.equity))
            capital.append(reference._capital(state, at))
            occupancy.append(OccupancyPoint(at, sum(s.symbol is not None for s in state.slots),
                                            sum(s.quarantined for s in state.slots)))

        record(bars[0].open_time)
        for opened, grouping in groupby(bars, lambda b: b.open_time):
            group = tuple(grouping)
            for at, field, buys in (
                (opened, "open", True), (opened + timedelta(hours=1), "low", False),
                (opened + timedelta(hours=2), "high", False),
                (opened + timedelta(hours=4), "close", False),
            ):
                batch = tuple(simulator.quote(b.symbol, at, getattr(b, field)) for b in group)
                transition = engine.on_quotes(
                    state, batch, closing_day=field == "close" and at.hour == 0
                    and state.account.trading_day != at.date(),
                )
                state = transition.state
                events.extend(transition.events)
                if at.hour == 0:
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
        for order in state.orders:
            if order.unresolved and order.intent.side == Side.BUY:
                state = engine.reconcile_cancelled(state, order.intent.intent_id).state
        capital[-1] = reference._capital(state, capital[-1].at)
        occupancy[-1] = OccupancyPoint(occupancy[-1].at,
                                      sum(s.symbol is not None for s in state.slots),
                                      sum(s.quarantined for s in state.slots))
        gains = sum((b.net_pnl for b in state.closed_baskets if b.net_pnl > 0), D("0"))
        losses = -sum((b.net_pnl for b in state.closed_baskets if b.net_pnl < 0), D("0"))
        execution = EXECUTION_POLICY + "; fixed_reusable_pool_slots; allocation_prepare_and_dispatch"
        simulation = BacktestResult(
            POOL_VERSION, state.configuration_digest, digest(bars), digest(self.costs),
            state, tuple(curve), tuple(events), tuple(fills),
            state.equity - state.account.initial_equity, _drawdown(tuple(curve)),
            gains / losses if losses else None, len(state.closed_baskets),
            execution_assumption=execution,
        )
        return PoolResearchResult(
            POOL_VERSION, digest(self.policy()), self.plan.plan_digest, self.plan.symbols,
            self.plan.capacity, simulation, tuple(capital), tuple(occupancy),
            self.plan.capacity * self.plan.slot_principal,
            self.plan.capacity * self.plan.slot_costs, self.plan.remainder,
            tuple(e for e in events if e.reason.startswith(ADMISSION_PREFIX)),
        )
