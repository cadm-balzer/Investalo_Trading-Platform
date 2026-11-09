"""One bound Paper cycle; fetch/validate first, then commit each immutable input."""
from dataclasses import dataclass
from datetime import datetime, timezone

from investalo_marketdata.paper_feed import H4, SYMBOLS, BitgetPaperFeed, boundary
from investalo_trading import PaperRunner
from .paper_store import PaperStore

WARMUP_BARS = 40


@dataclass(frozen=True)
class PaperCycle:
    revision: int
    updates: int
    fills: int


@dataclass(frozen=True)
class PaperWorker:
    runner: PaperRunner
    store: PaperStore
    feed: BitgetPaperFeed
    clock: object = lambda: datetime.now(timezone.utc)

    def run_once(self) -> PaperCycle:
        # Authoritative identity/state check before any network request.
        saved = self.store.read()
        now = self.clock()
        end = boundary(now)
        checkpoint = saved or self.runner.start(now)
        self.runner.validate(checkpoint)
        if now < checkpoint.observed_at:
            raise ValueError("Paper clock regressed")
        bars = []
        for symbol in SYMBOLS:
            last = checkpoint.state.basket(symbol).last_bar_open
            start = last if last is not None else end - WARMUP_BARS*H4
            rows = self.feed.closed_bars(symbol, start=start, end=end, now=now)
            if (len(rows) != (end-start)//H4
                    or any(bar.symbol != symbol or bar.open_time != start+index*H4
                           for index, bar in enumerate(rows))):
                raise ValueError("Paper H4 coverage differs")
            # Overlap verifies the last committed candle has not been revised.
            if last is not None:
                self.runner.bar(checkpoint, rows[0], now=now)
                rows = rows[1:]
            bars.extend(rows)
        quotes = [self.feed.quote(symbol) for symbol in SYMBOLS]
        now = self.clock()
        if now < checkpoint.observed_at or boundary(now) != end:
            raise ValueError("Paper clock/boundary changed during fetch")
        # Validate the entire batch before initialization/any persisted update.
        # Quotes are real bid/ask, not historical candle closes.
        midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        needs_day = (checkpoint.state.account.trading_day < now.date()
                     and checkpoint.observed_at < midnight)
        day_bars = tuple(next((b for b in bars if b.symbol == symbol and b.close_time == midnight),
                              None) for symbol in SYMBOLS)
        candidate = checkpoint
        if needs_day:
            if any(b is None for b in day_bars):
                raise ValueError("Paper midnight coverage missing")
            candidate = self.runner.day(candidate, day_bars, now=now).checkpoint
        for quote in quotes:
            candidate = self.runner.quote(candidate, quote, now=now).checkpoint
        ordered = sorted(bars, key=lambda bar: (bar.open_time, bar.symbol))
        for bar in ordered:
            candidate = self.runner.bar(candidate, bar, now=now).checkpoint
        if saved is None:
            checkpoint = self.store.initialize(checkpoint)
        initial_revision, fills = checkpoint.revision, 0
        def input_time():
            at = self.clock()
            if boundary(at) != end or at.date() != now.date():
                raise ValueError("Paper boundary changed during commit")
            return at
        if needs_day:
            update = self.runner.day(checkpoint, day_bars, now=input_time())
            checkpoint = self.store.commit(checkpoint, update)
        for quote in quotes:
            update = self.runner.quote(checkpoint, quote, now=input_time())
            checkpoint = self.store.commit(checkpoint, update)
            fills += len(update.entry.fills) if update.entry else 0
        for bar in ordered:
            update = self.runner.bar(checkpoint, bar, now=input_time())
            checkpoint = self.store.commit(checkpoint, update)
            fills += len(update.entry.fills) if update.entry else 0
        return PaperCycle(checkpoint.revision, checkpoint.revision-initial_revision, fills)
