"""3x/4x preserve capital/economics and the old strict scenario identities."""
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from investalo_marketdata.futures_research_profile import ModerateEconomicScenario
from investalo_marketdata.futures_grid_profile import MODERATE_PROTOCOL_SHA256
from investalo_marketdata.futures_capital_backtest import run_scenario
from investalo_trading.futures_capital_journal import CapitalReplayJournal
from test_futures_capital_backtest import cases, fixture
from test_futures_current_grid import ARGS, profile

D = Decimal
FLAGS = dict(current_grids=True, grid_leverage_comparison=True, moderate_grid_leverage=True)


def moderate_cases():
    base = cases()[0]
    return tuple(ModerateEconomicScenario(f"base-h1-{v}x", 1, D(v), "base",
                                         base.path, base.costs) for v in (3, 4))


class ModerateGridLeverageTests(unittest.TestCase):
    def test_readonly_metric_restore_exactly_matches_original_normal_and_gap_results(self):
        from investalo_marketdata.futures_journal_metrics import restore_metrics
        for crash in (False, True):
            streams = fixture(crash=crash)
            anchor = streams["BNBUSDT", "trade"]
            bindings = tuple(sorted(s.data_digest for s in streams.values()))
            with TemporaryDirectory() as directory:
                scenario = moderate_cases()[1]
                output = Path(directory) / scenario.scenario_id
                original = run_scenario(
                    streams, scenario, output, MODERATE_PROTOCOL_SHA256, bindings,
                    cash_budget_protocol=MODERATE_PROTOCOL_SHA256, entry_hours=1,
                    realized_exit_costs=True, reserved_cash=True, **FLAGS)
                recovered, closed = restore_metrics(output / "journal.jsonl", scenario,
                    MODERATE_PROTOCOL_SHA256, bindings, anchor.start, anchor.end)
                self.assertEqual(closed, json.loads((output / "closed-baskets.json").read_text()))
                for key in ("net_pnl", "maximum_event_drawdown_pct", "fees", "funding_net",
                            "cost_restoration", "liquidations", "stage_fill_counts",
                            "profit_factor", "maximum_posted_margin", "journal_receipt",
                            "time_weighted_posted_margin", "decimal_reconciliation_residual"):
                    self.assertEqual(recovered[key], original[key], (crash, key))
                self.assertNotIn("capital_rejections", recovered)

    def test_legacy_constructor_still_rejects_3x_and_4x(self):
        for v in (3, 4):
            with self.subTest(v=v), self.assertRaises(ValueError):
                replace(cases()[0], scenario_id=f"base-h1-{v}x", leverage=D(v))
        self.assertEqual(profile().profile_digest,
                         "8bb5c87b6f42cd3ff5729eba0aa21e34316b812eba24081d75e239e34ade54d7")

    def test_only_explicit_new_grid_axis_uses_unchanged_capital_and_costs(self):
        original = profile()
        digests = set()
        for scenario in moderate_cases():
            with self.subTest(v=scenario.leverage):
                new = scenario.profile(**ARGS, **FLAGS)
                digests.add(new.profile_digest)
                self.assertEqual(new.plan.budgets, original.plan.budgets)
                self.assertEqual(new.plan.grid_rules, original.plan.grid_rules)
                self.assertEqual(scenario.costs, cases()[0].costs)
                for bad in ({}, ARGS, ARGS | FLAGS | {"moderate_grid_leverage": False},
                            ARGS | FLAGS | {"grid_leverage_comparison": False},
                            ARGS | FLAGS | {"entry_hours": 4}):
                    with self.assertRaises(ValueError):
                        scenario.profile(**bad)
                with self.assertRaises(ValueError):
                    replace(scenario, costs=replace(scenario.costs, entry_fee_rate=D(".002")))
        self.assertEqual(len(digests), 2)
        with self.assertRaises(ValueError):
            cases()[0].profile(**ARGS, **FLAGS)

    def test_full_market_and_gap_restores_bind_own_leverage_and_genesis(self):
        for crash in (False, True):
            streams = fixture(crash=crash)
            bindings = tuple(sorted(s.data_digest for s in streams.values()))
            with TemporaryDirectory() as directory:
                for scenario in moderate_cases():
                    with self.subTest(crash=crash, v=scenario.leverage):
                        output = Path(directory) / scenario.scenario_id
                        report = run_scenario(
                            streams, scenario, output, MODERATE_PROTOCOL_SHA256, bindings,
                            cash_budget_protocol=MODERATE_PROTOCOL_SHA256, entry_hours=1,
                            realized_exit_costs=True, reserved_cash=True, **FLAGS)
                        self.assertTrue(report["full_journal_restore_verified"])
                        self.assertEqual(report["fixed_cycle_leverage"], str(scenario.leverage))
                        self.assertFalse(report["execution_enabled"])
                        self.assertNotIn("6", report["stage_fill_counts"])
                        entries = []
                        for line in (output / "journal.jsonl").read_text().splitlines()[1:]:
                            c = json.loads(line)["command"]
                            if c["kind"] == "entry":
                                entries.append(c["arguments"]["assessment"]["capital"]["request"])
                        self.assertTrue(entries)
                        self.assertTrue(all(D(e["requested_leverage"]) == scenario.leverage for e in entries))
                        with self.assertRaises(ValueError):
                            CapitalReplayJournal.restore(
                                output / "journal.jsonl", profile_digest=profile().profile_digest,
                                protocol_digest=MODERATE_PROTOCOL_SHA256, dataset_digests=bindings)
                        if crash:
                            self.assertEqual(report["liquidations"], 5)
                            self.assertEqual(report["end_open_baskets"], [])
