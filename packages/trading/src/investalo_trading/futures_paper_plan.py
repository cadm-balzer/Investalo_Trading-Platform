"""Dedicated Paper candidate pool: a candidate is not an allocated basket."""
from dataclasses import dataclass, field
from decimal import Decimal

from .capital_digest import digest
from .futures_capital_grid import CapitalGridPlan, CapitalGridRule
from .futures_risk import FuturesBudget, FuturesPlan
from .models import floor_step, precise

D = Decimal


@dataclass(frozen=True)
class CapitalPaperPoolPlan(CapitalGridPlan):
    capital_policy: str = field(default="isolated-usdt-capital-paper-pool/1", init=False)
    initial_slots: int = 5
    configured_limit: int = 5

    def __post_init__(self):
        # Eligibility repeats a fixed budget; only initial_slots are funded.
        # CapitalPlan's sum of every candidate budget is deliberately inapplicable.
        FuturesPlan.__post_init__(self)
        if (type(self.initial_slots) is not int or not 3 <= self.initial_slots <= 5
                or self.initial_slots > len(self.symbols)
                or type(self.configured_limit) is not int or not 3 <= self.configured_limit <= 7):
            raise ValueError("Paper requires initial3–5 funded slots and configured3–7 ceiling")
        first = self.budgets[0]
        if (any((b.capital, b.cost_reserve) != (first.capital, first.cost_reserve)
                for b in self.budgets)
                or first.capital != floor_step(self.initial_equity / self.initial_slots, self.quantum)
                or self.remainder != self.initial_equity - self.initial_slots * first.capital):
            raise ValueError("equal immutable initial funded ranges required")
        if (type(self.grid_rules) is not tuple
                or tuple(r.symbol for r in self.grid_rules if type(r) is CapitalGridRule) != self.symbols
                or len(self.grid_rules) != len(self.symbols)):
            raise ValueError("complete ordered Paper grid required")
        from .futures_replay_journal import _sha
        _sha(self.grid_source_digest)
        if any(r.maximum_market_quantity < c.minimum_quantity
               for r, c in zip(self.grid_rules, self.contracts, strict=True)):
            raise ValueError("market maximum below minimum quantity")

    @property
    def simultaneous_limit(self):
        # Profit-funded new epochs are a separate step; a ceiling alone funds nothing.
        return min(self.initial_slots, self.configured_limit, len(self.symbols))

    @property
    def plan_digest(self):
        return digest((self.capital_policy, self, "candidate-pool", "frozen-own-ranges", "2x-paper"))

    def entry_quantity(self, symbol, capital, leverage, maximum_price):
        if leverage != D(2):
            raise ValueError("Paper baseline requires fixed2× leverage")
        return super().entry_quantity(symbol, capital, leverage, maximum_price)


@precise
def paper_pool_plan(tenant_id, account_id, policy_digest, contracts, grid_rules,
                    grid_source_digest, *, initial_slots=5, configured_limit=5,
                    initial_equity=D("10000"), cost_ratio=D(".01"), quantum=D(".00000001")):
    if (type(initial_slots) is not int or not 3 <= initial_slots <= 5
            or not D(0) < cost_ratio < D(1)):
        raise ValueError("bounded own Paper capital profile required")
    total = floor_step(initial_equity / initial_slots, quantum)
    principal = floor_step(total / (1 + cost_ratio), quantum)
    return CapitalPaperPoolPlan(
        tenant_id, account_id, policy_digest, initial_equity, quantum,
        initial_equity - initial_slots * total, contracts,
        tuple(FuturesBudget(c.symbol, total, total - principal) for c in contracts),
        grid_rules, grid_source_digest, initial_slots, configured_limit,
    )
