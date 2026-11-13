"""Technical capacity from trusted current Futures cash; no profit/risk forecast."""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_CEILING

from .futures_ledger import number, timestamp
from .models import floor_step, precise


@dataclass(frozen=True)
class CapacityEvidence:
    observed_at: datetime
    unposted_cash: Decimal
    reserved_unposted_cash: Decimal
    active_baskets: int
    funded_capacity: int
    minimum_full_range: Decimal
    funded_range_budget: Decimal
    eligible_assets: int
    quantum: Decimal = Decimal(".00000001")

    def __post_init__(self):
        timestamp(self.observed_at)
        number(self.unposted_cash, nonnegative=True)
        number(self.reserved_unposted_cash, nonnegative=True)
        number(self.minimum_full_range, positive=True)
        number(self.funded_range_budget, positive=True)
        number(self.quantum, positive=True)
        if self.funded_range_budget != floor_step(self.funded_range_budget, self.quantum):
            raise ValueError("acknowledged range budget must already use cash precision")
        if (type(self.active_baskets) is not int or not 0 <= self.active_baskets <= 7
                or type(self.funded_capacity) is not int or not 3 <= self.funded_capacity <= 7
                or type(self.eligible_assets) is not int or not 0 <= self.eligible_assets <= 140
                or self.active_baskets > self.funded_capacity):
            raise ValueError("invalid funded capacity")


@dataclass(frozen=True)
class CapacityRecommendation:
    recommended_limit: int | None
    free_cash: Decimal
    additional_baskets: int
    new_range_budget: Decimal | None
    reason: str


@precise
def recommend_capacity(evidence: CapacityEvidence, configured_limit: int, *, now: datetime):
    """Caller owns Futures reconciliation and the current full-range minimum.

    Cash is after posted margin/fees. Reserved cash includes ALL remaining
    regular/manual amounts and fee/restoration backing of existing baskets.
    funded_capacity AND funded_range_budget belong to a separately acknowledged
    allocation/profit epoch, not a UI limit. Free profit cannot silently resize it.
    """
    if type(evidence) is not CapacityEvidence:
        raise ValueError("trusted Futures evidence required")
    if type(configured_limit) is not int or not 3 <= configured_limit <= 7:
        raise ValueError("three to seven configured baskets required")
    timestamp(now)
    free = max(Decimal(0), evidence.unposted_cash - evidence.reserved_unposted_cash)
    if not 0 <= (now-evidence.observed_at).total_seconds() <= 30:
        return CapacityRecommendation(None, free, 0, None, "stale_futures_cash")
    if evidence.unposted_cash < evidence.reserved_unposted_cash:
        return CapacityRecommendation(None, free, 0, None, "reserved_cash_shortfall")
    cap = min(configured_limit, evidence.funded_capacity, evidence.eligible_assets)
    if cap < 3:
        return CapacityRecommendation(None, free, 0, None, "candidate_pool_insufficient")
    if evidence.active_baskets >= cap:
        # Lowering capacity never resizes or closes an open basket.
        return CapacityRecommendation(cap, free, 0, None, "await_basket_closure")
    minimum = ((evidence.minimum_full_range/evidence.quantum).to_integral_value(rounding=ROUND_CEILING)
               * evidence.quantum)
    if evidence.funded_range_budget < minimum:
        return CapacityRecommendation(None, free, 0, None, "range_below_market_minimum")
    count = min(cap-evidence.active_baskets, int(free // evidence.funded_range_budget))
    target = evidence.active_baskets + count
    if target < 3:
        return CapacityRecommendation(None, free, 0, None, "full_ranges_not_funded")
    return CapacityRecommendation(target, free, count, evidence.funded_range_budget if count else None,
                                  "current_full_ranges")
