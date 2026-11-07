"""Public Bitget V3 SPOT history only, bounded backward pagination, no signing.

Official reference:
https://www.bitget.com/docs/catalog/market/market-data#get-klinecandlestick-history
V3 calls its interval `4H`, not `4Hutc`; actual UTC alignment is validated.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from investalo_trading import Candle
from .snapshot import (
    BITGET_URL, H4, MAX_BARS, SYMBOLS, DatasetSnapshot, SnapshotSource, decode_json,
    make_snapshot, price, utc_time,
)

MAX_RESPONSE_BYTES = 256 * 1024
PAGE_LIMIT = 100
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
FetchJSON = Callable[[str], object]


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("public data redirects are not permitted")


def fetch_public_json(url: str) -> object:
    # Adapter constructs the fixed origin/path. No credentials, cookies or API keys.
    if not url.startswith(BITGET_URL + "?"):
        raise ValueError("only the fixed public history endpoint is allowed")
    request = Request(url, headers={"Accept": "application/json",
                                   "User-Agent": "Investalo-marketdata/1"})
    with build_opener(_NoRedirect()).open(request, timeout=10) as response:
        payload = response.read(MAX_RESPONSE_BYTES + 1)
    return decode_json(payload, max_bytes=MAX_RESPONSE_BYTES)


def milliseconds(value: datetime) -> int:
    delta = utc_time(value) - EPOCH
    return delta.days * 86_400_000 + delta.seconds * 1000 + delta.microseconds // 1000


def _rows(payload: object, symbol: str) -> tuple[Candle, ...]:
    if not isinstance(payload, dict) or payload.get("code") != "00000":
        raise ValueError("Bitget did not confirm a successful response")
    rows = payload.get("data")
    # Documentation permits one additional interval due to endTime rounding.
    if not isinstance(rows, list) or len(rows) > PAGE_LIMIT + 1:
        raise ValueError("unexpected Bitget page count")
    candles = []
    for row in rows:
        if not isinstance(row, list) or len(row) != 7:
            raise ValueError("unexpected Bitget candle row")
        stamp = row[0]
        if not isinstance(stamp, str) or not stamp.isascii() or not stamp.isdigit() or len(stamp) > 15:
            raise ValueError("Bitget timestamp must be bounded Unix millisecond text")
        try:
            opened = EPOCH + timedelta(milliseconds=int(stamp))
        except OverflowError:
            raise ValueError("Bitget timestamp outside bounds") from None
        utc_time(opened, aligned=True)
        # Volumes remain provenance input, not fabricated Candle fields.
        price(row[5], zero=True)
        price(row[6], zero=True)
        candles.append(Candle(symbol, opened, opened + H4,
                              *(price(row[index]) for index in (1, 2, 3, 4))))
    candles.sort(key=lambda bar: bar.open_time)
    if len({bar.open_time for bar in candles}) != len(candles):
        raise ValueError("duplicate candle within Bitget response")
    return tuple(candles)


@dataclass(frozen=True)
class BitgetHistoryAdapter:
    fetch_json: FetchJSON = fetch_public_json
    page_delay_seconds: float = 0.1
    sleep: Callable[[float], None] = time.sleep

    def __post_init__(self):
        if not isinstance(self.page_delay_seconds, (int, float)) or not 0.05 <= self.page_delay_seconds <= 10:
            raise ValueError("public request pace must remain below documented 20/sec/IP")

    def fetch_history(self, symbol: str, *, start: datetime, end: datetime,
                      retrieved_at: datetime | None = None) -> DatasetSnapshot:
        if symbol not in SYMBOLS:
            raise ValueError("unsupported public spot symbol")
        start, end = utc_time(start, aligned=True), utc_time(end, aligned=True)
        retrieved_at = utc_time(retrieved_at or datetime.now(timezone.utc))
        if retrieved_at > datetime.now(timezone.utc) or end > retrieved_at:
            raise ValueError("future/unclosed requested history")
        if not start < end or (end - start) // H4 > MAX_BARS:
            raise ValueError("request must contain 1..10000 H4 intervals")
        collected: dict[datetime, Candle] = {}
        cursor = end
        for page_number in range(MAX_BARS // PAGE_LIMIT + 2):
            if cursor <= start:
                break
            if page_number:
                self.sleep(self.page_delay_seconds)
            # Both bounds fit inside 90 days. V3 floors timestamps to interval
            # boundaries: subtracting 1 ms skips a candle at every page boundary.
            # Exact UTC boundaries were verified with public V3 responses.
            page_start = max(start, cursor - H4 * PAGE_LIMIT)
            url = BITGET_URL + "?" + urlencode({
                "category": "SPOT", "symbol": symbol.replace("/", ""),
                "interval": "4H", "type": "market", "limit": str(PAGE_LIMIT),
                "startTime": str(milliseconds(page_start)),
                "endTime": str(milliseconds(cursor)),
            })
            rows = _rows(self.fetch_json(url), symbol)
            if not rows:
                break
            if any(bar.open_time >= cursor or bar.close_time > retrieved_at for bar in rows):
                raise ValueError("Bitget returned future/nonprogressing candles")
            for bar in rows:
                if start <= bar.open_time and bar.close_time <= end:
                    if bar.open_time in collected:
                        raise ValueError("duplicate candle across Bitget pages")
                    collected[bar.open_time] = bar
            if len(collected) > MAX_BARS:
                raise ValueError("history exceeds resource bound")
            earliest = rows[0].open_time
            if earliest >= cursor:
                raise ValueError("history pagination made no progress")
            cursor = earliest
        else:
            raise ValueError("history pagination exceeds request bound")
        # Only transport order is normalized. Interior gaps or conflicting prices
        # fail validation; leading/trailing availability shortfall is explicit.
        candles = tuple(collected[key] for key in sorted(collected))
        return make_snapshot(symbol, candles, SnapshotSource("bitget", "3", BITGET_URL, retrieved_at),
                             synthetic=False, requested_start=start, requested_end=end)
