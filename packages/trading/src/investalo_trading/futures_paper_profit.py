"""One actual journal-backed Q36 grant; no cash credit, risk reset or recovery."""
from dataclasses import dataclass, replace
from datetime import timedelta
from decimal import Decimal

from .capital_digest import digest
from .futures_ledger import timestamp
from .futures_paper import _check, _finish
from .futures_paper_profit_plan import CapitalPaperProfitPlan, PaperProfitEpoch, MAX_EPOCHS
from .models import floor_step, precise

D = Decimal
ZERO = D(0)


def _bind(config, signal, plan):
    profile = replace(config.profile, plan=plan)
    economic = replace(signal.economic, ledger=replace(signal.economic.ledger, plan=plan))
    return replace(config, profile=profile), replace(signal, profile=profile, economic=economic)


@precise
def refresh_profit_budgets(config, signal):
    """Only flat reusable candidates adopt the latest budget; old ladders stay frozen."""
    plan = config.profile.plan
    if type(plan) is not CapitalPaperProfitPlan:
        return config, signal
    stopped = {s.symbol for s in signal.economic.stopped}
    occupied = tuple(bool(b.quantity) or b.symbol in stopped for b in signal.economic.ledger.baskets)
    if sum(occupied) > plan.funded_slots:
        raise ValueError("own allocated ranges exceeded")
    indices = tuple(index if used else len(plan.epochs)
                    for index, used in zip(plan.budget_indices, occupied, strict=True))
    budgets = tuple(plan.budget_at(symbol, index)
                    for symbol, index in zip(plan.symbols, indices, strict=True))
    committed_ranges = sum((budget.capital for budget, used in zip(budgets, occupied, strict=True)
                            if used), ZERO)
    remainder = (plan.initial_equity + plan.allocated_profit - committed_ranges
                 - (plan.funded_slots - sum(occupied)) * plan.target_range)
    return _bind(config, signal, replace(plan, budgets=budgets, budget_indices=indices,
                                        remainder=remainder))


@dataclass(frozen=True)
class PaperProfitAssessment:
    reasons: tuple[str, ...]
    epoch: PaperProfitEpoch | None = None


@precise
def assess_profit_epoch(state, *, now):
    now = timestamp(now)
    plan, signal = state.config.profile.plan, state.signal
    if type(plan) is not CapitalPaperProfitPlan:
        return PaperProfitAssessment(("profit_profile_required",))
    ledger = signal.economic.ledger
    previous = plan.epochs[-1] if plan.epochs else None
    reasons = []
    if len(plan.epochs) >= MAX_EPOCHS:
        reasons.append("profit_history_capacity")
    if ledger.closed_baskets < (previous.closed_count if previous else 0) + 3:
        reasons.append("three_new_closures_required")
    allocated = plan.allocated_profit + plan.original_range
    if ledger.realized_net_pnl < allocated:
        reasons.append("full_realized_range_required")
    capacity = min(plan.funded_slots + 1, 7)
    if capacity > len(plan.symbols):
        reasons.append("candidate_pool_expansion_required")
    if plan.funded_slots < 7 and capacity > plan.configured_limit:
        reasons.append("configured_ceiling_reached")
    if (not state.warmed or signal.trade_at is None or now < state.observed_at
            or not timedelta(0) <= now - signal.trade_at <= timedelta(seconds=30)
            or signal.last_hour is None
            or signal.last_hour.close_time != now.replace(minute=0, second=0, microsecond=0)
            or any(b.marked_at != signal.trade_at for b in ledger.baskets)):
        reasons.append("fresh_complete_valuation_required")
    if ledger.halted or signal.economic.liquidation_required or signal.economic.stopped:
        reasons.append("paper_reconciliation_required")
    if ledger.equity < plan.initial_equity + allocated:
        reasons.append("profit_no_longer_equity_backed")
    if reasons:
        return PaperProfitAssessment(tuple(reasons))
    total = floor_step((plan.initial_equity - plan.original_remainder + allocated)
                       / capacity, plan.quantum)
    epoch = PaperProfitEpoch(
        len(plan.epochs) + 1, now, capacity, total, allocated, ledger.closed_baskets,
        ledger.realized_net_pnl, digest((ledger.state_digest, signal.economic.state_digest)),
        ledger.unposted_cash, ledger.equity,
    )
    # Extend the allocation, never the actual ledger cash or original risk basis.
    config, candidate = _bind(state.config, signal, replace(plan, epochs=(*plan.epochs, epoch)))
    config, candidate = refresh_profit_budgets(config, candidate)
    proposed = config.profile.plan
    # All vacant funded ranges must fit alongside every existing remaining ladder.
    reserved = proposed.remainder
    active = 0
    for row, budget in zip(ledger.baskets, proposed.budgets, strict=True):
        if row.quantity:
            active += 1
            reserved += max(ZERO, budget.margin_capital - row.margin_committed)
            reserved += max(ZERO, budget.cost_reserve - proposed.basket_cost_usage(row))
            reserved += max(ZERO, row.margin_committed - row.isolated_balance)
    reserved += (capacity - active) * total
    if ledger.unposted_cash < reserved:
        return PaperProfitAssessment(("insufficient_liquid_profit",))
    return PaperProfitAssessment((), epoch)


def apply_profit_epoch(state, expected_revision, at):
    _check(state, expected_revision, at)
    assessment = assess_profit_epoch(state, now=at)
    if assessment.reasons:
        raise ValueError("profit epoch not eligible: " + ",".join(assessment.reasons))
    plan = state.config.profile.plan
    new = replace(plan, epochs=(*plan.epochs, assessment.epoch))
    config, signal = _bind(state.config, state.signal, new)
    config, signal = refresh_profit_budgets(config, signal)
    return _finish(state, ("profit_epoch", assessment.epoch), config=config, signal=signal,
                   observed_at=timestamp(at))
