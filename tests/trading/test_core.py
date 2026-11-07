from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext, ROUND_UP
import unittest

from investalo_trading import (
    Candle, CryptoEngine, EntryStage, Fill, IndicatorState, OrderIntent, OrderRecord,
    OrderStatus, PaperSimulator, Quote, Side, SimulationCosts, StrategyConfig,
    TradingRejected, dump_state, load_state,
)
from investalo_trading.indicators import advance

D = Decimal
START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def candle(index: int, close: str, previous: str | None = None) -> Candle:
    p, o = D(close), D(previous or close)
    return Candle("BTCUSDT", START + timedelta(hours=4 * index),
                  START + timedelta(hours=4 * (index + 1)), o, max(p, o), min(p, o), p)


class TradingCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = CryptoEngine()
        self.state = self.engine.start("tenant-a", "paper-a", START)

    def quoted(self, state, price="100", at=START, symbol="BTCUSDT"):
        return self.engine.on_quote(state, Quote(symbol, at, D(price), D(price))).state

    def filled_stages(self, count=5):
        """Real intent/fill transitions; no fabricated allocation in production."""
        state = self.state
        for number in range(1, count + 1):
            at = START + timedelta(minutes=number)
            price = D("100") * D(".95") ** (number - 1)
            state = self.engine.on_quote(state, Quote("BTCUSDT", at, price, price)).state
            amount = self.engine.config.allocations[number - 1].quantize(D(".00000001"), rounding="ROUND_DOWN")
            intent = OrderIntent(f"fixture-{number}", state.basket("BTCUSDT").basket_id, "BTCUSDT",
                                 Side.BUY, at, self.engine.config.version, "fixture",
                                 stage=number, maximum_quote=amount,
                                 maximum_price=None if number == 1 else price)
            state = replace(state, orders=state.orders + (OrderRecord(intent),))
            quantity = (amount / price).quantize(D(".00000001"), rounding="ROUND_DOWN")
            state = self.engine.apply_fill(state, Fill(
                f"fixture-fill-{number}", intent.intent_id, at + timedelta(microseconds=1),
                quantity, price, D(".01"))).state
        return state

    def seeded_rsi(self, state, rsi, *, previous_close="90", last_index=0, stages=1, rearmed=False):
        """Indicator seed with analytically controlled next RSI for rule edge cases."""
        basket = state.basket("BTCUSDT")
        gain, loss = D(rsi), D("100") - D(rsi)
        indicators = IndicatorState(
            previous_close=D(previous_close), changes=14, average_gain=gain,
            average_loss=loss, true_ranges=10, atr=D("100"),
            upper_band=D("1000"), lower_band=D("1"), rsi=D(rsi),
        )
        return replace(state, baskets=tuple(
            replace(b, indicators=indicators, last_bar_open=START + timedelta(hours=4 * last_index),
                    rearmed=rearmed) if b.symbol == "BTCUSDT" else b for b in state.baskets))

    def test_allocations_reserve_and_no_leverage(self):
        allocations = self.engine.config.allocations
        self.assertAlmostEqual(float(allocations[0]), 44.4097493278)
        self.assertAlmostEqual(float(allocations[5]), 135.5277994622)
        self.assertAlmostEqual(float(sum(allocations)), 500.0)
        state = self.filled_stages()
        self.assertEqual(state.basket("BTCUSDT").completed_regular_stages, 5)
        self.assertFalse(state.basket("BTCUSDT").manual_used)
        self.assertLessEqual(state.basket("BTCUSDT").principal_spent, D("500"))

    def test_indicator_seed_is_wilder_not_simple_rolling_average(self):
        cfg = self.engine.config
        state = IndicatorState()
        for i in range(15):
            state = advance(state, candle(i, str(100 - i)), cfg)
        self.assertEqual(state.rsi, 0)
        self.assertEqual(state.average_loss, 1)
        state = advance(state, candle(15, "86", "86"), cfg)  # flat: average loss decays 13/14
        self.assertAlmostEqual(state.average_loss, D(13) / D(14), delta=D("1e-27"))
        self.assertEqual(state.rsi, 0)

    def test_supertrend_wilder_atr_hl2_and_strict_band_crossing(self):
        state = IndicatorState()
        for index in range(10):
            opened = START + timedelta(hours=4 * index)
            state = advance(state, Candle("BTCUSDT", opened, opened + timedelta(hours=4),
                                          D("100"), D("101"), D("99"), D("100")),
                            self.engine.config)
        self.assertEqual(state.atr, D("2"))
        self.assertEqual(state.supertrend, D("106"))  # HL2 100 plus ATR2 * 3.
        self.assertFalse(state.bullish)
        opened = START + timedelta(hours=40)
        state = advance(state, Candle("BTCUSDT", opened, opened + timedelta(hours=4),
                                      D("100"), D("108"), D("99"), D("107")),
                        self.engine.config)
        self.assertEqual(state.atr, D("2.7"))  # Wilder: (9*2 + TR9)/10.
        self.assertTrue(state.bullish)
        self.assertEqual(state.supertrend, D("95.4"))  # HL2 103.5 minus ATR2.7 * 3.
        opened += timedelta(hours=4)
        state = advance(state, Candle("BTCUSDT", opened, opened + timedelta(hours=4),
                                      D("107"), D("107"), D("95.4"), D("95.4")),
                        self.engine.config)
        self.assertTrue(state.bullish)  # A close equal to the carried lower band does not flip.
        self.assertEqual(state.supertrend, D("95.4"))
        opened += timedelta(hours=4)
        state = advance(state, Candle("BTCUSDT", opened, opened + timedelta(hours=4),
                                      D("95.4"), D("95.4"), D("95.3"), D("95.3")),
                        self.engine.config)
        self.assertFalse(state.bullish)

    def test_first_entry_requires_two_closed_sub30_bars_and_idempotence(self):
        state = self.state
        created = []
        for i in range(17):
            bar = candle(i, str(100 - i))
            state = self.quoted(state, str(bar.close), bar.close_time)
            if bar.close_time.hour == 0:
                state = self.engine.reset_day(state, bar.close_time)
            transition = self.engine.on_bar(state, bar)
            state = transition.state
            created.extend(transition.intents)
            if i == 14:
                self.assertFalse(transition.intents)
            if i == 15:
                self.assertEqual(len(transition.intents), 1)
                again = self.engine.on_bar(load_state(dump_state(state)), bar)
                self.assertEqual(again.state, state)
                self.assertFalse(again.intents)
        self.assertEqual(len(created), 1)
        self.assertEqual(state.basket("BTCUSDT").quantity, 0)  # intent is not a fill

    def test_unfinished_revised_and_gapped_candle_fail_closed(self):
        bar = candle(0, "100")
        with self.assertRaisesRegex(TradingRejected, "unfinished"):
            self.engine.on_bar(self.state, bar, observed_at=bar.close_time - timedelta(seconds=1))
        result = self.engine.on_bar(self.quoted(self.state, at=bar.close_time), bar)
        with self.assertRaisesRegex(TradingRejected, "revised"):
            self.engine.on_bar(result.state, candle(0, "99"))
        gap = self.engine.on_bar(result.state, candle(2, "98"))
        self.assertEqual(gap.state, result.state)
        self.assertEqual(gap.events[0].reason, "candle_gap")

    def test_equal30_neither_rearms_nor_triggers(self):
        state = self.seeded_rsi(self.filled_stages(1), "30", previous_close="90")
        at = START + timedelta(hours=8)
        state = self.quoted(state, "90", at)
        result = self.engine.on_bar(state, candle(1, "90"))
        self.assertEqual(result.state.basket("BTCUSDT").indicators.rsi, D("30"))
        self.assertFalse(result.state.basket("BTCUSDT").rearmed)
        self.assertFalse(result.intents)

    def test_rearm_then_single_closed_sub30_next_entry(self):
        state = self.seeded_rsi(self.filled_stages(1), "40", previous_close="90")
        at = START + timedelta(hours=8)
        state = self.quoted(state, "90", at)
        state = self.engine.on_bar(state, candle(1, "90")).state
        self.assertTrue(state.basket("BTCUSDT").rearmed)
        state = self.seeded_rsi(state, "20", previous_close="90", last_index=1, rearmed=True)
        at = START + timedelta(hours=12)
        state = self.quoted(state, "90", at)
        result = self.engine.on_bar(state, candle(2, "90"))
        self.assertEqual(result.intents[0].stage, 2)
        self.assertTrue(result.state.basket("BTCUSDT").rearmed)  # only fill consumes latch
        fill = Fill("rearm-fill", result.intents[0].intent_id, at + timedelta(microseconds=1), D(".1"), D("90"))
        self.assertFalse(self.engine.apply_fill(result.state, fill).state.basket("BTCUSDT").rearmed)

    def test_regular_sixth_is_never_generated(self):
        state = self.seeded_rsi(self.filled_stages(5), "20", previous_close="60", rearmed=True)
        at = START + timedelta(hours=8)
        state = self.quoted(state, "60", at)
        result = self.engine.on_bar(state, candle(1, "60"))
        self.assertFalse(any(i.side == Side.BUY for i in result.intents))

    def test_manual_requires_five_stages_price_cap_and_audited_approval(self):
        with self.assertRaises(TradingRejected):
            self.engine.preview_manual(self.filled_stages(4), "BTCUSDT", START + timedelta(minutes=4))
        state = self.filled_stages(5)
        now = START + timedelta(minutes=6)
        state = self.quoted(state, "78", now)
        with self.assertRaisesRegex(TradingRejected, "price_above_limit"):
            self.engine.preview_manual(state, "BTCUSDT", now)
        state = self.quoted(state, "60", now + timedelta(seconds=1))
        now += timedelta(seconds=1)
        preview = self.engine.preview_manual(state, "BTCUSDT", now)
        self.assertEqual(preview.maximum_price, state.basket("BTCUSDT").last_regular_price * D(".95"))
        with self.assertRaisesRegex(TradingRejected, "authorization"):
            self.engine.confirm_manual(state, preview, now, authorization_reference="")
        accepted = self.engine.confirm_manual(state, preview, now, authorization_reference="mfa-audit-1")
        self.assertEqual(accepted.intents[0].stage, 6)
        with self.assertRaises(TradingRejected):
            self.engine.confirm_manual(accepted.state, preview, now, authorization_reference="mfa-audit-1")
        self.assertLessEqual(accepted.intents[0].maximum_quote, D("500") - state.basket("BTCUSDT").principal_spent)

    def test_manual_preview_cannot_be_reused_after_quote_change_or_expiry(self):
        now = START + timedelta(minutes=6)
        state = self.quoted(self.filled_stages(), "60", now)
        preview = self.engine.preview_manual(state, "BTCUSDT", now)
        changed = self.quoted(state, "59", now + timedelta(seconds=1))
        with self.assertRaisesRegex(TradingRejected, "preview_changed"):
            self.engine.confirm_manual(changed, preview, now + timedelta(seconds=1), authorization_reference="audit")
        with self.assertRaisesRegex(TradingRejected, "expired"):
            self.engine.confirm_manual(state, preview, preview.expires_at, authorization_reference="audit")
        with self.assertRaisesRegex(TradingRejected, "invalid_preview"):
            self.engine.confirm_manual(state, replace(preview, expires_at=now + timedelta(days=1)),
                                       now, authorization_reference="audit")
        with self.assertRaisesRegex(TradingRejected, "preview_changed"):
            self.engine.confirm_manual(state, replace(preview, quoted_ask=D("1")),
                                       now, authorization_reference="audit")

    def test_gap_55_exit_has_priority_over_manual_and_regular_buys(self):
        state = self.filled_stages()
        now = START + timedelta(minutes=6)
        result = self.engine.on_quote(state, Quote("BTCUSDT", now, D("40"), D("41")))
        self.assertTrue(result.state.basket("BTCUSDT").exiting)
        self.assertEqual(len(result.intents), 1)
        self.assertEqual(result.intents[0].side, Side.SELL)
        self.assertEqual(result.intents[0].reason, "first_fill_55pct_exit")
        with self.assertRaises(TradingRejected):
            self.engine.preview_manual(result.state, "BTCUSDT", now)

    def test_55_risk_stop_survives_flat_restart_until_explicit_basket_resume(self):
        state = self.filled_stages(1)
        at = START + timedelta(minutes=2)
        state = self.engine.on_quote(state, Quote("BTCUSDT", at, D("40"), D("40"))).state
        with self.assertRaisesRegex(TradingRejected, "not_flat"):
            self.engine.resume_basket(state, "BTCUSDT", at)
        state, _, _ = PaperSimulator(self.engine).settle(state, at)
        self.assertTrue(state.basket("BTCUSDT").risk_stopped)
        self.assertFalse(state.account.halted)  # Basket stop, independent account limits.
        state = load_state(dump_state(state))
        state = self.seeded_rsi(state, "20", previous_close="40")
        for index in (1, 2):
            bar = candle(index, "40")
            state = self.quoted(state, "40", bar.close_time)
            result = self.engine.on_bar(state, bar)
            state = result.state
            self.assertFalse(result.intents)
        self.assertEqual(result.events[-1].reason, "basket_risk_stopped")
        resumed = self.engine.resume_basket(state, "BTCUSDT", candle(2, "40").close_time)
        self.assertEqual(resumed.basket("BTCUSDT").sub30_count, 0)
        self.assertFalse(resumed.basket("BTCUSDT").risk_stopped)
        for index in (3, 4):
            bar = candle(index, "40")
            resumed = self.quoted(resumed, "40", bar.close_time)
            result = self.engine.on_bar(resumed, bar)
            resumed = result.state
            if index == 3:
                self.assertFalse(result.intents)
            else:
                self.assertEqual(result.intents[0].stage, 1)

    def test_explicit_manual_paper_execution_remains_one_use_and_within_budget(self):
        now = START + timedelta(minutes=6)
        state = self.quoted(self.filled_stages(), "60", now)
        preview = self.engine.preview_manual(state, "BTCUSDT", now)
        accepted = self.engine.confirm_manual(state, preview, now, authorization_reference="mfa-audit")
        state, fills, events = PaperSimulator(self.engine).settle(accepted.state, now)
        self.assertEqual(len(fills), 1)
        basket = state.basket("BTCUSDT")
        self.assertTrue(basket.manual_used)
        self.assertEqual(len(basket.entries), 6)
        self.assertLessEqual(basket.principal_spent, D("500"))
        self.assertLess(basket.costs_spent, D("5"))
        repeated, duplicate_fills, _ = PaperSimulator(self.engine).settle(state, now)
        self.assertEqual(repeated, state)
        self.assertFalse(duplicate_fills)
        with self.assertRaisesRegex(TradingRejected, "already_used"):
            self.engine.preview_manual(state, "BTCUSDT", now + timedelta(seconds=1))

    def test_protection_net_floor_monotonic_and_blocks_buys(self):
        state = self.filled_stages(1)
        at = START + timedelta(minutes=2)
        state = self.quoted(state, "106", at)
        basket = state.basket("BTCUSDT")
        self.assertTrue(basket.protected)
        self.assertGreater(basket.stop_price, D("100"))
        previous_stop = basket.stop_price
        state = self.quoted(state, "105", at + timedelta(seconds=1))
        self.assertGreaterEqual(state.basket("BTCUSDT").stop_price, previous_stop)
        with self.assertRaisesRegex(TradingRejected, "profit_protection"):
            self.engine.preview_manual(state, "BTCUSDT", at + timedelta(seconds=1))
        result = self.engine.on_quote(state, Quote("BTCUSDT", at + timedelta(seconds=2), D("99"), D("99")))
        self.assertEqual(result.intents[0].reason, "trailing_stop")

    def test_net_floor_covers_modeled_exit_fee_and_slippage(self):
        state = self.quoted(self.filled_stages(1), "106", START + timedelta(minutes=2))
        floor = state.basket("BTCUSDT").stop_price
        at = START + timedelta(minutes=3)
        state = self.engine.on_quote(state, Quote("BTCUSDT", at, floor, floor)).state
        state, fills, _ = PaperSimulator(self.engine).settle(state, at)
        self.assertEqual(len(fills), 1)
        self.assertEqual(len(state.closed_baskets), 1)
        self.assertAlmostEqual(state.closed_baskets[0].net_pnl, D("0"), delta=D("1e-27"))

    def test_partial_fill_vwap_duplicate_and_restart_unknown_order(self):
        state = self.quoted(self.state)
        intent = OrderIntent("partial", state.basket("BTCUSDT").basket_id, "BTCUSDT", Side.BUY,
                             START, self.engine.config.version, "rsi_entry", stage=1, maximum_quote=D("44"))
        state = replace(state, orders=(OrderRecord(intent),))
        first = Fill("fill-a", "partial", START + timedelta(seconds=1),
                     D(".1"), D("100"), D(".01"), final=False)
        state = self.engine.apply_fill(state, first).state
        self.assertEqual(state.basket("BTCUSDT").completed_regular_stages, 0)
        self.assertEqual(self.engine.apply_fill(state, first).state, state)
        with self.assertRaisesRegex(TradingRejected, "conflicting"):
            self.engine.apply_fill(state, replace(first, price=D("99")))
        with self.assertRaisesRegex(TradingRejected, "out_of_order_fill"):
            self.engine.apply_fill(state, Fill("earlier", "partial", START, D(".01"), D("100")))
        unknown = self.engine.mark_order_unknown(state, "partial")
        restored = load_state(dump_state(unknown))
        self.assertEqual(restored, unknown)
        with self.assertRaisesRegex(TradingRejected, "uncertain"):
            self.engine.validate_dispatch(restored, "partial", START)
        second = Fill("fill-b", "partial", START + timedelta(seconds=1), D(".1"), D("90"), D(".01"))
        final = self.engine.apply_fill(restored, second).state
        self.assertEqual(final.basket("BTCUSDT").entries[0].vwap, D("95"))
        self.assertEqual(final.basket("BTCUSDT").completed_regular_stages, 1)

    def test_fill_violation_is_booked_then_halts_not_hidden(self):
        state = self.quoted(self.state)
        intent = OrderIntent("bad", state.basket("BTCUSDT").basket_id, "BTCUSDT", Side.BUY,
                             START, self.engine.config.version, "rsi_entry", stage=1,
                             maximum_quote=D("10"), maximum_price=D("100"))
        state = replace(state, orders=(OrderRecord(intent),))
        result = self.engine.apply_fill(state, Fill("bad-fill", "bad", START, D(".2"), D("110")))
        self.assertEqual(result.state.basket("BTCUSDT").quantity, D(".2"))
        self.assertEqual(result.state.account.cash, D("9978"))
        self.assertTrue(result.state.account.halted)
        self.assertIn("fill_exceeds_quote_budget", result.state.account.halt_reasons)
        self.assertEqual(result.intents[0].side, Side.SELL)

    def test_daily_equity_reset_missing_baseline_and_initial_limit(self):
        state = self.quoted(self.state, "100", START)
        day2 = START + timedelta(days=1)
        self.assertIn("daily_baseline_required", self.engine.risk_reasons(state, day2))
        state = self.engine.reset_day(state, day2)
        self.assertEqual(state.account.day_start_equity, D("10000"))
        loss = replace(state, account=replace(state.account, cash=D("9400")))
        result = self.engine.on_quote(loss, Quote("BTCUSDT", day2, D("99"), D("99")))
        self.assertTrue(result.state.account.halted)
        self.assertIn("daily_loss_limit", result.state.account.halt_reasons)
        another = replace(state, account=replace(state.account, cash=D("9200"), day_start_equity=D("9500")))
        self.assertIn("initial_loss_limit", self.engine.risk_reasons(another, day2))
        self.assertNotIn("daily_loss_limit", self.engine.risk_reasons(another, day2))
        with self.assertRaises(TradingRejected):
            self.engine.resume(result.state, day2)

    def test_midnight_baseline_requires_current_valuation_for_each_holding(self):
        state = self.filled_stages(1)
        day2 = START + timedelta(days=1)
        with self.assertRaisesRegex(TradingRejected, "midnight_valuation"):
            self.engine.reset_day(state, day2)
        state = self.quoted(state, "99", day2)
        reset = self.engine.reset_day(state, day2)
        self.assertEqual(reset.account.day_start_equity, state.equity)
        self.assertEqual(self.engine.reset_day(reset, day2), reset)

    def test_strategy_configuration_is_bound_to_snapshot(self):
        modified = CryptoEngine(replace(self.engine.config, rsi_period=10))
        with self.assertRaisesRegex(ValueError, "configuration"):
            modified.on_quote(self.state, Quote("BTCUSDT", START, D("100"), D("100")))
        with self.assertRaises(ValueError):
            load_state(dump_state(self.state).replace('"schema_version":1', '"schema_version":9'))

    def test_recheck_before_dispatch_rejects_changed_risk(self):
        state = self.quoted(self.state)
        intent = OrderIntent("dispatch", state.basket("BTCUSDT").basket_id, "BTCUSDT", Side.BUY,
                             START, self.engine.config.version, "rsi_entry", stage=1, maximum_quote=D("44"))
        state = replace(state, orders=(OrderRecord(intent),))
        self.engine.validate_dispatch(state, "dispatch", START)
        changed = replace(state, account=replace(state.account, halted=True))
        with self.assertRaisesRegex(TradingRejected, "halted"):
            self.engine.validate_dispatch(changed, "dispatch", START)

    def test_old_identical_bar_replay_after_later_bars_is_a_noop(self):
        state = self.state
        for i in range(3):
            state = self.engine.on_bar(state, candle(i, "100")).state
        restored = load_state(dump_state(state))
        result = self.engine.on_bar(restored, candle(0, "100"))
        self.assertEqual(result.state, restored)
        self.assertFalse(result.intents)

    def test_delayed_closed_signal_and_stale_quotes_do_not_open_positions(self):
        state = self.seeded_rsi(self.filled_stages(1), "20", previous_close="90", rearmed=True)
        now = START + timedelta(hours=8, minutes=1)
        state = self.quoted(state, "90", now)
        result = self.engine.on_bar(state, candle(1, "90"), observed_at=now)
        self.assertFalse(result.intents)
        self.assertEqual(result.events[-1].reason, "stale_signal")
        stale = self.engine.on_quote(state, Quote("BTCUSDT", now, D("1"), D("1")),
                                     now=now + timedelta(seconds=31))
        self.assertEqual(stale.state, state)
        self.assertEqual(stale.events[0].reason, "stale_quote")

    def test_unknown_partial_buy_is_cancelled_while_protective_sell_proceeds(self):
        state = self.quoted(self.state)
        intent = OrderIntent("pending", state.basket("BTCUSDT").basket_id, "BTCUSDT", Side.BUY,
                             START, self.engine.config.version, "rsi_entry", stage=1, maximum_quote=D("44"))
        state = replace(state, orders=(OrderRecord(intent),))
        state = self.engine.apply_fill(state, Fill("part", "pending", START, D(".1"), D("100"),
                                                  D(".01"), final=False)).state
        state = self.engine.mark_order_unknown(state, "pending")
        now = START + timedelta(seconds=1)
        result = self.engine.on_quote(state, Quote("BTCUSDT", now, D("40"), D("40")))
        self.assertEqual(result.state.orders[0].status, OrderStatus.CANCEL_REQUESTED)
        self.assertEqual(result.events[0].kind, "cancel_order")
        self.assertEqual(result.intents[0].side, Side.SELL)
        state = self.engine.apply_fill(result.state, Fill(
            "exit-part", result.intents[0].intent_id, now, D(".1"), D("40"), D(".01"))).state
        self.assertEqual(state.basket("BTCUSDT").quantity, 0)
        self.assertFalse(state.closed_baskets)  # unknown buy still requires reconciliation
        state = self.engine.reconcile_cancelled(state, "pending").state
        self.assertEqual(len(state.closed_baskets), 1)
        self.assertEqual(state.closed_baskets[0].net_pnl, D("-6.02"))
        self.assertEqual(state.basket("BTCUSDT").cycle, 1)

    def test_notification_is_once_and_instrument_minimum_is_not_rounded_up(self):
        state = self.filled_stages()
        self.assertTrue(state.basket("BTCUSDT").reserve_notified)
        result = self.engine.reconcile_cancelled(state, "fixture-5")
        self.assertFalse(result.events)
        from investalo_trading import InstrumentRules
        engine = CryptoEngine(instrument_rules=(InstrumentRules("BTCUSDT", minimum_quote=D("100")),))
        state = engine.start("t", "a", START)
        for i in range(16):
            bar = candle(i, str(100 - i))
            state = engine.on_quote(state, Quote("BTCUSDT", bar.close_time, bar.close, bar.close)).state
            if bar.close_time.hour == 0:
                state = engine.reset_day(state, bar.close_time)
            result = engine.on_bar(state, bar)
            state = result.state
        self.assertFalse(result.intents)
        self.assertEqual(result.events[-1].reason, "below_minimum_quote")

    def test_decimal_context_does_not_change_results(self):
        expected = PaperSimulator().run(SimulatorTests().series(30))
        with localcontext() as context:
            context.prec = 8
            context.rounding = ROUND_UP
            # Build identical input outside changed arithmetic context.
            actual = PaperSimulator().run(SimulatorTests().series(30))
        self.assertEqual(expected.fills, actual.fills)
        self.assertEqual(expected.state, actual.state)


class SimulatorTests(unittest.TestCase):
    def series(self, length=60):
        prices = [D("100") - D(i) for i in range(40)] + [D("61") + D(i) * 2 for i in range(20)]
        return [candle(i, str(p), str(prices[i - 1] if i else p)) for i, p in enumerate(prices[:length])]

    def test_reference_never_fabricates_manual_and_executes_after_closed_signal(self):
        result = PaperSimulator().run(self.series())
        buys = [f for f in result.fills if next(
            o.intent.side for o in result.state.orders if o.intent.intent_id == f.intent_id) == Side.BUY]
        self.assertTrue(buys)
        self.assertFalse(result.manual_fills_fabricated)
        self.assertFalse(any(o.intent.stage == 6 for o in result.state.orders))
        for fill in result.fills:
            intent = next(o.intent for o in result.state.orders if o.intent.intent_id == fill.intent_id)
            self.assertGreater(fill.occurred_at, intent.created_at)
        self.assertNotEqual(result.net_pnl, 0)

    def test_future_data_cannot_change_prefix_execution_or_indicator(self):
        bars = self.series()
        prefix = PaperSimulator().run(bars[:30])
        full = PaperSimulator().run(bars)
        cutoff = bars[29].close_time
        expected = [f for f in full.fills if f.occurred_at < cutoff]
        self.assertEqual(list(prefix.fills), expected)
        future_modified = bars[:30] + [replace(b, open=b.open * 3, high=b.high * 3,
                                             low=b.low * 3, close=b.close * 3) for b in bars[30:]]
        changed = PaperSimulator().run(future_modified)
        self.assertEqual([f for f in full.fills if f.occurred_at < cutoff],
                         [f for f in changed.fills if f.occurred_at < cutoff])

    def test_costs_in_execution_and_no_final_close_fill(self):
        bars = [candle(i, str(100 - i)) for i in range(16)]
        result = PaperSimulator().run(bars)
        self.assertFalse(result.fills)  # final bar only produces a signal
        self.assertEqual(result.net_pnl, 0)
        result = PaperSimulator().run(bars + [candle(16, "84")])
        self.assertTrue(result.fills)
        self.assertLess(result.state.account.cash, D("10000"))
        self.assertGreater(result.fills[0].fee, 0)
        self.assertGreater(result.fills[0].price, D("84"))

    def test_gap_history_and_duplicate_input_rejected(self):
        with self.assertRaisesRegex(ValueError, "gap"):
            PaperSimulator().run([candle(0, "100"), candle(2, "98")])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            PaperSimulator().run([candle(0, "100"), candle(0, "100")])

    def test_two_assets_share_account_equity_and_independent_basket_caps(self):
        btc = self.series()
        eth = [replace(b, symbol="ETHUSDT", open=b.open / 10, high=b.high / 10,
                       low=b.low / 10, close=b.close / 10) for b in btc]
        result = PaperSimulator().run(btc + eth)
        buy_symbols = {o.intent.symbol for o in result.state.orders if o.intent.side == Side.BUY}
        self.assertEqual(buy_symbols, {"BTCUSDT", "ETHUSDT"})
        self.assertEqual(result.state.account.initial_equity, D("10000"))
        for basket in result.state.baskets:
            self.assertLessEqual(basket.principal_spent, D("500"))
        self.assertFalse(any(e.reason == "stale_quote" for e in result.events))


if __name__ == "__main__":
    unittest.main()
