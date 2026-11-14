"""Declared local Paper economics with current native Classic contract grids."""
from datetime import datetime
from dataclasses import replace
from decimal import Decimal
import hashlib

from investalo_marketdata.futures_broker_calibration import ContractRules, SYMBOLS
from investalo_marketdata.futures_paper_universe import SEVEN_SYMBOLS
from investalo_marketdata.snapshot import canonical
from investalo_trading.futures_capital_grid import CapitalGridRule
from investalo_trading.futures_capital_signals import CapitalH1SignalProfile
from investalo_trading.futures_economics import MarginSchedule, MarginTier
from investalo_trading.futures_paper import FuturesPaperConfig
from investalo_trading.futures_paper_plan import paper_pool_plan
from investalo_trading.futures_paper_profit_plan import paper_profit_plan
from investalo_trading.futures_risk import FuturesContract
from investalo_trading.futures_replay_journal import _sha

D = Decimal
ASSUMPTIONS = {
    "schema_version": "futures-local-paper-economics/1",
    "cash": "10000", "initial_slots": 3, "configured_limit": 5, "leverage": "2",
    "cost_ratio": "0.01", "money_quantum": "0.00000001",
    "entry_fee_rate": "0.0006", "exit_fee_rate": "0.0006",
    "maintenance_rate": "0.005", "tier_notional_cap": "1000000",
    "tier_maximum_leverage": "20", "slippage": "0.0005",
    "liquidation_fee_rate": "0.001", "assume_insurance_credit": True,
    "funding_valuation": "Q49-native-mark-minute-open",
    "fills": "declared-full-paper-fills",
    "account_fee_rate_verified": False, "maintenance_tiers_verified": False,
    "broker_admission_verified": False, "execution_enabled": False,
}


def local_config(tenant_id: str, account_id: str, rules: tuple[ContractRules, ...],
                 source_digest: str, trading_from: datetime) -> FuturesPaperConfig:
    """No balance import, fee-tariff transfer or source-status substitution."""
    return _local_config(tenant_id, account_id, rules, source_digest, trading_from,
                         symbols=SYMBOLS, assumptions=ASSUMPTIONS, profit=False)


def _local_config(tenant_id, account_id, rules, source_digest, trading_from, *,
                  symbols, assumptions, profit):
    _sha(source_digest)
    if (type(rules) is not tuple or len(rules) != len(symbols)
            or any(type(r) is not ContractRules for r in rules)
            or tuple(r.symbol for r in rules) != symbols
            or any(r.status != "normal" or not r.min_leverage <= 2 <= r.max_leverage for r in rules)):
        raise ValueError("complete normal fixed2x native Classic cohort required")
    policy = hashlib.sha256(canonical(assumptions).encode()).hexdigest()
    schedule = MarginSchedule((MarginTier(D("1000000"), D(".005"), D(20)),))
    contracts = tuple(FuturesContract(
        "BITGET:" + r.symbol, r.quantity_step, r.min_quantity, r.min_notional,
        D(".0006"), D(".0006"), schedule, policy,
    ) for r in rules)
    plan = (paper_profit_plan if profit else paper_pool_plan)(
        tenant_id, account_id, policy, contracts,
        tuple(CapitalGridRule(c.symbol, r.price_tick, r.max_market_quantity)
              for c, r in zip(contracts, rules, strict=True)),
        source_digest, initial_slots=3, configured_limit=assumptions["configured_limit"],
    )
    return FuturesPaperConfig(CapitalH1SignalProfile(plan, 1, D(".0005"), policy),
                             trading_from, D(".001"), True)


def local_profit_config(tenant_id, account_id, rules, source_digest, trading_from):
    """Separate explicitly allocated Q36 profile; never upgrade an existing journal."""
    base = local_config(tenant_id, account_id, rules, source_digest, trading_from)
    assumptions = {**ASSUMPTIONS, "schema_version": "futures-local-paper-economics/2",
                   "profit_policy": "three-closures; original-full-range; slots-to-seven-then-volume"}
    policy = hashlib.sha256(canonical(assumptions).encode()).hexdigest()
    old = base.profile.plan
    plan = paper_profit_plan(tenant_id, account_id, policy,
        tuple(replace(c, assumptions_digest=policy) for c in old.contracts),
        old.grid_rules, source_digest, initial_slots=old.initial_slots,
        configured_limit=old.configured_limit)
    return replace(base, profile=replace(base.profile, plan=plan, assumptions_digest=policy))


def local_seven_profit_config(tenant_id, account_id, rules, source_digest, trading_from):
    """New seven-native-candidate allocation; no migration of existing journals."""
    assumptions = {**ASSUMPTIONS, "schema_version": "futures-local-paper-economics/3",
                   "configured_limit": 7, "candidates": list(SEVEN_SYMBOLS),
                   "profit_policy": "three-closures; original-full-range; slots-to-seven-then-volume"}
    return _local_config(tenant_id, account_id, rules, source_digest, trading_from,
                         symbols=SEVEN_SYMBOLS, assumptions=assumptions, profit=True)
