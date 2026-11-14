"""Actual status files and journal acknowledgements, including crash boundaries."""
from dataclasses import replace
from datetime import timedelta
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from investalo_trading.capital_digest import digest
from investalo_trading.futures_paper_journal import FuturesPaperJournal
from investalo_trading.futures_paper_status import (
    FuturesAssetPublisher, FuturesAssetReader, MAX_BYTES, PaperStatusCommitUnknown,
)
from investalo_trading.futures_paper_view import FuturesAssetState, asset_snapshot, asset_state
from investalo_trading.futures_replay_journal import JournalCommitUnknown
from investalo_trading.snapshot import _decode, primitive
from investalo_workers.futures_paper_worker import FuturesPaperWorker
from test_futures_paper_runtime import frames, journal, packet
from test_futures_paper_view import initial, opened, NOW, END
from test_futures_paper_settlement import settlement


def ready(path, genesis=None):
    genesis = genesis or initial()
    saved = journal(path, genesis)
    saved.append("warmup", hours=frames(genesis, range(130, 98, -2)),
                 expected_revision=0, at=END)
    quote = packet(saved.state, at=NOW)
    saved.append("batch", batch=quote, expected_revision=1, at=NOW)
    return saved


def display(state, now=NOW, ready=True):
    return asset_snapshot(state, tenant_id="tenant", account_id="account", now=now, account_ready=ready)


class FuturesPaperStatusTests(unittest.TestCase):
    def test_compact_roundtrip_preserves_view_and_recomputes_time_and_account_blockers(self):
        state = opened()
        values = _decode(FuturesAssetState, primitive(asset_state(state)))
        self.assertNotIn("funding_ids", primitive(values))
        for later in (NOW, NOW + timedelta(seconds=31), NOW + timedelta(hours=1)):
            for ready_account in (True, False):
                with self.subTest(now=later, ready=ready_account):
                    self.assertEqual(display(values, later, ready_account),
                                     display(state, later, ready_account))
        with self.assertRaises(ValueError):
            display(values, NOW - timedelta(seconds=1))
        with self.assertRaises(ValueError):
            replace(values, assets=values.assets[::-1])
        with self.assertRaises(ValueError):
            replace(values.assets[0], regular_entries=0)
        # A valid last fill at one price tick has a zero tick-floored next ceiling.
        zero = values.assets[0].maximum_fill_price * 0
        self.assertEqual(replace(values.assets[0], maximum_fill_price=zero).maximum_fill_price, zero)

    def test_published_real_positions_survive_independent_reader_and_expire_without_refresh(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            with ready(root / "paper.jsonl") as saved:
                reader = FuturesAssetReader(root, lambda: NOW)
                self.assertIsNone(reader("tenant", "account"))
                with FuturesAssetPublisher(root, saved, clock=lambda: NOW) as writer:
                    value = writer.publish(expected_revision=2)
                    self.assertEqual(value.journal_receipt, saved.receipt)
                    self.assertEqual(display(reader("tenant", "account")), display(saved.state))
                    path = next(p for p in root.glob("*.json"))
                    self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                    self.assertLess(path.stat().st_size, MAX_BYTES)
                    raw = path.read_bytes()
                    later = NOW + timedelta(seconds=31)
                    writer._clock = lambda: later
                    self.assertEqual(writer.publish(expected_revision=2), value)
                    self.assertEqual(path.read_bytes(), raw)
                    snapshot = display(reader("tenant", "account"), later)
                    self.assertFalse(snapshot["data_fresh"])
                    self.assertEqual(sum(a["position"] is not None for a in snapshot["assets"]), 3)
                    self.assertIn("data_stale", snapshot["assets"][0]["next_buy"]["reasons"])
                self.assertIsNone(reader("other-tenant", "account"))
                self.assertIsNone(reader("tenant", "other-account"))

    def test_writer_lock_cas_context_and_external_change_reject_before_overwrite(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            with ready(root / "paper.jsonl") as saved:
                with FuturesAssetPublisher(root, saved, clock=lambda: NOW) as writer:
                    with self.assertRaises(BlockingIOError):
                        FuturesAssetPublisher(root, saved, clock=lambda: NOW)
                    with self.assertRaises(ValueError):
                        writer.publish(expected_revision=1)
                    writer.publish(expected_revision=2)
                    root.chmod(0o755)
                    with self.assertRaises(ValueError):
                        writer.check()
                    root.chmod(0o700)
                    path = next(root.glob("*.json"))
                    raw = path.read_bytes()
                    path.write_bytes(raw.replace(b'"revision":2', b'"revision":1'))
                    with self.assertRaises(ValueError):
                        writer.check()
                    with self.assertRaises(ValueError):
                        writer.publish(expected_revision=2)
                    self.assertEqual(path.read_bytes(), raw.replace(b'"revision":2', b'"revision":1'))

    def test_poisoned_journal_cannot_publish_or_fetch_another_worker_batch(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            with ready(root / "paper.jsonl") as saved:
                with FuturesAssetPublisher(root, saved, clock=lambda: NOW) as writer:
                    writer.publish(expected_revision=2)
                    path = next(root.glob("*.json"))
                    raw = path.read_bytes()
                    quote = packet(saved.state, at=NOW + timedelta(seconds=1))
                    with patch("investalo_trading.futures_capital_journal.os.fsync",
                               side_effect=OSError("lost")), self.assertRaises(JournalCommitUnknown):
                        saved.append("batch", batch=quote, expected_revision=2, at=quote.quoted_at)
                    with self.assertRaises(JournalCommitUnknown):
                        writer.publish(expected_revision=3)
                    feed = unittest.mock.Mock()
                    worker = FuturesPaperWorker(saved, feed, lambda: quote.quoted_at, writer)
                    with self.assertRaises(JournalCommitUnknown):
                        worker.run_once()
                    feed.batch.assert_not_called()
                    self.assertEqual(path.read_bytes(), raw)

    def test_unknown_status_before_replace_keeps_prior_and_requires_anchored_restart(self):
        self._unknown_status(replaced=False)

    def test_unknown_directory_ack_after_replace_reads_new_receipt_once(self):
        self._unknown_status(replaced=True)

    def _unknown_status(self, *, replaced):
        with TemporaryDirectory() as folder:
            root, genesis = Path(folder), initial()
            path = root / "paper.jsonl"
            with ready(path, genesis) as saved:
                with FuturesAssetPublisher(root, saved, clock=lambda: NOW) as writer:
                    writer.publish(expected_revision=2)
                    quote = packet(saved.state, at=NOW + timedelta(seconds=1))
                    expected = saved.append("batch", batch=quote, expected_revision=2, at=quote.quoted_at)
                    writer._clock = lambda: quote.quoted_at
                    real_sync = os.fsync
                    calls = []

                    def fail(fd):
                        calls.append(fd)
                        if len(calls) == (2 if replaced else 1):
                            raise OSError("status ack lost")
                        return real_sync(fd)

                    with patch("investalo_trading.futures_paper_status.os.fsync", side_effect=fail):
                        with self.assertRaises(PaperStatusCommitUnknown):
                            writer.publish(expected_revision=3)
                    with self.assertRaises(PaperStatusCommitUnknown):
                        writer.publish(expected_revision=3)
                    reader = FuturesAssetReader(root, lambda: quote.quoted_at)
                    receipt = reader.publication("tenant", "account").journal_receipt
                    self.assertEqual(receipt["sequence"], 3 if replaced else 2)
                    if not replaced:
                        self.assertTrue(any(p.name.startswith(".") for p in root.iterdir()))
            with FuturesPaperJournal.restore(path, config_digest=genesis.config.config_digest,
                                              minimum_receipt=receipt) as restored:
                self.assertEqual(restored.state, expected)
                self.assertTrue(restored.acknowledges(receipt))
                with FuturesAssetPublisher(root, restored, clock=lambda: quote.quoted_at) as writer:
                    repaired = writer.publish(expected_revision=3)
                    self.assertEqual(repaired.journal_receipt["sequence"], 3)
                    self.assertEqual(repaired.state, asset_state(expected))

    def test_old_status_requires_full_restore_anchor_and_rejects_fork_truncation(self):
        with TemporaryDirectory() as folder:
            root, genesis = Path(folder), initial()
            path = root / "paper.jsonl"
            with ready(path, genesis) as saved:
                with FuturesAssetPublisher(root, saved, clock=lambda: NOW) as writer:
                    old = writer.publish(expected_revision=2)
                    quote = packet(saved.state, at=NOW + timedelta(seconds=1))
                    saved.append("batch", batch=quote, expected_revision=2, at=quote.quoted_at)
            with FuturesPaperJournal.restore(path, config_digest=genesis.config.config_digest) as saved:
                with self.assertRaisesRegex(ValueError, "minimum_receipt"):
                    FuturesAssetPublisher(root, saved, clock=lambda: quote.quoted_at)
            with FuturesPaperJournal.restore(path, config_digest=genesis.config.config_digest,
                                              minimum_receipt=old.journal_receipt) as saved:
                with FuturesAssetPublisher(root, saved, clock=lambda: quote.quoted_at) as writer:
                    current = writer.publish(expected_revision=3)
            lines = path.read_bytes().splitlines(keepends=True)
            path.write_bytes(b"".join(lines[:-1]))
            with self.assertRaises(ValueError):
                FuturesPaperJournal.restore(path, config_digest=genesis.config.config_digest,
                                            minimum_receipt=current.journal_receipt)
            # A valid alternate branch at the same revision cannot meet the anchor.
            with ready(root / "fork.jsonl", genesis) as fork:
                quote = packet(fork.state, price="99", at=NOW + timedelta(seconds=1))
                fork.append("batch", batch=quote, expected_revision=2, at=quote.quoted_at)
            with self.assertRaisesRegex(ValueError, "anchor"):
                FuturesPaperJournal.restore(root / "fork.jsonl", config_digest=genesis.config.config_digest,
                                            minimum_receipt=current.journal_receipt)

    def test_reader_rejects_symlinks_hardlinks_permissions_oversize_corrupt_and_foreign_content(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            with ready(root / "paper.jsonl") as saved:
                with FuturesAssetPublisher(root, saved, clock=lambda: NOW) as writer:
                    writer.publish(expected_revision=2)
                path, reader = next(root.glob("*.json")), FuturesAssetReader(root, lambda: NOW)
                original = path.read_bytes()
                for raw in (b"x", original.replace(b'"revision":2', b'"revision":1'),
                            b"x" * (MAX_BYTES + 1)):
                    path.write_bytes(raw)
                    with self.subTest(raw=len(raw)), self.assertRaises(ValueError):
                        reader("tenant", "account")
                record = json.loads(original)
                record["state"]["tenant_id"] = "foreign"
                record["content_digest"] = digest({k: v for k, v in record.items() if k != "content_digest"})
                path.write_text(json.dumps(record) + "\n")
                with self.assertRaises(ValueError):
                    reader("tenant", "account")
                path.write_bytes(original)
                path.chmod(0o644)
                with self.assertRaises(ValueError):
                    reader("tenant", "account")
                path.chmod(0o600)
                os.link(path, root / "hardlink")
                with self.assertRaises(ValueError):
                    reader("tenant", "account")
                (root / "hardlink").unlink()
                original_path = root / "original"
                path.rename(original_path)
                path.symlink_to(original_path)
                with self.assertRaises(OSError):
                    reader("tenant", "account")
                root.chmod(0o755)
                with self.assertRaises(ValueError):
                    reader("tenant", "account")

    def test_future_publication_rejected_and_republication_never_reverses_clock(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            with ready(root / "paper.jsonl") as saved:
                with FuturesAssetPublisher(root, saved, clock=lambda: NOW + timedelta(seconds=1)) as writer:
                    writer.publish(expected_revision=2)
                    reader = FuturesAssetReader(root, lambda: NOW)
                    with self.assertRaises(ValueError):
                        reader("tenant", "account")
                    writer._clock = lambda: NOW
                    with self.assertRaises(ValueError):
                        writer.publish(expected_revision=2)

    def test_injected_worker_publishes_after_warmup_batch_and_funding_commit(self):
        with TemporaryDirectory() as folder:
            root, genesis = Path(folder), initial()
            with journal(root / "paper.jsonl", genesis) as saved:
                clock = [END]

                class Feed:
                    def warmup(self, state):
                        return frames(state, range(130, 98, -2))

                    def batch(self, state):
                        return packet(state, at=clock[0])

                    def settlement(self, state):
                        return settlement(state, rates=(".0001",) * 5)

                with FuturesAssetPublisher(root, saved, clock=lambda: clock[0]) as writer:
                    worker = FuturesPaperWorker(saved, Feed(), lambda: clock[0], writer)
                    worker.warmup()
                    reader = FuturesAssetReader(root, lambda: clock[0])
                    self.assertEqual(reader("tenant", "account").revision, 1)
                    clock[0] = NOW
                    cycle = worker.run_once()
                    self.assertEqual(reader("tenant", "account").revision, cycle.revision)
                    self.assertEqual(cycle.entries, 3)
                    clock[0] = END + timedelta(hours=1, seconds=5)
                    cycle = worker.settle_once()
                    self.assertEqual((cycle.entries, cycle.closures), (0, 0))
                    self.assertEqual(reader("tenant", "account").trade_at, NOW)
                    self.assertEqual(reader.publication("tenant", "account").journal_receipt, saved.receipt)
