"""Actual-entry reducer with synthetic broker evidence; no native orders."""
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal, localcontext
import unittest

from investalo_trading.futures_broker_entries import (
    BrokerEntryObservation, observe_broker_entry, observe_broker_prices,
    prepare_broker_entry, replay_broker_hour, start_broker_entries,
)
from investalo_trading.futures_capital_signals import assess_capital_signal
from investalo_trading.futures_ledger import LedgerMark
from investalo_trading.models import floor_step
from test_futures_capital_h1 import h1_ready, h1_start
from test_futures_capital_signals import buy, hour
from test_futures_paper_runtime import warmed

D = Decimal


def ready(grid=False, **kwargs):
    return start_broker_entries(warmed(**kwargs).signal if grid else h1_ready())


def prepare(book, price="100", symbol="SYNTH0", command_id=None):
    return prepare_broker_entry(book, symbol, D(price), command_id or f"order-{book.revision}",
                                book.revision, book.as_of)


def receipt(book, *, state="filled", quantity=None, price="98", fee="-.352", margin=None,
            matches=True, at=None):
    order = book.pending
    quantity = order.request.quantity if quantity is None else D(quantity)
    price = D(price) if quantity else None
    if margin is None:
        # Test fixture only. Production must supply confirmed entry capital.
        with localcontext() as precision:
            precision.prec = 160
            margin = quantity * price / 2 if quantity else D(0)
    return BrokerEntryObservation(
        order.order_digest, state, quantity, price, D(fee) if fee is not None else None,
        margin, matches, at or book.as_of, f"synthetic-native-{book.revision}")


def observe(book, observation=None, **kwargs):
    evidence = observation or receipt(book, **kwargs)
    return observe_broker_entry(book, evidence, book.revision, evidence.observed_at)


def advance(book, price):
    frame = hour(book.signal, D(price), all_assets=True)
    return replay_broker_hour(book, frame, book.revision, frame.close_time)


def prices(book, price, seconds=1):
    marks = tuple(LedgerMark(s, D(price)) for s in book.signal.profile.plan.symbols)
    return observe_broker_prices(book, marks, marks, f"marks-{book.revision}", book.revision,
                                 book.as_of + timedelta(seconds=seconds))


class BrokerEntryTests(unittest.TestCase):
    def test_first_order_uses_own_margin_times_leverage_and_native_quantity_floor(self):
        book = prepare(ready())
        request = book.pending.request
        self.assertEqual(request.posted_margin, D("293.13365892"))
        self.assertEqual(request.requested_leverage, 2)
        step = book.signal.profile.plan.contracts[0].quantity_step
        with localcontext() as precision:
            precision.prec = 160
            expected = floor_step(D("293.13365892") * 2 / 100, step)
        self.assertEqual(request.quantity, expected)
        self.assertGreater(request.quantity * 100, 580)  # Separate from20USDT test.
        self.assertFalse(book.execution_enabled)

    def test_actual_price_fee_and_margin_replace_model_estimates(self):
        book = prepare(ready())
        before = book.signal.economic.ledger.unposted_cash
        evidence = receipt(book, price="97.123", fee="-.007")
        settled = observe(book, evidence)
        basket = settled.signal.economic.ledger.baskets[0]
        self.assertEqual(basket.quantity, evidence.quantity)
        self.assertEqual(basket.average_entry, D("97.123"))
        self.assertEqual(basket.entry_fees, D(".007"))
        self.assertEqual(basket.margin_committed, evidence.posted_margin)
        self.assertEqual(settled.signal.economic.ledger.unposted_cash,
                         before - evidence.posted_margin - D(".007"))
        self.assertEqual(settled.signal.economic.stages[0].price, D("97.123"))
        self.assertFalse(settled.signal.signals[0].rearmed)
        self.assertFalse(settled.signal.signals[0].protected)

    def test_native_weighted_average_can_fall_between_price_ticks(self):
        book = prepare(ready(grid=True))
        evidence = receipt(book, price="97.12345")
        settled = observe(book, evidence)
        self.assertEqual(settled.signal.economic.stages[0].price, D("97.12345"))
        self.assertEqual(settled.signal.economic.ledger.baskets[0].average_entry, D("97.12345"))

    def test_partial_order_is_pending_then_one_stage_on_terminal_cancellation(self):
        book = prepare(ready())
        before = book.signal.economic.state_digest
        book = observe(book, state="partially_filled", quantity="1.2", price="97", fee="-.01")
        self.assertEqual(book.signal.economic.state_digest, before)
        self.assertEqual(book.observation.quantity, D("1.2"))
        self.assertIs(observe(book, book.observation), book)
        with self.assertRaisesRegex(ValueError, "outstanding"):
            prepare(book, symbol="SYNTH1")
        with self.assertRaisesRegex(ValueError, "outstanding"):
            advance(book, "96")
        book = observe(book, state="partially_filled", quantity="2.4", price="96", fee="-.02")
        book = observe(book, state="canceled", quantity="2.4", price="96", fee="-.02")
        self.assertIsNone(book.pending)
        self.assertEqual(len(book.signal.economic.stages), 1)
        self.assertEqual(book.signal.economic.stages[0].quantity, D("2.4"))
        self.assertEqual(book.signal.economic.stages[0].own_capital, D("115.2"))
        self.assertEqual(book.signal.economic.ledger.baskets[0].entry_fees, D(".02"))
        self.assertIn("terminal_partial_entry", book.notices)

    def test_missing_native_fee_margin_or_position_match_cannot_be_invented(self):
        original = prepare(ready())
        variants = (
            replace(receipt(original), signed_fee=None),
            replace(receipt(original), posted_margin=None),
            replace(receipt(original), position_matches=False),
            replace(receipt(original), signed_fee=D(".01")),  # Unsupported rebate.
        )
        for evidence in variants:
            with self.subTest(evidence=evidence):
                pending = observe(original, evidence)
                self.assertIsNotNone(pending.pending)
                self.assertEqual(pending.signal.economic.stages, ())
                self.assertEqual(pending.signal.economic.ledger.baskets[0].quantity, 0)
                settled = observe(pending, replace(receipt(pending), evidence_digest="resolved"))
                self.assertIsNone(settled.pending)

    def test_unfilled_cancellation_consumes_command_without_advancing_stage(self):
        book = prepare(ready(), command_id="single-command")
        book = observe(book, state="canceled", quantity="0", fee="0")
        self.assertIsNone(book.pending)
        self.assertEqual(book.signal.economic.stages, ())
        with self.assertRaisesRegex(ValueError, "reused"):
            prepare(book, command_id="single-command")
        retried = prepare(book, command_id="new-command")
        self.assertEqual(retried.pending.assessment.capital.stage, 1)
        self.assertEqual(len(retried.signal.economic.decisions), 1)

    def test_unfilled_cancellation_cannot_hide_a_debit(self):
        original = prepare(ready())
        for fields in (dict(fee="-.01"), dict(margin=D(".01"))):
            with self.subTest(fields=fields), self.assertRaisesRegex(ValueError, "zero debit"):
                observe(original, state="canceled", quantity="0", **fields)

    def test_market_slippage_and_actual_margin_overrun_remain_truthfully_booked(self):
        book = prepare(ready())
        evidence = receipt(book, price="105")
        settled = observe(book, evidence)
        self.assertEqual(settled.signal.economic.ledger.baskets[0].average_entry, 105)
        self.assertEqual(settled.signal.economic.stages[0].own_capital, evidence.posted_margin)
        self.assertIn("market_fill_above_planning_price", settled.notices)
        self.assertIn("actual_stage_margin_overrun", settled.notices)

    def test_delayed_receipt_uses_fresh_marks_without_rechecking_expired_signal(self):
        book = prepare(ready())
        order = book.pending
        book = prices(book, "97", seconds=45)
        self.assertEqual(book.pending, order)
        with self.assertRaisesRegex(ValueError, "stale closed"):
            assess_capital_signal(book.signal, "SYNTH0", D(97), book.as_of)
        settled = observe(book, price="97")
        self.assertEqual(len(settled.signal.economic.stages), 1)
        self.assertFalse(settled.signal.economic.ledger.halted)

    def test_wrong_order_size_and_stale_evidence_are_rejected(self):
        book = prepare(ready())
        variants = (
            replace(receipt(book), order_digest="foreign"),
            replace(receipt(book), quantity=book.pending.request.quantity + D(1)),
            replace(receipt(book), quantity=book.pending.request.quantity - D(".1")),
            replace(receipt(book), observed_at=book.as_of + timedelta(seconds=1)),
        )
        for evidence in variants:
            with self.subTest(evidence=evidence), self.assertRaises(ValueError):
                observe_broker_entry(book, evidence, book.revision, book.as_of)
        with self.assertRaisesRegex(ValueError, "fresh"):
            observe_broker_entry(book, receipt(book), book.revision, book.as_of + timedelta(seconds=6))
        with self.assertRaisesRegex(ValueError, "stale revision"):
            observe_broker_entry(book, receipt(book), book.revision - 1, book.as_of)
        with self.assertRaises(ValueError):
            observe(book, replace(receipt(book), quantity=D("1.234567891"), state="canceled"))

    def test_cumulative_quantity_and_average_cannot_regress_or_be_rewritten(self):
        book = prepare(ready())
        book = observe(book, state="partially_filled", quantity="1", price="97")
        for fields in (
            dict(state="partially_filled", quantity="0.5", price="97"),
            dict(state="partially_filled", quantity="1", price="96"),
        ):
            with self.subTest(fields=fields), self.assertRaisesRegex(ValueError, "regressing"):
                observe(book, **fields)
        terminal = observe(book, replace(receipt(book), signed_fee=None))
        with self.assertRaisesRegex(ValueError, "regressing"):
            observe(terminal, state="partially_filled", quantity="2", price="97")

    def test_duplicates_after_settlement_and_changed_revision_cannot_book_twice(self):
        book = prepare(ready(), command_id="once")
        evidence = receipt(book)
        settled = observe(book, evidence)
        with self.assertRaises(ValueError):
            observe(settled, evidence)
        with self.assertRaises(ValueError):
            prepare_broker_entry(settled, "SYNTH1", D(100), "once", settled.revision, settled.as_of)
        self.assertEqual(len(settled.signal.economic.stages), 1)

    def test_five_real_rsi_stages_keep_margin_schedule_and_manual_sixth(self):
        book = observe(prepare(ready()), price="98")
        last = D(98)
        amounts = [D("293.13365892")]
        for stage in range(2, 6):
            for _ in range(20):
                book = advance(book, last)
            book = advance(book, last * D("1.04"))
            self.assertTrue(book.signal.signals[0].rearmed)
            last *= D(".95")
            book = advance(book, last)
            book = prepare(book, price=last)
            amounts.append(book.pending.request.posted_margin)
            book = observe(book, price=last)
            self.assertEqual(book.signal.economic.stages[-1].stage, stage)
            self.assertFalse(book.signal.signals[0].rearmed)
        self.assertEqual(amounts, list(book.signal.profile.plan.stage_capital("SYNTH0")[:5]))
        self.assertEqual(amounts, [D("293.13365892"), D("366.41707366"),
                                  D("458.02134207"), D("572.52667759"), D("715.65834699")])
        self.assertTrue(book.signal.signals[0].manual_notice)
        self.assertEqual(book.signal.profile.plan.stage_capital("SYNTH0")[5], D("894.57293374"))
        with self.assertRaisesRegex(ValueError, "manual sixth"):
            prepare(book, price=last)

    def test_next_buy_uses_last_actual_fill_price_not_the_planning_price(self):
        book = observe(prepare(ready()), price="97")
        for _ in range(20):
            book = advance(book, "97")
        book = advance(book, "100")
        self.assertTrue(book.signal.signals[0].rearmed)
        book = advance(book, "92.15")
        with self.assertRaisesRegex(ValueError, "five-percent"):
            prepare(book, price="92.16")
        book = prepare(book, price="92.15")
        self.assertEqual(book.pending.assessment.capital.stage, 2)

    def test_capacity_is_funded_slots_and_not_candidate_count(self):
        book = ready(grid=True, candidates=5, slots=3, limit=7)
        for symbol in ("SYNTH0", "SYNTH1", "SYNTH2"):
            book = observe(prepare(book, symbol=symbol), price="98")
        with self.assertRaisesRegex(ValueError, "simultaneous_limit"):
            prepare(book, symbol="SYNTH3")
        self.assertEqual(sum(bool(b.quantity) for b in book.signal.economic.ledger.baskets), 3)

    def test_native_maximum_does_not_silently_reduce_reserved_stage_volume(self):
        signal = warmed().signal
        plan = replace(signal.profile.plan, grid_rules=tuple(
            replace(rule, maximum_market_quantity=D(1)) for rule in signal.profile.plan.grid_rules))
        economic = replace(signal.economic, ledger=replace(signal.economic.ledger, plan=plan))
        signal = replace(signal, profile=replace(signal.profile, plan=plan), economic=economic)
        with self.assertRaisesRegex(ValueError, "splitting"):
            prepare(start_broker_entries(signal))

    def test_existing_paper_fills_cannot_be_adopted_as_native_positions(self):
        with self.assertRaisesRegex(ValueError, "simulated"):
            start_broker_entries(buy(h1_ready()))
        with self.assertRaises(ValueError):
            start_broker_entries({"signal": h1_ready()})

    def test_first_order_needs_two_closed_rsi_values_and_frozen2x(self):
        book = start_broker_entries(h1_start())
        for i in range(15):
            book = advance(book, 130 - 2 * i)
        self.assertEqual(book.signal.signals[0].below_count, 1)
        with self.assertRaisesRegex(ValueError, "confirmation"):
            prepare(book, price="102")
        book = advance(book, "100")
        self.assertEqual(prepare(book).pending.request.requested_leverage, 2)
        prepared = prepare(book)
        decisions = tuple(replace(d, leverage=D(3)) for d in prepared.signal.economic.decisions)
        signal = replace(prepared.signal, economic=replace(prepared.signal.economic, decisions=decisions))
        with self.assertRaisesRegex(ValueError, "fixed2x"):
            prepare(replace(book, signal=signal))

    def test_falling_price_without_rsi_rearm_never_sends_next_stage(self):
        book = observe(prepare(ready()))
        book = advance(book, "90")
        with self.assertRaisesRegex(ValueError, "rearm"):
            prepare(book, price="90")
        self.assertEqual(len(book.signal.economic.stages), 1)

    def test_6_and_8_percent_warnings_do_not_block_a_fully_reserved_next_buy(self):
        book = ready()
        for symbol in book.signal.profile.plan.symbols:
            book = observe(prepare(book, symbol=symbol), price="98")
        for _ in range(20):
            book = advance(book, "98")
        book = advance(book, "101.92")
        self.assertTrue(book.signal.signals[0].rearmed)
        book = advance(book, "50")
        self.assertIn("initial_loss_limit", book.signal.economic.warnings)
        self.assertIn("daily_loss_limit", book.signal.economic.warnings)
        self.assertFalse(book.signal.economic.ledger.halted)
        self.assertTrue(all(not s.exit_reasons for s in book.signal.signals))
        book = prepare(book, price="50")
        self.assertEqual(book.pending.request.posted_margin, D("366.41707366"))
        self.assertEqual(book.pending.assessment.capital.stage, 2)

    def test_actual_underfunded_fill_is_retained_with_integrity_failure(self):
        book = prepare(ready())
        settled = observe(book, margin=D(".01"))
        self.assertEqual(settled.signal.economic.ledger.baskets[0].margin_committed, D(".01"))
        self.assertEqual(len(settled.signal.economic.stages), 1)
        self.assertIn("entry_fill_initial_margin_breach",
                      settled.signal.economic.ledger.halt_reasons)


if __name__ == "__main__":
    unittest.main()
