"""Separate current-grid research policy; inherited cash/margin rules stay hard."""
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_CEILING
import re

from .allocation import identifier
from .futures_capital_research import CapitalReservedCashPlan
from .futures_ledger import EntryFill, ExitFill, LiquidationSettlement
from .models import floor_step, precise, positive


@dataclass(frozen=True)
class CapitalGridRule:
    symbol: str
    price_tick: Decimal
    maximum_market_quantity: Decimal

    def __post_init__(self):
        identifier(self.symbol)
        positive(self.price_tick, "price tick")
        positive(self.maximum_market_quantity, "market quantity maximum")


@dataclass(frozen=True)
class CapitalGridPlan(CapitalReservedCashPlan):
    capital_policy: str = field(default="isolated-usdt-capital-current-grid/5", init=False)
    grid_rules: tuple[CapitalGridRule, ...] = ()
    grid_source_digest: str = ""

    def __post_init__(self):
        super().__post_init__()
        if (type(self.grid_rules) is not tuple or len(self.grid_rules) != len(self.contracts)
                or any(type(r) is not CapitalGridRule for r in self.grid_rules)
                or tuple(r.symbol for r in self.grid_rules) != self.symbols
                or type(self.grid_source_digest) is not str
                or re.fullmatch("[0-9a-f]{64}", self.grid_source_digest) is None):
            raise ValueError("complete ordered grid rules and source binding required")
        if any(r.maximum_market_quantity < c.minimum_quantity
               for r, c in zip(self.grid_rules, self.contracts, strict=True)):
            raise ValueError("market maximum below minimum quantity")

    @precise
    def entry_quantity(self, symbol, capital, leverage, maximum_price):
        index = self.symbols.index(symbol)
        rule, contract = self.grid_rules[index], self.contracts[index]
        if maximum_price != floor_step(maximum_price, rule.price_tick):
            raise ValueError("current-grid entry price must be on tick")
        return floor_step(min(capital * leverage / maximum_price,
                              rule.maximum_market_quantity), contract.quantity_step)

    @precise
    def adverse_price(self, symbol, price, *, buy):
        positive(price, "declared adverse price")
        if type(buy) is not bool:
            raise ValueError("explicit trade direction required")
        step = self.grid_rules[self.symbols.index(symbol)].price_tick
        return ((price / step).to_integral_value(rounding=ROUND_CEILING) * step
                if buy else floor_step(price, step))

    def validate_exit_quantity(self, symbol, quantity):
        positive(quantity, "exit quantity")
        rule = self.grid_rules[self.symbols.index(symbol)]
        if quantity > rule.maximum_market_quantity:
            raise ValueError("basket needs multiple exit orders; full-fill model cannot represent them")

    def validate_trade_fill(self, payload):
        if type(payload) not in (EntryFill, ExitFill, LiquidationSettlement):
            return
        index = self.symbols.index(payload.symbol)
        rule, contract = self.grid_rules[index], self.contracts[index]
        if (payload.price != floor_step(payload.price, rule.price_tick)
                or payload.quantity != floor_step(payload.quantity, contract.quantity_step)
                or payload.quantity > rule.maximum_market_quantity):
            raise ValueError("trade fill outside frozen price/quantity grid or market maximum")
