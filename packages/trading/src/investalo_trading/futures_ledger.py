"""Pure reconciled-event research ledger; no order authority, broker or persistence."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from decimal import Decimal

from .allocation import identifier, revision
from .futures_risk import FuturesPlan
from .models import floor_step, precise, utc
from .snapshot import digest

D = Decimal
VERSION = "isolated-usdt-long-ledger/1"
ZERO = D("0")


def number(value: Decimal, *, positive: bool = False, nonnegative: bool = False):
    if (not isinstance(value, Decimal) or not value.is_finite()
            or len(value.as_tuple().digits) > 36 or abs(value.as_tuple().exponent) > 72
            or value.copy_abs() > D("1e24")
            or value and value.copy_abs() < D("1e-72")
            or positive and value <= 0 or nonnegative and value < 0):
        raise ValueError("bounded Decimal required")


def timestamp(value: datetime):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("explicit UTC timestamp required")
    if value.year < 1970:
        raise ValueError("timestamp before Unix epoch")
    return utc(value)


@dataclass(frozen=True)
class LedgerMark:
    symbol: str
    price: Decimal

    def __post_init__(self):
        identifier(self.symbol)
        number(self.price, positive=True)


@dataclass(frozen=True)
class MarkBatch:
    marks: tuple[LedgerMark, ...]

    def __post_init__(self):
        if (type(self.marks) is not tuple or not 3 <= len(self.marks) <= 7
                or any(not isinstance(m, LedgerMark) for m in self.marks)
                or tuple(m.symbol for m in self.marks) != tuple(sorted({m.symbol for m in self.marks}))):
            raise ValueError("complete canonical immutable mark batch required")


@dataclass(frozen=True)
class EntryFill:
    symbol: str
    quantity: Decimal
    price: Decimal
    posted_margin: Decimal
    fee: Decimal
    broker_leverage: Decimal

    def __post_init__(self):
        identifier(self.symbol)
        for value in (self.quantity, self.price, self.broker_leverage):
            number(value, positive=True)
        number(self.posted_margin, nonnegative=True)
        number(self.fee, nonnegative=True)
        if not D("2") <= self.broker_leverage <= D("10"):
            raise ValueError("research broker setting must remain within2–10")


@dataclass(frozen=True)
class ExitFill:
    symbol: str
    quantity: Decimal
    price: Decimal
    fee: Decimal

    def __post_init__(self):
        identifier(self.symbol)
        number(self.quantity, positive=True)
        number(self.price, positive=True)
        number(self.fee, nonnegative=True)


@dataclass(frozen=True)
class LiquidationSettlement(ExitFill):
    """Explicit terminal evidence; never infer insurance credit from a gap."""
    returned_margin: Decimal
    insurance_credit: Decimal
    evidence_digest: str

    def __post_init__(self):
        super().__post_init__()
        number(self.returned_margin, nonnegative=True)
        number(self.insurance_credit, nonnegative=True)
        identifier(self.evidence_digest)


@dataclass(frozen=True)
class FundingSettlement:
    symbol: str
    mark: Decimal
    rate: Decimal

    def __post_init__(self):
        identifier(self.symbol)
        number(self.mark, positive=True)
        number(self.rate)
        if not D("-1") <= self.rate <= D("1"):
            raise ValueError("funding rate outside signed fractional bounds")


@dataclass(frozen=True)
class MarginPosting:
    symbol: str
    amount: Decimal
    cost_restoration: bool = False

    def __post_init__(self):
        identifier(self.symbol)
        number(self.amount, positive=True)
        if type(self.cost_restoration) is not bool:
            raise ValueError("explicit cost restoration flag required")


@dataclass(frozen=True)
class DailyBasis:
    equity: Decimal
    evidence_digest: str

    def __post_init__(self):
        number(self.equity, positive=True)
        identifier(self.evidence_digest)


Payload = MarkBatch | DailyBasis | FundingSettlement | MarginPosting | EntryFill | ExitFill | LiquidationSettlement
PHASES = {MarkBatch: 0, DailyBasis: 1, FundingSettlement: 2, MarginPosting: 3,
          EntryFill: 4, ExitFill: 5, LiquidationSettlement: 5}


@dataclass(frozen=True)
class LedgerCommand:
    tenant_id: str
    account_id: str
    plan_digest: str
    expected_revision: int
    event_id: str
    occurred_at: datetime
    payload: Payload

    def __post_init__(self):
        for value in (self.tenant_id, self.account_id, self.plan_digest, self.event_id):
            identifier(value)
        revision(self.expected_revision)
        timestamp(self.occurred_at)
        if type(self.payload) not in PHASES:
            raise ValueError("supported immutable event required")


@dataclass(frozen=True)
class LedgerBasket:
    symbol: str
    mark: Decimal
    marked_at: datetime
    cycle: int = 0
    quantity: Decimal = ZERO
    average_entry: Decimal = ZERO
    first_fill: Decimal = ZERO
    margin_committed: Decimal = ZERO
    isolated_balance: Decimal = ZERO
    broker_leverage: Decimal = D("2")
    charges_in_budget_epoch: Decimal = ZERO
    entry_fees: Decimal = ZERO
    exit_fees: Decimal = ZERO
    funding_net: Decimal = ZERO
    realized_price_pnl: Decimal = ZERO
    entered_quantity: Decimal = ZERO
    opened_at: datetime | None = None
    last_funding_at: datetime | None = None
    cost_restored: Decimal = ZERO

    def __post_init__(self):
        identifier(self.symbol)
        timestamp(self.marked_at)
        number(self.mark, positive=True)
        revision(self.cycle)
        for name in ("quantity", "average_entry", "first_fill", "margin_committed",
                     "charges_in_budget_epoch", "entry_fees", "exit_fees", "entered_quantity",
                     "cost_restored"):
            number(getattr(self, name), nonnegative=True)
        for value in (self.isolated_balance, self.funding_net, self.realized_price_pnl):
            number(value)
        number(self.broker_leverage, positive=True)
        if self.last_funding_at is not None:
            timestamp(self.last_funding_at)
        if not D("2") <= self.broker_leverage <= D("10"):
            raise ValueError("invalid broker setting")
        if self.quantity:
            if not self.average_entry or not self.first_fill or self.opened_at is None or not self.cycle:
                raise ValueError("position lacks immutable first-fill/cycle identity")
            timestamp(self.opened_at)
            if self.entered_quantity < self.quantity:
                raise ValueError("remaining quantity exceeds fills")
        elif any((self.average_entry, self.first_fill, self.margin_committed,
                  self.isolated_balance, self.entry_fees, self.exit_fees, self.funding_net,
                  self.realized_price_pnl, self.entered_quantity, self.cost_restored)) or self.opened_at is not None:
            raise ValueError("flat basket retains position balances")

    @property
    @precise
    def equity(self):
        return self.isolated_balance + self.quantity * (self.mark - self.average_entry)


@dataclass(frozen=True)
class FuturesLedgerState:
    plan: FuturesPlan
    revision: int
    as_of: datetime
    phase: int
    day_started_at: datetime
    day_start_equity: Decimal
    day_evidence_digest: str
    unposted_cash: Decimal
    baskets: tuple[LedgerBasket, ...]
    halt_reasons: tuple[str, ...]
    closed_baskets: int
    realized_net_pnl: Decimal
    audit_head: str

    def __post_init__(self):
        if not isinstance(self.plan, FuturesPlan):
            raise ValueError("immutable funded plan required")
        for value in (self.revision, self.closed_baskets):
            revision(value)
        if type(self.phase) is not int or not 0 <= self.phase <= 5:
            raise ValueError("invalid equal-time phase")
        timestamp(self.as_of)
        day = timestamp(self.day_started_at)
        if day != day.replace(hour=0, minute=0, second=0, microsecond=0) or day > self.as_of:
            raise ValueError("invalid day basis timestamp")
        number(self.day_start_equity, positive=True)
        number(self.unposted_cash)
        number(self.realized_net_pnl)
        identifier(self.day_evidence_digest)
        identifier(self.audit_head)
        if (type(self.baskets) is not tuple or any(not isinstance(b, LedgerBasket) for b in self.baskets)
                or tuple(b.symbol for b in self.baskets) != self.plan.symbols
                or any(b.marked_at > self.as_of or b.opened_at and b.opened_at > self.as_of
                       or b.last_funding_at and b.last_funding_at > self.as_of
                       for b in self.baskets)):
            raise ValueError("complete immutable own-plan baskets required")
        if type(self.halt_reasons) is not tuple or len(set(self.halt_reasons)) != len(self.halt_reasons):
            raise ValueError("unique immutable halt reasons required")
        for reason in self.halt_reasons:
            identifier(reason)

    @property
    @precise
    def equity(self):
        return self.unposted_cash + sum((b.equity for b in self.baskets), ZERO)

    @property
    def state_digest(self):
        return digest((VERSION, self))

    @property
    def halted(self):
        return bool(self.halt_reasons)

    @property
    @precise
    def reserve_shortfall(self):
        needed = self.plan.remainder
        for b, budget in zip(self.baskets, self.plan.budgets, strict=True):
            needed += max(ZERO, budget.margin_capital - b.margin_committed)
            needed += max(ZERO, budget.cost_reserve - b.charges_in_budget_epoch)
            # Funding paid from isolated principal must not free an equivalent
            # unposted cost reserve before that principal has been restored.
            needed += max(ZERO, b.margin_committed - b.isolated_balance)
        return max(ZERO, needed - self.unposted_cash)


@dataclass(frozen=True)
class ClosedBasket:
    symbol: str
    cycle: int
    opened_at: datetime
    closed_at: datetime
    first_fill: Decimal
    entered_quantity: Decimal
    price_pnl: Decimal
    entry_fees: Decimal
    exit_fees: Decimal
    funding_net: Decimal

    @property
    @precise
    def net_pnl(self):
        return self.price_pnl - self.entry_fees - self.exit_fees + self.funding_net


@dataclass(frozen=True)
class LiquidatedBasket(ClosedBasket):
    insurance_credit: Decimal
    evidence_digest: str

    @property
    @precise
    def net_pnl(self):
        return super().net_pnl + self.insurance_credit


@dataclass(frozen=True)
class LedgerTransition:
    state: FuturesLedgerState
    event_digest: str
    prior_digest: str
    equity_before: Decimal
    equity_after: Decimal
    closed: ClosedBasket | None = None
    execution_enabled: bool = False

    def __post_init__(self):
        if self.execution_enabled is not False:
            raise ValueError("research ledger cannot enable execution")


@precise
def _halt_reasons(state: FuturesLedgerState) -> tuple[str, ...]:
    """Record breaches, including deficits; never rescue margin or clear a halt."""
    reasons = list(state.halt_reasons)
    if state.unposted_cash < 0:
        reasons.append("account_cash_deficit")
    if state.equity <= state.day_start_equity * D(".94"):
        reasons.append("daily_loss_limit")
    if state.equity <= state.plan.initial_equity * D(".92"):
        reasons.append("initial_loss_limit")
    for b, c, budget in zip(state.baskets, state.plan.contracts, state.plan.budgets, strict=True):
        if b.margin_committed > budget.margin_capital or b.charges_in_budget_epoch > budget.cost_reserve:
            reasons.append("basket_budget_breach")
        if not b.quantity:
            continue
        try:
            nominal = b.quantity * max(b.mark, b.average_entry, b.first_fill)
            tier = c.schedule.tier_for(nominal)
            protected = tier.maintenance_rate + c.protective_exit_fee_rate
            if protected >= 1:
                raise ValueError("invalid protected rate")
            if b.equity <= b.quantity * b.mark * protected:
                reasons.append("isolated_position_unsafe")
            if b.broker_leverage > tier.maximum_leverage:
                reasons.append("contract_leverage_breach")
        except ValueError:
            reasons.append("missing_margin_coverage")
    return state.plan.ledger_halt_reasons(reasons)


@precise
def start_futures_ledger(plan: FuturesPlan, marks: tuple[LedgerMark, ...],
                         at: datetime, evidence_digest: str) -> FuturesLedgerState:
    at = timestamp(at)
    if at != at.replace(hour=0, minute=0, second=0, microsecond=0):
        raise ValueError("initial research ledger starts at exact UTC midnight")
    batch = MarkBatch(marks)
    if tuple(m.symbol for m in batch.marks) != plan.symbols:
        raise ValueError("foreign or incomplete initial marks")
    state = FuturesLedgerState(
        plan, 0, at, 0, at, plan.initial_equity, evidence_digest, plan.initial_equity,
        tuple(LedgerBasket(m.symbol, m.price, at) for m in marks), (), 0, ZERO,
        digest((VERSION, plan, batch, at, evidence_digest)),
    )
    return replace(state, halt_reasons=_halt_reasons(state))


@precise
def apply_futures_event(state: FuturesLedgerState, command: LedgerCommand) -> LedgerTransition:
    """Book caller-reconciled evidence, including unsafe actual outcomes.

    Intent/risk authorization and durable broker-event deduplication are outside
    this reducer. Identical commands require their original revision and fail
    replay. Deficits and fills after a halt remain truthful and terminally flagged.
    """
    context = (state.plan.tenant_id, state.plan.account_id, state.plan.plan_digest)
    if (command.tenant_id, command.account_id, command.plan_digest) != context:
        raise ValueError("foreign ledger context")
    if command.expected_revision != state.revision:
        raise ValueError("stale ledger revision")
    payload = command.payload
    if (isinstance(payload, LiquidationSettlement)
            and not getattr(state.plan, "supports_capital_liquidations", False)):
        raise ValueError("liquidation settlement requires its separate capital research plan")
    phase = PHASES[type(payload)]
    if command.occurred_at < state.as_of or command.occurred_at == state.as_of and phase < state.phase:
        raise ValueError("backdated or ambiguous equal-time event ordering")
    baskets = list(state.baskets)
    cash, closed = state.unposted_cash, None
    extra_reasons = []
    changes = {}
    if isinstance(payload, MarkBatch):
        if tuple(m.symbol for m in payload.marks) != state.plan.symbols:
            raise ValueError("foreign or incomplete marks")
        baskets = [replace(b, mark=m.price, marked_at=command.occurred_at)
                   for b, m in zip(baskets, payload.marks, strict=True)]
    elif isinstance(payload, DailyBasis):
        midnight = command.occurred_at.replace(hour=0, minute=0, second=0, microsecond=0)
        if (command.occurred_at != midnight or midnight <= state.day_started_at
                or any(b.marked_at != midnight for b in baskets) or payload.equity != state.equity):
            raise ValueError("day basis needs exact fresh pre-mutation midnight evidence")
        changes = {"day_started_at": midnight, "day_start_equity": state.equity,
                   "day_evidence_digest": payload.evidence_digest}
    else:
        if payload.symbol not in state.plan.symbols:
            raise ValueError("foreign event symbol")
        index = state.plan.symbols.index(payload.symbol)
        b, contract = baskets[index], state.plan.contracts[index]
        if isinstance(payload, (EntryFill, ExitFill)):
            if payload.quantity != floor_step(payload.quantity, contract.quantity_step):
                raise ValueError("fill quantity outside contract step")
            if isinstance(payload, EntryFill):
                if state.halted:
                    extra_reasons.append("entry_fill_after_halt")
                if state.day_started_at != command.occurred_at.replace(
                        hour=0, minute=0, second=0, microsecond=0):
                    extra_reasons.append("entry_fill_without_current_day_basis")
                if any(not timedelta(0) <= command.occurred_at - row.marked_at <= timedelta(seconds=30)
                       for row in baskets):
                    extra_reasons.append("entry_fill_without_fresh_mark")
                quantity = b.quantity + payload.quantity
                average = (b.quantity * b.average_entry + payload.quantity * payload.price) / quantity
                cash -= payload.posted_margin + payload.fee
                b = replace(
                    b, cycle=b.cycle if b.quantity else b.cycle + 1, quantity=quantity,
                    average_entry=average, first_fill=b.first_fill if b.quantity else payload.price,
                    margin_committed=b.margin_committed + payload.posted_margin,
                    isolated_balance=b.isolated_balance + payload.posted_margin,
                    broker_leverage=payload.broker_leverage, entry_fees=b.entry_fees + payload.fee,
                    charges_in_budget_epoch=b.charges_in_budget_epoch + payload.fee,
                    entered_quantity=b.entered_quantity + payload.quantity,
                    opened_at=b.opened_at if b.quantity else command.occurred_at,
                )
                if b.isolated_balance < b.quantity * b.average_entry / b.broker_leverage:
                    extra_reasons.append("entry_fill_initial_margin_breach")
            else:
                if payload.quantity > b.quantity:
                    raise ValueError("exit exceeds actual remaining long quantity")
                fraction = payload.quantity / b.quantity
                released = b.isolated_balance if fraction == 1 else b.isolated_balance * fraction
                committed = b.margin_committed if fraction == 1 else b.margin_committed * fraction
                pnl = payload.quantity * (payload.price - b.average_entry)
                cash += released + pnl - payload.fee
                costs = b.charges_in_budget_epoch + payload.fee
                if payload.quantity == b.quantity:
                    closed = ClosedBasket(
                        b.symbol, b.cycle, b.opened_at, command.occurred_at, b.first_fill,
                        b.entered_quantity, b.realized_price_pnl + pnl, b.entry_fees,
                        b.exit_fees + payload.fee, b.funding_net,
                    )
                    if isinstance(payload, LiquidationSettlement):
                        if released + pnl - payload.fee + payload.insurance_credit != payload.returned_margin:
                            raise ValueError("liquidation terminal balance does not reconcile")
                        cash += payload.insurance_credit
                        closed = LiquidatedBasket(
                            b.symbol, b.cycle, b.opened_at, command.occurred_at, b.first_fill,
                            b.entered_quantity, b.realized_price_pnl + pnl, b.entry_fees,
                            b.exit_fees + payload.fee, b.funding_net,
                            payload.insurance_credit, payload.evidence_digest,
                        )
                    if (getattr(state.plan, "per_cycle_cost_budgets", False)
                            and not isinstance(payload, LiquidationSettlement)):
                        if costs > state.plan.budgets[index].cost_reserve:
                            extra_reasons.append("basket_budget_breach")
                        next_costs = ZERO
                    else:
                        next_costs = costs
                    b = LedgerBasket(b.symbol, b.mark, b.marked_at, cycle=b.cycle,
                                     charges_in_budget_epoch=next_costs, last_funding_at=b.last_funding_at)
                else:
                    if isinstance(payload, LiquidationSettlement):
                        raise ValueError("liquidation settlement must close the entire basket")
                    b = replace(b, quantity=b.quantity - payload.quantity,
                                margin_committed=b.margin_committed - committed,
                                isolated_balance=b.isolated_balance - released,
                                realized_price_pnl=b.realized_price_pnl + pnl,
                                exit_fees=b.exit_fees + payload.fee, charges_in_budget_epoch=costs)
        elif isinstance(payload, MarginPosting):
            if not b.quantity:
                raise ValueError("margin posting needs an existing position")
            if payload.cost_restoration and payload.amount > b.margin_committed - b.isolated_balance:
                raise ValueError("cost restoration exceeds outstanding isolated principal debit")
            cash -= payload.amount
            b = replace(
                b, margin_committed=b.margin_committed + (ZERO if payload.cost_restoration else payload.amount),
                isolated_balance=b.isolated_balance + payload.amount,
                cost_restored=b.cost_restored + (payload.amount if payload.cost_restoration else ZERO),
            )
        else:
            if b.mark != payload.mark or b.marked_at != command.occurred_at:
                raise ValueError("funding requires same-time mark evidence")
            if b.last_funding_at is not None and command.occurred_at <= b.last_funding_at:
                raise ValueError("duplicate funding settlement timestamp")
            payment = -b.quantity * payload.mark * payload.rate
            b = replace(b, isolated_balance=b.isolated_balance + payment,
                        funding_net=b.funding_net + payment,
                        charges_in_budget_epoch=b.charges_in_budget_epoch + max(ZERO, -payment),
                        last_funding_at=command.occurred_at)
        baskets[index] = b
    provisional = replace(
        state, revision=state.revision + 1, as_of=command.occurred_at, phase=phase,
        unposted_cash=cash, baskets=tuple(baskets),
        closed_baskets=state.closed_baskets + bool(closed),
        realized_net_pnl=state.realized_net_pnl + (closed.net_pnl if closed else ZERO),
        halt_reasons=tuple(dict.fromkeys((*state.halt_reasons, *extra_reasons))), **changes,
    )
    provisional = replace(provisional, halt_reasons=_halt_reasons(provisional))
    event_digest = digest((VERSION, command))
    result = replace(provisional, audit_head=digest((
        VERSION, state.audit_head, event_digest, provisional.state_digest,
    )))
    return LedgerTransition(result, event_digest, state.state_digest, state.equity, result.equity, closed)
