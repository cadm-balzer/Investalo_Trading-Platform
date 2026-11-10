"""Offline allocation proposal; no strategy activation or execution authority."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from decimal import Decimal

from .models import floor_step, positive, precise, utc
from .snapshot import digest

D = Decimal
ALLOCATION_VERSION = "equal-spot-stress-proposal/1"


def identifier(value: str) -> None:
    if not isinstance(value, str) or not value or len(value) > 128 or value.strip() != value:
        raise ValueError("invalid allocation identifier")


def revision(value: int) -> None:
    if type(value) is not int or value < 0:
        raise ValueError("invalid allocation revision")


@dataclass(frozen=True)
class AllocationPlan:
    tenant_id: str
    account_id: str
    symbols: tuple[str, ...]
    initial_capital: Decimal
    cost_ratio: Decimal
    quantum: Decimal = D("0.00000001")

    @precise
    def __post_init__(self) -> None:
        identifier(self.tenant_id)
        identifier(self.account_id)
        if type(self.symbols) is not tuple or not 3 <= len(self.symbols) <= 5:
            raise ValueError("a proposal requires three to five symbols")
        for symbol in self.symbols:
            identifier(symbol)
        if len(set(self.symbols)) != len(self.symbols):
            raise ValueError("duplicate symbol")
        for name in ("initial_capital", "cost_ratio", "quantum"):
            positive(getattr(self, name), name)
        if self.cost_ratio >= 1 or self.slot_principal <= 0:
            raise ValueError("invalid cost ratio or allocation precision")
        object.__setattr__(self, "symbols", tuple(sorted(self.symbols)))

    @property
    @precise
    def slot_total(self) -> Decimal:
        return floor_step(self.initial_capital / len(self.symbols), self.quantum)

    @property
    @precise
    def slot_principal(self) -> Decimal:
        return floor_step(self.slot_total / (1 + self.cost_ratio), self.quantum)

    @property
    @precise
    def slot_costs(self) -> Decimal:
        return self.slot_total - self.slot_principal

    @property
    @precise
    def remainder(self) -> Decimal:
        return self.initial_capital - len(self.symbols) * self.slot_total

    @property
    @precise
    def stages(self) -> tuple[Decimal, ...]:
        """Five regular stages and one manual reserve, all rounded down."""
        weights = tuple(D("1.25") ** i for i in range(6))
        return tuple(floor_step(self.slot_principal * w / sum(weights), self.quantum)
                     for w in weights)

    @property
    def plan_digest(self) -> str:
        return digest((ALLOCATION_VERSION, self, D("0.06"), D("0.08"), D("0.5"), 30))


@dataclass(frozen=True)
class AssetUse:
    symbol: str
    principal_spent: Decimal
    fees_spent: Decimal
    quantity: Decimal
    bid: Decimal
    marked_at: datetime
    first_fill: Decimal | None = None

    def __post_init__(self) -> None:
        identifier(self.symbol)
        for name in ("principal_spent", "fees_spent", "quantity"):
            positive(getattr(self, name), name, zero=True)
        positive(self.bid, "bid")
        object.__setattr__(self, "marked_at", utc(self.marked_at))
        if self.first_fill is not None:
            positive(self.first_fill, "first_fill")
        if (self.quantity > 0 or self.principal_spent > 0) and self.first_fill is None:
            raise ValueError("spent/held basket requires its first fill")
        if self.first_fill is not None and self.principal_spent == 0:
            raise ValueError("first fill requires principal spending")


@dataclass(frozen=True)
class PurchaseRequest:
    tenant_id: str
    account_id: str
    plan_digest: str
    expected_revision: int
    intent_id: str
    symbol: str
    principal: Decimal
    estimated_fee: Decimal
    maximum_price: Decimal

    def __post_init__(self) -> None:
        for name in ("tenant_id", "account_id", "plan_digest", "intent_id", "symbol"):
            identifier(getattr(self, name))
        revision(self.expected_revision)
        for name in ("principal", "maximum_price"):
            positive(getattr(self, name), name)
        positive(self.estimated_fee, "estimated_fee", zero=True)


@dataclass(frozen=True)
class BuyReservation:
    request: PurchaseRequest
    status: str = "open"

    def __post_init__(self) -> None:
        if not isinstance(self.request, PurchaseRequest):
            raise ValueError("invalid reserved purchase")
        if self.status not in ("open", "unknown", "cancel_requested"):
            raise ValueError("only unresolved buys belong in reservations")


@dataclass(frozen=True)
class AllocationView:
    tenant_id: str
    account_id: str
    plan_digest: str
    revision: int
    as_of: datetime
    day_started_at: datetime
    day_start_equity: Decimal
    cash: Decimal
    assets: tuple[AssetUse, ...]
    reservations: tuple[BuyReservation, ...] = ()
    halted: bool = False

    def __post_init__(self) -> None:
        for name in ("tenant_id", "account_id", "plan_digest"):
            identifier(getattr(self, name))
        revision(self.revision)
        positive(self.day_start_equity, "day_start_equity")
        positive(self.cash, "cash", zero=True)
        object.__setattr__(self, "as_of", utc(self.as_of))
        object.__setattr__(self, "day_started_at", utc(self.day_started_at))
        if type(self.halted) is not bool:
            raise ValueError("invalid halt flag")
        if type(self.assets) is not tuple or type(self.reservations) is not tuple:
            raise ValueError("allocation records must be immutable tuples")
        if any(not isinstance(a, AssetUse) for a in self.assets):
            raise ValueError("invalid asset record")
        if any(not isinstance(r, BuyReservation) for r in self.reservations):
            raise ValueError("invalid reservation record")
        if len({a.symbol for a in self.assets}) != len(self.assets):
            raise ValueError("duplicate asset record")
        if len({r.request.intent_id for r in self.reservations}) != len(self.reservations):
            raise ValueError("duplicate reservation identity")
        if len({r.request.symbol for r in self.reservations}) != len(self.reservations):
            raise ValueError("overlapping unresolved buys")
        object.__setattr__(self, "assets", tuple(sorted(self.assets, key=lambda a: a.symbol)))
        object.__setattr__(self, "reservations", tuple(sorted(
            self.reservations, key=lambda r: r.request.intent_id)))

    @property
    @precise
    def equity(self) -> Decimal:
        return self.cash + sum((a.quantity * a.bid for a in self.assets), D("0"))


@dataclass(frozen=True)
class PurchaseAssessment:
    allowed: bool
    reasons: tuple[str, ...]
    view_digest: str
    equity: Decimal
    daily_headroom: Decimal
    initial_headroom: Decimal
    holding_stress: Decimal
    pending_stress: Decimal
    unused_costs: Decimal
    projected_loss: Decimal
    maximum_principal: Decimal


@precise
def assess_purchase(plan: AllocationPlan, view: AllocationView,
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
    initial = view.equity - plan.initial_capital * D("0.92")
    headroom = min(daily, initial)
    if headroom <= 0:
        reasons.append("account_loss_limit")
    unused_costs = sum((max(D("0"), plan.slot_costs - a.fees_spent)
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
                > plan.slot_principal or
                a.fees_spent + sum((p.estimated_fee for p in pending), D("0"))
                > plan.slot_costs):
            reasons.append("existing_budget_overrun")
        if any(a.first_fill is not None and p.maximum_price > a.first_fill for p in pending):
            reasons.append("unbounded_pending_price")
    asset = by_symbol[request.symbol]
    if asset.first_fill is not None and request.maximum_price > asset.first_fill:
        reasons.append("unbounded_purchase_price")
    slot_remaining = plan.slot_principal - asset.principal_spent - sum(
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
    if request.estimated_fee > max(D("0"), plan.slot_costs - asset.fees_spent):
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


def reserve_purchase(plan: AllocationPlan, view: AllocationView,
                     request: PurchaseRequest, now: datetime) -> AllocationView:
    """Advance an immutable offline view; not durable CAS or broker dispatch."""
    assessment = assess_purchase(plan, view, request, now)
    if not assessment.allowed:
        raise ValueError("purchase rejected: " + ",".join(assessment.reasons))
    return replace(view, revision=view.revision + 1,
                   reservations=view.reservations + (BuyReservation(request),))
