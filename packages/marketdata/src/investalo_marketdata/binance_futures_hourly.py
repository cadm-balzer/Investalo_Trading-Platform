"""Own bounded H1/Funding source for the capital profile; legacy H4 unchanged."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import time
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, build_opener

from investalo_trading.timeframe_research import ResearchCandle
from .binance_futures import (
    ENDPOINTS, MAX_RESPONSE_BYTES, PAGE_LIMIT, FundingObservation, candle_record,
    digest, parse_rows as parse_legacy_rows, stamp,
)
from .bitget import _NoRedirect, milliseconds
from .futures_snapshot import funding_rate
from .snapshot import decode_json, fields, iso, parse_time, price, utc_time

VERSION = "binance-usdt-futures-hourly/1"
SYMBOLS = ("BNBUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT")
KINDS = ("trade", "mark", "funding")
H1 = timedelta(hours=1)
HOUR_MS = 3_600_000
MAX_HOURS = 30_000
MAX_FUNDING = 10_000
MAX_PAGES = 40


def hour_time(value):
    value = utc_time(value)
    if any((value.minute, value.second, value.microsecond)):
        raise ValueError("exact UTC hour required")
    return value


def request_url(symbol, kind, start_ms, end_ms):
    if symbol not in SYMBOLS or kind not in KINDS:
        raise ValueError("unsupported native hourly stream")
    stamp(start_ms)
    stamp(end_ms)
    span = MAX_HOURS if kind == "funding" else PAGE_LIMIT
    if start_ms > end_ms or end_ms - start_ms + 1 > span * HOUR_MS:
        raise ValueError("invalid or excessive hourly page window")
    params = {"symbol": symbol}
    if kind != "funding":
        params["interval"] = "1h"
    params.update(startTime=str(start_ms), endTime=str(end_ms), limit=str(PAGE_LIMIT))
    return ENDPOINTS[kind] + "?" + urlencode(params)


def fetch_hourly_json(url):
    """Unsigned, canonical public GET only; no redirects or automatic retries."""
    if not isinstance(url, str) or len(url) > 512:
        raise ValueError("bounded public URL required")
    parsed = urlsplit(url)
    endpoint = parsed.scheme + "://" + parsed.netloc + parsed.path
    kind = next((key for key in KINDS if ENDPOINTS[key] == endpoint), None)
    try:
        params = parse_qs(parsed.query, strict_parsing=True)
        expected = request_url(params["symbol"][0], kind,
                               int(params["startTime"][0]), int(params["endTime"][0]))
    except (KeyError, TypeError, ValueError):
        raise ValueError("fixed public hourly URLs required") from None
    if url != expected:
        raise ValueError("canonical bounded hourly query required")
    request = Request(url, headers={"Accept": "application/json",
                                   "User-Agent": "Investalo-binance-hourly/1"})
    with build_opener(_NoRedirect()).open(request, timeout=15) as response:
        payload = response.read(MAX_RESPONSE_BYTES + 1)
    return decode_json(payload, max_bytes=MAX_RESPONSE_BYTES)


def parse_rows(payload, symbol, kind):
    if symbol not in SYMBOLS or kind not in KINDS:
        raise ValueError("unsupported native hourly stream")
    if kind == "funding":
        return parse_legacy_rows(payload, symbol, kind)
    if type(payload) is not list or len(payload) > PAGE_LIMIT:
        raise ValueError("bounded native hourly page required")
    rows = []
    for value in payload:
        if type(value) is not list or len(value) != 12:
            raise ValueError("native hourly kline row required")
        opened = hour_time(stamp(value[0]))
        if stamp(value[6]) != opened + H1 - timedelta(milliseconds=1):
            raise ValueError("native inclusive H1 close mismatch")
        rows.append(ResearchCandle(
            f"BINANCE:{symbol}:USDT-M:{kind}", opened, opened + H1,
            *(price(value[index]) for index in (1, 2, 3, 4))))
    if any(a.open_time >= b.open_time for a, b in zip(rows, rows[1:])):
        raise ValueError("duplicate or unsorted hourly page")
    return tuple(rows)


@dataclass(frozen=True)
class HourlySnapshot:
    symbol: str
    kind: str
    start: datetime
    end: datetime
    retrieved_at: datetime
    rows: tuple[ResearchCandle | FundingObservation, ...]

    def __post_init__(self):
        if self.symbol not in SYMBOLS or self.kind not in KINDS:
            raise ValueError("unsupported native hourly stream")
        hour_time(self.start)
        hour_time(self.end)
        utc_time(self.retrieved_at)
        if (not self.start < self.end <= self.retrieved_at <= datetime.now(timezone.utc)
                or (self.end - self.start) // H1 > MAX_HOURS):
            raise ValueError("closed bounded hourly window required")
        limit = MAX_FUNDING if self.kind == "funding" else MAX_HOURS
        if type(self.rows) is not tuple or len(self.rows) > limit:
            raise ValueError("bounded immutable hourly rows required")
        previous = None
        for row in self.rows:
            if self.kind == "funding":
                if type(row) is not FundingObservation:
                    raise ValueError("native funding observation required")
                row.__post_init__()
                at = row.timestamp
                if previous is not None and at <= previous:
                    raise ValueError("ascending unique funding required")
            else:
                if (type(row) is not ResearchCandle
                        or row.symbol != f"BINANCE:{self.symbol}:USDT-M:{self.kind}"):
                    raise ValueError("own native hourly identity required")
                row.__post_init__()
                at = hour_time(row.open_time)
                if row.close_time != at + H1 or previous is not None and at != previous + H1:
                    raise ValueError("contiguous exact H1 coverage required")
                for key in ("open", "high", "low", "close"):
                    price(str(getattr(row, key)))
            if not self.start <= at < self.end:
                raise ValueError("row outside hourly research window")
            previous = at
        if self.kind != "funding" and (
                not self.rows or self.rows[0].open_time != self.start
                or self.rows[-1].close_time != self.end):
            raise ValueError("incomplete requested hourly coverage")

    def data_record(self):
        return {
            "schema_version": VERSION, "venue": "binance", "market": "USDT-M-perpetual",
            "symbol": self.symbol, "kind": self.kind, "url": ENDPOINTS[self.kind],
            "interval": None if self.kind == "funding" else "1h",
            "start": iso(self.start), "end_exclusive": iso(self.end),
            "rows": [r.record() if self.kind == "funding" else candle_record(r) for r in self.rows],
        }

    @property
    def data_digest(self):
        return digest(self.data_record())

    def record(self):
        return {**self.data_record(), "retrieved_at": iso(self.retrieved_at), "data_digest": self.data_digest}


def load_hourly_snapshot(text):
    raw = fields(decode_json(text), {
        "schema_version", "venue", "market", "symbol", "kind", "url", "interval",
        "start", "end_exclusive", "rows", "retrieved_at", "data_digest",
    })
    limit = MAX_FUNDING if raw["kind"] == "funding" else MAX_HOURS
    if type(raw["rows"]) is not list or len(raw["rows"]) > limit:
        raise ValueError("bounded hourly source required")
    rows = []
    for value in raw["rows"]:
        if raw["kind"] == "funding":
            row = fields(value, {"timestamp", "rate", "mark_price", "rate_type"})
            rows.append(FundingObservation(
                parse_time(row["timestamp"]), funding_rate(row["rate"]),
                None if row["mark_price"] is None else price(row["mark_price"]), row["rate_type"]))
        else:
            row = fields(value, {"symbol", "open_time", "close_time", "open", "high", "low", "close"})
            rows.append(ResearchCandle(
                row["symbol"], parse_time(row["open_time"]), parse_time(row["close_time"]),
                *(price(row[key]) for key in ("open", "high", "low", "close"))))
    result = HourlySnapshot(raw["symbol"], raw["kind"], parse_time(raw["start"]),
                            parse_time(raw["end_exclusive"]), parse_time(raw["retrieved_at"]), tuple(rows))
    if raw != result.record():
        raise ValueError("hourly native source identity/digest mismatch")
    return result


@dataclass(frozen=True)
class HourlyHistoryAdapter:
    fetch_json: object = fetch_hourly_json
    sleep: object = time.sleep
    page_delay_seconds: float = 0.2

    def __post_init__(self):
        if (not callable(self.fetch_json) or not callable(self.sleep)
                or type(self.page_delay_seconds) not in (int, float)
                or not 0.1 <= self.page_delay_seconds <= 10):
            raise ValueError("callable transport and bounded pace required")

    def fetch_history(self, symbol, kind, *, start, end, retrieved_at):
        HourlySnapshot(symbol, "funding", start, end, retrieved_at, ())
        first_stop = end if kind == "funding" else min(end, start + H1 * PAGE_LIMIT)
        request_url(symbol, kind, milliseconds(start), milliseconds(first_stop) - 1)
        cursor, stop, rows, pages = milliseconds(start), milliseconds(end), [], []
        for page_number in range(MAX_PAGES):
            if cursor >= stop:
                break
            if page_number:
                self.sleep(self.page_delay_seconds)
            page_stop = stop if kind == "funding" else min(stop, cursor + PAGE_LIMIT * HOUR_MS)
            url = request_url(symbol, kind, cursor, page_stop - 1)
            payload = self.fetch_json(url)
            batch = parse_rows(payload, symbol, kind)
            pages.append({"url": url, "response_digest": digest(payload), "rows": len(batch)})
            times = [milliseconds(r.timestamp if kind == "funding" else r.open_time) for r in batch]
            if any(not cursor <= at < page_stop for at in times):
                raise ValueError("native response outside hourly page")
            if kind == "funding":
                if not batch:
                    break
                cursor = times[-1] + 1
            else:
                if len(batch) != (page_stop - cursor) // HOUR_MS:
                    raise ValueError("missing requested native H1 candles")
                cursor = page_stop
            rows.extend(batch)
            if len(rows) > (MAX_FUNDING if kind == "funding" else MAX_HOURS):
                raise ValueError("hourly row resource bound exceeded")
        else:
            raise ValueError("hourly pagination bound exhausted")
        return HourlySnapshot(symbol, kind, start, end, retrieved_at, tuple(rows)), tuple(pages)


def funding_diagnostics(snapshot):
    """Declared 8h calendar diagnostic; missing native marks stay missing."""
    if type(snapshot) is not HourlySnapshot or snapshot.kind != "funding":
        raise ValueError("native hourly-profile funding required")
    span = 28_800_000
    if milliseconds(snapshot.start) % span or milliseconds(snapshot.end) % span:
        raise ValueError("declared 8h diagnostic needs aligned boundaries")
    expected = set(range(milliseconds(snapshot.start), milliseconds(snapshot.end), span))
    buckets = [milliseconds(r.timestamp) // span * span for r in snapshot.rows]
    observed = set(buckets)
    return {
        "declared_interval_hours": 8, "expected_buckets": len(expected), "observed_events": len(buckets),
        "missing_buckets": len(expected - observed), "unexpected_buckets": len(observed - expected),
        "duplicate_buckets": len(buckets) - len(observed),
        "max_native_offset_ms": max((milliseconds(r.timestamp) % span for r in snapshot.rows), default=None),
        "missing_native_mark_prices": sum(r.mark_price is None for r in snapshot.rows),
        "historical_schedule_verified": False,
    }
