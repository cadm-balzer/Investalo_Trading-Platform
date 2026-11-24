"""Approved small BTC Demo Market test; no browser, broker or dispatch authority."""
from dataclasses import dataclass, field
from decimal import Decimal, localcontext, ROUND_FLOOR
from uuid import UUID

from . import parse
from .futures_demo import DemoBinding, DemoRejected, clock, digest, number, text
from .futures_demo_preview import _row

VERSION = "bitget-classic-btc-demo-market-test/1"
CONFIRMATION = "btc-demo-market-long-isolated-2x-estimate-20-usdt"
CLOSE_CONFIRMATION = "btc-demo-market-close-owned-long-reduce-only"
PLANNING_CAP = Decimal(20)
PRICE_BUFFER = Decimal("1.01")


@dataclass(frozen=True)
class BTCMarketGrid:
    symbol: str
    quantity_step: Decimal
    min_quantity: Decimal
    min_notional: Decimal
    max_market_quantity: Decimal | None

    def __post_init__(self):
        if self.symbol != "BTCUSDT":
            raise DemoRejected("market_test_btc_required")
        for value in (self.quantity_step, self.min_quantity, self.min_notional):
            number(value)
        if self.max_market_quantity is not None:
            number(self.max_market_quantity)
            if self.max_market_quantity < self.min_quantity:
                raise DemoRejected("invalid_market_quantity_maximum")

    def check(self, quantity, reference_price):
        number(quantity); number(reference_price)
        with localcontext() as precision:
            precision.prec = 160
            if (quantity % self.quantity_step or quantity < self.min_quantity
                    or quantity * reference_price < self.min_notional
                    or self.max_market_quantity is not None and quantity > self.max_market_quantity):
                raise DemoRejected("market_test_outside_grid")

    def record(self):
        return {name: text(value) if isinstance(value, Decimal) else value
                for name, value in vars(self).items()}


@dataclass(frozen=True, repr=False)
class BTCMarketIntent:
    """Base-coin quantity is fixed. Reference price is never a broker limit."""
    binding: DemoBinding
    command_id: UUID
    grid: BTCMarketGrid
    action: str
    quantity: Decimal
    reference_price: Decimal
    before_quantity: Decimal
    observed_ms: int
    client_oid: str = field(init=False)
    intent_digest: str = field(init=False)

    def __post_init__(self):
        if (type(self.binding) is not DemoBinding or type(self.command_id) is not UUID
                or type(self.grid) is not BTCMarketGrid or self.action not in ("open_long", "reduce_long")):
            raise DemoRejected("invalid_market_test_intent")
        self.grid.check(self.quantity, self.reference_price)
        clock(self.observed_ms)
        number(self.before_quantity, zero=True)
        with localcontext() as precision:
            precision.prec = 160
            if (self.action == "open_long" and self.quantity * self.reference_price * PRICE_BUFFER > PLANNING_CAP
                    or self.action == "reduce_long" and self.quantity > self.before_quantity):
                raise DemoRejected("market_test_outside_budget")
        key = dict(version=VERSION, owner=str(self.binding.owner.tenant_id),
                   account=str(self.binding.account_id), command=str(self.command_id))
        object.__setattr__(self, "client_oid", "ivd" + digest(key)[:29])
        object.__setattr__(self, "intent_digest", digest(dict(version=VERSION,
            binding=self.binding.record(), command=str(self.command_id), grid=self.grid.record(),
            action=self.action, quantity=text(self.quantity), reference_price=text(self.reference_price),
            before=text(self.before_quantity), observed_ms=self.observed_ms, price_buffer=text(PRICE_BUFFER))))

    def __repr__(self):
        return "BTCMarketIntent(<private>)"


@dataclass(frozen=True)
class BTCMarketPreview:
    grid: BTCMarketGrid
    quantity: Decimal
    reference_price: Decimal
    observed_ms: int

    def intent(self, binding, command_id):
        return BTCMarketIntent(binding, command_id, self.grid, "open_long",
                               self.quantity, self.reference_price, Decimal(0), self.observed_ms)

    def public(self):
        with localcontext() as precision:
            precision.prec = 160
            value = self.quantity * self.reference_price
            return dict(schema=VERSION, symbol="BTCUSDT", environment="demo",
                order_type="market", side="long", leverage=2, margin_mode="isolated",
                quantity_btc=text(self.quantity), reference_price_usdt=text(self.reference_price),
                estimated_notional_usdt=text(value), estimated_margin_usdt=text(value / 2),
                planning_notional_usdt=text(value * PRICE_BUFFER), planning_cap_usdt="20",
                price_buffer_percent="1", execution_price_guaranteed=False,
                native_max_market_quantity_btc=(None if self.grid.max_market_quantity is None
                                                else text(self.grid.max_market_quantity)),
                observed_ms=self.observed_ms, submission_enabled=False)


def btc_market_preview(contracts, ticker, *, now_ms):
    clock(now_ms)
    config, config_ms = _row(contracts, now_ms)
    quote, quote_ms = _row(ticker, now_ms)
    if (config.get("baseCoin") != "BTC" or config.get("quoteCoin") != "USDT"
            or config.get("symbolStatus") != "normal" or config.get("symbolType") != "perpetual"
            or config.get("supportMarginCoins") != ["USDT"]):
        raise DemoRejected("unsupported_demo_btc_contract")
    places = config.get("volumePlace")
    if (type(places) is not str or not places.isascii() or not places.isdecimal()
            or not 0 <= int(places) <= 12):
        raise DemoRejected("invalid_demo_precision")
    native_max = config.get("maxMarketOrderQty")
    maximum = parse.amount(native_max)
    if native_max not in (None, "") and maximum is None:
        raise DemoRejected("invalid_market_quantity_maximum")
    grid = BTCMarketGrid("BTCUSDT", parse.amount(config.get("sizeMultiplier")),
        parse.amount(config.get("minTradeNum")), parse.amount(config.get("minTradeUSDT")), maximum)
    with localcontext() as precision:
        precision.prec = 160
        if grid.quantity_step % Decimal(1).scaleb(-int(places)):
            raise DemoRejected("inconsistent_demo_volume_grid")
        ask, bid = parse.amount(quote.get("askPr")), parse.amount(quote.get("bidPr"))
        if ask is None or bid is None or not 0 < bid <= ask:
            raise DemoRejected("invalid_demo_quote")
        source_ms = parse.timestamp_ms(quote.get("ts"))
        if not 0 <= now_ms - source_ms <= 5000:
            raise DemoRejected("stale_demo_quote")
        cap = PLANNING_CAP / (ask * PRICE_BUFFER)
        if maximum is not None:
            cap = min(cap, maximum)
        quantity = (cap / grid.quantity_step).to_integral_value(rounding=ROUND_FLOOR) * grid.quantity_step
        grid.check(quantity, ask)
        return BTCMarketPreview(grid, quantity, ask, min(config_ms, quote_ms, source_ms))
