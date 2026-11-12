#!/usr/bin/env python3
"""Create-only frozen economic/source preflight; no price replay or performance."""
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / name) for name in ("packages/trading/src", "packages/marketdata/src")]

from investalo_marketdata.binance_futures_hourly import load_hourly_snapshot
from investalo_marketdata.futures_research_profile import (
    PROTOCOL_SHA256, funding_reference, load_economic_protocol,
)
from investalo_marketdata.snapshot import canonical, decode_json, iso
from investalo_trading.snapshot import primitive

SOURCE_RECEIPT_SHA256 = "1209f326a288c088558d5524eb510cec952665a7d8e29862406da7daf711e01b"


def main():
    raw_protocol = (ROOT / "docs/research-protocols/futures-capital-economics-20261112.json").read_bytes()
    scenarios = load_economic_protocol(raw_protocol)
    protocol = decode_json(raw_protocol)
    raw_receipt = (ROOT / "docs/research-protocols/futures-h1-history-receipt-20261112.json").read_bytes()
    if hashlib.sha256(raw_receipt).hexdigest() != SOURCE_RECEIPT_SHA256:
        raise ValueError("frozen native source receipt changed")
    source_receipt = decode_json(raw_receipt)
    if source_receipt["protocol_sha256"] != protocol["source_protocol_sha256"]:
        raise ValueError("foreign source protocol")
    if len(sys.argv) != 2:
        raise SystemExit("usage: preflight-futures-capital.py NEW_OUTPUT_DIRECTORY (create-only)")
    output = Path(sys.argv[1]).resolve()
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    source = ROOT / "infra/local/futures-h1-research-data/20261112-native-network"
    streams = {(r["symbol"], r["kind"]): r for r in source_receipt["streams"]}
    if set(streams) != {(s, k) for s in protocol["symbols"] for k in ("trade", "mark", "funding")}:
        raise ValueError("complete source cohort required")
    artifacts, coverage, group_sizes = [], [], {}
    reference_counts = {s.scenario_id: {"native_mark": 0, "H1_open_approximation": 0,
                                       "positive_rate_stressed": 0} for s in scenarios}
    price_rows, funding_rows, exact_hour_rows = 0, 0, 0
    for symbol in protocol["symbols"]:
        snapshots = {}
        for kind in ("trade", "mark", "funding"):
            entry = streams[symbol, kind]
            filename = f"{symbol}-{kind}.json"
            if entry["file"] != filename:
                raise ValueError("fixed native source filename required")
            path = source / filename
            if path.stat().st_size > 16 * 1024 * 1024:
                raise ValueError("native source exceeds bounded snapshot size")
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != entry["file_sha256"]:
                raise ValueError("native source file hash mismatch")
            snapshot = load_hourly_snapshot(raw.decode())
            if (snapshot.symbol != symbol or snapshot.kind != kind
                    or snapshot.data_digest != entry["data_digest"] or len(snapshot.rows) != entry["rows"]
                    or iso(snapshot.start) != protocol["start"]
                    or iso(snapshot.end) != protocol["end_exclusive"]):
                raise ValueError("native source window or digest mismatch")
            if kind != "funding":
                if len(snapshot.rows) != protocol["expected_h1_bars_per_stream"]:
                    raise ValueError("incomplete native price axis")
                price_rows += len(snapshot.rows)
            snapshots[kind] = snapshot
            artifacts.append({key: entry[key] for key in (
                "symbol", "kind", "file", "file_sha256", "data_digest", "rows")})
        if tuple(r.open_time for r in snapshots["trade"].rows) != tuple(
                r.open_time for r in snapshots["mark"].rows):
            raise ValueError("trade and mark axes differ")
        funding = snapshots["funding"]
        funding_digest = funding.data_digest
        missing, exact = 0, 0
        for row in funding.rows:
            index = (row.timestamp.replace(minute=0, second=0, microsecond=0)
                     - funding.start) // timedelta(hours=1)
            mark = snapshots["mark"].rows[index]
            for scenario in scenarios:
                ref = funding_reference(symbol, row, mark, funding_digest, scenario)
                counts = reference_counts[scenario.scenario_id]
                counts["native_mark" if row.mark_price is not None else "H1_open_approximation"] += 1
                counts["positive_rate_stressed"] += ref.applied_rate != ref.native_rate
                if ref.timestamp != row.timestamp:
                    raise ValueError("native funding timestamp shifted")
            missing += row.mark_price is None
            exact += row.timestamp.microsecond == 0
            group_sizes[row.timestamp] = group_sizes.get(row.timestamp, 0) + 1
        funding_rows += len(funding.rows)
        exact_hour_rows += exact
        coverage.append({"symbol": symbol, "funding_events": len(funding.rows),
                         "exact_hour_events": exact, "missing_native_settlement_marks": missing})
        print(f"{symbol}: native hashes/axes and {len(funding.rows)} funding references across ten scenarios verified",
              flush=True)
    if max(group_sizes.values()) > len(protocol["symbols"]):
        raise ValueError("duplicate symbol in simultaneous funding group")
    records = []
    for scenario in scenarios:
        profile = scenario.profile()
        records.append({
            "scenario": primitive(scenario), "assumptions_digest": scenario.assumptions_digest,
            "profile_digest": profile.profile_digest, "profile": primitive(profile),
            "funding_reference_counts": reference_counts[scenario.scenario_id],
        })
    receipt = {
        "schema_version": "futures-capital-economic-preflight/1",
        "verified_at": iso(datetime.now(timezone.utc)), "protocol_sha256": PROTOCOL_SHA256,
        "source_receipt_sha256": SOURCE_RECEIPT_SHA256, "artifacts": artifacts,
        "native_price_rows": price_rows, "native_funding_rows": funding_rows,
        "funding_exact_hour_rows": exact_hour_rows,
        "native_timestamp_groups": len(group_sizes), "maximum_simultaneous_settlements": max(group_sizes.values()),
        "coverage": coverage, "profiles": records,
        "economic_profile_frozen": True, "native_funding_references_verified": True,
        "historical_broker_cost_margin_and_insurance_rules_verified": False,
        "full_market_replay_job_implemented": False, "performance_evaluated": False,
        "holdout_requested": False, "execution_enabled": False,
    }
    with (output / "receipt.json").open("x", encoding="utf-8") as handle:
        handle.write(canonical(receipt) + "\n")
    print(f"source/economics preflight: {price_rows} price rows, {funding_rows} settlements, ten profiles; no performance",
          flush=True)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as error:
        raise SystemExit(f"economic preflight failed: {type(error).__name__}; inspect output before a new run") from None
