"""Bounded public Binance spot H1 source for a separately identified study."""
from datetime import datetime, timedelta, timezone
import hashlib
import time
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, build_opener

from investalo_trading.timeframe_research import MAX_BARS, ResearchCandle
from .bitget import EPOCH, _NoRedirect, milliseconds
from .snapshot import canonical, decode_json, fields, iso, parse_time, price, utc_time

VERSION = "binance-spot-timeframe-source/1"
URL = "https://data-api.binance.vision/api/v3/klines"
SYMBOLS = ("BNBUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT")
HOUR = timedelta(hours=1)
PAGE_LIMIT = 1000
MAX_RESPONSE = 512 * 1024
MAX_BYTES = 8 * 1024 * 1024
KNOWN_MISSING = datetime(2023, 3, 24, 13, tzinfo=timezone.utc)


def sha(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def request_url(symbol, start, end):
    if symbol not in SYMBOLS:
        raise ValueError("unsupported research candidate")
    start, end = utc_time(start), utc_time(end)
    if (any((start.minute, start.second, start.microsecond, end.minute, end.second, end.microsecond))
            or not start < end or end - start > HOUR * PAGE_LIMIT):
        raise ValueError("bounded aligned hourly page required")
    return URL + "?" + urlencode({
        "symbol": symbol, "interval": "1h", "startTime": milliseconds(start),
        "endTime": milliseconds(end) - 1, "limit": PAGE_LIMIT,
    })


def fetch_json(url):
    if not isinstance(url, str) or len(url) > 512:
        raise ValueError("bounded URL required")
    parsed = urlsplit(url)
    if parsed.scheme + "://" + parsed.netloc + parsed.path != URL or parsed.fragment:
        raise ValueError("fixed public data endpoint required")
    try:
        query = parse_qs(parsed.query, strict_parsing=True)
        expected = request_url(
            query["symbol"][0], EPOCH + timedelta(milliseconds=int(query["startTime"][0])),
            EPOCH + timedelta(milliseconds=int(query["endTime"][0]) + 1),
        )
    except (ValueError, KeyError, OverflowError):
        raise ValueError("canonical public query required") from None
    if expected != url:
        raise ValueError("canonical public query required")
    request = Request(url, headers={"Accept": "application/json",
                                   "User-Agent": "Investalo-timeframe-research/1"})
    with build_opener(_NoRedirect()).open(request, timeout=15) as response:
        raw = response.read(MAX_RESPONSE + 1)
    return decode_json(raw, max_bytes=MAX_RESPONSE)


def record(bar):
    return {
        "symbol": bar.symbol, "open_time": iso(bar.open_time), "close_time": iso(bar.close_time),
        **{field: str(getattr(bar, field)) for field in ("open", "high", "low", "close")},
    }


def validate_history(symbol, bars, start, end):
    if (not start < end or end - start > HOUR * MAX_BARS
            or any((start.minute, start.second, start.microsecond,
                    end.minute, end.second, end.microsecond))):
        raise ValueError("bounded aligned hourly window required")
    expected = tuple(start + i * HOUR for i in range(int((end - start) / HOUR))
                     if start + i * HOUR != KNOWN_MISSING)
    if (symbol not in SYMBOLS or not bars or len(bars) > MAX_BARS
            or any(b.symbol != symbol or b.close_time - b.open_time != HOUR for b in bars)
            or bars[0].open_time != start or bars[-1].close_time != end
            or tuple(b.open_time for b in bars) != expected):
        raise ValueError("exact hourly window with only the declared native gap required")


def fetch_history(symbol, start, end, fetch=fetch_json, delay=time.sleep):
    start, end = utc_time(start), utc_time(end)
    if (not start < end or end - start > HOUR * MAX_BARS
            or end > datetime.now(timezone.utc)):
        raise ValueError("bounded closed research window required")
    cursor, bars, pages, irregular_closes = start, [], [], []
    while cursor < end:
        page_end = min(end, cursor + HOUR * PAGE_LIMIT)
        url = request_url(symbol, cursor, page_end)
        if pages:
            delay(0.1)
        payload = fetch(url)
        expected = tuple(cursor + i * HOUR for i in range(int((page_end - cursor) / HOUR))
                         if cursor + i * HOUR != KNOWN_MISSING)
        if type(payload) is not list or len(payload) != len(expected):
            raise ValueError("missing/extra hourly page rows; no gap repair")
        for index, row in enumerate(payload):
            opened = expected[index]
            if (type(row) is not list or len(row) != 12
                    or type(row[0]) is not int or row[0] != milliseconds(opened)
                    or type(row[6]) is not int):
                raise ValueError(f"unexpected native hourly candle at {iso(opened)}")
            if row[6] != milliseconds(opened + HOUR) - 1:
                # The preceding candle was closed early during the same
                # interruption. Preserve its native stamp; this entire H4
                # block is excluded before either performance run.
                if (opened != KNOWN_MISSING - HOUR
                        or not milliseconds(opened) <= row[6] < milliseconds(opened + HOUR) - 1):
                    raise ValueError(f"unexpected native close at {iso(opened)}: {row[6]}")
                irregular_closes.append({"open_time": iso(opened), "native_close_ms": row[6]})
            for field in (5, 7, 9, 10):
                price(row[field], zero=True)
            if type(row[8]) is not int or row[8] < 0:
                raise ValueError("unexpected trade count")
            bars.append(ResearchCandle(symbol, opened, opened + HOUR,
                                       *(price(row[i]) for i in (1, 2, 3, 4))))
        pages.append({
            "url": url, "rows": len(payload), "decoded_response_sha256": sha(payload),
            "observed_at": iso(datetime.now(timezone.utc)),
        })
        cursor = page_end
    bars = tuple(bars)
    validate_history(symbol, bars, start, end)
    snapshot = {
        "schema_version": VERSION, "venue": "binance", "market": "spot", "timeframe": "1h",
        "symbol": symbol, "start": iso(start), "end_exclusive": iso(end), "url": URL,
        "retrieved_at": iso(datetime.now(timezone.utc)), "candles": [record(b) for b in bars],
        "missing_intervals": [iso(KNOWN_MISSING)] if start <= KNOWN_MISSING < end else [],
        "irregular_native_closes": irregular_closes,
    }
    snapshot["data_digest"] = sha({k: v for k, v in snapshot.items() if k != "retrieved_at"})
    return snapshot, pages


def load_history(raw):
    value = decode_json(raw, max_bytes=MAX_BYTES)
    fields(value, {"schema_version", "venue", "market", "timeframe", "symbol", "start",
                   "end_exclusive", "url", "retrieved_at", "candles", "data_digest",
                   "missing_intervals", "irregular_native_closes"})
    if (value["schema_version"] != VERSION or value["venue"] != "binance"
            or value["market"] != "spot" or value["timeframe"] != "1h" or value["url"] != URL
            or type(value["candles"]) is not list or not 1 <= len(value["candles"]) <= MAX_BARS
            or value["data_digest"] != sha({k: v for k, v in value.items()
                                            if k not in ("retrieved_at", "data_digest")})):
        raise ValueError("hourly source identity/digest mismatch")
    bars = []
    for item in value["candles"]:
        fields(item, {"symbol", "open_time", "close_time", "open", "high", "low", "close"})
        bars.append(ResearchCandle(
            item["symbol"], parse_time(item["open_time"]), parse_time(item["close_time"]),
            *(price(item[k]) for k in ("open", "high", "low", "close")),
        ))
    start, end = parse_time(value["start"]), parse_time(value["end_exclusive"])
    retrieved = parse_time(value["retrieved_at"])
    if end > retrieved or retrieved > datetime.now(timezone.utc):
        raise ValueError("unclosed/future hourly data")
    if value["missing_intervals"] != ([iso(KNOWN_MISSING)] if start <= KNOWN_MISSING < end else []):
        raise ValueError("native gap disclosure mismatch")
    irregular = value["irregular_native_closes"]
    if type(irregular) is not list or len(irregular) > 1:
        raise ValueError("bounded native close evidence required")
    for item in irregular:
        fields(item, {"open_time", "native_close_ms"})
        opened, closed = parse_time(item["open_time"]), item["native_close_ms"]
        if (opened != KNOWN_MISSING - HOUR or not start <= opened < end
                or type(closed) is not int
                or not milliseconds(opened) <= closed < milliseconds(opened + HOUR) - 1):
            raise ValueError("unexpected native partial candle evidence")
    validate_history(value["symbol"], bars, start, end)
    return value, tuple(bars)
