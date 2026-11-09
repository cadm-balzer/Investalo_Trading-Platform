"""Public, unsigned Bitget SPOT quotes and bounded closed-H4 windows."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, build_opener

from investalo_trading import Candle, Quote
from .bitget import EPOCH, MAX_RESPONSE_BYTES, _NoRedirect, _rows, milliseconds
from .snapshot import H4, decode_json, price, utc_time

ORIGIN = "https://api.bitget.com"
PATHS = ("/api/v3/market/tickers", "/api/v3/market/candles")
SYMBOLS = ("BTCUSDT", "ETHUSDT")


def fetch_feed_json(url: str) -> object:
    target = urlsplit(url)
    if (target.scheme != "https" or target.netloc != "api.bitget.com"
            or target.path not in PATHS or target.fragment):
        raise ValueError("Only fixed public feed endpoints permitted")
    request = Request(url, headers={"Accept": "application/json",
                                   "User-Agent": "Investalo-paper-feed/1"})
    with build_opener(_NoRedirect()).open(request, timeout=5) as response:
        payload = response.read(MAX_RESPONSE_BYTES + 1)
    return decode_json(payload, max_bytes=MAX_RESPONSE_BYTES)


def boundary(now: datetime) -> datetime:
    now = utc_time(now)
    return now.replace(hour=now.hour // 4 * 4, minute=0, second=0, microsecond=0)


def timestamp(value: object) -> datetime:
    if (not isinstance(value, str) or not value.isascii() or not value.isdigit()
            or not 1 <= len(value) <= 15):
        raise ValueError("Bounded millisecond timestamp required")
    try:
        return EPOCH + timedelta(milliseconds=int(value))
    except OverflowError:
        raise ValueError("Timestamp outside bounds") from None


@dataclass(frozen=True)
class BitgetPaperFeed:
    fetch_json: object = fetch_feed_json

    def quote(self, symbol: str, *, now: datetime | None = None) -> Quote:
        if symbol not in SYMBOLS:
            raise ValueError("Unsupported paper symbol")
        payload = self.fetch_json(ORIGIN + PATHS[0] + "?" + urlencode(
            {"category": "SPOT", "symbol": symbol}))
        if not isinstance(payload, dict) or payload.get("code") != "00000":
            raise ValueError("Public ticker unavailable")
        rows = payload.get("data")
        if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
            raise ValueError("Exactly one ticker required")
        row = rows[0]
        if row.get("symbol") != symbol or row.get("category") != "SPOT":
            raise ValueError("Ticker symbol/category differs")
        quote = Quote(symbol, timestamp(row.get("ts")),
                      price(row.get("bid1Price")), price(row.get("ask1Price")))
        received_at = utc_time(now or datetime.now(timezone.utc))
        if not 0 <= (received_at - quote.observed_at).total_seconds() <= 30:
            raise ValueError("Public ticker is not fresh")
        return quote

    def closed_bars(self, symbol: str, *, start: datetime, end: datetime,
                    now: datetime) -> tuple[Candle, ...]:
        if symbol not in SYMBOLS:
            raise ValueError("Unsupported paper symbol")
        start, end = utc_time(start, aligned=True), utc_time(end, aligned=True)
        if not start < end <= boundary(now) or (end - start) // H4 > 100:
            raise ValueError("Bounded closed H4 window required")
        payload = self.fetch_json(ORIGIN + PATHS[1] + "?" + urlencode({
            "category": "SPOT", "symbol": symbol, "interval": "4H",
            # Current-candles excludes startTime in observed SPOT responses.
            # Request one preceding interval; normalize only transport overlap.
            "type": "market", "limit": "100", "startTime": str(milliseconds(start-H4)),
            "endTime": str(milliseconds(end)),
        }))
        rows = _rows(payload, symbol)
        # The documented boundary rounding may add one preceding/current bar.
        if any(bar.open_time < start-H4 or bar.open_time > end for bar in rows):
            raise ValueError("Candle window outside bounds")
        closed = tuple(bar for bar in rows if start <= bar.open_time < end)
        expected = int((end - start) // H4)
        if (len(closed) != expected or
                any(bar.open_time != start + index*H4 for index, bar in enumerate(closed))):
            raise ValueError(f"Closed H4 coverage incomplete: expected={expected} received={len(closed)} "
                             f"first={closed[0].open_time.isoformat() if closed else 'none'} "
                             f"last={closed[-1].open_time.isoformat() if closed else 'none'}")
        return closed
