"""Bounded unsigned Classic V2 futures H4 history; no account/execution caller."""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable
from urllib.parse import urlencode
from urllib.request import Request, build_opener

from investalo_trading import Candle
from .bitget import EPOCH, _NoRedirect, milliseconds
from .futures_snapshot import (
    ENDPOINTS, SYMBOLS, FuturesSnapshot, FuturesSource, candle_symbol,
    make_futures_snapshot,
)
from .snapshot import H4, MAX_BARS, decode_json, price, utc_time

PAGE_LIMIT = 200
MAX_RESPONSE_BYTES = 256 * 1024
MAX_PAGES = MAX_BARS // PAGE_LIMIT + 2
FetchJSON = Callable[[str], object]


def fetch_futures_json(url: str) -> object:
    if not isinstance(url, str) or not any(url.startswith(endpoint + "?")
                                            for endpoint in ENDPOINTS.values()):
        raise ValueError("only fixed public futures history endpoints allowed")
    request = Request(url, headers={"Accept": "application/json",
                                   "User-Agent": "Investalo-futures-history/1"})
    with build_opener(_NoRedirect()).open(request, timeout=10) as response:
        payload = response.read(MAX_RESPONSE_BYTES + 1)
    return decode_json(payload, max_bytes=MAX_RESPONSE_BYTES)


def _rows(payload: object, symbol: str, price_kind: str) -> tuple[Candle, ...]:
    if not isinstance(payload, dict) or payload.get("code") != "00000":
        raise ValueError("Bitget did not confirm successful futures history")
    rows = payload.get("data")
    if not isinstance(rows, list) or len(rows) > PAGE_LIMIT + 1:
        raise ValueError("unexpected futures page count")
    result = []
    for row in rows:
        if not isinstance(row, list) or len(row) != 7:
            raise ValueError("unexpected futures candle row")
        stamp = row[0]
        if (not isinstance(stamp, str) or not stamp.isascii()
                or not stamp.isdigit() or len(stamp) > 15):
            raise ValueError("bounded Unix millisecond text required")
        try:
            opened = EPOCH + timedelta(milliseconds=int(stamp))
        except OverflowError:
            raise ValueError("futures timestamp outside bounds") from None
        utc_time(opened, aligned=True)
        price(row[5], zero=True)
        price(row[6], zero=True)
        result.append(Candle(candle_symbol(symbol, price_kind), opened, opened + H4,
                             *(price(row[index]) for index in (1, 2, 3, 4))))
    result.sort(key=lambda bar: bar.open_time)
    if len({bar.open_time for bar in result}) != len(result):
        raise ValueError("duplicate futures candle within page")
    return tuple(result)


@dataclass(frozen=True)
class BitgetFuturesHistoryAdapter:
    fetch_json: FetchJSON = fetch_futures_json
    page_delay_seconds: float = 0.1
    sleep: Callable[[float], None] = time.sleep

    def __post_init__(self):
        if (type(self.page_delay_seconds) not in (int, float)
                or not 0.05 <= self.page_delay_seconds <= 10):
            raise ValueError("public request pace must remain below 20/sec/IP")
        if not callable(self.fetch_json) or not callable(self.sleep):
            raise ValueError("callable transport and pacing required")

    def fetch_history(self, symbol: str, price_kind: str, *, start: datetime,
                      end: datetime, retrieved_at: datetime | None = None) -> FuturesSnapshot:
        if symbol not in SYMBOLS or price_kind not in ENDPOINTS:
            raise ValueError("unsupported futures symbol/price kind")
        start, end = utc_time(start, aligned=True), utc_time(end, aligned=True)
        retrieved_at = utc_time(retrieved_at or datetime.now(timezone.utc))
        if retrieved_at > datetime.now(timezone.utc) or end > retrieved_at:
            raise ValueError("future/unclosed requested futures history")
        if not start < end or (end - start) // H4 > MAX_BARS:
            raise ValueError("request must contain 1..10000 H4 intervals")
        collected = {}
        cursor = end
        for page_number in range(MAX_PAGES):
            if cursor <= start:
                break
            if page_number:
                self.sleep(self.page_delay_seconds)
            page_start = max(start, cursor - H4 * PAGE_LIMIT)
            url = ENDPOINTS[price_kind] + "?" + urlencode({
                "symbol": symbol, "productType": "USDT-FUTURES", "granularity": "4H",
                "limit": str(PAGE_LIMIT), "startTime": str(milliseconds(page_start)),
                "endTime": str(milliseconds(cursor)),
            })
            rows = _rows(self.fetch_json(url), symbol, price_kind)
            if not rows:
                break
            # One earlier boundary is permitted by interval rounding; an arbitrary
            # older response must not skip a requested interior window.
            if any(bar.open_time < page_start - H4 or bar.open_time >= cursor
                   or bar.close_time > retrieved_at for bar in rows):
                raise ValueError("futures response outside page/closed bounds")
            for bar in rows:
                if start <= bar.open_time and bar.close_time <= end:
                    if bar.open_time in collected:
                        raise ValueError("duplicate futures candle across pages")
                    collected[bar.open_time] = bar
            if len(collected) > MAX_BARS:
                raise ValueError("futures history exceeds resource bound")
            cursor = rows[0].open_time
        else:
            raise ValueError("futures history exceeds request bound")
        candles = tuple(collected[key] for key in sorted(collected))
        return make_futures_snapshot(
            symbol, price_kind, candles, FuturesSource(price_kind, retrieved_at),
            requested_start=start, requested_end=end,
        )
