"""Public Demo H1 observations using the strategy's Decimal/Wilder indicator.

This monitor has no credentials, account mutation or order authority. A closed
bar is current until the next H1 boundary; fetching it again does not advance RSI.
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import os
import ssl
import threading
import time
from urllib.parse import urlencode
from urllib.error import HTTPError
from urllib.request import Request, ProxyHandler, HTTPSHandler, build_opener

from . import parse
from .transport import ReadResponse, _NoRedirect
from investalo_trading.futures_signals import IndicatorParameters
from investalo_trading.indicators import advance
from investalo_trading.models import IndicatorState
from investalo_trading.timeframe_research import ResearchCandle

SYMBOLS = ("AVAXUSDT", "BNBUSDT", "BTCUSDT", "ETHUSDT", "LINKUSDT", "SOLUSDT", "XRPUSDT")
SCHEMA = "investalo-demo-signals/1"
H1 = timedelta(hours=1)
WARM_BARS = 300
MAX_BYTES = 256 * 1024
ORIGIN = "https://api.bitget.com"


def boundary(now):
    if type(now) is not datetime or now.tzinfo is None or now.utcoffset() != timedelta(0):
        raise ValueError("UTC observation time required")
    return now.replace(minute=0, second=0, microsecond=0)


def milliseconds(now):
    return int((now - parse.EPOCH) // timedelta(milliseconds=1))


def signal_url(symbol, end):
    if symbol not in SYMBOLS or end != boundary(end):
        raise ValueError("fixed Demo symbol and H1 boundary required")
    return ORIGIN + "/api/v2/mix/market/candles?" + urlencode({
        "symbol": symbol, "productType": "USDT-FUTURES", "granularity": "1H",
        "endTime": str(milliseconds(end) - 1), "limit": str(WARM_BARS + 1),
        "kLineType": "market",
    })


def public_demo_signals_get(symbol, end, *, timeout_seconds=3):
    """Fixed keyless GET, Demo header, bounded body, no redirect/proxy/retry."""
    if type(timeout_seconds) not in (float, int) or not .05 <= timeout_seconds <= 3:
        raise ValueError("bounded public request timeout required")
    request = Request(signal_url(symbol, end), headers={
        "Accept": "application/json", "paptrading": "1",
        "User-Agent": "Investalo-demo-h1-monitor/1",
    }, method="GET")
    tls = ssl.create_default_context()
    tls.minimum_version = ssl.TLSVersion.TLSv1_2
    try:
        with build_opener(ProxyHandler({}), HTTPSHandler(context=tls), _NoRedirect()).open(
                request, timeout=timeout_seconds) as response:
            body = response.read(MAX_BYTES + 1)
            if response.status != 200 or len(body) > MAX_BYTES:
                raise ValueError("bounded public candles required")
            return ReadResponse(response.status, body)
    except HTTPError as error:
        error.close()
        raise ValueError("public candles unavailable") from None


def signal_asset(response, symbol, *, end, received_at):
    """Reject gaps/duplicate bars and never consume the unfinished current H1."""
    if symbol not in SYMBOLS or end != boundary(end) or boundary(received_at) != end:
        raise ValueError("own current closed H1 window required")
    rows, server_at = parse.envelope(response)
    if (not timedelta(0) <= received_at - server_at <= timedelta(seconds=5)
            or type(rows) is not list or not WARM_BARS <= len(rows) <= WARM_BARS + 1):
        raise ValueError("fresh complete public H1 response required")
    bars, seen = [], set()
    for row in rows:
        if (type(row) is not list or len(row) != 7 or type(row[0]) is not str
                or not row[0].isascii() or not row[0].isdigit() or len(row[0]) > 15):
            raise ValueError("native H1 row required")
        opened = parse.EPOCH + timedelta(milliseconds=int(row[0]))
        if opened != boundary(opened) or opened in seen or opened > end:
            raise ValueError("aligned unique nonfuture H1 bars required")
        seen.add(opened)
        prices = tuple(parse.amount(value) for value in row[1:5])
        if any(p is None or p <= 0 for p in prices):
            raise ValueError("positive complete OHLC required")
        bar = ResearchCandle("BITGET:" + symbol, opened, opened + H1, *prices)
        for volume in row[5:]:
            if parse.amount(volume) is None:
                raise ValueError("native volume required")
        if bar.close_time <= end:
            bars.append(bar)
    bars.sort(key=lambda bar: bar.open_time)
    if len(bars) < WARM_BARS:
        raise ValueError("300 completed warmup bars required")
    bars = bars[-WARM_BARS:]
    expected_start = end - WARM_BARS * H1
    if any(bar.open_time != expected_start + i * H1 for i, bar in enumerate(bars)):
        raise ValueError("complete latest consecutive closed H1 window required")
    state, previous, below = IndicatorState(), None, 0
    for bar in bars:
        previous = state.rsi
        state = advance(state, bar, IndicatorParameters())
        below = min(2, below + 1) if state.rsi is not None and state.rsi < 30 else 0
    if state.rsi is None or previous is None:
        raise ValueError("warmed Wilder RSI required")
    return {
        "symbol": symbol, "status": "confirmed", "rsi": format(state.rsi, "f"),
        "previous_rsi": format(previous, "f"), "below_count": below,
        "close_price": format(bars[-1].close, "f"), "candle_closed_at": end.isoformat(),
        "fetched_at": received_at.isoformat(),
        "entry_condition": ("confirmed" if below == 2 else
                            "waiting_confirmation" if below == 1 else "waiting_rsi"),
    }


def unavailable_asset(symbol):
    return dict(symbol=symbol, status="unavailable", rsi=None, previous_rsi=None,
        below_count=None, close_price=None, candle_closed_at=None, fetched_at=None,
        entry_condition="unavailable")


class DemoSignalMonitor:
    """One public collection per closed hour, bounded single-flight and failures.

    Cached market values keep their original fetched time. Account/actor guards
    belong to the private reader and run even when this public cache is used.
    No result, including two RSI confirmations, constitutes order permission.
    """
    def __init__(self, *, fetch=public_demo_signals_get, clock=None):
        self.fetch = fetch
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.lock, self.pid = threading.Lock(), os.getpid()
        self.end, self.assets, self.retry_at = None, {}, None
        self.last_start, self.pacing_lock = None, threading.Lock()

    def _one(self, symbol, end, deadline):
        try:
            with self.pacing_lock:
                if self.last_start is not None:
                    time.sleep(max(0, .11 - (time.monotonic() - self.last_start)))
                remaining = deadline - time.monotonic()
                if remaining < .05:
                    raise ValueError("public collection deadline exceeded")
                self.last_start = time.monotonic()
            response = self.fetch(symbol, end, timeout_seconds=min(3, remaining))
            if time.monotonic() > deadline:
                raise ValueError("public collection deadline exceeded")
            return signal_asset(response, symbol, end=end, received_at=self.clock())
        except Exception:
            return unavailable_asset(symbol)

    def __call__(self):
        if os.getpid() != self.pid or not self.lock.acquire(blocking=False):
            raise ValueError("signal monitor unavailable")
        try:
            now = self.clock()
            end = boundary(now)
            if self.end != end:
                self.end, self.assets, self.retry_at = end, {}, None
            missing = tuple(symbol for symbol in SYMBOLS
                            if self.assets.get(symbol, {}).get("status") != "confirmed")
            if missing and (self.retry_at is None or now >= self.retry_at):
                deadline = time.monotonic() + 4.5
                with ThreadPoolExecutor(max_workers=3) as workers:
                    values = tuple(workers.map(lambda s: self._one(s, end, deadline), missing))
                self.assets.update((value["symbol"], value) for value in values)
                self.retry_at = self.clock() + timedelta(seconds=30)
            served = self.clock()
            if boundary(served) != end:
                raise ValueError("H1 boundary crossed during collection; refresh")
            return dict(observed_at=served.isoformat(), timeframe="H1", rsi_period=14,
                warmup_bars=WARM_BARS, next_candle_close=(end + H1).isoformat(),
                assets=[dict(self.assets.get(s, unavailable_asset(s))) for s in SYMBOLS])
        finally:
            self.lock.release()
