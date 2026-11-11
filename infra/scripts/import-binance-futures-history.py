#!/usr/bin/env python3
"""Frozen native Binance source import; create-only artifacts, no DB/performance."""
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / name) for name in ("packages/trading/src", "packages/marketdata/src")]

from investalo_marketdata.binance_futures import (
    BinanceHistoryAdapter, fetch_binance_json, funding_diagnostics, load_binance_snapshot,
)
from investalo_marketdata.snapshot import canonical, decode_json, iso, parse_time

PROTOCOL_SHA256 = "158efdde024bf3856cf23fc6b6c324727c0b66cb2e23c2c00c052b257ee35bbf"


def main():
    protocol_path = ROOT / "docs/research-protocols/binance-futures-history-20261111.json"
    protocol_bytes = protocol_path.read_bytes()
    if hashlib.sha256(protocol_bytes).hexdigest() != PROTOCOL_SHA256:
        raise ValueError("frozen Binance source protocol changed")
    protocol = decode_json(protocol_bytes)
    if len(sys.argv) != 2:
        raise SystemExit("usage: import-binance-futures-history.py OUTPUT_DIRECTORY (create-only)")
    output = Path(sys.argv[1]).resolve()
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    started, streams = datetime.now(timezone.utc), []
    adapter = BinanceHistoryAdapter(fetch_binance_json)
    start, end = parse_time(protocol["start"]), parse_time(protocol["end_exclusive"])
    for symbol in protocol["symbols"]:
        for kind in (*protocol["price_kinds"], "funding"):
            snapshot, pages = adapter.fetch_history(symbol, kind, start=start, end=end, retrieved_at=started)
            if kind != "funding" and len(snapshot.rows) != protocol["expected_h4_bars_per_stream"]:
                raise ValueError("frozen native H4 count mismatch")
            text = canonical(snapshot.record())
            if load_binance_snapshot(text) != snapshot:
                raise ValueError("native Binance snapshot roundtrip mismatch")
            filename = f"{symbol}-{kind}.json"
            with (output / filename).open("x", encoding="utf-8") as handle:
                handle.write(text)
            stream = {
                "symbol": symbol, "kind": kind, "file": filename,
                "file_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "data_digest": snapshot.data_digest, "rows": len(snapshot.rows), "pages": pages,
            }
            if kind == "funding":
                stream["coverage_diagnostic"] = funding_diagnostics(snapshot)
            streams.append(stream)
            print(f"{symbol} {kind}: {len(snapshot.rows)} native rows; {len(pages)} GETs", flush=True)
    funding = [s["coverage_diagnostic"] for s in streams if s["kind"] == "funding"]
    receipt = {
        "schema_version": "binance-futures-source-receipt/1", "venue": "binance",
        "protocol_file": str(protocol_path.relative_to(ROOT)), "protocol_sha256": PROTOCOL_SHA256,
        "started_at": iso(started), "finished_at": iso(datetime.now(timezone.utc)), "streams": streams,
        "all_price_windows_complete": True,
        "all_funding_windows_match_declared_buckets": all(
            not (d["missing_buckets"] or d["unexpected_buckets"] or d["duplicate_buckets"]) for d in funding
        ),
        "bitget_trading_target_unchanged": True, "net_backtest_ready": False,
        "historical_schedule_verified": False, "historical_fee_and_maintenance_rules_verified": False,
        "performance_evaluated": False, "holdout_requested": False, "execution_enabled": False,
    }
    with (output / "receipt.json").open("x", encoding="utf-8") as handle:
        handle.write(canonical(receipt) + "\n")


if __name__ == "__main__":
    main()
