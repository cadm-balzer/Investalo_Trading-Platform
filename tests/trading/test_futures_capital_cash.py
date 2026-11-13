"""Financial regressions: real own budgets, no hypothetical empty-slot claims."""
from dataclasses import fields
from decimal import Decimal
import unittest

from investalo_trading.futures_capital_research import (
    CapitalCashPlan, CapitalRealizedCashPlan, prepare_capital_entry, start_capital_research,
)
from investalo_trading.futures_ledger import ExitFill, FundingSettlement, LedgerMark, MarginPosting
from test_futures_capital_research import start, choose, buy, event, mark

D = Decimal


def cash_start(slots=5, plan_type=CapitalCashPlan):
    original = start(slots)
    plan = plan_type(**{f.name: getattr(original.ledger.plan, f.name)
                       for f in fields(original.ledger.plan) if f.init})
    return start_capital_research(plan, tuple(LedgerMark(s, D(100)) for s in plan.symbols),
                                  original.as_of, "cash-budget-initial")


def fund(state, rate):
    state = mark(state, "100")
    return event(state, FundingSettlement("SYNTH0", D(100), D(rate)))


class CapitalCashTests(unittest.TestCase):
    def test_small_closed_loss_allows_four_full_ranges_but_refuses_fifth(self):
        state = buy(choose(cash_start()))
        state = mark(state, "99")
        b = state.ledger.baskets[0]
        state = event(state, ExitFill(b.symbol, b.quantity, b.mark, D(".1")))
        self.assertLess(state.ledger.unposted_cash, D(10000))
        for s in state.ledger.plan.symbols[:4]:
            state = mark(state, "100", s)
            state = buy(choose(state, symbol=s), symbol=s)
        state = mark(state, "100", "SYNTH4")
        state = choose(state, symbol="SYNTH4")
        result = prepare_capital_entry(state, "SYNTH4", D(100), state.as_of)
        self.assertEqual(result.reasons, ("insufficient_unposted_cash",))
        self.assertEqual(sum(bool(b.quantity) for b in state.ledger.baskets), 4)
        self.assertFalse(state.ledger.halted)

    def test_five_initial_ranges_and_all_five_regular_stages_remain_funded(self):
        state = cash_start()
        for s in state.ledger.plan.symbols:
            state = mark(state, "100", s)
            state = buy(choose(state, symbol=s), symbol=s)
        for stage in range(2, 6):
            for s in state.ledger.plan.symbols:
                b = state.ledger.baskets[state.ledger.plan.symbols.index(s)]
                state = buy(state, str(b.mark * D(".95")), s)
        self.assertEqual(len(state.stages), 25)
        self.assertGreater(state.ledger.unposted_cash, D(5) * state.ledger.plan.stage_capital("SYNTH0")[5])
        with self.assertRaisesRegex(ValueError, "manual reserve"):
            prepare_capital_entry(state, "SYNTH0", state.ledger.baskets[0].mark, state.as_of)

    def test_received_funding_covers_later_gross_debits_and_exit_stays_valid(self):
        state = buy(choose(cash_start()))
        state = fund(state, "-.15")
        state = fund(state, ".10")
        b = state.ledger.baskets[0]
        self.assertGreater(b.charges_in_budget_epoch, state.ledger.plan.budgets[0].cost_reserve)
        self.assertGreater(b.funding_net, 0)
        self.assertEqual(state.ledger.plan.basket_cost_usage(b), b.entry_fees)
        self.assertFalse(state.ledger.halted)
        state = event(state, ExitFill(b.symbol, b.quantity, b.mark, D(".1")))
        self.assertFalse(state.ledger.halted)
        self.assertGreater(state.ledger.realized_net_pnl, 0)

    def test_uncovered_net_funding_and_paid_restoration_keep_real_budget_gate(self):
        state = buy(choose(cash_start()))
        state = fund(state, ".01")
        b = state.ledger.baskets[0]
        debit = -b.funding_net
        state = event(state, MarginPosting("SYNTH0", debit, True))
        self.assertEqual(state.ledger.plan.basket_cost_usage(state.ledger.baskets[0]),
                         b.entry_fees + debit)
        state = fund(state, "-.02")
        self.assertEqual(state.ledger.plan.basket_cost_usage(state.ledger.baskets[0]),
                         b.entry_fees + debit)
        state = fund(state, ".1")
        self.assertIn("basket_budget_breach", state.ledger.halt_reasons)

    def test_historical_gross_budget_policy_is_preserved(self):
        state = buy(choose(start(5)))
        state = fund(state, "-.15")
        state = fund(state, ".10")
        self.assertIn("basket_budget_breach", state.ledger.halt_reasons)
        self.assertNotEqual(state.ledger.plan.plan_digest, cash_start().ledger.plan.plan_digest)


class CapitalRealizedCashTests(unittest.TestCase):
    def test_full_profitable_exit_covers_only_own_cost_overrun_and_old_policy_stays_strict(self):
        for plan_type, halted in ((CapitalCashPlan, True), (CapitalRealizedCashPlan, False)):
            with self.subTest(plan=plan_type.__name__):
                state = buy(choose(cash_start(plan_type=plan_type)))
                state = mark(state, "110")
                b = state.ledger.baskets[0]
                state = event(state, ExitFill(b.symbol, b.quantity, b.mark, D(20)))
                self.assertEqual(state.ledger.halted, halted)
                self.assertGreater(state.ledger.realized_net_pnl, 0)
                self.assertEqual(state.ledger.realized_net_pnl,
                                 b.quantity * (b.mark - b.average_entry) - b.entry_fees - D(20))
                self.assertEqual(state.ledger.baskets[0].quantity, 0)
                if not halted:
                    state = mark(state, "100")
                    state = buy(choose(state))
                    self.assertEqual(state.ledger.baskets[0].cycle, 2)
                    self.assertEqual(state.ledger.plan.stage_capital(b.symbol),
                                     cash_start().ledger.plan.stage_capital(b.symbol))

    def test_losing_full_exit_cannot_use_another_baskets_profit(self):
        state = cash_start(plan_type=CapitalRealizedCashPlan)
        state = buy(choose(state, symbol="SYNTH1"), symbol="SYNTH1")
        state = mark(state, "200", "SYNTH1")
        other = state.ledger.baskets[1]
        state = event(state, ExitFill(other.symbol, other.quantity, other.mark, D(".1")))
        self.assertGreater(state.ledger.realized_net_pnl, 0)
        state = mark(state, "100")
        state = buy(choose(state))
        state = mark(state, "99")
        b = state.ledger.baskets[0]
        previous_realized = state.ledger.realized_net_pnl
        state = event(state, ExitFill(b.symbol, b.quantity, b.mark, D(20)))
        self.assertIn("basket_budget_breach", state.ledger.halt_reasons)
        self.assertGreater(state.ledger.realized_net_pnl, 0)
        self.assertLess(state.ledger.realized_net_pnl - previous_realized, 0)

    def test_partial_profitable_exit_cannot_cover_open_cost_budget(self):
        state = buy(choose(cash_start(plan_type=CapitalRealizedCashPlan)))
        state = mark(state, "200")
        b = state.ledger.baskets[0]
        state = event(state, ExitFill(b.symbol, b.quantity / 2, b.mark, D(20)))
        self.assertGreater(state.ledger.baskets[0].realized_price_pnl, 0)
        self.assertIn("basket_budget_breach", state.ledger.halt_reasons)

    def test_unrealized_profit_and_later_exit_do_not_clear_open_budget_halt(self):
        state = buy(choose(cash_start(plan_type=CapitalRealizedCashPlan)))
        state = mark(state, "200")
        state = event(state, FundingSettlement("SYNTH0", D(200), D(".1")))
        self.assertIn("basket_budget_breach", state.ledger.halt_reasons)
        state = mark(state, "300")
        b = state.ledger.baskets[0]
        state = event(state, ExitFill(b.symbol, b.quantity, b.mark, D(".1")))
        self.assertGreater(state.ledger.realized_net_pnl, 0)
        self.assertIn("basket_budget_breach", state.ledger.halt_reasons)

    def test_small_positive_net_profit_must_cover_the_whole_overrun(self):
        from investalo_trading.models import precise
        @precise
        def price(b):
            return b.average_entry + (b.entry_fees + D(21) + D(1)) / b.quantity
        state = buy(choose(cash_start(plan_type=CapitalRealizedCashPlan)))
        state = mark(state, str(price(state.ledger.baskets[0])))
        b = state.ledger.baskets[0]
        state = event(state, ExitFill(b.symbol, b.quantity, b.mark, D(21)))
        self.assertGreater(state.ledger.realized_net_pnl, 0)
        self.assertLess(state.ledger.realized_net_pnl, D(2))
        self.assertIn("basket_budget_breach", state.ledger.halt_reasons)

    def test_full_six_stage_budget_and_manual_reserve_are_unchanged(self):
        state = cash_start(plan_type=CapitalRealizedCashPlan)
        for s in state.ledger.plan.symbols:
            state = mark(state, "100", s)
            state = buy(choose(state, symbol=s), symbol=s)
        for _ in range(4):
            for s in state.ledger.plan.symbols:
                b = state.ledger.baskets[state.ledger.plan.symbols.index(s)]
                state = buy(state, str(b.mark * D(".95")), s)
        self.assertEqual(len(state.stages), 25)
        self.assertFalse(state.ledger.halted)
        self.assertGreater(state.ledger.unposted_cash, D(5) * state.ledger.plan.stage_capital("SYNTH0")[5])
        self.assertNotEqual(state.ledger.plan.plan_digest, cash_start().ledger.plan.plan_digest)
