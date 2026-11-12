"""Durable capital profile recovery and larger ID policy, without market performance."""
from dataclasses import FrozenInstanceError, replace
from datetime import timedelta
from decimal import Decimal
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from investalo_trading.capital_identity_history import CapitalIdentityHistory
from investalo_trading.futures_capital_journal import CapitalReplayJournal
from investalo_trading.futures_capital_signals import (
    CapitalSignalProfile, assess_capital_signal, replay_capital_hour,
)
from investalo_trading.futures_ledger import (
    ExitFill, FundingSettlement, LedgerMark, MarginPosting, MarkBatch,
)
from investalo_trading.futures_replay_journal import JournalCommitUnknown
from investalo_trading.identity_history import IdentityHistory
from investalo_trading.snapshot import digest, primitive
from test_futures_capital_research import liquidation, start as economic_start
from test_futures_capital_signals import hour
from test_futures_ledger import AT

D = Decimal
PROTOCOL = "a" * 64
DATA = ("b" * 64, "c" * 64)


def profile(hours=1, slots=3):
    return CapitalSignalProfile(economic_start(slots).ledger.plan, hours, D("0"), "synthetic-only")


def create(path, hours=1, slots=3, **kwargs):
    plan = profile(hours, slots)
    marks = tuple(LedgerMark(s, D("100")) for s in plan.plan.symbols)
    return CapitalReplayJournal.create(
        path, plan, marks, marks, AT, "synthetic-initial",
        **{"protocol_digest": PROTOCOL, "dataset_digests": DATA, **kwargs})


def restore(path, hours=1, slots=3, **kwargs):
    return CapitalReplayJournal.restore(
        path, profile_digest=profile(hours, slots).profile_digest,
        protocol_digest=PROTOCOL, dataset_digests=DATA, **kwargs)


def append(journal, kind, at=None, **kwargs):
    return journal.append(kind, expected_revision=journal.state.revision,
                          at=at or journal.state.as_of, **kwargs)


def feed(journal, price):
    value = hour(journal.state, price, all_assets=True)
    return append(journal, "hour", at=value.close_time, frame=value)


def h4(journal, price):
    for _ in range(4):
        feed(journal, price)


def ready(journal):
    for i in range(16):
        h4(journal, D("130") - i * 2)


def buy(journal, leverage="2", symbol="SYNTH0"):
    state = journal.state
    index = state.profile.plan.symbols.index(symbol)
    if not state.economic.ledger.baskets[index].quantity:
        append(journal, "leverage", symbol=symbol, leverage=D(leverage),
               evidence_digest="static-synthetic", event_id=f"decision-{state.revision}")
    state = journal.state
    assessment = assess_capital_signal(state, symbol, state.trade_prices[index].price, state.as_of)
    return append(journal, "entry", assessment=assessment,
                  price=assessment.capital.request.maximum_fill_price,
                  event_id=f"fill-{state.revision}")


def quote(journal, price, at=None, event_id=None):
    values = tuple(LedgerMark(s, D(price)) for s in journal.state.profile.plan.symbols)
    return append(journal, "prices", at=at or journal.state.as_of + timedelta(microseconds=1),
                  trade=values, mark=values, event_id=event_id or f"quote-{journal.state.revision}")


def economic(journal, payload, at=None, event_id=None):
    return append(journal, "economic", at=at, payload=payload,
                  event_id=event_id or f"economic-{journal.state.revision}")


class CapitalIdentityTests(unittest.TestCase):
    def test_retains_more_than_legacy_maximum_without_eviction_or_prefix_mutation(self):
        history = CapitalIdentityHistory("event", 100005)
        first = history
        prefix = None
        for i in range(100005):
            history = history.append(f"event-{i:06}")
            if i == 1023:
                prefix = history
        self.assertEqual(len(history), 100005)
        self.assertEqual(len(first), 0)
        self.assertEqual(len(prefix), 1024)
        self.assertLess(history._root.height, 32)
        for i in range(100005):
            self.assertIn(f"event-{i:06}", history)
        self.assertNotIn("event-001024", prefix)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            history.append("event-000000")
        with self.assertRaisesRegex(ValueError, "capacity"):
            history.append("new")

    def test_distinct_hash_domain_compact_codec_and_old_policy_unchanged(self):
        old = IdentityHistory("event", 20).append("id")
        new = CapitalIdentityHistory("event", 20).append("id")
        self.assertNotEqual(digest(old), digest(new))
        self.assertEqual(primitive(new)["count"], 1)
        self.assertLess(len(json.dumps(primitive(new))), 256)
        with self.assertRaises(ValueError):
            IdentityHistory("event", 100001)
        with self.assertRaisesRegex(ValueError, "own"):
            CapitalIdentityHistory("event", 20, old._root)
        with self.assertRaises(TypeError):
            CapitalIdentityHistory(**primitive(new))
        with self.assertRaises(FrozenInstanceError):
            new.capacity = 1

    def test_explicit_policy_and_identifier_bounds(self):
        for value in (0, True, 1000001):
            with self.subTest(capacity=value), self.assertRaises(ValueError):
                CapitalIdentityHistory("event", value)
        for value in ("", " bad", 1, "x" * 129):
            with self.subTest(identifier=value), self.assertRaises(ValueError):
                CapitalIdentityHistory("event").append(value)
        with self.assertRaises(ValueError):
            CapitalIdentityHistory("foreign")

    def test_mixed_insertion_orders_keep_every_identity_and_balance(self):
        for values in (range(1000), reversed(range(1000)), (i * 997 % 1000 for i in range(1000))):
            with self.subTest(order=type(values).__name__):
                state = CapitalIdentityHistory("fill", 1000)
                for i in values:
                    state = state.append(str(i))
                self.assertTrue(all(str(i) in state for i in range(1000)))
                self.assertLess(state._root.height, 20)


class CapitalJournalTests(unittest.TestCase):
    def test_genesis_roundtrip_is_distinct_and_execution_stays_off(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "journal"
            with create(path) as journal:
                before = journal.receipt
                self.assertEqual(journal.state.economic.event_ids.capacity, 250000)
                self.assertIs(type(journal.state.economic.event_ids), CapitalIdentityHistory)
                self.assertFalse(journal.state.execution_enabled)
            with restore(path, minimum_receipt=before) as journal:
                self.assertEqual(journal.receipt, before)
                self.assertEqual(journal.state.profile.plan, profile().plan)

    def test_five_actual_stages_and_manual_reserve_restore_without_hindsight(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "journal"
            with create(path) as journal:
                ready(journal)
                buy(journal)
                price = D("100")
                for _ in range(4):
                    for _ in range(20):
                        h4(journal, price)
                    h4(journal, price * D("1.04"))
                    price *= D(".95")
                    h4(journal, price)
                    buy(journal)
                before, state = journal.receipt, journal.state
                self.assertEqual(tuple(r.stage for r in state.economic.stages), (1, 2, 3, 4, 5))
                self.assertTrue(state.signals[0].manual_notice)
                self.assertEqual(state.economic.ledger.baskets[0].margin_committed, D("2405.75709923"))
            with restore(path, minimum_receipt=before) as journal:
                self.assertEqual(journal.receipt, before)
                self.assertEqual(journal.state, state)
                self.assertIn(state.economic.stages[0].event_id, journal.state.economic.event_ids)
                with self.assertRaisesRegex(ValueError, "manual sixth"):
                    buy(journal)

    def test_funding_partial_exit_protection_and_exact_midnight_survive_restore(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "journal"
            with create(path) as journal:
                ready(journal)
                buy(journal)
                quote(journal, "110")
                economic(journal, FundingSettlement("SYNTH0", D(110), D(".001")))
                stop = journal.state.signals[0].stop
                economic(journal, ExitFill("SYNTH0", D(1), D(110), D(".11")))
                while journal.state.last_hour.close_time.hour:
                    feed(journal, "110")
                state, before = journal.state, journal.receipt
            with restore(path) as journal:
                self.assertEqual(journal.state, state)
                self.assertEqual(journal.receipt, before)
                self.assertGreaterEqual(journal.state.signals[0].stop, stop)
                self.assertLess(journal.state.economic.ledger.baskets[0].funding_net, 0)
                self.assertEqual(journal.state.economic.ledger.day_started_at, state.last_hour.close_time)
                self.assertEqual(journal.state.economic.ledger.plan.initial_equity, D(10000))

    def test_native_funding_time_credit_and_explicit_cost_restoration_roundtrip(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "journal"
            with create(path) as journal:
                ready(journal)
                buy(journal)
                trade_at = journal.state.trade_at
                marks = tuple(LedgerMark(s, D(101)) for s in journal.state.profile.plan.symbols)
                economic(journal, MarkBatch(marks),
                         at=journal.state.as_of + timedelta(milliseconds=18))
                self.assertEqual(journal.state.trade_at, trade_at)
                self.assertFalse(journal.state.signals[0].protected)
                economic(journal, FundingSettlement("SYNTH0", D(101), D(".001")))
                b = journal.state.economic.ledger.baskets[0]
                debt = b.margin_committed - b.isolated_balance
                economic(journal, MarginPosting("SYNTH0", debt, cost_restoration=True))
                quote(journal, "101")
                economic(journal, FundingSettlement("SYNTH0", D(101), D("-.002")))
                state, before = journal.state, journal.receipt
                self.assertGreater(state.economic.ledger.baskets[0].funding_net, 0)
            with restore(path) as journal:
                self.assertEqual(journal.state, state)
                self.assertEqual(journal.receipt, before)
                with self.assertRaisesRegex(ValueError, "reserved entry capital"):
                    economic(journal, MarginPosting("SYNTH0", D(1)))
                self.assertEqual(journal.receipt, before)

    def test_liquidation_terminal_loss_and_unposted_reserve_remain_terminal(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "journal"
            with create(path) as journal:
                ready(journal)
                buy(journal, "10")
                quote(journal, "80")
                self.assertIn("liquidation_settlement_required", journal.state.signals[0].exit_reasons)
                economic(journal, liquidation(journal.state.economic))
                state, before = journal.state, journal.receipt
                self.assertGreater(state.economic.stopped[0].unposted_stage_capital, 0)
            with restore(path) as journal:
                self.assertEqual(journal.state, state)
                self.assertEqual(journal.receipt, before)
                self.assertEqual(journal.state.signals[0].exit_reasons, ("liquidated",))
                quote(journal, "110")
                with self.assertRaises(ValueError):
                    buy(journal)
                buy(journal, symbol="SYNTH1")

    def test_latched_liquidation_cannot_disappear_on_recovery_or_restart(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "journal"
            with create(path) as journal:
                ready(journal)
                buy(journal, "10")
                quote(journal, "80")
                quote(journal, "110")
                self.assertFalse(journal.state.economic.liquidation_required)
            with restore(path) as journal:
                self.assertIn("liquidation_settlement_required", journal.state.signals[0].exit_reasons)
                b = journal.state.economic.ledger.baskets[0]
                with self.assertRaisesRegex(ValueError, "terminal receipt"):
                    economic(journal, ExitFill(b.symbol, b.quantity, D(110), D(0)))
                with self.assertRaisesRegex(ValueError, "unsettled liquidation"):
                    buy(journal, symbol="SYNTH1")

    def test_normal_cycle_exit_keeps_wilder_history_and_next_frozen_leverage(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "journal"
            with create(path) as journal:
                ready(journal)
                buy(journal)
                quote(journal, "110")
                b = journal.state.economic.ledger.baskets[0]
                economic(journal, ExitFill(b.symbol, b.quantity, D(110), b.quantity * D(".11")))
                self.assertEqual(journal.state.signals[0].cycle, 2)
                for _ in range(2):
                    h4(journal, "90")
                buy(journal, "5")
                state, before = journal.state, journal.receipt
            with restore(path) as journal:
                self.assertEqual(journal.state, state)
                self.assertEqual(journal.receipt, before)
                self.assertEqual(tuple(d.leverage for d in state.economic.decisions), (D(2), D(5)))
                self.assertEqual(journal.state.economic.ledger.closed_baskets, 1)

    def test_partial_h4_buffer_and_h1_or_h4_cadence_continue_identically(self):
        with TemporaryDirectory() as directory:
            for hours in (1, 4):
                path = Path(directory) / str(hours)
                with create(path, hours) as journal:
                    for i in range(7):
                        feed(journal, str(100 - i))
                    state, before = journal.state, journal.receipt
                    self.assertEqual(len(state.h4_buffer), 3)
                    next_hour = hour(state, "92", all_assets=True)
                    expected = replay_capital_hour(state, next_hour, state.revision, next_hour.close_time)
                with restore(path, hours, minimum_receipt=before) as journal:
                    actual = append(journal, "hour", at=next_hour.close_time, frame=next_hour)
                    self.assertEqual(actual, expected)
                    self.assertFalse(actual.h4_buffer)
                    self.assertEqual(actual.signals[0].entry_indicator.true_ranges, 2)
                with self.assertRaises(ValueError):
                    restore(path, 5 - hours)

    def test_synthetic_five_coin_hourly_axis_with_finer_quotes_restores_all_ids(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "journal"
            with create(path, slots=5) as journal:
                for i in range(1200):
                    frame = hour(journal.state, str(100 + i % 2), all_assets=True)
                    for minute in (5, 20, 35, 50):
                        quote(journal, str(100 + i % 2),
                              at=frame.trade[0].open_time + timedelta(minutes=minute),
                              event_id=f"quote-{i}-{minute}")
                    append(journal, "hour", at=frame.close_time, frame=frame)
                state, before = journal.state, journal.receipt
                self.assertEqual(state.revision, 6000)
                self.assertEqual(len(state.economic.event_ids), 6050)
                self.assertIn("quote-0-5", state.economic.event_ids)
            with restore(path, slots=5, minimum_receipt=before) as journal:
                self.assertEqual(journal.state, state)
                self.assertEqual(journal.receipt, before)
                self.assertIn("quote-0-5", journal.state.economic.event_ids)
                self.assertEqual(journal.state.profile.plan.symbols, state.profile.plan.symbols)

    def test_duplicate_hours_and_old_event_ids_cannot_be_appended_after_restore(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "journal"
            with create(path) as journal:
                feed(journal, "100")
                quote(journal, "100", event_id="old")
            with restore(path) as journal:
                before = journal.receipt
                with self.assertRaisesRegex(ValueError, "duplicate hour"):
                    append(journal, "hour", frame=journal.state.last_hour)
                with self.assertRaisesRegex(ValueError, "duplicate"):
                    quote(journal, "100", event_id="old")
                self.assertEqual(journal.receipt, before)

    def test_capacity_failure_in_multi_event_midnight_transition_is_atomic(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "journal"
            with create(path, identity_capacity=24) as journal:
                for _ in range(23):
                    feed(journal, "100")
                before, raw = journal.receipt, path.read_bytes()
                with self.assertRaisesRegex(ValueError, "capacity"):
                    feed(journal, "100")  # mark fits; day basis does not
                self.assertEqual(journal.receipt, before)
                self.assertEqual(path.read_bytes(), raw)
            with restore(path) as journal:
                self.assertEqual(journal.receipt, before)
                self.assertEqual(len(journal.state.economic.event_ids), 23)

    def test_command_and_file_resource_exhaustion_preserve_acknowledged_state(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "journal"
            with create(path, command_capacity=1) as journal:
                feed(journal, "100")
                before, raw = journal.receipt, path.read_bytes()
                with self.assertRaisesRegex(ValueError, "capacity"):
                    feed(journal, "100")
                self.assertEqual(journal.receipt, before)
                self.assertEqual(path.read_bytes(), raw)
            path = Path(directory) / "filelimit"
            with create(path) as journal:
                before, size = journal.receipt, path.stat().st_size
                with patch("investalo_trading.futures_capital_journal.MAX_FILE_BYTES", size), \
                        self.assertRaisesRegex(ValueError, "capacity"):
                    feed(journal, "100")
                self.assertEqual(journal.receipt, before)
                self.assertEqual(path.stat().st_size, size)

    def test_rejected_revision_time_unfinished_hour_and_stale_assessment_never_write(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "journal"
            with create(path) as journal:
                frame = hour(journal.state, "100", all_assets=True)
                before, raw = journal.receipt, path.read_bytes()
                for rev in (-1, True, 1):
                    with self.subTest(revision=rev), self.assertRaises(ValueError):
                        journal.append("hour", expected_revision=rev, at=frame.close_time, frame=frame)
                with self.assertRaisesRegex(ValueError, "unfinished"):
                    append(journal, "hour", frame=frame)
                self.assertEqual(journal.receipt, before)
                self.assertEqual(path.read_bytes(), raw)
                ready(journal)
                append(journal, "leverage", symbol="SYNTH0", leverage=D(2),
                       evidence_digest="static", event_id="decision")
                assessment = assess_capital_signal(journal.state, "SYNTH0", D(100), journal.state.as_of)
                quote(journal, "100")
                before, raw = journal.receipt, path.read_bytes()
                with self.assertRaisesRegex(ValueError, "stale"):
                    append(journal, "entry", assessment=assessment, price=D(100), event_id="stale")
                self.assertEqual(journal.receipt, before)
                self.assertEqual(path.read_bytes(), raw)

    def test_foreign_actor_protocol_dataset_and_noncanonical_genesis_rejected_before_creation(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "journal"
            with create(path):
                pass
            bindings = {
                "profile_digest": profile().profile_digest,
                "protocol_digest": PROTOCOL, "dataset_digests": DATA,
            }
            foreign = replace(profile().plan, account_id="foreign")
            other = replace(profile(), plan=foreign)
            for changed in (
                {"profile_digest": other.profile_digest},
                {"protocol_digest": "f" * 64}, {"dataset_digests": ("f" * 64,)},
            ):
                with self.subTest(changed=changed), self.assertRaises(ValueError):
                    CapitalReplayJournal.restore(path, **{**bindings, **changed})
            new = Path(directory) / "invalid"
            for changed in ({"command_capacity": True}, {"identity_capacity": 1000001},
                            {"dataset_digests": DATA[::-1]}, {"protocol_digest": "bad"}):
                with self.subTest(changed=changed), self.assertRaises(ValueError):
                    create(new, **changed)
                self.assertFalse(new.exists())

    def test_private_create_only_exclusive_file_policy(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "journal"
            with create(path):
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                with self.assertRaises(FileExistsError):
                    create(path)
                with self.assertRaises(BlockingIOError):
                    restore(path)
            symlink = Path(directory) / "link"
            symlink.symlink_to(path)
            with self.assertRaises(OSError):
                restore(symlink)
            symlink.unlink()
            path.chmod(0o644)
            with self.assertRaises(ValueError):
                restore(path)

    def test_unknown_fsync_stops_writer_then_full_restore_finds_complete_transition(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "journal"
            journal = create(path)
            original = journal.receipt
            with patch("investalo_trading.futures_capital_journal.os.fsync", side_effect=OSError), \
                    self.assertRaises(JournalCommitUnknown):
                feed(journal, "100")
            for access in (lambda: journal.state, lambda: journal.receipt,
                           lambda: journal.append("hour", expected_revision=0, at=AT)):
                with self.assertRaises(JournalCommitUnknown):
                    access()
            journal.close()
            with restore(path, minimum_receipt=original) as journal:
                self.assertEqual(journal.state.revision, 1)
                feed(journal, "101")

    def test_partial_write_is_terminal_and_never_automatically_repaired(self):
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

    def test_acknowledged_anchor_detects_lost_complete_tail_and_accepts_unknown_tail(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "journal"
            with create(path) as journal:
                first = journal.receipt
                feed(journal, "100")
                last = journal.receipt
            with restore(path, minimum_receipt=first) as journal:
                self.assertEqual(journal.receipt, last)
            raw = path.read_bytes()
            with self.assertRaisesRegex(ValueError, "anchor mismatch"):
                restore(path, minimum_receipt={**last, "head": "f" * 64})
            path.write_bytes(raw.splitlines(keepends=True)[0])
            with self.assertRaisesRegex(ValueError, "truncated"):
                restore(path, minimum_receipt=last)

    def test_invalid_payload_schema_changed_input_chain_and_truncation_fail_closed(self):
        with TemporaryDirectory() as directory:
            original = Path(directory) / "journal"
            with create(original) as journal:
                feed(journal, "100")
                quote(journal, "101")
            raw = original.read_bytes()
            records = [json.loads(line) for line in raw.splitlines()]
            damaged = [raw[:-1], raw[:-20],
                       raw.replace(b'"execution_enabled":false', b'"execution_enabled":true'),
                       raw.replace(b'"capital_policy":"isolated-usdt-capital-ladder/1"',
                                   b'"capital_policy":"foreign"'),
                       raw.replace(b'"sequence":1', b'"sequence":2'),
                       raw + b'{"duplicate":1,"duplicate":2}\n']
            records[-1]["state_digest"] = "f" * 64
            damaged.append(b"\n".join(json.dumps(r).encode() for r in records) + b"\n")
            records = [json.loads(line) for line in raw.splitlines()]
            records[-1]["command"]["arguments"]["trade"][0]["price"] = "102"
            damaged.append(b"\n".join(json.dumps(r).encode() for r in records) + b"\n")
            for i, value in enumerate(damaged):
                path = Path(directory) / str(i)
                path.write_bytes(value)
                path.chmod(0o600)
                with self.subTest(i=i), self.assertRaises(ValueError):
                    restore(path)
                self.assertEqual(path.read_bytes(), value)


if __name__ == "__main__":
    unittest.main()
