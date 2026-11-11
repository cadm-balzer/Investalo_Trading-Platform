"""Causal remaining-fill/gap research bounds; no order continuation authority."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from .allocation import identifier, revision
from .futures_ledger import LedgerMark, PHASES, EntryFill, timestamp
from .futures_pending import MAX_IDENTITIES, PendingResearchState
from .models import floor_step, precise
from .snapshot import digest

D = Decimal
ZERO = D("0")
VERSION = "isolated-usdt-long-continuation/1"


@dataclass(frozen=True)
class ContinuationScenario:
    tenant_id: str
    account_id: str
    plan_digest: str
    expected_revision: int
    intent_id: str
    order_id: str
    minimum_marks: tuple[LedgerMark, ...]

    def __post_init__(self):
        for value in (self.tenant_id, self.account_id, self.plan_digest, self.intent_id, self.order_id):
            identifier(value)
        revision(self.expected_revision)
        if (type(self.minimum_marks) is not tuple or not 3 <= len(self.minimum_marks) <= 7
                or any(type(m) is not LedgerMark for m in self.minimum_marks)
                or tuple(m.symbol for m in self.minimum_marks) != tuple(
                    sorted({m.symbol for m in self.minimum_marks}))):
            raise ValueError("complete canonical immutable gap marks required")


@dataclass(frozen=True)
class ContinuationAssessment:
    risk_covered: bool
    reasons: tuple[str, ...]
    state_digest: str
    scenario_digest: str
    assessed_at: datetime
    remaining_quantity: Decimal
    projected_remaining_fee: Decimal
    unconsumed_intent_margin: Decimal
    effective_gap_marks: tuple[LedgerMark, ...]
    current_equity: Decimal
    projected_equity: Decimal
    gap_equity_before: Decimal
    gap_equity_after: Decimal
    headroom: Decimal
    stress_loss: Decimal
    required_isolated_balance: Decimal | None
    available_isolated_balance: Decimal
    additional_margin_required: Decimal | None
    requires_reconciliation: bool = True
    execution_enabled: bool = False

    def __post_init__(self):
        if self.execution_enabled is not False or self.requires_reconciliation is not True:
            raise ValueError("research cannot enable execution or release an unknown order")


@precise
def assess_futures_continuation(state: PendingResearchState, scenario: ContinuationScenario,
                               now: datetime) -> ContinuationAssessment:
    """Bound every prefix after the first actual fill using already posted collateral.

    First-fill anchor is known, later prices are <= the frozen intent ceiling.
    Future margin transfers never count. Conservative whole-tier maintenance
    and adverse prices yield affine bounds in filled quantity; check both ends.
    This reports research coverage, not whether an unknown order may be retried.
    """
    now = timestamp(now)
    ledger, plan, p = state.ledger, state.ledger.plan, state.pending
    if (scenario.tenant_id, scenario.account_id, scenario.plan_digest) != (
            plan.tenant_id, plan.account_id, plan.plan_digest):
        raise ValueError("foreign continuation context")
    if p is None or (scenario.intent_id, scenario.order_id) != (p.intent_id, p.order_id):
        raise ValueError("attempted own pending order required")
    if tuple(m.symbol for m in scenario.minimum_marks) != plan.symbols:
        raise ValueError("foreign or incomplete gap marks")
    if any(m.price > b.mark for m, b in zip(scenario.minimum_marks, ledger.baskets, strict=True)):
        raise ValueError("gap minimum cannot exceed current mark")
    reasons = []
    if scenario.expected_revision != state.revision:
        reasons.append("stale_revision")
    if now < state.as_of or any(not timedelta(0) <= now - b.marked_at <= timedelta(seconds=30)
                                for b in ledger.baskets):
        reasons.append("stale_or_future_marks")
    if len({b.marked_at for b in ledger.baskets}) != 1:
        reasons.append("incomplete_mark_batch")
    if ledger.day_started_at != now.replace(hour=0, minute=0, second=0, microsecond=0):
        reasons.append("invalid_day_basis")
    if ledger.halted or state.reconciliation_halts:
        reasons.append("account_halted")
    if any(len(ids) >= MAX_IDENTITIES for ids in (
            state.intent_ids, state.order_ids, state.fill_ids, state.event_ids)):
        reasons.append("identity_capacity_exhausted")
    if now == ledger.as_of and ledger.phase > PHASES[EntryFill]:
        reasons.append("entry_event_ordering")
    remaining = max(ZERO, p.request.quantity - p.filled_quantity)
    if not remaining:
        reasons.append("no_remaining_quantity")
    if (p.filled_quantity > p.request.quantity or p.posted_margin > p.request.posted_margin
            or p.fees > p.fee_ceiling):
        reasons.append("pending_intent_bounds_breached")
    index = plan.symbols.index(p.request.symbol)
    target = ledger.baskets[index]
    if not target.quantity or not target.first_fill:
        # A request ceiling cannot invent a favorable first-fill stress anchor
        # or prove a broker can post the required buffer before the first gap.
        reasons.append("first_fill_or_posted_buffer_unproven")
    if target.entered_quantity < p.filled_quantity:
        reasons.append("pending_position_cycle_changed")
    if target.broker_leverage != p.request.requested_leverage:
        reasons.append("broker_leverage_changed")
    c = plan.contracts[index]
    future_fee = remaining * p.request.maximum_fill_price * c.entry_fee_rate
    if future_fee > p.fee_reserved:
        reasons.append("remaining_fee_reservation_exceeded")
    if remaining != floor_step(remaining, c.quantity_step):
        reasons.append("invalid_remaining_quantity_step")

    cash_after = ledger.unposted_cash - future_fee
    projected_equity = cash_after
    # Charge the full remaining fee even at the zero-quantity endpoint. This
    # also covers unusual fee timing without assuming a fee rebate.
    gap_before = gap_after = cash_after
    unused_costs = remaining_margin = restoration = ZERO
    floors = []
    required = None
    for i, (b, contract, budget, gap) in enumerate(zip(
            ledger.baskets, plan.contracts, plan.budgets, scenario.minimum_marks, strict=True)):
        extra = remaining if i == index else ZERO
        quantity = b.quantity + extra
        old_basis = b.quantity * b.average_entry
        basis = old_basis + extra * p.request.maximum_fill_price
        fee = future_fee if i == index else ZERO
        floor = min(b.mark, gap.price, b.first_fill * D(".5")) if b.quantity else min(b.mark, gap.price)
        floors.append(LedgerMark(b.symbol, floor))
        projected_equity += b.isolated_balance + quantity * b.mark - basis
        gap_before += b.isolated_balance + b.quantity * floor - old_basis
        gap_after += b.isolated_balance + quantity * floor - basis
        costs = b.charges_in_budget_epoch + fee
        if b.margin_committed > budget.margin_capital or costs > budget.cost_reserve:
            reasons.append("basket_capital_or_cost_limit")
        unused_costs += max(ZERO, budget.cost_reserve - costs)
        remaining_margin += max(ZERO, budget.margin_capital - b.margin_committed)
        restoration += max(ZERO, b.margin_committed - b.isolated_balance)
        if not quantity:
            continue
        maximum_price = max(b.mark, b.average_entry, b.first_fill,
                            p.request.maximum_fill_price if extra else ZERO)
        try:
            tier = contract.schedule.tier_for(quantity * maximum_price)
            protected = tier.maintenance_rate + contract.protective_exit_fee_rate
            if protected >= 1:
                raise ValueError("invalid protected rate")
            if b.quantity and b.equity <= b.quantity * b.mark * protected:
                reasons.append("isolated_position_already_unsafe")
            if b.quantity and b.isolated_balance + b.quantity * floor - old_basis <= (
                    b.quantity * floor * protected):
                reasons.append("pre_fill_gap_liquidation")
            if b.isolated_balance + quantity * floor - basis <= quantity * floor * protected:
                reasons.append("remaining_fill_gap_liquidation")
            if b.broker_leverage > tier.maximum_leverage:
                reasons.append("contract_leverage_limit")
            if i == index:
                stress_needed = max(ZERO, old_basis - b.quantity * floor +
                                    b.quantity * floor * protected,
                                    basis - quantity * floor + quantity * floor * protected)
                strict_stress = floor_step(stress_needed, plan.quantum) + plan.quantum
                nominal_needed = quantity * maximum_price / p.request.requested_leverage
                nominal_rounded = floor_step(nominal_needed, plan.quantum)
                if nominal_rounded < nominal_needed:
                    nominal_rounded += plan.quantum
                required = max(strict_stress, nominal_rounded)
                if b.isolated_balance < nominal_needed:
                    reasons.append("remaining_initial_margin_requirement")
        except ValueError:
            reasons.append("missing_or_invalid_margin_coverage")
    headroom = min(projected_equity - ledger.day_start_equity * D(".94"),
                   projected_equity - plan.initial_equity * D(".92"))
    if min(ledger.equity - ledger.day_start_equity * D(".94"),
           ledger.equity - plan.initial_equity * D(".92"), headroom) <= 0:
        reasons.append("account_loss_limit")
    account_floor = max(ledger.day_start_equity * D(".94"), plan.initial_equity * D(".92"))
    if gap_before <= account_floor:
        reasons.append("pre_fill_gap_account_loss")
    if gap_before - unused_costs < account_floor:
        reasons.append("pre_fill_gap_cost_coverage")
    stress_loss = projected_equity - gap_after
    if stress_loss + unused_costs > headroom:
        reasons.append("correlated_remaining_fill_stress")
    if cash_after < remaining_margin + unused_costs + restoration + plan.remainder:
        reasons.append("insufficient_unposted_cash")
    if not target.quantity:
        required = None  # no invented first-fill price or broker buffer requirement
    return ContinuationAssessment(
        not reasons, tuple(dict.fromkeys(reasons)), state.state_digest,
        digest((VERSION, scenario)), now, remaining, future_fee, p.margin_reserved,
        tuple(floors), ledger.equity, projected_equity, gap_before, gap_after,
        headroom, stress_loss, required, target.isolated_balance,
        max(ZERO, required - target.isolated_balance) if required is not None else None,
    )
