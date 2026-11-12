"""Financial regressions: real own budgets, no hypothetical empty-slot claims."""
from dataclasses import fields
from decimal import Decimal
import unittest

from investalo_trading.futures_capital_research import CapitalCashPlan, prepare_capital_entry, start_capital_research
from investalo_trading.futures_ledger import ExitFill, FundingSettlement, LedgerMark, MarginPosting
from test_futures_capital_research import start, choose, buy, event, mark

D = Decimal


def cash_start(slots=5):
    original = start(slots)
    plan = CapitalCashPlan(**{f.name: getattr(original.ledger.plan, f.name)
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
