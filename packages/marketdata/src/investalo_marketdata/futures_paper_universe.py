"""Explicit native Paper cohorts; research/default five remain frozen."""
from .futures_broker_calibration import SYMBOLS

SEVEN_SYMBOLS = tuple(sorted((*SYMBOLS, "LINKUSDT", "AVAXUSDT")))


def paper_symbols(symbols):
    if type(symbols) is not tuple or symbols not in (SYMBOLS, SEVEN_SYMBOLS):
        raise ValueError("ordered explicit Classic five or seven candidate cohort required")
    return symbols


def native_symbols(prefixed):
    if type(prefixed) is not tuple or any(type(s) is not str or not s.startswith("BITGET:") for s in prefixed):
        raise ValueError("own native Classic candidate identities required")
    return paper_symbols(tuple(s.removeprefix("BITGET:") for s in prefixed))
