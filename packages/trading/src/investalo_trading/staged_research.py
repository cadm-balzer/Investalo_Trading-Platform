"""Research-only admission adapter using the unchanged deterministic RSI core."""

from __future__ import annotations

import json
from dataclasses import dataclass, fields, replace
from datetime import datetime, time, timezone
from decimal import Decimal
from typing import Iterable

from .allocation import (
    AllocationPlan, AllocationView, AssetUse, BuyReservation, PurchaseAssessment,
    PurchaseRequest, assess_purchase,
)
from .engine import CryptoEngine
from .models import (
    Candle, DomainEvent, EngineState, Fill, InstrumentRules, OrderIntent, OrderRecord,
    OrderStatus, Side, StrategyConfig, TradingRejected, Transition, positive, precise,
)
from .portfolio import (
    EXECUTION_POLICY, MAX_BARS_PER_ASSET, PortfolioBacktestResult, PortfolioSimulator,
)
from .simulator import PaperSimulator, SimulationCosts
from .snapshot import digest, primitive

D = Decimal
RESEARCH_VERSION = "allocated-rsi-research/1"
ADMISSION_PREFIX = "allocation:"


@dataclass(frozen=True, init=False)
class ResearchConfig(StrategyConfig):
    """Separate version; inherit signal/protection rules without widening v1."""

    plan: AllocationPlan

    def __init__(self, plan: AllocationPlan, costs: SimulationCosts):
        if plan.cost_ratio != D("0.01"):
            raise ValueError("approved research profile requires one percent cost reserve")
        reference = StrategyConfig(
            initial_equity=plan.initial_capital, basket_principal=plan.slot_principal,
            basket_cost_reserve=plan.slot_costs,
            estimated_exit_fee_rate=costs.fee_rate,
            estimated_exit_slippage_fraction=costs.slippage_fraction,
        )
        for field in fields(StrategyConfig):
            object.__setattr__(self, field.name, getattr(reference, field.name))
        object.__setattr__(self, "version", RESEARCH_VERSION)
        object.__setattr__(self, "symbols", plan.symbols)
        object.__setattr__(self, "plan", plan)

    @property
    def allocations(self) -> tuple[Decimal, ...]:
        return self.plan.stages


@dataclass(frozen=True)
class LifetimeSpend:
    symbol: str
    principal: Decimal = D("0")
    fees: Decimal = D("0")
    first_fill: Decimal | None = None

    def __post_init__(self) -> None:
        positive(self.principal, "lifetime principal", zero=True)
        positive(self.fees, "lifetime fees", zero=True)
        if self.first_fill is not None:
            positive(self.first_fill, "lifetime first fill")


@dataclass(frozen=True)
class ResearchState(EngineState):
    spending: tuple[LifetimeSpend, ...] = ()


@dataclass(frozen=True)
class Admission:
    boundary: str
    at: datetime
    intent_id: str
    symbol: str
    stage: int
    principal: Decimal
    plan_digest: str
    assessment: PurchaseAssessment


@dataclass(frozen=True)
class AllocatedResearchEngine(CryptoEngine):
    """No runtime registration, broker interface, manual automation or cycle reset."""

    fee_rate: Decimal = D("0.001")
    slippage_fraction: Decimal = D("0.001")

    def __post_init__(self) -> None:
        super().__post_init__()
        if not isinstance(self.config, ResearchConfig):
            raise ValueError("allocated engine requires the separate research configuration")
        if (self.fee_rate != self.config.estimated_exit_fee_rate or
                self.slippage_fraction != self.config.estimated_exit_slippage_fraction):
            raise ValueError("admission costs must match execution assumptions")

    def start(self, tenant_id: str, account_id: str, at: datetime) -> ResearchState:
        plan = self.config.plan
        if (tenant_id, account_id) != (plan.tenant_id, plan.account_id):
            raise ValueError("research identity differs from allocation")
        base = super().start(tenant_id, account_id, at)
        return ResearchState(**{f.name: getattr(base, f.name) for f in fields(EngineState)},
                             spending=tuple(LifetimeSpend(s) for s in plan.symbols))

    def _validate(self, state: EngineState, symbol: str | None = None) -> None:
        super()._validate(state, symbol)
        if (not isinstance(state, ResearchState)
                or tuple(s.symbol for s in state.spending) != self.config.symbols):
            raise ValueError("research lifetime ledger required")
        if (state.account.tenant_id, state.account.account_id) != (
                self.config.plan.tenant_id, self.config.plan.account_id):
            raise ValueError("foreign research state")

    @precise
    def _request(self, state: ResearchState, intent: OrderIntent,
                 principal: Decimal, revision: int) -> PurchaseRequest:
        quote = state.quote(intent.symbol)
        if quote is None:
            raise TradingRejected("complete_allocation_quotes_required")
        plan = self.config.plan
        return PurchaseRequest(
            plan.tenant_id, plan.account_id, plan.plan_digest, revision, intent.intent_id,
            intent.symbol, principal, principal * self.fee_rate,
            intent.maximum_price or quote.ask * (1 + self.slippage_fraction),
        )

    @precise
    def _assess(self, state: ResearchState, intent: OrderIntent, now: datetime,
                *, dispatch: bool = False) -> PurchaseAssessment:
        self._validate(state)
        plan = self.config.plan
        assets: list[AssetUse] = []
        for basket, spent in zip(state.baskets, state.spending):
            quote = state.quote(basket.symbol)
            if quote is None:
                raise TradingRejected("complete_allocation_quotes_required")
            assets.append(AssetUse(basket.symbol, spent.principal, spent.fees,
                                   basket.quantity, quote.bid, quote.observed_at,
                                   basket.first_fill_price or spent.first_fill))
        pending: list[BuyReservation] = []
        for index, record in enumerate(state.orders):
            if (not record.unresolved or record.intent.side != Side.BUY
                    or dispatch and record.intent.intent_id == intent.intent_id):
                continue
            remaining = max(D("0"), record.intent.maximum_quote - record.filled_principal)
            if remaining <= 0:
                raise TradingRejected("unresolved_filled_order_requires_reconciliation")
            status = str(record.status)
            if record.filled_quantity:
                status = "unknown"  # A partial order requires authoritative reconciliation.
            pending.append(BuyReservation(
                self._request(state, record.intent, remaining, index), status,
            ))
        view = AllocationView(
            plan.tenant_id, plan.account_id, plan.plan_digest, len(state.orders),
            assets[0].marked_at,
            datetime.combine(state.account.trading_day, time(), timezone.utc),
            state.account.day_start_equity, state.account.cash, tuple(assets), tuple(pending),
            state.account.halted or any(
                o.unresolved and o.intent.side == Side.SELL and
                (o.status != OrderStatus.OPEN or o.filled_quantity > 0) for o in state.orders),
        )
        principal = intent.maximum_quote
        if dispatch:
            record = next(o for o in state.orders if o.intent.intent_id == intent.intent_id)
            principal -= record.filled_principal
        return assess_purchase(plan, view, self._request(state, intent, principal, view.revision), now)

    def _evidence(self, assessment: PurchaseAssessment, intent: OrderIntent,
                  at: datetime, boundary: str) -> str:
        record = Admission(boundary, at, intent.intent_id, intent.symbol, intent.stage,
                           intent.maximum_quote, self.config.plan.plan_digest, assessment)
        return ADMISSION_PREFIX + json.dumps(primitive(record), sort_keys=True,
                                             separators=(",", ":"), allow_nan=False)

    def _buy(self, state: ResearchState, symbol: str, stage: int, now: datetime,
             event: str, authorization: str | None = None) -> Transition:
        # No approved reuse policy yet: never replenish a slot after closing.
        if state.basket(symbol).cycle:
            return Transition(state, events=(DomainEvent(
                "entry_blocked", symbol, "", "research_cycle_reuse_not_enabled"),))
        proposed = super()._buy(state, symbol, stage, now, event, authorization)
        if not proposed.intents:
            return proposed
        intent = proposed.intents[0]
        try:
            assessment = self._assess(state, intent, now)
        except TradingRejected as error:
            return Transition(state, events=(DomainEvent(
                "entry_blocked", symbol, intent.intent_id, str(error)),))
        evidence = DomainEvent("allocation_admission", symbol, intent.intent_id,
                               self._evidence(assessment, intent, now, "prepare"))
        if not assessment.allowed:
            return Transition(state, events=(evidence,))
        return replace(proposed, events=proposed.events + (evidence,))

    def _buy_rejection_for_dispatch(self, state: ResearchState, record: OrderRecord,
                                    now: datetime) -> str | None:
        reason = super()._buy_rejection_for_dispatch(state, record, now)
        if reason:
            return reason
        try:
            assessment = self._assess(state, record.intent, now, dispatch=True)
        except TradingRejected as error:
            return str(error)
        if not assessment.allowed:
            return self._evidence(assessment, record.intent, now, "dispatch")
        return None

    @precise
    def apply_fill(self, state: ResearchState, fill: Fill) -> Transition:
        applied = super().apply_fill(state, fill)
        if len(applied.state.processed_fills) == len(state.processed_fills):
            return applied
        order = next(o for o in state.orders if o.intent.intent_id == fill.intent_id)
        symbol = order.intent.symbol
        after = applied.state.basket(symbol)
        first = after.first_fill_price or state.basket(symbol).first_fill_price
        updated = tuple(replace(
            spent,
            principal=spent.principal + (fill.quantity * fill.price if order.intent.side == Side.BUY
                                         else D("0")),
            fees=spent.fees + fill.fee,
            first_fill=first or spent.first_fill,
        ) if spent.symbol == symbol else spent for spent in state.spending)
        return replace(applied, state=replace(applied.state, spending=updated))


@dataclass(frozen=True)
class StagedResearchResult:
    version: str
    policy_digest: str
    plan_digest: str
    portfolio: PortfolioBacktestResult
    # Full creation assessments and allocation-related dispatch rejections.
    admissions: tuple[DomainEvent, ...]
    validation_status: str = "not_evaluated"


@dataclass(frozen=True)
class StagedResearchSimulator:
    plan: AllocationPlan
    instrument_rules: tuple[InstrumentRules, ...]
    costs: SimulationCosts = SimulationCosts()

    @precise
    def __post_init__(self) -> None:
        if tuple(r.symbol for r in self.instrument_rules) != self.plan.symbols:
            raise ValueError("complete canonical research instrument rules required")
        for rules in self.instrument_rules:
            if rules.quote_step / self.plan.quantum != (
                    rules.quote_step / self.plan.quantum).to_integral_value():
                raise ValueError("instrument quote step must be a multiple of plan quantum")

    def engine(self) -> AllocatedResearchEngine:
        return AllocatedResearchEngine(
            ResearchConfig(self.plan, self.costs), self.instrument_rules,
            self.costs.fee_rate, self.costs.slippage_fraction,
        )

    def policy(self) -> dict:
        return {
            "version": RESEARCH_VERSION,
            "plan_digest": self.plan.plan_digest,
            "configuration_digest": digest((self.engine().config, self.instrument_rules)),
            "cost_digest": digest(self.costs),
            "maximum_bars_per_asset": MAX_BARS_PER_ASSET,
            "execution": EXECUTION_POLICY,
            "admission": "prepare_and_dispatch; full_stage_or_reject; correlated_50pct",
            "cycles": "one_basket_per_slot; lifetime_fees_and_principal_no_reuse",
            "signal_priority": self.plan.symbols,
            "manual": "five_regular_rsi_stages; sixth_manual_never_fabricated",
        }

    @precise
    def run(self, candles: Iterable[Candle]) -> StagedResearchResult:
        reference = PortfolioSimulator(PaperSimulator(self.engine(), self.costs))
        result = reference.run(candles, tenant_id=self.plan.tenant_id,
                               account_id=self.plan.account_id)
        policy_digest = digest(self.policy())
        execution = EXECUTION_POLICY + "; allocation_prepare_and_dispatch; no_cycle_reuse"
        simulation = replace(result.simulation, execution_assumption=execution)
        labelled = replace(result, schema_version=RESEARCH_VERSION, policy_digest=policy_digest,
                           execution_policy=execution, simulation=simulation)
        admissions = tuple(e for e in simulation.events if e.reason.startswith(ADMISSION_PREFIX))
        return StagedResearchResult(RESEARCH_VERSION, policy_digest, self.plan.plan_digest,
                                    labelled, admissions)
