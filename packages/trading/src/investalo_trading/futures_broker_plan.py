"""Native Demo plan with explicitly approved unknown Market maxima."""
from dataclasses import dataclass, field
from decimal import Decimal
from .allocation import identifier
from .futures_capital_grid import CapitalGridRule
from .futures_paper_profit_plan import CapitalPaperProfitPlan
from .futures_replay_journal import _sha
from .models import positive, floor_step, precise


@dataclass(frozen=True)
class BrokerGridRule(CapitalGridRule):
    maximum_market_quantity: Decimal | None

    def __post_init__(self):
        identifier(self.symbol)
        positive(self.price_tick, "native price tick")
        if self.maximum_market_quantity is not None:
            positive(self.maximum_market_quantity, "native market maximum")


@dataclass(frozen=True)
class CapitalBrokerPlan(CapitalPaperProfitPlan):
    capital_policy: str = field(default="isolated-usdt-capital-native-demo/1", init=False)
    grid_rules: tuple[BrokerGridRule, ...] = ()
    approved_policy_digest: str = ""

    @property
    def native_observed_day_basis(self):
        return True

    def __post_init__(self):
        _sha(self.approved_policy_digest)
        super().__post_init__()

    def _valid_grid_rules(self):
        return (type(self.grid_rules) is tuple
                and tuple(r.symbol for r in self.grid_rules if type(r) is BrokerGridRule) == self.symbols
                and len(self.grid_rules) == len(self.symbols)
                and all(r.maximum_market_quantity is None or r.maximum_market_quantity >= c.minimum_quantity
                        for r, c in zip(self.grid_rules, self.contracts, strict=True)))

    @precise
    def entry_quantity(self, symbol, capital, leverage, maximum_price):
        index = self.symbols.index(symbol)
        c, r = self.contracts[index], self.grid_rules[index]
        quantity = floor_step(capital * leverage / maximum_price, c.quantity_step)
        # Preserve a complete stage; a known too-small native maximum blocks it.
        if r.maximum_market_quantity is not None and quantity > r.maximum_market_quantity:
            raise ValueError("complete native stage exceeds Market maximum")
        return quantity

    def validate_exit_quantity(self, symbol, quantity):
        positive(quantity, "owned native exit quantity")
        maximum = self.grid_rules[self.symbols.index(symbol)].maximum_market_quantity
        if maximum is not None and quantity > maximum:
            raise ValueError("native exit requires a separately supported split")

    def validate_trade_fill(self, payload):
        from .futures_ledger import EntryFill, ExitFill, LiquidationSettlement
        if type(payload) not in (EntryFill, ExitFill, LiquidationSettlement):
            return
        c = self.contracts[self.symbols.index(payload.symbol)]
        if payload.quantity != floor_step(payload.quantity, c.quantity_step):
            raise ValueError("native fill quantity outside broker grid")
        # A broker-reported weighted average need not itself be on a price tick.
        self.validate_exit_quantity(payload.symbol, payload.quantity)
