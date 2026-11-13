"""Closed native H1 entry causality and separate durable identity."""
from dataclasses import fields, replace
from datetime import timedelta
from decimal import Decimal
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from investalo_trading.futures_capital_research import CapitalCashPlan
from investalo_trading.futures_capital_signals import (
    CapitalH1SignalProfile, CapitalSignalProfile, assess_capital_signal,
    replay_capital_hour, start_capital_signals,
)
from investalo_trading.futures_capital_journal import CapitalReplayJournal, H1_VERSION
from test_futures_capital_signals import start, advance_hour, hour, buy

D = Decimal
PROTOCOL = "a" * 64
DATASETS = ("b" * 64,)


def h1_start():
    old = start()
    plan = CapitalCashPlan(**{f.name: getattr(old.profile.plan, f.name)
                             for f in fields(old.profile.plan) if f.init})
    profile = CapitalH1SignalProfile(plan, 1, D(0), "synthetic-costs")
    economic = replace(old.economic, ledger=replace(old.economic.ledger, plan=plan))
    return start_capital_signals(profile, economic, old.trade_prices)


def h1_ready():
    state = h1_start()
    for i in range(16):
        state = advance_hour(state, D(130) - 2 * i, all_assets=True)
    return state


class CapitalH1Tests(unittest.TestCase):
    def test_warmup_and_two_closed_values_required_without_h4_wait(self):
        state, legacy = h1_start(), start()
        for i in range(16):
            state = advance_hour(state, D(130) - 2 * i, all_assets=True)
            legacy = advance_hour(legacy, D(130) - 2 * i, all_assets=True)
            if i < 15:
                with self.assertRaisesRegex(ValueError, "no regular|confirmation"):
                    buy(state)
        self.assertEqual(state.signals[0].below_count, 2)
        self.assertIsNone(legacy.signals[0].entry_indicator.rsi)
        self.assertEqual(state.last_entry_at, state.last_hour.close_time)
        self.assertEqual(len(buy(state).economic.stages), 1)

    def test_unfinished_and_stale_hours_cannot_supply_a_signal(self):
        state = h1_ready()
        frame = hour(state, "96")
        with self.assertRaisesRegex(ValueError, "unfinished"):
            replay_capital_hour(state, frame, state.revision, frame.close_time - timedelta(seconds=1))
        with self.assertRaisesRegex(ValueError, "stale closed H1"):
            assess_capital_signal(state, "SYNTH0", D(98), state.as_of + timedelta(seconds=31))
        advanced = advance_hour(state, "96")
        self.assertEqual(advanced.last_entry_at.hour, 17)
        self.assertEqual(len(buy(advanced).economic.stages), 1)

    def test_actual_fill_rearm_and_five_percent_drop_still_required(self):
        state = buy(h1_ready())
        state = advance_hour(state, "92")
        with self.assertRaisesRegex(ValueError, "rearm"):
            buy(state)
        for price in (90, 88, 86, 84, 82, 80, 78, 76, 74, 72, 70, 68, 66, 64, 62, 60, 82):
            state = advance_hour(state, str(price))
        self.assertTrue(state.signals[0].rearmed)
        self.assertGreater(state.signals[0].entry_indicator.rsi, 30)
        self.assertFalse(state.signals[0].protected)
        for price in range(80, 58, -2):
            state = advance_hour(state, str(price))
            if state.signals[0].entry_indicator.rsi < 30:
                break
        self.assertLess(state.signals[0].entry_indicator.rsi, 30)
        with self.assertRaisesRegex(ValueError, "five-percent"):
            assess_capital_signal(state, "SYNTH0", D(96), state.as_of)
        filled = buy(state)
        self.assertEqual(len(filled.economic.stages), 2)
        self.assertFalse(filled.signals[0].rearmed)
        self.assertEqual(filled.economic.ledger.baskets[0].broker_leverage, D(2))

    def test_protection_blocks_further_h1_buys(self):
        state = buy(h1_ready())
        state = advance_hour(state, "106")
        self.assertTrue(state.signals[0].protected)
        with self.assertRaisesRegex(ValueError, "no regular"):
            assess_capital_signal(state, "SYNTH0", D(90), state.as_of)

    def test_profile_rejects_legacy_cash_or_changed_protection(self):
        old, new = start(), h1_start()
        with self.assertRaisesRegex(ValueError, "corrected cash"):
            CapitalH1SignalProfile(old.profile.plan, 1, D(0), "synthetic-costs")
        with self.assertRaisesRegex(ValueError, "H1 protection"):
            replace(new.profile, protection_hours=4)
        h4 = CapitalSignalProfile(new.profile.plan, 1, D(0), "synthetic-costs")
        self.assertNotEqual(h4.profile_digest, new.profile.profile_digest)
        self.assertNotIn("signal_policy", h4.__dataclass_fields__)

    def test_full_h1_journal_restore_and_foreign_h4_identity_rejected(self):
        initial = h1_start()
        with TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            with CapitalReplayJournal.create(
                    path, initial.profile, initial.trade_prices, initial.trade_prices,
                    initial.as_of, "synthetic-genesis",
                    protocol_digest=PROTOCOL, dataset_digests=DATASETS) as journal:
                for i in range(17):
                    frame = hour(journal.state, str(130 - 2 * i), all_assets=True)
                    journal.append("hour", expected_revision=journal.state.revision,
                                   at=frame.close_time, frame=frame)
                receipt, expected = journal.receipt, journal.state
                self.assertEqual(receipt["schema_version"], H1_VERSION)
            with CapitalReplayJournal.restore(
                    path, profile_digest=initial.profile.profile_digest, protocol_digest=PROTOCOL,
                    dataset_digests=DATASETS, minimum_receipt=receipt) as restored:
                self.assertEqual(restored.state, expected)
                self.assertEqual(restored.receipt, receipt)
                frame = hour(restored.state, "94", all_assets=True)
                continued = restored.append("hour", expected_revision=restored.state.revision,
                                            at=frame.close_time, frame=frame)
                self.assertEqual(continued, advance_hour(expected, "94", all_assets=True))
            h4 = CapitalSignalProfile(initial.profile.plan, 1, D(0), "synthetic-costs")
            with self.assertRaisesRegex(ValueError, "foreign"):
                CapitalReplayJournal.restore(path, profile_digest=h4.profile_digest,
                                             protocol_digest=PROTOCOL, dataset_digests=DATASETS)
            header = json.loads(path.read_text().splitlines()[0])
            self.assertEqual(header["profile"]["signal_policy"], initial.profile.signal_policy)


if __name__ == "__main__":
    unittest.main()
