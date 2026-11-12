"""Q41–Q43 capital-only research. No RSI authority, broker or durable executor."""
from dataclasses import dataclass, field, replace
from functools import cached_property
from datetime import datetime, timedelta
from decimal import Decimal

from .allocation import identifier, revision
from .futures_economics import LongPosition
from .futures_ledger import (
    DailyBasis, EntryFill, ExitFill, FundingSettlement, FuturesLedgerState,
    LedgerCommand, LedgerMark, LiquidationSettlement, MarginPosting, MarkBatch, PHASES,
    apply_futures_event, number, start_futures_ledger, timestamp,
)
from .futures_risk import (
    FuturesAssessment, FuturesBudget, FuturesContract, FuturesExposure, FuturesPlan,
    FuturesPurchase, FuturesView, assess_futures_purchase,
)
from .identity_history import IdentityHistory
from .models import floor_step, precise
from .capital_digest import CapitalCanonical, digest

D = Decimal
ZERO = D("0")
VERSION = "isolated-usdt-capital-ladder/1"
DIAGNOSTIC_REASONS = {
    "account_loss_limit", "correlated_account_stress", "isolated_stress_liquidation",
}


@dataclass(frozen=True)
class CapitalPlan(FuturesPlan, CapitalCanonical):
    capital_policy: str = field(default=VERSION, init=False)

    def __post_init__(self):
        super().__post_init__()
        if self.remainder + sum((b.capital for b in self.budgets), ZERO) != self.initial_equity:
            raise ValueError("complete funded capital allocation required")

    @cached_property
    def plan_digest(self):
        return digest((VERSION, self, "fixed-cycle-leverage", "six-own-capital-stages"))

    @property
    def supports_capital_liquidations(self):
        return True

    @property
    def per_cycle_cost_budgets(self):
        return True

    def ledger_halt_reasons(self, reasons):
        # An unsafe isolated basket awaits settlement, not an account-wide exit.
        return tuple(dict.fromkeys(r for r in reasons if r not in {
            "daily_loss_limit", "initial_loss_limit", "isolated_position_unsafe",
        }))

    @precise
    def stage_capital(self, symbol):
        pool = self.budgets[self.symbols.index(symbol)].margin_capital
        weights = tuple(D("1.25") ** i for i in range(6))
        return tuple(floor_step(pool * w / sum(weights), self.quantum) for w in weights)


@precise
def equal_capital_plan(tenant_id, account_id, policy_digest, contracts,
                       initial_equity=D("10000"), cost_ratio=D(".01"), quantum=D(".00000001")):
    """Declared research costs, not broker-calibrated funding or margin terms."""
    if (type(contracts) is not tuple or not 3 <= len(contracts) <= 7
            or any(not isinstance(c, FuturesContract) for c in contracts)):
        raise ValueError("three to seven immutable native contracts required")
    number(initial_equity, positive=True)
    number(cost_ratio, positive=True)
    number(quantum, positive=True)
    if cost_ratio >= 1:
        raise ValueError("invalid cost reserve ratio")
    total = floor_step(initial_equity / len(contracts), quantum)
    principal = floor_step(total / (1 + cost_ratio), quantum)
    return CapitalPlan(
        tenant_id, account_id, policy_digest, initial_equity, quantum,
        initial_equity - len(contracts) * total, contracts,
        tuple(FuturesBudget(c.symbol, total, total - principal) for c in contracts),
    )


@dataclass(frozen=True)
class LeverageDecision(CapitalCanonical):
    symbol: str
    cycle: int
    leverage: Decimal
    decided_at: datetime
    evidence_digest: str

    def __post_init__(self):
        identifier(self.symbol)
        revision(self.cycle)
        number(self.leverage, positive=True)
        timestamp(self.decided_at)
        identifier(self.evidence_digest)
        if not self.cycle or not D("2") <= self.leverage <= D("10"):
            raise ValueError("cycle leverage must be within2–10")


@dataclass(frozen=True)
class StageReceipt(CapitalCanonical):
    symbol: str
    cycle: int
    stage: int
    quantity: Decimal
    price: Decimal
    own_capital: Decimal
    event_id: str

    def __post_init__(self):
        identifier(self.symbol)
        identifier(self.event_id)
        revision(self.cycle)
        if not self.cycle or type(self.stage) is not int or not 1 <= self.stage <= 5:
            raise ValueError("regular full-fill stage required")
        for value in (self.quantity, self.price, self.own_capital):
            number(value, positive=True)


@dataclass(frozen=True)
class StoppedBasket(CapitalCanonical):
    symbol: str
    cycle: int
    unposted_stage_capital: Decimal
    evidence_digest: str

    def __post_init__(self):
        identifier(self.symbol)
        identifier(self.evidence_digest)
        revision(self.cycle)
        number(self.unposted_stage_capital, nonnegative=True)
        if not self.cycle:
            raise ValueError("actual stopped cycle required")


@dataclass(frozen=True)
class CapitalResearchState(CapitalCanonical):
    ledger: FuturesLedgerState
    revision: int
    as_of: datetime
    decisions: tuple[LeverageDecision, ...]
    stages: tuple[StageReceipt, ...]
    stopped: tuple[StoppedBasket, ...]
    event_ids: IdentityHistory
    audit_head: str

    def __post_init__(self):
        if not isinstance(self.ledger.plan, CapitalPlan):
            raise ValueError("own capital policy required; no legacy conversion")
        revision(self.revision)
        timestamp(self.as_of)
        identifier(self.audit_head)
        if self.as_of < self.ledger.as_of:
            raise ValueError("wrapper predates ledger")
        for rows, kind in ((self.decisions, LeverageDecision), (self.stages, StageReceipt),
                           (self.stopped, StoppedBasket)):
            if (type(rows) is not tuple or any(not isinstance(row, kind)
                    or row.symbol not in self.ledger.plan.symbols for row in rows)):
                raise ValueError("immutable own records required")
        if len({(r.symbol, r.cycle) for r in self.decisions}) != len(self.decisions):
            raise ValueError("one leverage decision per cycle")
        if len({r.symbol for r in self.stopped}) != len(self.stopped):
            raise ValueError("stopped basket cannot restart implicitly")
        if not isinstance(self.event_ids, IdentityHistory) or self.event_ids.namespace != "event":
            raise ValueError("full event history required")
        if len(self.event_ids) != self.revision:
            raise ValueError("every acknowledged change needs complete identity evidence")
        keys = {(d.symbol, d.cycle) for d in self.decisions}
        stages_by_cycle = {}
        for r in self.stages:
            key = (r.symbol, r.cycle)
            if r.event_id not in self.event_ids or key not in keys:
                raise ValueError("stage lacks frozen decision or full event evidence")
            stages_by_cycle.setdefault(key, []).append(r.stage)
        for decision in self.decisions:
            if decision.decided_at > self.as_of:
                raise ValueError("future leverage decision")
            stages = stages_by_cycle.get((decision.symbol, decision.cycle), [])
            if stages != list(range(1, len(stages) + 1)):
                raise ValueError("actual regular stages must be consecutive")

    @cached_property
    def state_digest(self):
        return digest((VERSION, self))

    @property
    def warnings(self):
        ledger = self.ledger
        return tuple(r for r, breached in (
            ("daily_loss_limit", ledger.equity <= ledger.day_start_equity * D(".94")),
            ("initial_loss_limit", ledger.equity <= ledger.plan.initial_equity * D(".92")),
        ) if breached)

    @property
    @precise
    def liquidation_required(self):
        result = []
        for b, c in zip(self.ledger.baskets, self.ledger.plan.contracts, strict=True):
            if b.quantity:
                tier = c.schedule.tier_for(b.quantity * max(b.mark, b.average_entry, b.first_fill))
                if b.equity <= b.quantity * b.mark * (
                        tier.maintenance_rate + c.protective_exit_fee_rate):
                    result.append(b.symbol)
        return tuple(result)


@dataclass(frozen=True)
class CapitalAssessment:
    state_digest: str
    request: FuturesPurchase
    stage: int
    allowed: bool
    reasons: tuple[str, ...]
    diagnostics: tuple[str, ...]
    legacy_stress: FuturesAssessment | None
    required_initial_margin: Decimal | None
    execution_enabled: bool = False

    def __post_init__(self):
        if self.execution_enabled is not False:
            raise ValueError("capital assessment cannot enable execution")


def start_capital_research(plan, marks, at, evidence_digest, *, identity_capacity=50000):
    if type(plan) is not CapitalPlan:
        raise ValueError("explicit capital plan required")
    ledger = start_futures_ledger(plan, marks, at, evidence_digest)
    return CapitalResearchState(
        ledger, 0, at, (), (), (), IdentityHistory("event", identity_capacity),
        digest((VERSION, ledger.state_digest)),
    )


def _check(state, expected_revision, at):
    at = timestamp(at)
    revision(expected_revision)
    if expected_revision != state.revision or at < state.as_of:
        raise ValueError("stale revision or backdated capital event")
    return at


def _finish(state, at, event_id, body, **changes):
    events = state.event_ids.append(event_id)
    candidate = replace(state, revision=state.revision + 1, as_of=at,
                        event_ids=events, **changes)
    return replace(candidate, audit_head=digest((
        VERSION, state.audit_head, event_id, body, candidate.state_digest,
    )))


def freeze_basket_leverage(state, symbol, leverage, evidence_digest,
                           event_id, expected_revision, at):
    """Trusted declared research decision; no claim of actual AI validation."""
    at = _check(state, expected_revision, at)
    b = state.ledger.baskets[state.ledger.plan.symbols.index(symbol)]
    if b.quantity or any(r.symbol == symbol for r in state.stopped):
        raise ValueError("cannot change an open or stopped basket leverage")
    decision = LeverageDecision(symbol, b.cycle + 1, leverage, at, evidence_digest)
    if any((r.symbol, r.cycle) == (symbol, decision.cycle) for r in state.decisions):
        raise ValueError("cycle leverage is already frozen")
    return _finish(state, at, event_id, decision, decisions=(*state.decisions, decision))


@precise
def prepare_capital_entry(state, symbol, maximum_price, at):
    """Capital admission only: RSI/rearm/protection and manual authority are separate."""
    at = _check(state, state.revision, at)
    plan = state.ledger.plan
    index = plan.symbols.index(symbol)
    b, contract = state.ledger.baskets[index], plan.contracts[index]
    if any(r.symbol == symbol for r in state.stopped):
        raise ValueError("basket is liquidated; explicit recovery is required")
    cycle = b.cycle if b.quantity else b.cycle + 1
    decisions = tuple(r for r in state.decisions if (r.symbol, r.cycle) == (symbol, cycle))
    if not decisions:
        raise ValueError("freeze leverage before the first entry")
    stage = 1 + sum((r.symbol, r.cycle) == (symbol, cycle) for r in state.stages)
    if stage > 5:
        raise ValueError("sixth stage is manual reserve; no automated admission")
    capital = plan.stage_capital(symbol)[stage - 1]
    number(maximum_price, positive=True)
    quantity = floor_step(capital * decisions[0].leverage / maximum_price, contract.quantity_step)
    if quantity <= 0:
        raise ValueError("planned order rounds to zero")
    request = FuturesPurchase(
        plan.tenant_id, plan.account_id, plan.plan_digest, state.revision,
        symbol, quantity, maximum_price, capital, decisions[0].leverage,
    )
    reasons = []
    if state.liquidation_required:
        reasons.append("liquidation_requires_settlement")
    if state.ledger.equity <= 0 or state.ledger.unposted_cash < 0:
        reasons.append("account_capital_exhausted")
    if reasons:
        return CapitalAssessment(state.state_digest, request, stage, False, tuple(reasons),
                                 state.warnings, None, None)
    exposures = tuple(FuturesExposure(
        row.symbol, row.mark, row.marked_at,
        LongPosition(row.quantity, row.average_entry, row.first_fill, row.isolated_balance)
        if row.quantity else None, row.charges_in_budget_epoch,
    ) for row in state.ledger.baskets)
    view = FuturesView(
        plan.tenant_id, plan.account_id, plan.plan_digest, state.revision,
        state.ledger.as_of, state.ledger.day_started_at, state.ledger.day_start_equity,
        state.ledger.unposted_cash, exposures, state.ledger.halted,
    )
    legacy = assess_futures_purchase(plan, view, request, at)
    # First-fill anchors belong to stress, not the actual entry basis of an
    # averaged-down position. Retain actual initialmargin and cash checks below.
    reasons = [r for r in legacy.reasons if r not in DIAGNOSTIC_REASONS | {
        "initial_margin_requirement", "insufficient_unposted_cash",
    }]
    if at == state.ledger.as_of and state.ledger.phase > PHASES[EntryFill]:
        reasons.append("entry_event_ordering")
    if b.quantity and b.broker_leverage != request.requested_leverage:
        reasons.append("basket_leverage_changed")
    basis = b.quantity * b.average_entry + quantity * maximum_price
    initial = max(basis, (b.quantity + quantity) * b.mark) / request.requested_leverage
    if b.isolated_balance + capital < initial:
        reasons.append("initial_margin_requirement")
    reserves = plan.remainder
    stopped = {r.symbol: r for r in state.stopped}
    for row, budget in zip(state.ledger.baskets, plan.budgets, strict=True):
        committed = row.margin_committed + (capital if row.symbol == symbol else ZERO)
        fees = row.charges_in_budget_epoch + (
            quantity * maximum_price * contract.entry_fee_rate if row.symbol == symbol else ZERO)
        reserves += stopped[row.symbol].unposted_stage_capital if row.symbol in stopped else max(
            ZERO, budget.margin_capital - committed)
        reserves += max(ZERO, budget.cost_reserve - fees)
        # Keep principal restoration backing separate from unused cost reserve.
        reserves += max(ZERO, row.margin_committed - row.isolated_balance)
    if legacy.unposted_cash_after < reserves:
        reasons.append("insufficient_unposted_cash")
    diagnostics = tuple(dict.fromkeys((*state.warnings,
        *(r for r in legacy.reasons if r in DIAGNOSTIC_REASONS))))
    return CapitalAssessment(
        state.state_digest, request, stage, not reasons, tuple(dict.fromkeys(reasons)),
        diagnostics, legacy, initial,
    )


@precise
def simulate_capital_fill(state, assessment, price, event_id, expected_revision, at):
    """Explicit full-fill research model. Not a broker receipt/partial-fill API."""
    at = _check(state, expected_revision, at)
    if assessment.state_digest != state.state_digest or not assessment.allowed:
        raise ValueError("stale or rejected capital assessment")
    request = assessment.request
    fresh = prepare_capital_entry(state, request.symbol, request.maximum_fill_price, at)
    if not fresh.allowed or fresh != assessment:
        raise ValueError("capital admission changed")
    number(price, positive=True)
    if price > request.maximum_fill_price:
        raise ValueError("fill exceeds declared price bound")
    c = state.ledger.plan.contracts[state.ledger.plan.symbols.index(request.symbol)]
    payload = EntryFill(
        request.symbol, request.quantity, price, request.posted_margin,
        request.quantity * price * c.entry_fee_rate, request.requested_leverage,
    )
    transition = _book(state, payload, event_id, at)
    b = transition.state.baskets[state.ledger.plan.symbols.index(request.symbol)]
    receipt = StageReceipt(request.symbol, b.cycle, assessment.stage, payload.quantity,
                           price, payload.posted_margin, event_id)
    return _finish(state, at, event_id, payload, ledger=transition.state,
                   stages=(*state.stages, receipt))


def _book(state, payload, event_id, at):
    plan = state.ledger.plan
    command = LedgerCommand(
        plan.tenant_id, plan.account_id, plan.plan_digest, state.ledger.revision,
        event_id, at, payload,
    )
    return apply_futures_event(state.ledger, command)


@precise
def record_capital_event(state, payload, event_id, expected_revision, at):
    """Trusted complete economic evidence; no invented fills, funding or topups."""
    at = _check(state, expected_revision, at)
    if type(payload) not in (MarkBatch, DailyBasis, FundingSettlement, ExitFill,
                            LiquidationSettlement, MarginPosting):
        raise ValueError("unsupported capital event; entries require model admission")
    if isinstance(payload, MarginPosting) and not payload.cost_restoration:
        raise ValueError("extra margin cannot consume reserved entry capital")
    stopped = state.stopped
    if isinstance(payload, LiquidationSettlement):
        b = state.ledger.baskets[state.ledger.plan.symbols.index(payload.symbol)]
        if not b.quantity or any(r.symbol == payload.symbol for r in stopped):
            raise ValueError("own open basket required for terminal liquidation")
        budget = state.ledger.plan.budgets[state.ledger.plan.symbols.index(payload.symbol)]
        stopped += (StoppedBasket(b.symbol, b.cycle,
                                 budget.margin_capital - b.margin_committed,
                                 payload.evidence_digest),)
    transition = _book(state, payload, event_id, at)
    return _finish(state, at, event_id, payload, ledger=transition.state, stopped=stopped)
