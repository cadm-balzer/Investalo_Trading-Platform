#!/usr/bin/env python3
"""Create-only public futures data acceptance; no DB, broker account or replay."""
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / name) for name in ("packages/trading/src", "packages/marketdata/src")]

from investalo_marketdata.futures_bitget import BitgetFuturesHistoryAdapter, fetch_futures_json
from investalo_marketdata.futures_snapshot import dump_futures_snapshot, load_futures_snapshot
from investalo_marketdata.snapshot import canonical, decode_json, iso, parse_time


def main():
    protocol_path = ROOT / "docs/research-protocols/futures-history-20261110.json"
    protocol_bytes = protocol_path.read_bytes()
    protocol = decode_json(protocol_bytes)
    if len(sys.argv) != 2:
        raise SystemExit("usage: import-futures-history.py OUTPUT_DIRECTORY (create-only)")
    output = Path(sys.argv[1]).resolve()
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    records = []
    started = datetime.now(timezone.utc)
    for symbol in protocol["symbols"]:
        for kind in protocol["price_kinds"]:
            pages = []

            def fetch(url):
                payload = fetch_futures_json(url)
                pages.append({
                    "url": url, "observed_at": iso(datetime.now(timezone.utc)),
                    "decoded_response_sha256": hashlib.sha256(canonical(payload).encode()).hexdigest(),
                    "provider_request_time_ms": payload.get("requestTime"),
                    "returned_rows": len(payload.get("data", [])),
                })
                return payload

            snapshot = BitgetFuturesHistoryAdapter(fetch).fetch_history(
                symbol, kind, start=parse_time(protocol["requested_start"], aligned=True),
                end=parse_time(protocol["requested_end_exclusive"], aligned=True),
                # Covers all closed historical candles; not a claim about API fetch completion.
                retrieved_at=started,
            )
            text = dump_futures_snapshot(snapshot)
            if load_futures_snapshot(text) != snapshot:
                raise ValueError("futures snapshot roundtrip mismatch")
            filename = f"{symbol}-{kind}-4h.json"
            with (output / filename).open("x", encoding="utf-8") as handle:
                handle.write(text)
            record = {
                "symbol": symbol, "price_kind": kind, "file": filename,
                "data_digest": snapshot.data_digest,
                "file_sha256": hashlib.sha256(text.encode()).hexdigest(),
                "bars": len(snapshot.candles), "coverage": snapshot.coverage.record(),
                "pages": pages,
            }
            records.append(record)
            print(f"{symbol} {kind}: {len(snapshot.candles)} bars; "
                  f"complete={snapshot.coverage.complete}; pages={len(pages)}", flush=True)
    receipt = {
        "schema_version": "futures-history-import-receipt/1",
        "protocol_file": str(protocol_path.relative_to(ROOT)),
        "protocol_sha256": hashlib.sha256(protocol_bytes).hexdigest(),
        "started_at": iso(started), "finished_at": iso(datetime.now(timezone.utc)),
        "output_directory": str(output), "streams": records,
        "all_requested_streams_complete": all(
            r["coverage"]["complete"] and r["bars"] == protocol["expected_bars_per_stream"]
            for r in records),
        "funding_imported": False, "historical_maintenance_known": False,
        "performance_evaluated": False, "holdout_requested": False,
        "execution_enabled": False,
    }
    with (output / "receipt.json").open("x", encoding="utf-8") as handle:
        handle.write(canonical(receipt) + "\n")


if __name__ == "__main__":
    main()
