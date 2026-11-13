"""Read-only economic metrics from a complete capital journal after interrupted export.

Admission attempts without commands cannot be reconstructed here. They are omitted,
never reported as zero. No state mutation, source import or simulated recovery.
"""
from decimal import Decimal
import json
from types import SimpleNamespace

from investalo_trading import futures_capital_journal as codec
from investalo_trading.futures_ledger import ExitFill, LiquidationSettlement, MarginPosting
from investalo_trading.models import precise
from .futures_capital_backtest import MarketReplay
from .snapshot import iso

D = Decimal
ZERO = D(0)


def restore_metrics(path, scenario, protocol_digest, dataset_digests, start, end):
    with path.open() as handle:
        header = json.loads(next(handle))
    proxy = SimpleNamespace(state=codec._genesis(header))
    expected = scenario.profile(cash_budgets=True, entry_hours=1, realized_exit_costs=True,
                                reserved_cash=True, current_grids=True,
                                grid_leverage_comparison=True, moderate_grid_leverage=True)
    if proxy.state.profile != expected:
        raise ValueError("foreign scenario/profile metric journal")
    sampler = MarketReplay(proxy, scenario, None)
    original = codec._apply

    @precise
    def observed(state, command):
        candidate = original(state, command)  # Retain every causal admission/hash check.
        kind = command["kind"]
        if kind in ("entry", "economic", "funding_batch"):
            args = codec._arguments(kind, command["arguments"])
            if kind == "entry":
                a = args["assessment"].capital
                sampler.stage_counts[str(a.stage)] += 1
                c = state.profile.plan.contracts[state.profile.plan.symbols.index(a.request.symbol)]
                sampler.fees += a.request.quantity * args["price"] * c.entry_fee_rate
            elif kind == "funding_batch":
                quantities = {b.symbol: b.quantity for b in state.economic.ledger.baskets}
                sampler.funding -= sum((quantities[p.symbol] * p.mark * p.rate
                                        for p in args["batch"].settlements), ZERO)
            else:
                payload = args["payload"]
                if isinstance(payload, ExitFill):
                    i = state.profile.plan.symbols.index(payload.symbol)
                    b = state.economic.ledger.baskets[i]
                    if payload.quantity != b.quantity:
                        raise ValueError("native metric recovery requires full basket closes")
                    from dataclasses import replace
                    credit = payload.insurance_credit if type(payload) is LiquidationSettlement else ZERO
                    pnl = b.realized_price_pnl + b.quantity * (payload.price - b.average_entry)
                    sampler.closed.append(dict(
                        symbol=b.symbol, cycle=b.cycle, opened_at=iso(b.opened_at),
                        closed_at=iso(candidate.as_of),
                        stages=sum(r.symbol == b.symbol and r.cycle == b.cycle for r in state.economic.stages),
                        leverage=str(b.broker_leverage), reasons=list(state.signals[i].exit_reasons),
                        liquidated=type(payload) is LiquidationSettlement, price_pnl=str(pnl),
                        fees=str(b.entry_fees + b.exit_fees + payload.fee),
                        funding_net=str(b.funding_net), insurance_credit=str(credit),
                        net_pnl=str(pnl - b.entry_fees - b.exit_fees - payload.fee + b.funding_net + credit),
                        closing_cost_usage=str(state.profile.plan.basket_cost_usage(replace(
                            b, exit_fees=b.exit_fees + payload.fee,
                            charges_in_budget_epoch=b.charges_in_budget_epoch + payload.fee))),
                        cost_reserve=str(state.profile.plan.budgets[i].cost_reserve)))
                    sampler.fees += payload.fee
                    sampler.insurance += credit
                elif isinstance(payload, MarginPosting):
                    if not payload.cost_restoration:
                        raise ValueError("unknown extra capital posting")
                    sampler.restored += payload.amount
        proxy.state = candidate
        sampler.sample()
        return candidate

    # Dedicated offline process only; never an application/worker concurrency hook.
    codec._apply = observed
    try:
        with codec.CapitalReplayJournal.restore(
                path, profile_digest=proxy.state.profile.profile_digest,
                protocol_digest=protocol_digest, dataset_digests=dataset_digests) as restored:
            if restored.state.as_of != end or restored.state.last_hour.close_time != end:
                raise ValueError("incomplete native window; no recovered result")
            proxy.state, proxy.receipt = restored.state, restored.receipt
            report = sampler.report(start, end)
    finally:
        codec._apply = original
    for key in ("capital_rejections", "eligible_closed_h4_candidates",
                "closed_h4_signal_filters", "account_warning_hours"):
        report.pop(key)
    report.update(full_journal_restore_verified=True, recovered_from_complete_journal=True,
                  admission_metrics_reconstructed=False, entry_timeframe="H1",
                  capital_policy=proxy.state.profile.plan.capital_policy,
                  grid_source_digest=proxy.state.profile.plan.grid_source_digest,
                  grid_price_rounding="adverse entry ceiling / exit floor",
                  broker_admission_verified=False, grid_leverage_comparison=True,
                  moderate_grid_leverage=True, fixed_cycle_leverage=str(scenario.leverage))
    return report, sampler.closed
