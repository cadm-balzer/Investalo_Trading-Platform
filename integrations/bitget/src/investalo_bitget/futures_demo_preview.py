"""Public Demo BTC test proposal only; no key, account access or order transport."""
from dataclasses import dataclass
from decimal import Decimal, localcontext, ROUND_FLOOR
import hashlib
import ssl
import sys
import time
from urllib.error import HTTPError
from urllib.request import HTTPSHandler, ProxyHandler, Request, build_opener

from . import parse
from .futures_demo import DemoRejected, clock, number, text
from .signing import ORIGIN
from .transport import MAX_RESPONSE_BYTES, ReadResponse, _NoRedirect

TARGETS = {
    "contracts": "/api/v2/mix/market/contracts?productType=USDT-FUTURES&symbol=BTCUSDT",
    "ticker": "/api/v2/mix/market/ticker?symbol=BTCUSDT&productType=USDT-FUTURES",
}


def public_demo_btc_get(axis):
    if type(axis) is not str or axis not in TARGETS:
        raise DemoRejected("invalid_public_demo_axis")
    try:
        tls = ssl.create_default_context()
        tls.minimum_version = ssl.TLSVersion.TLSv1_2
        opener = build_opener(ProxyHandler({}), HTTPSHandler(context=tls), _NoRedirect())
        request = Request(ORIGIN + TARGETS[axis], method="GET",
                          headers={"paptrading": "1", "Accept": "application/json"})
        with opener.open(request, timeout=3) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
            if response.status != 200 or len(body) > MAX_RESPONSE_BYTES:
                raise ValueError()
            return ReadResponse(response.status, body)
    except HTTPError as error:
        error.close()
        raise DemoRejected("public_demo_quote_unavailable") from None
    except Exception:
        raise DemoRejected("public_demo_quote_unavailable") from None


def _row(response, now):
    rows, at = parse.envelope(response)
    if not 0 <= now - int(at.timestamp() * 1000) <= 5000 or type(rows) is not list:
        raise DemoRejected("stale_demo_market")
    found = [row for row in rows if type(row) is dict and row.get("symbol") == "BTCUSDT"]
    if len(found) != 1:
        raise DemoRejected("unique_btc_demo_market_required")
    return found[0], int(at.timestamp() * 1000)


@dataclass(frozen=True)
class BTCPreviewGrid:
    """Preview projection; an absent native maximum is never an execution grid."""
    quantity_step: Decimal
    price_tick: Decimal
    min_quantity: Decimal
    min_notional: Decimal
    max_limit_quantity: Decimal | None

    def __post_init__(self):
        for value in (self.quantity_step, self.price_tick, self.min_quantity, self.min_notional):
            number(value)
        if self.max_limit_quantity is not None:
            number(self.max_limit_quantity)
            if self.max_limit_quantity < self.min_quantity:
                raise DemoRejected("invalid_demo_quantity_maximum")

    def check(self, quantity, price):
        number(quantity); number(price)
        if (quantity % self.quantity_step or price % self.price_tick or quantity < self.min_quantity
                or quantity * price < self.min_notional
                or self.max_limit_quantity is not None and quantity > self.max_limit_quantity):
            raise DemoRejected("test_order_outside_grid")


@dataclass(frozen=True)
class BTCTestPreview:
    grid: BTCPreviewGrid
    quantity: Decimal
    limit_price: Decimal
    ask: Decimal
    observed_ms: int
    source_sha256: tuple[str, str]

    def public(self):
        with localcontext() as context:
            context.prec = 160
            notional = self.quantity * self.limit_price
            return dict(schema="investalo-demo-btc-test-preview/1", symbol="BTCUSDT",
                environment="demo", product_type="USDT-FUTURES", side="long",
                order_type="limit", force="ioc", leverage=2, margin_mode="isolated",
                quantity_btc=text(self.quantity), limit_price_usdt=text(self.limit_price),
                quote_ask_usdt=text(self.ask), maximum_notional_usdt=text(notional),
                initial_margin_estimate_usdt=text(notional / Decimal(2)),
                notional_cap_usdt="20", fees_verified=False, account_verified=False,
                native_max_quantity_btc=None if self.grid.max_limit_quantity is None else text(self.grid.max_limit_quantity),
                maximum_quantity_verified=self.grid.max_limit_quantity is not None,
                submission_enabled=False, observed_ms=self.observed_ms,
                source_sha256=list(self.source_sha256))


def btc_test_preview(contracts, ticker, *, now_ms):
    clock(now_ms)
    config, config_ms = _row(contracts, now_ms)
    quote, quote_ms = _row(ticker, now_ms)
    if (config.get("baseCoin") != "BTC" or config.get("quoteCoin") != "USDT"
            or config.get("symbolStatus") != "normal" or config.get("symbolType") != "perpetual"
            or config.get("supportMarginCoins") != ["USDT"]):
        raise DemoRejected("unsupported_demo_btc_contract")
    places = []
    for name in ("pricePlace", "volumePlace"):
        value = config.get(name)
        if type(value) is not str or not value.isascii() or not value.isdecimal() or not 0 <= int(value) <= 12:
            raise DemoRejected("invalid_demo_precision")
        places.append(int(value))
    tick_step = parse.amount(config.get("priceEndStep"))
    with localcontext() as context:
        context.prec = 160
        if tick_step is None or tick_step <= 0 or tick_step != tick_step.to_integral_value():
            raise DemoRejected("invalid_demo_price_step")
        grid = BTCPreviewGrid(parse.amount(config.get("sizeMultiplier")),
            tick_step.scaleb(-places[0]), parse.amount(config.get("minTradeNum")),
            parse.amount(config.get("minTradeUSDT")), parse.amount(config.get("maxOrderQty")))
        if grid.quantity_step % Decimal(1).scaleb(-places[1]):
            raise DemoRejected("inconsistent_demo_volume_grid")
        ask, bid = parse.amount(quote.get("askPr")), parse.amount(quote.get("bidPr"))
        if ask is None or bid is None or not 0 < bid <= ask:
            raise DemoRejected("invalid_demo_quote")
        source_ms = parse.timestamp_ms(quote.get("ts"))
        if not 0 <= now_ms - source_ms <= 5000:
            raise DemoRejected("stale_demo_quote")
        limit = ((ask * Decimal("1.001") / grid.price_tick).to_integral_value(rounding=ROUND_FLOOR)
                 * grid.price_tick)
        if limit <= 0:
            raise DemoRejected("test_order_outside_cap")
        cap_quantity = Decimal(20) / limit
        if grid.max_limit_quantity is not None:
            cap_quantity = min(cap_quantity, grid.max_limit_quantity)
        quantity = ((cap_quantity / grid.quantity_step)
                    .to_integral_value(rounding=ROUND_FLOOR) * grid.quantity_step)
        grid.check(quantity, limit)
        if limit < ask or limit > ask * Decimal("1.001") or quantity * limit > Decimal(20):
            raise DemoRejected("test_order_outside_cap")
        return BTCTestPreview(grid, quantity, limit, ask, min(config_ms, quote_ms, source_ms),
            (hashlib.sha256(contracts.body).hexdigest(), hashlib.sha256(ticker.body).hexdigest()))


if __name__ == "__main__":
    if sys.argv[1:] != ["--demo-btc-preview"]:
        raise SystemExit("Explicit --demo-btc-preview required; no requests made.")
    import json
    try:
        contracts, ticker = public_demo_btc_get("contracts"), public_demo_btc_get("ticker")
        preview = btc_test_preview(contracts, ticker, now_ms=time.time_ns() // 1_000_000)
        print(json.dumps(preview.public(), sort_keys=True))
    except Exception:
        raise SystemExit("Demo BTC preview unconfirmed; no order sent.") from None
