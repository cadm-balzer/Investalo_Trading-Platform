"""Exact-hour simultaneous funding, causal indicators and full journal restore."""
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from investalo_trading.futures_capital_signals import (
    CapitalFundingBatch, record_signal_funding_batch, replay_capital_hour, replay_valued_capital_hour,
)
from investalo_trading.futures_ledger import FundingSettlement, LedgerMark, MarkBatch
from test_futures_capital_journal import append, create, feed, ready, restore, buy, economic
from test_futures_capital_signals import hour, start

D = Decimal


class CapitalFundingBoundaryTests(unittest.TestCase):
    def test_exact_midnight_marks_precede_day_basis_and_funding_without_time_shift(self):
        with TemporaryDirectory() as directory:
            with create(Path(directory) / "journal") as journal:
                ready(journal)
                buy(journal)
                for _ in range(7):
                    feed(journal, "100")
                frame = hour(journal.state, "100", all_assets=True)
                self.assertEqual(frame.close_time.hour, 0)
                marks = tuple(LedgerMark(s, D(101)) for s in journal.state.profile.plan.symbols)
                append(journal, "valued_hour", at=frame.close_time,
                       frame=frame, marks=marks, evidence_digest="native-same-time-reference")
                before = journal.state
                batch = CapitalFundingBatch(tuple(FundingSettlement(s, D(101), D(".001"))
                                                   for s in before.profile.plan.symbols), "native-batch")
                after = append(journal, "funding_batch", batch=batch, event_id="native-hour-batch")
                self.assertEqual(after.as_of, frame.close_time)
                self.assertEqual(after.economic.ledger.day_start_equity, before.economic.ledger.equity)
                self.assertLess(after.economic.ledger.equity, after.economic.ledger.day_start_equity)
                self.assertEqual(after.economic.revision - before.economic.revision, 3)
                self.assertEqual(after.revision - before.revision, 1)
                self.assertEqual(after.trade_prices, before.trade_prices)
                self.assertTrue(all(b.last_funding_at == frame.close_time
                                    for b in after.economic.ledger.baskets))

    def test_valuation_does_not_change_native_candles_or_indicator_inputs(self):
        state = start()
        frame = hour(state, "99", all_assets=True)
        plain = replay_capital_hour(state, frame, state.revision, frame.close_time)
        marks = tuple(LedgerMark(s, D(103)) for s in state.profile.plan.symbols)
        valued = replay_valued_capital_hour(state, frame, marks, "native-funding-reference",
                                          state.revision, frame.close_time)
        self.assertEqual(plain.signals, valued.signals)
        self.assertEqual(plain.h4_buffer, valued.h4_buffer)
        self.assertEqual(plain.last_hour, valued.last_hour)
        self.assertEqual(plain.trade_prices, valued.trade_prices)
        self.assertNotEqual(plain.economic.ledger.baskets, valued.economic.ledger.baskets)
        self.assertNotEqual(plain.state_digest, valued.state_digest)
        self.assertEqual(frame.mark[0].close, 99)

    def test_complete_valuation_evidence_and_closed_hour_required(self):
        state = start()
        frame = hour(state, "100", all_assets=True)
        marks = tuple(LedgerMark(s, D(101)) for s in state.profile.plan.symbols)
        for changed in (marks[:-1], marks[::-1]):
            with self.subTest(marks=changed), self.assertRaises(ValueError):
                replay_valued_capital_hour(state, frame, changed, "native", state.revision, frame.close_time)
        with self.assertRaises(ValueError):
            replay_valued_capital_hour(state, frame, marks, "", state.revision, frame.close_time)
        with self.assertRaises(ValueError):
            replay_valued_capital_hour(state, frame, marks, "native", state.revision, state.as_of)
        with self.assertRaises(ValueError):
            replay_capital_hour(state, frame, state.revision, frame.close_time, valuation_evidence="unbound")

    def test_batch_rejects_empty_duplicate_noncanonical_or_foreign_payloads(self):
        a = FundingSettlement("SYNTH0", D(100), D(".001"))
        b = FundingSettlement("SYNTH1", D(100), D(".001"))
        for values in ((), (a, a), (b, a), [a], (MarkBatch(tuple(
                LedgerMark(s, D(100)) for s in start().profile.plan.symbols)),)):
            with self.subTest(values=type(values).__name__), self.assertRaises(ValueError):
                CapitalFundingBatch(values, "evidence")

    def test_stale_or_mismatched_mark_cannot_settle_simultaneous_batch(self):
        state = start()
        batch = CapitalFundingBatch((FundingSettlement("SYNTH0", D(101), D(".001")),), "evidence")
        with self.assertRaisesRegex(ValueError, "valuation"):
            record_signal_funding_batch(state, batch, "batch", state.revision, state.as_of)
        batch = CapitalFundingBatch((FundingSettlement("SYNTH0", D(100), D(".001")),), "evidence")
        with self.assertRaisesRegex(ValueError, "valuation"):
            record_signal_funding_batch(state, batch, "batch", state.revision,
                                        state.as_of + timedelta(milliseconds=1))

    def test_second_settlement_failure_never_acknowledges_first_or_writes_partial_batch(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "journal"
            with create(path) as journal:
                economic(journal, FundingSettlement("SYNTH1", D(100), D(".001")))
                batch = CapitalFundingBatch(tuple(
                    FundingSettlement(s, D(100), D(".001")) for s in ("SYNTH0", "SYNTH1")), "evidence")
                before, raw = journal.receipt, path.read_bytes()
                with self.assertRaisesRegex(ValueError, "duplicate funding"):
                    append(journal, "funding_batch", batch=batch, event_id="failed-batch")
                self.assertEqual(journal.receipt, before)
                self.assertEqual(path.read_bytes(), raw)

    def test_native_milliseconds_all_ids_and_new_commands_survive_full_restore(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "journal"
            with create(path) as journal:
                frame = hour(journal.state, "100", all_assets=True)
                marks = tuple(LedgerMark(s, D(101)) for s in journal.state.profile.plan.symbols)
                append(journal, "valued_hour", at=frame.close_time,
                       frame=frame, marks=marks, evidence_digest="native-exact")
                batch = CapitalFundingBatch(tuple(
                    FundingSettlement(s, D(101), D(".001")) for s in journal.state.profile.plan.symbols),
                    "first-native-batch")
                append(journal, "funding_batch", batch=batch, event_id="first-group")
                at = journal.state.as_of + timedelta(milliseconds=18)
                economic(journal, MarkBatch(marks), at=at)
                batch = CapitalFundingBatch(tuple(
                    FundingSettlement(s, D(101), D("-.001")) for s in journal.state.profile.plan.symbols),
                    "later-native-batch")
                append(journal, "funding_batch", at=at, batch=batch, event_id="second-group")
                state, before = journal.state, journal.receipt
                self.assertEqual(len(state.economic.event_ids), 8)
            with restore(path, minimum_receipt=before) as journal:
                self.assertEqual(journal.state, state)
                self.assertEqual(journal.receipt, before)
                self.assertTrue(all(b.last_funding_at == at for b in journal.state.economic.ledger.baskets))
                self.assertFalse(journal.state.execution_enabled)

    def test_revised_duplicate_valued_hour_fails_and_normal_hour_remains_idempotent(self):
        state = start()
        frame = hour(state, "100", all_assets=True)
        marks = tuple(LedgerMark(s, D(101)) for s in state.profile.plan.symbols)
        state = replay_valued_capital_hour(state, frame, marks, "native", state.revision, frame.close_time)
        self.assertIs(replay_capital_hour(state, frame, state.revision, state.as_of), state)
        with self.assertRaisesRegex(ValueError, "revised valued hour"):
            replay_valued_capital_hour(state, frame, marks, "native", state.revision, state.as_of)


if __name__ == "__main__":
    unittest.main()
