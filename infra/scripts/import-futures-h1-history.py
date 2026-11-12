#!/usr/bin/env python3
"""Frozen create-only native H1/Funding cohort; no DB or performance."""
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / name) for name in ("packages/trading/src", "packages/marketdata/src")]

from investalo_marketdata.binance_futures_hourly import (
    HourlyHistoryAdapter, fetch_hourly_json, funding_diagnostics, load_hourly_snapshot,
)
from investalo_marketdata.snapshot import canonical, decode_json, iso, parse_time

PROTOCOL_SHA256 = "3b3ecdd1b9c630a59e0b5f33f1255b0012c73dce7274bba81ee3435224336c57"


def main():
    protocol_path = ROOT / "docs/research-protocols/futures-h1-history-20261112.json"
    raw = protocol_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PROTOCOL_SHA256:
        raise ValueError("frozen hourly protocol changed")
    protocol = decode_json(raw)
    if len(sys.argv) != 2:
        raise SystemExit("usage: import-futures-h1-history.py NEW_OUTPUT_DIRECTORY (create-only)")
    output = Path(sys.argv[1]).resolve()
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    started, streams = datetime.now(timezone.utc), []
    adapter = HourlyHistoryAdapter(fetch_hourly_json)
    start, end = parse_time(protocol["start"]), parse_time(protocol["end_exclusive"])
    for symbol in protocol["symbols"]:
        for kind in (*protocol["price_kinds"], "funding"):
            snapshot, pages = adapter.fetch_history(symbol, kind, start=start, end=end, retrieved_at=started)
            if kind != "funding" and len(snapshot.rows) != protocol["expected_h1_bars_per_stream"]:
                raise ValueError("frozen H1 source count mismatch")
            text = canonical(snapshot.record())
            filename = f"{symbol}-{kind}.json"
            path = output / filename
            with path.open("x", encoding="utf-8") as handle:
                handle.write(text)
            readback = path.read_text(encoding="utf-8")
            if readback != text or load_hourly_snapshot(readback) != snapshot:
                raise ValueError("saved hourly source roundtrip mismatch")
            stream = {
                "symbol": symbol, "kind": kind, "file": filename,
                "file_sha256": hashlib.sha256(readback.encode()).hexdigest(),
                "data_digest": snapshot.data_digest, "rows": len(snapshot.rows), "pages": pages,
            }
            if kind == "funding":
                stream["coverage_diagnostic"] = funding_diagnostics(snapshot)
            streams.append(stream)
            print(f"{symbol} {kind}: {len(snapshot.rows)} native rows; {len(pages)} GETs", flush=True)
    diagnostics = [s["coverage_diagnostic"] for s in streams if s["kind"] == "funding"]
    receipt = {
        "schema_version": "futures-hourly-source-receipt/1", "venue": "binance",
        "protocol_file": str(protocol_path.relative_to(ROOT)), "protocol_sha256": PROTOCOL_SHA256,
        "started_at": iso(started), "finished_at": iso(datetime.now(timezone.utc)), "streams": streams,
        "shared_hourly_axis_verified": True, "all_price_windows_complete": True,
        "all_funding_windows_match_declared_buckets": all(
            not (d["missing_buckets"] or d["unexpected_buckets"] or d["duplicate_buckets"])
            for d in diagnostics),
        "bitget_trading_target_unchanged": True, "net_backtest_ready": False,
        "historical_schedule_verified": False, "historical_fee_and_maintenance_rules_verified": False,
        "performance_evaluated": False, "holdout_requested": False, "execution_enabled": False,
    }
    with (output / "receipt.json").open("x", encoding="utf-8") as handle:
        handle.write(canonical(receipt) + "\n")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as error:
        raise SystemExit(f"hourly import failed: {type(error).__name__}; inspect output before a new run") from None
