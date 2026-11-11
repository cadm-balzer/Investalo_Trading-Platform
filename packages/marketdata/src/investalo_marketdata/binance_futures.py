"""Separate native Binance research data. No Bitget identity or execution."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import time
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, build_opener

from investalo_trading import Candle
from .bitget import EPOCH, _NoRedirect, milliseconds
from .futures_snapshot import funding_rate
from .snapshot import (
    H4, MAX_BARS, canonical, decimal_string, decode_json, fields, iso,
    parse_time, price, utc_time,
)

VERSION = "binance-usdt-futures-research/1"
SYMBOLS = ("BTCUSDT", "ETHUSDT")
ENDPOINTS = {
    "trade": "https://fapi.binance.com/fapi/v1/klines",
    "mark": "https://fapi.binance.com/fapi/v1/markPriceKlines",
    "index": "https://fapi.binance.com/fapi/v1/indexPriceKlines",
    "funding": "https://fapi.binance.com/fapi/v1/fundingRate",
}
PAGE_LIMIT = 1000
MAX_PAGES = 21
MAX_RESPONSE_BYTES = 512 * 1024


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def stamp(value):
    if type(value) is not int or not 0 <= value <= 253402300799999:
        raise ValueError("bounded integer millisecond timestamp required")
    return EPOCH + timedelta(milliseconds=value)


def request_url(symbol, kind, start_ms, end_ms):
    if symbol not in SYMBOLS or kind not in ENDPOINTS:
        raise ValueError("unsupported Binance research stream")
    stamp(start_ms)
    stamp(end_ms)
    max_span = (MAX_BARS if kind == "funding" else PAGE_LIMIT) * 14_400_000
    if start_ms > end_ms or end_ms - start_ms + 1 > max_span:
        raise ValueError("invalid or excessive inclusive page window")
    params = {"pair" if kind == "index" else "symbol": symbol}
    if kind != "funding":
        params["interval"] = "4h"
    params.update(startTime=str(start_ms), endTime=str(end_ms), limit=str(PAGE_LIMIT))
    return ENDPOINTS[kind] + "?" + urlencode(params)


def fetch_binance_json(url):
    """Exact public GET URLs only; no redirects, authentication or retries."""
    if not isinstance(url, str) or len(url) > 512:
        raise ValueError("bounded public URL required")
    parsed = urlsplit(url)
    endpoint = parsed.scheme + "://" + parsed.netloc + parsed.path
    kind = next((key for key, value in ENDPOINTS.items() if value == endpoint), None)
    try:
        params = parse_qs(parsed.query, strict_parsing=True)
        symbol = params["pair" if kind == "index" else "symbol"][0]
        expected = request_url(symbol, kind, int(params["startTime"][0]), int(params["endTime"][0]))
    except (KeyError, TypeError, ValueError):
        raise ValueError("only fixed public Binance research URLs allowed") from None
    if url != expected:
        raise ValueError("only canonical bounded public queries allowed")
    request = Request(url, headers={"Accept": "application/json",
                                   "User-Agent": "Investalo-binance-research/1"})
    with build_opener(_NoRedirect()).open(request, timeout=15) as response:
        payload = response.read(MAX_RESPONSE_BYTES + 1)
    return decode_json(payload, max_bytes=MAX_RESPONSE_BYTES)


@dataclass(frozen=True)
class FundingObservation:
    timestamp: datetime
    rate: Decimal
    mark_price: Decimal | None
    rate_type: str | None

    def __post_init__(self):
        utc_time(self.timestamp)
        if self.timestamp.microsecond % 1000 or not isinstance(self.rate, Decimal):
            raise ValueError("native millisecond time and Decimal rate required")
        funding_rate(str(self.rate))
        if self.mark_price is not None:
            if not isinstance(self.mark_price, Decimal):
                raise ValueError("native mark price must be Decimal")
            price(str(self.mark_price))
        if self.rate_type not in (None, "Regular", "Special"):
            raise ValueError("unsupported native funding rate type")

    def record(self):
        return {"timestamp": iso(self.timestamp), "rate": str(self.rate),
                "mark_price": None if self.mark_price is None else decimal_string(self.mark_price),
                "rate_type": self.rate_type}


def candle_record(bar):
    return {"symbol": bar.symbol, "open_time": iso(bar.open_time), "close_time": iso(bar.close_time),
            **{key: decimal_string(getattr(bar, key)) for key in ("open", "high", "low", "close")}}


@dataclass(frozen=True)
class BinanceSnapshot:
    symbol: str
    kind: str
    start: datetime
    end: datetime
    retrieved_at: datetime
    rows: tuple[Candle | FundingObservation, ...]

    def __post_init__(self):
        if self.symbol not in SYMBOLS or self.kind not in ENDPOINTS:
            raise ValueError("unsupported Binance research stream")
        utc_time(self.start, aligned=True)
        utc_time(self.end, aligned=True)
        utc_time(self.retrieved_at)
        if (not self.start < self.end <= self.retrieved_at <= datetime.now(timezone.utc)
                or (self.end - self.start) // H4 > MAX_BARS):
            raise ValueError("closed bounded research window required")
        if not isinstance(self.rows, tuple) or len(self.rows) > MAX_BARS:
            raise ValueError("bounded immutable rows required")
        previous = None
        for row in self.rows:
            if self.kind == "funding":
                if not isinstance(row, FundingObservation):
                    raise ValueError("native funding observation required")
                row.__post_init__()
                at = row.timestamp
                if previous is not None and at <= previous:
                    raise ValueError("funding must be unique and ascending")
            else:
                if not isinstance(row, Candle) or row.symbol != f"BINANCE:{self.symbol}:USDT-M:{self.kind}":
                    raise ValueError("native Binance candle identity required")
                at = utc_time(row.open_time, aligned=True)
                if row.close_time != at + H4 or previous is not None and at != previous + H4:
                    raise ValueError("closed contiguous H4 candles required")
                for key in ("open", "high", "low", "close"):
                    if not isinstance(getattr(row, key), Decimal):
                        raise ValueError("Decimal OHLC required")
                    price(str(getattr(row, key)))
                if row.high < max(row.open, row.close, row.low) or row.low > min(row.open, row.close):
                    raise ValueError("inconsistent OHLC")
            if not self.start <= at < self.end:
                raise ValueError("row outside exact research window")
            previous = at
        if self.kind != "funding" and (
            not self.rows or self.rows[0].open_time != self.start or self.rows[-1].close_time != self.end
        ):
            raise ValueError("incomplete requested H4 coverage")

    def data_record(self):
        return {
            "schema_version": VERSION, "venue": "binance", "market": "USDT-M-perpetual",
            "symbol": self.symbol, "kind": self.kind, "url": ENDPOINTS[self.kind],
            "start": iso(self.start), "end_exclusive": iso(self.end),
            "rows": [row.record() if self.kind == "funding" else candle_record(row) for row in self.rows],
        }

    @property
    def data_digest(self):
        return digest(self.data_record())

    def record(self):
        return {**self.data_record(), "retrieved_at": iso(self.retrieved_at), "data_digest": self.data_digest}


def load_binance_snapshot(text):
    raw = fields(decode_json(text), {
        "schema_version", "venue", "market", "symbol", "kind", "url", "start", "end_exclusive",
        "rows", "retrieved_at", "data_digest",
    })
    if not isinstance(raw["rows"], list) or len(raw["rows"]) > MAX_BARS:
        raise ValueError("bounded rows required")
    rows = []
    for value in raw["rows"]:
        if raw["kind"] == "funding":
            row = fields(value, {"timestamp", "rate", "mark_price", "rate_type"})
            rows.append(FundingObservation(parse_time(row["timestamp"]), funding_rate(row["rate"]),
                                           None if row["mark_price"] is None else price(row["mark_price"]),
                                           row["rate_type"]))
        else:
            row = fields(value, {"symbol", "open_time", "close_time", "open", "high", "low", "close"})
            rows.append(Candle(row["symbol"], parse_time(row["open_time"]), parse_time(row["close_time"]),
                               *(price(row[key]) for key in ("open", "high", "low", "close"))))
    result = BinanceSnapshot(raw["symbol"], raw["kind"], parse_time(raw["start"]),
                             parse_time(raw["end_exclusive"]), parse_time(raw["retrieved_at"]), tuple(rows))
    if raw != result.record():
        raise ValueError("Binance source identity/digest mismatch")
    return result


def parse_rows(payload, symbol, kind):
    if not isinstance(payload, list) or len(payload) > PAGE_LIMIT:
        raise ValueError("unexpected Binance public page")
    rows = []
    for value in payload:
        if kind == "funding":
            if not isinstance(value, dict) or set(value) not in (
                {"symbol", "fundingTime", "fundingRate", "markPrice"},
                {"symbol", "fundingTime", "fundingRate", "markPrice", "rateType"},
            ) or value["symbol"] != symbol:
                raise ValueError("unexpected native funding row")
            rows.append(FundingObservation(
                stamp(value["fundingTime"]), funding_rate(value["fundingRate"]),
                None if value["markPrice"] == "" else price(value["markPrice"]), value.get("rateType"),
            ))
        else:
            if not isinstance(value, list) or len(value) != 12:
                raise ValueError("unexpected native kline row")
            opened = stamp(value[0])
            utc_time(opened, aligned=True)
            if stamp(value[6]) != opened + H4 - timedelta(milliseconds=1):
                raise ValueError("native inclusive kline close mismatch")
            rows.append(Candle(f"BINANCE:{symbol}:USDT-M:{kind}", opened, opened + H4,
                               *(price(value[index]) for index in (1, 2, 3, 4))))
    times = [row.timestamp if kind == "funding" else row.open_time for row in rows]
    if any(a >= b for a, b in zip(times, times[1:])):
        raise ValueError("duplicate or nonascending native page")
    return tuple(rows)


@dataclass(frozen=True)
class BinanceHistoryAdapter:
    fetch_json: object = fetch_binance_json
    sleep: object = time.sleep
    page_delay_seconds: float = 0.2

    def __post_init__(self):
        if (not callable(self.fetch_json) or not callable(self.sleep)
                or type(self.page_delay_seconds) not in (int, float)
                or not 0.1 <= self.page_delay_seconds <= 10):
            raise ValueError("callable transport and bounded pace required")

    def fetch_history(self, symbol, kind, *, start, end, retrieved_at):
        # Validate before IO, without admitting an incomplete candle artifact.
        BinanceSnapshot(symbol, "funding", start, end, retrieved_at, ())
        first_stop = end if kind == "funding" else min(end, start + H4 * PAGE_LIMIT)
        request_url(symbol, kind, milliseconds(start), milliseconds(first_stop) - 1)
        cursor, stop, rows, pages = milliseconds(start), milliseconds(end), [], []
        for page_number in range(MAX_PAGES):
            if cursor >= stop:
                break
            if page_number:
                self.sleep(self.page_delay_seconds)
            page_stop = stop if kind == "funding" else min(stop, cursor + PAGE_LIMIT * 14_400_000)
            url = request_url(symbol, kind, cursor, page_stop - 1)
            payload = self.fetch_json(url)
            batch = parse_rows(payload, symbol, kind)
            pages.append({"url": url, "response_digest": digest(payload), "rows": len(batch)})
            times = [milliseconds(row.timestamp if kind == "funding" else row.open_time) for row in batch]
            if any(not cursor <= at < page_stop for at in times):
                raise ValueError("native response outside requested page")
            if kind == "funding":
                if not batch:
                    break
                cursor = times[-1] + 1  # preserve native offsets; never round settlements
            else:
                if len(batch) != (page_stop - cursor) // 14_400_000:
                    raise ValueError("missing requested native H4 candles")
                cursor = page_stop
            rows.extend(batch)
            if len(rows) > MAX_BARS:
                raise ValueError("native row resource bound exceeded")
        else:
            raise ValueError("native pagination bound exhausted")
        return BinanceSnapshot(symbol, kind, start, end, retrieved_at, tuple(rows)), tuple(pages)


def funding_diagnostics(snapshot):
    """Declared 8h bucket audit only; original timestamps remain authoritative."""
    if not isinstance(snapshot, BinanceSnapshot) or snapshot.kind != "funding":
        raise ValueError("native Binance funding snapshot required")
    span_ms = 28_800_000
    if milliseconds(snapshot.start) % span_ms or milliseconds(snapshot.end) % span_ms:
        raise ValueError("declared 8h diagnostic requires aligned window boundaries")
    expected = set(range(milliseconds(snapshot.start), milliseconds(snapshot.end), span_ms))
    buckets = [milliseconds(row.timestamp) // span_ms * span_ms for row in snapshot.rows]
    observed = set(buckets)
    return {
        "declared_interval_hours": 8, "expected_buckets": len(expected), "observed_events": len(buckets),
        "missing_buckets": len(expected - observed), "unexpected_buckets": len(observed - expected),
        "duplicate_buckets": len(buckets) - len(observed),
        "max_native_offset_ms": max((milliseconds(row.timestamp) % span_ms for row in snapshot.rows), default=None),
        "missing_native_mark_prices": sum(row.mark_price is None for row in snapshot.rows),
        "historical_schedule_verified": False,
    }
