"""Synthetic economic identities and failure cases, not historical performance."""
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext
import unittest

from investalo_trading.futures_economics import MarginSchedule, MarginTier
from investalo_trading.futures_ledger import (
    DailyBasis, EntryFill, ExitFill, FundingSettlement, LedgerCommand,
    LedgerMark, LedgerTransition, MarginPosting, MarkBatch, apply_futures_event,
    start_futures_ledger,
)
from investalo_trading.futures_risk import (
    FuturesBudget, FuturesContract, FuturesExposure, FuturesPlan, FuturesPurchase, FuturesView,
    assess_futures_purchase,
)

D = Decimal
AT = datetime(2026, 11, 1, tzinfo=timezone.utc)


def fixture(slots=3):
    symbols = tuple(f"SYNTH{i}" for i in range(slots))
    contracts = tuple(FuturesContract(
        s, D(".0001"), D(".001"), D("5"), D(".001"), D(".001"),
        MarginSchedule((MarginTier(D("1000000"), D(".005"), D("20")),)), "synthetic-only",
    ) for s in symbols)
    capital = D("1000") if slots > 5 else D("2000") if slots > 3 else D("3000")
    plan = FuturesPlan("tenant", "account", "synthetic-policy", D("10000"), D(".00000001"),
                       D("10000") - slots * capital, contracts,
                       tuple(FuturesBudget(s, capital, D("20")) for s in symbols))
    return start_futures_ledger(plan, tuple(LedgerMark(s, D("100")) for s in symbols),
                                AT, "synthetic-midnight-evidence")


def command(state, payload, *, at=None, event_id=None):
    plan = state.plan
    return LedgerCommand(plan.tenant_id, plan.account_id, plan.plan_digest, state.revision,
                         event_id or f"event-{state.revision}", at or state.as_of, payload)


def step(state, payload, *, at=None):
    return apply_futures_event(state, command(state, payload, at=at))


def marks(state, price, at, symbol=None):
    return step(state, MarkBatch(tuple(
        LedgerMark(b.symbol, D(price) if symbol is None or symbol == b.symbol else b.mark)
        for b in state.baskets)), at=at).state


def buy(state, quantity="1", price="100", margin="60", fee=".1", leverage="2", symbol="SYNTH0"):
    return step(state, EntryFill(symbol, D(quantity), D(price), D(margin), D(fee), D(leverage))).state


class FuturesLedgerTests(unittest.TestCase):
    def test_margin_transfer_does_not_multiply_pnl_or_change_equity(self):
        initial = fixture()
        a = buy(initial)
        b = buy(initial, margin="100", leverage="10")
        self.assertEqual(a.equity, D("9999.9"))
        self.assertEqual(a.equity, b.equity)
        self.assertEqual(a.unposted_cash - b.unposted_cash, D("40"))
        self.assertEqual(b.baskets[0].isolated_balance - a.baskets[0].isolated_balance, D("40"))
        self.assertFalse(a.halted)

    def test_two_partial_entry_fills_freeze_first_fill_and_lower_average(self):
        state = buy(fixture(), quantity=".5", margin="30", fee=".05")
        state = marks(state, "90", AT + timedelta(seconds=1))
        state = buy(state, quantity="1.5", price="90", margin="90", fee=".135", leverage="3")
        b = state.baskets[0]
        self.assertEqual(b.first_fill, D("100"))
        self.assertEqual(b.average_entry, D("92.5"))
        self.assertEqual(b.quantity, D("2"))
        self.assertEqual(b.margin_committed, D("120"))
        self.assertEqual(b.entry_fees, D(".185"))
        self.assertEqual(state.equity, D("9994.815"))

    def test_minimum_order_size_is_not_invented_for_partial_fill_fragments(self):
        state = buy(fixture(), quantity=".0001", margin=".006", fee="0")
        self.assertEqual(state.baskets[0].quantity, D(".0001"))
        self.assertFalse(state.halted)

    def test_remaining_partial_fill_can_use_margin_already_posted_by_first_fragment(self):
        state = buy(fixture(), quantity=".5", margin="60", fee=".05")
        state = buy(state, quantity=".5", margin="0", fee=".05")
        self.assertEqual(state.baskets[0].quantity, D("1"))
        self.assertEqual(state.baskets[0].isolated_balance, D("60"))
        self.assertEqual(state.unposted_cash, D("9939.9"))
        self.assertEqual(state.equity, D("9999.9"))
        self.assertFalse(state.halted)

    def test_funding_debits_only_isolated_balance_once(self):
        state = buy(fixture())
        state = marks(state, "100", AT + timedelta(hours=8))
        cash = state.unposted_cash
        result = step(state, FundingSettlement("SYNTH0", D("100"), D(".001")))
        b = result.state.baskets[0]
        self.assertEqual(result.equity_after - result.equity_before, D("-.1"))
        self.assertEqual(result.state.unposted_cash, cash)
        self.assertEqual(b.isolated_balance, D("59.9"))
        self.assertEqual(b.margin_committed, D("60"))
        self.assertEqual(b.funding_net, D("-.1"))
        self.assertEqual(b.charges_in_budget_epoch, D(".2"))

    def test_funding_credit_is_profit_not_new_committed_margin_or_cost_reset(self):
        state = buy(fixture(), margin="70")
        state = marks(state, "100", AT + timedelta(hours=8))
        state = step(state, FundingSettlement("SYNTH0", D("100"), D("-.2"))).state
        self.assertEqual(state.baskets[0].isolated_balance, D("90"))
        self.assertEqual(state.baskets[0].margin_committed, D("70"))
        self.assertEqual(state.baskets[0].charges_in_budget_epoch, D(".1"))
        self.assertEqual(state.equity, D("10019.9"))
        self.assertNotIn("basket_budget_breach", state.halt_reasons)

    def test_cost_reserve_restores_funding_debit_without_double_charge_or_margin_budget_growth(self):
        state = buy(fixture(), margin="2980")
        state = marks(state, "100", AT + timedelta(hours=8))
        state = step(state, FundingSettlement("SYNTH0", D("100"), D(".001"))).state
        self.assertEqual(state.reserve_shortfall, 0)
        # Exactly the remaining planned reserves are still backed; a funding
        # debit does not release its unpaid restoration as spendable cash.
        expected_needed = D("1000") + 2 * D("3000") + D("19.8") + D(".1")
        self.assertEqual(state.unposted_cash, expected_needed)
        before = state.equity
        state = step(state, MarginPosting("SYNTH0", D(".1"), cost_restoration=True)).state
        self.assertEqual(state.baskets[0].isolated_balance, D("2980"))
        self.assertEqual(state.baskets[0].margin_committed, D("2980"))
        self.assertEqual(state.baskets[0].charges_in_budget_epoch, D(".2"))
        self.assertEqual(state.equity, before)
        self.assertNotIn("basket_budget_breach", state.halt_reasons)
        result = step(state, ExitFill("SYNTH0", D("1"), D("100"), D(".1")))
        self.assertEqual(result.closed.net_pnl, D("-.3"))
        self.assertEqual(result.state.unposted_cash, D("9999.7"))

    def test_cost_restoration_cannot_mint_an_unrelated_margin_transfer(self):
        state = buy(fixture())
        with self.assertRaisesRegex(ValueError, "restoration exceeds"):
            step(state, MarginPosting("SYNTH0", D(".1"), cost_restoration=True),
                 at=AT + timedelta(seconds=1))

    def test_funding_with_no_open_position_books_no_income(self):
        state = fixture()
        result = step(state, FundingSettlement("SYNTH0", D("100"), D("-.1")))
        self.assertEqual(result.equity_after, result.equity_before)
        self.assertEqual(result.state.baskets[0].funding_net, 0)

    def test_duplicate_settlement_is_rejected_even_with_new_event_id_and_revision(self):
        state = fixture()
        state = step(state, FundingSettlement("SYNTH0", D("100"), D(".001"))).state
        with self.assertRaisesRegex(ValueError, "duplicate funding"):
            step(state, FundingSettlement("SYNTH0", D("100"), D("-.001")))

    def test_existing_purchase_assessor_projection_matches_declared_fill_for_three_to_seven_slots(self):
        for slots in (3, 5, 7):
            with self.subTest(slots=slots):
                state = fixture(slots)
                p = state.plan
                view = FuturesView(
                    p.tenant_id, p.account_id, p.plan_digest, 0, AT, AT, p.initial_equity,
                    state.unposted_cash, tuple(FuturesExposure(b.symbol, b.mark, AT) for b in state.baskets),
                )
                request = FuturesPurchase(p.tenant_id, p.account_id, p.plan_digest, 0,
                                          "SYNTH0", D("1"), D("100"), D("60"), D("2"))
                assessed = assess_futures_purchase(p, view, request, AT)
                self.assertTrue(assessed.allowed, assessed.reasons)
                actual = buy(state)
                self.assertEqual(actual.equity, assessed.projected_equity)
                self.assertEqual(actual.unposted_cash, assessed.unposted_cash_after)
                self.assertFalse(actual.halted)

    def test_funding_requires_exact_settlement_mark_not_later_or_stale_price(self):
        state = buy(fixture())
        for mark, at in ((D("99"), AT), (D("100"), AT + timedelta(hours=8))):
            with self.subTest(mark=mark, at=at), self.assertRaises(ValueError):
                step(state, FundingSettlement("SYNTH0", mark, D(".001")), at=at)

    def test_partial_close_preserves_remaining_quantity_costbasis_and_collateral(self):
        state = buy(fixture(), quantity="2", margin="120", fee=".2")
        state = marks(state, "110", AT + timedelta(seconds=1))
        result = step(state, ExitFill("SYNTH0", D(".5"), D("110"), D(".055")))
        b = result.state.baskets[0]
        self.assertEqual(b.quantity, D("1.5"))
        self.assertEqual(b.average_entry, D("100"))
        self.assertEqual(b.first_fill, D("100"))
        self.assertEqual(b.isolated_balance, D("90"))
        self.assertEqual(b.margin_committed, D("90"))
        self.assertEqual(b.realized_price_pnl, D("5"))
        self.assertEqual(result.state.unposted_cash - state.unposted_cash, D("34.945"))
        self.assertEqual(result.equity_after - result.equity_before, D("-.055"))
        self.assertIsNone(result.closed)

    def test_whole_cycle_closes_to_exact_net_price_fees_and_signed_funding(self):
        state = buy(fixture(), quantity="2", margin="120", fee=".2")
        state = marks(state, "100", AT + timedelta(hours=8))
        state = step(state, FundingSettlement("SYNTH0", D("100"), D(".001"))).state
        state = marks(state, "110", AT + timedelta(hours=8, seconds=1))
        state = step(state, ExitFill("SYNTH0", D(".5"), D("110"), D(".055"))).state
        state = marks(state, "120", AT + timedelta(hours=8, seconds=2))
        result = step(state, ExitFill("SYNTH0", D("1.5"), D("120"), D(".18")))
        self.assertEqual(result.closed.net_pnl, D("34.365"))
        self.assertEqual(result.closed.price_pnl, D("35"))
        self.assertEqual(result.closed.funding_net, D("-.2"))
        self.assertEqual(result.state.equity, D("10034.365"))
        self.assertEqual(result.state.unposted_cash, result.state.equity)
        self.assertEqual(result.state.realized_net_pnl, result.closed.net_pnl)
        self.assertEqual(result.state.closed_baskets, 1)
        self.assertEqual(result.state.baskets[0].isolated_balance, 0)

    def test_new_cycle_changes_first_fill_but_not_original_equity_or_cost_epoch(self):
        state = buy(fixture())
        state = marks(state, "110", AT + timedelta(seconds=1))
        state = step(state, ExitFill("SYNTH0", D("1"), D("110"), D(".11"))).state
        old_charges = state.baskets[0].charges_in_budget_epoch
        state = marks(state, "90", AT + timedelta(seconds=2))
        state = buy(state, price="90", fee=".09")
        self.assertEqual(state.baskets[0].cycle, 2)
        self.assertEqual(state.baskets[0].first_fill, D("90"))
        self.assertEqual(state.plan.initial_equity, D("10000"))
        self.assertEqual(state.baskets[0].charges_in_budget_epoch, old_charges + D(".09"))

    def test_gap_does_not_invent_stop_fill_or_liquidation_recovery(self):
        state = buy(fixture(), quantity="10", margin="600", fee="1")
        state = marks(state, "1", AT + timedelta(seconds=1))
        b = state.baskets[0]
        self.assertEqual(b.quantity, D("10"))
        self.assertEqual(b.equity, D("-390"))
        self.assertEqual(state.equity, D("9009"))
        self.assertTrue(state.halted)
        self.assertIn("isolated_position_unsafe", state.halt_reasons)
        self.assertIn("daily_loss_limit", state.halt_reasons)
        self.assertIn("initial_loss_limit", state.halt_reasons)
        self.assertEqual(state.closed_baskets, 0)

    def test_later_posting_and_price_recovery_never_clear_gap_halt(self):
        state = buy(fixture(), quantity="10", margin="600", fee="1")
        state = marks(state, "1", AT + timedelta(seconds=1))
        before = state.equity
        state = step(state, MarginPosting("SYNTH0", D("500"))).state
        self.assertEqual(state.equity, before)
        state = marks(state, "100", AT + timedelta(seconds=2))
        self.assertTrue(state.halted)
        self.assertIn("isolated_position_unsafe", state.halt_reasons)

    def test_funding_can_record_signed_isolated_deficit_without_other_basket_rescue(self):
        state = buy(fixture())
        state = marks(state, "100", AT + timedelta(hours=8))
        other = state.baskets[1:]
        cash = state.unposted_cash
        state = step(state, FundingSettlement("SYNTH0", D("100"), D(".7"))).state
        self.assertEqual(state.baskets[0].isolated_balance, D("-10"))
        self.assertEqual(state.unposted_cash, cash)
        self.assertEqual(state.baskets[1:], other)
        self.assertIn("isolated_position_unsafe", state.halt_reasons)

    def test_broker_close_after_gap_records_deficit_and_all_fees_once(self):
        state = buy(fixture(), quantity="10", margin="600", fee="1")
        state = marks(state, "1", AT + timedelta(seconds=1))
        result = step(state, ExitFill("SYNTH0", D("10"), D("1"), D(".01")))
        self.assertEqual(result.closed.net_pnl, D("-991.01"))
        self.assertEqual(result.state.unposted_cash, D("9008.99"))
        self.assertEqual(result.state.equity, D("9008.99"))
        self.assertTrue(result.state.halted)

    def test_normal_loss_blocks_unfunded_future_budgets_without_inventing_permanent_account_halt(self):
        state = buy(fixture())
        state = marks(state, "90", AT + timedelta(seconds=1))
        state = step(state, ExitFill("SYNTH0", D("1"), D("90"), D(".09"))).state
        self.assertEqual(state.reserve_shortfall, D("10"))
        self.assertFalse(state.halted)
        self.assertEqual(state.equity, D("9989.81"))

    def test_known_fill_after_halt_is_booked_and_explicitly_flagged(self):
        state = buy(fixture(), quantity="10", margin="600", fee="1")
        state = marks(state, "1", AT + timedelta(seconds=1))
        state = buy(state, price="1", margin="1", fee=".001")
        self.assertEqual(state.baskets[0].quantity, D("11"))
        self.assertIn("entry_fill_after_halt", state.halt_reasons)

    def test_daily_basis_needs_pre_mutation_midnight_batch_and_never_rebases_initial(self):
        state = buy(fixture())
        midnight = AT + timedelta(days=1)
        state = marks(state, "110", midnight)
        before = state.equity
        state = step(state, DailyBasis(before, "synthetic-h4-close-evidence")).state
        self.assertEqual(state.day_start_equity, before)
        self.assertEqual(state.day_started_at, midnight)
        self.assertEqual(state.plan.initial_equity, D("10000"))
        self.assertEqual(state.equity, before)

    def test_day_basis_cannot_use_intraday_time_wrong_equity_stale_or_postfill_marks(self):
        state = buy(fixture())
        midnight = AT + timedelta(days=1)
        for sample, value, at in (
            (state, state.equity, midnight),
            (marks(state, "100", midnight), D("10000"), midnight),
            (marks(state, "100", midnight + timedelta(hours=1)), state.equity,
             midnight + timedelta(hours=1)),
        ):
            with self.subTest(at=at, value=value), self.assertRaises(ValueError):
                step(sample, DailyBasis(value, "synthetic-evidence"), at=at)
        fresh = marks(state, "100", midnight)
        mutated = buy(fresh)
        with self.assertRaises(ValueError):
            step(mutated, DailyBasis(mutated.equity, "synthetic-evidence"))
        self.assertIn("entry_fill_without_current_day_basis", mutated.halt_reasons)

    def test_equal_timestamp_funding_uses_existing_inventory_before_entry_exit(self):
        state = buy(fixture())
        state = marks(state, "100", AT + timedelta(hours=8))
        state = step(state, FundingSettlement("SYNTH0", D("100"), D(".001"))).state
        state = buy(state, fee=".1")
        self.assertEqual(state.baskets[0].funding_net, D("-.1"))
        with self.assertRaises(ValueError):
            step(state, FundingSettlement("SYNTH0", D("100"), D(".001")))
        state = step(state, ExitFill("SYNTH0", D("1"), D("100"), D(".1"))).state
        with self.assertRaises(ValueError):
            buy(state)

    def test_stale_revision_context_and_backdated_events_do_not_mutate_source(self):
        state = fixture()
        original = state.state_digest
        event = command(state, EntryFill("SYNTH0", D("1"), D("100"), D("60"), D(".1"), D("2")))
        result = apply_futures_event(state, event)
        self.assertEqual(state.state_digest, original)
        with self.assertRaises(ValueError):
            apply_futures_event(result.state, event)
        for invalid in (replace(event, tenant_id="foreign"), replace(event, account_id="foreign"),
                        replace(event, plan_digest="foreign"),
                        replace(event, occurred_at=AT - timedelta(seconds=1))):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                apply_futures_event(state, invalid)

    def test_overclose_quantity_step_and_foreign_mark_batches_rejected(self):
        state = buy(fixture())
        for payload in (
            ExitFill("SYNTH0", D("2"), D("100"), D(".1")),
            ExitFill("SYNTH0", D(".00001"), D("100"), D("0")),
            EntryFill("foreign", D("1"), D("100"), D("60"), D("0"), D("2")),
            MarkBatch(tuple(LedgerMark(f"FOREIGN{i}", D("100")) for i in range(3))),
        ):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                step(state, payload)

    def test_budget_and_initial_margin_breaches_record_actual_outcome(self):
        state = buy(fixture(), margin="3000", fee="21")
        self.assertEqual(state.baskets[0].margin_committed, D("3000"))
        self.assertEqual(state.unposted_cash, D("6979"))
        self.assertIn("basket_budget_breach", state.halt_reasons)
        under = buy(fixture(), margin="10")
        self.assertIn("entry_fill_initial_margin_breach", under.halt_reasons)

    def test_all_baskets_share_original_limits_and_are_atomically_marked(self):
        state = fixture(slots=5)
        for symbol in state.plan.symbols:
            state = buy(state, quantity="4", margin="240", fee=".4", symbol=symbol)
        state = marks(state, "50", AT + timedelta(seconds=1))
        self.assertEqual(state.equity, D("8998"))
        self.assertIn("daily_loss_limit", state.halt_reasons)
        self.assertIn("initial_loss_limit", state.halt_reasons)
        self.assertEqual(len({b.marked_at for b in state.baskets}), 1)

    def test_high_precision_accounting_isolated_from_callers_decimal_context(self):
        state = fixture()
        payload = EntryFill("SYNTH0", D(".3"), D("100.123456789012345678"),
                            D("18"), D(".0300370370367037037034"), D("2"))
        expected = step(state, payload)
        with localcontext() as ctx:
            ctx.prec = 4
            observed = step(state, payload)
        self.assertEqual(expected, observed)
        state = expected.state
        state = marks(state, "90", AT + timedelta(seconds=1))
        # Average with a non-terminating quotient must not be rejected as a
        # lexical public input: internal arithmetic has its own bounded scale.
        state = buy(state, quantity="1", price="90", margin="60", fee=".09")
        self.assertGreater(len(state.baskets[0].average_entry.as_tuple().digits), 28)

    def test_audit_head_and_state_digest_change_with_event_body_identity_and_revision(self):
        state = fixture()
        payload = EntryFill("SYNTH0", D("1"), D("100"), D("60"), D(".1"), D("2"))
        a = apply_futures_event(state, command(state, payload, event_id="a"))
        b = apply_futures_event(state, command(state, payload, event_id="b"))
        self.assertNotEqual(a.event_digest, b.event_digest)
        self.assertNotEqual(a.state.audit_head, b.state.audit_head)
        self.assertEqual(a.prior_digest, state.state_digest)
        self.assertEqual(a.state.revision, 1)
        self.assertEqual(a.state, apply_futures_event(state, command(state, payload, event_id="a")).state)

    def test_immutable_bounded_inputs_and_no_execution_flag(self):
        state = fixture()
        with self.assertRaises(FrozenInstanceError):
            state.unposted_cash = D("0")
        for invalid in (float("nan"), D("NaN"), D("1e99"), D("1e-99")):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                EntryFill("SYNTH0", D("1"), D("100"), D("60"), invalid, D("2"))
        for leverage in ("1", "10.001"):
            with self.subTest(leverage=leverage), self.assertRaises(ValueError):
                EntryFill("SYNTH0", D("1"), D("100"), D("60"), D(".1"), D(leverage))
        with self.assertRaises(ValueError):
            LedgerTransition(state, "event", "before", state.equity, state.equity, execution_enabled=True)
