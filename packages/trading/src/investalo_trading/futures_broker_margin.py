"""Durable native margin baseline; no simulated debit or execution authority."""
from dataclasses import dataclass
from decimal import Decimal

from .capital_digest import CapitalCanonical
from .futures_ledger import number
from .futures_replay_journal import _sha
from .models import precise


@dataclass(frozen=True)
class BrokerMarginPosition(CapitalCanonical):
    symbol: str
    quantity: Decimal
    average_entry: Decimal
    allocated_margin: Decimal
    funding_total: Decimal
    deducted_fees: Decimal
    realized_pnl: Decimal

    def __post_init__(self):
        if self.symbol not in ("AVAXUSDT", "BNBUSDT", "BTCUSDT", "ETHUSDT",
                               "LINKUSDT", "SOLUSDT", "XRPUSDT"):
            raise ValueError("known native margin symbol required")
        for value in (self.quantity, self.average_entry, self.allocated_margin):
            number(value, positive=True)
        number(self.funding_total)
        number(self.deducted_fees, nonnegative=True)
        number(self.realized_pnl)


@dataclass(frozen=True)
class BrokerMarginBaseline(CapitalCanonical):
    order_digest: str
    intent_digest: str
    source_digest: str
    wallet_ms: int
    positions_ms: int
    equity: Decimal
    unrealized_pnl: Decimal
    isolated_margin: Decimal
    positions: tuple[BrokerMarginPosition, ...]

    def __post_init__(self):
        for value in (self.order_digest, self.intent_digest, self.source_digest):
            _sha(value)
        for value in (self.wallet_ms, self.positions_ms):
            if type(value) is not int or not 0 <= value < 10**15:
                raise ValueError("native baseline clock required")
        if abs(self.wallet_ms - self.positions_ms) > 5000:
            raise ValueError("same fresh baseline cohort required")
        number(self.equity)
        number(self.unrealized_pnl)
        number(self.isolated_margin, nonnegative=True)
        if (type(self.positions) is not tuple or len(self.positions) > 7
                or any(type(p) is not BrokerMarginPosition for p in self.positions)
                or tuple(p.symbol for p in self.positions) !=
                tuple(sorted(set(p.symbol for p in self.positions)))):
            raise ValueError("canonical immutable margin baseline required")

    @property
    def start_ms(self):
        return min(self.wallet_ms, self.positions_ms)

    @property
    def observed_ms(self):
        return max(self.wallet_ms, self.positions_ms)

    @property
    @precise
    def collateral_without_upl(self):
        return self.equity - self.unrealized_pnl
