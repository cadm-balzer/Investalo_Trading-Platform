"""Own Paper recovery: complete new range, retained loss, no broker authority."""
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from .allocation import revision
from .capital_digest import digest
from .futures_capital_research import _finish as finish_economic
from .futures_capital_signals import _finish as finish_signal
from .futures_ledger import timestamp
from .futures_paper import _check, _finish
from .futures_paper_profit import refresh_profit_budgets
from .futures_replay_journal import _sha
from .models import precise

ZERO = Decimal(0)
VERSION = "own-futures-paper-recovery/1"


@dataclass(frozen=True)
class PaperRecoveryRequest:
    tenant_id: str
    account_id: str
    actor_id: str
    symbol: str
    cycle: int
    expected_revision: int
    state_digest: str
    event_id: str
    consent: bool

    def __post_init__(self):
        for value in (self.tenant_id, self.account_id, self.actor_id, self.event_id):
            if type(value) is not str or str(UUID(value)) != value:
                raise ValueError("canonical own recovery UUID required")
        revision(self.cycle)
        revision(self.expected_revision)
        _sha(self.state_digest)
        if not self.cycle or type(self.symbol) is not str or self.consent is not True:
            raise ValueError("explicit own stopped cycle and manual consent required")


@dataclass(frozen=True)
class PaperLiquidation:
    symbol: str
    cycle: int
    liquidated_at: datetime
    net_loss: Decimal
    leverage: Decimal
    evidence_digest: str

    def __post_init__(self):
        revision(self.cycle)
        timestamp(self.liquidated_at)
        _sha(self.evidence_digest)
        if not self.cycle or self.net_loss < 0 or self.leverage != 2:
            raise ValueError("actual own fixed2x liquidation record required")


@precise
def liquidation_record(basket, settlement, at):
    net = (basket.realized_price_pnl + basket.quantity * (settlement.price - basket.average_entry)
           - basket.entry_fees - basket.exit_fees - settlement.fee + basket.funding_net
           + settlement.insurance_credit)
    return PaperLiquidation(basket.symbol, basket.cycle, timestamp(at), max(ZERO, -net),
                            basket.broker_leverage, settlement.evidence_digest)


@dataclass(frozen=True)
class PaperRecoveryAssessment:
    reasons: tuple[str, ...]
    available: Decimal
    required: Decimal


@dataclass(frozen=True)
class PaperRecoveryRow:
    liquidation: PaperLiquidation
    reasons: tuple[str, ...]
    available: Decimal
    required: Decimal


@dataclass(frozen=True)
class PaperRecoveryState:
    tenant_id: str
    account_id: str
    revision: int
    state_digest: str
    known_at: datetime
    trade_at: datetime
    settings_revision: int
    configured_limit: int
    rows: tuple[PaperRecoveryRow, ...]

    def __post_init__(self):
        for value in (self.tenant_id, self.account_id):
            if str(UUID(value)) != value:
                raise ValueError("canonical own recovery account required")
        revision(self.revision)
        revision(self.settings_revision)
        _sha(self.state_digest)
        timestamp(self.known_at)
        timestamp(self.trade_at)
        if (type(self.configured_limit) is not int or not 3 <= self.configured_limit <= 7
                or type(self.rows) is not tuple or len(self.rows) > 7
                or any(type(r) is not PaperRecoveryRow or r.required <= 0 or r.available < 0
                       for r in self.rows)
                or len({r.liquidation.symbol for r in self.rows}) != len(self.rows)):
            raise ValueError("bounded own stopped recovery projection required")


def recovery_state(state, liquidations):
    plan = state.config.profile.plan
    rows = []
    for stopped in state.signal.economic.stopped:
        matches = tuple(r for r in liquidations if
            (r.symbol, r.cycle, r.evidence_digest) == (
                stopped.symbol, stopped.cycle, stopped.evidence_digest))
        if len(matches) != 1:
            raise ValueError("complete own journal liquidation history required")
        assessment = assess_paper_recovery(state, stopped.symbol, stopped.cycle, state.observed_at)
        rows.append(PaperRecoveryRow(matches[0], assessment.reasons, assessment.available, assessment.required))
    return PaperRecoveryState(plan.tenant_id, plan.account_id, state.revision, state.state_digest,
                              state.observed_at, state.signal.trade_at, state.settings_revision,
                              plan.configured_limit, tuple(rows))


def recovery_snapshot(state, now, *, account_ready=True, can_edit=True, executable=True):
    now = timestamp(now)
    fresh = (timedelta(0) <= now - state.known_at <= timedelta(seconds=30)
             and timedelta(0) <= now - state.trade_at <= timedelta(seconds=30)
             and state.trade_at.replace(minute=0, second=0, microsecond=0)
                 == now.replace(minute=0, second=0, microsecond=0))
    assets = []
    for row in state.rows:
        reasons = list(row.reasons)
        for reason, blocked in (
            ("reconciliation_stale", not fresh),
            ("account_blocked", not account_ready or not can_edit),
            ("runtime_unavailable", not executable),
        ):
            if blocked and reason not in reasons:
                reasons.append(reason)
        r = row.liquidation
        assets.append(dict(account_id=state.account_id, symbol=r.symbol.removeprefix("BITGET:"),
            cycle=r.cycle, revision=state.revision, state_digest=state.state_digest,
            liquidated_at=r.liquidated_at.isoformat(), net_loss=format(r.net_loss, "f"), leverage=str(r.leverage),
            available_capital=format(row.available, "f"), required_capital=format(row.required, "f"),
            reasons=reasons, allowed=not reasons))
    return assets


@precise
def assess_paper_recovery(state, symbol, cycle, now):
    """Only acknowledged full-fill Paper state; never infer real broker reconciliation."""
    now = timestamp(now)
    signal = state.signal
    economic, plan = signal.economic, state.config.profile.plan
    index = plan.symbols.index(symbol)
    row, budget = economic.ledger.baskets[index], plan.budgets[index]
    stopped = {s.symbol: s for s in economic.stopped}
    if symbol not in stopped or stopped[symbol].cycle != cycle or row.cycle != cycle:
        raise ValueError("own currently stopped Paper cycle required")
    reasons = []
    if (not state.warmed or now < state.observed_at
            or not timedelta(0) <= now - signal.trade_at <= timedelta(seconds=30)
            or signal.last_hour is None
            or signal.last_hour.close_time != now.replace(minute=0, second=0, microsecond=0)
            or any(b.marked_at != signal.trade_at for b in economic.ledger.baskets)):
        reasons.append("reconciliation_stale")
    if row.quantity:
        reasons.append("position_not_flat")
    if economic.ledger.halted or economic.liquidation_required:
        reasons.append("account_blocked")
    # Candidate count is not funded capacity. Target takes the latest future budget.
    required = plan.target_range
    reserved = plan.remainder - max(ZERO, required - budget.capital)
    occupied = 0
    for peer, own in zip(economic.ledger.baskets, plan.budgets, strict=True):
        if peer.quantity or peer.symbol in stopped:
            occupied += 1
        if peer.symbol == symbol or not (peer.quantity or peer.symbol in stopped):
            continue
        reserved += (stopped[peer.symbol].unposted_stage_capital if peer.symbol in stopped else
                     max(ZERO, own.margin_capital - peer.margin_committed))
        reserved += max(ZERO, own.cost_reserve - plan.basket_cost_usage(peer))
        reserved += max(ZERO, peer.margin_committed - peer.isolated_balance)
    if occupied > plan.funded_slots:
        raise ValueError("own funded recovery capacity exceeded")
    reserved += (plan.funded_slots - occupied) * plan.target_range
    available = max(ZERO, economic.ledger.unposted_cash - reserved)
    if available < required:
        reasons.append("new_basket_budget_missing")
    return PaperRecoveryAssessment(tuple(reasons), available, required)


def apply_paper_recovery(state, request, expected_revision, at):
    _check(state, expected_revision, at)
    plan = state.config.profile.plan
    if (type(request) is not PaperRecoveryRequest
            or (request.tenant_id, request.account_id) != (plan.tenant_id, plan.account_id)
            or request.expected_revision != expected_revision or request.state_digest != state.state_digest
            or request.event_id in state.signal.economic.event_ids):
        raise ValueError("foreign, stale or repeated own manual Paper recovery")
    assessment = assess_paper_recovery(state, request.symbol, request.cycle, at)
    if assessment.reasons:
        raise ValueError("own Paper recovery blocked: " + ",".join(assessment.reasons))
    economic = state.signal.economic
    ledger = economic.ledger
    # Begin a new cost budget; booked losses/cash/risk bases and historical journal stay intact.
    baskets = tuple(replace(b, charges_in_budget_epoch=ZERO) if b.symbol == request.symbol else b
                    for b in ledger.baskets)
    body = (VERSION, request, assessment, timestamp(at))
    ledger = replace(ledger, revision=ledger.revision + 1, baskets=baskets,
                     audit_head=digest((ledger.audit_head, body)))
    economic = finish_economic(economic, economic.as_of, request.event_id, body, ledger=ledger,
        stopped=tuple(s for s in economic.stopped if s.symbol != request.symbol))
    signals = tuple(replace(s, cycle=request.cycle + 1, below_count=0, rearmed=False,
        protected=False, stop=None, exit_reasons=(), manual_notice=False)
        if s.symbol == request.symbol else s for s in state.signal.signals)
    signal = finish_signal(state.signal, state.signal.as_of, body, economic=economic, signals=signals)
    config, signal = refresh_profit_budgets(state.config, signal)
    return _finish(state, body, config=config, signal=signal, observed_at=timestamp(at))
