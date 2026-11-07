"""Allowlisted public result schema. No state, fills, raw events or arbitrary metadata."""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StrictBool, StringConstraints, model_validator
from pydantic import ValidationError
from fastapi import HTTPException

from .research_spec import public_source


def finite_amount(value: str) -> str:
    number = Decimal(value)
    if not number.is_finite() or abs(number) > Decimal("1e12"):
        raise ValueError("Result amount outside display bounds")
    return value


Amount = Annotated[
    str, StringConstraints(strict=True, pattern=r"^-?\d+(?:\.\d+)?$", max_length=64),
    AfterValidator(finite_amount),
]
Digest = Annotated[str, StringConstraints(strict=True, pattern=r"^[a-f0-9]{64}$")]


class PublicRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Source(PublicRecord):
    venue: Literal["bitget", "csv", "synthetic"]
    api_version: Literal["3", "csv-v1", "fixture-v1"]
    url: str | None
    retrieved_at: datetime

    @model_validator(mode="after")
    def reviewed(self):
        if self.retrieved_at.utcoffset() != timedelta(0):
            raise ValueError("UTC source retrieval required")
        public_source(self.model_dump(mode="json"))
        if self.venue != "bitget" and self.url is not None:
            raise ValueError("Private source URL")
        return self


class CostAssumptions(PublicRecord):
    fee_rate: Amount
    spread_fraction: Amount
    slippage_fraction: Amount
    initial_equity: Amount
    basket_principal: Amount
    basket_cost_reserve: Amount


class Validation(PublicRecord):
    status: Literal["not_evaluated"]
    reason: Literal[
        "Synthetische Testdaten sind kein wirtschaftlicher Leistungsnachweis.",
        "Unabhängiger Holdout, Kostenkalibrierung und Mindeststichprobe sind nicht bewertet.",
    ]


class EquityPoint(PublicRecord):
    at: datetime
    equity: Amount


class Coverage(PublicRecord):
    requested_start: datetime | None
    requested_end: datetime | None
    actual_start: datetime
    actual_end: datetime
    complete: StrictBool | None
    missing_leading_bars: Annotated[int, Field(strict=True, ge=0, le=10000)] | None
    missing_trailing_bars: Annotated[int, Field(strict=True, ge=0, le=10000)] | None


class ResultSummary(PublicRecord):
    schema_version: Literal["backtest-result/1"]
    symbol: Literal["BTC/USDT", "ETH/USDT"]
    timeframe: Literal["4h"]
    strategy_version: Literal["crypto-basket/1.0.0"]
    data_digest: Digest
    simulation_data_digest: Digest
    configuration_digest: Digest
    cost_digest: Digest
    source: Source
    synthetic: StrictBool
    bar_count: Annotated[int, Field(strict=True, ge=1, le=10000)]
    start: datetime
    end: datetime
    net_pnl: Amount
    maximum_drawdown_fraction: Amount
    profit_factor: Amount | None
    closed_basket_count: Annotated[int, Field(strict=True, ge=0, le=10000)]
    equity_curve_sampled: StrictBool
    cost_assumptions: CostAssumptions
    coverage: Coverage
    validation: Validation

    @model_validator(mode="after")
    def reviewed_summary(self):
        times = [
            self.start, self.end, self.coverage.actual_start, self.coverage.actual_end,
            self.coverage.requested_start, self.coverage.requested_end,
        ]
        if any(value is not None and value.utcoffset() != timedelta(0) for value in times):
            raise ValueError("UTC result bounds required")
        if self.start >= self.end or self.coverage.actual_start != self.start or self.coverage.actual_end != self.end:
            raise ValueError("Result coverage differs")
        if not Decimal("0") <= Decimal(self.maximum_drawdown_fraction) <= Decimal("1"):
            raise ValueError("Invalid drawdown fraction")
        if self.profit_factor is not None and Decimal(self.profit_factor) < 0:
            raise ValueError("Negative profit factor")
        if self.source.venue == "synthetic" and not self.synthetic:
            raise ValueError("Synthetic source differs")
        if self.synthetic != (self.validation.reason ==
                "Synthetische Testdaten sind kein wirtschaftlicher Leistungsnachweis."):
            raise ValueError("Validation provenance differs")
        for key in ("fee_rate", "spread_fraction", "slippage_fraction"):
            if not Decimal("0") <= Decimal(getattr(self.cost_assumptions, key)) < Decimal("1"):
                raise ValueError("Invalid cost fraction")
        for key in ("initial_equity", "basket_principal", "basket_cost_reserve"):
            if Decimal(getattr(self.cost_assumptions, key)) <= 0:
                raise ValueError("Invalid research capital")
        return self


class Result(ResultSummary):
    equity_curve: Annotated[list[EquityPoint], Field(min_length=1, max_length=2000)]

    @model_validator(mode="after")
    def bounded_curve(self):
        if self.start >= self.end:
            raise ValueError("Invalid research interval")
        times = [point.at for point in self.equity_curve]
        if any(at.utcoffset() != timedelta(0) for at in times):
            raise ValueError("UTC equity points required")
        if any(not self.start <= at <= self.end for at in times):
            raise ValueError("Curve outside research interval")
        if any(a > b for a, b in zip(times, times[1:])):
            raise ValueError("Curve not ordered")
        if any(Decimal(point.equity) < 0 for point in self.equity_curve):
            raise ValueError("Negative research equity")
        if self.synthetic != (self.validation.reason ==
                "Synthetische Testdaten sind kein wirtschaftlicher Leistungsnachweis."):
            raise ValueError("Validation provenance differs")
        return self


def publish_result(value: dict | None, *, summary: bool = False) -> dict | None:
    if value is None:
        return None
    model = ResultSummary if summary else Result
    try:
        return model.model_validate(value).model_dump(mode="json")
    except (ValidationError, ValueError, TypeError):
        raise HTTPException(503, "Research result unavailable") from None
