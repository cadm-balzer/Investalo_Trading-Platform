"""Original-account BTC test proposal; read-only and never an order grant."""
from datetime import datetime, timezone
from decimal import Decimal, localcontext
import json
import re
import time

from investalo_bitget.futures_demo_preview import btc_test_preview
from .demo_startup_check import _inspect_startup, _validate_startup

SCHEMA = "investalo-demo-btc-test/1"
READINESS_SCHEMA = "investalo-demo-btc-readiness/1"
WALLET_FIELDS = ("account_equity", "available", "locked", "isolated_margin",
                 "crossed_margin", "unrealized_pnl", "coupon", "grant", "asset_mode")


def inspect_btc_test(get, binding, owner, account, wallet):
    readiness, market = _inspect_startup(get, binding, owner, account, wallet,
        config_symbols=("BTCUSDT",), extra_axes=("contracts", "ticker"), schema=READINESS_SCHEMA)
    _validate_startup(readiness, config_symbols=("BTCUSDT",), schema=READINESS_SCHEMA)
    proposal = btc_test_preview(market["contracts"], market["ticker"],
                               now_ms=time.time_ns() // 1_000_000).public()
    observed = min(datetime.fromisoformat(readiness["observed_at"]),
                   datetime.fromtimestamp(proposal["observed_ms"] / 1000, timezone.utc))
    return validate_btc_test(dict(schema=SCHEMA, observed_at=observed.isoformat(), readiness=readiness,
                preview=proposal, unknown_wallet_fields=[
                    field for field in WALLET_FIELDS if getattr(wallet, field) is None],
                execution_enabled=False))


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
