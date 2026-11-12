"""Synthetic causal H1/H4 checks; no claim of native market performance."""
from dataclasses import FrozenInstanceError, replace
from datetime import timedelta
from decimal import Decimal
import unittest

from investalo_trading.futures_capital_signals import (
    CapitalHour, CapitalSignalProfile, assess_capital_signal, declare_signal_leverage,
    observe_capital_prices, record_signal_economic_event, replay_capital_hour,
    simulate_signal_entry, start_capital_signals,
)
from investalo_trading.futures_ledger import ExitFill, FundingSettlement, LedgerMark, MarginPosting, MarkBatch
from investalo_trading.models import IndicatorState
from investalo_trading.timeframe_research import ResearchCandle
from test_futures_capital_research import liquidation, start as capital_start
from test_futures_ledger import AT, fixture

D = Decimal


def start(hours=1, slippage="0"):
    economic = capital_start()
    profile = CapitalSignalProfile(economic.ledger.plan, hours, D(slippage), "synthetic-costs")
    return start_capital_signals(
        profile, economic, tuple(LedgerMark(s, D("100")) for s in profile.plan.symbols))


def hour(state, price, *, mark=None, all_assets=False, close=None):
    close = close or (state.last_hour.close_time if state.last_hour else AT) + timedelta(hours=1)
    def bars(kind):
        value = D(mark) if kind == "mark" and mark is not None else D(price)
        return tuple(ResearchCandle(
            f"{s}:USDT-M:{kind}", close - timedelta(hours=1), close,
            p, p + 1, p - 1, p,
        ) for i, s in enumerate(state.profile.plan.symbols)
                     for p in (value if i == 0 or all_assets else D("100"),))
    return CapitalHour(bars("trade"), bars("mark"))


def advance_hour(state, price, **kwargs):
    frame = hour(state, price, **kwargs)
    return replay_capital_hour(state, frame, state.revision, frame.close_time)


def h4(state, price, **kwargs):
    for _ in range(4):
        state = advance_hour(state, price, **kwargs)
    return state


def ready(**kwargs):
    state = start(**kwargs)
    for i in range(16):
        state = h4(state, D("130") - 2 * i, all_assets=True)
    return state


def buy(state, symbol="SYNTH0", leverage="2", *, price=None, maximum=None, event_id=None):
    index = state.profile.plan.symbols.index(symbol)
    if not state.economic.ledger.baskets[index].quantity:
        state = declare_signal_leverage(
            state, symbol, D(leverage), "declared-synthetic-leverage",
            f"decision-{state.revision}", state.revision, state.as_of)
    maximum = D(maximum) if maximum is not None else state.trade_prices[index].price * (1 + state.profile.slippage)
    assessment = assess_capital_signal(state, symbol, maximum, state.as_of)
    if not assessment.capital.allowed:
        raise AssertionError(assessment.capital.reasons)
    return simulate_signal_entry(
        state, assessment, D(price) if price is not None else maximum,
        event_id or f"entry-{state.revision}", state.revision, state.as_of)


def quote(state, price, *, mark=None, all_assets=False, at=None, event_id=None):
    trade = tuple(LedgerMark(p.symbol, D(price) if i == 0 or all_assets else p.price)
                  for i, p in enumerate(state.trade_prices))
    marks = tuple(LedgerMark(b.symbol, D(mark if mark is not None else price)
                            if i == 0 or all_assets else b.mark)
                  for i, b in enumerate(state.economic.ledger.baskets))
    return observe_capital_prices(
        state, trade, marks, event_id or f"quote-{state.revision}",
        state.revision, at or state.as_of + timedelta(microseconds=1))


def event(state, payload, at=None):
    return record_signal_economic_event(
        state, payload, f"economic-{state.revision}", state.revision, at or state.as_of)


class CapitalSignalTests(unittest.TestCase):
    def test_separate_profile_identity_and_no_legacy_or_unsupported_interval(self):
        economic = capital_start()
        a = start(1)
        b = start(4)
        self.assertNotEqual(a.profile.profile_digest, b.profile.profile_digest)
        self.assertFalse(a.execution_enabled)
        with self.assertRaises(ValueError):
            CapitalSignalProfile(fixture().plan, 1, D("0"), "synthetic")
        for interval in (True, 2, 0):
            with self.subTest(interval=interval), self.assertRaises(ValueError):
                CapitalSignalProfile(economic.ledger.plan, interval, D("0"), "synthetic")
        with self.assertRaises(FrozenInstanceError):
            a.profile.protection_hours = 4

    def test_advanced_economic_state_cannot_be_wrapped_as_a_fresh_start(self):
        state = buy(ready())
        with self.assertRaisesRegex(ValueError, "genesis"):
            start_capital_signals(state.profile, state.economic, state.trade_prices)

    def test_no_lookahead_open_hour_does_not_change_state(self):
        state = start()
        frame = hour(state, "1000")
        before = state.state_digest
        with self.assertRaisesRegex(ValueError, "unfinished"):
            replay_capital_hour(state, frame, state.revision, AT)
        self.assertEqual(state.state_digest, before)

    def test_first_hour_can_follow_finer_observations_inside_that_hour(self):
        state = quote(start(), "101", at=AT + timedelta(minutes=15))
        state = advance_hour(state, "102")
        self.assertEqual(state.last_hour.close_time, AT + timedelta(hours=1))
        self.assertEqual(state.signals[0].protection_indicator.true_ranges, 1)
        self.assertEqual(state.signals[0].entry_indicator.true_ranges, 0)

    def test_futures_price_kinds_and_canonical_complete_axes_are_required(self):
        state = start()
        frame = hour(state, "100")
        foreign = replace(frame.trade[0], symbol="BTCUSDT")
        with self.assertRaisesRegex(ValueError, "price kinds"):
            replay_capital_hour(state, replace(frame, trade=(foreign, *frame.trade[1:])),
                                state.revision, frame.close_time)
        with self.assertRaises(ValueError):
            replace(frame, mark=frame.mark[:-1])
        with self.assertRaises(ValueError):
            replace(frame, mark=(replace(frame.mark[0], close_time=AT + timedelta(hours=2)),
                                 *frame.mark[1:]))

    def test_gapped_revised_and_old_hours_are_rejected_last_repeat_is_idempotent(self):
        state = advance_hour(start(), "100")
        self.assertIs(replay_capital_hour(state, state.last_hour, state.revision, state.as_of), state)
        for data in (hour(state, "100", close=AT + timedelta(hours=3)),
                     hour(start(), "101")):
            with self.assertRaises(ValueError):
                replay_capital_hour(state, data, state.revision, data.close_time)
        state = advance_hour(state, "100")
        with self.assertRaises(ValueError):
            replay_capital_hour(state, hour(start(), "100"), state.revision, state.as_of)

    def test_actual_wilder_h4_confirmation_needs_two_closes_h1_does_not_add_entries(self):
        state = start()
        for i in range(15):
            state = h4(state, D("130") - 2 * i, all_assets=True)
        self.assertEqual(state.signals[0].entry_indicator.rsi, 0)
        self.assertEqual(state.signals[0].below_count, 1)
        with self.assertRaisesRegex(ValueError, "confirmation"):
            buy(state)
        for _ in range(3):
            state = advance_hour(state, "100", all_assets=True)
            self.assertEqual(state.signals[0].entry_indicator.true_ranges, 15)
            self.assertEqual(state.signals[0].below_count, 1)
        state = advance_hour(state, "100", all_assets=True)
        self.assertEqual(state.signals[0].entry_indicator.true_ranges, 16)
        self.assertEqual(state.signals[0].protection_indicator.true_ranges, 64)
        state = buy(state)
        self.assertEqual(state.economic.ledger.baskets[0].margin_committed, D("293.13365892"))
        self.assertEqual(state.economic.ledger.baskets[0].broker_leverage, 2)

    def test_entry_requires_frozen_leverage_from_an_actual_first_signal(self):
        state = start()
        with self.assertRaisesRegex(ValueError, "signal"):
            declare_signal_leverage(state, "SYNTH0", D("10"), "declared", "d", state.revision, AT)
        state = ready()
        with self.assertRaisesRegex(ValueError, "freeze"):
            assess_capital_signal(state, "SYNTH0", D("100"), state.as_of)
        state = buy(state, leverage="5")
        self.assertEqual(state.economic.ledger.baskets[0].broker_leverage, 5)
        with self.assertRaises(ValueError):
            declare_signal_leverage(state, "SYNTH0", D("10"), "changed", "d", state.revision, state.as_of)

    def test_actual_rearm_then_five_percent_drop_adds_full_second_own_capital_stage(self):
        state = buy(ready())
        for _ in range(20):
            state = h4(state, "100")
        state = h4(state, "104")
        self.assertTrue(state.signals[0].rearmed)
        self.assertGreater(state.signals[0].entry_indicator.rsi, 30)
        self.assertFalse(state.signals[0].protected)
        state = h4(state, "95")
        self.assertLess(state.signals[0].entry_indicator.rsi, 30)
        state = buy(state)
        self.assertEqual(tuple(r.stage for r in state.economic.stages), (1, 2))
        self.assertEqual(state.economic.stages[-1].own_capital, D("366.41707366"))
        self.assertLess(state.economic.ledger.baskets[0].average_entry, 100)
        self.assertEqual(state.economic.ledger.baskets[0].first_fill, 100)
        self.assertFalse(state.signals[0].rearmed)

    def test_lower_price_without_actual_rearm_cannot_add_stage(self):
        state = h4(buy(ready()), "90")
        with self.assertRaisesRegex(ValueError, "rearm"):
            assess_capital_signal(state, "SYNTH0", D("90"), state.as_of)

    def test_exact_rsi30_is_neither_entry_nor_rearm(self):
        state = buy(ready())
        boundary = IndicatorState(previous_close=D("100"), changes=14,
                                  average_gain=D("3"), average_loss=D("7"))
        state = replace(state, signals=(replace(state.signals[0], entry_indicator=boundary),
                                        *state.signals[1:]))
        state = h4(state, "100")
        self.assertEqual(state.signals[0].entry_indicator.rsi, 30)
        self.assertFalse(state.signals[0].rearmed)
        with self.assertRaisesRegex(ValueError, "no regular"):
            assess_capital_signal(state, "SYNTH0", D("90"), state.as_of)

    def test_slippage_and_better_actual_fill_control_the_next_price_ceiling(self):
        state = buy(ready(slippage=".01"), price="99")
        state = h4(state, "94.05")
        state = replace(state, signals=(replace(state.signals[0], rearmed=True), *state.signals[1:]))
        with self.assertRaisesRegex(ValueError, "five-percent"):
            assess_capital_signal(state, "SYNTH0", D("94.05") * D("1.01"), state.as_of)
        self.assertEqual(assess_capital_signal(
            state, "SYNTH0", D("94.05"), state.as_of).capital.stage, 2)

    def test_all_five_stages_use_actual_rsi_and_manual_sixth_stays_reserved(self):
        state = buy(ready())
        last = D("100")
        for stage in range(2, 6):
            for _ in range(20):
                state = h4(state, last)
            state = h4(state, last * D("1.04"))
            self.assertTrue(state.signals[0].rearmed)
            last *= D(".95")
            state = h4(state, last)
            state = buy(state)
            self.assertEqual(state.economic.stages[-1].stage, stage)
            self.assertEqual(state.economic.ledger.baskets[0].broker_leverage, 2)
        self.assertEqual(state.economic.ledger.baskets[0].margin_committed, D("2405.75709923"))
        self.assertTrue(state.signals[0].manual_notice)
        self.assertGreater(state.profile.plan.stage_capital("SYNTH0")[5], 0)
        with self.assertRaisesRegex(ValueError, "manual sixth"):
            assess_capital_signal(state, "SYNTH0", last, state.as_of)

    def test_three_parallel_baskets_can_cross_warning_limits_without_forced_account_exit(self):
        state = ready()
        for symbol in state.profile.plan.symbols:
            state = buy(state, symbol, leverage="10")
        state = quote(state, "91", all_assets=True)
        self.assertIn("initial_loss_limit", state.economic.warnings)
        self.assertIn("daily_loss_limit", state.economic.warnings)
        self.assertFalse(state.economic.ledger.halted)
        self.assertFalse(state.economic.liquidation_required)
        self.assertTrue(all(not s.exit_reasons for s in state.signals))

    def test_fills_do_not_reuse_previous_close_as_profit_activation(self):
        state = buy(ready(), price="90")
        self.assertFalse(state.signals[0].protected)
        state = event(state, MarkBatch(tuple(LedgerMark(b.symbol, b.mark)
                                            for b in state.economic.ledger.baskets)),
                      state.as_of + timedelta(microseconds=1))
        self.assertFalse(state.signals[0].protected)
        state = event(state, FundingSettlement("SYNTH0", D("100"), D(".001")))
        self.assertFalse(state.signals[0].protected)
        state = quote(state, "94.5")
        self.assertTrue(state.signals[0].protected)

    def test_closed_h1_and_h4_protection_have_same_entries_and_different_update_cadence(self):
        a, b = ready(hours=1), ready(hours=4)
        self.assertEqual(a.signals[0].entry_indicator, b.signals[0].entry_indicator)
        self.assertEqual(a.signals[0].protection_indicator.true_ranges, 64)
        self.assertEqual(b.signals[0].protection_indicator.true_ranges, 16)
        a, b = buy(a), buy(b)
        for value in ("110", "120", "130"):
            a, b = advance_hour(a, value), advance_hour(b, value)
        self.assertEqual(a.signals[0].entry_indicator, b.signals[0].entry_indicator)
        self.assertEqual(a.signals[0].protection_indicator.true_ranges, 67)
        self.assertEqual(b.signals[0].protection_indicator.true_ranges, 16)
        self.assertGreater(a.signals[0].stop, b.signals[0].stop)

    def test_intrahour_stop_is_observed_before_next_closed_indicator(self):
        state = quote(buy(ready()), "110")
        stop = state.signals[0].stop
        indicator = state.signals[0].protection_indicator
        state = quote(state, stop - D(".01"))
        self.assertIn("protective_stop_crossed", state.signals[0].exit_reasons)
        self.assertEqual(state.signals[0].protection_indicator, indicator)
        self.assertEqual(state.signals[0].entry_indicator.true_ranges, 16)
        with self.assertRaisesRegex(ValueError, "no regular"):
            assess_capital_signal(state, "SYNTH0", D("95"), state.as_of)

    def test_stop_never_moves_down_and_pending_exit_is_not_erased_by_recovery(self):
        state = quote(buy(ready()), "110")
        old_stop = state.signals[0].stop
        state = quote(state, "120")
        self.assertGreaterEqual(state.signals[0].stop, old_stop)
        state = quote(state, "99")
        reasons = state.signals[0].exit_reasons
        state = quote(state, "130")
        self.assertTrue(set(reasons) <= set(state.signals[0].exit_reasons))

    def test_liquidation_precedes_emergency_and_requires_explicit_terminal_settlement(self):
        state = quote(buy(ready(), leverage="10"), "80")
        self.assertEqual(state.signals[0].exit_reasons[0], "liquidation_settlement_required")
        self.assertNotIn("first_fill_emergency_exit", state.signals[0].exit_reasons)
        b = state.economic.ledger.baskets[0]
        with self.assertRaisesRegex(ValueError, "terminal receipt"):
            event(state, ExitFill("SYNTH0", b.quantity, D("80"), D("0")))
        state = event(state, liquidation(state.economic))
        self.assertEqual(state.signals[0].exit_reasons, ("liquidated",))
        state = quote(state, "110")
        self.assertFalse(state.economic.ledger.baskets[0].quantity)
        with self.assertRaises(ValueError):
            buy(state)
        # Its settled loss does not disable another genuinely funded first entry.
        state = buy(state, "SYNTH1")
        self.assertGreater(state.economic.ledger.baskets[1].quantity, 0)

    def test_trade_emergency_and_mark_liquidation_are_separate_price_kinds(self):
        state = quote(buy(ready()), "44", mark="100")
        self.assertIn("first_fill_emergency_exit", state.signals[0].exit_reasons)
        self.assertFalse(state.economic.liquidation_required)
        self.assertNotIn("liquidation_settlement_required", state.signals[0].exit_reasons)

    def test_price_recovery_cannot_erase_an_already_observed_liquidation_obligation(self):
        state = quote(buy(ready(), leverage="10"), "80")
        state = quote(state, "110")
        self.assertFalse(state.economic.liquidation_required)
        self.assertIn("liquidation_settlement_required", state.signals[0].exit_reasons)
        b = state.economic.ledger.baskets[0]
        with self.assertRaisesRegex(ValueError, "terminal receipt"):
            event(state, ExitFill("SYNTH0", b.quantity, D("110"), D("0")))
        with self.assertRaisesRegex(ValueError, "unsettled liquidation"):
            buy(state, "SYNTH1")

    def test_signed_funding_changes_protected_net_floor_without_inventing_price(self):
        state = quote(buy(ready()), "110")
        before = state.signals[0].stop
        trade_at = state.trade_at
        state = event(state, FundingSettlement("SYNTH0", D("110"), D(".01")))
        self.assertGreater(state.signals[0].stop, before)
        self.assertEqual(state.trade_at, trade_at)
        self.assertLess(state.economic.ledger.baskets[0].funding_net, 0)
        with self.assertRaises(ValueError):
            event(state, MarginPosting("SYNTH0", D("10")))

    def test_partial_exit_and_funding_keep_whole_cycle_costs_in_the_net_floor(self):
        state = quote(buy(ready()), "110")
        old = state.signals[0].stop
        state = event(state, ExitFill("SYNTH0", D("1"), D("110"), D(".11")))
        self.assertEqual(state.economic.ledger.baskets[0].realized_price_pnl, D("10"))
        self.assertEqual(state.signals[0].stop, old)
        # A later mark is required before the subsequent funding phase.
        state = event(state, MarkBatch(tuple(LedgerMark(b.symbol, b.mark)
                                            for b in state.economic.ledger.baskets)),
                      state.as_of + timedelta(microseconds=1))
        state = event(state, FundingSettlement("SYNTH0", D("110"), D(".025")))
        self.assertGreater(state.signals[0].stop, old)
        self.assertFalse(state.economic.ledger.halted)

    def test_normal_exit_resets_cycle_but_retains_wilder_history_and_new_leverage_is_possible(self):
        state = quote(buy(ready()), "110")
        indicator = state.signals[0].entry_indicator
        protection = state.signals[0].protection_indicator
        b = state.economic.ledger.baskets[0]
        state = event(state, ExitFill("SYNTH0", b.quantity, D("110"), b.quantity * D(".11")))
        self.assertEqual(state.signals[0].cycle, 2)
        self.assertEqual(state.signals[0].entry_indicator, indicator)
        self.assertEqual(state.signals[0].protection_indicator, protection)
        self.assertFalse(state.signals[0].protected)
        self.assertFalse(state.signals[0].below_count)
        for _ in range(2):
            state = h4(state, "90")
        state = buy(state, leverage="5")
        self.assertEqual(state.economic.ledger.baskets[0].broker_leverage, 5)
        self.assertEqual(tuple(d.leverage for d in state.economic.decisions), (D("2"), D("5")))

    def test_original_initial_equity_and_exact_midnight_basis_survive_new_day(self):
        state = ready()
        state = buy(state)
        while state.last_hour.close_time.hour:
            state = advance_hour(state, "99")
        self.assertEqual(state.economic.ledger.day_started_at, state.last_hour.close_time)
        self.assertEqual(state.economic.ledger.day_start_equity, state.economic.ledger.equity)
        self.assertEqual(state.profile.plan.initial_equity, D("10000"))

    def test_stale_signal_changed_assessment_and_duplicate_evidence_are_rejected(self):
        state = ready()
        state = declare_signal_leverage(
            state, "SYNTH0", D("2"), "declared", "decision", state.revision, state.as_of)
        assessment = assess_capital_signal(state, "SYNTH0", D("100"), state.as_of)
        changed = quote(state, "100", event_id="quote-once")
        with self.assertRaisesRegex(ValueError, "stale"):
            simulate_signal_entry(changed, assessment, D("100"), "fill", changed.revision, changed.as_of)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            quote(changed, "100", event_id="quote-once")
        with self.assertRaisesRegex(ValueError, "stale"):
            assess_capital_signal(state, "SYNTH0", D("100"), state.as_of + timedelta(seconds=31))

    def test_repeated_last_frame_after_fill_does_not_activate_hindsight_protection(self):
        state = buy(ready(), price="90")
        self.assertIs(replay_capital_hour(state, state.last_hour, state.revision, state.as_of), state)
        self.assertFalse(state.signals[0].protected)


if __name__ == "__main__":
    unittest.main()
