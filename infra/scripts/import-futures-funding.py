#!/usr/bin/env python3
"""Create-only observations and honest calendar diagnostics; no DB or net backtest."""
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / name) for name in ("packages/trading/src", "packages/marketdata/src")]

from investalo_marketdata.futures_funding import (
    BitgetFundingHistoryAdapter, audit_funding_coverage, fetch_funding_json,
    regular_funding_expectation,
)
from investalo_marketdata.futures_snapshot import dump_funding_snapshot, load_funding_snapshot
from investalo_marketdata.snapshot import canonical, decode_json, iso, parse_time

PROTOCOL_SHA256 = "a97d484d9a9e1ce9f16e3748128ddf9ed81e2a68c932bd6d7acee6e5ad4ee418"


def main():
    protocol_path = ROOT / "docs/research-protocols/futures-funding-20261111.json"
    protocol_bytes = protocol_path.read_bytes()
    if hashlib.sha256(protocol_bytes).hexdigest() != PROTOCOL_SHA256:
        raise ValueError("frozen funding protocol changed")
    protocol = decode_json(protocol_bytes)
    if len(sys.argv) != 2:
        raise SystemExit("usage: import-futures-funding.py OUTPUT_DIRECTORY (create-only)")
    output = Path(sys.argv[1]).resolve()
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    started, streams = datetime.now(timezone.utc), []
    for symbol in protocol["symbols"]:
        expectation = regular_funding_expectation(
            symbol, parse_time(protocol["requested_start"]),
            parse_time(protocol["requested_end_exclusive"]),
            interval_hours=protocol["declared_interval_hours"],
            assumptions_digest=hashlib.sha256(protocol_bytes).hexdigest(),
        )
        if len(expectation.settlements) != protocol["expected_events_per_symbol"]:
            raise ValueError("frozen settlement expectation changed")
        result = BitgetFundingHistoryAdapter(fetch_funding_json).fetch_history(
            symbol, start=expectation.start, end=expectation.end, retrieved_at=started,
        )
        artifacts = {}
        for label, snapshot in (("requested", result.requested), ("recent-observed", result.observed)):
            text = dump_funding_snapshot(snapshot)
            if load_funding_snapshot(text) != snapshot:
                raise ValueError("funding snapshot roundtrip mismatch")
            filename = f"{symbol}-{label}-funding.json"
            with (output / filename).open("x", encoding="utf-8") as handle:
                handle.write(text)
            artifacts[label] = {
                "file": filename, "file_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "data_digest": snapshot.data_digest, "events": len(snapshot.events),
            }
        coverage = audit_funding_coverage(result.requested, expectation)
        stream = {
            "symbol": symbol, "artifacts": artifacts, "coverage": coverage,
            "pages": [page.record() for page in result.pages],
            "termination": result.termination,
            "observed_start": iso(result.observed.events[0].timestamp) if result.observed.events else None,
            "observed_last_settlement": iso(result.observed.events[-1].timestamp)
            if result.observed.events else None,
        }
        streams.append(stream)
        print(f"{symbol}: requested={len(result.requested.events)}; "
              f"recent_observed={len(result.observed.events)}; "
              f"missing={coverage['missing_events']}; pages={len(result.pages)}", flush=True)
    receipt = {
        "schema_version": "funding-availability-receipt/1",
        "protocol_file": str(protocol_path.relative_to(ROOT)),
        "protocol_sha256": hashlib.sha256(protocol_bytes).hexdigest(),
        "started_at": iso(started), "finished_at": iso(datetime.now(timezone.utc)),
        "streams": streams,
        "all_windows_match_declared_calendar": all(
            s["coverage"]["complete_against_declared_calendar"] for s in streams),
        "historical_schedule_verified": False, "net_backtest_ready": False,
        "performance_evaluated": False, "holdout_requested": False, "execution_enabled": False,
    }
    with (output / "receipt.json").open("x", encoding="utf-8") as handle:
        handle.write(canonical(receipt) + "\n")


if __name__ == "__main__":
    main()
