"""Operator import/fetch CLI. This command never evaluates strategy performance."""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError

from . import (
    MAX_BYTES, SnapshotSource, dump_snapshot, import_csv, load_snapshot, synthetic_snapshot,
)
from .bitget import BitgetHistoryAdapter
from .snapshot import SYMBOLS, parse_time

VALIDATION_CODES = {
    "Bitget did not confirm a successful response": "PROVIDER_REJECTED",
    "unexpected Bitget page count": "PROVIDER_PAGE_SIZE",
    "unexpected Bitget candle row": "PROVIDER_ROW_SCHEMA",
    "Bitget timestamp must be bounded Unix millisecond text": "PROVIDER_TIMESTAMP_TYPE",
    "Bitget timestamp outside bounds": "PROVIDER_TIMESTAMP_RANGE",
    "duplicate candle within Bitget response": "PROVIDER_DUPLICATE_IN_PAGE",
    "Bitget returned future/nonprogressing candles": "PROVIDER_FUTURE_OR_NONPROGRESS",
    "duplicate candle across Bitget pages": "PROVIDER_DUPLICATE_ACROSS_PAGES",
    "history pagination made no progress": "PROVIDER_NO_PROGRESS",
    "history pagination exceeds request bound": "PROVIDER_REQUEST_LIMIT",
    "public data redirects are not permitted": "PROVIDER_REDIRECT",
    "future/unclosed requested history": "REQUEST_NOT_CLOSED",
    "request must contain 1..10000 H4 intervals": "REQUEST_RANGE",
    "no history available; no snapshot or validation claim can be created": "HISTORY_UNAVAILABLE",
    "duplicate/out-of-order/gapped candles": "HISTORY_ORDER_OR_GAP",
    "bounded Decimal string required": "PRICE_STRING_REQUIRED",
    "price/precision outside supported bounds": "PRICE_RANGE",
    "timestamp must align to UTC H4": "TIMESTAMP_ALIGNMENT",
    "explicit UTC timestamp required": "TIMESTAMP_UTC",
    "future/unclosed candle": "CANDLE_NOT_CLOSED",
    "inconsistent OHLC": "OHLC_CONTRADICTION",
    "input exceeds resource bound": "INPUT_SIZE",
    "snapshot digest/coverage mismatch": "SNAPSHOT_INTEGRITY",
}


def failure_code(error: Exception) -> str:
    """Only static diagnostics, never exception URLs, imported rows or file paths."""
    if isinstance(error, FileExistsError):
        return "OUTPUT_EXISTS"
    if isinstance(error, HTTPError):
        return "TRANSPORT_HTTP"
    if isinstance(error, URLError):
        return "TRANSPORT_NETWORK_OR_TLS"
    if isinstance(error, OSError):
        return "IO_UNAVAILABLE"
    if isinstance(error, ValueError):
        return VALIDATION_CODES.get(str(error), "INVALID_DATA")
    if isinstance(error, TypeError):
        return "INVALID_SCHEMA"
    return "INTERNAL_FAILURE"


def read_bounded(path: Path) -> bytes:
    with path.open("rb") as source:
        payload = source.read(MAX_BYTES + 1)
    if len(payload) > MAX_BYTES:
        raise ValueError("input exceeds resource bound")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create/validate labelled immutable H4 snapshots")
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("input", type=Path)
    csv = sub.add_parser("csv")
    csv.add_argument("input", type=Path)
    csv.add_argument("--symbol", choices=SYMBOLS, required=True)
    choice = csv.add_mutually_exclusive_group(required=True)
    choice.add_argument("--synthetic", action="store_true")
    choice.add_argument("--real", action="store_true", help="operator assertion, not venue verification")
    csv.add_argument("--source-url")
    csv.add_argument("--requested-start", type=parse_time)
    csv.add_argument("--requested-end", type=parse_time)
    fixture = sub.add_parser("synthetic")
    fixture.add_argument("--symbol", choices=SYMBOLS, required=True)
    fixture.add_argument("--bars", type=int, default=240)
    fixture.add_argument("--start", type=parse_time)
    bitget = sub.add_parser("bitget")
    bitget.add_argument("--symbol", choices=SYMBOLS, required=True)
    bitget.add_argument("--start", type=parse_time, required=True)
    bitget.add_argument("--end", type=parse_time, required=True)
    for command in (csv, fixture, bitget):
        command.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    stage = "input"
    try:
        if args.command == "validate":
            snapshot = load_snapshot(read_bounded(args.input))
        elif args.command == "csv":
            source = SnapshotSource("csv", "csv-v1", args.source_url, datetime.now(timezone.utc))
            snapshot = import_csv(read_bounded(args.input), symbol=args.symbol, source=source,
                                  synthetic=args.synthetic, requested_start=args.requested_start,
                                  requested_end=args.requested_end)
        elif args.command == "synthetic":
            stage = "fixture"
            parameters = {"bars": args.bars}
            if args.start:
                parameters["start"] = args.start
            snapshot = synthetic_snapshot(args.symbol, **parameters)
        else:
            stage = "public_fetch"
            snapshot = BitgetHistoryAdapter().fetch_history(args.symbol, start=args.start, end=args.end)
        if args.command != "validate":
            stage = "output"
            # Create-only; an existing immutable snapshot is never overwritten.
            with args.output.open("x", encoding="utf-8") as target:
                target.write(dump_snapshot(snapshot) + "\n")
        print(json.dumps({"data_digest": snapshot.data_digest, "symbol": snapshot.symbol,
                          "bar_count": len(snapshot.candles), "synthetic": snapshot.synthetic,
                          "coverage": snapshot.coverage.record()}, sort_keys=True))
        return 0
    except Exception as error:
        # Never echo raw response bodies, imported rows or credentials in paths.
        print(json.dumps({"error": "snapshot_rejected", "stage": stage,
                          "code": failure_code(error), "validation_claim": False}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
