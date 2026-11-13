"""Frozen grid-only comparison: budget, causal replay and liquidation boundaries."""
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from investalo_marketdata.futures_capital_backtest import run_scenario
from investalo_marketdata.futures_grid_profile import METADATA_SHA256
from investalo_trading.futures_capital_grid import CapitalGridPlan
from investalo_trading.futures_capital_research import (
    freeze_basket_leverage, prepare_capital_entry, record_capital_event,
    simulate_capital_fill, start_capital_research,
)
from investalo_trading.futures_capital_journal import CapitalReplayJournal
from investalo_trading.futures_ledger import ExitFill, FundingSettlement, LedgerMark, MarkBatch
from investalo_trading.models import floor_step
from test_futures_capital_backtest import AT, cases, fixture

D = Decimal
ARGS = dict(cash_budgets=True, entry_hours=1, realized_exit_costs=True, reserved_cash=True)


def profile():
    return cases()[0].profile(**ARGS, current_grids=True)


def economic(price="100"):
    plan = profile().plan
    return start_capital_research(
        plan, tuple(LedgerMark(s, D(price)) for s in plan.symbols), AT, "synthetic-grid-genesis")


class CurrentGridResearchTests(unittest.TestCase):
    def test_separate_identity_preserves_entire_capital_and_economic_axis(self):
        old = cases()[0].profile(**ARGS)
        new = profile()
        self.assertIs(type(new.plan), CapitalGridPlan)
        self.assertNotEqual(new.profile_digest, old.profile_digest)
        self.assertNotEqual(new.plan.plan_digest, old.plan.plan_digest)
        self.assertEqual(new.assumptions_digest, old.assumptions_digest)
        self.assertEqual(new.plan.budgets, old.plan.budgets)
        self.assertEqual(new.plan.remainder, old.plan.remainder)
        for a, b in zip(new.plan.contracts, old.plan.contracts):
            self.assertEqual(a.entry_fee_rate, b.entry_fee_rate)
            self.assertEqual(a.protective_exit_fee_rate, b.protective_exit_fee_rate)
            self.assertEqual(a.schedule, b.schedule)
            self.assertEqual(new.plan.stage_capital(a.symbol), old.plan.stage_capital(b.symbol))
        self.assertEqual(new.plan.contracts[-1].quantity_step, D(1))
        self.assertEqual(new.plan.grid_source_digest, METADATA_SHA256)

    def test_grid_selection_requires_complete_reserved_h1_base2x(self):
        for args in ({}, {"cash_budgets": True}, ARGS | {"entry_hours": 4},
                     ARGS | {"current_grids": 1}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                cases()[0].profile(**({"current_grids": True} | args))
        for scenario in cases()[1:]:
            with self.subTest(scenario=scenario.scenario_id), self.assertRaises(ValueError):
                scenario.profile(**ARGS, current_grids=True)

    def test_adverse_entry_and_exit_ticks_do_not_invent_favorable_prices(self):
        plan = profile().plan
        symbol = "BINANCE:BTCUSDT"
        self.assertEqual(plan.adverse_price(symbol, D("23455.01"), buy=True), D("23455.1"))
        self.assertEqual(plan.adverse_price(symbol, D("23455.09"), buy=False), D("23455.0"))
        self.assertEqual(plan.adverse_price(symbol, D("23455.1"), buy=True), D("23455.1"))
        with self.assertRaises(ValueError):
            plan.adverse_price(symbol, D(100), buy=1)

    def test_source_identity_complete_grids_and_market_max_are_bound(self):
        plan = profile().plan
        for args in ({"grid_rules": plan.grid_rules[:-1]}, {"grid_source_digest": "not-sha"},
                     {"grid_rules": tuple(reversed(plan.grid_rules))}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                replace(plan, **args)
        self.assertNotEqual(replace(plan, grid_source_digest="e" * 64).plan_digest, plan.plan_digest)

    def test_market_cap_and_tick_guard_never_increase_stage_notional(self):
        plan = profile().plan
        symbol = plan.symbols[0]
        rule = plan.grid_rules[0]
        quantity = plan.entry_quantity(symbol, D("175.88019535"), D(2), D(1))
        self.assertEqual(quantity, rule.maximum_market_quantity)
        self.assertLessEqual(quantity, D("175.88019535") * 2)
        with self.assertRaises(ValueError):
            plan.entry_quantity(symbol, D(100), D(2), D("1.001"))
        with self.assertRaises(ValueError):
            plan.validate_exit_quantity(symbol, rule.maximum_market_quantity + D(".01"))

    def test_five_full_capital_stages_fixed_leverage_manual_reserve_untouched(self):
        state = economic()
        symbol = "BINANCE:XRPUSDT"
        state = freeze_basket_leverage(state, symbol, D(2), "synthetic-leverage",
                                      "choice", state.revision, state.as_of)
        capitals = state.ledger.plan.stage_capital(symbol)
        for i in range(5):
            price = state.ledger.plan.adverse_price(symbol, D(100) * D(".95") ** i, buy=True)
            at = AT + timedelta(seconds=i + 1)
            state = record_capital_event(state, MarkBatch(tuple(
                LedgerMark(b.symbol, price if b.symbol == symbol else b.mark)
                for b in state.ledger.baskets)), f"mark-{i}", state.revision, at)
            assessment = prepare_capital_entry(state, symbol, price, at)
            self.assertTrue(assessment.allowed, assessment.reasons)
            self.assertEqual(assessment.request.posted_margin, capitals[i])
            self.assertEqual(assessment.request.requested_leverage, D(2))
            self.assertEqual(assessment.request.quantity % 1, D(0))
            state = simulate_capital_fill(state, assessment, price, f"fill-{i}", state.revision, at)
        basket = state.ledger.baskets[-1]
        self.assertEqual(basket.margin_committed, sum(capitals[:5]))
        self.assertLess(basket.average_entry, D(100))
        with self.assertRaisesRegex(ValueError, "manual"):
            prepare_capital_entry(state, symbol, basket.mark, state.as_of)
        with self.assertRaises(ValueError):
            freeze_basket_leverage(state, symbol, D(5), "other", "change",
                                   state.revision, state.as_of)

    def test_fill_rechecks_price_grid_and_preserves_state_on_denial(self):
        state = economic()
        symbol = "BINANCE:XRPUSDT"
        state = freeze_basket_leverage(state, symbol, D(2), "choice-evidence",
                                      "choice", state.revision, state.as_of)
        assessment = prepare_capital_entry(state, symbol, D(100), state.as_of)
        before = state.state_digest
        with self.assertRaises(ValueError):
            simulate_capital_fill(state, assessment, D("99.99999"), "off-tick",
                                  state.revision, state.as_of)
        self.assertEqual(state.state_digest, before)

    def test_real_underfunding_and_declared_price_guard_still_reject(self):
        state = economic()
        symbol = "BINANCE:XRPUSDT"
        state = freeze_basket_leverage(state, symbol, D(2), "choice-evidence",
                                      "choice", state.revision, state.as_of)
        assessment = prepare_capital_entry(state, symbol, D(100), state.as_of)
        state = simulate_capital_fill(state, assessment, D(100), "fill", state.revision, state.as_of)
        at = state.as_of + timedelta(seconds=1)
        state = record_capital_event(state, MarkBatch(tuple(
            LedgerMark(b.symbol, b.mark) for b in state.ledger.baskets)),
            "funding-mark", state.revision, at)
        state = record_capital_event(state, FundingSettlement(symbol, D(100), D(".2")),
                                     "funding", state.revision, at)
        denied = prepare_capital_entry(state, symbol, D(100), state.as_of)
        self.assertIn("initial_margin_requirement", denied.reasons)
        denied = prepare_capital_entry(state, symbol, D("99.9"), state.as_of)
        self.assertIn("fill_bound_below_mark", denied.reasons)
        self.assertFalse(denied.allowed)

    def test_grid_quantity_covers_nano_funding_without_rounding_cash_up(self):
        state = economic()
        symbol = "BINANCE:XRPUSDT"
        state = freeze_basket_leverage(state, symbol, D(2), "choice-evidence",
                                      "choice", state.revision, state.as_of)
        assessment = prepare_capital_entry(state, symbol, D(100), state.as_of)
        state = simulate_capital_fill(state, assessment, D(100), "fill", state.revision, state.as_of)
        before = state.ledger.baskets[-1].isolated_balance
        at = state.as_of + timedelta(seconds=1)
        state = record_capital_event(state, MarkBatch(tuple(
            LedgerMark(b.symbol, b.mark) for b in state.ledger.baskets)),
            "funding-mark", state.revision, at)
        state = record_capital_event(state, FundingSettlement(symbol, D(100), D("1e-11")),
                                     "funding", state.revision, at)
        self.assertEqual(before - state.ledger.baskets[-1].isolated_balance, D("3e-9"))
        self.assertTrue(prepare_capital_entry(state, symbol, D(100), state.as_of).allowed)

    def test_exit_events_also_enforce_tick_and_quantity_grid(self):
        plan = profile().plan
        for quantity, price in (("1.5", "100"), ("1", "100.00001")):
            with self.subTest(quantity=quantity, price=price), self.assertRaises(ValueError):
                plan.validate_trade_fill(ExitFill("BINANCE:XRPUSDT", D(quantity), D(price), D(0)))

    def test_genesis_restores_grid_metadata_and_rejects_foreign_expected_profile(self):
        current = profile()
        marks = tuple(LedgerMark(s, D(100)) for s in current.plan.symbols)
        with TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            with CapitalReplayJournal.create(path, current, marks, marks, AT, "evidence",
                    protocol_digest="a" * 64, dataset_digests=("b" * 64,)) as journal:
                receipt = journal.receipt
            with CapitalReplayJournal.restore(path, profile_digest=current.profile_digest,
                    protocol_digest="a" * 64, dataset_digests=("b" * 64,),
                    minimum_receipt=receipt) as restored:
                self.assertEqual(restored.receipt, receipt)
                self.assertEqual(restored.state.profile.plan, current.plan)
            with self.assertRaises(ValueError):
                CapitalReplayJournal.restore(path,
                    profile_digest=cases()[0].profile(**ARGS).profile_digest,
                    protocol_digest="a" * 64, dataset_digests=("b" * 64,))

    def test_complete_synthetic_market_and_restore_keep_all_fills_on_grid(self):
        streams = fixture()
        bindings = tuple(sorted(s.data_digest for s in streams.values()))
        with TemporaryDirectory() as directory:
            output = Path(directory) / "grid"
            report = run_scenario(streams, cases()[0], output, "a" * 64, bindings,
                                  cash_budget_protocol="a" * 64, entry_hours=1,
                                  realized_exit_costs=True, reserved_cash=True, current_grids=True)
            self.assertTrue(report["full_journal_restore_verified"])
            self.assertEqual(report["capital_policy"], CapitalGridPlan.capital_policy)
            self.assertFalse(report["broker_admission_verified"])
            self.assertNotIn("6", report["stage_fill_counts"])
            self.assertLess(abs(D(report["decimal_reconciliation_residual"])), D("1e-8"))
            plan, entries = profile().plan, 0
            for line in (output / "journal.jsonl").read_text().splitlines()[1:]:
                command = json.loads(line)["command"]
                if command["kind"] != "entry":
                    continue
                entries += 1
                request = command["arguments"]["assessment"]["capital"]["request"]
                index = plan.symbols.index(request["symbol"])
                qty, price = D(request["quantity"]), D(command["arguments"]["price"])
                self.assertEqual(qty, floor_step(qty, plan.contracts[index].quantity_step))
                self.assertEqual(price, floor_step(price, plan.grid_rules[index].price_tick))
            self.assertGreater(entries, 0)
