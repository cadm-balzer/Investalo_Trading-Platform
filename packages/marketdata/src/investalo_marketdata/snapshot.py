"""Bounded immutable research data; no broker credentials or execution."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from urllib.parse import urlsplit

from investalo_trading import Candle

SCHEMA_VERSION = "marketdata-snapshot/1"
MAX_BARS = 10_000
MAX_BYTES = 16 * 1024 * 1024
H4 = timedelta(hours=4)
SYMBOLS = ("BTC/USDT", "ETH/USDT")
BITGET_URL = "https://api.bitget.com/api/v3/market/history-candles"


def utc_time(value: datetime, *, aligned: bool = False) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("explicit UTC timestamp required")
    result = value.astimezone(timezone.utc)
    if result.year < 1970:
        raise ValueError("timestamps before the Unix epoch are unsupported")
    if aligned and (result.hour % 4 or result.minute or result.second or result.microsecond):
        raise ValueError("timestamp must align to UTC H4")
    return result


def parse_time(value: object, *, aligned: bool = False) -> datetime:
    if not isinstance(value, str) or len(value) > 40 or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)", value
    ):
        raise ValueError("UTC ISO timestamp string required")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("invalid timestamp") from None
    return utc_time(result, aligned=aligned)


def iso(value: datetime) -> str:
    return utc_time(value).isoformat().replace("+00:00", "Z")


def price(value: object, *, zero: bool = False) -> Decimal:
    """Bound lexical work and numeric magnitude before arithmetic/canonicalization."""
    if not isinstance(value, str) or len(value) > 64 or not re.fullmatch(
        r"[+]?\d+(?:\.\d+)?(?:[eE][+-]?\d{1,3})?", value
    ):
        raise ValueError("bounded Decimal string required")
    result = Decimal(value)
    if (not result.is_finite() or result < 0 or (not zero and result == 0)
            or result > Decimal("1e24")
            or result and result < Decimal("1e-24")
            or len(result.as_tuple().digits) > 36 or abs(result.as_tuple().exponent) > 24):
        raise ValueError("price/precision outside supported bounds")
    return result


def decimal_string(value: Decimal) -> str:
    price(str(value), zero=True)
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON member")
        result[key] = value
    return result


def decode_json(value: str | bytes, *, max_bytes: int = MAX_BYTES):
    if isinstance(value, bytes):
        if len(value) > max_bytes:
            raise ValueError("input exceeds resource bound")
        value = value.decode("utf-8")
    if not isinstance(value, str) or len(value.encode("utf-8")) > max_bytes:
        raise ValueError("input exceeds resource bound")
    try:
        return json.loads(value, object_pairs_hook=_strict_object,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))
    except (json.JSONDecodeError, RecursionError):
        raise ValueError("invalid bounded JSON") from None


def fields(value: object, expected: set[str]) -> dict:
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError("unexpected record fields")
    return value


@dataclass(frozen=True)
class SnapshotSource:
    venue: str
    api_version: str
    url: str | None
    retrieved_at: datetime

    def __post_init__(self):
        utc_time(self.retrieved_at)
        if not isinstance(self.venue, str) or not isinstance(self.api_version, str):
            raise ValueError("source identifiers must be strings")
        versions = {"bitget": "3", "csv": "csv-v1", "synthetic": "fixture-v1"}
        if versions.get(self.venue) != self.api_version:
            raise ValueError("unsupported provenance")
        if self.venue == "bitget" and self.url != BITGET_URL:
            raise ValueError("Bitget provenance must identify the public V3 endpoint")
        if self.venue == "synthetic" and self.url is not None:
            raise ValueError("synthetic data has no venue source URL")
        if self.url is not None:
            if not isinstance(self.url, str) or len(self.url) > 256:
                raise ValueError("source URL too long")
            parsed = urlsplit(self.url)
            if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                    or parsed.query or parsed.fragment):
                raise ValueError("clean HTTPS source URL required")

    def record(self, *, retrieval: bool = True) -> dict:
        result = {"venue": self.venue, "api_version": self.api_version, "url": self.url}
        if retrieval:
            result["retrieved_at"] = iso(self.retrieved_at)
        return result


@dataclass(frozen=True)
class InstrumentMetadata:
    """Optional provenance only; never silently applied as historical simulator rules."""
    venue_symbol: str
    quantity_step: Decimal
    quote_step: Decimal
    minimum_quote: Decimal
    basis: str
    source_url: str
    as_of: datetime

    def __post_init__(self):
        if self.venue_symbol not in ("BTCUSDT", "ETHUSDT"):
            raise ValueError("unsupported venue symbol")
        if not all(isinstance(value, Decimal) for value in
                   (self.quantity_step, self.quote_step, self.minimum_quote)):
            raise ValueError("instrument precision must use Decimal")
        price(str(self.quantity_step))
        price(str(self.quote_step))
        price(str(self.minimum_quote), zero=True)
        if self.basis not in ("historical", "current", "assumed"):
            raise ValueError("instrument rules need explicit provenance basis")
        if not isinstance(self.source_url, str):
            raise ValueError("metadata URL must be a string")
        parsed = urlsplit(self.source_url)
        if (len(self.source_url) > 256 or parsed.scheme != "https" or not parsed.hostname
                or parsed.username or parsed.password or parsed.query or parsed.fragment):
            raise ValueError("clean HTTPS metadata URL required")
        utc_time(self.as_of)

    def record(self) -> dict:
        return {
            "venue_symbol": self.venue_symbol,
            "quantity_step": decimal_string(self.quantity_step),
            "quote_step": decimal_string(self.quote_step),
            "minimum_quote": decimal_string(self.minimum_quote),
            "basis": self.basis, "source_url": self.source_url, "as_of": iso(self.as_of),
        }


@dataclass(frozen=True)
class HistoryCoverage:
    requested_start: datetime | None
    requested_end: datetime | None
    actual_start: datetime
    actual_end: datetime

    def __post_init__(self):
        utc_time(self.actual_start, aligned=True)
        utc_time(self.actual_end, aligned=True)
        if self.actual_start >= self.actual_end:
            raise ValueError("empty coverage")
        if (self.requested_start is None) != (self.requested_end is None):
            raise ValueError("both requested bounds required")
        if self.requested_start is not None:
            utc_time(self.requested_start, aligned=True)
            utc_time(self.requested_end, aligned=True)
            if not self.requested_start <= self.actual_start < self.actual_end <= self.requested_end:
                raise ValueError("actual history outside requested window")
            if (self.requested_end - self.requested_start) // H4 > MAX_BARS:
                raise ValueError("requested history exceeds bar bound")

    @property
    def complete(self) -> bool | None:
        if self.requested_start is None:
            return None
        return self.requested_start == self.actual_start and self.requested_end == self.actual_end

    def record(self) -> dict:
        requested = self.requested_start is not None
        return {
            "requested_start": iso(self.requested_start) if requested else None,
            "requested_end": iso(self.requested_end) if requested else None,
            "actual_start": iso(self.actual_start), "actual_end": iso(self.actual_end),
            "complete": self.complete,
            "missing_leading_bars": (self.actual_start - self.requested_start) // H4 if requested else None,
            "missing_trailing_bars": (self.requested_end - self.actual_end) // H4 if requested else None,
        }


def candle_record(bar: Candle) -> dict:
    return {"symbol": bar.symbol, "open_time": iso(bar.open_time), "close_time": iso(bar.close_time),
            **{key: decimal_string(getattr(bar, key)) for key in ("open", "high", "low", "close")}}


@dataclass(frozen=True)
class DatasetSnapshot:
    symbol: str
    source: SnapshotSource
    synthetic: bool
    candles: tuple[Candle, ...]
    coverage: HistoryCoverage
    instrument_metadata: InstrumentMetadata | None = None
    schema_version: str = SCHEMA_VERSION
    timeframe: str = "4h"
    data_digest: str = field(init=False)

    def __post_init__(self):
        if self.schema_version != SCHEMA_VERSION or self.timeframe != "4h" or self.symbol not in SYMBOLS:
            raise ValueError("unsupported snapshot contract")
        if not isinstance(self.source, SnapshotSource) or not isinstance(self.coverage, HistoryCoverage):
            raise ValueError("immutable source/coverage records required")
        if self.instrument_metadata is not None and not isinstance(self.instrument_metadata, InstrumentMetadata):
            raise ValueError("immutable instrument metadata required")
        if type(self.synthetic) is not bool or self.source.venue == "synthetic" and not self.synthetic:
            raise ValueError("truthful synthetic boolean required")
        if not isinstance(self.candles, tuple) or not 1 <= len(self.candles) <= MAX_BARS:
            raise ValueError("snapshot needs 1..10000 immutable candles")
        if self.source.retrieved_at > datetime.now(timezone.utc):
            raise ValueError("future retrieval timestamp")
        for index, bar in enumerate(self.candles):
            if not isinstance(bar, Candle) or bar.symbol != self.symbol:
                raise ValueError("candle symbol mismatch")
            utc_time(bar.open_time, aligned=True)
            utc_time(bar.close_time, aligned=True)
            if bar.close_time - bar.open_time != H4 or bar.close_time > self.source.retrieved_at:
                raise ValueError("future/unclosed candle")
            for name in ("open", "high", "low", "close"):
                price(str(getattr(bar, name)))
            if index and self.candles[index - 1].close_time != bar.open_time:
                raise ValueError("duplicate/out-of-order/gapped candles")
        if (self.coverage.actual_start != self.candles[0].open_time
                or self.coverage.actual_end != self.candles[-1].close_time):
            raise ValueError("coverage disagrees with candles")
        if self.coverage.requested_end is not None and self.coverage.requested_end > self.source.retrieved_at:
            raise ValueError("future/unclosed requested history")
        metadata = self.instrument_metadata
        if metadata and (metadata.venue_symbol != self.symbol.replace("/", "")
                         or metadata.as_of > self.source.retrieved_at):
            raise ValueError("instrument provenance mismatch/future")
        object.__setattr__(self, "data_digest",
                           hashlib.sha256(canonical(self.digest_record()).encode()).hexdigest())

    def digest_record(self) -> dict:
        return {
            "schema_version": self.schema_version, "symbol": self.symbol, "timeframe": self.timeframe,
            "source": self.source.record(retrieval=False), "synthetic": self.synthetic,
            "instrument_metadata": self.instrument_metadata.record() if self.instrument_metadata else None,
            "candles": [candle_record(bar) for bar in self.candles],
        }

    def record(self) -> dict:
        return {**self.digest_record(), "source": self.source.record(),
                "coverage": self.coverage.record(), "data_digest": self.data_digest}


def make_snapshot(symbol: str, candles: tuple[Candle, ...], source: SnapshotSource, *,
                  synthetic: bool, requested_start: datetime | None = None,
                  requested_end: datetime | None = None,
                  instrument_metadata: InstrumentMetadata | None = None) -> DatasetSnapshot:
    if not candles:
        raise ValueError("no history available; no snapshot or validation claim can be created")
    return DatasetSnapshot(symbol, source, synthetic, candles,
                           HistoryCoverage(requested_start, requested_end,
                                           candles[0].open_time, candles[-1].close_time),
                           instrument_metadata)


def dump_snapshot(snapshot: DatasetSnapshot) -> str:
    return canonical(snapshot.record())


def load_snapshot(value: str | bytes) -> DatasetSnapshot:
    raw = fields(decode_json(value), {
        "schema_version", "symbol", "timeframe", "source", "synthetic", "candles",
        "coverage", "data_digest", "instrument_metadata",
    })
    source = fields(raw["source"], {"venue", "api_version", "url", "retrieved_at"})
    source = SnapshotSource(source["venue"], source["api_version"], source["url"],
                            parse_time(source["retrieved_at"]))
    rows = raw["candles"]
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_BARS:
        raise ValueError("candle count outside resource bounds")
    candles = []
    for value in rows:
        row = fields(value, {"symbol", "open_time", "close_time", "open", "high", "low", "close"})
        candles.append(Candle(row["symbol"], parse_time(row["open_time"], aligned=True),
                              parse_time(row["close_time"], aligned=True),
                              *(price(row[name]) for name in ("open", "high", "low", "close"))))
    item = raw["instrument_metadata"]
    metadata = None
    if item is not None:
        item = fields(item, {"venue_symbol", "quantity_step", "quote_step", "minimum_quote",
                             "basis", "source_url", "as_of"})
        metadata = InstrumentMetadata(item["venue_symbol"], price(item["quantity_step"]),
                                      price(item["quote_step"]), price(item["minimum_quote"], zero=True),
                                      item["basis"], item["source_url"], parse_time(item["as_of"]))
    coverage = fields(raw["coverage"], {"requested_start", "requested_end", "actual_start",
                                       "actual_end", "complete", "missing_leading_bars",
                                       "missing_trailing_bars"})
    if coverage["complete"] is not None and type(coverage["complete"]) is not bool:
        raise ValueError("coverage complete must be boolean or null")
    for key in ("missing_leading_bars", "missing_trailing_bars"):
        if coverage[key] is not None and (type(coverage[key]) is not int or coverage[key] < 0):
            raise ValueError("coverage missing counts must be nonnegative integers or null")
    requested_start = parse_time(coverage["requested_start"], aligned=True) if coverage["requested_start"] else None
    requested_end = parse_time(coverage["requested_end"], aligned=True) if coverage["requested_end"] else None
    result = make_snapshot(raw["symbol"], tuple(candles), source, synthetic=raw["synthetic"],
                           requested_start=requested_start, requested_end=requested_end,
                           instrument_metadata=metadata)
    if raw["schema_version"] != SCHEMA_VERSION or raw["timeframe"] != "4h":
        raise ValueError("unsupported schema/timeframe")
    if coverage != result.coverage.record() or raw["data_digest"] != result.data_digest:
        raise ValueError("snapshot digest/coverage mismatch")
    return result


def to_trading_candles(snapshot: DatasetSnapshot) -> tuple[Candle, ...]:
    """Only translate public symbols into the existing versioned core notation."""
    return tuple(replace(bar, symbol=bar.symbol.replace("/", "")) for bar in snapshot.candles)
