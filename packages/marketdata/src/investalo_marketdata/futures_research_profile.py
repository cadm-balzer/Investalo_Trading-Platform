"""Frozen declared Futures costs and native funding references; no performance job."""
from dataclasses import dataclass, fields
from datetime import datetime, timedelta
from decimal import Decimal
import hashlib
import re

from investalo_trading.futures_capital_research import CapitalCashPlan, CapitalRealizedCashPlan, equal_capital_plan
from investalo_trading.futures_capital_signals import (
    CapitalFundingBatch, CapitalHour, CapitalSignalProfile, CapitalH1SignalProfile, CapitalSignalState,
)
from investalo_trading.futures_economics import MarginSchedule, MarginTier
from investalo_trading.futures_ledger import ExitFill, FundingSettlement, LedgerMark, LiquidationSettlement
from investalo_trading.futures_risk import FuturesContract
from investalo_trading.models import precise
from investalo_trading.snapshot import digest
from investalo_trading.timeframe_research import ResearchCandle

from .binance_futures import FundingObservation, candle_record
from .binance_futures_hourly import SYMBOLS, hour_time
from .snapshot import decode_json

VERSION = "futures-capital-economic-scenario/1"
PROTOCOL_SHA256 = "eb9a278513facb4f7560413c6ae269dc2fd44adf917eec00ebec9925ddcc8c06"
D = Decimal
ZERO = D(0)


@dataclass(frozen=True)
class ScenarioCosts:
    entry_fee_rate: Decimal
    exit_fee_rate: Decimal
    slippage: Decimal
    maintenance_rate: Decimal
    liquidation_fee_rate: Decimal
    positive_funding_multiplier: Decimal

    def __post_init__(self):
        for name in ("entry_fee_rate", "exit_fee_rate", "slippage",
                     "maintenance_rate", "liquidation_fee_rate"):
            value = getattr(self, name)
            if type(value) is not Decimal or not value.is_finite() or not ZERO < value < D(1):
                raise ValueError("explicit bounded economic cost required")
        if (type(self.positive_funding_multiplier) is not Decimal
                or self.positive_funding_multiplier not in (D(1), D(2))):
            raise ValueError("explicit declared funding stress required")


@dataclass(frozen=True)
class EconomicScenario:
    scenario_id: str
    protection_hours: int
    leverage: Decimal
    cost_kind: str
    path: str
    costs: ScenarioCosts

    def __post_init__(self):
        if (type(self.protection_hours) is not int or self.protection_hours not in (1, 4)
                or type(self.leverage) is not Decimal or self.leverage not in (D(2), D(5), D(10))
                or self.cost_kind not in ("base", "stress")
                or self.path not in ("open-low-high-close", "open-high-low-close")
                or type(self.costs) is not ScenarioCosts):
            raise ValueError("declared non-AI economic scenario required")
        prefix = "order" if self.path == "open-high-low-close" else self.cost_kind
        if (self.scenario_id != f"{prefix}-h{self.protection_hours}-{self.leverage}x"
                or (prefix != "base" and self.leverage != 2)
                or prefix == "order" and self.cost_kind != "base"):
            raise ValueError("scenario label and frozen comparison axes differ")

    @property
    def assumptions_digest(self):
        return digest((VERSION, PROTOCOL_SHA256, self))

    def profile(self, tenant_id="offline-research", account_id="futures-capital-five", *,
                cash_budgets=False, entry_hours=4, realized_exit_costs=False):
        if (type(cash_budgets) is not bool or type(realized_exit_costs) is not bool
                or type(entry_hours) is not int or entry_hours not in (1, 4)
                or realized_exit_costs and not cash_budgets):
            raise ValueError("explicit research cash policy required")
        contracts = tuple(FuturesContract(
            f"BINANCE:{s}", D(".00000001"), D(".00000001"), D(5),
            self.costs.entry_fee_rate, self.costs.exit_fee_rate,
            MarginSchedule((MarginTier(D("1000000"), self.costs.maintenance_rate, D(10)),)),
            self.assumptions_digest,
        ) for s in SYMBOLS)
        plan = equal_capital_plan(
            tenant_id, account_id, self.assumptions_digest, contracts,
            initial_equity=D(10000), cost_ratio=D(".01"), quantum=D(".00000001"))
        if cash_budgets:
            plan_type = CapitalRealizedCashPlan if realized_exit_costs else CapitalCashPlan
            plan = plan_type(**{f.name: getattr(plan, f.name) for f in fields(plan) if f.init})
        return (CapitalH1SignalProfile if entry_hours == 1 else CapitalSignalProfile)(
            plan, self.protection_hours, self.costs.slippage, self.assumptions_digest)


def load_economic_protocol(raw):
    """Byte-pinned before decoding; modifying assumptions requires a new protocol."""
    if (type(raw) is not bytes or len(raw) > 64 * 1024
            or hashlib.sha256(raw).hexdigest() != PROTOCOL_SHA256):
        raise ValueError("frozen economic protocol changed")
    document = decode_json(raw, max_bytes=64 * 1024)
    costs = {name: ScenarioCosts(**{key: D(value) for key, value in document[name].items()})
             for name in ("base", "stress")}
    scenarios = tuple(EconomicScenario(
        r["id"], r["protection_hours"], D(r["leverage"]), r["costs"], r["path"], costs[r["costs"]],
    ) for r in document["scenarios"])
    if len(scenarios) != 10 or len({s.scenario_id for s in scenarios}) != 10:
        raise ValueError("complete predeclared scenario set required")
    return scenarios


@dataclass(frozen=True)
class FundingReference:
    symbol: str
    timestamp: datetime
    native_rate: Decimal
    applied_rate: Decimal
    mark: Decimal
    reference_kind: str
    evidence_digest: str
    scenario_digest: str

    @property
    def payload(self):
        return FundingSettlement(self.symbol, self.mark, self.applied_rate)


@precise
def funding_reference(symbol, row, mark_hour, source_digest, scenario):
    if (symbol not in SYMBOLS or type(row) is not FundingObservation
            or type(mark_hour) is not ResearchCandle or type(scenario) is not EconomicScenario
            or mark_hour.symbol != f"BINANCE:{symbol}:USDT-M:mark"
            or not mark_hour.open_time <= row.timestamp < mark_hour.close_time
            or mark_hour.close_time - mark_hour.open_time != timedelta(hours=1)):
        raise ValueError("matching native funding and containing H1 mark required")
    hour_time(mark_hour.open_time)
    if (row.timestamp.minute or row.timestamp.second
            or type(source_digest) is not str or re.fullmatch("[0-9a-f]{64}", source_digest) is None):
        raise ValueError("unsupported native funding time or source digest")
    mark = row.mark_price if row.mark_price is not None else mark_hour.open
    kind = "native-settlement-mark" if row.mark_price is not None else "containing-H1-mark-open-approximation"
    rate = row.rate * (scenario.costs.positive_funding_multiplier if row.rate > 0 else D(1))
    # Validate transformed cost stress against the same signed ledger contract.
    ledger_symbol = f"BINANCE:{symbol}"
    FundingSettlement(ledger_symbol, mark, rate)
    return FundingReference(
        ledger_symbol, row.timestamp, row.rate, rate, mark, kind,
        digest((VERSION, scenario.assumptions_digest, symbol, row, candle_record(mark_hour), source_digest)),
        scenario.assumptions_digest,
    )


def funding_batch(references, profile, at):
    if (type(references) is not tuple or not references
            or any(type(r) is not FundingReference or r.timestamp != at
                   or r.scenario_digest != profile.assumptions_digest
                   or r.symbol not in profile.plan.symbols for r in references)):
        raise ValueError("same-time own-scenario native funding references required")
    return CapitalFundingBatch(
        tuple(r.payload for r in references), digest((VERSION, "funding-batch", references)))


def boundary_valuation(frame, references, profile):
    """Combine exact-boundary funding marks before any day baseline is recorded."""
    if type(frame) is not CapitalHour:
        raise ValueError("closed native hour required")
    batch = funding_batch(references, profile, frame.close_time)
    if tuple(b.symbol for b in frame.mark) != tuple(
            f"{s}:USDT-M:mark" for s in profile.plan.symbols):
        raise ValueError("complete canonical native mark hour required")
    values = {p.symbol: p.mark for p in batch.settlements}
    marks = tuple(LedgerMark(s, values.get(s, b.close))
                  for s, b in zip(profile.plan.symbols, frame.mark, strict=True))
    return marks, batch.evidence_digest


@precise
def declared_exit(state, symbol, scenario, *, unsafe_state=None):
    """Typed simulated outcome, never a broker receipt or guaranteed stop fill."""
    if type(state) is not CapitalSignalState or type(scenario) is not EconomicScenario:
        raise ValueError("typed capital signal state and declared scenario required")
    if state.profile != scenario.profile(
            state.profile.plan.tenant_id, state.profile.plan.account_id,
            cash_budgets=type(state.profile.plan) in (CapitalCashPlan, CapitalRealizedCashPlan),
            entry_hours=state.profile.entry_hours,
            realized_exit_costs=type(state.profile.plan) is CapitalRealizedCashPlan):
        raise ValueError("foreign economic scenario")
    index = state.profile.plan.symbols.index(symbol)
    basket, signal = state.economic.ledger.baskets[index], state.signals[index]
    if not basket.quantity or not signal.exit_reasons:
        raise ValueError("actual model exit obligation required")
    liquidating = symbol in state.economic.liquidation_required
    if unsafe_state is not None:
        if (type(unsafe_state) is not CapitalSignalState
                or unsafe_state.profile != state.profile
                or symbol not in unsafe_state.economic.liquidation_required
                or unsafe_state.as_of > state.as_of
                or unsafe_state.trade_prices[index] != state.trade_prices[index]):
            raise ValueError("original unchanged-price unsafe liquidation evidence required")
        original = unsafe_state.economic.ledger.baskets[index]
        if (original.mark != basket.mark or original.cycle != basket.cycle
                or original.quantity != basket.quantity or original.average_entry != basket.average_entry):
            raise ValueError("price recovery cannot replace original unsafe liquidation evidence")
    if not liquidating and "liquidation_settlement_required" in signal.exit_reasons:
        if unsafe_state is None:
            raise ValueError("original unchanged-price unsafe liquidation evidence required")
        liquidating = True
    observed = state.trade_prices[index].price
    price_out = (min(observed, basket.mark) if liquidating else observed) * (1 - scenario.costs.slippage)
    fee = basket.quantity * price_out * (
        scenario.costs.liquidation_fee_rate if liquidating else scenario.costs.exit_fee_rate)
    if not liquidating:
        return ExitFill(symbol, basket.quantity, price_out, fee)
    net = basket.isolated_balance + basket.quantity * (price_out - basket.average_entry) - fee
    credit = max(ZERO, -net)
    return LiquidationSettlement(
        symbol, basket.quantity, price_out, fee, net + credit, credit,
        digest((VERSION, "declared-isolated-insurance-model", state.state_digest,
                scenario.assumptions_digest, symbol, price_out, fee, net, credit,
                unsafe_state.state_digest if unsafe_state is not None else None)),
    )
