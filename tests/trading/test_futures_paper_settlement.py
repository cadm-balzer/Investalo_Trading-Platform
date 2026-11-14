"""Delayed native funding: exact marks, no invented fills, durable full replay."""
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from investalo_trading.futures_ledger import LedgerMark
from investalo_trading.futures_paper import PaperFunding, run_paper_batch
from investalo_trading.futures_paper_journal import FuturesPaperJournal
from investalo_trading.futures_paper_settlement import PaperSettlement, settle_paper_funding
from investalo_trading.futures_replay_journal import JournalCommitUnknown
from test_futures_capital_signals import hour
from test_futures_paper_runtime import initial, frames, journal, packet, step, warmed

D = Decimal


def settlement(state, *, price="100", rates=(".0001", "-.0002", "0"), at=None, input_id=None):
    frame = hour(state.signal, price, all_assets=True)
    at = at or frame.close_time
    symbols = state.config.profile.plan.symbols
    return PaperSettlement(
        input_id or f"settlement-{state.revision}", at,
        tuple(LedgerMark(symbol, D(price)) for symbol in symbols), "c" * 64,
        tuple(PaperFunding(symbol, f"native-{symbol}-{at.isoformat()}", at, D(rate))
              for symbol, rate in zip(symbols, rates)), (frame,))


def apply(state, value=None, lag=5):
    value = value or settlement(state)
    return settle_paper_funding(state, value, state.revision,
                                value.settled_at + timedelta(seconds=lag))


class FuturesPaperSettlementTests(unittest.TestCase):
    def test_original_paper_journal_identity_remains_byte_identical(self):
        # Captured from merged PR60 reducers, before adding the settlement command.
        genesis = initial()
        with TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.jsonl"
            with journal(path, genesis) as saved:
                saved.append("warmup", hours=frames(genesis, range(130, 98, -2)),
                             expected_revision=0, at=genesis.config.trading_from)
                quote = packet(saved.state)
                saved.append("batch", batch=quote, expected_revision=1, at=quote.quoted_at)
                self.assertEqual(saved.receipt["context_digest"],
                                 "4abc6965402c7d16eb47f3131d0d9691d9630e0f7d3a7be1580a9d822403cd04")
                self.assertEqual(saved.receipt["head"],
                                 "dd1141cee4e3b93478f17a7fd39b2e6c5107568c48e637622520d8056715a29d")
                self.assertEqual(saved.state.state_digest,
                                 "0a387a15917d1eb7983f86b4d00456a4f59d70c88775ec0aa37bb42383f073f4")

    def test_signed_native_payments_use_exact_marks_and_keep_ladders_cash_and_quote_clock(self):
        before = step(warmed())
        value = settlement(before, price="103")
        after = apply(before, value)
        self.assertEqual(after.observed_at, value.settled_at + timedelta(seconds=5))
        self.assertEqual(after.signal.as_of, value.settled_at)
        self.assertEqual(after.signal.trade_at, before.signal.trade_at)
        self.assertEqual(after.signal.trade_prices, before.signal.trade_prices)
        self.assertEqual(after.signal.economic.stages, before.signal.economic.stages)
        self.assertEqual(after.signal.economic.decisions, before.signal.economic.decisions)
        self.assertEqual(after.config, before.config)
        self.assertEqual(after.signal.economic.ledger.unposted_cash, before.signal.economic.ledger.unposted_cash)
        self.assertEqual(after.signal.economic.ledger.closed_baskets, 0)
        self.assertEqual(after.attempts, ())
        for index, (old, new) in enumerate(zip(before.signal.economic.ledger.baskets,
                                             after.signal.economic.ledger.baskets)):
            expected = -old.quantity * D(103) * value.funding[index].rate if index < 3 else D(0)
            self.assertEqual(new.quantity, old.quantity)
            self.assertEqual(new.isolated_balance - old.isolated_balance, expected)
            self.assertEqual(new.funding_net - old.funding_net, expected)
            self.assertEqual(new.mark, D(103))
        self.assertEqual(len(after.funding_ids), 3)
        self.assertFalse(after.execution_enabled)

    def test_resume_needs_real_fresh_quotes_and_restores_only_own_cost_cash(self):
        before = step(warmed())
        value = settlement(before, rates=(".0001",) * 3)
        after = apply(before, value)
        later = after.observed_at + timedelta(seconds=1)
        resumed = step(after, at=later)
        self.assertEqual(resumed.signal.trade_at, later)
        self.assertEqual(resumed.signal.economic.stages, before.signal.economic.stages)
        self.assertGreater(resumed.signal.economic.ledger.baskets[0].cost_restored,
                           before.signal.economic.ledger.baskets[0].cost_restored)
        self.assertFalse(resumed.signal.economic.ledger.halted)
        self.assertEqual(resumed.config.profile.plan.budgets, before.config.profile.plan.budgets)
        with self.assertRaises(ValueError):
            run_paper_batch(after, packet(after, at=value.settled_at), after.revision, after.observed_at)

    def test_midnight_day_basis_precedes_funding_using_exact_boundary_marks(self):
        state = step(warmed())
        for _ in range(7):
            frame = hour(state.signal, "100", all_assets=True)
            state = step(state, hours=(frame,), at=frame.close_time + timedelta(seconds=1))
        value = settlement(state, price="101", rates=(".001",) * 3)
        after = apply(state, value)
        ledger = after.signal.economic.ledger
        self.assertEqual(value.settled_at.hour, 0)
        self.assertEqual(ledger.day_started_at, value.settled_at)
        paid = sum(-old.quantity * D(101) * D(".001") for old in state.signal.economic.ledger.baskets)
        self.assertEqual(ledger.equity - ledger.day_start_equity, paid)
        self.assertEqual(ledger.phase, 2)

    def test_same_hour_settlement_does_not_advance_indicators_or_quote_clock(self):
        state = step(warmed())
        value = settlement(state, at=state.signal.as_of + timedelta(seconds=2))
        value = replace(value, hours=())
        after = apply(state, value)
        self.assertEqual(after.signal.last_hour, state.signal.last_hour)
        self.assertEqual(after.signal.last_entry_at, state.signal.last_entry_at)
        self.assertEqual(after.signal.trade_at, state.signal.trade_at)
        self.assertEqual(after.signal.signals[0].entry_indicator, state.signal.signals[0].entry_indicator)

    def test_liquidation_cannot_be_erased_by_recovered_quotes_or_another_settlement(self):
        state = step(warmed())
        value = settlement(state, price="51", rates=(".1",) * 3)
        after = apply(state, value)
        self.assertTrue(after.signal.economic.liquidation_required)
        self.assertTrue(all("liquidation_settlement_required" in s.exit_reasons
                            for s in after.signal.signals[:3]))
        self.assertEqual(after.signal.economic.ledger.closed_baskets, 0)
        self.assertEqual(len(after.signal.economic.stages), 3)
        with self.assertRaisesRegex(ValueError, "reconciliation"):
            step(after, price="100", at=after.observed_at + timedelta(seconds=1))
        with self.assertRaisesRegex(ValueError, "reconciliation"):
            apply(after)

    def test_missing_future_old_gapped_or_foreign_evidence_is_atomic(self):
        state = step(warmed())
        value = settlement(state)
        wrong = (
            replace(value, hours=()),
            replace(value, marks=tuple(reversed(value.marks))),
            replace(value, marks=value.marks[:-1]),
            replace(value, funding=(replace(value.funding[0], symbol="foreign"),)),
            replace(value, hours=(hour(state.signal, "100", all_assets=True,
                                      close=value.settled_at + timedelta(hours=1)),)),
        )
        for bad in wrong:
            with self.subTest(value=bad.input_id), self.assertRaises(ValueError):
                apply(state, bad)
        for at in (value.settled_at - timedelta(seconds=1),
                   value.settled_at + timedelta(hours=1, seconds=1)):
            with self.subTest(at=at), self.assertRaises(ValueError):
                settle_paper_funding(state, value, state.revision, at)
        with self.assertRaises(ValueError):
            settle_paper_funding(state, value, True, value.settled_at)
        with self.assertRaises(ValueError):
            settle_paper_funding(initial(), value, 0, value.settled_at)
        self.assertEqual(state.revision, 2)
        self.assertFalse(state.funding_ids)

    def test_duplicate_native_ids_reject_even_with_new_packet_and_later_time(self):
        state = step(warmed())
        value = settlement(state)
        after = apply(state, value)
        next_value = settlement(after)
        next_value = replace(next_value, funding=tuple(
            replace(new, native_id=old.native_id)
            for old, new in zip(value.funding, next_value.funding)))
        with self.assertRaises(ValueError):
            apply(after, next_value)
        with self.assertRaises(ValueError):
            apply(after, value)
        self.assertEqual(len(after.funding_ids), 3)

    def test_constructor_rejects_mixed_times_and_opaque_or_unbounded_evidence(self):
        value = settlement(step(warmed()))
        invalid = (
            {"funding": ()}, {"funding": value.funding[::-1]},
            {"funding": (replace(value.funding[0], settled_at=value.settled_at + timedelta(seconds=1)),)},
            {"funding": (value.funding[0],) * 2}, {"funding": list(value.funding)},
            {"marks": list(value.marks)}, {"valuation_digest": "unknown"},
            {"valuation_digest": "Z" * 64}, {"hours": value.hours * 2},
        )
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(value, **changes)

    def test_full_journal_restart_after_settlement_and_fresh_continuation(self):
        genesis = initial()
        with TemporaryDirectory() as directory:
            path = Path(directory) / "paper.jsonl"
            with journal(path, genesis) as saved:
                saved.append("warmup", hours=frames(genesis, range(130, 98, -2)),
                             expected_revision=0, at=genesis.config.trading_from)
                value = packet(saved.state)
                saved.append("batch", batch=value, expected_revision=1, at=value.quoted_at)
                value = settlement(saved.state)
                expected = saved.append("settlement", settlement=value, expected_revision=2,
                                        at=value.settled_at + timedelta(seconds=5))
                receipt, raw = saved.receipt, path.read_bytes()
                bad = replace(value, input_id="other-packet")
                with self.assertRaises(ValueError):
                    saved.append("settlement", settlement=bad, expected_revision=3,
                                 at=expected.observed_at)
                self.assertEqual(path.read_bytes(), raw)
                self.assertEqual(saved.receipt, receipt)
            with FuturesPaperJournal.restore(path, config_digest=genesis.config.config_digest,
                                              minimum_receipt=receipt) as saved:
                self.assertEqual(saved.state, expected)
                self.assertEqual(saved.receipt, receipt)
                value = packet(saved.state, at=expected.observed_at + timedelta(seconds=1))
                actual = saved.append("batch", batch=value, expected_revision=3, at=value.quoted_at)
                self.assertEqual(actual, run_paper_batch(expected, value, 3, value.quoted_at))

    def test_unknown_fsync_ack_stops_writer_and_full_readback_books_funding_once(self):
        genesis = initial()
        with TemporaryDirectory() as directory:
            path = Path(directory) / "paper.jsonl"
            with journal(path, genesis) as saved:
                saved.append("warmup", hours=frames(genesis, range(130, 98, -2)),
                             expected_revision=0, at=genesis.config.trading_from)
                quote = packet(saved.state)
                saved.append("batch", batch=quote, expected_revision=1, at=quote.quoted_at)
                before, receipt = saved.state, saved.receipt
                value = settlement(before)
                with patch("investalo_trading.futures_capital_journal.os.fsync", side_effect=OSError):
                    with self.assertRaises(JournalCommitUnknown):
                        saved.append("settlement", settlement=value, expected_revision=2,
                                     at=value.settled_at + timedelta(seconds=5))
                with self.assertRaises(JournalCommitUnknown):
                    _ = saved.state
            with FuturesPaperJournal.restore(path, config_digest=genesis.config.config_digest,
                                              minimum_receipt=receipt) as saved:
                self.assertEqual(saved.state, apply(before, value))
                self.assertEqual(len(saved.state.funding_ids), 3)

    def test_worker_settlement_guard_and_durable_ack_have_no_trading_fills(self):
        from investalo_workers.futures_paper_worker import FuturesPaperWorker
        class Feed:
            def settlement(self, state):
                return settlement(state)
        genesis = initial()
        with TemporaryDirectory() as directory:
            path = Path(directory) / "paper.jsonl"
            with journal(path, genesis) as saved:
                saved.append("warmup", hours=frames(genesis, range(130, 98, -2)),
                             expected_revision=0, at=genesis.config.trading_from)
                quote = packet(saved.state)
                saved.append("batch", batch=quote, expected_revision=1, at=quote.quoted_at)
                value = settlement(saved.state)
                worker = FuturesPaperWorker(saved, Feed(), lambda: value.settled_at + timedelta(seconds=5))
                guard_calls = []
                def guard():
                    guard_calls.append(True)
                    if len(guard_calls) == 2:
                        raise RuntimeError("source archive not acknowledged")
                receipt = saved.receipt
                with self.assertRaisesRegex(RuntimeError, "archive"):
                    worker.settle_once(guard=guard)
                self.assertEqual(saved.receipt, receipt)
                cycle = worker.settle_once()
                self.assertEqual((cycle.entries, cycle.closures), (0, 0))
                self.assertEqual(cycle.state_digest, saved.state.state_digest)
                self.assertFalse(cycle.execution_enabled)
