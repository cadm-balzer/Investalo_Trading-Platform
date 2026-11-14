"""Native-grid binding and explicit model boundaries for local acceptance."""
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from investalo_marketdata.futures_broker_calibration import parse_contracts
from investalo_workers.futures_local_profile import local_config, local_profit_config
from investalo_trading.futures_paper_account import PaperAccountBinding
from investalo_workers.futures_paper_bootstrap import PaperBootstrapSpec, save_spec, load_spec
from test_futures_broker_calibration import payload

D = Decimal
AT = datetime(2026, 11, 14, 21, tzinfo=timezone.utc)
TENANT, ACCOUNT, USER = (f"00000000-0000-4000-8000-{n:012d}" for n in (1, 2, 3))


class LocalFuturesProfileTests(unittest.TestCase):
    def test_explicit_profit_allocation_roundtrips_without_changing_fixed_default(self):
        rules = parse_contracts(payload())
        fixed = local_config(TENANT, ACCOUNT, rules, "a" * 64, AT)
        profit = local_profit_config(TENANT, ACCOUNT, rules, "a" * 64, AT)
        self.assertNotEqual(profit.config_digest, fixed.config_digest)
        self.assertEqual(profit.profile.plan.budgets, fixed.profile.plan.budgets)
        self.assertFalse(profit.profile.plan.epochs)
        self.assertEqual(profit.profile.plan.funded_slots, 3)
        binding = PaperAccountBinding(TENANT, ACCOUNT, USER, "https://paper.invalid",
                                      "synthetic-profile", 0, AT)
        spec = PaperBootstrapSpec(binding, profit)
        with TemporaryDirectory() as folder:
            path = Path(folder) / "allocation.json"
            self.assertEqual(save_spec(path, spec), spec.spec_digest)
            self.assertEqual(load_spec(path, spec.spec_digest), spec)
        self.assertEqual(local_config(TENANT, ACCOUNT, rules, "a" * 64, AT), fixed)

    def test_native_grids_and_fixed_declared_economics_do_not_transfer_public_tariffs(self):
        rules = tuple(replace(r, taker_fee_rate=D(".01")) for r in parse_contracts(payload()))
        config = local_config(TENANT, ACCOUNT, rules, "a" * 64, AT)
        plan = config.profile.plan
        self.assertEqual((plan.initial_equity, plan.initial_slots, plan.configured_limit,
                          plan.simultaneous_limit), (D(10000), 3, 5, 3))
        self.assertEqual(plan.budgets[0].capital, D("3333.33333333"))
        for c, grid, native in zip(plan.contracts, plan.grid_rules, rules, strict=True):
            self.assertEqual((c.quantity_step, c.minimum_quantity, c.minimum_notional),
                             (native.quantity_step, native.min_quantity, native.min_notional))
            self.assertEqual((grid.price_tick, grid.maximum_market_quantity),
                             (native.price_tick, native.max_market_quantity))
            self.assertEqual(c.entry_fee_rate, D(".0006"))
        binding = PaperAccountBinding(TENANT, ACCOUNT, USER, "https://synthetic.invalid", "own", 0, AT)
        self.assertEqual(PaperBootstrapSpec(binding, config).config, config)
        self.assertEqual(config.profile.entry_hours, 1)

    def test_source_status_leverage_completeness_and_order_are_required(self):
        rules = parse_contracts(payload())
        for bad in (
            rules[:-1], tuple(reversed(rules)),
            (replace(rules[0], status="limit_open"), *rules[1:]),
            (replace(rules[0], min_leverage=D(3)), *rules[1:]),
            (replace(rules[0], max_leverage=D(1)), *rules[1:]),
            list(rules),
        ):
            with self.subTest(rules=bad), self.assertRaises(ValueError):
                local_config(TENANT, ACCOUNT, bad, "a" * 64, AT)

    def test_original_source_hash_is_part_of_allocation_identity(self):
        rules = parse_contracts(payload())
        first = local_config(TENANT, ACCOUNT, rules, "a" * 64, AT)
        second = local_config(TENANT, ACCOUNT, rules, "b" * 64, AT)
        self.assertNotEqual(first.config_digest, second.config_digest)
        with self.assertRaises(ValueError):
            local_config(TENANT, ACCOUNT, rules, "invalid", AT)
