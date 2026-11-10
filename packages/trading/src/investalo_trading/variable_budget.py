"""Offline mixed slot budgets with the unchanged independent account risk gates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from .allocation import (
    AllocationView, PurchaseAssessment, PurchaseRequest, identifier,
)
from .models import floor_step, positive, precise, utc
from .snapshot import digest

D = Decimal
VARIABLE_VERSION = "variable-slot-stress-research/1"


@dataclass(frozen=True)
class SlotLimit:
    symbol: str
    principal: Decimal
    costs: Decimal

    def __post_init__(self) -> None:
        identifier(self.symbol)
        positive(self.principal, "slot principal")
        positive(self.costs, "slot costs", zero=True)


@dataclass(frozen=True)
class VariablePlan:
    """Frozen budgets; funded capital is separate from the initial loss basis.

    The caller authorizes budget epochs. This assessor does not mint capital,
    prove profit grants, reset cycle spending or authorize execution.
    """

    tenant_id: str
    account_id: str
    policy_digest: str
    initial_equity: Decimal
    quantum: Decimal
    remainder: Decimal
    limits: tuple[SlotLimit, ...]

    def __post_init__(self) -> None:
        for value in (self.tenant_id, self.account_id, self.policy_digest):
            identifier(value)
        positive(self.initial_equity, "initial equity")
        positive(self.quantum, "quantum")
        positive(self.remainder, "unallocated remainder", zero=True)
        if type(self.limits) is not tuple or not 3 <= len(self.limits) <= 7:
            raise ValueError("three to seven immutable slot budgets required")
        if any(not isinstance(limit, SlotLimit) for limit in self.limits):
            raise ValueError("slot limit records required")
        if len({limit.symbol for limit in self.limits}) != len(self.limits):
            raise ValueError("duplicate slot limit")
        object.__setattr__(self, "limits", tuple(sorted(self.limits, key=lambda limit: limit.symbol)))

    @property
    def symbols(self) -> tuple[str, ...]:
        return tuple(limit.symbol for limit in self.limits)

    @property
    def plan_digest(self) -> str:
        return digest((VARIABLE_VERSION, self, D("0.06"), D("0.08"), D("0.5"), 30))


@precise
def assess_purchase(plan: VariablePlan, view: AllocationView,
                    request: PurchaseRequest, now: datetime) -> PurchaseAssessment:
    """Caller must supply complete authenticated holdings and order evidence."""
    now = utc(now)
    context = (plan.tenant_id, plan.account_id, plan.plan_digest)
    if (view.tenant_id, view.account_id, view.plan_digest) != context:
        raise ValueError("foreign allocation view")
    if (request.tenant_id, request.account_id, request.plan_digest) != context:
        raise ValueError("foreign purchase request")
    if tuple(a.symbol for a in view.assets) != plan.symbols or request.symbol not in plan.symbols:
        raise ValueError("incomplete or foreign exposure")
    by_symbol = {a.symbol: a for a in view.assets}
    limits = {limit.symbol: limit for limit in plan.limits}
    for reservation in view.reservations:
        pending = reservation.request
        if ((pending.tenant_id, pending.account_id, pending.plan_digest) != context
                or pending.symbol not in by_symbol
                or pending.expected_revision >= view.revision):
            raise ValueError("foreign or uncommitted reservation")
    reasons: list[str] = []
    if request.expected_revision != view.revision:
        reasons.append("stale_revision")
    if not timedelta(0) <= now - view.as_of <= timedelta(seconds=30):
        reasons.append("stale_or_future_view")
    if any(a.marked_at != view.as_of for a in view.assets):
        reasons.append("incomplete_mark_batch")
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if view.day_started_at != midnight or view.as_of < midnight:
        reasons.append("invalid_day_basis")
    if view.halted:
        reasons.append("account_halted")
    daily = view.equity - view.day_start_equity * D("0.94")
    initial = view.equity - plan.initial_equity * D("0.92")
    headroom = min(daily, initial)
    if headroom <= 0:
        reasons.append("account_loss_limit")
    unused_costs = sum((max(D("0"), limits[a.symbol].costs - a.fees_spent)
                        for a in view.assets), D("0"))
    holding_stress = sum((max(D("0"), a.quantity * (a.bid - D("0.5") * a.first_fill))
                          for a in view.assets if a.first_fill is not None), D("0"))
    pending_principal = sum((r.request.principal for r in view.reservations), D("0"))
    pending_stress = D("0.5") * pending_principal
    if any(r.status != "open" for r in view.reservations):
        reasons.append("unresolved_order_outcome")
    if any(r.request.symbol == request.symbol or r.request.intent_id == request.intent_id
           for r in view.reservations):
        reasons.append("overlapping_reservation")
    for a in view.assets:
        pending = tuple(r.request for r in view.reservations if r.request.symbol == a.symbol)
        if (a.principal_spent + sum((p.principal for p in pending), D("0"))
                > limits[a.symbol].principal or
                a.fees_spent + sum((p.estimated_fee for p in pending), D("0"))
                > limits[a.symbol].costs):
            reasons.append("existing_budget_overrun")
        if any(a.first_fill is not None and p.maximum_price > a.first_fill for p in pending):
            reasons.append("unbounded_pending_price")
    asset = by_symbol[request.symbol]
    if asset.first_fill is not None and request.maximum_price > asset.first_fill:
        reasons.append("unbounded_purchase_price")
    slot_remaining = limits[request.symbol].principal - asset.principal_spent - sum(
        (r.request.principal for r in view.reservations if r.request.symbol == request.symbol),
        D("0"))
    cash_remaining = view.cash - pending_principal - unused_costs - plan.remainder
    risk_remaining = D("2") * (headroom - holding_stress - pending_stress - unused_costs)
    maximum = floor_step(max(D("0"), min(slot_remaining, cash_remaining, risk_remaining)),
                         plan.quantum)
    if request.principal != floor_step(request.principal, plan.quantum):
        reasons.append("principal_precision")
    if request.principal > slot_remaining:
        reasons.append("basket_budget")
    if request.estimated_fee > max(D("0"), limits[request.symbol].costs - asset.fees_spent):
        reasons.append("fee_budget")
    if request.principal > cash_remaining:
        reasons.append("cash_budget")
    projected = holding_stress + pending_stress + D("0.5") * request.principal + unused_costs
    if projected > headroom:
        reasons.append("correlated_stress")
    # A bound is usable only when every prerequisite is valid.
    prerequisites = set(reasons) - {
        "basket_budget", "cash_budget", "correlated_stress", "principal_precision"}
    if prerequisites:
        maximum = D("0")
    return PurchaseAssessment(not reasons, tuple(dict.fromkeys(reasons)), digest(view),
                              view.equity, daily, initial, holding_stress, pending_stress,
                              unused_costs, projected, maximum)
