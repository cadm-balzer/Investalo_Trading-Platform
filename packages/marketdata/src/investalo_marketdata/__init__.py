"""Immutable market data boundary. Pure validation/import plus optional public I/O."""
from .snapshot import (
    BITGET_URL, H4, MAX_BARS, MAX_BYTES, SCHEMA_VERSION, DatasetSnapshot, HistoryCoverage,
    InstrumentMetadata, SnapshotSource, dump_snapshot, load_snapshot, make_snapshot,
    to_trading_candles,
)
from .csv_import import import_csv
from .fixture import synthetic_snapshot
from .bitget import BitgetHistoryAdapter
from .window import window_snapshot

__all__ = [
    "BITGET_URL", "H4", "MAX_BARS", "MAX_BYTES", "SCHEMA_VERSION", "DatasetSnapshot",
    "HistoryCoverage", "InstrumentMetadata", "SnapshotSource", "dump_snapshot",
    "load_snapshot", "make_snapshot", "to_trading_candles", "import_csv",
    "synthetic_snapshot",
    "BitgetHistoryAdapter",
    "window_snapshot",
]
