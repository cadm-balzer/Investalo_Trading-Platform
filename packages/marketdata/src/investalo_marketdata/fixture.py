"""Deterministic synthetic integration data, never venue performance evidence."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext

from investalo_trading import Candle
from .snapshot import H4, MAX_BARS, SnapshotSource, make_snapshot, utc_time


def synthetic_snapshot(symbol: str, *, bars: int = 240,
                       start: datetime = datetime(2020, 1, 1, tzinfo=timezone.utc),
                       retrieved_at: datetime | None = None):
    utc_time(start, aligned=True)
    if type(bars) is not int or not 1 <= bars <= MAX_BARS:
        raise ValueError("synthetic count outside resource bound")
    candles = []
    with localcontext() as context:
        context.prec = 36
        previous = Decimal("100")
        for index in range(bars):
            # Repeated declines/rebounds exercise indicators/exits without randomness.
            change = (Decimal("-2") if index % 60 < 32 else Decimal("2.5"))
            close = max(Decimal("20"), previous + change)
            opened = start + H4 * index
            candles.append(Candle(symbol, opened, opened + H4, previous,
                                  max(previous, close) + Decimal("1"),
                                  min(previous, close) - Decimal("1"), close))
            previous = close
    source = SnapshotSource("synthetic", "fixture-v1", None,
                            retrieved_at or datetime.now(timezone.utc))
    return make_snapshot(symbol, tuple(candles), source, synthetic=True,
                         requested_start=start, requested_end=start + H4 * bars)
