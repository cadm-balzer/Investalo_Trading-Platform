"""Isolated USDT long economics for offline research.

Margin and liquidation use a conservative whole-tier model. They do not
represent a broker's historical liquidation calculation.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .models import positive, precise

ECONOMICS_VERSION = "isolated-usdt-long-economics/1"
ZERO = Decimal("0")
ONE = Decimal("1")


def _fraction(value: Decimal, name: str, *, signed: bool = False) -> None:
    positive(value, name, zero=True) if not signed else _finite(value, name)
    if value >= ONE or value <= -ONE:
        raise ValueError(f"{name} must have absolute value less than one")


def _finite(value: Decimal, name: str) -> None:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ValueError(f"{name} must be a finite Decimal")


@dataclass(frozen=True)
class MarginTier:
    upper_notional: Decimal
    maintenance_rate: Decimal
    maximum_leverage: Decimal

    def __post_init__(self) -> None:
        positive(self.upper_notional, "upper_notional")
        _fraction(self.maintenance_rate, "maintenance_rate")
        positive(self.maximum_leverage, "maximum_leverage")
        if self.maximum_leverage < ONE:
            raise ValueError("maximum_leverage must be at least one")


@dataclass(frozen=True)
class MarginSchedule:
    tiers: tuple[MarginTier, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.tiers, tuple) or not 1 <= len(self.tiers) <= 32:
            raise ValueError("tiers must be a tuple of one to 32 margin tiers")
        previous: MarginTier | None = None
        for tier in self.tiers:
            if not isinstance(tier, MarginTier):
                raise ValueError("tiers must contain MarginTier records")
            if previous is not None:
                if tier.upper_notional <= previous.upper_notional:
                    raise ValueError("tier caps must strictly increase")
                if tier.maintenance_rate < previous.maintenance_rate:
                    raise ValueError("maintenance rates must not decrease")
                if tier.maximum_leverage > previous.maximum_leverage:
                    raise ValueError("maximum leverage must not increase")
            previous = tier

    def tier_for(self, notional: Decimal) -> MarginTier:
        positive(notional, "notional")
        for tier in self.tiers:
            if notional < tier.upper_notional:
                return tier
        raise ValueError("notional exceeds margin schedule coverage")

    @precise
    def margin(self, notional: Decimal) -> Decimal:
        return notional * self.tier_for(notional).maintenance_rate


@dataclass(frozen=True)
class LongPosition:
    quantity: Decimal
    average_entry: Decimal
    first_fill: Decimal
    posted_margin: Decimal

    def __post_init__(self) -> None:
        positive(self.quantity, "quantity")
        positive(self.average_entry, "average_entry")
        positive(self.first_fill, "first_fill")
        positive(self.posted_margin, "posted_margin", zero=True)

    @precise
    def notional(self, mark: Decimal) -> Decimal:
        positive(mark, "mark")
        return self.quantity * mark

    @precise
    def unrealized_pnl(self, mark: Decimal) -> Decimal:
        positive(mark, "mark")
        return self.quantity * (mark - self.average_entry)

    @precise
    def equity(self, mark: Decimal) -> Decimal:
        return self.posted_margin + self.unrealized_pnl(mark)


@precise
def funding_payment(position: LongPosition, mark: Decimal, rate: Decimal) -> Decimal:
    """Return the signed account cash change for one specified funding rate."""
    _fraction(rate, "rate", signed=True)
    return -position.notional(mark) * rate


@precise
def realized_pnl(
    position: LongPosition,
    exit_price: Decimal,
    entry_fees: Decimal,
    exit_fee_rate: Decimal,
    funding_net: Decimal,
) -> Decimal:
    positive(exit_price, "exit_price")
    positive(entry_fees, "entry_fees", zero=True)
    _fraction(exit_fee_rate, "exit_fee_rate")
    _finite(funding_net, "funding_net")
    return (
        position.quantity * (exit_price - position.average_entry)
        - entry_fees
        - position.quantity * exit_price * exit_fee_rate
        + funding_net
    )


@precise
def net_breakeven(
    position: LongPosition,
    entry_fees: Decimal,
    exit_fee_rate: Decimal,
    funding_net: Decimal,
) -> Decimal:
    positive(entry_fees, "entry_fees", zero=True)
    _fraction(exit_fee_rate, "exit_fee_rate")
    _finite(funding_net, "funding_net")
    numerator = position.quantity * position.average_entry + entry_fees - funding_net
    if numerator <= ZERO:
        return ZERO
    return numerator / (position.quantity * (ONE - exit_fee_rate))


@precise
def liquidation_bound(
    position: LongPosition,
    schedule: MarginSchedule,
    close_fee_rate: Decimal,
    maximum_mark: Decimal,
) -> Decimal:
    """Conservative mark bound; equity equal to required reserve is unsafe."""
    _fraction(close_fee_rate, "close_fee_rate")
    maximum_mmr = schedule.tier_for(position.notional(maximum_mark)).maintenance_rate
    denominator = position.quantity * (ONE - maximum_mmr - close_fee_rate)
    if denominator <= ZERO:
        raise ValueError("maintenance and close fee rates exhaust the mark")
    numerator = position.quantity * position.average_entry - position.posted_margin
    if numerator <= ZERO:
        return ZERO
    return numerator / denominator
