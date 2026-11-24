"""Durable own basket journal with synthetic sender and actual files/processes."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
import json
import multiprocessing
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier
import unittest
from unittest.mock import patch
from uuid import UUID

from investalo_trading.futures_broker_entries import start_broker_entries
from investalo_trading.futures_broker_journal import (
    BrokerEntryJournal, BrokerSubmissionUnknown, VERSION,
)
from investalo_trading.futures_ledger import LedgerMark
from investalo_trading.futures_replay_journal import JournalCommitUnknown
from test_futures_broker_entries import receipt
from test_futures_capital_h1 import h1_start
from test_futures_capital_signals import hour
from test_futures_ledger import AT
from test_futures_paper_runtime import initial
from test_futures_paper_profit import (
    cycle, genesis as profit_genesis, grant, warmed as profit_warmed,
)

D = Decimal
ID = UUID("3d8d5375-0d20-4fbc-9668-2ffcb6bec198")
AUTH = "a" * 64
REQUEST = "b" * 64


def create(path, signal=None, **kwargs):
    signal = signal or h1_start()
    return BrokerEntryJournal.create(
        path, signal.profile, signal.trade_prices, signal.trade_prices, AT,
        "synthetic-initial-account", journal_id=ID, **kwargs)


def restore(path, minimum=None, signal=None, **kwargs):
    signal = signal or h1_start()
    return BrokerEntryJournal.restore(
        path, **{"journal_id": ID, "profile_digest": signal.profile.profile_digest,
                 "minimum_receipt": minimum, **kwargs})


def append(journal, kind, at=None, **kwargs):
    return journal.append(kind, expected_revision=journal.state.revision,
                          at=at or journal.state.as_of, **kwargs)


def feed(journal, price):
    frame = hour(journal.state.book.signal, D(price), all_assets=True)
    return append(journal, "hour", at=frame.close_time, frame=frame)


def ready(journal):
    for i in range(16):
        feed(journal, 130 - i * 2)
    return journal


def prepare(journal, symbol="SYNTH0", price="100", command=None):
    return append(journal, "prepare", symbol=symbol, planning_price=D(price),
                  command_id=command or f"entry-{journal.state.revision}")


def attempt(journal, at=None):
    return append(journal, "attempt", at=at, order_digest=journal.state.book.pending.order_digest,
                  authorization_digest=AUTH, request_digest=REQUEST)


def invoke(journal, sender, at=None):
    state = journal.state
    return journal.invoke_once(sender, expected_revision=state.revision, at=at or state.as_of,
                               order_digest=state.book.pending.order_digest,
                               authorization_digest=AUTH, request_digest=REQUEST)


def observe(journal, evidence=None, **kwargs):
    evidence = evidence or receipt(journal.state.book, at=journal.state.as_of, **kwargs)
    return append(journal, "observe", at=evidence.observed_at, observation=evidence)


def crash_sender(path, anchor, result_path):
    """Actual child exit after recorded attempt + one synthetic send."""
    with restore(path, anchor) as journal:
        def send(order, marker):
            with open(result_path, "x") as handle:
                handle.write(marker.request_digest)
                handle.flush()
                os.fsync(handle.fileno())
            os._exit(19)
        invoke(journal, send)


def reject_inherited_writer(journal, write_fd):
    try:
        # Each access must check PID before touching a fork-inherited RLock.
        for access in (lambda: journal.state, lambda: journal.receipt,
                       lambda: journal.checkpoint(),
                       lambda: invoke(journal, lambda *_: os._exit(23))):
            try:
                access()
                os._exit(24)
            except ValueError:
                pass
        os.write(write_fd, b"denied")
    finally:
        os.close(write_fd)
        journal.close()


class BrokerJournalTests(unittest.TestCase):
    def test_full_replay_of_warmup_order_attempt_fill_and_continuation(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "basket"
            with ready(create(path)) as journal:
                prepare(journal)
                before = journal.receipt
                attempt(journal)
                observe(journal, price="97.123", fee="-.007")
                expected, anchor = journal.checkpoint()
                self.assertEqual(anchor["schema_version"], VERSION)
                self.assertFalse(anchor["execution_enabled"])
            with restore(path, before) as journal:
                self.assertEqual(journal.checkpoint(), (expected, anchor))
                self.assertTrue(journal.acknowledges(before))
                self.assertEqual(journal.state.recovery_mode, "none")
                self.assertEqual(journal.state.book.signal.economic.stages[0].price, D("97.123"))
                self.assertEqual(journal.state.book.signal.economic.ledger.baskets[0].entry_fees, D(".007"))
                prepare(journal, symbol="SYNTH1")
                self.assertEqual(journal.state.book.pending.assessment.capital.stage, 1)

    def test_restart_before_attempt_preserves_exact_preparation_then_can_attempt_once(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "basket"
            with ready(create(path)) as journal:
                prepare(journal)
                order, anchor = journal.state.book.pending, journal.receipt
            with restore(path, anchor) as journal:
                self.assertEqual(journal.state.book.pending, order)
                self.assertEqual(journal.state.recovery_mode, "unsent_preparation")
                calls = []
                self.assertEqual(invoke(journal, lambda o, a: calls.append((o, a)) or "ack"), "ack")
                self.assertEqual(calls[0][0], order)
                self.assertEqual(journal.state.recovery_mode, "get_only")
                self.assertEqual(journal.state.book.signal.economic.stages, ())
                with self.assertRaisesRegex(ValueError, "resend"):
                    invoke(journal, lambda *_: calls.append("duplicate"))
                self.assertEqual(len(calls), 1)

    def test_sender_sees_already_durable_attempt_and_ack_is_not_a_fill(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "basket"
            with ready(create(path)) as journal:
                prepare(journal)
                def sender(order, marker):
                    raw = json.loads(path.read_bytes().splitlines()[-1])
                    self.assertEqual(raw["command"]["kind"], "attempt")
                    self.assertEqual(journal.state.current_attempt, marker)
                    self.assertEqual(marker.order_digest, order.order_digest)
                    self.assertEqual(marker.authorization_digest, AUTH)
                    self.assertEqual(marker.request_digest, REQUEST)
                    return {"synthetic_ack": True}
                invoke(journal, sender)
                self.assertEqual(journal.state.book.signal.economic.stages, ())
                self.assertIsNotNone(journal.state.book.pending)

    def test_restart_after_uncertain_send_allows_get_observation_but_no_resend(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "basket"
            with ready(create(path)) as journal:
                prepare(journal)
                calls = []
                def sender(*_):
                    calls.append("POST")
                    raise OSError("synthetic missing ACK")
                with self.assertRaises(BrokerSubmissionUnknown):
                    invoke(journal, sender)
                anchor = journal.receipt
            with restore(path, anchor) as journal:
                self.assertEqual(journal.state.recovery_mode, "get_only")
                with self.assertRaisesRegex(ValueError, "resend"):
                    invoke(journal, sender)
                self.assertEqual(calls, ["POST"])
                observe(journal)
                self.assertIsNone(journal.state.book.pending)
                self.assertEqual(len(journal.state.book.signal.economic.stages), 1)
                self.assertEqual(len(journal.state.attempts), 1)

    def test_partial_unknown_fee_and_terminal_reconciliation_survive_multiple_restarts(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "basket"
            with ready(create(path)) as journal:
                prepare(journal)
                attempt(journal)
                observe(journal, state="partially_filled", quantity="1", price="97", fee=None)
                partial, anchor = journal.checkpoint()
            with restore(path, anchor) as journal:
                self.assertEqual(journal.state, partial)
                observe(journal, replace(receipt(journal.state.book, state="canceled", quantity="1",
                                                price="97"), signed_fee=None))
                unknown, anchor = journal.checkpoint()
            with restore(path, anchor) as journal:
                self.assertEqual(journal.state, unknown)
                observe(journal, state="canceled", quantity="1", price="97", fee="-.01")
                complete, anchor = journal.checkpoint()
            with restore(path, anchor) as journal:
                self.assertEqual(journal.state, complete)
                self.assertEqual(len(journal.state.book.signal.economic.stages), 1)
                self.assertEqual(journal.state.book.signal.economic.stages[0].quantity, 1)
                self.assertEqual(journal.state.book.signal.economic.ledger.baskets[0].entry_fees, D(".01"))

    def test_expired_unsent_preparation_can_be_discarded_but_command_stays_consumed(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "basket"
            with ready(create(path)) as journal:
                prepare(journal, command="original")
                anchor, order = journal.receipt, journal.state.book.pending
            with restore(path, anchor) as journal:
                with self.assertRaisesRegex(ValueError, "fresh"):
                    attempt(journal, journal.state.as_of + timedelta(seconds=31))
                append(journal, "cancel_preparation", at=journal.state.as_of + timedelta(seconds=31),
                       order_digest=order.order_digest)
                self.assertEqual(journal.state.book.signal.economic.stages, ())
                feed(journal, "98")
                with self.assertRaisesRegex(ValueError, "reused"):
                    prepare(journal, price="98", command="original")
                prepare(journal, price="98", command="new")
                self.assertEqual(journal.state.book.pending.assessment.capital.stage, 1)

    def test_attempted_order_cannot_be_discarded_or_observed_before_attempt(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "basket"
            with ready(create(path)) as journal:
                prepare(journal)
                with self.assertRaisesRegex(ValueError, "recorded"):
                    observe(journal)
                attempt(journal, at=journal.state.as_of + timedelta(seconds=1))
                with self.assertRaisesRegex(ValueError, "GET-only"):
                    append(journal, "cancel_preparation", order_digest=journal.state.book.pending.order_digest)
                with self.assertRaisesRegex(ValueError, "predates"):
                    append(journal, "observe", observation=receipt(journal.state.book))
                with self.assertRaises(ValueError):
                    prepare(journal, symbol="SYNTH1")

    def test_original_signal_clock_is_not_renewed_by_prepare_or_current_marks(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "basket"
            with ready(create(path)) as journal:
                close = journal.state.as_of
                append(journal, "prepare", at=close + timedelta(seconds=20), symbol="SYNTH0",
                       planning_price=D(100), command_id="late")
                marks = tuple(LedgerMark(s, D(100)) for s in journal.state.book.signal.profile.plan.symbols)
                append(journal, "prices", at=close + timedelta(seconds=31),
                       trade=marks, marks=marks, event_id="fresh-marks")
                with self.assertRaisesRegex(ValueError, "stale closed"):
                    attempt(journal)
                self.assertEqual(journal.state.attempts, ())

    def test_fsync_failure_poisoned_writer_never_sends_and_restore_retains_attempt(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "basket"
            journal = ready(create(path))
            prepare(journal)
            anchor = journal.receipt
            calls = []
            with patch("investalo_trading.futures_capital_journal.os.fsync", side_effect=OSError), \
                    self.assertRaises(JournalCommitUnknown):
                invoke(journal, lambda *_: calls.append("POST"))
            self.assertEqual(calls, [])
            for access in (lambda: journal.state, lambda: journal.receipt,
                           lambda: journal.checkpoint(), lambda: journal.acknowledges(anchor)):
                with self.assertRaises(JournalCommitUnknown):
                    access()
            journal.close()
            with restore(path, anchor) as journal:
                self.assertEqual(journal.state.recovery_mode, "get_only")
                with self.assertRaises(ValueError):
                    invoke(journal, lambda *_: calls.append("POST"))
                self.assertEqual(calls, [])

    def test_child_exit_after_once_send_restores_get_only(self):
        with TemporaryDirectory() as directory:
            path, sent = Path(directory) / "basket", Path(directory) / "synthetic-send"
            with ready(create(path)) as journal:
                prepare(journal)
                anchor = journal.receipt
            process = multiprocessing.get_context("fork").Process(
                target=crash_sender, args=(path, anchor, sent))
            process.start()
            process.join(10)
            self.assertFalse(process.is_alive())
            self.assertEqual(process.exitcode, 19)
            self.assertEqual(sent.read_text(), REQUEST)
            with restore(path, anchor) as journal:
                self.assertEqual(len(journal.state.attempts), 1)
                with self.assertRaises(ValueError):
                    invoke(journal, lambda *_: self.fail("resend"))
                observe(journal)
                self.assertEqual(len(journal.state.book.signal.economic.stages), 1)

    def test_concurrent_attempts_have_one_sender_and_one_marker(self):
        with TemporaryDirectory() as directory:
            with ready(create(Path(directory) / "basket")) as journal:
                prepare(journal)
                revision, order = journal.state.revision, journal.state.book.pending
                barrier, calls = Barrier(2), []
                def contender(_):
                    barrier.wait(timeout=5)
                    try:
                        journal.invoke_once(lambda *_: calls.append("POST"), expected_revision=revision,
                                            at=journal.state.as_of, order_digest=order.order_digest,
                                            authorization_digest=AUTH, request_digest=REQUEST)
                        return "sent"
                    except ValueError:
                        return "denied"
                with ThreadPoolExecutor(max_workers=2) as workers:
                    outcomes = list(workers.map(contender, range(2)))
                self.assertEqual(sorted(outcomes), ["denied", "sent"])
                self.assertEqual(calls, ["POST"])
                self.assertEqual(len(journal.state.attempts), 1)

    def test_duplicate_observation_after_restore_cannot_change_balance_or_revision(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "basket"
            with ready(create(path)) as journal:
                prepare(journal)
                attempt(journal)
                evidence = receipt(journal.state.book, state="partially_filled", quantity="1")
                observe(journal, evidence)
                anchor = journal.receipt
            with restore(path, anchor) as journal:
                with self.assertRaisesRegex(ValueError, "duplicate"):
                    observe(journal, evidence)
                self.assertEqual(journal.receipt, anchor)

    def test_unknown_new_tail_is_replayed_but_acknowledged_tail_cannot_be_lost(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "basket"
            with ready(create(path)) as journal:
                prepare(journal)
                original, raw = journal.receipt, path.read_bytes()
                attempt(journal)
                after = journal.receipt
            with restore(path, original) as journal:
                self.assertEqual(journal.receipt, after)
            path.write_bytes(raw)
            with self.assertRaisesRegex(ValueError, "truncated"):
                restore(path, after)
            self.assertEqual(path.read_bytes(), raw)

    def test_journal_context_schema_and_chain_corruption_are_rejected_without_repair(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "original"
            with ready(create(source)) as journal:
                prepare(journal)
                attempt(journal)
                anchor = journal.receipt
            raw = source.read_bytes()
            changed = [raw[:-1], raw[:-20], raw + b'{"x":1,"x":2}\n',
                       raw.replace(b'"execution_enabled":false', b'"execution_enabled":true'),
                       raw.replace(b'"environment":"bitget_demo"', b'"environment":"live"'),
                       raw.replace(VERSION.encode(), b"foreign-paper"),
                       raw.replace(REQUEST.encode(), ("c" * 64).encode())]
            for index, data in enumerate(changed):
                path = Path(directory) / str(index)
                path.write_bytes(data)
                path.chmod(0o600)
                with self.subTest(index=index), self.assertRaises(ValueError):
                    restore(path, anchor)
                self.assertEqual(path.read_bytes(), data)
            with self.assertRaisesRegex(ValueError, "foreign"):
                restore(source, anchor, journal_id=UUID("9" * 32))
            with self.assertRaisesRegex(ValueError, "foreign"):
                restore(source, anchor, profile_digest="d" * 64)
            with self.assertRaisesRegex(ValueError, "prefix"):
                restore(source, {**anchor, "head": "e" * 64})

    def test_file_is_create_only_owned_private_exclusive_and_capacity_never_evicts(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "basket"
            with create(path, command_capacity=1) as journal:
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                with self.assertRaises(FileExistsError):
                    create(path)
                with self.assertRaises(BlockingIOError):
                    restore(path)
                feed(journal, "130")
                raw = path.read_bytes()
                with self.assertRaisesRegex(ValueError, "capacity"):
                    feed(journal, "128")
                self.assertEqual(path.read_bytes(), raw)
                anchor = journal.receipt
            path.chmod(0o644)
            with self.assertRaises(ValueError):
                restore(path, anchor)
            path.chmod(0o600)
            link = Path(directory) / "symlink"
            link.symlink_to(path)
            with self.assertRaises(OSError):
                restore(link, anchor)
            hard = Path(directory) / "hardlink"
            os.link(path, hard)
            with self.assertRaises(ValueError):
                restore(path, anchor)

    def test_partial_write_is_terminal_and_never_sends_or_repairs(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "basket"
            journal = ready(create(path))
            prepare(journal)
            anchor, original = journal.receipt, journal._handle
            class ShortWriter:
                def __getattr__(self, key):
                    return getattr(original, key)
                def write(self, value):
                    return original.write(value[:len(value) // 2])
            journal._handle = ShortWriter()
            with self.assertRaises(JournalCommitUnknown):
                invoke(journal, lambda *_: self.fail("sender must not run"))
            journal.close()
            damaged = path.read_bytes()
            with self.assertRaises(ValueError):
                restore(path, anchor)
            self.assertEqual(path.read_bytes(), damaged)

    def test_candidate_grid_and_original_profit_allocation_roundtrip(self):
        for signal in (initial(candidates=7, slots=3, limit=7).signal,
                       profit_genesis(candidates=7, limit=7).signal):
            with self.subTest(policy=signal.profile.plan.capital_policy), TemporaryDirectory() as directory:
                path = Path(directory) / "basket"
                with ready(create(path, signal)) as journal:
                    prepare(journal)
                    attempt(journal)
                    observe(journal)
                    expected, anchor = journal.checkpoint()
                with restore(path, anchor, signal) as journal:
                    self.assertEqual(journal.checkpoint(), (expected, anchor))
                    self.assertEqual(journal.state.book.signal.profile.plan.funded_slots, 3)

    def test_prepared_order_cannot_accept_wrong_attempt_bindings_or_synthetic_paper_commands(self):
        with TemporaryDirectory() as directory:
            with ready(create(Path(directory) / "basket")) as journal:
                prepare(journal)
                with self.assertRaises(ValueError):
                    append(journal, "attempt", order_digest="f" * 64,
                           authorization_digest=AUTH, request_digest=REQUEST)
                with self.assertRaises(ValueError):
                    append(journal, "attempt", order_digest=journal.state.book.pending.order_digest,
                           authorization_digest="read-consent", request_digest=REQUEST)
                with self.assertRaises(ValueError):
                    append(journal, "entry", price=D(98))
                with self.assertRaises(ValueError):
                    append(journal, "attempt", order_digest=journal.state.book.pending.order_digest,
                           authorization_digest=AUTH, request_digest=REQUEST, extra=True)
                self.assertEqual(journal.state.attempts, ())

    def test_live_file_replacement_edit_truncation_or_permission_change_stops_sender(self):
        with TemporaryDirectory() as directory:
            for index, change in enumerate(("replace", "edit", "truncate", "mode")):
                path = Path(directory) / str(index)
                journal = ready(create(path))
                prepare(journal)
                raw = path.read_bytes()
                if change == "replace":
                    path.rename(Path(directory) / f"old-{index}")
                    path.write_bytes(raw)
                    path.chmod(0o600)
                elif change == "edit":
                    path.write_bytes(raw.replace(b"synthetic-initial-account", b"synthetic-edited--account"))
                elif change == "truncate":
                    path.write_bytes(raw[:-1])
                else:
                    path.chmod(0o644)
                damaged = path.read_bytes()
                with self.subTest(change=change), self.assertRaises(JournalCommitUnknown):
                    invoke(journal, lambda *_: self.fail("changed file must not send"))
                journal.close()
                self.assertEqual(path.read_bytes(), damaged)

    def test_inherited_writer_is_rejected_by_actual_child_and_parent_remains_usable(self):
        with TemporaryDirectory() as directory:
            with ready(create(Path(directory) / "basket")) as journal:
                prepare(journal)
                read_fd, write_fd = os.pipe()
                process = multiprocessing.get_context("fork").Process(
                    target=reject_inherited_writer, args=(journal, write_fd))
                process.start()
                os.close(write_fd)
                process.join(10)
                self.assertFalse(process.is_alive())
                self.assertEqual(process.exitcode, 0)
                self.assertEqual(os.read(read_fd, 64), b"denied")
                os.close(read_fd)
                self.assertEqual(journal.state.attempts, ())
                invoke(journal, lambda *_: "synthetic-ack")
                self.assertEqual(len(journal.state.attempts), 1)

    def test_advanced_paper_profit_profile_cannot_seed_a_fresh_actual_journal(self):
        model = grant(cycle(profit_warmed()))
        self.assertGreater(len(model.signal.profile.plan.epochs), 0)
        with TemporaryDirectory() as directory:
            path = Path(directory) / "basket"
            with self.assertRaisesRegex(ValueError, "simulated"):
                create(path, model.signal)
            self.assertFalse(path.exists())

    def test_stale_prepare_is_not_renewed_on_restore_and_invalid_header_writes_nothing(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "basket"
            with ready(create(path)) as journal:
                prepare(journal)
                anchor = journal.receipt
            with restore(path, anchor) as journal:
                with self.assertRaisesRegex(ValueError, "fresh"):
                    attempt(journal, at=journal.state.as_of + timedelta(seconds=31))
                self.assertEqual(journal.receipt, anchor)
            invalid = Path(directory) / "invalid"
            with self.assertRaises(ValueError):
                create(invalid, command_capacity=True)
            self.assertFalse(invalid.exists())


if __name__ == "__main__":
    unittest.main()
