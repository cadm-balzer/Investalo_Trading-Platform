"""Original-account BTC test proposal; read-only and never an order grant."""
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal, localcontext
import json
import re
import time

from investalo_bitget.futures_demo_preview import btc_test_preview
from investalo_bitget.futures_demo_market import btc_market_preview, VERSION as MARKET_VERSION
from investalo_bitget import parse
from .demo_startup_check import _inspect_startup, _validate_startup, wallet_blockers

SCHEMA = "investalo-demo-btc-test/1"
READINESS_SCHEMA = "investalo-demo-btc-readiness/1"
WALLET_FIELDS = ("account_equity", "available", "locked", "isolated_margin",
                 "crossed_margin", "unrealized_pnl", "coupon", "grant", "asset_mode")


def inspect_btc_test(get, binding, owner, account, wallet, *, on_grant_source=None, market_test=False):
    if type(market_test) is not bool:
        raise ValueError()
    # The existing fixed BTC account GET shares the original credential and
    # five-second cohort. Capture its documented grant without another request.
    btc_grant = {}
    def read(axis, cursor=None):
        response = get(axis, cursor)
        if axis == "BTCUSDT":
            raw, _ = parse.envelope(response)
            if (type(raw) is not dict or raw.get("marginCoin") != "USDT"
                    or "symbol" in raw and raw["symbol"] != "BTCUSDT"):
                raise ValueError()
            btc_grant["amount"] = parse.amount(raw.get("grant"))
        return response
    readiness, market = _inspect_startup(read, binding, owner, account, wallet,
        config_symbols=("BTCUSDT",), extra_axes=("contracts", "ticker"), schema=READINESS_SCHEMA)
    confirmed = btc_grant["amount"]
    if wallet.grant is not None and confirmed is not None and wallet.grant != confirmed:
        raise ValueError()
    source = "wallet" if wallet.grant is not None else "unconfirmed"
    if wallet.grant is None and confirmed is not None:
        wallet = replace(wallet, grant=confirmed)
        source = "btc_account"
        readiness["blockers"] = sorted(
            set(readiness["blockers"]) - {"wallet_unknown", "wallet_collateral", "initial_balance_changed"}
            | wallet_blockers(wallet))
    _validate_startup(readiness, config_symbols=("BTCUSDT",), schema=READINESS_SCHEMA)
    proposal = (btc_market_preview if market_test else btc_test_preview)(market["contracts"], market["ticker"],
                               now_ms=time.time_ns() // 1_000_000).public()
    observed = min(datetime.fromisoformat(readiness["observed_at"]),
                   datetime.fromtimestamp(proposal["observed_ms"] / 1000, timezone.utc))
    result = (validate_btc_market_test if market_test else validate_btc_test)(dict(
                schema="investalo-demo-btc-market-preview-report/1" if market_test else SCHEMA,
                observed_at=observed.isoformat(), readiness=readiness,
                preview=proposal, unknown_wallet_fields=[
                    field for field in WALLET_FIELDS if getattr(wallet, field) is None],
                execution_enabled=False))
    if on_grant_source is not None:
        on_grant_source(source)
    return result


def validate_btc_market_test(value):
    from .demo_account_sync import public_amount
    if (type(value) is not dict or set(value) != {"schema", "observed_at", "readiness", "preview",
            "unknown_wallet_fields", "execution_enabled"}
            or value["schema"] != "investalo-demo-btc-market-preview-report/1"
            or value["execution_enabled"] is not False):
        raise ValueError()
    readiness = _validate_startup(value["readiness"], config_symbols=("BTCUSDT",), schema=READINESS_SCHEMA)
    constants = dict(schema=MARKET_VERSION, symbol="BTCUSDT", environment="demo", order_type="market",
        side="long", leverage=2, margin_mode="isolated", planning_cap_usdt="20", price_buffer_percent="1",
        execution_price_guaranteed=False, submission_enabled=False)
    amounts = ("quantity_btc", "reference_price_usdt", "estimated_notional_usdt",
               "estimated_margin_usdt", "planning_notional_usdt")
    p = value["preview"]
    if (type(p) is not dict or set(p) != set(constants) | set(amounts) | {
            "native_max_market_quantity_btc", "observed_ms"}
            or any(type(p[k]) is not type(v) or p[k] != v for k, v in constants.items())):
        raise ValueError()
    q, price, notional, margin, planned = (public_amount(p[k]) for k in amounts)
    maximum = (None if p["native_max_market_quantity_btc"] is None
               else public_amount(p["native_max_market_quantity_btc"]))
    with localcontext() as precision:
        precision.prec = 200
        if (any(v <= 0 for v in (q, price, notional, margin, planned))
                or q * price != notional or margin * 2 != notional
                or planned != notional * Decimal("1.01") or planned > 20
                or maximum is not None and (maximum <= 0 or q > maximum)):
            raise ValueError()
    if type(p["observed_ms"]) is not int or not 0 <= p["observed_ms"] < 10**15:
        raise ValueError()
    at = datetime.fromisoformat(value["observed_at"])
    fields = value["unknown_wallet_fields"]
    if (at.tzinfo is None or at > datetime.fromisoformat(readiness["observed_at"])
            or at > datetime.fromtimestamp(p["observed_ms"] / 1000, timezone.utc)
            or type(fields) is not list or any(type(f) is not str or f not in WALLET_FIELDS for f in fields)
            or fields != [f for f in WALLET_FIELDS if f in fields]
            or fields and "wallet_unknown" not in readiness["blockers"]
            or len(json.dumps(value, separators=(",", ":")).encode()) > 65536):
        raise ValueError()
    return value


def validate_btc_test(value):
    from .demo_account_sync import public_amount
    if (type(value) is not dict or set(value) != {"schema", "observed_at", "readiness", "preview",
            "unknown_wallet_fields", "execution_enabled"} or value["schema"] != SCHEMA
            or value["execution_enabled"] is not False):
        raise ValueError()
    readiness = _validate_startup(value["readiness"], config_symbols=("BTCUSDT",), schema=READINESS_SCHEMA)
    constants = dict(schema="investalo-demo-btc-test-preview/1", symbol="BTCUSDT", environment="demo",
        product_type="USDT-FUTURES", side="long", order_type="limit", force="ioc", leverage=2,
        margin_mode="isolated", notional_cap_usdt="20", fees_verified=False,
        account_verified=False, submission_enabled=False)
    amounts = ("quantity_btc", "limit_price_usdt", "quote_ask_usdt",
               "maximum_notional_usdt", "initial_margin_estimate_usdt")
    p = value["preview"]
    if (type(p) is not dict or set(p) != set(constants) | set(amounts) | {
            "native_max_quantity_btc", "maximum_quantity_verified", "observed_ms", "source_sha256"}
            or any(type(p[k]) is not type(v) or p[k] != v for k, v in constants.items())):
        raise ValueError()
    q, price, ask, notional, margin = (public_amount(p[k]) for k in amounts)
    maximum = None if p["native_max_quantity_btc"] is None else public_amount(p["native_max_quantity_btc"])
    with localcontext() as ctx:
        ctx.prec = 200
        if (any(v <= 0 for v in (q, price, ask, notional, margin)) or q * price != notional
                or margin * 2 != notional or notional > 20 or not ask <= price <= ask * Decimal("1.001")
                or type(p["maximum_quantity_verified"]) is not bool
                or p["maximum_quantity_verified"] != (maximum is not None)
                or maximum is not None and (maximum <= 0 or q > maximum)):
            raise ValueError()
    if (type(p["observed_ms"]) is not int or not 0 <= p["observed_ms"] < 10**15
            or type(p["source_sha256"]) is not list or len(p["source_sha256"]) != 2
            or any(type(v) is not str or re.fullmatch("[a-f0-9]{64}", v) is None for v in p["source_sha256"])):
        raise ValueError()
    at = datetime.fromisoformat(value["observed_at"])
    if (at.tzinfo is None or at > datetime.fromisoformat(readiness["observed_at"])
            or at > datetime.fromtimestamp(p["observed_ms"] / 1000, timezone.utc)):
        raise ValueError()
    fields = value["unknown_wallet_fields"]
    if (type(fields) is not list or any(type(f) is not str or f not in WALLET_FIELDS for f in fields)
            or fields != [f for f in WALLET_FIELDS if f in fields]
            or fields and "wallet_unknown" not in readiness["blockers"]
            or len(json.dumps(value, separators=(",", ":")).encode()) > 65536):
        raise ValueError()
    return value
