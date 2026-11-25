"""Strict public H1 response projection, independent of wallet/order schemas."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import re
from uuid import UUID

from investalo_bitget.futures_demo_signals import SCHEMA, SYMBOLS, WARM_BARS, boundary
from .demo_account_sync import MAX_VIEW_BYTES

FIELDS = frozenset(("schema", "tenant_id", "account_id", "source", "execution_enabled",
    "observed_at", "timeframe", "rsi_period", "warmup_bars", "next_candle_close", "assets"))
ASSET_FIELDS = frozenset(("symbol", "status", "rsi", "previous_rsi", "below_count",
    "close_price", "candle_closed_at", "fetched_at", "entry_condition"))
NULL_FIELDS = ASSET_FIELDS - {"symbol", "status", "entry_condition"}


def _time(value):
    if (type(value) is not str or len(value) > 40 or re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)", value) is None):
        raise ValueError("public UTC timestamp required")
    result = datetime.fromisoformat(value)
    if result.tzinfo is None or result.utcoffset() != timedelta(0):
        raise ValueError("public UTC timestamp required")
    return result.astimezone(timezone.utc)


def _number(value, *, rsi=False):
    # Wilder uses 36-digit Decimal precision. Native amount's stricter scale
    # limit must not reject an internally calculated, unrounded RSI.
    if (type(value) is not str or len(value) > 96
            or re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", value) is None):
        raise ValueError("unsigned public decimal required")
    number = Decimal(value)
    if not number.is_finite() or number > (Decimal(100) if rsi else Decimal("1e30")):
        raise ValueError("bounded public decimal required")
    return number


def validate_signals(value):
    """Allow only the existing browser contract; unknown data remains unknown."""
    if (type(value) is not dict or set(value) != FIELDS or value["schema"] != SCHEMA
            or value["source"] != "bitget_classic_demo" or value["execution_enabled"] is not False
            or value["timeframe"] != "H1" or type(value["rsi_period"]) is not int
            or value["rsi_period"] != 14 or type(value["warmup_bars"]) is not int
            or value["warmup_bars"] != WARM_BARS or type(value["assets"]) is not list
            or len(value["assets"]) != len(SYMBOLS)):
        raise ValueError("public H1 signal schema required")
    for key in ("tenant_id", "account_id"):
        if type(value[key]) is not str or str(UUID(value[key])) != value[key]:
            raise ValueError("canonical public account binding required")
    observed = _time(value["observed_at"])
    end = boundary(observed)
    if _time(value["next_candle_close"]) != end + timedelta(hours=1):
        raise ValueError("next H1 boundary required")
    for symbol, asset in zip(SYMBOLS, value["assets"], strict=True):
        if type(asset) is not dict or set(asset) != ASSET_FIELDS or asset["symbol"] != symbol:
            raise ValueError("exact fixed signal assets required")
        if asset["status"] == "unavailable":
            if (asset["entry_condition"] != "unavailable"
                    or any(asset[field] is not None for field in NULL_FIELDS)):
                raise ValueError("unknown signal must remain unknown")
            continue
        if asset["status"] != "confirmed":
            raise ValueError("public signal status required")
        rsi, previous = (_number(asset[field], rsi=True) for field in ("rsi", "previous_rsi"))
        count = (2 if previous < 30 else 1) if rsi < 30 else 0
        condition = ("confirmed" if count == 2 else
                     "waiting_confirmation" if count == 1 else "waiting_rsi")
        if (type(asset["below_count"]) is not int or asset["below_count"] != count
                or asset["entry_condition"] != condition or _number(asset["close_price"]) <= 0
                or _time(asset["candle_closed_at"]) != end
                or not end <= _time(asset["fetched_at"]) <= observed):
            raise ValueError("consistent completed H1 observation required")
    if len(json.dumps(value, separators=(",", ":")).encode()) > MAX_VIEW_BYTES:
        raise ValueError("bounded public signal view required")
    return value
