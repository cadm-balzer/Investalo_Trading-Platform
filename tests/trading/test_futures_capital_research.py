"""Declared synthetic capital mechanics; no historical RSI or AI performance."""
from dataclasses import FrozenInstanceError, replace
from datetime import timedelta
from decimal import Decimal
import unittest

from investalo_trading.futures_capital_research import (
    CapitalPlan, equal_capital_plan, freeze_basket_leverage, prepare_capital_entry,
    record_capital_event, simulate_capital_fill, start_capital_research,
)
from investalo_trading.futures_ledger import (
    DailyBasis, EntryFill, ExitFill, FundingSettlement, LedgerMark, LiquidatedBasket,
    LiquidationSettlement, MarginPosting, MarkBatch, apply_futures_event,
)
from investalo_trading.models import precise
from investalo_trading.futures_pending import start_long_pending_research, start_pending_research
from investalo_trading.futures_signals import FIRST_FILL_MODEL, ReplayProfile
from test_futures_ledger import AT, command, fixture, step

D = Decimal


def start(slots=3, capacity=50000):
    legacy = fixture(slots)
    plan = equal_capital_plan("tenant", "account", "declared-static-research",
                              legacy.plan.contracts)
    return start_capital_research(
        plan, tuple(LedgerMark(s, D("100")) for s in plan.symbols), AT,
        "synthetic-initial-marks", identity_capacity=capacity,
    )


def choose(state, leverage="2", symbol="SYNTH0"):
    return freeze_basket_leverage(
        state, symbol, D(leverage), f"declared-leverage-{leverage}",
        f"decision-{state.revision}", state.revision, state.as_of,
    )


def event(state, payload, at=None, event_id=None):
    return record_capital_event(
        state, payload, event_id or f"event-{state.revision}", state.revision,
        at or state.as_of,
    )


def mark(state, price, symbol="SYNTH0", at=None):
    return event(state, MarkBatch(tuple(
        LedgerMark(b.symbol, D(price) if b.symbol == symbol else b.mark)
        for b in state.ledger.baskets)),
        at or state.as_of + timedelta(seconds=1))


def buy(state, price=None, symbol="SYNTH0"):
    b = state.ledger.baskets[state.ledger.plan.symbols.index(symbol)]
    if price is not None:
        state = mark(state, price, symbol)
        b = state.ledger.baskets[state.ledger.plan.symbols.index(symbol)]
    assessment = prepare_capital_entry(state, symbol, b.mark, state.as_of)
    if not assessment.allowed:
        raise AssertionError(assessment.reasons)
    return simulate_capital_fill(state, assessment, b.mark,
                                 f"fill-{state.revision}", state.revision, state.as_of)


@precise
def liquidation(state, price="80"):
    b = state.ledger.baskets[0]
    price = D(price)
    fee = b.quantity * price * D(".001")
    net = b.isolated_balance + b.quantity * (price - b.average_entry) - fee
    # Explicit synthetic terminal evidence, not the reducer assuming insurance.
    credit = max(D("0"), -net)
    return LiquidationSettlement(b.symbol, b.quantity, price, fee,
                                 net + credit, credit, "synthetic-terminal-receipt")


class CapitalResearchTests(unittest.TestCase):
    def test_three_slot_budget_matches_confirmed_table_and_rounding(self):
        plan = start().ledger.plan
        self.assertEqual(plan.stage_capital("SYNTH0"), tuple(map(D, (
            "293.13365892", "366.41707366", "458.02134207",
            "572.52667759", "715.65834699", "894.57293374",
        ))))
        self.assertEqual(plan.budgets[0].margin_capital, D("3300.330033"))
        self.assertEqual(plan.budgets[0].cost_reserve, D("33.00330033"))
        self.assertEqual(plan.remainder, D(".00000001"))

    def test_all_capital_is_funded_for_three_to_seven_slots(self):
        for slots in range(3, 8):
            with self.subTest(slots=slots):
                plan = start(slots).ledger.plan
                self.assertEqual(sum(b.capital for b in plan.budgets) + plan.remainder,
                                 plan.initial_equity)
                self.assertLessEqual(sum(plan.stage_capital(plan.symbols[0])),
                                     plan.budgets[0].margin_capital)

    def test_capital_policy_has_distinct_identity_and_no_legacy_conversion(self):
        state = start()
        plan = state.ledger.plan
        legacy = fixture().plan
        matching = replace(legacy, budgets=plan.budgets, remainder=plan.remainder,
                           policy_digest=plan.policy_digest)
        self.assertNotEqual(plan.plan_digest, matching.plan_digest)
        with self.assertRaisesRegex(ValueError, "explicit capital"):
            start_capital_research(matching, tuple(LedgerMark(s, D("100"))
                                  for s in matching.symbols), AT, "evidence")
        with self.assertRaisesRegex(ValueError, "complete funded"):
            replace(plan, remainder=plan.remainder + 1)

    def test_legacy_signal_adapter_rejects_new_policy(self):
        plan = start().ledger.plan
        with self.assertRaisesRegex(ValueError, "frozen futures plan"):
            ReplayProfile(plan, tuple((s, D("0")) for s in plan.symbols), D("0"),
                          "declared-profile", FIRST_FILL_MODEL)
        for start_wrapper in (start_pending_research, start_long_pending_research):
            with self.subTest(wrapper=start_wrapper.__name__):
                with self.assertRaises(ValueError):
                    start_wrapper(start().ledger)

    def test_recorded_cost_overrun_is_not_hidden_by_warning_policy(self):
        state = buy(choose(start(), "10"))
        state = mark(state, "110")
        b = state.ledger.baskets[0]
        state = event(state, ExitFill("SYNTH0", b.quantity, D("110"), D("40")))
        self.assertGreater(state.ledger.realized_net_pnl, 0)
        self.assertIn("basket_budget_breach", state.ledger.halt_reasons)

    def test_nominal_uses_selected_leverage_with_same_own_capital(self):
        for leverage in ("2", "5", "10"):
            with self.subTest(leverage=leverage):
                state = choose(start(), leverage)
                result = prepare_capital_entry(state, "SYNTH0", D("100"), state.as_of)
                self.assertTrue(result.allowed, result.reasons)
                self.assertEqual(result.request.posted_margin, D("293.13365892"))
                nominal = result.request.quantity * result.request.maximum_fill_price
                self.assertLessEqual(nominal, D("293.13365892") * D(leverage))
                self.assertLess(D("293.13365892") * D(leverage) - nominal, D(".01"))
                self.assertIn("isolated_stress_liquidation", result.diagnostics)
                self.assertFalse(result.execution_enabled)

    def test_leverage_decision_is_required_before_entry(self):
        with self.assertRaisesRegex(ValueError, "freeze leverage"):
            prepare_capital_entry(start(), "SYNTH0", D("100"), AT)

    def test_decision_cannot_change_before_fill_or_during_basket(self):
        state = choose(start(), "5")
        for candidate in (state, buy(state)):
            with self.subTest(filled=bool(candidate.stages)):
                with self.assertRaisesRegex(ValueError, "frozen|open"):
                    choose(candidate, "10")
        with self.assertRaises(FrozenInstanceError):
            state.decisions[0].leverage = D("10")

    def test_out_of_range_and_backdated_decisions_rejected(self):
        for leverage in ("1", "11", "NaN"):
            with self.subTest(leverage=leverage):
                with self.assertRaises(ValueError):
                    choose(start(), leverage)
        state = mark(start(), "100")
        with self.assertRaisesRegex(ValueError, "backdated"):
            freeze_basket_leverage(state, "SYNTH0", D("2"), "evidence",
                                   "decision", state.revision, AT)

    def test_five_entries_keep_capital_weights_and_frozen_leverage(self):
        state = choose(start())
        for stage in range(5):
            state = buy(state, D("100") * D(".95") ** stage)
            self.assertEqual(state.ledger.baskets[0].broker_leverage, D("2"))
            self.assertEqual(state.stages[-1].stage, stage + 1)
            self.assertFalse(state.ledger.halted)
        self.assertEqual(state.ledger.baskets[0].margin_committed, D("2405.75709923"))
        with self.assertRaisesRegex(ValueError, "manual reserve"):
            prepare_capital_entry(state, "SYNTH0", state.ledger.baskets[0].mark, state.as_of)

    def test_account_warnings_do_not_force_exit_or_block_other_basket(self):
        state = choose(choose(start(), "10"), "2", "SYNTH1")
        for stage in range(4):
            state = buy(state, D("100") * D(".95") ** stage)
        state = mark(state, "82")
        self.assertIn("SYNTH0", state.liquidation_required)
        self.assertIn("initial_loss_limit", state.warnings)
        self.assertFalse(state.ledger.halted)
        blocked = prepare_capital_entry(state, "SYNTH1", D("100"), state.as_of)
        self.assertIn("liquidation_requires_settlement", blocked.reasons)
        state = event(state, liquidation(state))
        self.assertFalse(state.ledger.halted)
        admitted = prepare_capital_entry(state, "SYNTH1", D("100"),
                                        state.as_of + timedelta(microseconds=1))
        self.assertTrue(admitted.allowed, admitted.reasons)
        # No refilling the lost margin allocation or consuming leftover dead-slot reserve.
        self.assertEqual(state.stopped[0].unposted_stage_capital, D("1610.23128076"))
        with self.assertRaisesRegex(ValueError, "liquidated"):
            prepare_capital_entry(state, "SYNTH0", D("82"),
                                  state.as_of + timedelta(microseconds=1))

    def test_three_parallel_full_ladders_can_cross_warning_thresholds(self):
        state = start()
        for symbol in state.ledger.plan.symbols:
            state = choose(state, symbol=symbol)
        for stage in range(5):
            price = D("100") * D(".95") ** stage
            state = event(state, MarkBatch(tuple(LedgerMark(s, price)
                          for s in state.ledger.plan.symbols)),
                          state.as_of + timedelta(seconds=1))
            for symbol in state.ledger.plan.symbols:
                state = buy(state, symbol=symbol)
        self.assertEqual(len(state.stages), 15)
        self.assertIn("initial_loss_limit", state.warnings)
        self.assertFalse(state.ledger.halted)
        self.assertEqual(sum(b.margin_committed for b in state.ledger.baskets),
                         D("7217.27129769"))

    def test_liquidation_requires_explicit_reconciled_terminal_balance(self):
        state = mark(buy(choose(start(), "10")), "80")
        payload = liquidation(state)
        before = state.state_digest
        with self.assertRaisesRegex(ValueError, "does not reconcile"):
            event(state, replace(payload, insurance_credit=D("0")))
        self.assertEqual(state.state_digest, before)
        settled = event(state, payload)
        self.assertEqual(settled.ledger.baskets[0].quantity, 0)
        self.assertEqual(settled.ledger.unposted_cash, state.ledger.unposted_cash)
        self.assertEqual(settled.ledger.realized_net_pnl,
                         -state.ledger.baskets[0].margin_committed
                         -state.ledger.baskets[0].entry_fees)
        self.assertEqual(settled.ledger.closed_baskets, 1)
        self.assertFalse(settled.ledger.halted)

    def test_positive_terminal_margin_is_returned(self):
        state = mark(buy(choose(start(), "10")), "90")
        payload = liquidation(state, "90.54")
        self.assertGreater(payload.returned_margin, 0)
        settled = event(state, payload)
        self.assertEqual(settled.ledger.unposted_cash - state.ledger.unposted_cash,
                         payload.returned_margin)
        self.assertIn("SYNTH0", tuple(r.symbol for r in settled.stopped))

    def test_liquidation_is_full_only_and_not_accepted_by_legacy_plan(self):
        state = buy(choose(start(), "10"))
        payload = liquidation(state)
        with self.assertRaisesRegex(ValueError, "entire basket"):
            event(state, replace(payload, quantity=payload.quantity - D(".0001")))
        old = fixture()
        with self.assertRaisesRegex(ValueError, "separate capital"):
            step(old, payload)

    def test_closed_liquidation_profit_includes_explicit_insurance_credit(self):
        state = mark(buy(choose(start(), "10")), "80")
        payload = liquidation(state)
        closed = apply_futures_event(state.ledger, command(state.ledger, payload)).closed
        self.assertIsInstance(closed, LiquidatedBasket)
        self.assertGreater(closed.insurance_credit, 0)
        self.assertEqual(closed.net_pnl,
                         -state.ledger.baskets[0].margin_committed
                         -state.ledger.baskets[0].entry_fees)

    def test_funding_is_booked_and_only_explicit_cost_restoration_allowed(self):
        state = buy(choose(start()))
        state = mark(state, "100")
        state = event(state, FundingSettlement("SYNTH0", D("100"), D(".001")),
                      state.as_of)
        self.assertLess(state.ledger.baskets[0].funding_net, 0)
        with self.assertRaisesRegex(ValueError, "extra margin"):
            event(state, MarginPosting("SYNTH0", D("1")))
        debit = state.ledger.baskets[0].margin_committed - state.ledger.baskets[0].isolated_balance
        state = event(state, MarginPosting("SYNTH0", debit, True))
        self.assertEqual(state.ledger.baskets[0].isolated_balance,
                         state.ledger.baskets[0].margin_committed)

    def test_current_initial_margin_and_cost_limits_still_apply(self):
        state = buy(choose(start(), "2"))
        state = mark(state, "120")
        result = prepare_capital_entry(state, "SYNTH0", D("120"), state.as_of)
        self.assertFalse(result.allowed)
        self.assertIn("initial_margin_requirement", result.reasons)
        poor = replace(start().ledger.plan, budgets=tuple(
            replace(b, cost_reserve=D(".001")) for b in start().ledger.plan.budgets))
        candidate = start_capital_research(poor, tuple(LedgerMark(s, D("100"))
                    for s in poor.symbols), AT, "evidence")
        result = prepare_capital_entry(choose(candidate, "10"), "SYNTH0", D("100"), AT)
        self.assertIn("basket_capital_or_cost_limit", result.reasons)

    def test_new_cycle_can_choose_new_leverage_after_normal_exit(self):
        state = buy(choose(start(), "2"))
        state = mark(state, "110")
        b = state.ledger.baskets[0]
        state = event(state, ExitFill("SYNTH0", b.quantity, D("110"),
                                     b.quantity * D("110") * D(".001")))
        state = choose(state, "5")
        self.assertEqual(tuple(d.leverage for d in state.decisions), (D("2"), D("5")))
        request = prepare_capital_entry(state, "SYNTH0", D("110"),
                                       state.as_of + timedelta(microseconds=1)).request
        self.assertEqual(request.requested_leverage, D("5"))

    def test_new_cycles_get_fresh_cost_reserves_without_refunding_paid_fees(self):
        state = start()
        for cycle in range(35):
            state = choose(state)
            state = buy(state, "100")
            state = mark(state, "110")
            b = state.ledger.baskets[0]
            state = event(state, ExitFill(
                "SYNTH0", b.quantity, D("110"), b.quantity * D("110") * D(".001")))
            self.assertFalse(state.ledger.halted)
            self.assertEqual(state.ledger.baskets[0].charges_in_budget_epoch, 0)
            self.assertEqual(state.ledger.baskets[0].cycle, cycle + 1)
            self.assertEqual(state.ledger.equity,
                             state.ledger.plan.initial_equity + state.ledger.realized_net_pnl)
        # Cumulative fees exceed the one-cycle reserve, yet each actual cycle
        # was funded and net PnL already includes every paid fee.
        self.assertEqual(state.ledger.closed_baskets, 35)

    def test_stale_foreign_or_over_bound_fill_is_rejected(self):
        state = choose(start())
        result = prepare_capital_entry(state, "SYNTH0", D("100"), state.as_of)
        with self.assertRaisesRegex(ValueError, "price bound"):
            simulate_capital_fill(state, result, D("101"), "fill", state.revision, state.as_of)
        with self.assertRaisesRegex(ValueError, "changed"):
            simulate_capital_fill(state, result, D("100"), "fill", state.revision,
                                  state.as_of + timedelta(seconds=31))
        other = choose(start(), "5")
        with self.assertRaisesRegex(ValueError, "stale"):
            simulate_capital_fill(other, result, D("100"), "fill", other.revision, other.as_of)

    def test_duplicate_events_and_capacity_exhaustion_never_evict(self):
        state = choose(start())
        state = mark(state, "100")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            event(state, MarkBatch(tuple(LedgerMark(s, D("100"))
                  for s in state.ledger.plan.symbols)),
                  state.as_of + timedelta(seconds=1), "event-1")
        full = choose(start(capacity=1))
        with self.assertRaisesRegex(ValueError, "capacity"):
            mark(full, "100")
        self.assertEqual(len(full.event_ids), 1)
        self.assertEqual(full.ledger.revision, 0)

    def test_day_basis_requires_exact_midnight_and_original_equity_stays_fixed(self):
        state = buy(choose(start()))
        midnight = AT + timedelta(days=1)
        state = mark(state, "95", at=midnight)
        result = prepare_capital_entry(state, "SYNTH0", D("95"), midnight)
        self.assertIn("invalid_day_basis", result.reasons)
        equity = state.ledger.equity
        state = event(state, DailyBasis(equity, "synthetic-midnight"), midnight)
        self.assertEqual(state.ledger.day_start_equity, equity)
        self.assertEqual(state.ledger.plan.initial_equity, D("10000"))
        self.assertTrue(prepare_capital_entry(state, "SYNTH0", D("95"), midnight).allowed)

    def test_legacy_limits_still_latch_and_no_broad_profile_conversion(self):
        old = fixture()
        old = step(old, EntryFill("SYNTH0", D("10"), D("100"),
                                 D("1000"), D("1"), D("2"))).state
        old = step(old, MarkBatch(tuple(
            LedgerMark(b.symbol, D("20") if b.symbol == "SYNTH0" else b.mark)
            for b in old.baskets)), at=AT + timedelta(seconds=1)).state
        self.assertIn("daily_loss_limit", old.halt_reasons)
        self.assertIn("initial_loss_limit", old.halt_reasons)


if __name__ == "__main__":
    unittest.main()
