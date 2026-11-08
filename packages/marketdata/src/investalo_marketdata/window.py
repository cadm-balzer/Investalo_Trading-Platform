"""Exact immutable H4 windows; no interpolation, simulation or holdout authority."""
from __future__ import annotations

from datetime import datetime

from .snapshot import DatasetSnapshot, H4, make_snapshot, utc_time


def window_snapshot(snapshot: DatasetSnapshot, *, start: datetime,
                    end: datetime) -> DatasetSnapshot:
    """Select [start, end) only when every requested closed H4 candle exists.

    Coverage names the exact selected interval; its digest uses the existing
    candle/provenance contract. Original source, retrieval time, label, metadata
    and exact Candle values are preserved.
    It neither assigns a research purpose nor evaluates strategy performance.
    """
    if not isinstance(snapshot, DatasetSnapshot):
        raise ValueError("immutable snapshot required for window")
    start = utc_time(start, aligned=True)
    end = utc_time(end, aligned=True)
    if start >= end:
        raise ValueError("window must contain at least one H4 interval")
    if start < snapshot.coverage.actual_start or end > snapshot.coverage.actual_end:
        raise ValueError("requested window is not fully covered")
    candles = tuple(
        bar for bar in snapshot.candles
        if start <= bar.open_time and bar.close_time <= end
    )
    if len(candles) != (end - start) // H4:
        raise ValueError("requested window is not fully covered")
    return make_snapshot(
        snapshot.symbol, candles, snapshot.source, synthetic=snapshot.synthetic,
        requested_start=start, requested_end=end,
        instrument_metadata=snapshot.instrument_metadata,
    )
