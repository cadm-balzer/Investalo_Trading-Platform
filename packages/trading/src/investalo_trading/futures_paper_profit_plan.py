"""Explicit Q36 Paper policy; historical fixed ranges remain a separate plan."""
from dataclasses import dataclass, field, fields
from datetime import datetime
from decimal import Decimal

from .allocation import revision
from .futures_capital_grid import CapitalGridRule
from .futures_ledger import number, timestamp
from .futures_paper_plan import CapitalPaperPoolPlan, paper_pool_plan
from .futures_replay_journal import _sha
from .futures_risk import FuturesBudget, FuturesPlan
from .models import floor_step, precise

D = Decimal
MAX_EPOCHS = 256


@dataclass(frozen=True)
class PaperProfitEpoch:
    index: int
    at: datetime
    capacity: int
    range_budget: Decimal
    allocated_profit: Decimal
    closed_count: int
    realized_net: Decimal
    financial_digest: str
    cash: Decimal
    equity: Decimal

    def __post_init__(self):
        for value in (self.index, self.closed_count):
            revision(value)
        if not self.index or type(self.capacity) is not int or not 3 <= self.capacity <= 7:
            raise ValueError("bounded own profit epoch required")
        timestamp(self.at)
        for value in (self.range_budget, self.allocated_profit):
            number(value, positive=True)
        for value in (self.realized_net, self.cash, self.equity):
            number(value)
        _sha(self.financial_digest)


@dataclass(frozen=True)
class CapitalPaperProfitPlan(CapitalPaperPoolPlan):
    capital_policy: str = field(default="isolated-usdt-capital-paper-profit/2", init=False)
    cost_ratio: Decimal = D(".01")
    epochs: tuple[PaperProfitEpoch, ...] = ()
    budget_indices: tuple[int, ...] = ()

    @precise
    def __post_init__(self):
        FuturesPlan.__post_init__(self)
        if (type(self.initial_slots) is not int or not 3 <= self.initial_slots <= 5
                or self.initial_slots > len(self.symbols)
                or type(self.configured_limit) is not int or not 3 <= self.configured_limit <= 7
                or not D(0) < self.cost_ratio < D(1)):
            raise ValueError("own initial3–5/ceiling3–7 profit profile required")
        number(self.cost_ratio, positive=True)
        if (type(self.grid_rules) is not tuple
                or tuple(r.symbol for r in self.grid_rules if type(r) is CapitalGridRule) != self.symbols
                or len(self.grid_rules) != len(self.symbols)
                or any(r.maximum_market_quantity < c.minimum_quantity
                       for r, c in zip(self.grid_rules, self.contracts, strict=True))):
            raise ValueError("complete ordered own profit grids required")
        _sha(self.grid_source_digest)
        if (type(self.epochs) is not tuple or len(self.epochs) > MAX_EPOCHS
                or any(type(e) is not PaperProfitEpoch for e in self.epochs)
                or type(self.budget_indices) is not tuple
                or len(self.budget_indices) != len(self.symbols)):
            raise ValueError("bounded immutable profit and cycle budget history required")
        previous_count, previous_at = 0, None
        for i, epoch in enumerate(self.epochs, 1):
            capacity = min(self.initial_slots + i, 7)
            allocated = self.original_range * i
            total = floor_step((self.initial_equity - self.original_remainder + allocated)
                               / capacity, self.quantum)
            if (epoch.index != i or epoch.capacity != capacity or epoch.capacity > len(self.symbols)
                    or epoch.allocated_profit != allocated or epoch.range_budget != total
                    or epoch.closed_count < previous_count + 3
                    or epoch.realized_net < allocated or epoch.equity < self.initial_equity + allocated
                    or epoch.cash < 0 or previous_at is not None and epoch.at < previous_at):
                raise ValueError("actual net-backed once-only profit progression required")
            previous_count, previous_at = epoch.closed_count, epoch.at
        for symbol, budget, index in zip(self.symbols, self.budgets, self.budget_indices, strict=True):
            if (type(index) is not int or not 0 <= index <= len(self.epochs)
                    or budget != self.budget_at(symbol, index)):
                raise ValueError("budget must retain its actual acknowledged epoch")
        if self.remainder != floor_step(self.remainder, self.quantum):
            raise ValueError("deferred range capital must use own cash precision")
        if not self.epochs and self.remainder != self.original_remainder:
            raise ValueError("complete original own profit allocation required")

    @property
    @precise
    def original_range(self):
        return floor_step(self.initial_equity / self.initial_slots, self.quantum)

    @property
    @precise
    def original_remainder(self):
        return self.initial_equity - self.initial_slots * self.original_range

    @property
    def allocated_profit(self):
        return self.epochs[-1].allocated_profit if self.epochs else D(0)

    @property
    def funded_slots(self):
        return self.epochs[-1].capacity if self.epochs else self.initial_slots

    @property
    def target_range(self):
        return self.epochs[-1].range_budget if self.epochs else self.original_range

    @property
    def simultaneous_limit(self):
        return min(self.funded_slots, self.configured_limit, len(self.symbols))

    @precise
    def budget_at(self, symbol, index):
        total = self.epochs[index - 1].range_budget if index else self.original_range
        principal = floor_step(total / (1 + self.cost_ratio), self.quantum)
        return FuturesBudget(symbol, total, total - principal)


def paper_profit_plan(*args, cost_ratio=D(".01"), **kwargs):
    base = paper_pool_plan(*args, cost_ratio=cost_ratio, **kwargs)
    return CapitalPaperProfitPlan(
        **{f.name: getattr(base, f.name) for f in fields(base) if f.init},
        cost_ratio=cost_ratio, budget_indices=(0,) * len(base.symbols))
