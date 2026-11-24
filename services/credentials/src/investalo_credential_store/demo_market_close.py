"""Close only the single journal-confirmed opening; no independent send authority."""
from datetime import datetime
from decimal import Decimal, localcontext

from investalo_bitget.futures_demo import DemoRejected, clock, text
from investalo_bitget.futures_demo_market import BTCMarketIntent, BTCMarketPreview
from investalo_bitget.models import FuturesAccount, ProductType
from .demo_startup_check import _validate_startup


def opening_test(traces):
    opened = [t for t in traces if not t.can_submit and t.intent.action == "open_long"]
    if (len(opened) != 1 or type(opened[0].intent) is not BTCMarketIntent
            or opened[0].state != "filled" or opened[0].observation is None
            or opened[0].observation.quantity != opened[0].intent.quantity):
        raise DemoRejected("opening_test_not_confirmed")
    return opened[0]


def check_market_close(intent, opening, readiness, wallet, market, *, now_ms):
    clock(now_ms)
    try:
        if (type(intent) is not BTCMarketIntent or intent.action != "reduce_long"
                or opening_test((opening,)) is not opening
                or intent.binding != opening.intent.binding
                or intent.quantity != opening.observation.quantity
                or intent.before_quantity != intent.quantity
                or type(wallet) is not FuturesAccount or wallet.product_type is not ProductType.USDT
                or wallet.margin_coin != "USDT" or wallet.asset_mode != "single"
                or wallet.locked != 0 or type(market) is not BTCMarketPreview):
            raise ValueError()
        _validate_startup(readiness, config_symbols=("BTCUSDT",), schema="investalo-demo-btc-readiness/1")
        account = readiness["account"]
        if (account["tenant_id"] != str(intent.binding.owner.tenant_id)
                or account["account_id"] != str(intent.binding.account_id)
                or len(account["positions"]) != 1
                or any(o["count"] != 0 or not o["complete"] for o in readiness["orders"])
                or not all(c["matches"] for c in readiness["configurations"])):
            raise ValueError()
        p = account["positions"][0]
        if (p["symbol"] != "BTCUSDT" or p["side"] != "long" or p["margin_mode"] != "isolated"
                or p["leverage"] is None or Decimal(p["leverage"]) != 2
                or Decimal(p["quantity"]) != intent.quantity
                or p["entry_price"] is None or Decimal(p["entry_price"]) != opening.observation.average_price):
            raise ValueError()
        at = int(datetime.fromisoformat(readiness["observed_at"]).timestamp() * 1000)
        if not 0 <= now_ms - min(at, market.observed_ms) <= 5000 or market.grid != intent.grid:
            raise ValueError()
        market.grid.check(intent.quantity, market.reference_price)
    except Exception:
        raise DemoRejected("market_close_position_not_confirmed") from None


def close_prepared(intent, consent):
    with localcontext() as precision:
        precision.prec = 160
        notional = text(intent.quantity * intent.reference_price)
    return dict(schema="investalo-demo-market-close-prepared/1",
        tenant_id=str(intent.binding.owner.tenant_id), account_id=str(intent.binding.account_id),
        quantity_btc=text(intent.quantity), reference_price_usdt=text(intent.reference_price),
        estimated_notional_usdt=notional, observed_ms=intent.observed_ms,
        consent_request=consent, expires_ms=intent.observed_ms+30000)


def close_settlement(account, opening):
    wallet = account["wallet"]
    # A filled order alone does not prove the account is flat.
    flat = not account["positions"] and all(wallet[k] == "0" for k in (
        "locked", "unrealized_pnl", "isolated_margin", "crossed_margin"))
    value = opening.observation.reported_fee
    fee = None if value is None else ("-" if value < 0 else "") + text(value.copy_abs())
    return dict(observed_at=account["observed_at"], wallet=wallet,
        open_position_count=len(account["positions"]), position_closed=flat,
        opening_reported_fee_usdt=fee)
