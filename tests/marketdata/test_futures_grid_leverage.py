"""Explicit fixed-leverage grid research; original 2x contract stays frozen."""
from decimal import Decimal
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from investalo_marketdata.futures_capital_backtest import run_scenario
from investalo_marketdata.futures_grid_profile import LEVERAGE_PROTOCOL_SHA256
from investalo_trading.futures_capital_research import (
    freeze_basket_leverage, prepare_capital_entry, simulate_capital_fill, start_capital_research,
)
from investalo_trading.futures_ledger import LedgerMark
from investalo_trading.futures_capital_journal import CapitalReplayJournal
from test_futures_capital_backtest import AT, cases, fixture
from test_futures_current_grid import ARGS, profile

D = Decimal
FLAGS = dict(current_grids=True, grid_leverage_comparison=True)


def leverage_cases():
    return tuple(s for s in cases() if s.scenario_id in
                 ("base-h1-2x", "base-h1-5x", "base-h1-10x"))


class GridLeverageResearchTests(unittest.TestCase):
    def test_original_grid_identity_and_restrictions_remain_frozen(self):
        self.assertEqual(profile().profile_digest,
                         "8bb5c87b6f42cd3ff5729eba0aa21e34316b812eba24081d75e239e34ade54d7")
        for scenario in leverage_cases()[1:]:
            with self.subTest(leverage=scenario.leverage), self.assertRaises(ValueError):
                scenario.profile(**ARGS, current_grids=True)

    def test_new_comparison_binds_protocol_without_changing_cash_grid_or_fees(self):
        original = profile()
        for scenario in leverage_cases():
            with self.subTest(leverage=scenario.leverage):
                new = scenario.profile(**ARGS, **FLAGS)
                self.assertNotEqual(new.profile_digest, original.profile_digest)
                self.assertEqual(new.plan.budgets, original.plan.budgets)
                self.assertEqual(new.plan.grid_rules, original.plan.grid_rules)
                self.assertEqual(new.plan.grid_source_digest, original.plan.grid_source_digest)
                self.assertEqual(new.plan.quantum, original.plan.quantum)
                for a, b in zip(new.plan.contracts, original.plan.contracts, strict=True):
                    self.assertEqual(new.plan.stage_capital(a.symbol),
                                     original.plan.stage_capital(b.symbol))
                    self.assertEqual(a.entry_fee_rate, b.entry_fee_rate)
                    self.assertEqual(a.protective_exit_fee_rate, b.protective_exit_fee_rate)
                    self.assertEqual(a.schedule, b.schedule)
                    self.assertEqual(a.quantity_step, b.quantity_step)

    def test_comparison_requires_explicit_complete_h1_base_grid_selection(self):
        for kwargs in (dict(grid_leverage_comparison=True), ARGS | FLAGS | {"entry_hours": 4},
                       ARGS | FLAGS | {"grid_leverage_comparison": 1},
                       ARGS | FLAGS | {"current_grids": False}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                cases()[0].profile(**kwargs)
        for scenario in cases():
            if scenario not in leverage_cases():
                with self.subTest(scenario=scenario.scenario_id), self.assertRaises(ValueError):
                    scenario.profile(**ARGS, **FLAGS)

    def test_each_basket_leverage_is_frozen_before_entry_without_new_capital(self):
        for scenario in leverage_cases():
            with self.subTest(leverage=scenario.leverage):
                plan = scenario.profile(**ARGS, **FLAGS).plan
                state = start_capital_research(
                    plan, tuple(LedgerMark(s, D(100)) for s in plan.symbols), AT, "grid-leverage")
                symbol = plan.symbols[-1]
                state = freeze_basket_leverage(state, symbol, scenario.leverage, "choice",
                                              "leverage", state.revision, AT)
                assessment = prepare_capital_entry(state, symbol, D(100), AT)
                self.assertTrue(assessment.allowed, assessment.reasons)
                self.assertEqual(assessment.request.posted_margin, plan.stage_capital(symbol)[0])
                self.assertEqual(assessment.request.requested_leverage, scenario.leverage)
                self.assertLessEqual(assessment.request.quantity * 100,
                                     assessment.request.posted_margin * scenario.leverage)
                state = simulate_capital_fill(state, assessment, D(100), "entry", state.revision, AT)
                with self.assertRaises(ValueError):
                    freeze_basket_leverage(state, symbol, D(2), "other", "change", state.revision, AT)

    def test_higher_leverage_full_market_restore_and_actual_fill_leverages(self):
        self._market(crash=False)

    def test_higher_leverage_gap_liquidations_remain_terminal_and_restore(self):
        self._market(crash=True)

    def _market(self, *, crash):
        streams = fixture(crash=crash)
        bindings = tuple(sorted(s.data_digest for s in streams.values()))
        with TemporaryDirectory() as directory:
            for scenario in leverage_cases()[1:]:
                with self.subTest(leverage=scenario.leverage, crash=crash):
                    output = Path(directory) / scenario.scenario_id
                    report = run_scenario(
                        streams, scenario, output, LEVERAGE_PROTOCOL_SHA256, bindings,
                        cash_budget_protocol=LEVERAGE_PROTOCOL_SHA256, entry_hours=1,
                        realized_exit_costs=True, reserved_cash=True, **FLAGS)
                    self.assertTrue(report["full_journal_restore_verified"])
                    self.assertTrue(report["grid_leverage_comparison"])
                    self.assertEqual(report["fixed_cycle_leverage"], str(scenario.leverage))
                    self.assertFalse(report["execution_enabled"])
                    self.assertNotIn("6", report["stage_fill_counts"])
                    self.assertLess(abs(D(report["decimal_reconciliation_residual"])), D("1e-8"))
                    entries = 0
                    for line in (output / "journal.jsonl").read_text().splitlines()[1:]:
                        command = json.loads(line)["command"]
                        if command["kind"] == "entry":
                            entries += 1
                            request = command["arguments"]["assessment"]["capital"]["request"]
                            self.assertEqual(D(request["requested_leverage"]), scenario.leverage)
                    self.assertGreater(entries, 0)
                    with self.assertRaises(ValueError):
                        CapitalReplayJournal.restore(
                            output / "journal.jsonl", profile_digest=profile().profile_digest,
                            protocol_digest=LEVERAGE_PROTOCOL_SHA256, dataset_digests=bindings)
                    if crash:
                        self.assertEqual(report["liquidations"], 5)
                        self.assertEqual(report["end_open_baskets"], [])
                        closed = json.loads((output / "closed-baskets.json").read_text())
                        self.assertTrue(all(row["liquidated"] and D(row["net_pnl"]) < 0
                                            for row in closed))
