"""Synthetic causal evidence; these tests are not historical futures performance."""
from dataclasses import FrozenInstanceError, replace
from datetime import timedelta
from decimal import Decimal, localcontext
import unittest

from investalo_trading.futures_ledger import (
    DailyBasis, EntryFill, ExitFill, FundingSettlement, LedgerMark, MarginPosting, MarkBatch,
)
from investalo_trading.futures_pending import OrderResolution, start_pending_research
from investalo_trading.futures_signals import (
    FIRST_FILL_MODEL, H4Frame, ReplayProfile, replay_attempt, replay_cancel_unattempted,
    replay_economic_event, replay_fill, replay_frame, replay_terminal, reserve_signal,
    start_signal_replay,
)
from investalo_trading.models import Candle
from test_futures_ledger import AT, fixture

D = Decimal


def start(slots=3, buffer=None, slippage="0"):
    ledger = fixture(slots)
    # Deliberately declared synthetic allocation, not a proposed economic default.
    buffer = D(buffer) if buffer is not None else ledger.plan.budgets[0].margin_capital - D("580")
    profile = ReplayProfile(ledger.plan, tuple((s, buffer) for s in ledger.plan.symbols),
                            D(slippage), "synthetic-profile-only", FIRST_FILL_MODEL)
    return start_signal_replay(profile, start_pending_research(ledger))


def frame(state, price, *, close=None, mark=None):
    close = close or (state.last_frame.close_time if state.last_frame else AT) + timedelta(hours=4)
    prices = tuple(D(price) if i == 0 else D("100") for i in range(len(state.signals)))
    def bars(kind):
        return tuple(Candle(
            f"{s}:USDT-M:{kind}", close - timedelta(hours=4), close,
            p, p + 1, p / 2 if p <= 1 else p - 1, p,
        ) for s, p in zip(state.profile.plan.symbols,
                         prices if kind == "trade" or mark is None else
                         tuple(D(mark) if i == 0 else D("100") for i in range(len(prices))),
                         strict=True))
    return H4Frame(bars("trade"), bars("mark"))


def advance(state, price, *, mark=None):
    data = frame(state, price, mark=mark)
    return replay_frame(state, data, state.revision, data.close_time)


def ready(**kwargs):
    state = start(**kwargs)
    for i in range(16):
        state = advance(state, D("130") - 2 * i)
    return state


def reserve(state, intent=None):
    return reserve_signal(state, "SYNTH0", intent or f"intent-{state.revision}",
                          state.revision, state.as_of)


def attempt(state, order=None):
    return replay_attempt(state, state.binding.intent_id, order or f"order-{state.revision}",
                          state.revision, state.as_of)


def fill(state, *, quantity=None, price=None, margin=None, fill_id=None, order=None):
    p = state.economic.pending
    q = p.request.quantity if quantity is None else D(quantity)
    price = p.request.maximum_fill_price if price is None else D(price)
    margin = p.request.posted_margin if margin is None else D(margin)
    return replay_fill(state, EntryFill(
        p.request.symbol, q, price, margin, q * price * D(".001"), D("2"),
    ), order or p.order_id, fill_id or f"fill-{state.revision}", state.revision, state.as_of)


def terminal(state, status="filled"):
    p = state.economic.pending
    return replay_terminal(state, OrderResolution(
        p.intent_id, p.order_id, p.filled_quantity, p.posted_margin, p.fees,
        status, "synthetic-terminal-evidence",
    ), state.revision, state.as_of)


def purchased(state=None):
    return terminal(fill(attempt(reserve(state or ready()))))


class FuturesSignalReplayTests(unittest.TestCase):
    def test_shared_wilder_needs_two_completed_below_30_bars(self):
        state = start()
        for i in range(15):
            state = advance(state, D("130") - 2 * i)
        self.assertEqual(state.signals[0].indicator.rsi, 0)
        self.assertEqual(state.signals[0].below_count, 1)
        with self.assertRaisesRegex(ValueError, "confirmation"):
            reserve(state)
        state = advance(state, "100")
        prepared = reserve(state)
        self.assertEqual(prepared.binding.stage, 1)
        self.assertEqual(prepared.binding.cycle, 1)
        self.assertEqual(prepared.binding.request.requested_leverage, 2)
        self.assertFalse(prepared.execution_enabled)
        self.assertEqual(prepared.economic.ledger, state.economic.ledger)

    def test_buffers_manual_sixth_and_costs_have_separate_frozen_pools(self):
        state = ready()
        amounts = state.profile.stage_margins("SYNTH0")
        budget = state.profile.plan.budgets[0]
        self.assertEqual(len(amounts), 6)
        self.assertLessEqual(sum(amounts) + D("2400") + budget.cost_reserve, budget.capital)
        for a, b in zip(amounts, amounts[1:]):
            self.assertLessEqual(abs(b - a * D("1.25")), state.profile.plan.quantum * 2)
        binding = reserve(state).binding
        self.assertEqual(binding.buffer_margin, D("2400"))
        self.assertEqual(binding.stage_margin, amounts[0])
        self.assertEqual(binding.request.posted_margin, amounts[0] + D("2400"))
        self.assertNotEqual(amounts[5], binding.buffer_margin)

    def test_real_fill_partial_terminal_vwap_controls_next_stage(self):
        state = attempt(reserve(ready()))
        q = state.binding.request.quantity
        first = D(".2")
        state = fill(state, quantity=first, price="99")
        state = fill(state, quantity=D(".3"), price="98", margin="0")
        self.assertFalse(state.quarantine)
        self.assertEqual(len(state.signals[0].stages), 0)
        self.assertEqual(state.economic.pending.filled_quantity, D(".5"))
        self.assertLess(D(".5"), q)
        state = terminal(state, "cancelled")
        self.assertEqual(state.signals[0].stages[0].vwap, D("98.4"))
        self.assertEqual(state.economic.ledger.baskets[0].first_fill, D("99"))
        state = advance(state, "90")
        with self.assertRaisesRegex(ValueError, "rearm"):
            reserve(state)

    def test_terminal_cancel_preserves_rearm_observed_after_last_actual_partial_fill(self):
        state = fill(attempt(reserve(ready())), quantity=".5", price="99")
        for _ in range(20):
            state = advance(state, "99")
        state = advance(state, "103")
        self.assertTrue(state.signals[0].rearmed)
        self.assertFalse(state.signals[0].protected)
        state = advance(state, "94")
        self.assertLess(state.signals[0].indicator.rsi, 30)
        state = terminal(state, "cancelled")
        self.assertTrue(state.signals[0].rearmed)
        self.assertEqual(reserve(state).binding.stage, 2)

    def test_cancel_with_no_fill_does_not_consume_stage_or_margin(self):
        state = attempt(reserve(ready()))
        ledger = state.economic.ledger
        state = terminal(state, "cancelled")
        self.assertEqual(state.economic.ledger, ledger)
        self.assertFalse(state.signals[0].stages)
        self.assertEqual(reserve(state).binding.stage, 1)

    def test_cancel_unattempted_keeps_actual_ledger(self):
        state = reserve(ready())
        ledger = state.economic.ledger
        result = replay_cancel_unattempted(state, state.binding.intent_id,
                                          state.revision, state.as_of)
        self.assertIsNone(result.binding)
        self.assertEqual(result.economic.ledger, ledger)
        self.assertEqual(reserve(result).binding.stage, 1)
        with self.assertRaises(ValueError):
            replay_cancel_unattempted(attempt(state), state.binding.intent_id,
                                      state.revision + 1, state.as_of)

    def test_under_30_without_intervening_rearm_cannot_average_down(self):
        state = advance(purchased(), "85")
        with self.assertRaisesRegex(ValueError, "rearm"):
            reserve(state)

    def test_real_incremental_rearm_then_five_percent_drop_adds_second_stage(self):
        state = purchased()
        for _ in range(20):
            state = advance(state, "100")
        state = advance(state, "104")
        self.assertGreater(state.signals[0].indicator.rsi, 30)
        self.assertTrue(state.signals[0].rearmed)
        self.assertFalse(state.signals[0].protected)
        state = advance(state, "95")
        self.assertLess(state.signals[0].indicator.rsi, 30)
        state = terminal(fill(attempt(reserve(state))))
        self.assertFalse(state.quarantine)
        self.assertEqual(len(state.signals[0].stages), 2)
        self.assertLess(state.economic.ledger.baskets[0].average_entry, D("100"))
        self.assertEqual(state.economic.ledger.baskets[0].first_fill, D("100"))
        self.assertEqual(state.signals[0].stages[-1].vwap, D("95"))
        self.assertEqual(state.economic.ledger.baskets[0].broker_leverage, D("2"))

    def test_exact_rsi30_is_neither_entry_nor_rearm(self):
        state = purchased()
        signal = state.signals[0]
        indicator = replace(signal.indicator, average_gain=D("3"), average_loss=D("7"),
                            previous_close=D("100"))
        state = replace(state, signals=(replace(signal, indicator=indicator), *state.signals[1:]))
        state = advance(state, "100")
        self.assertEqual(state.signals[0].indicator.rsi, D("30"))
        self.assertFalse(state.signals[0].rearmed)
        with self.assertRaisesRegex(ValueError, "no regular"):
            reserve(state)

    def test_rearm_alone_cannot_bypass_actual_last_stage_drop(self):
        state = purchased()
        # Boundary test isolates the price gate; no fabricated historical result.
        signal = replace(state.signals[0], rearmed=True)
        state = replace(state, signals=(signal, *state.signals[1:]))
        with self.assertRaisesRegex(ValueError, "five-percent"):
            reserve(state)

    def test_fill_price_ceiling_includes_slippage_in_five_percent_gate(self):
        state = purchased(ready(slippage=".01"))
        signal = replace(state.signals[0], rearmed=True)
        data = frame(state, state.signals[0].stages[-1].vwap * D(".95"))
        state = replay_frame(state, data, state.revision, data.close_time)
        state = replace(state, signals=(replace(state.signals[0], rearmed=True), *state.signals[1:]))
        with self.assertRaisesRegex(ValueError, "five-percent"):
            reserve(state)

    def test_five_regular_stages_never_automatically_spend_manual_sixth(self):
        state = purchased()
        for low in ("94", "88", "82", "76"):
            # Avoid +5% profit protection while constructing independent RSI boundary states.
            state = advance(state, low)
            signal = replace(state.signals[0], rearmed=True)
            state = replace(state, signals=(signal, *state.signals[1:]))
            state = terminal(fill(attempt(reserve(state))))
        self.assertFalse(state.quarantine)
        self.assertEqual(tuple(s.stage for s in state.signals[0].stages), (1, 2, 3, 4, 5))
        self.assertTrue(state.signals[0].manual_notice)
        self.assertGreater(state.profile.stage_margins("SYNTH0")[5], 0)
        state = replace(state, signals=(replace(state.signals[0], rearmed=True), *state.signals[1:]))
        with self.assertRaisesRegex(ValueError, "no regular"):
            reserve(state)

    def test_missing_full_first_fragment_margin_books_then_quarantines(self):
        state = attempt(reserve(ready()))
        before = state.economic.ledger.unposted_cash
        state = fill(state, quantity=".1", margin="60")
        self.assertLess(state.economic.ledger.unposted_cash, before)
        self.assertEqual(state.economic.ledger.baskets[0].quantity, D(".1"))
        self.assertIn("declared_first_fragment_margin_missing", state.quarantine)
        self.assertIsNotNone(state.economic.pending)
        with self.assertRaises(ValueError):
            reserve(state)

    def test_outside_intent_price_books_truth_and_preserves_cycle_binding(self):
        state = attempt(reserve(ready()))
        original = state.binding
        state = fill(state, price="101")
        self.assertIn("entry_fill_outside_intent", state.quarantine)
        self.assertEqual(state.binding.signal_digest, original.signal_digest)
        self.assertEqual(state.binding.cycle, 1)
        self.assertEqual(state.economic.ledger.baskets[0].first_fill, D("101"))

    def test_cheap_fill_cannot_use_pre_fill_close_as_profit_observation(self):
        state = terminal(fill(attempt(reserve(ready())), price="90"))
        self.assertFalse(state.signals[0].protected)
        self.assertIsNone(state.signals[0].stop)
        state = advance(state, "93")
        self.assertFalse(state.signals[0].protected)
        state = advance(state, "95")
        self.assertTrue(state.signals[0].protected)

    def test_late_pending_fill_after_protection_books_then_quarantines(self):
        state = fill(attempt(reserve(ready())), quantity=".1")
        state = advance(state, "110")
        self.assertTrue(state.signals[0].protected)
        state = fill(state, quantity=".1", margin="0")
        self.assertIn("entry_after_protection_or_exit", state.quarantine)
        self.assertEqual(state.economic.ledger.baskets[0].quantity, D(".2"))
        self.assertIsNotNone(state.economic.pending)

    def test_unplanned_fill_never_creates_a_regular_stage(self):
        state = ready()
        state = replay_fill(state, EntryFill("SYNTH0", D(".1"), D("100"),
                                            D("60"), D(".01"), D("2")),
                            "unexpected-order", "unexpected-fill", state.revision, state.as_of)
        self.assertIn("entry_outside_signal_cycle", state.quarantine)
        self.assertEqual(state.economic.ledger.baskets[0].quantity, D(".1"))
        self.assertFalse(state.signals[0].stages)

    def test_late_fill_after_close_is_booked_in_new_ledger_cycle_and_quarantined(self):
        state = attempt(reserve(ready()))
        state = fill(state, quantity=".1")
        state = replay_fill(state, ExitFill("SYNTH0", D(".1"), D("100"), D(".01")),
                            "exit-order", "exit-first-fragment", state.revision, state.as_of)
        self.assertIsNotNone(state.binding)
        # Ledger order phases require a later instant for entry after exit.
        at = state.as_of + timedelta(seconds=1)
        p = state.economic.pending
        state = replay_fill(state, EntryFill("SYNTH0", D(".1"), D("99"), ZERO, D(".0099"), D("2")),
                            p.order_id, "late-fragment", state.revision, at)
        self.assertEqual(state.economic.ledger.baskets[0].cycle, 2)
        self.assertEqual(state.binding.cycle, 1)
        self.assertIn("entry_outside_signal_cycle", state.quarantine)
        state = terminal(state, "cancelled")
        self.assertIn("terminal_outside_signal_cycle", state.quarantine)
        self.assertFalse(state.signals[0].stages)

    def test_new_flat_cycle_retains_indicator_history_but_needs_new_confirmation(self):
        state = purchased()
        old = state.signals[0].indicator
        q = state.economic.ledger.baskets[0].quantity
        state = replay_fill(state, ExitFill("SYNTH0", q, D("100"), q * D(".1")),
                            "exit-order", "close-all", state.revision, state.as_of)
        self.assertEqual(state.signals[0].cycle, 2)
        self.assertEqual(state.signals[0].indicator, old)
        self.assertFalse(state.signals[0].stages)
        self.assertEqual(state.signals[0].below_count, 0)
        state = advance(state, "99")
        with self.assertRaisesRegex(ValueError, "confirmation"):
            reserve(state)
        state = advance(state, "98")
        self.assertEqual(reserve(state).binding.cycle, 2)

    def test_funding_changes_net_floor_and_protection_blocks_further_buys(self):
        state = purchased()
        state = advance(state, "110")
        self.assertTrue(state.signals[0].protected)
        old_stop = state.signals[0].stop
        state = replay_economic_event(state, FundingSettlement("SYNTH0", D("110"), D(".01")),
                                      "funding-debit", state.revision, state.as_of)
        self.assertGreater(state.signals[0].stop, old_stop)
        with self.assertRaisesRegex(ValueError, "no regular"):
            reserve(state)
        state = advance(state, "101")
        self.assertIn("protective_stop_crossed", state.signals[0].exit_reasons)
        self.assertGreater(state.economic.ledger.baskets[0].quantity, 0)  # No invented exit.

    def test_positive_funding_never_lowers_existing_stop(self):
        state = advance(purchased(), "110")
        stop = state.signals[0].stop
        state = replay_economic_event(state, FundingSettlement("SYNTH0", D("110"), D("-.01")),
                                      "funding-credit", state.revision, state.as_of)
        self.assertEqual(state.signals[0].stop, stop)

    def test_partial_exit_net_floor_accounts_for_already_realized_profit(self):
        state = advance(purchased(), "110")
        stop = state.signals[0].stop
        state = replay_fill(state, ExitFill("SYNTH0", D(".2"), D("110"), D(".022")),
                            "partial-exit-order", "partial-exit", state.revision, state.as_of)
        self.assertEqual(state.signals[0].stop, stop)
        self.assertTrue(state.signals[0].protected)
        self.assertGreater(state.economic.ledger.baskets[0].realized_price_pnl, 0)

    def test_first_fill_emergency_and_mark_account_halt_do_not_invent_stop_fills(self):
        state = advance(purchased(), "44")
        self.assertIn("first_fill_emergency_exit", state.signals[0].exit_reasons)
        self.assertGreater(state.economic.ledger.baskets[0].quantity, 0)
        state = replay_fill(state, EntryFill("SYNTH0", D("20"), D("44"), ZERO, D(".88"), D("2")),
                            "unexpected-extra", "known-extra", state.revision, state.as_of)
        state = advance(state, "44", mark="1")
        self.assertTrue(state.economic.ledger.halted)
        self.assertIn("account_risk_exit_required", state.signals[0].exit_reasons)
        state = replay_economic_event(state, MarginPosting("SYNTH0", D("1")),
                                      "known-posting", state.revision, state.as_of)
        self.assertTrue(state.economic.ledger.halted)

    def test_midnight_basis_matches_complete_mark_not_trade_and_does_not_reset_halt(self):
        state = purchased()
        state = advance(state, "99", mark="98")
        data = frame(state, "98", mark="97")
        state = replay_frame(state, data, state.revision, data.close_time)
        self.assertEqual(state.economic.ledger.day_started_at, data.close_time)
        self.assertEqual(state.economic.ledger.day_start_equity, state.economic.ledger.equity)
        self.assertEqual(state.economic.ledger.day_evidence_digest, data.frame_digest)
        self.assertEqual(state.signals[0].indicator.previous_close, D("98"))
        self.assertEqual(state.economic.ledger.baskets[0].mark, D("97"))

    def test_insolvent_midnight_keeps_known_marks_without_fabricated_positive_basis(self):
        state = purchased()
        state = replay_fill(state, EntryFill("SYNTH0", D("200"), D("100"), ZERO, ZERO, D("2")),
                            "known-unsafe", "known-unsafe-fill", state.revision, state.as_of)
        original_basis = state.economic.ledger.day_started_at
        state = advance(state, "99", mark="1")
        self.assertLess(state.economic.ledger.equity, 0)
        state = advance(state, "98", mark="1")
        self.assertEqual(state.as_of.hour, 0)
        self.assertEqual(state.economic.ledger.day_started_at, original_basis)
        state = advance(state, "97", mark="1")
        self.assertEqual(state.as_of.hour, 4)
        self.assertTrue(state.economic.ledger.halted)
        self.assertEqual(state.economic.ledger.baskets[0].marked_at, state.last_frame.close_time)
        self.assertGreater(state.economic.ledger.baskets[0].quantity, 200)

    def test_pending_intent_cannot_be_attempted_from_a_later_h4_frame(self):
        state = reserve(ready())
        state = advance(state, "99")
        with self.assertRaisesRegex(ValueError, "stale"):
            attempt(state)
        self.assertIsNotNone(state.economic.pending)
        state = replay_cancel_unattempted(state, state.binding.intent_id, state.revision, state.as_of)
        self.assertIsNone(state.binding)

    def test_attempt_rechecks_funding_halt_after_signal_reservation(self):
        state = advance(purchased(), "95")
        state = replace(state, signals=(replace(state.signals[0], rearmed=True), *state.signals[1:]))
        state = reserve(state)
        state = replay_economic_event(state, FundingSettlement("SYNTH0", D("95"), D("1")),
                                      "known-cost-breach", state.revision, state.as_of)
        self.assertTrue(state.economic.ledger.halted)
        with self.assertRaisesRegex(ValueError, "no longer covered"):
            attempt(state)
        self.assertIsNone(state.economic.pending.order_id)

    def test_unknown_attempt_never_retries_or_times_out(self):
        state = attempt(reserve(ready()))
        with self.assertRaises(ValueError):
            attempt(state)
        state = advance(state, "99")
        with self.assertRaises(ValueError):
            replay_cancel_unattempted(state, state.binding.intent_id, state.revision, state.as_of)
        self.assertIsNotNone(state.binding)

    def test_frame_revision_and_time_axis_are_bound(self):
        state = ready()
        self.assertIs(replay_frame(state, state.last_frame, state.revision, state.as_of), state)
        with self.assertRaises(ValueError):
            replay_frame(state, frame(state, "99"), state.revision - 1, state.as_of)
        next_frame = frame(state, "99")
        with self.assertRaisesRegex(ValueError, "unfinished"):
            replay_frame(state, next_frame, state.revision, next_frame.close_time - timedelta(seconds=1))
        with self.assertRaisesRegex(ValueError, "gapped"):
            replay_frame(state, frame(state, "99", close=next_frame.close_time + timedelta(hours=4)),
                         state.revision, next_frame.close_time + timedelta(hours=4))
        revised = replace(state.last_frame, trade=frame(state, "99", close=state.as_of).trade)
        with self.assertRaisesRegex(ValueError, "revised"):
            replay_frame(state, revised, state.revision, state.as_of)

    def test_spot_or_wrong_price_kind_cannot_seed_futures_rsi(self):
        state = start()
        data = frame(state, "100")
        for symbol in ("SYNTH0", "SYNTH0:USDT-M:mark", "SYNTH1:USDT-M:trade"):
            bad = replace(data, trade=(replace(data.trade[0], symbol=symbol), *data.trade[1:]))
            with self.subTest(symbol=symbol), self.assertRaisesRegex(ValueError, "native futures"):
                replay_frame(state, bad, state.revision, data.close_time)
        with self.assertRaises(ValueError):
            H4Frame(data.trade[:-1], data.mark)

    def test_no_fake_midnight_repair_and_external_mark_basis_injection(self):
        state = start()
        data = frame(state, "100", close=AT + timedelta(days=1, hours=4))
        with self.assertRaisesRegex(ValueError, "midnight"):
            replay_frame(state, data, state.revision, data.close_time)
        for payload in (DailyBasis(D("10000"), "fake"), MarkBatch(tuple(
                LedgerMark(s, D("100")) for s in state.profile.plan.symbols))):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                replay_economic_event(state, payload, "fake-event", state.revision, state.as_of)

    def test_stale_signal_and_revisions_cannot_buy(self):
        state = ready()
        with self.assertRaisesRegex(ValueError, "stale H4"):
            reserve_signal(state, "SYNTH0", "intent", state.revision,
                           state.as_of + timedelta(seconds=31))
        with self.assertRaisesRegex(ValueError, "stale revision"):
            reserve_signal(state, "SYNTH0", "intent", state.revision - 1, state.as_of)

    def test_profile_requires_explicit_buffer_and_research_model(self):
        state = start()
        for changes in (
            {"first_fill_model": "broker-atomic"},
            {"margin_buffers": ()},
            {"margin_buffers": tuple((s, D("3000")) for s in state.profile.plan.symbols)},
            {"slippage": D("1")},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(state.profile, **changes)
        with self.assertRaises(FrozenInstanceError):
            state.profile.slippage = D(".01")
        with self.assertRaises(ValueError):
            start_signal_replay(state.profile, attempt(reserve(ready())).economic)

    def test_all_seven_funded_slots_and_decimal_context_replay_are_deterministic(self):
        baseline = reserve(ready(slots=7))
        with localcontext() as context:
            context.prec = 6
            other = reserve(ready(slots=7))
        self.assertEqual(other, baseline)
        self.assertEqual(len(other.signals), 7)
        self.assertEqual(other.binding.request.requested_leverage, 2)

    def test_replayed_fill_ids_and_terminal_totals_cannot_be_reused(self):
        state = fill(attempt(reserve(ready())), quantity=".1", fill_id="fill-fixed")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            fill(state, quantity=".1", margin="0", fill_id="fill-fixed")
        p = state.economic.pending
        wrong = OrderResolution(p.intent_id, p.order_id, p.filled_quantity + D(".1"),
                                p.posted_margin, p.fees, "cancelled", "wrong-total")
        with self.assertRaisesRegex(ValueError, "totals"):
            replay_terminal(state, wrong, state.revision, state.as_of)
        state = terminal(state, "cancelled")
        with self.assertRaises(ValueError):
            replay_terminal(state, wrong, state.revision, state.as_of)

    def test_three_actual_baskets_share_risk_but_each_has_own_signal_and_margin(self):
        state = start()
        for i in range(16):
            data = frame(state, D("130") - 2 * i)
            data = H4Frame(
                tuple(replace(data.trade[0], symbol=b.symbol) for b in data.trade),
                tuple(replace(data.mark[0], symbol=b.symbol) for b in data.mark),
            )
            state = replay_frame(state, data, state.revision, data.close_time)
        for symbol in state.profile.plan.symbols:
            state = reserve_signal(state, symbol, f"{symbol}-intent", state.revision, state.as_of)
            state = terminal(fill(attempt(state)))
        self.assertFalse(state.quarantine)
        self.assertEqual(tuple(s.cycle for s in state.signals), (1, 1, 1))
        self.assertEqual(tuple(len(s.stages) for s in state.signals), (1, 1, 1))
        self.assertTrue(all(b.quantity > 0 for b in state.economic.ledger.baskets))


ZERO = D("0")

if __name__ == "__main__":
    unittest.main()
