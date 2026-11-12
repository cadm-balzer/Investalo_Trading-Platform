#!/usr/bin/env python3
"""Freeze, import and compare research only; no DB, holdout or broker execution."""
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
from decimal import Decimal, localcontext
import gc
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / name) for name in ("packages/trading/src", "packages/marketdata/src")]

from investalo_marketdata.timeframe_spot import (
    MAX_BYTES, SYMBOLS, URL, fetch_history, load_history,
)
from investalo_marketdata.snapshot import canonical, iso, parse_time
from investalo_trading.models import Side
from investalo_trading.pool_research import PoolPlan
from investalo_trading.simulator import SimulationCosts
from investalo_trading.snapshot import digest, primitive
from investalo_trading.timeframe_research import (
    GAP_END, GAP_START, TimeframeReplay, aggregate_h4,
)

D = Decimal
PROTOCOL = ROOT / "docs/research-protocols/h1-h4-baskets-20261111.json"


def json_value(value):
    if isinstance(value, dict):
        return {str(k): json_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_value(v) for v in value]
    converted = primitive(value)
    return json_value(converted) if converted is not value else value


def runners():
    for multiplier, capacities in ((1, (3, 5)), (2, (5,))):
        for capacity in capacities:
            for hours in (1, 4):
                name = f"h{hours}-slots{capacity}-costs{multiplier}x"
                costs = SimulationCosts(*(D("0.001") * multiplier for _ in range(3)))
                plan = PoolPlan("timeframe-research", "shared-10000-usdt", SYMBOLS,
                                D("10000"), D("0.01"), capacity)
                yield name, TimeframeReplay(plan, hours, costs)


def expected_protocol():
    return {
        "schema_version": "h1-h4-basket-study/1", "purpose": "research",
        "start": "2022-08-01T00:00:00Z", "end_exclusive": "2025-08-01T00:00:00Z",
        "symbols": SYMBOLS, "venue": "binance", "market": "spot", "url": URL,
        "expected_hourly_intervals_per_asset": 26304, "native_hourly_bars_per_asset": 26303,
        "evaluated_hourly_bars_per_asset": 26300, "evaluated_h4_bars_per_asset": 6575,
        "native_gap": "2023-03-24T13:00:00Z",
        "shared_excluded_block": {"start": iso(GAP_START), "end_exclusive": iso(GAP_END)},
        "h4_source": "exact_four_hour_aggregation_of_same_native_hourly_source",
        "holdout_evaluated": False, "execution_enabled": False,
        "economic_assumptions": "spot_no_leverage; fixed_initial_slots; no_profit_etapes; modeled_costs_and_precision",
        "selection": "all_six_prespecified_cases_reported; no_parameter_search",
        "cases": [
            {"id": name, "policy": primitive(runner.policy()), "policy_digest": digest(runner.policy())}
            for name, runner in runners()
        ],
    }


def protocol():
    raw = PROTOCOL.read_bytes()
    value = json.loads(raw)
    if value != json.loads(canonical(expected_protocol())):
        raise ValueError("frozen study configuration differs")
    return value, hashlib.sha256(raw).hexdigest()


def write_new(path, value):
    with path.open("x", encoding="utf-8") as handle:
        handle.write(canonical(value) + "\n")


def import_data(output):
    frozen, protocol_sha = protocol()
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    streams = []
    for symbol in SYMBOLS:
        snapshot, pages = fetch_history(symbol, parse_time(frozen["start"]),
                                       parse_time(frozen["end_exclusive"]))
        raw = (canonical(snapshot) + "\n").encode()
        restored, bars = load_history(raw)
        if restored != snapshot or len(bars) != frozen["native_hourly_bars_per_asset"]:
            raise ValueError("source roundtrip or window mismatch")
        filename = f"{symbol}-1h.json"
        (output / filename).write_bytes(raw)
        streams.append({
            "symbol": symbol, "file": filename, "file_sha256": hashlib.sha256(raw).hexdigest(),
            "data_digest": snapshot["data_digest"], "bars": len(bars), "pages": pages,
        })
        print(f"{symbol}: {len(bars)} exact hourly bars, {len(pages)} public GETs", flush=True)
    write_new(output / "source-receipt.json", {
        "schema_version": "h1-h4-source-receipt/1", "protocol_sha256": protocol_sha,
        "streams": streams, "venue": "binance", "market": "spot",
        "performance_evaluated": False, "holdout_requested": False, "execution_enabled": False,
    })


def inputs(directory):
    frozen, protocol_sha = protocol()
    receipt = json.loads((directory / "source-receipt.json").read_text())
    if (receipt.get("protocol_sha256") != protocol_sha
            or receipt.get("venue") != "binance" or receipt.get("market") != "spot"
            or [s["symbol"] for s in receipt["streams"]] != list(SYMBOLS)):
        raise ValueError("source receipt/protocol/cohort mismatch")
    hourly, manifest = [], []
    for stream in receipt["streams"]:
        if stream["file"] != f"{stream['symbol']}-1h.json":
            raise ValueError("fixed source filename required")
        path = directory / stream["file"]
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
            raise ValueError("bounded regular source file required")
        raw = path.read_bytes()
        snapshot, bars = load_history(raw)
        if (hashlib.sha256(raw).hexdigest() != stream["file_sha256"]
                or snapshot["data_digest"] != stream["data_digest"]
                or snapshot["symbol"] != stream["symbol"]
                or len(bars) != frozen["native_hourly_bars_per_asset"]
                or iso(bars[0].open_time) != frozen["start"]
                or iso(bars[-1].close_time) != frozen["end_exclusive"]):
            raise ValueError("exact frozen research input differs")
        hourly.extend(b for b in bars if not GAP_START <= b.open_time < GAP_END)
        manifest.append({k: stream[k] for k in ("symbol", "file_sha256", "data_digest", "bars")})
    return tuple(hourly), {"protocol_sha256": protocol_sha, "datasets": manifest}


def summary(name, runner, result):
    with localcontext() as context:
        context.prec = 36
        state, capital = result["state"], result["capital"]
        buys = [o for o in state.orders if o.intent.side == Side.BUY and o.filled_quantity > 0]
        cycles = defaultdict(list)
        for order in buys:
            cycles[order.intent.basket_id].append(order.intent.stage)
        gains = sum((b.net_pnl for b in state.closed_baskets if b.net_pnl > 0), D("0"))
        losses = -sum((b.net_pnl for b in state.closed_baskets if b.net_pnl < 0), D("0"))
        seconds = D(str((capital[-1].at - capital[0].at).total_seconds()))
        weighted = sum((a.position_principal * D(str((b.at - a.at).total_seconds()))
                        for a, b in zip(capital, capital[1:])), D("0")) / seconds
        ids = {o.intent.intent_id: o.intent.side for o in state.orders}
        reasons = Counter(e.reason for e in result["events"]
                          if e.kind in ("entry_blocked", "simulated_order_cancelled"))
        admission_reasons, admission_stages = Counter(), Counter()
        for event in result["events"]:
            if event.reason.startswith("allocation:"):
                admission = json.loads(event.reason[len("allocation:"):])
                if not admission["assessment"]["allowed"]:
                    admission_reasons.update(admission["assessment"]["reasons"])
                    admission_stages[admission["stage"]] += 1
        policy = runner.policy()
        return json_value({
            "id": name, "hours": runner.hours, "capacity": runner.plan.capacity,
            "policy_digest": result["policy_digest"], "data_digest": result["data_digest"],
            "configuration_digest": state.configuration_digest,
            "costs": runner.costs, "initial_capital": state.account.initial_equity,
            "slot_total": runner.plan.slot_principal + runner.plan.slot_costs,
            "slot_principal": runner.plan.slot_principal, "slot_costs": runner.plan.slot_costs,
            "stages": runner.plan.stages,
            "net_pnl": result["net_pnl"], "net_return_fraction": result["net_pnl"] / state.account.initial_equity,
            "maximum_drawdown_fraction": result["maximum_drawdown_fraction"],
            "time_weighted_position_principal": weighted,
            "time_weighted_principal_fraction": weighted / state.account.initial_equity,
            "maximum_position_principal": max(p.position_principal for p in capital),
            "maximum_active_baskets": max(p.active_baskets for p in capital),
            "closed_baskets": len(state.closed_baskets),
            "profit_factor_closed_only": gains / losses if losses else None,
            "closed_baskets_by_asset": {s: sum(b.symbol == s for b in state.closed_baskets) for s in SYMBOLS},
            "filled_buy_orders_by_stage": dict(sorted(Counter(o.intent.stage for o in buys).items())),
            "basket_maximum_stage_distribution": dict(sorted(Counter(max(v) for v in cycles.values()).items())),
            "entry_fees": sum((f.fee for f in result["fills"] if ids[f.intent_id] == Side.BUY), D("0")),
            "exit_fees": sum((f.fee for f in result["fills"] if ids[f.intent_id] == Side.SELL), D("0")),
            "blocked_entry_reasons": dict(reasons), "halted": state.account.halted,
            "allocation_rejected_attempts_by_reason": dict(admission_reasons),
            "allocation_rejected_attempts_by_stage": dict(sorted(admission_stages.items())),
            "halt_reasons": state.account.halt_reasons,
            "first_halt_at": result["first_halt_at"],
            "retained_bar_counts": {s: len(h) for s, h in zip(SYMBOLS, state.bar_evidence)},
            "open_positions": [
                {"symbol": b.symbol, "quantity": b.quantity, "average_price": b.average_price}
                for b in state.baskets if b.quantity
            ],
            "execution_assumption": policy["execution"],
            "holdout_evaluated": False, "execution_enabled": False,
        })


def run(directory, output):
    hourly, manifest = inputs(directory)
    sealed = json.loads((directory / "dataset-manifest.json").read_text())
    if sealed != manifest:
        raise ValueError("dataset manifest differs; never reseal after performance")
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    h4 = tuple(bar for symbol in SYMBOLS
               for segment in (
                   tuple(b for b in hourly if b.symbol == symbol and b.open_time < GAP_START),
                   tuple(b for b in hourly if b.symbol == symbol and b.open_time >= GAP_END),
               ) for bar in aggregate_h4(segment))
    reports = []
    for name, runner in runners():
        print(f"starting {name}", flush=True)
        result = runner.run(
            hourly if runner.hours == 1 else h4,
            observe=lambda count, state: print(
                f"{name}: {count} frames, {len(state.closed_baskets)} closed baskets",
                flush=True,
            ),
        )
        report = summary(name, runner, result)
        reports.append(report)
        write_new(output / f"{name}.json", report)
        # Actual economic curve stays in ignored local artifacts, without
        # serializing a Merkle root as if it could restore the engine state.
        write_new(output / f"{name}-curve.json", {
            "case": name, "policy_digest": report["policy_digest"],
            "data_digest": report["data_digest"],
            "points": [json_value({
                "at": p.at, "equity": q.equity, "position_principal": p.position_principal,
                "active_baskets": p.active_baskets,
            }) for p, q in zip(result["capital"], result["curve"])],
        })
        print(f"completed {name}: net={report['net_pnl']}, closed={report['closed_baskets']}", flush=True)
        del result
        gc.collect()
    write_new(output / "comparison.json", {
        "schema_version": "h1-h4-basket-comparison/1", "source_manifest": manifest,
        "cases": reports, "completed_at": iso(datetime.now(timezone.utc)),
        "research_only": True, "holdout_evaluated": False, "execution_enabled": False,
    })


def export_results(directory):
    """Compact review artifacts; verify curves against every reported end value."""
    frozen, protocol_sha = protocol()
    comparison_path = directory / "comparison.json"
    comparison = json.loads(comparison_path.read_text())
    expected = list(runners())
    if (comparison.get("schema_version") != "h1-h4-basket-comparison/1"
            or comparison["source_manifest"]["protocol_sha256"] != protocol_sha
            or [r["id"] for r in comparison["cases"]] != [name for name, _ in expected]
            or comparison["execution_enabled"] is not False
            or comparison["holdout_evaluated"] is not False):
        raise ValueError("complete frozen comparison required")
    monthly = {}
    with localcontext() as context:
        context.prec = 64
        for report, (name, runner) in zip(comparison["cases"], expected):
            if report["policy_digest"] != digest(runner.policy()):
                raise ValueError("case policy differs")
            curve_path = directory / f"{name}-curve.json"
            curve = json.loads(curve_path.read_text())
            if (curve["case"] != name or curve["data_digest"] != report["data_digest"]
                    or curve["policy_digest"] != report["policy_digest"]
                    or len(curve["points"]) != 4 * (
                        frozen["evaluated_hourly_bars_per_asset"] if runner.hours == 1
                        else frozen["evaluated_h4_bars_per_asset"]) + 1
                    or D(curve["points"][-1]["equity"]) - D(report["initial_capital"]) != D(report["net_pnl"])):
                raise ValueError("full curve/report mismatch")
            points = {}
            for point in curve["points"]:
                at = datetime.fromisoformat(point["at"])
                if at.day == 1 and at.hour == at.minute == at.second == at.microsecond == 0:
                    # First sample at a repeated boundary is the prior close,
                    # before the same-time next-open gap.
                    points.setdefault(at.date().isoformat(), point["equity"])
            if len(points) != 37:
                raise ValueError("exact 37 monthly research boundaries required")
            monthly[name] = points
            report["curve_file_sha256"] = hashlib.sha256(curve_path.read_bytes()).hexdigest()
            report["annual_net_pnl"] = [
                str(D(points[f"{year + 1}-08-01"]) - D(points[f"{year}-08-01"]))
                for year in (2022, 2023, 2024)
            ]
            # Keep diagnostics concise instead of using entire serialized
            # admission records as counter labels.
            simplified = Counter()
            for reason, count in report["blocked_entry_reasons"].items():
                if reason.startswith("allocation:"):
                    for cause in json.loads(reason[len("allocation:"):])["assessment"]["reasons"]:
                        simplified[cause] += count
                else:
                    simplified[reason] += count
            report["blocked_entry_reasons"] = dict(simplified)
    comparison["raw_comparison_sha256"] = hashlib.sha256(comparison_path.read_bytes()).hexdigest()
    comparison["monthly_curve_policy"] = "37_month_boundaries; previous_close_before_open_gap; full_curve_used_for_metrics"
    write_new(ROOT / "docs/research-protocols/h1-h4-baskets-result-20261111.json", comparison)
    with (ROOT / "docs/research-protocols/h1-h4-baskets-monthly-20261111.csv").open("x", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["utc_previous_close", *monthly])
        for at in next(iter(monthly.values())):
            writer.writerow([at, *(points[at] for points in monthly.values())])
    print("All six curves verified; compact results and 37 monthly boundaries exported.")


def main():
    if len(sys.argv) == 2 and sys.argv[1] == "freeze":
        write_new(PROTOCOL, expected_protocol())
        print(PROTOCOL.relative_to(ROOT))
    elif len(sys.argv) == 3 and sys.argv[1] == "import":
        import_data(Path(sys.argv[2]).resolve())
    elif len(sys.argv) == 3 and sys.argv[1] == "seal":
        _, manifest = inputs(Path(sys.argv[2]).resolve())
        write_new(Path(sys.argv[2]).resolve() / "dataset-manifest.json", manifest)
        print(canonical(manifest))
    elif len(sys.argv) == 4 and sys.argv[1] == "run":
        run(Path(sys.argv[2]).resolve(), Path(sys.argv[3]).resolve())
    elif len(sys.argv) == 3 and sys.argv[1] == "export":
        export_results(Path(sys.argv[2]).resolve())
    else:
        raise SystemExit("usage: research-timeframes.py freeze | import DIR | seal DIR | run SOURCE OUT | export OUT")


if __name__ == "__main__":
    main()
