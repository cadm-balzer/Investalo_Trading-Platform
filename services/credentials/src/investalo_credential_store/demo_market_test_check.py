"""Fresh native admission for the explicitly approved small Market test only."""
from datetime import datetime
from decimal import Decimal, localcontext

from investalo_bitget.futures_demo import DemoRejected, clock
from investalo_bitget.futures_demo_market import (
    BTCMarketIntent, BTCMarketPreview, PLANNING_CAP, PRICE_BUFFER)
from investalo_bitget.models import FuturesAccount, ProductType
from .demo_startup_check import _validate_startup


def check_btc_market_test(intent, readiness, wallet, market, *, now_ms):
    """Pure check for a trusted current account reader; never an order grant.

    Identity/current actor/key/pacing must be checked by the original reader.
    Neither a browser readiness report nor this return value authorizes POST.
    """
    clock(now_ms)
    if (type(intent) is not BTCMarketIntent or type(market) is not BTCMarketPreview
            or type(wallet) is not FuturesAccount or wallet.product_type is not ProductType.USDT
            or wallet.margin_coin != "USDT" or intent.action != "open_long"
            or intent.before_quantity != 0):
        raise DemoRejected("invalid_market_test_scope")
    try:
        _validate_startup(readiness, config_symbols=("BTCUSDT",),
                          schema="investalo-demo-btc-readiness/1")
        account = readiness["account"]
        if (account["tenant_id"] != str(intent.binding.owner.tenant_id)
                or account["account_id"] != str(intent.binding.account_id)
                or account["positions"]
                or any(o["count"] != 0 or not o["complete"] for o in readiness["orders"])
                or not all(c["matches"] for c in readiness["configurations"])
                or set(readiness["blockers"]) - {"wallet_unknown"}):
            raise ValueError()
        at = int(datetime.fromisoformat(readiness["observed_at"]).timestamp() * 1000)
        if not 0 <= now_ms - min(at, market.observed_ms) <= 5000:
            raise ValueError()
        # Full original 10k/flat baseline. Only missing grant is accepted;
        # a known positive grant, other missing fields or exposure still denies.
        if (wallet.account_equity != Decimal(10000) or wallet.available != Decimal(10000)
                or any(getattr(wallet, field) != Decimal(0) for field in
                       ("coupon", "locked", "isolated_margin", "crossed_margin", "unrealized_pnl"))
                or wallet.grant not in (None, Decimal(0)) or wallet.asset_mode != "single"
                or wallet.assets not in (None, ())):
            raise ValueError()
        projected = account["wallet"]
        for public, native in (("equity", "account_equity"), ("available", "available"),
                              ("locked", "locked"), ("isolated_margin", "isolated_margin"),
                              ("crossed_margin", "crossed_margin"), ("unrealized_pnl", "unrealized_pnl")):
            if projected[public] is None or Decimal(projected[public]) != getattr(wallet, native):
                raise ValueError()
        if market.grid != intent.grid:
            raise ValueError()
        market.grid.check(intent.quantity, market.reference_price)
        with localcontext() as precision:
            precision.prec = 160
            # Recheck the fixed approved quantity at the fresh ask. Do not
            # silently resize/reprice the command after exact-body consent.
            planned = intent.quantity * market.reference_price * PRICE_BUFFER
            if planned > PLANNING_CAP or planned / 2 > wallet.available:
                raise ValueError()
        return dict(grant_verified=wallet.grant is not None,
                    native_market_max_verified=market.grid.max_market_quantity is not None,
                    costs_verified=False, pending_scope_verified=False)
    except Exception:
        raise DemoRejected("market_test_account_not_confirmed") from None
