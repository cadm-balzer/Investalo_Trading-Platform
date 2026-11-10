"""Research-only profit epochs: grow funded slots to seven, then future budgets."""

from dataclasses import dataclass, fields, replace
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
import json

from .allocation import AllocationView, AssetUse, BuyReservation
from .models import (
    DomainEvent, OrderStatus, Side, TradingRejected, Transition, floor_step, precise, utc,
)
from .pool_research import (
    CycleReceipt, PoolConfig, PoolEngine, PoolPlan, PoolResearchResult,
    PoolResearchSimulator, PoolState, Slot,
)
from .snapshot import digest, primitive
from .variable_budget import SlotLimit, VariablePlan, assess_purchase

D = Decimal
PROFIT_VERSION = "seven-slot-profit-rsi-research/1"
CHECK_CLOSES = 3


@dataclass(frozen=True)
class CycleBudget:
    total: Decimal
    principal: Decimal
    costs: Decimal
    stages: tuple[Decimal, ...]

    @classmethod
    @precise
    def make(cls, total: Decimal, plan) -> "CycleBudget":
        principal = floor_step(total / (1 + plan.cost_ratio), plan.quantum)
        weights = tuple(D("1.25") ** i for i in range(6))
        stages = tuple(floor_step(principal * w / sum(weights), plan.quantum) for w in weights)
        return cls(total, principal, total - principal, stages)


@dataclass(frozen=True)
class ProfitPlan(PoolPlan):
    maximum_capacity: int = 7

    def __post_init__(self) -> None:
        super().__post_init__()
        if type(self.maximum_capacity) is not int or self.maximum_capacity != 7:
            raise ValueError("approved maximum capacity is seven")
        if len(self.symbols) < self.maximum_capacity:
            raise ValueError("candidate pool must cover maximum funded capacity")

    @property
    def plan_digest(self) -> str:
        return digest((PROFIT_VERSION, self, CHECK_CLOSES,
                       "original_full_slot_threshold; one_etape; slots_then_future_volume"))

    @property
    def step(self) -> Decimal:
        return self.slot_plan.slot_total

    @property
    def original_budget(self) -> CycleBudget:
        return CycleBudget.make(self.step, self)


@dataclass(frozen=True, init=False)
class ProfitConfig(PoolConfig):
    def __init__(self, plan: ProfitPlan, costs):
        if not isinstance(plan, ProfitPlan):
            raise ValueError("profit epoch plan required")
        super().__init__(plan, costs)
        object.__setattr__(self, "version", PROFIT_VERSION)


@dataclass(frozen=True)
class BudgetEpoch:
    index: int
    at: datetime
    capacity: int
    budget: CycleBudget
    allocated_profit: Decimal
    closed_count: int
    realized_pnl: Decimal
    receipts_digest: str
    cash: Decimal
    equity: Decimal


@dataclass(frozen=True)
class ProfitSlot(Slot):
    budget: CycleBudget | None = None
    epoch: int = 0


@dataclass(frozen=True)
class BudgetCycleReceipt(CycleReceipt):
    budget: CycleBudget
    epoch: int


@dataclass(frozen=True)
class ProfitState(PoolState):
    epochs: tuple[BudgetEpoch, ...] = ()


@dataclass(frozen=True)
class ProfitEngine(PoolEngine):
    def __post_init__(self) -> None:
        super().__post_init__()
        if not isinstance(self.config, ProfitConfig):
            raise ValueError("profit research configuration required")

    def start(self, tenant_id: str, account_id: str, at: datetime) -> ProfitState:
        base = super().start(tenant_id, account_id, at)
        plan = self.config.plan
        budget = plan.original_budget
        epoch = BudgetEpoch(0, utc(at), plan.capacity, budget, D("0"), 0, D("0"),
                            digest(()), base.account.cash, base.equity)
        return ProfitState(**{f.name: getattr(base, f.name) for f in fields(PoolState)
                              if f.name != "slots"},
                           slots=tuple(ProfitSlot(i, budget=budget) for i in range(plan.capacity)),
                           epochs=(epoch,))

    def _slot_capacity(self, state: ProfitState) -> int:
        if not isinstance(state, ProfitState) or not state.epochs:
            raise ValueError("profit epoch state required")
        return state.epochs[-1].capacity

    def _vacant_slot(self, state: ProfitState, index: int) -> ProfitSlot:
        epoch = state.epochs[-1]
        return ProfitSlot(index, budget=epoch.budget, epoch=epoch.index)

    def _cycle_budget(self, state: ProfitState, symbol: str):
        slot = self._slot(state, symbol)
        budget = slot.budget if slot is not None else state.epochs[-1].budget
        return budget.principal, budget.costs, budget.stages

    @precise
    def _target(self, capacity: int, allocated: Decimal) -> CycleBudget:
        plan = self.config.plan
        total = floor_step((plan.initial_capital - plan.remainder + allocated) / capacity,
                           plan.quantum)
        return CycleBudget.make(total, plan)

    @precise
    def _validate(self, state, symbol=None) -> None:
        super()._validate(state, symbol)
        plan = self.config.plan
        if type(state.epochs) is not tuple or len(state.cycles) != len(state.closed_baskets):
            raise ValueError("immutable profit history required")
        for index, epoch in enumerate(state.epochs):
            if (not isinstance(epoch, BudgetEpoch) or type(epoch.index) is not int
                    or epoch.index != index or type(epoch.capacity) is not int
                    or type(epoch.closed_count) is not int or epoch.closed_count < 0
                    or epoch.closed_count > len(state.cycles)):
                raise ValueError("invalid budget epoch")
            if epoch.at != utc(epoch.at):
                raise ValueError("UTC budget epoch required")
            if index == 0:
                if (epoch.capacity != plan.capacity or epoch.allocated_profit != 0
                        or epoch.closed_count != 0 or epoch.realized_pnl != 0
                        or epoch.cash != plan.initial_capital or epoch.equity != plan.initial_capital):
                    raise ValueError("invalid initial budget epoch")
            else:
                previous = state.epochs[index - 1]
                if (epoch.capacity != min(previous.capacity + 1, plan.maximum_capacity)
                        or epoch.allocated_profit != previous.allocated_profit + plan.step
                        or epoch.closed_count < previous.closed_count + CHECK_CLOSES
                        or epoch.at < previous.at
                        or epoch.equity < plan.initial_capital + epoch.allocated_profit):
                    raise ValueError("invalid profit grant progression")
                if epoch.realized_pnl < epoch.allocated_profit:
                    raise ValueError("profit grant exceeds realized net surplus")
                if any(b.closed_at > epoch.at for b in state.closed_baskets[:epoch.closed_count]):
                    raise ValueError("future closure cannot fund a profit epoch")
            prefix = state.cycles[:epoch.closed_count]
            if (epoch.receipts_digest != digest(prefix)
                    or epoch.realized_pnl != sum((c.net_pnl for c in prefix), D("0"))
                    or epoch.budget != self._target(epoch.capacity, epoch.allocated_profit)):
                raise ValueError("profit receipt or target budget mismatch")
        for slot in state.slots:
            if (not isinstance(slot, ProfitSlot) or type(slot.epoch) is not int
                    or not 0 <= slot.epoch < len(state.epochs)
                    or slot.budget != state.epochs[slot.epoch].budget
                    or slot.symbol is None and slot.epoch != state.epochs[-1].index):
                raise ValueError("invalid frozen slot budget")
        for receipt, closed in zip(state.cycles, state.closed_baskets):
            if (not isinstance(receipt, BudgetCycleReceipt)
                    or (receipt.basket_id, receipt.symbol, receipt.net_pnl) != (
                        closed.basket_id, closed.symbol, closed.net_pnl)
                    or type(receipt.epoch) is not int or not 0 <= receipt.epoch < len(state.epochs)
                    or receipt.budget != state.epochs[receipt.epoch].budget):
                raise ValueError("invalid closed budget receipt")

    @precise
    def _variable_plan(self, state: ProfitState) -> VariablePlan:
        plan, epoch = self.config.plan, state.epochs[-1]
        limits = tuple(SlotLimit(f"SLOT{s.index}", s.budget.principal, s.budget.costs)
                       for s in state.slots)
        remainder = (plan.initial_capital + epoch.allocated_profit
                     - sum((s.budget.total for s in state.slots), D("0")))
        return VariablePlan(plan.tenant_id, plan.account_id,
                            digest((plan.plan_digest, epoch.index)), plan.initial_capital,
                            plan.quantum, remainder, limits)

    def _marks(self, state: ProfitState, now: datetime) -> datetime:
        quotes = tuple(state.quote(s) for s in self.config.symbols)
        if any(q is None for q in quotes):
            raise TradingRejected("complete_allocation_quotes_required")
        at = quotes[0].observed_at
        if any(q.observed_at != at for q in quotes):
            raise TradingRejected("complete_allocation_mark_batch_required")
        if not timedelta(0) <= utc(now) - at <= timedelta(seconds=30):
            raise TradingRejected("stale_or_future_allocation_marks")
        return at

    @precise
    def _assess(self, state: ProfitState, intent, now, *, dispatch=False):
        self._validate(state)
        at = self._marks(state, now)
        assigned = self._slot(state, intent.symbol)
        if assigned is None or assigned.quarantined:
            raise TradingRejected("funded_slot_required")
        plan = self._variable_plan(state)
        assets = []
        for slot in state.slots:
            if slot.symbol is None:
                assets.append(AssetUse(f"SLOT{slot.index}", D("0"), D("0"), D("0"), D("1"), at))
            else:
                basket = state.basket(slot.symbol)
                assets.append(AssetUse(
                    f"SLOT{slot.index}", basket.principal_spent, basket.costs_spent,
                    basket.quantity, state.quote(slot.symbol).bid, at, basket.first_fill_price))

        def projected(order, amount, revision):
            slot = self._slot(state, order.symbol)
            if slot is None:
                raise TradingRejected("unassigned_pending_order")
            return replace(self._request(state, order, amount, revision),
                           plan_digest=plan.plan_digest, symbol=f"SLOT{slot.index}")

        pending = []
        for index, record in enumerate(state.orders):
            if (not record.unresolved or record.intent.side != Side.BUY
                    or dispatch and record.intent.intent_id == intent.intent_id):
                continue
            remaining = record.intent.maximum_quote - record.filled_principal
            if remaining <= 0:
                raise TradingRejected("unresolved_filled_order_requires_reconciliation")
            status = "unknown" if record.filled_quantity else str(record.status)
            pending.append(BuyReservation(projected(record.intent, remaining, index), status))
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
        return replace(result, view_digest=digest((state.epochs, state.slots, view)))

    def _finalize_closed(self, state: ProfitState, symbol: str) -> ProfitState:
        slot = self._slot(state, symbol)
        finalized = super()._finalize_closed(state, symbol)
        if len(finalized.cycles) == len(state.cycles):
            return finalized
        old = finalized.cycles[-1]
        receipt = BudgetCycleReceipt(**primitive_fields(old), budget=slot.budget, epoch=slot.epoch)
        return replace(finalized, cycles=finalized.cycles[:-1] + (receipt,))

    @precise
    def evaluate_growth(self, state: ProfitState, now: datetime) -> Transition:
        """One offline etape; neither cash credit, broker call nor operator resume."""
        self._validate(state)
        now = utc(now)
        plan, previous = self.config.plan, state.epochs[-1]
        realized = sum((c.net_pnl for c in state.cycles), D("0"))
        if (len(state.cycles) < previous.closed_count + CHECK_CLOSES
                or realized - previous.allocated_profit < plan.step):
            return Transition(state)
        try:
            self._marks(state, now)
        except TradingRejected as error:
            return Transition(state, events=(DomainEvent(
                "profit_etape_blocked", "", str(len(state.cycles)), str(error)),))
        reasons = list(self.risk_reasons(state, now))
        if state.account.halted:
            reasons.append("account_halted")
        if any(s.quarantined for s in state.slots) or any(b.risk_stopped for b in state.baskets):
            reasons.append("risk_resume_required")
        if any(o.unresolved for o in state.orders):
            reasons.append("orders_require_reconciliation")
        if any(b.closed_at > now for b in state.closed_baskets):
            reasons.append("future_close_receipt")
        allocated = previous.allocated_profit + plan.step
        capacity = min(previous.capacity + 1, plan.maximum_capacity)
        budget = self._target(capacity, allocated)
        epoch = BudgetEpoch(len(state.epochs), now, capacity, budget, allocated, len(state.cycles),
                            realized, digest(state.cycles), state.account.cash, state.equity)
        candidate = replace(
            state, epochs=state.epochs + (epoch,),
            slots=tuple(replace(s, budget=budget, epoch=epoch.index) if s.symbol is None else s
                        for s in state.slots) + tuple(
                ProfitSlot(i, budget=budget, epoch=epoch.index)
                for i in range(len(state.slots), capacity)),
        )
        reserves = sum((max(D("0"), s.budget.costs - (
            state.basket(s.symbol).costs_spent if s.symbol is not None else D("0")))
                        for s in candidate.slots), D("0"))
        pending = sum((max(D("0"), o.intent.maximum_quote - o.filled_principal)
                       for o in state.orders if o.unresolved and o.intent.side == Side.BUY), D("0"))
        if state.equity < plan.initial_capital + allocated:
            reasons.append("profit_no_longer_equity_backed")
        if state.account.cash - pending - reserves - self._variable_plan(state).remainder < plan.step:
            reasons.append("insufficient_liquid_profit")
        stress = sum((max(D("0"), b.quantity * (
            state.quote(b.symbol).bid - D("0.5") * b.first_fill_price))
                      for b in state.baskets if b.quantity), D("0"))
        headroom = min(state.equity - state.account.day_start_equity * D("0.94"),
                       state.equity - plan.initial_capital * D("0.92"))
        if stress + pending * D("0.5") + reserves > headroom:
            reasons.append("correlated_stress")
        if reasons:
            blocked = DomainEvent(
                "profit_etape_blocked", "", str(len(state.cycles)),
                json.dumps(tuple(dict.fromkeys(reasons))))
            return Transition(state, events=(blocked,))
        self._validate(candidate)
        event = DomainEvent("profit_etape_granted", "", str(epoch.index),
                            json.dumps(primitive(epoch), sort_keys=True, separators=(",", ":")))
        return Transition(candidate, events=(event,))

    def on_bar(self, state, bar, *, observed_at=None):
        # Duplicate, revised, unfinished and gapped bars keep their original semantics.
        basket = state.basket(bar.symbol)
        key = f"{bar.symbol}:{bar.open_time.isoformat()}"
        if (any(k == key for k, _ in state.processed_bars)
                or basket.last_bar_open is not None and bar.open_time != (
                    basket.last_bar_open + timedelta(hours=4))
                or utc(observed_at or bar.close_time) < bar.close_time):
            return super().on_bar(state, bar, observed_at=observed_at)
        growth = self.evaluate_growth(state, observed_at or bar.close_time)
        processed = super().on_bar(growth.state, bar, observed_at=observed_at)
        return replace(processed, events=growth.events + processed.events)


def primitive_fields(value) -> dict:
    """Copy typed dataclass fields without changing Decimals to JSON strings."""
    return {f.name: getattr(value, f.name) for f in fields(value)}


@dataclass(frozen=True)
class ProfitResearchResult(PoolResearchResult):
    initial_capacity: int = 5
    maximum_capacity: int = 7
    budget_epochs: tuple[BudgetEpoch, ...] = ()
    allocated_profit: Decimal = D("0")
    unassigned_planning_capital: Decimal = D("0")


@dataclass(frozen=True)
class ProfitResearchSimulator(PoolResearchSimulator):
    def engine(self) -> ProfitEngine:
        return ProfitEngine(ProfitConfig(self.plan, self.costs), self.instrument_rules,
                            self.costs.fee_rate, self.costs.slippage_fraction)

    def policy(self) -> dict:
        result = super().policy()
        result.update(version=PROFIT_VERSION, maximum_capacity=7, check_closes=CHECK_CLOSES,
                      cycles="slots_to_seven_then_future_volume; original_threshold; frozen_cycles")
        return result

    @precise
    def run(self, candles) -> ProfitResearchResult:
        base = super().run(candles)
        state = base.simulation.state
        simulation = replace(
            base.simulation, strategy_version=PROFIT_VERSION,
            execution_assumption=base.simulation.execution_assumption + "; staged_profit_epochs")
        labelled = replace(
            base, version=PROFIT_VERSION, simulation=simulation, capacity=len(state.slots),
            planned_principal=sum((s.budget.principal for s in state.slots), D("0")),
            planned_cost_reserve=sum((s.budget.costs for s in state.slots), D("0")),
        )
        return ProfitResearchResult(
            **primitive_fields(labelled), initial_capacity=self.plan.capacity,
            maximum_capacity=self.plan.maximum_capacity, budget_epochs=state.epochs,
            allocated_profit=state.epochs[-1].allocated_profit,
            unassigned_planning_capital=self.engine()._variable_plan(state).remainder)
