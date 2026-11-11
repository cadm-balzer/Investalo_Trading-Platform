"""Synthetic endpoint bounds, not executable broker orders or historical returns."""
from dataclasses import FrozenInstanceError, replace
from datetime import timedelta
from decimal import Decimal, localcontext
import unittest

from investalo_trading.futures_continuation import ContinuationScenario, assess_futures_continuation
from investalo_trading.futures_economics import MarginSchedule, MarginTier
from investalo_trading.futures_ledger import (
    DailyBasis, ExitFill, FundingSettlement, LedgerMark, MarginPosting, MarkBatch,
)
from investalo_trading.futures_pending import (
    MAX_IDENTITIES, record_fill, record_ledger_event, start_pending_research,
)
from test_futures_ledger import AT, buy, fixture
from test_futures_pending import attempted, fill, terminal

D = Decimal


def scenario(state, *, floor="100"):
    p, plan = state.pending, state.ledger.plan
    return ContinuationScenario(
        plan.tenant_id, plan.account_id, plan.plan_digest, state.revision,
        p.intent_id, p.order_id,
        tuple(LedgerMark(b.symbol, min(b.mark, D(floor))) for b in state.ledger.baskets),
    )


def assess(state, *, floor="100", at=None):
    return assess_futures_continuation(state, scenario(state, floor=floor), at or state.as_of)


def event(state, payload, at, event_id):
    return record_ledger_event(state, payload, event_id, state.revision, at).state


def mark(state, price="100", *, at=None):
    at = at or state.as_of + timedelta(seconds=1)
    return event(state, MarkBatch(tuple(LedgerMark(b.symbol, D(price)) for b in state.ledger.baskets)),
                 at, f"mark-{state.revision}")


class FuturesContinuationTests(unittest.TestCase):
    def test_remaining_fill_is_covered_only_with_margin_already_posted(self):
        state = fill(attempted())
        a = assess(state)
        self.assertTrue(a.risk_covered, a.reasons)
        self.assertEqual(a.remaining_quantity, D(".5"))
        self.assertEqual(a.projected_remaining_fee, D(".05"))
        self.assertEqual(a.available_isolated_balance, D("60"))
        self.assertEqual(a.required_isolated_balance, D("50.30000001"))
        self.assertEqual(a.additional_margin_required, 0)
        self.assertEqual(a.projected_equity, D("9999.9"))
        self.assertEqual(a.gap_equity_after, D("9949.9"))
        self.assertEqual(a.stress_loss, 50)
        self.assertTrue(a.requires_reconciliation)
        self.assertFalse(a.execution_enabled)
        self.assertIsNotNone(state.pending)

    def test_unposted_margin_reservation_cannot_cover_immediate_gap(self):
        state = fill(attempted(), margin="30")
        a = assess(state)
        self.assertEqual(a.unconsumed_intent_margin, 30)
        self.assertEqual(a.available_isolated_balance, 30)
        self.assertIn("remaining_fill_gap_liquidation", a.reasons)
        self.assertIn("remaining_initial_margin_requirement", a.reasons)
        self.assertEqual(a.additional_margin_required, D("20.30000001"))
        self.assertFalse(a.risk_covered)

    def test_declared_actual_own_margin_posting_can_cover_remaining_quantity(self):
        state = mark(fill(attempted(), margin="30"))
        before = assess(state)
        state = event(state, MarginPosting("SYNTH0", D("30")), state.as_of, "actual-own-margin")
        after = assess(state)
        self.assertFalse(before.risk_covered)
        self.assertTrue(after.risk_covered, after.reasons)
        self.assertEqual(after.available_isolated_balance, 60)
        self.assertEqual(before.current_equity, after.current_equity)
        self.assertEqual(after.unconsumed_intent_margin, 30)  # bookkeeping, not a cash transfer

    def test_request_price_ceiling_does_not_invent_first_fill_or_buffer_timing(self):
        state = attempted()
        a = assess(state)
        self.assertIn("first_fill_or_posted_buffer_unproven", a.reasons)
        self.assertFalse(a.risk_covered)
        self.assertEqual(a.available_isolated_balance, 0)
        self.assertEqual(a.unconsumed_intent_margin, 60)

    def test_existing_position_anchor_is_used_before_first_fragment_of_additional_order(self):
        state = start_pending_research(buy(fixture(), margin="120"))
        state = attempted(state, margin="60")
        a = assess(state)
        self.assertTrue(a.risk_covered, a.reasons)
        self.assertNotIn("first_fill_or_posted_buffer_unproven", a.reasons)
        self.assertEqual(a.available_isolated_balance, 120)
        self.assertEqual(a.unconsumed_intent_margin, 60)
        self.assertEqual(a.effective_gap_marks[0].price, 50)

    def test_low_first_fragment_blocks_upper_price_rest_before_it_is_filled(self):
        state = fill(attempted(quantity="10", margin="600"), quantity=".0001", price="1",
                     margin="600", fee=".0000001")
        a = assess(state)
        self.assertEqual(state.ledger.baskets[0].first_fill, 1)
        self.assertEqual(a.effective_gap_marks[0].price, D(".5"))
        self.assertEqual(a.remaining_quantity, D("9.9999"))
        self.assertIn("remaining_fill_gap_liquidation", a.reasons)
        self.assertIn("correlated_remaining_fill_stress", a.reasons)
        self.assertFalse(a.risk_covered)

    def test_first_fill_is_not_reset_when_later_fragment_is_cheaper(self):
        state = fill(attempted(quantity="2", margin="120"), quantity=".5", margin="120")
        state = mark(state, "90")
        state = fill(state, quantity=".5", price="90", margin="0", fee=".045", fill_id="fill-2")
        a = assess(state, floor="90")
        self.assertEqual(state.ledger.baskets[0].average_entry, 95)
        self.assertEqual(a.effective_gap_marks[0].price, 50)
        self.assertEqual(a.remaining_quantity, 1)
        self.assertTrue(a.risk_covered, a.reasons)

    def test_gap_at_current_position_is_checked_before_any_remaining_fill(self):
        state = fill(attempted(), margin="30")
        a = assess(state, floor="10")
        self.assertIn("pre_fill_gap_liquidation", a.reasons)
        self.assertFalse(a.risk_covered)

    def test_gap_below_fifty_percent_is_never_clamped_back_up(self):
        state = fill(attempted())
        a = assess(state, floor="20")
        self.assertEqual(a.effective_gap_marks[0].price, 20)
        self.assertIn("remaining_fill_gap_liquidation", a.reasons)
        self.assertGreater(a.required_isolated_balance, 80)
        self.assertEqual(a.stress_loss, 80)

    def test_already_posted_own_buffer_can_cover_a_larger_declared_gap(self):
        state = fill(attempted(margin="100"), margin="100")
        a = assess(state, floor="20")
        self.assertTrue(a.risk_covered, a.reasons)
        self.assertEqual(a.required_isolated_balance, D("80.12000001"))
        self.assertEqual(a.additional_margin_required, 0)
        self.assertEqual(a.gap_equity_after, D("9919.9"))

    def test_prior_normal_close_loss_blocks_full_budget_backing_without_permanent_halt(self):
        ledger = buy(fixture(), symbol="SYNTH1")
        state = fill(attempted(start_pending_research(ledger)))
        at = AT + timedelta(seconds=1)
        state = record_fill(state, ExitFill("SYNTH1", D("1"), D("90"), D(".09")),
                            "other-exit", "other-exit-fill", state.revision, at).state
        state = mark(state)
        a = assess(state)
        self.assertIn("insufficient_unposted_cash", a.reasons)
        self.assertNotIn("account_halted", a.reasons)
        self.assertFalse(a.risk_covered)
        self.assertEqual(state.ledger.plan.initial_equity, 10000)

    def test_funding_debit_reduces_available_collateral_without_invented_restoration(self):
        state = mark(fill(attempted(), margin="30"))
        state = event(state, FundingSettlement("SYNTH0", D("100"), D(".2")), state.as_of, "funding")
        a = assess(state)
        self.assertEqual(a.available_isolated_balance, 20)
        self.assertIn("remaining_fill_gap_liquidation", a.reasons)
        self.assertEqual(state.ledger.baskets[0].margin_committed, 30)
        state = event(state, MarginPosting("SYNTH0", D("10"), True), state.as_of, "restoration")
        b = assess(state)
        self.assertEqual(b.available_isolated_balance, 30)
        self.assertFalse(b.risk_covered)  # restored original30 still cannot cover full order
        self.assertEqual(a.projected_equity, b.projected_equity)

    def test_funding_credit_can_back_collateral_but_does_not_grow_the_original_budget(self):
        state = mark(fill(attempted(), margin="30"))
        state = event(state, FundingSettlement("SYNTH0", D("100"), D("-.6")), state.as_of, "credit")
        a = assess(state)
        self.assertTrue(a.risk_covered, a.reasons)
        self.assertEqual(a.available_isolated_balance, 60)
        self.assertEqual(state.ledger.baskets[0].margin_committed, 30)
        self.assertEqual(state.ledger.plan.budgets[0].capital, 3000)

    def test_other_baskets_contribute_correlated_gap_loss_without_cross_margin(self):
        ledger = buy(fixture(), quantity="7", margin="800", symbol="SYNTH1", fee=".7")
        state = fill(attempted(start_pending_research(ledger)))
        a = assess(state)
        self.assertTrue(a.risk_covered, a.reasons)
        self.assertEqual(a.stress_loss, 400)
        # The other basket's own margin cannot rescue the target, and its
        # larger gap contributes to the same account limit.
        s = replace(scenario(state), minimum_marks=tuple(
            LedgerMark(b.symbol, D("15") if b.symbol == "SYNTH1" else D("100"))
            for b in state.ledger.baskets))
        b = assess_futures_continuation(state, s, state.as_of)
        self.assertIn("pre_fill_gap_account_loss", b.reasons)
        self.assertIn("correlated_remaining_fill_stress", b.reasons)
        self.assertEqual(b.available_isolated_balance, 60)

    def test_hypothetical_cheap_remainder_profit_cannot_heal_zero_fill_cost_shortfall(self):
        state = start_pending_research(buy(fixture(), quantity=".5", margin="60", fee=".05"))
        state = mark(state, "40")
        state = fill(attempted(state, quantity="5", price="40", margin="600"),
                     quantity=".5", price="40", margin="600", fee=".02")
        midnight = AT + timedelta(days=1)
        state = mark(state, "654.91", at=midnight)
        state = event(state, DailyBasis(state.ledger.equity, "synthetic-h4-midnight"),
                      midnight, "midnight")
        state = mark(state, "70")
        a = assess(state, floor="50")
        account_floor = state.ledger.day_start_equity * D(".94")
        self.assertEqual(state.ledger.day_start_equity, D("10584.84"))
        self.assertEqual(a.gap_equity_before, D("9979.75"))
        self.assertEqual(a.gap_equity_after, D("10024.75"))
        self.assertGreater(a.gap_equity_before, account_floor)
        self.assertNotIn("correlated_remaining_fill_stress", a.reasons)
        self.assertNotIn("pre_fill_gap_account_loss", a.reasons)
        self.assertIn("pre_fill_gap_cost_coverage", a.reasons)
        self.assertFalse(a.risk_covered)

    def test_maintenance_tier_boundary_uses_full_remaining_exposure(self):
        ledger = fixture()
        contracts = list(ledger.plan.contracts)
        contracts[0] = replace(contracts[0], schedule=MarginSchedule((
            MarginTier(D("100"), D(".005"), D("20")),
            MarginTier(D("1000000"), D(".05"), D("2")),
        )))
        plan = replace(ledger.plan, contracts=tuple(contracts))
        state = fill(attempted(start_pending_research(replace(ledger, plan=plan))))
        a = assess(state)
        self.assertEqual(a.required_isolated_balance, D("52.55000001"))
        self.assertTrue(a.risk_covered, a.reasons)

    def test_contract_cap_or_missing_tier_blocks_remainder(self):
        for schedule, reason in (
                (MarginSchedule((MarginTier(D("1000000"), D(".005"), D("1")),)),
                 "contract_leverage_limit"),
                (MarginSchedule((MarginTier(D("100"), D(".005"), D("20")),)),
                 "missing_or_invalid_margin_coverage")):
            state = fill(attempted())
            contracts = list(state.ledger.plan.contracts)
            contracts[0] = replace(contracts[0], schedule=schedule)
            # Contradictory synthetic trusted input, not a permitted update
            # of a frozen live/research profile.
            plan = replace(state.ledger.plan, contracts=tuple(contracts))
            state = replace(state, ledger=replace(state.ledger, plan=plan),
                            pending=replace(state.pending, request=replace(
                                state.pending.request, plan_digest=plan.plan_digest)))
            a = assess(state)
            self.assertIn(reason, a.reasons)
            self.assertFalse(a.risk_covered)

    def test_strict_stress_boundary_and_quantum_margin(self):
        state = fill(attempted(), margin="50.3")
        a = assess(state)
        self.assertIn("remaining_fill_gap_liquidation", a.reasons)
        self.assertEqual(a.additional_margin_required, D(".00000001"))

    def test_new_revision_marks_or_funding_change_assessment_digest(self):
        state = fill(attempted())
        original = scenario(state, floor="50")
        a = assess_futures_continuation(state, original, AT)
        newer = mark(state, "99")
        b = assess_futures_continuation(newer, original, newer.as_of)
        self.assertIn("stale_revision", b.reasons)
        self.assertNotEqual(a.state_digest, b.state_digest)
        c = assess(newer, floor="99")
        self.assertNotEqual(a.scenario_digest, c.scenario_digest)
        self.assertNotEqual(a.projected_equity, c.projected_equity)

    def test_complete_marks_context_intent_and_order_are_required(self):
        state = fill(attempted())
        s = scenario(state)
        for kwargs in ({"account_id": "foreign"}, {"plan_digest": "foreign"},
                       {"intent_id": "foreign"}, {"order_id": "foreign"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                assess_futures_continuation(state, replace(s, **kwargs), AT)
        with self.assertRaisesRegex(ValueError, "canonical"):
            replace(s, minimum_marks=s.minimum_marks[:2])
        with self.assertRaisesRegex(ValueError, "canonical"):
            replace(s, minimum_marks=tuple(reversed(s.minimum_marks)))
        with self.assertRaisesRegex(ValueError, "gap minimum"):
            assess_futures_continuation(state, replace(s, minimum_marks=tuple(
                LedgerMark(b.symbol, D("101")) for b in state.ledger.baskets)), AT)

    def test_stale_marks_day_basis_and_latched_halts_are_never_resolved_by_assessment(self):
        state = fill(attempted())
        for at in (AT + timedelta(seconds=31), AT - timedelta(seconds=1)):
            self.assertIn("stale_or_future_marks", assess(state, at=at).reasons)
        a = assess(state, at=AT + timedelta(days=1))
        self.assertIn("invalid_day_basis", a.reasons)
        state = replace(state, reconciliation_halts=("unplanned_entry_fill",))
        self.assertIn("account_halted", assess(state).reasons)
        self.assertEqual(state.reconciliation_halts, ("unplanned_entry_fill",))

    def test_no_remainder_is_not_a_terminal_order_confirmation(self):
        state = fill(attempted(), quantity="1", fee=".1")
        a = assess(state)
        self.assertIn("no_remaining_quantity", a.reasons)
        self.assertFalse(a.risk_covered)
        self.assertTrue(a.requires_reconciliation)
        self.assertIsNotNone(state.pending)
        done = terminal(state, status="filled").state
        with self.assertRaisesRegex(ValueError, "pending order"):
            assess_futures_continuation(done, scenario(state), AT)

    def test_actual_gap_keeps_debt_open_and_unknown_order_reserved(self):
        state = fill(attempted(quantity="10", margin="600"), quantity="5", margin="600", fee=".5")
        state = mark(state, "1")
        a = assess(state, floor="1")
        self.assertFalse(a.risk_covered)
        self.assertIsNotNone(state.pending)
        self.assertEqual(state.ledger.closed_baskets, 0)
        self.assertEqual(state.ledger.baskets[0].quantity, 5)
        self.assertIn("correlated_remaining_fill_stress", a.reasons)

    def test_first_fill_after_closed_pending_cycle_is_not_reinvented(self):
        state = fill(attempted())
        state = record_fill(state, ExitFill("SYNTH0", D(".5"), D("100"), D(".05")),
                            "exit", "exit-fill", state.revision, AT).state
        a = assess(state)
        self.assertIn("first_fill_or_posted_buffer_unproven", a.reasons)
        self.assertIn("pending_position_cycle_changed", a.reasons)
        self.assertFalse(a.risk_covered)

    def test_research_coverage_cannot_enable_execution_or_release_unknown_order(self):
        state = fill(attempted())
        before = state.state_digest
        a = assess(state)
        self.assertEqual(before, state.state_digest)
        with self.assertRaises(FrozenInstanceError):
            a.risk_covered = False
        with self.assertRaisesRegex(ValueError, "cannot enable"):
            replace(a, execution_enabled=True)
        with self.assertRaisesRegex(ValueError, "cannot enable"):
            replace(a, requires_reconciliation=False)

    def test_exhausted_id_storage_cannot_support_remaining_fill_recording(self):
        state = fill(attempted())
        state = replace(state, fill_ids=tuple(f"fill-{i}" for i in range(MAX_IDENTITIES)))
        a = assess(state)
        self.assertIn("identity_capacity_exhausted", a.reasons)
        self.assertFalse(a.risk_covered)
        self.assertEqual(len(state.fill_ids), MAX_IDENTITIES)
        self.assertIsNotNone(state.pending)

    def test_remaining_fee_bound_is_not_relaxed_by_an_inconsistent_receipt(self):
        state = fill(attempted())
        state = replace(state, pending=replace(state.pending, fee_ceiling=D(".075")))
        a = assess(state)
        self.assertIn("remaining_fee_reservation_exceeded", a.reasons)
        self.assertFalse(a.risk_covered)

    def test_signed_isolated_funding_debt_remains_visible(self):
        state = mark(fill(attempted(), margin="30"))
        state = event(state, FundingSettlement("SYNTH0", D("100"), D("1")), state.as_of, "funding")
        a = assess(state)
        self.assertEqual(a.available_isolated_balance, D("-20"))
        self.assertFalse(a.risk_covered)
        self.assertIn("account_halted", a.reasons)
        self.assertEqual(a.additional_margin_required, D("70.30000001"))

    def test_three_five_seven_slot_projection_matches_declared_full_remainder_fill(self):
        for slots in (3, 5, 7):
            with self.subTest(slots=slots):
                state = fill(attempted(start_pending_research(fixture(slots))))
                a = assess(state)
                self.assertTrue(a.risk_covered, a.reasons)
                result = fill(state, margin="0", fill_id="fill-2")
                self.assertEqual(a.projected_equity, result.ledger.equity)
                gap = mark(result, "50")
                self.assertEqual(a.gap_equity_after, gap.ledger.equity)

    def test_affine_endpoint_bounds_cover_adversarial_quantity_price_and_fee_prefixes(self):
        state = fill(attempted())
        a = assess(state, floor="50")
        q0, basis0, net = D(".5"), D("50"), D("60")
        for q in (D("0"), D(".0001"), D(".1"), D(".25"), D(".5")):
            for price in (D("1"), D("90"), D("100")):
                for fee in (D("0"), D(".025"), D(".05")):
                    with self.subTest(quantity=q, price=price, fee=fee):
                        # Raw identities avoid constructing a retrospective fake fill.
                        isolated = net + (q0 + q) * D("50") - basis0 - q * price
                        self.assertGreaterEqual(isolated, D("10"))
                        account = state.ledger.unposted_cash - fee + isolated
                        self.assertGreaterEqual(account, a.gap_equity_after)
                        self.assertGreater(isolated, (q0 + q) * D("50") * D(".006"))

    def test_decimal_context_cannot_change_nonterminating_margin_bound(self):
        state = fill(attempted(leverage="3"), leverage="3")
        expected = assess(state)
        with localcontext() as context:
            context.prec = 4
            actual = assess(state)
        self.assertEqual(expected, actual)


if __name__ == "__main__":
    unittest.main()
