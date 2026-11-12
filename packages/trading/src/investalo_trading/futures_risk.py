"""Offline isolated-long purchase assessment; trusted snapshots, no execution authority."""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from decimal import Decimal

from .allocation import identifier, revision
from .futures_economics import LongPosition, MarginSchedule, liquidation_bound, _fraction
from .models import floor_step, positive, precise, utc
from .snapshot import digest

D = Decimal
RISK_VERSION = "isolated-usdt-long-stress/1"


@dataclass(frozen=True)
class FuturesContract:
    symbol: str
    quantity_step: Decimal
    minimum_quantity: Decimal
    minimum_notional: Decimal
    entry_fee_rate: Decimal
    protective_exit_fee_rate: Decimal
    schedule: MarginSchedule
    assumptions_digest: str

    def __post_init__(self):
        identifier(self.symbol)
        identifier(self.assumptions_digest)
        positive(self.quantity_step, "quantity step")
        positive(self.minimum_quantity, "minimum quantity", zero=True)
        positive(self.minimum_notional, "minimum notional", zero=True)
        _fraction(self.entry_fee_rate, "entry fee rate")
        _fraction(self.protective_exit_fee_rate, "protective exit fee rate")
        if not isinstance(self.schedule, MarginSchedule):
            raise ValueError("explicit maintenance assumptions required")


@dataclass(frozen=True)
class FuturesBudget:
    symbol: str
    capital: Decimal
    cost_reserve: Decimal

    def __post_init__(self):
        identifier(self.symbol)
        positive(self.capital, "basket capital")
        positive(self.cost_reserve, "cost reserve", zero=True)
        if self.cost_reserve >= self.capital:
            raise ValueError("basket needs margin capital")

    @property
    @precise
    def margin_capital(self):
        return self.capital - self.cost_reserve


@dataclass(frozen=True)
class FuturesPlan:
    tenant_id: str
    account_id: str
    policy_digest: str
    initial_equity: Decimal
    quantum: Decimal
    remainder: Decimal
    contracts: tuple[FuturesContract, ...]
    budgets: tuple[FuturesBudget, ...]

    def __post_init__(self):
        for name in (self.tenant_id, self.account_id, self.policy_digest):
            identifier(name)
        positive(self.initial_equity, "original initial equity")
        positive(self.quantum, "money quantum")
        positive(self.remainder, "reserved remainder", zero=True)
        for rows, kind in ((self.contracts, FuturesContract), (self.budgets, FuturesBudget)):
            if type(rows) is not tuple or not 3 <= len(rows) <= 7 or any(
                    not isinstance(row, kind) for row in rows):
                raise ValueError("three to seven immutable funded slots required")
            if len({row.symbol for row in rows}) != len(rows):
                raise ValueError("duplicate funded symbol")
        object.__setattr__(self, "contracts", tuple(sorted(self.contracts, key=lambda c: c.symbol)))
        object.__setattr__(self, "budgets", tuple(sorted(self.budgets, key=lambda b: b.symbol)))
        if self.symbols != tuple(b.symbol for b in self.budgets):
            raise ValueError("complete contract and budget bindings required")

    @property
    def symbols(self):
        return tuple(c.symbol for c in self.contracts)

    @property
    def plan_digest(self):
        return digest((RISK_VERSION, self, D(".06"), D(".08"), D(".5"), 30))

    def ledger_halt_reasons(self, reasons):
        """Legacy policy remains hard; separate research plans may specialize it."""
        return tuple(dict.fromkeys(reasons))


@dataclass(frozen=True)
class FuturesExposure:
    symbol: str
    mark: Decimal
    marked_at: datetime
    position: LongPosition | None = None
    fees_spent: Decimal = D("0")
    pending_margin: Decimal = D("0")
    unresolved_order: bool = False

    def __post_init__(self):
        identifier(self.symbol)
        positive(self.mark, "mark price")
        utc(self.marked_at)
        if self.position is not None and not isinstance(self.position, LongPosition):
            raise ValueError("linear long position required")
        positive(self.fees_spent, "booked fees and funding charges", zero=True)
        positive(self.pending_margin, "pending margin", zero=True)
        if type(self.unresolved_order) is not bool or self.pending_margin and not self.unresolved_order:
            raise ValueError("pending margin requires unresolved order evidence")


@dataclass(frozen=True)
class FuturesView:
    tenant_id: str
    account_id: str
    plan_digest: str
    revision: int
    as_of: datetime
    day_started_at: datetime
    day_start_equity: Decimal
    unposted_cash: Decimal
    exposures: tuple[FuturesExposure, ...]
    halted: bool = False

    def __post_init__(self):
        for value in (self.tenant_id, self.account_id, self.plan_digest):
            identifier(value)
        revision(self.revision)
        utc(self.as_of)
        utc(self.day_started_at)
        positive(self.day_start_equity, "day start equity")
        positive(self.unposted_cash, "unposted cash", zero=True)
        if type(self.exposures) is not tuple or not 3 <= len(self.exposures) <= 7 or any(
                not isinstance(e, FuturesExposure) for e in self.exposures):
            raise ValueError("complete immutable futures exposures required")
        if type(self.halted) is not bool:
            raise ValueError("boolean account halt required")

    @property
    @precise
    def equity(self):
        return self.unposted_cash + sum((e.position.equity(e.mark) for e in self.exposures
                                        if e.position is not None), D("0"))


@dataclass(frozen=True)
class FuturesPurchase:
    tenant_id: str
    account_id: str
    plan_digest: str
    expected_revision: int
    symbol: str
    quantity: Decimal
    maximum_fill_price: Decimal
    posted_margin: Decimal
    requested_leverage: Decimal

    def __post_init__(self):
        for value in (self.tenant_id, self.account_id, self.plan_digest, self.symbol):
            identifier(value)
        revision(self.expected_revision)
        for name in ("quantity", "maximum_fill_price", "posted_margin", "requested_leverage"):
            positive(getattr(self, name), name)
        if not D("2") <= self.requested_leverage <= D("10"):
            raise ValueError("requested leverage must be within approved research range2–10")


@dataclass(frozen=True)
class FuturesAssessment:
    allowed: bool
    reasons: tuple[str, ...]
    plan_digest: str
    view_digest: str
    request_digest: str
    current_equity: Decimal
    projected_equity: Decimal
    headroom: Decimal
    stress_loss: Decimal
    unused_cost_reserve: Decimal
    unposted_cash_after: Decimal
    remaining_margin_reserve: Decimal
    minimum_posted_margin: Decimal | None
    effective_entry_leverage: Decimal
    conservative_liquidation_bound: Decimal | None
    execution_enabled: bool = False

    def __post_init__(self):
        if self.execution_enabled is not False:
            raise ValueError("offline assessment cannot enable execution")


@precise
def assess_futures_purchase(plan: FuturesPlan, view: FuturesView,
                            request: FuturesPurchase, now: datetime) -> FuturesAssessment:
    """Project one worst-price full fill. Caller supplies reconciled funded budgets.

    This is not a fill ledger, persistent reservation, regime verdict or broker
    liquidation replica. All unresolved orders block this first research assessor.
    Fees/funding in the input snapshot must already be booked in cash/collateral.
    """
    now = utc(now)
    context = (plan.tenant_id, plan.account_id, plan.plan_digest)
    if (view.tenant_id, view.account_id, view.plan_digest) != context or (
            request.tenant_id, request.account_id, request.plan_digest) != context:
        raise ValueError("foreign futures context")
    if tuple(e.symbol for e in view.exposures) != plan.symbols or request.symbol not in plan.symbols:
        raise ValueError("incomplete or foreign futures exposure")
    contracts = {c.symbol: c for c in plan.contracts}
    budgets = {b.symbol: b for b in plan.budgets}
    exposures = {e.symbol: e for e in view.exposures}
    reasons = []
    if request.expected_revision != view.revision:
        reasons.append("stale_revision")
    if not timedelta(0) <= now - utc(view.as_of) <= timedelta(seconds=30):
        reasons.append("stale_or_future_marks")
    if any(e.marked_at != view.as_of for e in view.exposures):
        reasons.append("incomplete_mark_batch")
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if view.day_started_at != midnight or view.as_of < midnight:
        reasons.append("invalid_day_basis")
    if view.halted:
        reasons.append("account_halted")
    if min(view.equity - view.day_start_equity * D(".94"),
           view.equity - plan.initial_equity * D(".92")) <= 0:
        reasons.append("account_loss_limit")
    if any(e.unresolved_order for e in view.exposures):
        reasons.append("orders_require_reconciliation")
    for existing in view.exposures:
        if existing.position is None:
            continue
        p, c = existing.position, contracts[existing.symbol]
        try:
            maximum_mark = max(existing.mark, p.average_entry, p.first_fill)
            rate = c.schedule.tier_for(p.notional(maximum_mark)).maintenance_rate
            if p.equity(existing.mark) <= p.notional(existing.mark) * (
                    rate + c.protective_exit_fee_rate):
                reasons.append("isolated_position_already_unsafe")
        except ValueError:
            reasons.append("missing_or_invalid_margin_coverage")
    contract, before = contracts[request.symbol], exposures[request.symbol]
    if request.maximum_fill_price < before.mark:
        reasons.append("fill_bound_below_mark")
    if request.quantity != floor_step(request.quantity, contract.quantity_step):
        reasons.append("invalid_quantity_step")
    nominal = request.quantity * request.maximum_fill_price
    if request.quantity < contract.minimum_quantity or nominal < contract.minimum_notional:
        reasons.append("below_contract_minimum")
    entry_fee = nominal * contract.entry_fee_rate
    old = before.position
    quantity = request.quantity + (old.quantity if old else D("0"))
    average = (nominal + (old.quantity * old.average_entry if old else D("0"))) / quantity
    projected = LongPosition(quantity, average, old.first_fill if old else request.maximum_fill_price,
                             request.posted_margin + (old.posted_margin if old else D("0")))
    exposures[request.symbol] = replace(before, position=projected,
                                       fees_spent=before.fees_spent + entry_fee)
    cash_after = view.unposted_cash - request.posted_margin - entry_fee
    equity_after = cash_after + sum((e.position.equity(e.mark) for e in exposures.values()
                                    if e.position is not None), D("0"))
    headroom = min(equity_after - view.day_start_equity * D(".94"),
                   equity_after - plan.initial_equity * D(".92"))
    if headroom <= 0:
        reasons.append("account_loss_limit")
    remaining_margin = unused_costs = pending_margin = stress_loss = D("0")
    required = bound = None
    for symbol, e in exposures.items():
        budget, c, p = budgets[symbol], contracts[symbol], e.position
        posted = p.posted_margin if p else D("0")
        if posted + e.pending_margin > budget.margin_capital or e.fees_spent > budget.cost_reserve:
            reasons.append("basket_capital_or_cost_limit")
        remaining_margin += max(D("0"), budget.margin_capital - posted - e.pending_margin)
        unused_costs += max(D("0"), budget.cost_reserve - e.fees_spent)
        pending_margin += e.pending_margin
        if p is None:
            continue
        stress_mark = min(e.mark, p.first_fill * D(".5"))
        stress_loss += p.quantity * (e.mark - stress_mark)
        maximum_mark = max(e.mark, p.average_entry, p.first_fill)
        try:
            tier = c.schedule.tier_for(p.notional(maximum_mark))
            protected_rate = tier.maintenance_rate + c.protective_exit_fee_rate
            if protected_rate >= 1:
                raise ValueError("invalid maintenance protection")
            needed = max(D("0"), -p.unrealized_pnl(stress_mark) +
                         p.notional(stress_mark) * protected_rate)
            mark_floor = liquidation_bound(p, c.schedule, c.protective_exit_fee_rate, maximum_mark)
            if p.equity(stress_mark) <= p.notional(stress_mark) * protected_rate:
                reasons.append("isolated_stress_liquidation")
            if p.equity(e.mark) <= p.notional(e.mark) * protected_rate:
                reasons.append("isolated_position_already_unsafe")
            if symbol == request.symbol:
                # Strict surplus: equality at the protection boundary is unsafe.
                required = floor_step(needed, plan.quantum) + plan.quantum
                bound = mark_floor
                if request.requested_leverage > tier.maximum_leverage:
                    reasons.append("contract_leverage_limit")
                if projected.posted_margin < p.notional(maximum_mark) / request.requested_leverage:
                    reasons.append("initial_margin_requirement")
        except ValueError:
            reasons.append("missing_or_invalid_margin_coverage")
    if cash_after - pending_margin - remaining_margin - unused_costs - plan.remainder < 0:
        reasons.append("insufficient_unposted_cash")
    if stress_loss + unused_costs > headroom:
        reasons.append("correlated_account_stress")
    return FuturesAssessment(
        not reasons, tuple(dict.fromkeys(reasons)), plan.plan_digest, digest(view), digest(request),
        view.equity, equity_after, headroom, stress_loss, unused_costs, cash_after,
        remaining_margin, required, projected.quantity * projected.average_entry / projected.posted_margin,
        bound)
