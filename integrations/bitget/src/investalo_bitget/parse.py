"""Classic V2 field interpretation only. Unknown amounts remain None."""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from .models import (
    READ_AUTHORITIES, BitgetRejected, ClassicIdentity, ErrorCode, FuturesAccount,
    FuturesAsset, ProductType, SpotAsset, address, uid,
)
from .transport import MAX_RESPONSE_BYTES, ReadResponse

MAX_ASSETS = 2048
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise BitgetRejected(ErrorCode.INVALID_RESPONSE)
        result[key] = value
    return result


def timestamp_ms(value: object, *, optional: bool = False) -> int | None:
    if optional and value in (None, ""):
        return None
    if isinstance(value, str) and re.fullmatch(r"[0-9]{1,15}", value):
        value = int(value)
    if type(value) is not int or not 0 <= value < 10**15:
        raise BitgetRejected(ErrorCode.INVALID_RESPONSE)
    try:
        EPOCH + timedelta(milliseconds=value)
    except OverflowError:
        raise BitgetRejected(ErrorCode.INVALID_RESPONSE) from None
    return value


def envelope(response: ReadResponse) -> tuple[object, datetime]:
    if not isinstance(response, ReadResponse) or type(response.status) is not int or response.status != 200:
        raise BitgetRejected(ErrorCode.HTTP_FAILURE)
    if not isinstance(response.body, bytes) or len(response.body) > MAX_RESPONSE_BYTES:
        raise BitgetRejected(ErrorCode.RESPONSE_TOO_LARGE)
    try:
        raw = json.loads(response.body.decode("utf-8"), object_pairs_hook=_object,
                         parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except BitgetRejected:
        raise
    except (ValueError, RecursionError):
        raise BitgetRejected(ErrorCode.INVALID_RESPONSE) from None
    if not isinstance(raw, dict) or raw.get("code") != "00000":
        # No returned msg/message or arbitrary provider code leaves this boundary.
        raise BitgetRejected(ErrorCode.PROVIDER_REJECTED)
    if "data" not in raw or type(raw.get("requestTime")) is not int:
        raise BitgetRejected(ErrorCode.INVALID_RESPONSE)
    millis = timestamp_ms(raw["requestTime"])
    return raw["data"], EPOCH + timedelta(milliseconds=millis)


def amount(value: object, *, signed: bool = False) -> Decimal | None:
    if value is None or value == "":
        return None
    if (not isinstance(value, str) or len(value) > 96
            or not re.fullmatch(r"-?[0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]{1,2})?", value)):
        raise BitgetRejected(ErrorCode.INVALID_BALANCE)
    result = Decimal(value)
    if (not result.is_finite() or result.copy_abs() > Decimal("1e30")
            or len(result.as_tuple().digits) > 48 or abs(result.as_tuple().exponent) > 30
            or not signed and result < 0):
        raise BitgetRejected(ErrorCode.INVALID_BALANCE)
    return result


def coin(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,31}", value):
        raise BitgetRejected(ErrorCode.INVALID_BALANCE)
    return value


def identity(response: ReadResponse) -> ClassicIdentity:
    raw, at = envelope(response)
    if (not isinstance(raw, dict) or "userId" not in raw or "authorities" not in raw
            or {"permType", "permissions", "uid"}.intersection(raw)):
        raise BitgetRejected(ErrorCode.MODE_UNSUPPORTED)
    for field in ("accountMode", "accountType"):
        if field in raw:
            # These are not documented Classic fields; do not infer/normalize UTA.
            raise BitgetRejected(ErrorCode.MODE_UNSUPPORTED)
    user_id = uid(raw["userId"])
    parent_id = None if raw.get("parentId") is None else uid(raw["parentId"], parent=True)
    authorities = raw["authorities"]
    if (not isinstance(authorities, list) or not 1 <= len(authorities) <= len(READ_AUTHORITIES)
            or any(not isinstance(value, str) or value not in READ_AUTHORITIES for value in authorities)
            or len(set(authorities)) != len(authorities)):
        raise BitgetRejected(ErrorCode.PERMISSION_REJECTED)
    ips = raw.get("ips")
    whitelist = None
    if ips is not None:
        if not isinstance(ips, str) or len(ips) > 2048:
            raise BitgetRejected(ErrorCode.INVALID_RESPONSE)
        parts = ips.split(",") if ips else []
        if len(parts) > 32 or any(not value.strip() for value in parts):
            raise BitgetRejected(ErrorCode.INVALID_RESPONSE)
        whitelist = tuple(address(value.strip()) for value in parts)
        if len(set(whitelist)) != len(whitelist):
            raise BitgetRejected(ErrorCode.INVALID_RESPONSE)
    return ClassicIdentity(user_id, parent_id, tuple(sorted(authorities)), whitelist, at)


def _list(raw: object) -> list[dict]:
    if (not isinstance(raw, list) or len(raw) > MAX_ASSETS
            or any(not isinstance(value, dict) for value in raw)):
        raise BitgetRejected(ErrorCode.INVALID_BALANCE)
    return raw


def spot_assets(response: ReadResponse) -> tuple[tuple[SpotAsset, ...], datetime]:
    rows, at = envelope(response)
    assets = []
    seen = set()
    for row in _list(rows):
        name = coin(row.get("coin"))
        if name in seen:
            raise BitgetRejected(ErrorCode.INVALID_BALANCE)
        seen.add(name)
        assets.append(SpotAsset(name, *(amount(row.get(key)) for key in
                                       ("available", "frozen", "locked", "limitAvailable")),
                                timestamp_ms(row.get("uTime"), optional=True)))
    return tuple(assets), at


def futures_accounts(response: ReadResponse, product_type: ProductType) -> tuple[tuple[FuturesAccount, ...], datetime]:
    if not isinstance(product_type, ProductType):
        raise BitgetRejected(ErrorCode.INVALID_REQUEST)
    rows, at = envelope(response)
    accounts = []
    seen = set()
    for row in _list(rows):
        margin_coin = coin(row.get("marginCoin"))
        if margin_coin in seen or product_type is ProductType.USDT and margin_coin != "USDT" \
                or product_type is ProductType.USDC and margin_coin != "USDC":
            raise BitgetRejected(ErrorCode.INVALID_BALANCE)
        seen.add(margin_coin)
        mode = row.get("assetMode")
        if mode not in (None, "", "union", "single"):
            raise BitgetRejected(ErrorCode.MODE_UNSUPPORTED)
        nested = row.get("assetList")
        assets = None
        if nested is not None:
            parsed = []
            nested_seen = set()
            for item in _list(nested):
                name = coin(item.get("coin"))
                if name in nested_seen:
                    raise BitgetRejected(ErrorCode.INVALID_BALANCE)
                nested_seen.add(name)
                parsed.append(FuturesAsset(name, amount(item.get("balance"), signed=True),
                                          amount(item.get("available"), signed=True)))
            assets = tuple(parsed)
        signed = lambda key: amount(row.get(key), signed=True)
        nonnegative = lambda key: amount(row.get(key))
        accounts.append(FuturesAccount(
            product_type, margin_coin, signed("available"), nonnegative("locked"),
            signed("accountEquity"), signed("usdtEquity"), signed("btcEquity"),
            signed("unrealizedPL"), signed("crossedUnrealizedPL"), signed("isolatedUnrealizedPL"),
            nonnegative("crossedMaxAvailable"), nonnegative("isolatedMaxAvailable"),
            nonnegative("maxTransferOut"), nonnegative("crossedRiskRate"),
            nonnegative("isolatedMargin"), nonnegative("crossedMargin"),
            nonnegative("coupon"), nonnegative("grant"), mode or None,
            signed("unionTotalMargin"), signed("unionAvailable"), nonnegative("unionMm"), assets,
        ))
    return tuple(accounts), at
