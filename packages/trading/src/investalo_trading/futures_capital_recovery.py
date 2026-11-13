"""Explicit manual recovery candidate. Trusted reconciliation, no broker/HTTP authority.

Caller must durably acknowledge the returned receipt and candidate together
before publishing either. Historical research journals do not accept this action.
"""
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from decimal import Decimal

from .allocation import identifier, revision
from .capital_digest import CapitalCanonical, digest
from .futures_capital_research import CapitalResearchState, _finish
from .futures_capital_signals import CapitalSignalState, _finish as finish_signal
from .futures_ledger import timestamp
from .models import precise

VERSION = "futures-manual-liquidation-recovery/1"
ZERO = Decimal(0)


@dataclass(frozen=True)
class RecoveryRequest(CapitalCanonical):
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
        for v in (self.tenant_id, self.account_id, self.actor_id, self.symbol,
                  self.state_digest, self.event_id):
            identifier(v)
        revision(self.cycle)
        revision(self.expected_revision)
        if not self.cycle or type(self.consent) is not bool:
            raise ValueError("actual liquidated cycle and explicit manual consent required")


@dataclass(frozen=True)
class RecoveryReconciliation(CapitalCanonical):
    """Server-owned latest evidence; browser booleans are never authoritative."""
    state_digest: str
    checked_at: datetime
    position_flat: bool
    orders_complete: bool
    open_orders: int
    unknown_orders: int
    liquidation_booked: bool
    evidence_digest: str

    def __post_init__(self):
        identifier(self.state_digest)
        identifier(self.evidence_digest)
        timestamp(self.checked_at)
        for v in (self.position_flat, self.orders_complete, self.liquidation_booked):
            if type(v) is not bool:
                raise ValueError("explicit trusted reconciliation required")
        for v in (self.open_orders, self.unknown_orders):
            revision(v)


@dataclass(frozen=True)
class RecoveryAssessment(CapitalCanonical):
    request: RecoveryRequest
    reconciliation: RecoveryReconciliation
    checked_at: datetime
    reasons: tuple[str, ...]
    available_capital: Decimal
    required_capital: Decimal

    @property
    def allowed(self):
        return not self.reasons


@precise
def assess_recovery(state, request, reconciliation, at):
    if (type(state) is not CapitalResearchState or type(request) is not RecoveryRequest
            or type(reconciliation) is not RecoveryReconciliation):
        raise ValueError("typed own state, manual request and server evidence required")
    at = timestamp(at)
    plan = state.ledger.plan
    if (request.tenant_id != plan.tenant_id or request.account_id != plan.account_id
            or request.symbol not in plan.symbols or request.state_digest != state.state_digest
            or request.expected_revision != state.revision
            or reconciliation.state_digest != state.state_digest or at < state.as_of
            or request.event_id in state.event_ids):
        raise ValueError("foreign, stale, replayed or backdated recovery request")
    index = plan.symbols.index(request.symbol)
    basket, budget = state.ledger.baskets[index], plan.budgets[index]
    stopped = {s.symbol: s for s in state.stopped}
    if (request.symbol not in stopped or stopped[request.symbol].cycle != request.cycle
            or basket.cycle != request.cycle):
        raise ValueError("own currently stopped liquidation cycle required")
    reasons = []
    if not request.consent:
        reasons.append("manual_consent_required")
    if not timedelta(0) <= at - reconciliation.checked_at <= timedelta(seconds=30):
        reasons.append("reconciliation_stale")
    if basket.quantity or not reconciliation.position_flat:
        reasons.append("position_not_flat")
    if not reconciliation.orders_complete or reconciliation.unknown_orders:
        reasons.append("orders_unresolved")
    if reconciliation.open_orders:
        reasons.append("open_orders")
    if not reconciliation.liquidation_booked:
        reasons.append("liquidation_unbooked")
    if state.ledger.halted or state.liquidation_required:
        reasons.append("account_blocked")
    # Preserve every other slot's existing own range and restoration backing.
    # Empty eligible slots retain their full range, so repeated recoveries cannot
    # claim the same capital. Stopped peers retain their untouched stage capital.
    reserved = plan.remainder
    for row, own in zip(state.ledger.baskets, plan.budgets, strict=True):
        if row.symbol == request.symbol:
            continue
        reserved += (stopped[row.symbol].unposted_stage_capital if row.symbol in stopped else
                     max(ZERO, own.margin_capital - row.margin_committed))
        reserved += max(ZERO, own.cost_reserve - plan.basket_cost_usage(row))
        reserved += max(ZERO, row.margin_committed - row.isolated_balance)
    available = max(ZERO, state.ledger.unposted_cash - reserved)
    if available < budget.capital:
        reasons.append("new_basket_budget_missing")
    return RecoveryAssessment(request, reconciliation, at, tuple(reasons), available, budget.capital)


def recover_candidate(state, assessment, *, at):
    """Pure candidate + audit receipt; never commit, send orders or erase losses."""
    if type(assessment) is not RecoveryAssessment:
        raise ValueError("typed recovery assessment required")
    prepared = assess_recovery(state, assessment.request, assessment.reconciliation, assessment.checked_at)
    current = assess_recovery(state, assessment.request, assessment.reconciliation, at)
    if prepared != assessment or not prepared.allowed or not current.allowed:
        raise ValueError("manual recovery remains blocked")
    request = current.request
    candidate = _finish(
        state, current.checked_at, request.event_id, (VERSION, current),
        stopped=tuple(s for s in state.stopped if s.symbol != request.symbol))
    receipt = dict(schema_version=VERSION, actor_id=request.actor_id, event_id=request.event_id,
                   symbol=request.symbol, liquidated_cycle=request.cycle,
                   next_cycle=request.cycle + 1, prior_state_digest=state.state_digest,
                   candidate_state_digest=candidate.state_digest, assessment_digest=digest(current),
                   loss_retained=True, order_submitted=False)
    return candidate, receipt


def recover_signal_candidate(state, assessment, *, at):
    """Rearm only the recovered symbol; two newly closed RSI bars required."""
    if type(state) is not CapitalSignalState:
        raise ValueError("typed own signal state required")
    economic, receipt = recover_candidate(state.economic, assessment, at=at)
    symbol = assessment.request.symbol
    signals = tuple(replace(
        s, cycle=assessment.request.cycle + 1, below_count=0, rearmed=False,
        protected=False, stop=None, exit_reasons=(), manual_notice=False,
    ) if s.symbol == symbol else s for s in state.signals)
    candidate = finish_signal(state, assessment.checked_at, (VERSION, receipt),
                              economic=economic, signals=signals)
    return candidate, receipt | dict(prior_signal_digest=state.state_digest,
                                    candidate_signal_digest=candidate.state_digest)
