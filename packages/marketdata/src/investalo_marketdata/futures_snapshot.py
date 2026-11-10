"""Separate immutable public futures observations; no spot/core translation."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from types import MappingProxyType

from investalo_trading import Candle

from .snapshot import (
    H4, MAX_BARS, HistoryCoverage, candle_record, canonical, decode_json,
    fields, iso, parse_time, price, utc_time,
)

SCHEMA_VERSION = "futures-h4-snapshot/1"
FUNDING_SCHEMA_VERSION = "funding/1"
MARKET = "bitget-classic-v2-usdt-m-perpetual"
SYMBOLS = (
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ZECUSDT",
    "HYPEUSDT", "XMRUSDT", "LINKUSDT", "XLMUSDT", "NEARUSDT", "BCHUSDT",
    "LTCUSDT", "UNIUSDT", "AVAXUSDT", "HBARUSDT", "TRXUSDT", "BGBUSDT",
    "BATUSDT", "RENDERUSDT",
)
ENDPOINTS = MappingProxyType({
    "trade": "https://api.bitget.com/api/v2/mix/market/history-candles",
    "mark": "https://api.bitget.com/api/v2/mix/market/history-mark-candles",
    "index": "https://api.bitget.com/api/v2/mix/market/history-index-candles",
})
FUNDING_ENDPOINT = "https://api.bitget.com/api/v2/mix/market/history-fund-rate"
MAX_FUNDING_EVENTS = 10_000


def _symbol(value: object) -> str:
    if not isinstance(value, str) or value not in SYMBOLS:
        raise ValueError("unsupported futures venue symbol")
    return value


def _price_kind(value: object) -> str:
    if not isinstance(value, str) or value not in ENDPOINTS:
        raise ValueError("unsupported futures price kind")
    return value


def candle_symbol(symbol: str, price_kind: str) -> str:
    """Keep market and price kind in the Candle's identity across boundaries."""
    return f"{_symbol(symbol)}:USDT-M:{_price_kind(price_kind)}"


def _retrieved(value: datetime) -> None:
    utc_time(value)
    if value > datetime.now(timezone.utc):
        raise ValueError("future retrieval timestamp")


@dataclass(frozen=True)
class FuturesSource:
    price_kind: str
    retrieved_at: datetime

    def __post_init__(self):
        _price_kind(self.price_kind)
        _retrieved(self.retrieved_at)

    @property
    def url(self) -> str:
        return ENDPOINTS[self.price_kind]

    def record(self, *, retrieval: bool = True) -> dict:
        result = {
            "venue": "bitget", "api_version": "2", "kind": "public-futures-history",
            "price_kind": self.price_kind, "url": self.url,
        }
        if retrieval:
            result["retrieved_at"] = iso(self.retrieved_at)
        return result


@dataclass(frozen=True)
class FuturesSnapshot:
    symbol: str
    price_kind: str
    source: FuturesSource
    candles: tuple[Candle, ...]
    coverage: HistoryCoverage
    schema_version: str = SCHEMA_VERSION
    timeframe: str = "4h"
    market: str = MARKET
    data_digest: str = field(init=False)

    def __post_init__(self):
        expected_symbol = candle_symbol(self.symbol, self.price_kind)
        if (self.schema_version != SCHEMA_VERSION or self.timeframe != "4h"
                or self.market != MARKET):
            raise ValueError("unsupported futures snapshot contract")
        if not isinstance(self.source, FuturesSource) or not isinstance(self.coverage, HistoryCoverage):
            raise ValueError("immutable futures source/coverage records required")
        if self.source.price_kind != self.price_kind:
            raise ValueError("source price kind mismatch")
        _retrieved(self.source.retrieved_at)
        if not isinstance(self.candles, tuple) or not 1 <= len(self.candles) <= MAX_BARS:
            raise ValueError("snapshot needs 1..10000 immutable candles")
        for index, bar in enumerate(self.candles):
            if not isinstance(bar, Candle) or bar.symbol != expected_symbol:
                raise ValueError("futures candle symbol/price kind mismatch")
            utc_time(bar.open_time, aligned=True)
            utc_time(bar.close_time, aligned=True)
            if bar.close_time - bar.open_time != H4 or bar.close_time > self.source.retrieved_at:
                raise ValueError("future/unclosed futures candle")
            for name in ("open", "high", "low", "close"):
                value = getattr(bar, name)
                if not isinstance(value, Decimal):
                    raise ValueError("OHLC must use Decimal")
                price(str(value))
            if bar.high < max(bar.open, bar.close, bar.low) or bar.low > min(bar.open, bar.close):
                raise ValueError("inconsistent OHLC")
            if index and self.candles[index - 1].close_time != bar.open_time:
                raise ValueError("duplicate/out-of-order/gapped futures candles")
        if (self.coverage.actual_start != self.candles[0].open_time
                or self.coverage.actual_end != self.candles[-1].close_time):
            raise ValueError("coverage disagrees with futures candles")
        if self.coverage.requested_end is not None and self.coverage.requested_end > self.source.retrieved_at:
            raise ValueError("future/unclosed requested futures history")
        object.__setattr__(self, "data_digest", _digest(self.digest_record()))

    def digest_record(self) -> dict:
        return {
            "schema_version": self.schema_version, "market": self.market,
            "symbol": self.symbol, "timeframe": self.timeframe, "price_kind": self.price_kind,
            "source": self.source.record(retrieval=False),
            "candles": [candle_record(bar) for bar in self.candles],
        }

    def record(self) -> dict:
        return {**self.digest_record(), "source": self.source.record(),
                "coverage": self.coverage.record(), "data_digest": self.data_digest}


def _digest(value: dict) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def make_futures_snapshot(symbol: str, price_kind: str, candles: tuple[Candle, ...],
                          source: FuturesSource, *, requested_start: datetime | None = None,
                          requested_end: datetime | None = None) -> FuturesSnapshot:
    if (not isinstance(candles, tuple) or not 1 <= len(candles) <= MAX_BARS
            or not all(isinstance(bar, Candle) for bar in candles)):
        raise ValueError("snapshot needs 1..10000 immutable candles")
    return FuturesSnapshot(symbol, price_kind, source, candles, HistoryCoverage(
        requested_start, requested_end, candles[0].open_time, candles[-1].close_time,
    ))


def dump_futures_snapshot(snapshot: FuturesSnapshot) -> str:
    if not isinstance(snapshot, FuturesSnapshot):
        raise ValueError("futures snapshot required")
    return canonical(snapshot.record())


def load_futures_snapshot(value: str | bytes) -> FuturesSnapshot:
    raw = fields(decode_json(value), {
        "schema_version", "market", "symbol", "timeframe", "price_kind", "source",
        "candles", "coverage", "data_digest",
    })
    if (raw["schema_version"] != SCHEMA_VERSION or raw["timeframe"] != "4h"
            or raw["market"] != MARKET):
        raise ValueError("unsupported futures schema/timeframe/market")
    source_raw = fields(raw["source"], {
        "venue", "api_version", "kind", "price_kind", "url", "retrieved_at",
    })
    source = FuturesSource(source_raw["price_kind"], parse_time(source_raw["retrieved_at"]))
    if source_raw != source.record():
        raise ValueError("unsupported futures source identity")
    rows = raw["candles"]
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_BARS:
        raise ValueError("candle count outside resource bounds")
    candles = []
    for value in rows:
        row = fields(value, {"symbol", "open_time", "close_time", "open", "high", "low", "close"})
        candles.append(Candle(
            row["symbol"], parse_time(row["open_time"], aligned=True),
            parse_time(row["close_time"], aligned=True),
            *(price(row[name]) for name in ("open", "high", "low", "close")),
        ))
    coverage = fields(raw["coverage"], {
        "requested_start", "requested_end", "actual_start", "actual_end", "complete",
        "missing_leading_bars", "missing_trailing_bars",
    })
    if coverage["complete"] is not None and type(coverage["complete"]) is not bool:
        raise ValueError("coverage complete must be boolean or null")
    for key in ("missing_leading_bars", "missing_trailing_bars"):
        if coverage[key] is not None and (type(coverage[key]) is not int or coverage[key] < 0):
            raise ValueError("coverage missing counts must be nonnegative integers or null")
    requested_start = (None if coverage["requested_start"] is None else
                       parse_time(coverage["requested_start"], aligned=True))
    requested_end = (None if coverage["requested_end"] is None else
                     parse_time(coverage["requested_end"], aligned=True))
    result = make_futures_snapshot(raw["symbol"], raw["price_kind"], tuple(candles), source,
                                   requested_start=requested_start, requested_end=requested_end)
    if coverage != result.coverage.record() or raw["data_digest"] != result.data_digest:
        raise ValueError("futures snapshot digest/coverage mismatch")
    return result


def funding_rate(value: object) -> Decimal:
    """Signed fractional rate, bounded independently of the positive price parser."""
    if not isinstance(value, str) or len(value) > 64 or not re.fullmatch(
        r"[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d{1,3})?", value,
    ):
        raise ValueError("bounded signed Decimal funding rate required")
    result = Decimal(value)
    price(str(result.copy_abs()), zero=True)
    if not Decimal("-1") <= result <= Decimal("1"):
        raise ValueError("funding rate outside [-1,1]")
    return result


def _rate_string(value: Decimal) -> str:
    funding_rate(str(value))
    if value == 0:
        return "0"
    text = format(value, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


@dataclass(frozen=True)
class FundingEvent:
    timestamp: datetime
    rate: Decimal

    def __post_init__(self):
        utc_time(self.timestamp)
        if not isinstance(self.rate, Decimal):
            raise ValueError("funding rate must use Decimal")
        funding_rate(str(self.rate))

    def record(self) -> dict:
        return {"timestamp": iso(self.timestamp), "rate": _rate_string(self.rate)}


@dataclass(frozen=True)
class FundingSnapshot:
    """Observed events only: neither an expected cadence nor completeness proof."""
    symbol: str
    retrieved_at: datetime
    requested_start: datetime
    requested_end: datetime
    events: tuple[FundingEvent, ...]
    schema_version: str = FUNDING_SCHEMA_VERSION
    market: str = MARKET
    data_digest: str = field(init=False)

    def __post_init__(self):
        _symbol(self.symbol)
        if self.schema_version != FUNDING_SCHEMA_VERSION or self.market != MARKET:
            raise ValueError("unsupported funding snapshot contract")
        _retrieved(self.retrieved_at)
        utc_time(self.requested_start)
        utc_time(self.requested_end)
        if not self.requested_start < self.requested_end <= self.retrieved_at:
            raise ValueError("invalid/future funding window")
        if not isinstance(self.events, tuple) or len(self.events) > MAX_FUNDING_EVENTS:
            raise ValueError("funding snapshot needs 0..10000 immutable events")
        for index, event in enumerate(self.events):
            if not isinstance(event, FundingEvent):
                raise ValueError("immutable funding events required")
            if not self.requested_start <= event.timestamp < self.requested_end:
                raise ValueError("funding event outside requested window")
            if index and self.events[index - 1].timestamp >= event.timestamp:
                raise ValueError("duplicate/out-of-order funding events")
        object.__setattr__(self, "data_digest", _digest(self.digest_record()))

    def source_record(self, *, retrieval: bool = True) -> dict:
        result = {
            "venue": "bitget", "api_version": "2",
            "kind": "public-funding-history", "url": FUNDING_ENDPOINT,
        }
        if retrieval:
            result["retrieved_at"] = iso(self.retrieved_at)
        return result

    def digest_record(self) -> dict:
        return {
            "schema_version": self.schema_version, "market": self.market, "symbol": self.symbol,
            "source": self.source_record(retrieval=False),
            "requested_start": iso(self.requested_start), "requested_end": iso(self.requested_end),
            "events": [event.record() for event in self.events],
        }

    def record(self) -> dict:
        return {**self.digest_record(), "source": self.source_record(),
                "data_digest": self.data_digest}


def dump_funding_snapshot(snapshot: FundingSnapshot) -> str:
    if not isinstance(snapshot, FundingSnapshot):
        raise ValueError("funding snapshot required")
    return canonical(snapshot.record())


def load_funding_snapshot(value: str | bytes) -> FundingSnapshot:
    raw = fields(decode_json(value), {
        "schema_version", "market", "symbol", "source", "requested_start",
        "requested_end", "events", "data_digest",
    })
    if raw["schema_version"] != FUNDING_SCHEMA_VERSION or raw["market"] != MARKET:
        raise ValueError("unsupported funding schema/market")
    source = fields(raw["source"], {"venue", "api_version", "kind", "url", "retrieved_at"})
    rows = raw["events"]
    if not isinstance(rows, list) or len(rows) > MAX_FUNDING_EVENTS:
        raise ValueError("funding count outside resource bounds")
    events = []
    for value in rows:
        row = fields(value, {"timestamp", "rate"})
        events.append(FundingEvent(parse_time(row["timestamp"]), funding_rate(row["rate"])))
    result = FundingSnapshot(
        raw["symbol"], parse_time(source["retrieved_at"]), parse_time(raw["requested_start"]),
        parse_time(raw["requested_end"]), tuple(events),
    )
    if source != result.source_record() or raw["data_digest"] != result.data_digest:
        raise ValueError("funding source/digest mismatch")
    return result
