"""Bounded offline intent/reconciliation model; trusted evidence, no dispatch or DB."""
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from decimal import Decimal

from .allocation import identifier, revision
from .futures_ledger import (
    EntryFill, ExitFill, FuturesLedgerState, LedgerCommand, LedgerTransition,
    PHASES, apply_futures_event, number, timestamp,
)
from .futures_risk import FuturesPlan, FuturesPurchase
from .models import floor_step, precise
from .snapshot import digest
from .identity_history import IdentityHistory, NAMESPACES

D = Decimal
ZERO = D("0")
VERSION = "isolated-usdt-long-pending/1"
LONG_VERSION = "isolated-usdt-long-pending/2"
MAX_IDENTITIES = 1024


@dataclass(frozen=True)
class PendingPurchase:
    intent_id: str
    request: FuturesPurchase
    prepared_at: datetime
    fee_ceiling: Decimal
    order_id: str | None = None
    filled_quantity: Decimal = ZERO
    posted_margin: Decimal = ZERO
    fees: Decimal = ZERO

    def __post_init__(self):
        identifier(self.intent_id)
        if not isinstance(self.request, FuturesPurchase):
            raise ValueError("immutable purchase required")
        timestamp(self.prepared_at)
        if self.order_id is not None:
            identifier(self.order_id)
        for value in (self.fee_ceiling, self.filled_quantity, self.posted_margin, self.fees):
            number(value, nonnegative=True)
        if self.order_id is None and any((self.filled_quantity, self.posted_margin, self.fees)):
            raise ValueError("fills require attempted order identity")

    @property
    @precise
    def margin_reserved(self):
        return max(ZERO, self.request.posted_margin - self.posted_margin)

    @property
    @precise
    def fee_reserved(self):
        return max(ZERO, self.fee_ceiling - self.fees)


@dataclass(frozen=True)
class OrderResolution:
    intent_id: str
    order_id: str
    filled_quantity: Decimal
    posted_margin: Decimal
    fees: Decimal
    terminal_status: str
    evidence_digest: str

    def __post_init__(self):
        for value in (self.intent_id, self.order_id, self.evidence_digest):
            identifier(value)
        for value in (self.filled_quantity, self.posted_margin, self.fees):
            number(value, nonnegative=True)
        if self.terminal_status not in ("filled", "cancelled", "rejected"):
            raise ValueError("explicit terminal reconciliation required")
        if self.terminal_status == "rejected" and any(
                (self.filled_quantity, self.posted_margin, self.fees)):
            raise ValueError("rejected order cannot have fills")


@dataclass(frozen=True)
class PendingResearchState:
    ledger: FuturesLedgerState
    revision: int
    as_of: datetime
    pending: PendingPurchase | None
    intent_ids: tuple[str, ...] | IdentityHistory
    order_ids: tuple[str, ...] | IdentityHistory
    fill_ids: tuple[str, ...] | IdentityHistory
    event_ids: tuple[str, ...] | IdentityHistory
    completed_intents: int
    reconciliation_halts: tuple[str, ...]
    audit_head: str

    def __post_init__(self):
        if not isinstance(self.ledger, FuturesLedgerState):
            raise ValueError("reconciled ledger required")
        revision(self.revision)
        revision(self.completed_intents)
        timestamp(self.as_of)
        if self.as_of < self.ledger.as_of:
            raise ValueError("wrapper predates economic ledger")
        identifier(self.audit_head)
        if type(self.reconciliation_halts) is not tuple:
            raise ValueError("immutable halt reasons required")
        histories = (self.intent_ids, self.order_ids, self.fill_ids, self.event_ids)
        if all(isinstance(values, IdentityHistory) for values in histories):
            if (tuple(values.namespace for values in histories) != NAMESPACES
                    or len({values.capacity for values in histories}) != 1):
                raise ValueError("own canonical long identity histories required")
        elif not all(type(values) is tuple for values in histories):
            raise ValueError("cannot mix bounded and long identity histories")
        for values in (*histories, self.reconciliation_halts):
            if isinstance(values, IdentityHistory):
                continue
            if (type(values) is not tuple or len(values) > MAX_IDENTITIES
                    or len(set(values)) != len(values)):
                raise ValueError("bounded unique immutable identities required")
            for value in values:
                identifier(value)
        if self.pending is not None:
            p, plan = self.pending, self.ledger.plan
            if not isinstance(p, PendingPurchase) or p.intent_id not in self.intent_ids:
                raise ValueError("pending intent identity missing")
            if (p.request.tenant_id, p.request.account_id, p.request.plan_digest) != (
                    plan.tenant_id, plan.account_id, plan.plan_digest):
                raise ValueError("foreign pending context")
            if (p.request.symbol not in plan.symbols or p.prepared_at > self.as_of
                    or p.order_id is not None and p.order_id not in self.order_ids):
                raise ValueError("pending order binding missing")

    @property
    def state_digest(self):
        return digest((self.version, self))

    @property
    def version(self):
        return LONG_VERSION if isinstance(self.intent_ids, IdentityHistory) else VERSION


@dataclass(frozen=True)
class LedgerPurchaseAssessment:
    allowed: bool
    reasons: tuple[str, ...]
    state_digest: str
    request_digest: str
    current_equity: Decimal
    projected_equity: Decimal
    headroom: Decimal
    stress_loss: Decimal
    remaining_margin_reserve: Decimal
    unused_cost_reserve: Decimal
    outstanding_cost_restoration: Decimal
    cash_after: Decimal
    minimum_isolated_balance: Decimal | None
    effective_entry_leverage: Decimal | None
    execution_enabled: bool = False

    def __post_init__(self):
        if self.execution_enabled is not False:
            raise ValueError("offline assessment cannot enable execution")


@dataclass(frozen=True)
class PendingTransition:
    state: PendingResearchState
    prior_digest: str
    command_digest: str
    ledger_transition: LedgerTransition | None = None
    assessment: LedgerPurchaseAssessment | None = None
    execution_enabled: bool = False

    def __post_init__(self):
        if self.execution_enabled is not False:
            raise ValueError("offline transition cannot enable execution")


def start_pending_research(ledger: FuturesLedgerState) -> PendingResearchState:
    """Wrap a trusted reconciled ledger, not restore an uncertain broker account."""
    if type(ledger.plan) is not FuturesPlan:
        raise ValueError("legacy pending wrapper requires its legacy futures plan")
    return PendingResearchState(ledger, 0, ledger.as_of, None, (), (), (), (), 0, (),
                                digest((VERSION, ledger.state_digest)))


def start_long_pending_research(ledger: FuturesLedgerState, *, identity_capacity=50_000):
    """Fresh research genesis only. Existing evidence cannot be reset or converted."""
    if (not isinstance(ledger, FuturesLedgerState) or type(ledger.plan) is not FuturesPlan
            or ledger.revision != 0
            or any(b.quantity or b.cycle for b in ledger.baskets)):
        raise ValueError("fresh flat ledger genesis required; not a restore API")
    histories = tuple(IdentityHistory(namespace, identity_capacity) for namespace in NAMESPACES)
    return PendingResearchState(ledger, 0, ledger.as_of, None, *histories, 0, (),
                                digest((LONG_VERSION, ledger.state_digest, histories)))


@precise
def assess_ledger_purchase(state: PendingResearchState, request: FuturesPurchase,
                           now: datetime) -> LedgerPurchaseAssessment:
    """Worst full fill using gross budgets and signed net collateral separately."""
    now = timestamp(now)
    ledger, plan = state.ledger, state.ledger.plan
    if (request.tenant_id, request.account_id, request.plan_digest) != (
            plan.tenant_id, plan.account_id, plan.plan_digest) or request.symbol not in plan.symbols:
        raise ValueError("foreign purchase context")
    reasons = []
    if request.expected_revision != state.revision:
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
    if now == ledger.as_of and ledger.phase > PHASES[EntryFill]:
        reasons.append("entry_event_ordering")
    if min(ledger.equity - ledger.day_start_equity * D(".94"),
           ledger.equity - plan.initial_equity * D(".92")) <= 0:
        reasons.append("account_loss_limit")
    if state.pending is not None:
        reasons.append("orders_require_reconciliation")
    if any(len(ids) >= (ids.capacity if isinstance(ids, IdentityHistory) else MAX_IDENTITIES) for ids in (
            state.intent_ids, state.order_ids, state.fill_ids, state.event_ids)):
        reasons.append("identity_capacity_exhausted")
    index = plan.symbols.index(request.symbol)
    before, contract = ledger.baskets[index], plan.contracts[index]
    if request.maximum_fill_price < before.mark:
        reasons.append("fill_bound_below_mark")
    if request.quantity != floor_step(request.quantity, contract.quantity_step):
        reasons.append("invalid_quantity_step")
    nominal = request.quantity * request.maximum_fill_price
    if request.quantity < contract.minimum_quantity or nominal < contract.minimum_notional:
        reasons.append("below_contract_minimum")
    entry_fee = nominal * contract.entry_fee_rate
    quantity = before.quantity + request.quantity
    projected = replace(
        before, cycle=before.cycle if before.quantity else before.cycle + 1,
        quantity=quantity,
        average_entry=(before.quantity * before.average_entry + nominal) / quantity,
        first_fill=before.first_fill if before.quantity else request.maximum_fill_price,
        margin_committed=before.margin_committed + request.posted_margin,
        isolated_balance=before.isolated_balance + request.posted_margin,
        broker_leverage=request.requested_leverage,
        charges_in_budget_epoch=before.charges_in_budget_epoch + entry_fee,
        entry_fees=before.entry_fees + entry_fee,
        entered_quantity=before.entered_quantity + request.quantity,
        opened_at=before.opened_at if before.quantity else now,
    )
    baskets = tuple(projected if i == index else b for i, b in enumerate(ledger.baskets))
    cash_after = ledger.unposted_cash - request.posted_margin - entry_fee
    equity_after = cash_after + sum((b.equity for b in baskets), ZERO)
    headroom = min(equity_after - ledger.day_start_equity * D(".94"),
                   equity_after - plan.initial_equity * D(".92"))
    if headroom <= 0:
        reasons.append("account_loss_limit")
    remaining = unused_costs = restoration = stress_loss = ZERO
    required = None
    for original, b, c, budget in zip(
            ledger.baskets, baskets, plan.contracts, plan.budgets, strict=True):
        if b.margin_committed > budget.margin_capital or b.charges_in_budget_epoch > budget.cost_reserve:
            reasons.append("basket_capital_or_cost_limit")
        remaining += max(ZERO, budget.margin_capital - b.margin_committed)
        unused_costs += max(ZERO, budget.cost_reserve - b.charges_in_budget_epoch)
        restoration += max(ZERO, b.margin_committed - b.isolated_balance)
        if not b.quantity:
            continue
        stress_mark = min(b.mark, b.first_fill * D(".5"))
        stress_loss += b.quantity * (b.mark - stress_mark)
        try:
            tier = c.schedule.tier_for(b.quantity * max(b.mark, b.average_entry, b.first_fill))
            protected = tier.maintenance_rate + c.protective_exit_fee_rate
            if protected >= 1:
                raise ValueError("invalid protected rate")
            if original.quantity:
                old_tier = c.schedule.tier_for(original.quantity * max(
                    original.mark, original.average_entry, original.first_fill))
                if original.equity <= original.quantity * original.mark * (
                        old_tier.maintenance_rate + c.protective_exit_fee_rate):
                    reasons.append("isolated_position_already_unsafe")
            if b.isolated_balance + b.quantity * (stress_mark - b.average_entry) <= (
                    b.quantity * stress_mark * protected):
                reasons.append("isolated_stress_liquidation")
            if b.equity <= b.quantity * b.mark * protected:
                reasons.append("isolated_position_already_unsafe")
            if b.broker_leverage > tier.maximum_leverage:
                reasons.append("contract_leverage_limit")
            if b.symbol == request.symbol:
                needed = max(ZERO, b.quantity * (b.average_entry - stress_mark) +
                             b.quantity * stress_mark * protected)
                required = floor_step(needed, plan.quantum) + plan.quantum
                if b.isolated_balance < b.quantity * max(
                        b.mark, b.average_entry, b.first_fill) / request.requested_leverage:
                    reasons.append("initial_margin_requirement")
        except ValueError:
            reasons.append("missing_or_invalid_margin_coverage")
    pending_cash = state.pending.margin_reserved + state.pending.fee_reserved if state.pending else ZERO
    # Pending reservations are already part of the original future budgets.
    # Do not subtract them twice. Unknown orders independently block every buy.
    required_cash = remaining + unused_costs + restoration + plan.remainder
    if cash_after < required_cash or cash_after < pending_cash:
        reasons.append("insufficient_unposted_cash")
    if stress_loss + unused_costs > headroom:
        reasons.append("correlated_account_stress")
    effective = projected.quantity * projected.average_entry / projected.isolated_balance \
        if projected.isolated_balance > 0 else None
    return LedgerPurchaseAssessment(
        not reasons, tuple(dict.fromkeys(reasons)), state.state_digest, digest((state.version, request)),
        ledger.equity, equity_after, headroom, stress_loss, remaining, unused_costs,
        restoration, cash_after, required, effective,
    )


def _check(state, expected_revision, at):
    revision(expected_revision)
    timestamp(at)
    if expected_revision != state.revision:
        raise ValueError("stale pending revision")
    if at < state.as_of:
        raise ValueError("backdated pending event")


def _append(values, value):
    if isinstance(values, IdentityHistory):
        return values.append(value)
    identifier(value)
    if value in values:
        raise ValueError("duplicate evidence identity")
    if len(values) >= MAX_IDENTITIES:
        raise ValueError("identity capacity exhausted; never evict evidence")
    return (*values, value)


def _finish(state, at, body, *, ledger_transition=None, assessment=None, **changes):
    provisional = replace(state, revision=state.revision + 1, as_of=at, **changes)
    command_digest = digest((state.version, state.revision, at, body))
    result = replace(provisional, audit_head=digest((
        state.version, state.audit_head, command_digest, provisional.state_digest,
    )))
    return PendingTransition(result, state.state_digest, command_digest, ledger_transition, assessment)


@precise
def reserve_purchase(state: PendingResearchState, request: FuturesPurchase,
                     intent_id: str, at: datetime) -> PendingTransition:
    _check(state, request.expected_revision, at)
    assessment = assess_ledger_purchase(state, request, at)
    if not assessment.allowed:
        raise ValueError("purchase blocked: " + ",".join(assessment.reasons))
    c = state.ledger.plan.contracts[state.ledger.plan.symbols.index(request.symbol)]
    pending = PendingPurchase(intent_id, request, at,
                              request.quantity * request.maximum_fill_price * c.entry_fee_rate)
    return _finish(state, at, ("reserve", intent_id, request), pending=pending,
                   intent_ids=_append(state.intent_ids, intent_id), assessment=assessment)


def cancel_unattempted(state: PendingResearchState, intent_id: str,
                       expected_revision: int, at: datetime) -> PendingTransition:
    _check(state, expected_revision, at)
    if state.pending is None or state.pending.intent_id != intent_id or state.pending.order_id is not None:
        raise ValueError("only an unattempted own intent can be cancelled locally")
    return _finish(state, at, ("cancel-unattempted", intent_id), pending=None)


def record_order_attempt(state: PendingResearchState, intent_id: str, order_id: str,
                         expected_revision: int, at: datetime) -> PendingTransition:
    """Record uncertainty BEFORE any hypothetical external attempt; never authorize it."""
    _check(state, expected_revision, at)
    p = state.pending
    if p is None or p.intent_id != intent_id or p.order_id is not None:
        raise ValueError("order already attempted or intent missing")
    return _finish(state, at, ("attempt-uncertain", intent_id, order_id),
                   pending=replace(p, order_id=order_id),
                   order_ids=_append(state.order_ids, order_id))


def record_ledger_event(state: PendingResearchState, payload, event_id: str,
                        expected_revision: int, at: datetime) -> PendingTransition:
    _check(state, expected_revision, at)
    if type(payload) not in PHASES or isinstance(payload, (EntryFill, ExitFill)):
        raise ValueError("fills require broker fill identity")
    ids = _append(state.event_ids, event_id)
    plan = state.ledger.plan
    command = LedgerCommand(plan.tenant_id, plan.account_id, plan.plan_digest,
                            state.ledger.revision, event_id, at, payload)
    result = apply_futures_event(state.ledger, command)
    return _finish(state, at, ("ledger", command), ledger=result.state,
                   event_ids=ids, ledger_transition=result)


@precise
def record_fill(state: PendingResearchState, payload: EntryFill | ExitFill,
                order_id: str, fill_id: str, expected_revision: int,
                at: datetime) -> PendingTransition:
    """Book actual evidence once, including known outcomes exceeding the reservation."""
    _check(state, expected_revision, at)
    identifier(order_id)
    if type(payload) not in (EntryFill, ExitFill):
        raise ValueError("actual entry or exit fill required")
    ids = _append(state.fill_ids, fill_id)
    order_ids = state.order_ids if order_id in state.order_ids else _append(state.order_ids, order_id)
    p, breaches = state.pending, []
    if isinstance(payload, EntryFill):
        if p is None or p.order_id != order_id or p.request.symbol != payload.symbol:
            breaches.append("unplanned_entry_fill")
        else:
            p = replace(p, filled_quantity=p.filled_quantity + payload.quantity,
                        posted_margin=p.posted_margin + payload.posted_margin, fees=p.fees + payload.fee)
            if (p.filled_quantity > p.request.quantity or p.posted_margin > p.request.posted_margin
                    or p.fees > p.fee_ceiling or payload.price > p.request.maximum_fill_price
                    or payload.broker_leverage != p.request.requested_leverage):
                breaches.append("entry_fill_outside_intent")
    plan = state.ledger.plan
    command = LedgerCommand(plan.tenant_id, plan.account_id, plan.plan_digest,
                            state.ledger.revision, fill_id, at, payload)
    result = apply_futures_event(state.ledger, command)
    return _finish(state, at, ("fill", order_id, command), ledger=result.state, pending=p,
                   reconciliation_halts=tuple(dict.fromkeys((*state.reconciliation_halts, *breaches))),
                   fill_ids=ids, order_ids=order_ids, ledger_transition=result)


def reconcile_order(state: PendingResearchState, resolution: OrderResolution,
                    expected_revision: int, at: datetime) -> PendingTransition:
    """Caller attests final broker totals; a digest is not a broker/authenticity proof."""
    _check(state, expected_revision, at)
    p = state.pending
    if (p is None or (resolution.intent_id, resolution.order_id) != (p.intent_id, p.order_id)
            or (resolution.filled_quantity, resolution.posted_margin, resolution.fees) != (
                p.filled_quantity, p.posted_margin, p.fees)):
        raise ValueError("terminal reconciliation does not match booked order totals")
    if resolution.terminal_status == "filled" and resolution.filled_quantity < p.request.quantity:
        raise ValueError("filled status lacks remaining quantity")
    return _finish(state, at, ("terminal-reconciliation", resolution), pending=None,
                   completed_intents=state.completed_intents + 1)
