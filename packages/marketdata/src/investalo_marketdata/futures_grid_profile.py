"""Frozen quantity/price-grid axis, using current Bitget on Binance research prices."""
from dataclasses import fields, replace
from functools import lru_cache
import hashlib
from pathlib import Path

from investalo_trading.futures_capital_grid import CapitalGridPlan, CapitalGridRule
from investalo_trading.futures_capital_research import CapitalReservedCashPlan
from investalo_trading.snapshot import digest

from .futures_broker_calibration import parse_contracts

ROOT = Path(__file__).resolve().parents[4]
PROTOCOL_FILE = "docs/research-protocols/futures-capital-current-grid-20261113.json"
PROTOCOL_SHA256 = "8f24a3f0d9a7ba0af3daf497bf5ed2925a5478db35da138ed96a2b95afe84a8d"
METADATA_FILE = "docs/research-protocols/futures-bitget-classic-contracts-20261113.json"
METADATA_SHA256 = "2fd4704081bdf1df22d45b56780cfd7c1ffc6c18cb8dac97b9a6c83e331091f6"


@lru_cache(maxsize=1)
def frozen_grid_rules():
    for name, expected in ((PROTOCOL_FILE, PROTOCOL_SHA256), (METADATA_FILE, METADATA_SHA256)):
        payload = (ROOT / name).read_bytes()
        if hashlib.sha256(payload).hexdigest() != expected:
            raise ValueError("frozen current-grid reference changed")
    rules = parse_contracts(payload)
    if any(r.status != "normal" for r in rules):
        raise ValueError("frozen grid comparison requires normal contracts")
    return rules


def build_grid_profile(profile):
    if type(profile.plan) is not CapitalReservedCashPlan or profile.entry_hours != 1:
        raise ValueError("grid comparison requires own reserved cash and H1 entries")
    bindings = {f"BINANCE:{r.symbol}": r for r in frozen_grid_rules()}
    plan = profile.plan
    contracts = tuple(replace(
        c, quantity_step=bindings[c.symbol].quantity_step,
        minimum_quantity=bindings[c.symbol].min_quantity,
        minimum_notional=bindings[c.symbol].min_notional,
    ) for c in plan.contracts)
    execution = tuple(CapitalGridRule(
        c.symbol, bindings[c.symbol].price_tick, bindings[c.symbol].max_market_quantity,
    ) for c in plan.contracts)
    values = {f.name: getattr(plan, f.name) for f in fields(plan) if f.init}
    values.update(contracts=contracts, policy_digest=digest((
        plan.policy_digest, PROTOCOL_SHA256, METADATA_SHA256, "current-grid-axis")))
    return replace(profile, plan=CapitalGridPlan(
        **values, grid_rules=execution, grid_source_digest=METADATA_SHA256))
