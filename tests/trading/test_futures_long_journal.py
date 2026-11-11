"""Full retained evidence and replay/recovery failure cases; no market performance."""
from dataclasses import FrozenInstanceError, replace
from datetime import timedelta
from decimal import Decimal
import json
import math
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from investalo_trading.futures_ledger import EntryFill, ExitFill, FundingSettlement
from investalo_trading.futures_pending import (
    OrderResolution, assess_ledger_purchase, record_fill, record_ledger_event,
    start_long_pending_research, start_pending_research,
)
from investalo_trading.futures_replay_journal import FuturesReplayJournal, JournalCommitUnknown
from investalo_trading.futures_signals import (
    FIRST_FILL_MODEL, ReplayProfile, replay_frame, start_signal_replay,
)
from investalo_trading.identity_history import IdentityHistory
from investalo_trading.models import floor_step
from investalo_trading.snapshot import digest, primitive
from test_futures_ledger import AT, fixture
from test_futures_pending import request
from test_futures_signals import frame

D = Decimal
PROTOCOL = "a" * 64
DATA = ("b" * 64, "c" * 64)


def profile(ledger):
    return ReplayProfile(ledger.plan, tuple((s, D("2420")) for s in ledger.plan.symbols),
                         D(0), "synthetic-long-journal-only", FIRST_FILL_MODEL)


def create(path, **kwargs):
    ledger = fixture()
    return FuturesReplayJournal.create(path, profile(ledger), ledger,
                                      protocol_digest=PROTOCOL, dataset_digests=DATA, **kwargs)


def restore(path, **kwargs):
    return FuturesReplayJournal.restore(path, profile_digest=profile(fixture()).profile_digest,
                                       protocol_digest=PROTOCOL, dataset_digests=DATA, **kwargs)


def feed(journal, price):
    value = frame(journal.state, price)
    return journal.append("frame", expected_revision=journal.state.revision,
                          at=value.close_time, frame=value)


def entered(journal):
    for i in range(18):
        feed(journal, str(100 - 3 * i))
    state = journal.state
    symbol = state.profile.plan.symbols[0]
    journal.append("reserve", expected_revision=state.revision, at=state.as_of,
                   symbol=symbol, intent_id="long-intent")
    journal.append("attempt", expected_revision=journal.state.revision, at=journal.state.as_of,
                   intent_id="long-intent", order_id="long-order")
    p = journal.state.economic.pending
    quantity = floor_step(p.request.quantity / 2, state.profile.plan.contracts[0].quantity_step)
    payload = EntryFill(symbol, quantity, p.request.maximum_fill_price,
                        p.request.posted_margin, quantity * p.request.maximum_fill_price * D(".001"), D(2))
    journal.append("fill", expected_revision=journal.state.revision, at=journal.state.as_of,
                   payload=payload, order_id="long-order", fill_id="long-fill")
    return journal.state


class IdentityHistoryTests(unittest.TestCase):
    def test_all_12000_ids_remain_present_and_old_prefix_is_immutable(self):
        history = IdentityHistory("event", 12000)
        original = history
        prefix = None
        for i in range(12000):
            history = history.append(f"event-{i:05}")
            if i == 1023:
                prefix = history
        self.assertEqual(len(history), 12000)
        for i in range(12000):
            self.assertIn(f"event-{i:05}", history)
        self.assertEqual(len(original), 0)
        self.assertEqual(len(prefix), 1024)
        self.assertNotIn("event-01024", prefix)
        self.assertLessEqual(history._root.height, math.ceil(2 * math.log2(12001)))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            history.append("event-00000")
        with self.assertRaisesRegex(ValueError, "capacity"):
            history.append("new")

    def test_receipt_is_compact_bound_and_not_a_restore_object(self):
        history = IdentityHistory("fill", 2000)
        for i in range(1500):
            history = history.append(str(i))
        raw = primitive(history)
        self.assertLess(len(json.dumps(raw)), 256)
        self.assertEqual(raw["count"], 1500)
        self.assertNotEqual(digest(history), digest(IdentityHistory("fill", 2000)))
        self.assertNotEqual(digest(history), digest(replace(history, namespace="order")))
        with self.assertRaises(TypeError):
            IdentityHistory(**raw)
        with self.assertRaises(FrozenInstanceError):
            history.capacity = 1

    def test_policy_and_identifier_bounds(self):
        for value in (0, True, 100001):
            with self.subTest(value=value), self.assertRaises(ValueError):
                IdentityHistory("event", value)
        for value in ("", " bad", "x" * 129, 1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                IdentityHistory("event").append(value)

    def test_insert_orders_balance_without_dropping_ids(self):
        for values in (range(1000), reversed(range(1000)), (i * 997 % 1000 for i in range(1000))):
            with self.subTest(order=type(values).__name__):
                history = IdentityHistory("order")
                for value in values:
                    history = history.append(str(value))
                self.assertEqual(len(history), 1000)
                self.assertLess(history._root.height, 20)
                self.assertTrue(all(str(value) in history for value in range(1000)))


class LongPendingTests(unittest.TestCase):
    def test_default_bounded_digest_contract_stays_unchanged(self):
        state = start_pending_research(fixture())
        self.assertEqual(state.version, "isolated-usdt-long-pending/1")
        self.assertEqual(state.state_digest, digest((state.version, state)))
        self.assertIs(type(state.event_ids), tuple)

    def test_fresh_long_mode_has_distinct_version_and_same_risk_assessment(self):
        ledger = fixture()
        short, long = start_pending_research(ledger), start_long_pending_research(ledger)
        left, right = assess_ledger_purchase(short, request(short), AT), assess_ledger_purchase(long, request(long), AT)
        self.assertEqual(left.allowed, right.allowed)
        self.assertEqual(left.reasons, right.reasons)
        self.assertEqual(left.stress_loss, right.stress_loss)
        self.assertEqual(long.version, "isolated-usdt-long-pending/2")
        self.assertNotEqual(short.state_digest, long.state_digest)

    def test_mixed_or_swapped_namespace_policy_is_rejected(self):
        state = start_long_pending_research(fixture())
        for changes in ({"fill_ids": ()}, {"event_ids": state.fill_ids},
                        {"event_ids": IdentityHistory("event", 49999)},
                        {"reconciliation_halts": state.event_ids}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(state, **changes)

    def test_cannot_turn_existing_history_into_fresh_genesis(self):
        state = start_long_pending_research(fixture())
        event = FundingSettlement("SYNTH0", D(100), D(0))
        changed = record_ledger_event(state, event, "funding", state.revision, AT).state
        with self.assertRaisesRegex(ValueError, "genesis"):
            start_long_pending_research(changed.ledger)

    def test_early_fill_still_rejected_after_1200_recorded_ids(self):
        state = start_long_pending_research(fixture())
        payload = ExitFill("SYNTH0", D(1), D(100), D(0))
        # Identical global fill IDs remain retained without inventing economic fills.
        ids = state.fill_ids
        for i in range(1200):
            ids = ids.append(f"old-fill-{i}")
        state = replace(state, fill_ids=ids)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            record_fill(state, payload, "some-order", "old-fill-0", state.revision, AT)
        self.assertEqual(len(state.fill_ids), 1200)


class ReplayJournalTests(unittest.TestCase):
    def test_acknowledged_anchor_rejects_complete_prefix_loss_but_allows_unknown_tail(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "journal"
            with create(path) as journal:
                first = journal.receipt
                feed(journal, "100")
                last = journal.receipt
            # An unknown additional complete record is accepted after the old anchor.
            with restore(path, minimum_receipt=first) as journal:
                self.assertEqual(journal.receipt, last)
            lines = path.read_bytes().splitlines(keepends=True)
            path.write_bytes(lines[0])
            with self.assertRaisesRegex(ValueError, "truncated"):
                restore(path, minimum_receipt=last)
            wrong = {**first, "head": "f" * 64}
            with self.assertRaisesRegex(ValueError, "anchor mismatch"):
                restore(path, minimum_receipt=wrong)
            with self.assertRaisesRegex(ValueError, "foreign"):
                restore(path, minimum_receipt={**first, "context_digest": "f" * 64})

    def test_identity_capacity_does_not_reset_history_on_restore(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "journal"
            with create(path, identity_capacity=3) as journal:
                for _ in range(3):
                    feed(journal, "100")
                receipt = journal.receipt
                with self.assertRaisesRegex(ValueError, "capacity"):
                    feed(journal, "100")
            with restore(path) as journal:
                self.assertEqual(journal.receipt, receipt)
                self.assertEqual(len(journal.state.economic.event_ids), 3)
                with self.assertRaisesRegex(ValueError, "capacity"):
                    feed(journal, "100")

    def test_known_outside_intent_fill_is_booked_and_quarantine_survives_restore(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "journal"
            with create(path) as journal:
                state = entered(journal)
                journal.append("fill", expected_revision=state.revision, at=state.as_of,
                               payload=EntryFill("SYNTH0", D(".0001"), D(80), D(0), D(0), D(2)),
                               order_id="long-order", fill_id="unexpected-price")
                receipt = journal.receipt
                self.assertTrue(journal.state.economic.reconciliation_halts)
            with restore(path) as journal:
                self.assertEqual(journal.receipt, receipt)
                self.assertIn("unexpected-price", journal.state.economic.fill_ids)
                economic = journal.state.economic
                self.assertIn("account_halted", assess_ledger_purchase(
                    economic, request(economic), economic.as_of).reasons)

    def test_cancel_funding_and_exit_roundtrip_preserve_actual_economics(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "journal"
            with create(path) as journal:
                state = entered(journal)
                p = state.economic.pending
                journal.append("terminal", expected_revision=state.revision, at=state.as_of,
                               resolution=OrderResolution(p.intent_id, p.order_id, p.filled_quantity,
                                                          p.posted_margin, p.fees, "cancelled", "terminal"))
                feed(journal, "49")
                state = journal.state
                journal.append("economic", expected_revision=state.revision, at=state.as_of,
                               payload=FundingSettlement("SYNTH0", D(49), D(".0001")), event_id="funding-real-input")
                basket = journal.state.economic.ledger.baskets[0]
                journal.append("fill", expected_revision=journal.state.revision, at=journal.state.as_of,
                               payload=ExitFill(basket.symbol, basket.quantity, D(49), basket.quantity * D(".049")),
                               order_id="exit-order", fill_id="exit-fill")
                # Advance a full frame before a new setup, preserving old evidence.
                feed(journal, "46")
                feed(journal, "43")
                journal.append("reserve", expected_revision=journal.state.revision, at=journal.state.as_of,
                               symbol="SYNTH0", intent_id="cancel-me")
                journal.append("cancel", expected_revision=journal.state.revision, at=journal.state.as_of,
                               intent_id="cancel-me")
                receipt, state = journal.receipt, journal.state
            with restore(path) as journal:
                self.assertEqual(journal.receipt, receipt)
                self.assertEqual(journal.state.economic.ledger, state.economic.ledger)
                self.assertIsNone(journal.state.economic.pending)
                self.assertIn("cancel-me", journal.state.economic.intent_ids)
                self.assertIn("funding-real-input", journal.state.economic.event_ids)
                self.assertIn("exit-fill", journal.state.economic.fill_ids)

    def test_restore_partial_fill_and_unknown_order_without_retry_authority(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "journal"
            with create(path) as journal:
                state = entered(journal)
                receipt = journal.receipt
            with restore(path) as journal:
                self.assertEqual(journal.receipt, receipt)
                self.assertEqual(journal.state.state_digest, state.state_digest)
                p = journal.state.economic.pending
                self.assertEqual(p.order_id, "long-order")
                self.assertEqual(p.filled_quantity, floor_step(
                    p.request.quantity / 2, journal.state.profile.plan.contracts[0].quantity_step))
                with self.assertRaises(ValueError):
                    journal.append("attempt", expected_revision=journal.state.revision, at=journal.state.as_of,
                                   intent_id=p.intent_id, order_id="retry")
                resolution = OrderResolution(p.intent_id, p.order_id, p.filled_quantity,
                                             p.posted_margin, p.fees, "cancelled", "synthetic-terminal")
                journal.append("terminal", expected_revision=journal.state.revision, at=journal.state.as_of,
                               resolution=resolution)
            with restore(path) as journal:
                self.assertIsNone(journal.state.economic.pending)
                self.assertIn("long-fill", journal.state.economic.fill_ids)
                self.assertIn("long-order", journal.state.economic.order_ids)
                self.assertFalse(journal.receipt["execution_enabled"])

    def test_replay_1200_frames_restores_every_old_event_identity(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "journal"
            with create(path) as journal:
                first_event = None
                for i in range(1200):
                    value = frame(journal.state, str(100 + i % 2))
                    if first_event is None:
                        first_event = "mark-" + value.frame_digest
                    journal.append("frame", expected_revision=journal.state.revision,
                                   at=value.close_time, frame=value)
                receipt = journal.receipt
                self.assertGreater(len(journal.state.economic.event_ids), 1024)
            with restore(path) as journal:
                self.assertEqual(journal.receipt, receipt)
                self.assertIn(first_event, journal.state.economic.event_ids)
                self.assertEqual(journal.state.revision, 1200)
                self.assertTrue(all(s.indicator.rsi is not None for s in journal.state.signals))

    def test_unchanged_strategy_core_matches_bounded_replay_before_capacity(self):
        with TemporaryDirectory() as directory:
            with create(Path(directory) / "journal") as journal:
                ledger = fixture()
                short = start_signal_replay(profile(ledger), start_pending_research(ledger))
                for i in range(30):
                    value = frame(short, str(100 - i))
                    short = replay_frame(short, value, short.revision, value.close_time)
                    long = journal.append("frame", expected_revision=journal.state.revision,
                                          at=value.close_time, frame=value)
                    self.assertEqual(short.economic.ledger, long.economic.ledger)
                    self.assertEqual(short.signals, long.signals)

    def test_foreign_actor_profile_protocol_or_dataset_cannot_restore(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "journal"
            with create(path):
                pass
            for bindings in (
                {"profile_digest": "d" * 64}, {"protocol_digest": "d" * 64},
                {"dataset_digests": ("d" * 64,)},
            ):
                args = {"profile_digest": profile(fixture()).profile_digest,
                        "protocol_digest": PROTOCOL, "dataset_digests": DATA, **bindings}
                with self.subTest(bindings=bindings), self.assertRaises(ValueError):
                    FuturesReplayJournal.restore(path, **args)

    def test_create_only_private_file_and_exclusive_writer(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "journal"
            with create(path):
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                with self.assertRaises(FileExistsError):
                    create(path)
                with self.assertRaises(BlockingIOError):
                    restore(path)
            with restore(path):
                pass

    def test_symlink_hardlink_and_permissive_file_are_rejected(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "journal"
            with create(path):
                pass
            link = Path(directory) / "link"
            link.symlink_to(path)
            with self.assertRaises(OSError):
                restore(link)
            link.unlink()
            os.link(path, link)
            with self.assertRaises(ValueError):
                restore(path)
            link.unlink()
            path.chmod(0o644)
            with self.assertRaises(ValueError):
                restore(path)

    def test_rejected_input_does_not_append_or_mutate_state(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "journal"
            with create(path) as journal:
                before, size = journal.receipt, path.stat().st_size
                value = frame(journal.state, "100")
                for revision_value in (-1, True, 1):
                    with self.subTest(revision=revision_value), self.assertRaises(ValueError):
                        journal.append("frame", expected_revision=revision_value, at=value.close_time, frame=value)
                self.assertEqual(journal.receipt, before)
                self.assertEqual(path.stat().st_size, size)

    def test_duplicate_frame_cannot_create_another_journal_transition(self):
        with TemporaryDirectory() as directory:
            with create(Path(directory) / "journal") as journal:
                value = frame(journal.state, "100")
                journal.append("frame", expected_revision=0, at=value.close_time, frame=value)
                before = journal.receipt
                with self.assertRaisesRegex(ValueError, "duplicate frame"):
                    journal.append("frame", expected_revision=1, at=value.close_time, frame=value)
                self.assertEqual(journal.receipt, before)

    def test_command_capacity_is_terminal_without_discarding_evidence(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "journal"
            with create(path, command_capacity=1) as journal:
                feed(journal, "100")
                receipt = journal.receipt
                with self.assertRaisesRegex(ValueError, "capacity"):
                    feed(journal, "100")
                self.assertEqual(journal.receipt, receipt)
            with restore(path) as journal:
                self.assertEqual(journal.receipt, receipt)

    def test_unknown_fsync_commit_stops_then_full_readback_finds_actual_state(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "journal"
            journal = create(path)
            with patch("investalo_trading.futures_replay_journal.os.fsync", side_effect=OSError), \
                    self.assertRaises(JournalCommitUnknown):
                feed(journal, "100")
            with self.assertRaises(JournalCommitUnknown):
                journal.state
            with self.assertRaises(JournalCommitUnknown):
                journal.append("cancel", expected_revision=0, at=AT, intent_id="retry")
            journal.close()
            with restore(path) as journal:
                self.assertEqual(journal.state.revision, 1)
                self.assertEqual(journal.receipt["sequence"], 1)
                feed(journal, "101")

    def test_partial_write_stops_and_cannot_be_automatically_repaired(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "journal"
            journal = create(path)
            handle = journal._handle
            class ShortWriter:
                def __getattr__(self, name):
                    return getattr(handle, name)
                def write(self, value):
                    return handle.write(value[:20])
            journal._handle = ShortWriter()
            with self.assertRaises(JournalCommitUnknown):
                feed(journal, "100")
            journal.close()
            before = path.read_bytes()
            with self.assertRaises(ValueError):
                restore(path)
            self.assertEqual(path.read_bytes(), before)

    def test_truncated_or_mutated_records_fail_closed_without_tail_repair(self):
        with TemporaryDirectory() as directory:
            original = Path(directory) / "original"
            with create(original) as journal:
                feed(journal, "100")
            raw = original.read_bytes()
            records = [json.loads(line) for line in raw.splitlines()]
            damaged = [raw[:-1], raw[:-20], raw.replace(b'"sequence":1', b'"sequence":2'),
                       raw.replace(b'"execution_enabled":false', b'"execution_enabled":true')]
            records[-1]["state_digest"] = "f" * 64
            damaged.append(b"\n".join(json.dumps(r).encode() for r in records) + b"\n")
            records = [json.loads(line) for line in raw.splitlines()]
            records[-1]["command"]["arguments"]["frame"]["trade"][0]["close"] = "101"
            damaged.append(b"\n".join(json.dumps(r).encode() for r in records) + b"\n")
            damaged.append(raw + b'{"duplicate":1,"duplicate":2}\n')
            for i, value in enumerate(damaged):
                path = Path(directory) / f"damaged-{i}"
                path.write_bytes(value)
                path.chmod(0o600)
                with self.subTest(i=i), self.assertRaises(ValueError):
                    restore(path)
                self.assertEqual(path.read_bytes(), value)


if __name__ == "__main__":
    unittest.main()
