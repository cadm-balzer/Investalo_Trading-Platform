"""Declared local Paper economics with current native Classic contract grids."""
from datetime import datetime
from decimal import Decimal
import hashlib

from investalo_marketdata.futures_broker_calibration import ContractRules, SYMBOLS
from investalo_marketdata.snapshot import canonical
from investalo_trading.futures_capital_grid import CapitalGridRule
from investalo_trading.futures_capital_signals import CapitalH1SignalProfile
from investalo_trading.futures_economics import MarginSchedule, MarginTier
from investalo_trading.futures_paper import FuturesPaperConfig
from investalo_trading.futures_paper_plan import paper_pool_plan
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
    _sha(source_digest)
    if (type(rules) is not tuple or len(rules) != len(SYMBOLS)
            or any(type(r) is not ContractRules for r in rules)
            or tuple(r.symbol for r in rules) != SYMBOLS
            or any(r.status != "normal" or not r.min_leverage <= 2 <= r.max_leverage for r in rules)):
        raise ValueError("complete normal fixed2x native Classic cohort required")
    policy = hashlib.sha256(canonical(ASSUMPTIONS).encode()).hexdigest()
    schedule = MarginSchedule((MarginTier(D("1000000"), D(".005"), D(20)),))
    contracts = tuple(FuturesContract(
        "BITGET:" + r.symbol, r.quantity_step, r.min_quantity, r.min_notional,
        D(".0006"), D(".0006"), schedule, policy,
    ) for r in rules)
    plan = paper_pool_plan(
        tenant_id, account_id, policy, contracts,
        tuple(CapitalGridRule(c.symbol, r.price_tick, r.max_market_quantity)
              for c, r in zip(contracts, rules, strict=True)),
        source_digest, initial_slots=3, configured_limit=5,
    )
    return FuturesPaperConfig(CapitalH1SignalProfile(plan, 1, D(".0005"), policy),
                             trading_from, D(".001"), True)
