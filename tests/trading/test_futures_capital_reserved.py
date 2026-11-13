"""Own wallet budgets versus funding already charged to isolated margin."""
from datetime import timedelta
from decimal import Decimal
import unittest

from investalo_trading.futures_capital_research import (
    CapitalRealizedCashPlan, CapitalReservedCashPlan, prepare_capital_entry,
)
from investalo_trading.futures_ledger import ExitFill, MarginPosting
from test_futures_capital_cash import cash_start, fund
from test_futures_capital_research import buy, choose, event, mark

D = Decimal


class CapitalReservedCashTests(unittest.TestCase):
    def test_unrestored_funding_is_paid_from_own_isolated_cash_without_account_stop(self):
        for kind, halted in ((CapitalRealizedCashPlan, True), (CapitalReservedCashPlan, False)):
            with self.subTest(policy=kind.capital_policy):
                state = buy(choose(cash_start(plan_type=kind)))
                before = state.ledger
                state = fund(state, ".1")
                b = state.ledger.baskets[0]
                self.assertLess(b.isolated_balance, before.baskets[0].isolated_balance)
                self.assertEqual(state.ledger.unposted_cash, before.unposted_cash)
                self.assertEqual(state.ledger.equity - before.equity, b.funding_net)
                self.assertEqual(state.ledger.halted, halted)
                if not halted:
                    self.assertEqual(state.ledger.plan.basket_cost_usage(b), b.entry_fees)
                    self.assertEqual(state.ledger.plan.stage_capital(b.symbol),
                                     before.plan.stage_capital(b.symbol))
                    state = mark(state, "100", "SYNTH1")
                    state = buy(choose(state, symbol="SYNTH1"), symbol="SYNTH1")
                    self.assertEqual(len(state.stages), 2)

    def test_cost_restoration_leaves_cash_for_remaining_regular_entries_and_exit(self):
        state = buy(choose(cash_start(plan_type=CapitalReservedCashPlan)))
        state = fund(state, ".1")
        plan, b = state.ledger.plan, state.ledger.baskets[0]
        budget, c = plan.budgets[0], plan.contracts[0]
        regular = sum(plan.stage_capital(b.symbol)[:5])
        required = ((regular - b.margin_committed) * b.broker_leverage * c.entry_fee_rate
                    + regular * b.broker_leverage * c.protective_exit_fee_rate)
        capacity = plan.cost_restoration_capacity(b)
        self.assertGreater(capacity, 0)
        self.assertLess(capacity, -b.funding_net)
        state = mark(state, "100")
        before = state.ledger.unposted_cash
        state = event(state, MarginPosting(b.symbol, capacity, True))
        self.assertEqual(before - state.ledger.unposted_cash, capacity)
        self.assertEqual(state.ledger.plan.cost_restoration_capacity(state.ledger.baskets[0]), 0)
        remaining = budget.cost_reserve - plan.basket_cost_usage(state.ledger.baskets[0])
        self.assertEqual(remaining, required)
        self.assertFalse(state.ledger.halted)
        self.assertEqual(state.ledger.baskets[0].margin_committed, b.margin_committed)

    def test_all_twenty_five_buys_and_manual_cash_remain_fully_reserved(self):
        state = cash_start(plan_type=CapitalReservedCashPlan)
        for s in state.ledger.plan.symbols:
            state = mark(state, "100", s)
            state = buy(choose(state, symbol=s), symbol=s)
        for stage in range(2, 6):
            for s in state.ledger.plan.symbols:
                b = state.ledger.baskets[state.ledger.plan.symbols.index(s)]
                state = buy(state, str(b.mark * D(".95")), s)
        self.assertEqual(len(state.stages), 25)
        manual = sum(state.ledger.plan.stage_capital(s)[5] for s in state.ledger.plan.symbols)
        self.assertGreater(state.ledger.unposted_cash, manual)
        with self.assertRaisesRegex(ValueError, "manual reserve"):
            prepare_capital_entry(state, "SYNTH0", state.ledger.baskets[0].mark, state.as_of)

    def test_actual_restoration_overspend_still_halts_without_spending_manual_authority(self):
        state = buy(choose(cash_start(plan_type=CapitalReservedCashPlan)))
        state = fund(state, ".1")
        state = mark(state, "100")
        reserve = state.ledger.plan.budgets[0].cost_reserve
        state = event(state, MarginPosting("SYNTH0", reserve, True))
        self.assertIn("basket_budget_breach", state.ledger.halt_reasons)
        self.assertLess(state.ledger.plan.cost_restoration_capacity(state.ledger.baskets[0]), D(".00000001"))

    def test_funding_margin_deficit_cannot_be_hidden_or_rescued_from_unfilled_stages(self):
        state = buy(choose(cash_start(plan_type=CapitalReservedCashPlan)))
        state = fund(state, ".1")
        state = mark(state, "95")
        assessment = prepare_capital_entry(state, "SYNTH0", D(95), state.as_of)
        self.assertIn("initial_margin_requirement", assessment.reasons)
        self.assertFalse(state.ledger.halted)
        self.assertEqual(len(state.stages), 1)
        # Funding can still exhaust the actual isolated position.
        state = fund(state, "1")
        self.assertIn("SYNTH0", state.liquidation_required)
        self.assertNotIn("basket_budget_breach", state.ledger.halt_reasons)

    def test_close_keeps_funding_loss_and_does_not_credit_restoration_twice(self):
        state = buy(choose(cash_start(plan_type=CapitalReservedCashPlan)))
        state = fund(state, ".1")
        state = mark(state, "100")
        state = event(state, MarginPosting("SYNTH0", D(5), True))
        state = mark(state, "110")
        b = state.ledger.baskets[0]
        expected = b.quantity * (b.mark - b.average_entry) - b.entry_fees - D(".1") + b.funding_net
        state = event(state, ExitFill(b.symbol, b.quantity, b.mark, D(".1")))
        self.assertEqual(state.ledger.realized_net_pnl, expected)
        self.assertFalse(state.ledger.halted)
        state = mark(state, "100")
        state = buy(choose(state))
        self.assertEqual(state.ledger.baskets[0].cycle, 2)
        self.assertEqual(state.ledger.baskets[0].cost_restored, 0)

    def test_profitable_full_exit_retains_q44_and_old_halt_is_terminal(self):
        state = buy(choose(cash_start(plan_type=CapitalReservedCashPlan)))
        state = mark(state, "200")
        b = state.ledger.baskets[0]
        state = event(state, ExitFill(b.symbol, b.quantity, b.mark, D(20)))
        self.assertFalse(state.ledger.halted)
        state = mark(state, "100")
        state = buy(choose(state))
        state = fund(state, ".1")
        state = mark(state, "100")
        state = event(state, MarginPosting("SYNTH0", D(20), True))
        self.assertTrue(state.ledger.halted)
        state = mark(state, "300", at=state.as_of + timedelta(seconds=1))
        b = state.ledger.baskets[0]
        state = event(state, ExitFill(b.symbol, b.quantity, b.mark, D(".1")))
        self.assertTrue(state.ledger.halted)
