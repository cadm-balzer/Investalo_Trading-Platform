"""Native funding + minute mark evidence; no exact broker-settlement claim."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import time
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, build_opener

from investalo_trading.futures_paper import PaperFunding
from investalo_trading.snapshot import primitive

from .bitget import _NoRedirect, milliseconds
from .futures_paper_feed import (
    MAX_BYTES, ORIGIN, PATHS, SYMBOLS, NativeFunding, PublicRead,
    fetch_paper_source_json, request_url, stamp,
)
from .futures_snapshot import funding_rate
from .snapshot import canonical, decode_json, price, utc_time

VERSION = "bitget-classic-futures-settlement-evidence/1"
REFERENCE_POLICY = "native-minute-mark-open/1"
MINUTE = timedelta(minutes=1)


def minute_time(value):
    value = utc_time(value)
    if value.second or value.microsecond:
        raise ValueError("exact native minute boundary required; never round settlement time")
    return value


def mark_url(symbol, settled_at):
    settled_at = minute_time(settled_at)
    if symbol not in SYMBOLS:
        raise ValueError("fixed calibrated Classic candidate required")
    return ORIGIN + PATHS["mark"] + "?" + urlencode({
        "productType": "USDT-FUTURES", "symbol": symbol, "granularity": "1m", "limit": "3",
        "startTime": str(milliseconds(settled_at - MINUTE)),
        "endTime": str(milliseconds(settled_at + MINUTE)),
    })


def fetch_settlement_json(url):
    if type(url) is not str or len(url) > 512:
        raise ValueError("bounded canonical public URL required")
    if url in tuple(request_url(symbol, "funding") for symbol in SYMBOLS):
        return fetch_paper_source_json(url)
    try:
        parsed = urlsplit(url)
        query = parse_qs(parsed.query, strict_parsing=True)
        expected = mark_url(query["symbol"][0], stamp(query["startTime"][0]) + MINUTE)
    except (KeyError, TypeError, ValueError):
        raise ValueError("canonical public minute mark URL required") from None
    if url != expected:
        raise ValueError("canonical public minute mark URL required")
    request = Request(url, headers={"Accept": "application/json",
                                  "User-Agent": "Investalo-futures-settlement-evidence/1"})
    with build_opener(_NoRedirect()).open(request, timeout=5) as response:
        raw = response.read(MAX_BYTES + 1)
    return decode_json(raw, max_bytes=MAX_BYTES)


@dataclass(frozen=True)
class MarkMinute:
    symbol: str
    open_time: datetime
    close_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal

    def __post_init__(self):
        if (self.symbol not in tuple(f"BITGET:{s}:USDT-M:mark" for s in SYMBOLS)
                or minute_time(self.close_time) != minute_time(self.open_time) + MINUTE):
            raise ValueError("own native one-minute mark candle required")
        for value in (self.open, self.high, self.low, self.close):
            if type(value) is not Decimal:
                raise ValueError("typed mark minute prices required")
            price(str(value))
        if self.high < max(self.open, self.close, self.low) or self.low > min(self.open, self.close):
            raise ValueError("inconsistent mark minute OHLC")


@dataclass(frozen=True)
class SettlementEvidence:
    settled_at: datetime
    collected_at: datetime
    funding: tuple[NativeFunding, ...]
    minutes: tuple[MarkMinute, ...]
    reads: tuple[PublicRead, ...]

    def __post_init__(self):
        at = minute_time(self.settled_at)
        if utc_time(self.collected_at) < at + MINUTE:
            raise ValueError("closed settlement minute required")
        symbols = tuple("BITGET:" + symbol for symbol in SYMBOLS)
        if (type(self.funding) is not tuple or len(self.funding) != 5
                or any(type(row) is not NativeFunding for row in self.funding)
                or tuple(row.symbol for row in self.funding) != symbols
                or any(row.settled_at != at for row in self.funding)
                or type(self.minutes) is not tuple or len(self.minutes) != 5
                or any(type(row) is not MarkMinute for row in self.minutes)
                or tuple(row.symbol for row in self.minutes) != tuple(s + ":USDT-M:mark" for s in symbols)
                or any(row.open_time != at or row.close_time != at + MINUTE for row in self.minutes)
                or type(self.reads) is not tuple or len(self.reads) != 10
                or any(type(row) is not PublicRead for row in self.reads)):
            raise ValueError("complete canonical native funding/minute/response cohort required")
        for row in self.funding:
            PaperFunding(row.symbol, row.native_id, row.settled_at, row.rate)
        expected_urls = tuple(url for s in SYMBOLS for url in (request_url(s, "funding"), mark_url(s, at)))
        for row, url in zip(self.reads, expected_urls, strict=True):
            if (row.url != url or not utc_time(row.requested_at) <= utc_time(row.received_at) <= self.collected_at
                    or not timedelta(0) <= row.received_at - utc_time(row.server_at) <= timedelta(seconds=30)
                    or type(row.response_digest) is not str or len(row.response_digest) != 64
                    or any(c not in "0123456789abcdef" for c in row.response_digest)):
                raise ValueError("own native response clocks and SHA256 required")

    @property
    def data_digest(self):
        return hashlib.sha256(canonical(self.record()).encode()).hexdigest()

    def record(self):
        return {"schema_version": VERSION, "observation": primitive(self),
                "reference_policy": REFERENCE_POLICY, "reference_enabled": False,
                "exact_settlement_mark_available": False, "execution_enabled": False}


@dataclass(frozen=True)
class BitgetSettlementSource:
    fetch_json: object = fetch_settlement_json
    clock: object = lambda: datetime.now(timezone.utc)
    sleep: object = time.sleep
    pace_seconds: float = .1

    def __post_init__(self):
        if (not all(callable(c) for c in (self.fetch_json, self.clock, self.sleep))
                or type(self.pace_seconds) not in (int, float) or not .05 <= self.pace_seconds <= 1):
            raise ValueError("bounded paced transport and clock required")

    def collect(self, settled_at):
        settled_at, began = minute_time(settled_at), utc_time(self.clock())
        if not began - timedelta(hours=72) <= settled_at <= began - MINUTE:
            raise ValueError("closed native settlement minute within72h required")
        reads, funding, minutes = [], [], []

        def read(url):
            if reads:
                self.sleep(self.pace_seconds)
            before = utc_time(self.clock())
            if before < (reads[-1].received_at if reads else began):
                raise ValueError("source clock regressed")
            payload = self.fetch_json(url)
            after = utc_time(self.clock())
            raw = canonical(payload).encode()
            if after < before or after - began > timedelta(seconds=25) or len(raw) > MAX_BYTES:
                raise ValueError("bounded source collection clock/deadline required")
            if (type(payload) is not dict or payload.get("code") != "00000"
                    or type(payload.get("data")) is not list):
                raise ValueError("native successful public response required")
            server = stamp(payload.get("requestTime"), integer=True)
            if not timedelta(0) <= after - server <= timedelta(seconds=30):
                raise ValueError("stale/future provider response clock")
            reads.append(PublicRead(url, before, after, server, hashlib.sha256(raw).hexdigest()))
            return payload["data"], server

        for symbol in SYMBOLS:
            rows, server = read(request_url(symbol, "funding"))
            if not 1 <= len(rows) <= 100:
                raise ValueError("bounded nonempty native funding history required")
            last, selected = None, None
            for row in rows:
                if (type(row) is not dict or set(row) != {"symbol", "fundingTime", "fundingRate"}
                        or row["symbol"] != symbol):
                    raise ValueError("own native funding fields required")
                at, rate = stamp(row["fundingTime"]), funding_rate(row["fundingRate"])
                if at > server or last is not None and at >= last:
                    raise ValueError("duplicate, unsorted or future native funding")
                last = at
                if at == settled_at:
                    selected = NativeFunding("BITGET:" + symbol, f"BITGET:{symbol}:{row['fundingTime']}", at, rate)
            if selected is None:
                raise ValueError("exact native settlement rate not yet present")
            funding.append(selected)
            rows, server = read(mark_url(symbol, settled_at))
            if not 1 <= len(rows) <= 3:
                raise ValueError("bounded minute mark window required")
            selected, seen = None, set()
            for row in rows:
                if type(row) is not list or len(row) != 7:
                    raise ValueError("native seven-field minute mark row required")
                opened = minute_time(stamp(row[0]))
                if opened in seen or not settled_at - MINUTE <= opened <= settled_at + MINUTE:
                    raise ValueError("duplicate or out-of-window native mark minute")
                seen.add(opened)
                price(row[5], zero=True)
                price(row[6], zero=True)
                candle = MarkMinute(f"BITGET:{symbol}:USDT-M:mark", opened, opened + MINUTE,
                                        *(price(row[i]) for i in (1, 2, 3, 4)))
                if opened == settled_at:
                    if candle.close_time > server:
                        raise ValueError("unfinished native settlement mark minute")
                    selected = candle
            if selected is None:
                raise ValueError("exact native settlement minute missing")
            minutes.append(selected)
        collected = utc_time(self.clock())
        if collected < reads[-1].received_at or collected - began > timedelta(seconds=25):
            raise ValueError("bounded monotonic collection required")
        return SettlementEvidence(settled_at, collected, tuple(funding), tuple(minutes), tuple(reads))
