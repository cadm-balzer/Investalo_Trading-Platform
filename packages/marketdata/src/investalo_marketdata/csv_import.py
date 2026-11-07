"""Explicit provenance-labelled import. No sorting, gap filling or price rounding."""
import csv
import io
from datetime import datetime

from investalo_trading import Candle
from .snapshot import MAX_BARS, MAX_BYTES, DatasetSnapshot, SnapshotSource, make_snapshot, parse_time, price

CSV_FIELDS = ("symbol", "open_time", "close_time", "open", "high", "low", "close")


def import_csv(value: str | bytes, *, symbol: str, source: SnapshotSource,
               synthetic: bool, requested_start: datetime | None = None,
               requested_end: datetime | None = None) -> DatasetSnapshot:
    if isinstance(value, bytes):
        if len(value) > MAX_BYTES:
            raise ValueError("CSV exceeds resource bound")
        value = value.decode("utf-8-sig")
    if not isinstance(value, str) or len(value.encode("utf-8")) > MAX_BYTES:
        raise ValueError("CSV exceeds resource bound")
    reader = csv.DictReader(io.StringIO(value, newline=""), strict=True)
    if tuple(reader.fieldnames or ()) != CSV_FIELDS:
        raise ValueError("CSV header must exactly match the Candle contract")
    candles = []
    try:
        for row in reader:
            if len(candles) >= MAX_BARS or None in row or any(item is None for item in row.values()):
                raise ValueError("CSV count/columns outside bounds")
            candles.append(Candle(row["symbol"], parse_time(row["open_time"], aligned=True),
                                  parse_time(row["close_time"], aligned=True),
                                  *(price(row[name]) for name in ("open", "high", "low", "close"))))
    except csv.Error:
        raise ValueError("malformed CSV") from None
    return make_snapshot(symbol, tuple(candles), source, synthetic=synthetic,
                         requested_start=requested_start, requested_end=requested_end)
