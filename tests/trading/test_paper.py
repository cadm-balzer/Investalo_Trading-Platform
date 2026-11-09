from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest

from investalo_trading import (
    Candle, CryptoEngine, OrderStatus, PaperRunner, PaperSimulator, Quote,
    SimulationCosts, StrategyConfig, TradingRejected,
)

D = Decimal
START = datetime(2026, 1, 1, tzinfo=timezone.utc)


class PaperRunnerTests(unittest.TestCase):
    def setUp(self):
        self.runner = PaperRunner("tenant-a", "paper-a")
        self.initial = self.runner.start(START)

    def quote(self, at, price="100", symbol="BTCUSDT"):
        return Quote(symbol, at, D(price), D(price))

    def pending(self):
        checkpoint = self.initial
        for index in range(16):
            opened = START + timedelta(hours=4 * index)
            previous, price = D(100-index), D(99-index)
            bar = Candle("BTCUSDT", opened, opened + timedelta(hours=4),
                         previous, previous, price, price)
            checkpoint = self.runner.quote(
                checkpoint, self.quote(bar.close_time, str(price)), now=bar.close_time,
            ).checkpoint
            checkpoint = self.runner.bar(checkpoint, bar, now=bar.close_time).checkpoint
        self.assertTrue(any(order.unresolved for order in checkpoint.state.orders))
        self.assertEqual(checkpoint.state.basket("BTCUSDT").quantity, 0)
        return checkpoint

    def test_signals_wait_for_later_quote_and_restart_does_not_duplicate_fills(self):
        pending = self.pending()
        at = pending.observed_at + timedelta(seconds=1)
        quote = self.quote(at, "84")
        update = self.runner.quote(pending, quote, now=at)
        self.assertEqual(len(update.entry.fills), 1)
        self.assertEqual(len(update.checkpoint.state.processed_fills), 1)
        self.assertGreater(update.checkpoint.state.basket("BTCUSDT").quantity, 0)
        self.assertEqual(update.entry.revision, pending.revision + 1)
        # Actual disk roundtrip models committed checkpoint/restart, not a DB writer.
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoint.json"
            path.write_text(self.runner.dump(update.checkpoint))
            restarted = self.runner.restore(path.read_bytes())
        self.assertEqual(restarted, update.checkpoint)
        duplicate = self.runner.quote(restarted, quote, now=at + timedelta(seconds=1))
        self.assertEqual(duplicate.checkpoint, restarted)
        self.assertIsNone(duplicate.entry)

    def test_uncommitted_transition_can_be_recomputed_without_new_fill_identity(self):
        pending = self.pending()
        at = pending.observed_at + timedelta(seconds=1)
        quote = self.quote(at, "84")
        first = self.runner.quote(pending, quote, now=at)
        retry = self.runner.quote(self.runner.restore(self.runner.dump(pending)), quote, now=at)
        self.assertEqual(first, retry)
        self.assertEqual(pending.state.processed_fills, ())

    def test_other_asset_quote_cannot_fill_buy_at_old_quote(self):
        pending = self.pending()
        at = pending.observed_at + timedelta(seconds=1)
        update = self.runner.quote(pending, self.quote(at, "50", "ETHUSDT"), now=at)
        self.assertEqual(update.entry.fills, ())
        self.assertEqual(update.checkpoint.state.basket("BTCUSDT").quantity, 0)

    def test_identical_quote_at_signal_time_does_not_fill(self):
        pending = self.pending()
        quote = pending.state.quote("BTCUSDT")
        replay = self.runner.quote(pending, quote, now=quote.observed_at)
        self.assertIsNone(replay.entry)
        self.assertEqual(replay.checkpoint, pending)

    def test_dispatch_rechecks_account_halt(self):
        pending = self.pending()
        pending = replace(pending, state=replace(
            pending.state, account=replace(pending.state.account, halted=True),
        ))
        at = pending.observed_at + timedelta(seconds=1)
        update = self.runner.quote(pending, self.quote(at, "84"), now=at)
        self.assertEqual(update.entry.fills, ())
        self.assertEqual(update.checkpoint.state.basket("BTCUSDT").quantity, 0)

    def test_price_risk_exit_survives_restart_and_does_not_auto_resume(self):
        pending = self.pending()
        at = pending.observed_at + timedelta(seconds=1)
        entered = self.runner.quote(pending, self.quote(at, "84"), now=at).checkpoint
        at += timedelta(seconds=1)
        update = self.runner.quote(self.runner.restore(self.runner.dump(entered)),
                                   self.quote(at, "36"), now=at)
        self.assertEqual(len(update.entry.fills), 1)
        self.assertEqual(update.checkpoint.state.basket("BTCUSDT").quantity, 0)
        self.assertTrue(update.checkpoint.state.basket("BTCUSDT").risk_stopped)
        restored = self.runner.restore(self.runner.dump(update.checkpoint))
        self.assertTrue(restored.state.basket("BTCUSDT").risk_stopped)

    def test_unknown_order_is_never_retried_even_after_restore(self):
        pending = self.pending()
        intent = pending.state.orders[0].intent.intent_id
        pending = replace(pending, state=self.runner.simulator.engine.mark_order_unknown(
            pending.state, intent,
        ))
        restored = self.runner.restore(self.runner.dump(pending))
        at = restored.observed_at + timedelta(seconds=1)
        with self.assertRaises(TradingRejected):
            self.runner.quote(restored, self.quote(at, "84"), now=at)
        self.assertEqual(restored.state.orders[0].status, OrderStatus.UNKNOWN)

    def test_stale_future_revised_and_regressing_quotes_reject_without_changes(self):
        checkpoint = self.runner.quote(self.initial, self.quote(START), now=START).checkpoint
        for quote, now in [
            (self.quote(START + timedelta(seconds=1)), START + timedelta(seconds=40)),
            (self.quote(START + timedelta(seconds=2)), START + timedelta(seconds=1)),
            (self.quote(START, "99"), START),
            (self.quote(START - timedelta(seconds=1)), START - timedelta(seconds=1)),
        ]:
            with self.subTest(quote=quote, now=now), self.assertRaises(TradingRejected):
                self.runner.quote(checkpoint, quote, now=now)
        self.assertEqual(checkpoint.revision, 1)

    def test_gap_unfinished_and_revised_bars_reject_but_duplicate_is_noop(self):
        bar = Candle("BTCUSDT", START, START + timedelta(hours=4), D(100), D(100), D(100), D(100))
        with self.assertRaises(TradingRejected):
            self.runner.bar(self.initial, bar, now=START)
        first = self.runner.bar(self.initial, bar, now=bar.close_time).checkpoint
        restored = self.runner.restore(self.runner.dump(first))
        self.assertIsNone(self.runner.bar(restored, bar, now=bar.close_time).entry)
        revised = replace(bar, close=D(99), low=D(99))
        with self.assertRaises(TradingRejected):
            self.runner.bar(restored, revised, now=bar.close_time)
        gap = replace(bar, open_time=START + timedelta(hours=8),
                      close_time=START + timedelta(hours=12))
        with self.assertRaises(TradingRejected):
            self.runner.bar(restored, gap, now=gap.close_time)

    def test_late_bar_cannot_create_buy_from_stale_signal(self):
        pending = self.pending()
        # Fresh independent account, first15 bars, then late second sub30 bar.
        state = self.initial
        for index in range(16):
            opened = START + timedelta(hours=4*index)
            bar = Candle("BTCUSDT", opened, opened + timedelta(hours=4),
                         D(100-index), D(100-index), D(99-index), D(99-index))
            now = bar.close_time + (timedelta(seconds=31) if index == 15 else timedelta())
            state = self.runner.quote(state, self.quote(now, str(bar.close)), now=now).checkpoint
            state = self.runner.bar(state, bar, now=now).checkpoint
        self.assertEqual(state.state.orders, ())
        self.assertTrue(any(e.reason == "stale_signal" for e in state.last_entry.events))
        self.assertNotEqual(state, pending)

    def test_midnight_is_explicit_and_missing_baseline_blocks_new_exposure(self):
        midnight = START + timedelta(days=1)
        late = self.runner.quote(self.initial, self.quote(midnight + timedelta(seconds=1)),
                                 now=midnight + timedelta(seconds=1)).checkpoint
        self.assertEqual(late.state.account.trading_day, START.date())
        self.assertIn("daily_baseline_required", self.runner.simulator.engine.risk_reasons(
            late.state, midnight + timedelta(seconds=1),
        ))
        exact = self.runner.quote(self.initial, self.quote(midnight), now=midnight).checkpoint
        self.assertEqual(exact.state.account.trading_day, midnight.date())

    def test_restore_requires_same_tenant_account_configuration_and_costs(self):
        payload = self.runner.dump(self.initial)
        altered_config = StrategyConfig(daily_loss_fraction=D(".05"))
        different = [
            PaperRunner("tenant-b", "paper-a"),
            PaperRunner("tenant-a", "paper-b"),
            PaperRunner("tenant-a", "paper-a", PaperSimulator(CryptoEngine(altered_config))),
            PaperRunner("tenant-a", "paper-a", PaperSimulator(costs=SimulationCosts(spread_fraction=D(".002")))),
        ]
        for runner in different:
            with self.subTest(runner=runner), self.assertRaises(ValueError):
                runner.restore(payload)

    def test_snapshot_rejects_mode_schema_duplicates_extra_fields_and_revision(self):
        original = json.loads(self.runner.dump(self.initial))
        examples = []
        for key, value in [("mode", "live"), ("schema_version", "other"), ("extra", 1)]:
            document = dict(original)
            document[key] = value
            examples.append(json.dumps(document))
        for revision in [True, -1, 1]:
            document = json.loads(json.dumps(original))
            document["checkpoint"]["revision"] = revision
            examples.append(json.dumps(document))
        examples.append(self.runner.dump(self.initial).replace('"mode":"paper"', '"mode":"paper","mode":"paper"'))
        for payload in examples:
            with self.subTest(payload=payload[:50]), self.assertRaises(ValueError):
                self.runner.restore(payload)

    def test_manual_reserve_is_never_automatically_authorized(self):
        pending = self.pending()
        self.assertFalse(pending.state.basket("BTCUSDT").manual_used)
        self.assertTrue(all(order.intent.stage != 6 for order in pending.state.orders))


if __name__ == "__main__":
    unittest.main()
