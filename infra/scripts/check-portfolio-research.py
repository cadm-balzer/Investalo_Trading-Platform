#!/usr/bin/env python3
"""Replay ONLY the two already frozen research windows, with no DB/broker I/O."""

import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / path) for path in (
    "packages/marketdata/src", "packages/trading/src", "services/api/src",
)]

from investalo_marketdata import MAX_BYTES, dump_snapshot, load_snapshot, to_trading_candles
from investalo_trading import PortfolioSimulator, primitive
from investalo_trading.snapshot import digest
from investalo_api.research_spec import simulator, specification

ORIGINAL = Path("docs/research-protocols/crypto-h4-20261108.json")
FROZEN = Path("docs/research-protocols/crypto-portfolio-reference-20261109.json")
RESULT = Path("docs/research-protocols/crypto-portfolio-reference-result-20261109.json")


def protocol(root=ROOT):
    original = json.loads((root / ORIGINAL).read_text())
    if (original["schema_version"] != "crypto-research-protocol/1"
            or original["holdout_status"] != "reserved_not_evaluated"
            or original["frozen_specification"] != specification()
            or [a["symbol"] for a in original["assets"]] != ["BTC/USDT", "ETH/USDT"]):
        raise ValueError("original research specification differs")
    runner = PortfolioSimulator(simulator())
    return {
        "schema_version": "portfolio-research-protocol/1",
        "purpose": "research",
        "scope": "joint_baseline_only_not_q33_expanded_allocator",
        "start": "2022-08-01T00:00:00Z",
        "end": "2025-08-01T00:00:00Z",
        "holdout_status": "reserved_not_evaluated",
        "frozen_policy": {key: primitive(value) for key, value in runner.policy().items()},
        "policy_digest": digest(runner.policy()),
        "assets": [
            {"symbol": a["symbol"], "research": a["research"]}
            for a in original["assets"]
        ],
    }


def inputs(root=ROOT):
    expected = protocol(root)
    if json.loads((root / FROZEN).read_text()) != expected:
        raise ValueError("frozen portfolio specification differs")
    bars = []
    for asset in expected["assets"]:
        coin = asset["symbol"].split("/")[0].lower()
        path = root / f"infra/local/research-data/{coin}-research-three-year-20261108.json"
        if path.is_symlink() or not path.is_file():
            raise ValueError("fixed regular research input required")
        with path.open("rb") as source:
            payload = source.read(MAX_BYTES + 1)
        snapshot = load_snapshot(payload)
        frozen = asset["research"]
        if (snapshot.synthetic or snapshot.symbol != asset["symbol"]
                or snapshot.data_digest != frozen["data_digest"]
                or hashlib.sha256(dump_snapshot(snapshot).encode()).hexdigest() != frozen["content_digest"]
                or snapshot.coverage.record() != frozen["coverage"]
                or len(snapshot.candles) != 6576 or len(snapshot.candles) != frozen["bar_count"]):
            raise ValueError("research input binding differs")
        candles = to_trading_candles(snapshot)
        if (candles[0].open_time.isoformat() != "2022-08-01T00:00:00+00:00"
                or candles[-1].close_time.isoformat() != "2025-08-01T00:00:00+00:00"):
            raise ValueError("research input binding differs")
        bars.extend(candles)
    return tuple(bars)


def main():
    if os.geteuid() != 0:
        raise ValueError("protected local research files require the host owner")
    runner = PortfolioSimulator(simulator())
    result = runner.run(inputs(), account_id="joint-baseline-replay")
    report = {
        "schema_version": result.schema_version,
        "policy_digest": result.policy_digest,
        "data_digest": result.simulation.data_digest,
        "configuration_digest": result.simulation.configuration_digest,
        "cost_digest": result.simulation.cost_digest,
        "symbols": result.symbols,
        "net_pnl": result.simulation.net_pnl,
        "net_return_fraction": result.net_return_fraction,
        "maximum_drawdown_fraction": result.simulation.maximum_drawdown_fraction,
        "profit_factor": result.simulation.profit_factor,
        "closed_baskets": result.simulation.closed_basket_count,
        "closed_baskets_by_asset": {
            symbol: sum(b.symbol == symbol for b in result.simulation.state.closed_baskets)
            for symbol in result.symbols
        },
        "planned_principal": result.planned_principal,
        "initially_unassigned_capital": result.initially_unassigned_capital,
        "maximum_position_principal": result.maximum_position_principal,
        "time_weighted_position_principal": result.time_weighted_position_principal,
        "time_weighted_principal_fraction": result.time_weighted_principal_fraction,
        "peak_active_baskets": result.peak_active_baskets,
        "entry_fees": result.total_entry_fees,
        "exit_fees": result.total_exit_fees,
        "benchmark_policy": result.benchmark.policy,
        "benchmark_net_pnl": result.benchmark.net_pnl,
        "benchmark_maximum_drawdown_fraction": result.benchmark.maximum_drawdown_fraction,
        "benchmark_maximum_initial_loss_fraction": result.benchmark.maximum_initial_loss_fraction,
        "benchmark_maximum_daily_loss_fraction": result.benchmark.maximum_daily_loss_fraction,
        "validation_status": result.validation_status,
        "holdout_evaluated": False,
    }
    actual = {key: primitive(value) for key, value in report.items()}
    if json.loads((ROOT / RESULT).read_text()) != actual:
        expected = json.loads((ROOT / RESULT).read_text())
        differing = {key: value for key, value in actual.items() if expected.get(key) != value}
        raise ValueError(f"recorded joint baseline differs: {differing}; never overwrite it automatically")
    print(json.dumps(actual, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
