"""Synthetic reservation/economic failure cases; no broker or performance evidence."""
from dataclasses import FrozenInstanceError, replace
from datetime import timedelta
from decimal import Decimal, localcontext
import unittest

from investalo_trading.futures_ledger import EntryFill, ExitFill, FundingSettlement, MarginPosting, MarkBatch, LedgerMark
from investalo_trading.futures_pending import (
    MAX_IDENTITIES, OrderResolution, PendingTransition, assess_ledger_purchase,
    cancel_unattempted, reconcile_order, record_fill, record_ledger_event,
    record_order_attempt, reserve_purchase, start_pending_research,
)
from investalo_trading.futures_risk import FuturesPurchase
from test_futures_ledger import AT, buy, fixture, marks, step

D = Decimal


def request(state, *, symbol="SYNTH0", quantity="1", price="100", margin="60", leverage="2"):
    p = state.ledger.plan
    return FuturesPurchase(p.tenant_id, p.account_id, p.plan_digest, state.revision,
                           symbol, D(quantity), D(price), D(margin), D(leverage))


def prepare(state=None, **kwargs):
    state = state or start_pending_research(fixture())
    return reserve_purchase(state, request(state, **kwargs), "intent-1", state.as_of).state


def attempted(state=None, **kwargs):
    state = prepare(state, **kwargs)
    return record_order_attempt(state, "intent-1", "order-1", state.revision, state.as_of).state


def fill(state, quantity=".5", margin="60", fee=".05", price="100",
         *, fill_id="fill-1", order_id="order-1", leverage="2", symbol="SYNTH0", at=None):
    return record_fill(state, EntryFill(symbol, D(quantity), D(price), D(margin), D(fee), D(leverage)),
                       order_id, fill_id, state.revision, at or state.as_of).state


def terminal(state, *, status="cancelled", **kwargs):
    p = state.pending
    r = OrderResolution(p.intent_id, p.order_id, p.filled_quantity, p.posted_margin,
                        p.fees, status, "synthetic-terminal-evidence")
    return reconcile_order(state, replace(r, **kwargs), state.revision, state.as_of)


class FuturesPendingTests(unittest.TestCase):
    def test_reservation_binds_revisions_and_has_no_cash_movement_or_execution(self):
        state = start_pending_research(fixture())
        result = reserve_purchase(state, request(state), "intent-1", AT)
        self.assertTrue(result.assessment.allowed)
        self.assertFalse(result.execution_enabled)
        self.assertFalse(result.assessment.execution_enabled)
        self.assertIs(result.state.ledger, state.ledger)
        self.assertEqual(result.state.pending.margin_reserved, D("60"))
        self.assertEqual(result.state.pending.fee_reserved, D(".1"))
        self.assertEqual(result.state.revision, 1)
        with self.assertRaisesRegex(ValueError, "stale"):
            reserve_purchase(result.state, request(state), "intent-2", AT)
        self.assertNotEqual(result.state.state_digest, state.state_digest)

    def test_every_pending_intent_blocks_all_other_baskets(self):
        for state in (prepare(), attempted(), fill(attempted())):
            assessment = assess_ledger_purchase(state, request(state, symbol="SYNTH1"), state.as_of)
            self.assertIn("orders_require_reconciliation", assessment.reasons)
            self.assertFalse(assessment.allowed)
            with self.assertRaisesRegex(ValueError, "orders_require"):
                reserve_purchase(state, request(state, symbol="SYNTH2"), "intent-2", state.as_of)

    def test_unknown_outcome_never_expires_or_becomes_retryable(self):
        state = attempted()
        at = AT + timedelta(days=1)
        self.assertIn("orders_require_reconciliation", assess_ledger_purchase(state, request(state), at).reasons)
        with self.assertRaisesRegex(ValueError, "already attempted"):
            record_order_attempt(state, "intent-1", "order-retry", state.revision, at)
        with self.assertRaisesRegex(ValueError, "unattempted"):
            cancel_unattempted(state, "intent-1", state.revision, at)

    def test_local_cancellation_only_before_attempt_and_identity_never_reused(self):
        state = prepare()
        state = cancel_unattempted(state, "intent-1", state.revision, AT).state
        self.assertIsNone(state.pending)
        self.assertTrue(assess_ledger_purchase(state, request(state), AT).allowed)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            reserve_purchase(state, request(state), "intent-1", AT)

    def test_partial_fills_consume_reserves_once_and_can_use_already_posted_margin(self):
        state = fill(attempted())
        self.assertEqual(state.pending.margin_reserved, 0)
        self.assertEqual(state.pending.fee_reserved, D(".05"))
        self.assertEqual(state.ledger.baskets[0].quantity, D(".5"))
        state = fill(state, margin="0", fill_id="fill-2")
        self.assertEqual(state.pending.filled_quantity, 1)
        self.assertEqual(state.pending.fee_reserved, 0)
        self.assertEqual(state.ledger.baskets[0].isolated_balance, 60)
        self.assertEqual(state.ledger.equity, D("9999.9"))
        self.assertIsNotNone(state.pending)
        state = terminal(state, status="filled").state
        self.assertIsNone(state.pending)
        self.assertEqual(state.completed_intents, 1)
        self.assertTrue(assess_ledger_purchase(state, request(state), AT).allowed)

    def test_cancelled_partial_order_releases_only_unused_reserves_not_booked_cash(self):
        state = fill(attempted(), margin="30")
        self.assertEqual(state.pending.margin_reserved, 30)
        cash = state.ledger.unposted_cash
        state = terminal(state).state
        self.assertEqual(state.ledger.unposted_cash, cash)
        self.assertEqual(state.ledger.baskets[0].margin_committed, 30)
        self.assertEqual(state.ledger.baskets[0].quantity, D(".5"))

    def test_terminal_reconciliation_requires_exact_all_booked_totals(self):
        state = fill(attempted())
        for kwargs in ({"filled_quantity": D("1")}, {"posted_margin": D("0")},
                       {"fees": D("0")}, {"order_id": "foreign"}, {"intent_id": "foreign"}):
            with self.subTest(kwargs=kwargs), self.assertRaisesRegex(ValueError, "does not match"):
                terminal(state, **kwargs)
        with self.assertRaisesRegex(ValueError, "remaining quantity"):
            terminal(state, status="filled")
        with self.assertRaisesRegex(ValueError, "terminal"):
            terminal(state, terminal_status="open")
        with self.assertRaisesRegex(ValueError, "cannot have fills"):
            terminal(state, terminal_status="rejected")

    def test_explicit_no_fill_terminal_rejection_and_replay(self):
        state = attempted()
        p = state.pending
        r = OrderResolution(p.intent_id, p.order_id, D("0"), D("0"), D("0"),
                            "rejected", "synthetic-empty-order")
        result = reconcile_order(state, r, state.revision, AT)
        self.assertEqual(result.state.ledger.equity, 10000)
        with self.assertRaisesRegex(ValueError, "does not match"):
            reconcile_order(result.state, r, result.state.revision, AT)
        new = reserve_purchase(result.state, request(result.state), "intent-2", AT).state
        with self.assertRaisesRegex(ValueError, "duplicate"):
            record_order_attempt(new, "intent-2", "order-1", new.revision, AT)

    def test_fill_identity_cannot_be_relabelled_with_new_revision_order_or_payload(self):
        state = fill(attempted())
        for payload in (EntryFill("SYNTH0", D(".1"), D("90"), D("0"), D("0"), D("2")),
                        ExitFill("SYNTH0", D(".1"), D("100"), D("0"))):
            with self.assertRaisesRegex(ValueError, "duplicate"):
                record_fill(state, payload, "another-order", "fill-1", state.revision, AT)
        self.assertEqual(state.ledger.baskets[0].quantity, D(".5"))

    def test_actual_fill_outside_intent_is_booked_and_terminally_quarantined(self):
        for kwargs in ({"quantity": "1.1"}, {"margin": "61"}, {"fee": ".2"},
                       {"price": "101"}, {"leverage": "3"}):
            with self.subTest(kwargs=kwargs):
                state = fill(attempted(), **kwargs)
                self.assertIn("entry_fill_outside_intent", state.reconciliation_halts)
                self.assertGreater(state.ledger.baskets[0].quantity, 0)
                state = terminal(state).state
                self.assertIn("account_halted", assess_ledger_purchase(state, request(state), AT).reasons)

    def test_unsolicited_or_wrong_order_fill_is_not_discarded_or_applied_to_intent_totals(self):
        for state in (start_pending_research(fixture()), attempted()):
            state = fill(state, order_id="foreign-order")
            self.assertEqual(state.ledger.baskets[0].quantity, D(".5"))
            self.assertIn("unplanned_entry_fill", state.reconciliation_halts)
            if state.pending:
                self.assertEqual(state.pending.filled_quantity, 0)

    def test_funding_is_booked_while_order_uncertain_and_before_reassessment(self):
        state = fill(attempted())
        at = AT + timedelta(seconds=1)
        state = record_ledger_event(state, MarkBatch(tuple(
            LedgerMark(b.symbol, D("100")) for b in state.ledger.baskets)),
            "mark-1", state.revision, at).state
        state = record_ledger_event(state, FundingSettlement("SYNTH0", D("100"), D(".1")),
                                    "fund-1", state.revision, at).state
        state = terminal(state).state
        b = state.ledger.baskets[0]
        self.assertEqual(b.margin_committed, 60)
        self.assertEqual(b.isolated_balance, 55)
        a = assess_ledger_purchase(state, request(state), at)
        self.assertEqual(a.outstanding_cost_restoration, 5)
        self.assertEqual(a.current_equity, D("9994.95"))
        self.assertEqual(a.projected_equity, D("9994.85"))

    def test_positive_funding_does_not_expand_gross_budget_or_cause_false_gross_breach(self):
        ledger = buy(fixture(), margin="2900")
        ledger = marks(ledger, "100", AT + timedelta(seconds=1))
        ledger = step(ledger, FundingSettlement("SYNTH0", D("100"), D("-1"))).state
        state = start_pending_research(ledger)
        a = assess_ledger_purchase(state, request(state, margin="60"), state.as_of)
        self.assertTrue(a.allowed, a.reasons)
        self.assertEqual(a.remaining_margin_reserve, D("5980"))
        self.assertEqual(a.outstanding_cost_restoration, 0)
        self.assertEqual(a.current_equity, D("10099.9"))
        blocked = assess_ledger_purchase(state, request(state, margin="81"), state.as_of)
        self.assertIn("basket_capital_or_cost_limit", blocked.reasons)

    def test_funding_charge_does_not_free_spendable_cost_reserve_before_restoration(self):
        ledger = buy(fixture(), margin="2980")
        ledger = marks(ledger, "100", AT + timedelta(seconds=1))
        ledger = step(ledger, FundingSettlement("SYNTH0", D("100"), D(".001"))).state
        state = start_pending_research(ledger)
        a = assess_ledger_purchase(state, request(state, symbol="SYNTH1"), state.as_of)
        self.assertTrue(a.allowed, a.reasons)
        self.assertEqual(a.outstanding_cost_restoration, D(".1"))
        self.assertEqual(a.unused_cost_reserve, D("59.7"))
        state = record_ledger_event(state, MarginPosting("SYNTH0", D(".1"), True),
                                    "restoration", state.revision, state.as_of).state
        after = assess_ledger_purchase(state, request(state, symbol="SYNTH1"), state.as_of)
        self.assertTrue(after.allowed, after.reasons)
        self.assertEqual(after.outstanding_cost_restoration, 0)
        self.assertEqual(a.projected_equity, after.projected_equity)
        self.assertEqual(a.cash_after - after.cash_after, D(".1"))
        self.assertEqual(a.unused_cost_reserve, after.unused_cost_reserve)

    def test_negative_funding_and_insufficient_net_stress_collateral_block_next_buy(self):
        ledger = buy(fixture(), margin="60")
        ledger = marks(ledger, "100", AT + timedelta(seconds=1))
        ledger = step(ledger, FundingSettlement("SYNTH0", D("100"), D(".1"))).state
        state = start_pending_research(ledger)
        a = assess_ledger_purchase(state, request(state, quantity=".1", margin="5"), state.as_of)
        self.assertIn("isolated_stress_liquidation", a.reasons)
        self.assertFalse(a.allowed)

    def test_closed_loss_does_not_reset_original_limits_costs_or_full_budget_requirement(self):
        ledger = buy(fixture())
        ledger = step(ledger, ExitFill("SYNTH0", D("1"), D("90"), D(".09")),
                      at=AT + timedelta(seconds=1)).state
        ledger = marks(ledger, "100", AT + timedelta(seconds=2))
        state = start_pending_research(ledger)
        a = assess_ledger_purchase(state, request(state), state.as_of)
        self.assertIn("insufficient_unposted_cash", a.reasons)
        self.assertNotIn("account_halted", a.reasons)
        self.assertEqual(state.ledger.plan.initial_equity, 10000)
        self.assertEqual(a.unused_cost_reserve, D("59.71"))

    def test_gap_keeps_debt_halt_and_pending_order_without_fake_exit_or_rescue(self):
        state = fill(attempted(quantity="10", margin="600"), quantity="10", margin="600", fee="1")
        cash = state.ledger.unposted_cash
        at = AT + timedelta(seconds=1)
        state = record_ledger_event(state, MarkBatch(tuple(
            LedgerMark(b.symbol, D("1")) for b in state.ledger.baskets)),
            "gap", state.revision, at).state
        self.assertEqual(state.ledger.closed_baskets, 0)
        self.assertIsNotNone(state.pending)
        self.assertEqual(state.ledger.baskets[0].quantity, 10)
        self.assertEqual(state.ledger.baskets[0].equity, D("-390"))
        self.assertEqual(state.ledger.equity, D("9009"))
        self.assertEqual(state.ledger.unposted_cash, cash)
        self.assertIn("daily_loss_limit", state.ledger.halt_reasons)
        self.assertIn("initial_loss_limit", state.ledger.halt_reasons)
        self.assertIn("isolated_position_unsafe", state.ledger.halt_reasons)
        self.assertIn("orders_require_reconciliation",
                      assess_ledger_purchase(state, request(state, price="1"), at).reasons)

    def test_grid_minima_mark_bound_staleness_and_day_basis_still_apply(self):
        state = start_pending_research(fixture())
        for kwargs, reason in (({"quantity": ".00015"}, "invalid_quantity_step"),
                               ({"quantity": ".001"}, "below_contract_minimum"),
                               ({"price": "99"}, "fill_bound_below_mark"),
                               ({"margin": "50"}, "isolated_stress_liquidation")):
            self.assertIn(reason, assess_ledger_purchase(state, request(state, **kwargs), AT).reasons)
        a = assess_ledger_purchase(state, request(state), AT + timedelta(days=1))
        self.assertIn("stale_or_future_marks", a.reasons)
        self.assertIn("invalid_day_basis", a.reasons)

    def test_context_and_both_revision_domains_are_checked(self):
        state = attempted()
        with self.assertRaisesRegex(ValueError, "foreign"):
            assess_ledger_purchase(state, replace(request(state), account_id="foreign"), AT)
        with self.assertRaisesRegex(ValueError, "stale"):
            record_fill(state, EntryFill("SYNTH0", D("1"), D("100"), D("60"), D(".1"), D("2")),
                        "order-1", "fill-1", 0, AT)
        state = fill(state)
        self.assertEqual(state.revision, 3)
        self.assertEqual(state.ledger.revision, 1)
        self.assertEqual(state.pending.request.expected_revision, 0)

    def test_nonfill_event_dedup_and_equal_time_ordering_are_not_weakened(self):
        state = fill(attempted())
        with self.assertRaisesRegex(ValueError, "fills require"):
            record_ledger_event(state, ExitFill("SYNTH0", D(".5"), D("100"), D("0")),
                                "exit", state.revision, AT)
        with self.assertRaisesRegex(ValueError, "equal-time"):
            record_ledger_event(state, FundingSettlement("SYNTH0", D("100"), D(".001")),
                                "fund", state.revision, AT)
        at = AT + timedelta(seconds=1)
        payload = MarkBatch(tuple(LedgerMark(b.symbol, b.mark) for b in state.ledger.baskets))
        state = record_ledger_event(state, payload, "mark", state.revision, at).state
        with self.assertRaisesRegex(ValueError, "duplicate"):
            record_ledger_event(state, payload, "mark", state.revision, at)
        with self.assertRaisesRegex(ValueError, "backdated"):
            record_ledger_event(state, payload, "mark-2", state.revision, AT)

    def test_actual_exit_deduplicates_across_completed_cycles(self):
        state = fill(attempted(), quantity="1", fee=".1")
        state = terminal(state, status="filled").state
        payload = ExitFill("SYNTH0", D("1"), D("100"), D(".1"))
        state = record_fill(state, payload, "exit-order", "exit-fill", state.revision, AT).state
        self.assertEqual(state.ledger.closed_baskets, 1)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            record_fill(state, payload, "exit-order", "exit-fill", state.revision, AT)
        self.assertIn("entry_event_ordering", assess_ledger_purchase(state, request(state), AT).reasons)

    def test_exit_order_identity_cannot_be_reused_for_new_entry_intent(self):
        state = fill(attempted(), quantity="1", fee=".1")
        state = terminal(state, status="filled").state
        payload = ExitFill("SYNTH0", D("1"), D("101"), D(".1"))
        state = record_fill(state, payload, "exit-order", "exit-fill", state.revision, AT).state
        at = AT + timedelta(seconds=1)
        batch = MarkBatch(tuple(LedgerMark(b.symbol, b.mark) for b in state.ledger.baskets))
        state = record_ledger_event(state, batch, "next-mark", state.revision, at).state
        state = reserve_purchase(state, request(state), "intent-2", at).state
        with self.assertRaisesRegex(ValueError, "duplicate"):
            record_order_attempt(state, "intent-2", "exit-order", state.revision, at)

    def test_reconciliation_halt_is_separate_and_does_not_rewrite_ledger_hash(self):
        state = attempted()
        result = record_fill(state, EntryFill("SYNTH0", D(".5"), D("101"), D("60"), D(".05"), D("2")),
                             "order-1", "out-of-bound", state.revision, AT)
        self.assertEqual(result.ledger_transition.state, result.state.ledger)
        self.assertIn("entry_fill_outside_intent", result.state.reconciliation_halts)
        self.assertNotIn("entry_fill_outside_intent", result.state.ledger.halt_reasons)
        after = terminal(result.state).state
        at = AT + timedelta(seconds=1)
        payload = MarkBatch(tuple(LedgerMark(b.symbol, D("120")) for b in after.ledger.baskets))
        after = record_ledger_event(after, payload, "recovery", after.revision, at).state
        self.assertIn("entry_fill_outside_intent", after.reconciliation_halts)
        self.assertFalse(assess_ledger_purchase(after, request(after, price="120"), at).allowed)

    def test_booked_debt_does_not_become_zero_effective_leverage(self):
        ledger = buy(fixture(), margin="60")
        ledger = marks(ledger, "100", AT + timedelta(seconds=1))
        ledger = step(ledger, FundingSettlement("SYNTH0", D("100"), D("1"))).state
        state = start_pending_research(ledger)
        a = assess_ledger_purchase(state, request(state, margin="5"), state.as_of)
        self.assertIsNone(a.effective_entry_leverage)
        self.assertFalse(a.allowed)

    def test_capacity_fails_closed_without_evicting_duplicate_evidence(self):
        state = start_pending_research(fixture())
        full = tuple(f"fill-{i}" for i in range(MAX_IDENTITIES))
        state = replace(state, fill_ids=full)
        self.assertIn("identity_capacity_exhausted", assess_ledger_purchase(state, request(state), AT).reasons)
        with self.assertRaisesRegex(ValueError, "capacity"):
            fill(state, fill_id="new-fill")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            fill(state, fill_id="fill-0")

    def test_full_fill_projection_matches_ledger_for_three_five_seven_slots_and_funding(self):
        for slots in (3, 5, 7):
            ledger = buy(fixture(slots))
            ledger = marks(ledger, "100", AT + timedelta(seconds=1))
            ledger = step(ledger, FundingSettlement("SYNTH0", D("100"), D(".001"))).state
            state = start_pending_research(ledger)
            a = assess_ledger_purchase(state, request(state), state.as_of)
            self.assertTrue(a.allowed, a.reasons)
            state = fill(attempted(state), quantity="1", fee=".1")
            self.assertEqual(a.projected_equity, state.ledger.equity)
            self.assertEqual(a.cash_after, state.ledger.unposted_cash)
            self.assertEqual(state.ledger.baskets[0].margin_committed, 120)
            self.assertEqual(state.ledger.baskets[0].isolated_balance, D("119.9"))

    def test_actual_first_fragment_changes_stress_floor_before_next_intent(self):
        state = attempted(quantity="10", margin="600")
        state = fill(state, quantity=".0001", price="1", margin="600", fee=".0000001")
        state = fill(state, quantity="9.9999", margin="0", fee=".99999", fill_id="fill-2")
        state = terminal(state, status="filled").state
        self.assertEqual(state.ledger.baskets[0].first_fill, 1)
        a = assess_ledger_purchase(state, request(state, quantity=".1", margin="10"), AT)
        self.assertIn("isolated_stress_liquidation", a.reasons)
        self.assertIn("correlated_account_stress", a.reasons)
        self.assertFalse(a.allowed)

    def test_small_decimal_context_and_frozen_execution_contract(self):
        state = start_pending_research(fixture())
        expected = assess_ledger_purchase(state, request(state, quantity="3"), AT)
        with localcontext() as ctx:
            ctx.prec = 4
            actual = assess_ledger_purchase(state, request(state, quantity="3"), AT)
            state = fill(attempted(state), quantity=".3", margin="30", fee=".03")
        self.assertEqual(expected, actual)
        self.assertEqual(state.ledger.baskets[0].average_entry, 100)
        with self.assertRaises(FrozenInstanceError):
            state.revision = 0
        with self.assertRaisesRegex(ValueError, "cannot enable"):
            replace(actual, execution_enabled=True)
        with self.assertRaisesRegex(ValueError, "cannot enable"):
            PendingTransition(state, state.state_digest, state.state_digest, execution_enabled=True)


if __name__ == "__main__":
    unittest.main()
