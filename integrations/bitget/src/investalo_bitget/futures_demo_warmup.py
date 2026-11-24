"""Complete original Demo H1 trade+mark window; keyless, never order authority."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
import os
import threading
import time

from .futures_demo_signals import (
    SYMBOLS, WARM_BARS, boundary, closed_signal_candles, public_demo_signals_get,
)
from investalo_trading.capital_digest import digest
from investalo_trading.futures_capital_signals import CapitalHour
from investalo_trading.futures_broker_bootstrap import WARMUP_BATCH


@dataclass(frozen=True)
class DemoWarmupWindow:
    symbols: tuple[str, ...]
    end: datetime
    frames: tuple[CapitalHour, ...]
    fetched_at: datetime
    source_digest: str
    execution_enabled: bool = False


class DemoWarmupSource:
    def __init__(self, *, fetch=public_demo_signals_get, clock=lambda: datetime.now(timezone.utc)):
        if not callable(fetch) or not callable(clock):
            raise ValueError("native public candle source required")
        self.fetch, self.clock, self.pid = fetch, clock, os.getpid()
        self.lock, self.pacing = threading.Lock(), threading.Lock()
        self.last_start, self.window = None, None

    def collect(self, symbols, end):
        if (self.pid != os.getpid() or type(symbols) is not tuple or not 3 <= len(symbols) <= 7
                or len(set(symbols)) != len(symbols) or any(s not in SYMBOLS for s in symbols)
                or end != boundary(end) or end > boundary(self.clock())
                or not self.lock.acquire(blocking=False)):
            raise ValueError("own original bounded native warmup window required")
        try:
            if self.window is not None and (self.window.symbols, self.window.end) == (symbols, end):
                return self.window  # Original fetched_at/hash retained.
            deadline = time.monotonic()+4.5
            def one(pair):
                symbol, kind = pair
                with self.pacing:
                    if self.last_start is not None:
                        time.sleep(max(0, .11-(time.monotonic()-self.last_start)))
                    remaining = deadline-time.monotonic()
                    if remaining < .05:
                        raise ValueError("native warmup deadline exceeded")
                    self.last_start = time.monotonic()
                response = self.fetch(symbol, end, kind=kind, timeout_seconds=min(3, remaining))
                at = self.clock()
                if time.monotonic() > deadline:
                    raise ValueError("native warmup deadline exceeded")
                bars = closed_signal_candles(response, symbol, end=end, received_at=at)
                bars = tuple(replace(bar, symbol=f"{symbol}:USDT-M:{kind}") for bar in bars)
                return pair, bars, at, hashlib.sha256(response.body).hexdigest()
            pairs = tuple((s, kind) for s in symbols for kind in ("trade", "mark"))
            # Any failure joins the bounded workers and publishes no partial window.
            with ThreadPoolExecutor(max_workers=3) as pool:
                results = tuple(pool.map(one, pairs))
            if time.monotonic() > deadline:
                raise ValueError("native warmup deadline exceeded")
            values = {pair: bars for pair, bars, _, _ in results}
            frames = tuple(CapitalHour(tuple(values[(s, "trade")][i] for s in symbols),
                tuple(values[(s, "mark")][i] for s in symbols)) for i in range(WARM_BARS))
            observed = max(at for _, _, at, _ in results)
            source = digest(("bitget-demo-native-warmup/1", symbols, end,
                tuple((pair, at, sha) for pair, _, at, sha in results)))
            window = DemoWarmupWindow(symbols, end, frames, observed, source)
            self.window = window
            return window
        finally:
            self.lock.release()

    def __call__(self, *, symbols, end, offset, count):
        if (type(offset) is not int or type(count) is not int or not 0 <= offset < WARM_BARS
                or not 1 <= count <= WARMUP_BATCH or offset+count > WARM_BARS):
            raise ValueError("bounded original warmup slice required")
        return self.collect(symbols, end).frames[offset:offset+count]
