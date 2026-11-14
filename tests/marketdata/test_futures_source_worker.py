"""Native response archives, atomic cursor replay and bounded startup contract."""
from dataclasses import replace
from datetime import timedelta
import hashlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from investalo_marketdata.bitget import milliseconds
from investalo_marketdata.futures_paper_archive import FuturesPaperArchive, PaperArchiveCommitUnknown
from investalo_marketdata.futures_paper_feed import H1, SYMBOLS, stamp
from investalo_marketdata.snapshot import canonical
from investalo_trading.futures_paper_journal import FuturesPaperJournal
from investalo_trading.futures_paper import start_paper
from investalo_trading.futures_capital_research import start_capital_research
from investalo_trading.futures_capital_signals import start_capital_signals
from investalo_trading.futures_paper_status import FuturesAssetPublisher, FuturesAssetReader, PaperStatusCommitUnknown
from investalo_trading.futures_replay_journal import JournalCommitUnknown
from investalo_workers.futures_source_worker import FuturesSourceWorker
from investalo_workers.futures_paper_main import main
from test_futures_paper_feed import initial, AT, END, NOW
from test_futures_paper_runtime import frames, journal


class Provider:
    def __init__(self):
        self.now, self.urls = NOW, []
        self.target = END + H1

    def fetch(self, url):
        self.urls.append(url)
        query, path = parse_qs(urlsplit(url).query), urlsplit(url).path
        symbol = query["symbol"][0]
        if "granularity" in query:
            start, end = stamp(query["startTime"][0]), stamp(query["endTime"][0])
            interval = timedelta(minutes=1) if query["granularity"] == ["1m"] else H1
            rows = []
            at = start
            while at <= end:
                price = 100 if interval < H1 else 130 - 2 * ((at - AT) // H1)
                rows.append([str(milliseconds(at)), str(price), str(price + 1), str(price - 1),
                             str(price), "0", "0"])
                at += interval
        elif "history-fund-rate" in path:
            times = [END, END - 8 * H1, AT, AT - 8 * H1]
            if self.now >= self.target:
                times.insert(0, self.target)
            rows = [{"symbol": symbol, "fundingTime": str(milliseconds(at)),
                     "fundingRate": "-0.0001" if SYMBOLS.index(symbol) % 2 else "0.0001"}
                    for at in times]
        elif "current-fund-rate" in path:
            next_update = self.target if self.now < self.target else self.target + 8 * H1
            rows = [{"symbol": symbol, "fundingRateInterval": "8", "fundingRate": "0.0002",
                     "nextUpdate": str(milliseconds(next_update))}]
        else:
            rows = [{"symbol": symbol, "bidPr": "100", "askPr": "100.01", "markPrice": "100.005",
                     "ts": str(milliseconds(self.now))}]
        return {"code": "00000", "requestTime": milliseconds(self.now), "data": rows}


def configured(folder, genesis=None):
    root = Path(folder)
    for name in ("archive", "status"):
        (root / name).mkdir(mode=0o700)
    provider = Provider()
    saved = journal(root / "paper.jsonl", genesis or initial())
    archive = FuturesPaperArchive(root / "archive", lambda: provider.now,
                                  provider.fetch, provider.fetch, lambda _: None)
    publisher = FuturesAssetPublisher(root / "status", saved, clock=lambda: provider.now)
    worker = FuturesSourceWorker(saved, archive, publisher, lambda: provider.now)
    return saved, archive, publisher, worker, provider


def opened(worker, provider):
    assert worker.run_once().outcome == "warmed"
    provider.now += timedelta(seconds=1)
    result = worker.run_once()
    assert result.entries == 3
    return result


class FuturesSourceWorkerTests(unittest.TestCase):
    def test_actual_archive_warmup_quotes_cursor_and_status_use_same_acknowledged_revision(self):
        with TemporaryDirectory() as folder:
            saved, archive, publisher, worker, provider = configured(folder)
            try:
                cycle = opened(worker, provider)
                state, receipt, cursor = saved.source_checkpoint()
                self.assertEqual((cycle.revision, receipt["sequence"]), (2, 2))
                self.assertEqual(archive.load(cursor.market).collected_at, state.signal.trade_at)
                self.assertEqual(len(provider.urls), 50)
                published = FuturesAssetReader(Path(folder) / "status").publication("tenant", "account")
                self.assertEqual(published.journal_receipt, receipt)
                self.assertEqual(sum(bool(a.quantity) for a in published.state.assets), 3)
                self.assertFalse(cycle.execution_enabled)
                provider.now += timedelta(seconds=1)
                self.assertEqual(worker.run_once().entries, 0)
            finally:
                publisher.close()
                saved.close()

    def test_closed_minute_wait_is_before_fetch_and_funding_then_quotes_book_native_ids_once(self):
        with TemporaryDirectory() as folder:
            saved, archive, publisher, worker, provider = configured(folder)
            try:
                opened(worker, provider)
                provider.now = provider.target + timedelta(seconds=10)
                before, urls = saved.receipt, len(provider.urls)
                self.assertEqual(worker.run_once().outcome, "waiting_funding_minute")
                self.assertEqual((saved.receipt, len(provider.urls)), (before, urls))
                provider.now = provider.target + timedelta(seconds=65)
                result = worker.run_once()
                self.assertEqual((result.outcome, result.revision, result.entries),
                                 ("funding_and_quotes", 4, 0))
                self.assertEqual(len(saved.state.funding_ids), 5)
                self.assertIsNone(saved.source_checkpoint()[2].pending)
                funding = tuple(b.funding_net for b in saved.state.signal.economic.ledger.baskets)
                provider.now += timedelta(seconds=1)
                self.assertEqual(worker.run_once().outcome, "quotes")
                self.assertEqual(len(saved.state.funding_ids), 5)
                self.assertEqual(tuple(b.funding_net for b in saved.state.signal.economic.ledger.baskets), funding)
            finally:
                publisher.close()
                saved.close()

    def test_restart_after_funding_before_quotes_uses_pending_archived_pair_and_fresh_capture(self):
        self._interrupted_batch(unknown=False)

    def test_unknown_batch_write_full_readback_already_advances_cursor_without_duplicate_funding(self):
        self._interrupted_batch(unknown=True)

    def _interrupted_batch(self, *, unknown):
        with TemporaryDirectory() as folder:
            saved, archive, publisher, worker, provider = configured(folder)
            genesis = initial()
            try:
                opened(worker, provider)
                provider.now = provider.target + timedelta(seconds=65)
                original = saved.append

                def interrupted(kind, **args):
                    if kind == "source_batch":
                        if unknown:
                            with patch("investalo_trading.futures_capital_journal.os.fsync",
                                       side_effect=OSError("ack lost")):
                                return original(kind, **args)
                        raise RuntimeError("process ended after funding")
                    return original(kind, **args)

                with patch.object(saved, "append", side_effect=interrupted):
                    with self.assertRaises(JournalCommitUnknown if unknown else RuntimeError):
                        worker.run_once()
                published = FuturesAssetReader(Path(folder) / "status").publication("tenant", "account")
                self.assertEqual(published.journal_receipt["sequence"], 3)
            finally:
                publisher.close()
                saved.close()
            provider.now += timedelta(seconds=1)
            with FuturesPaperJournal.restore(Path(folder) / "paper.jsonl",
                    config_digest=genesis.config.config_digest, minimum_receipt=published.journal_receipt) as restored:
                cursor = restored.source_checkpoint()[2]
                self.assertEqual(cursor.pending is None, unknown)
                self.assertEqual(len(restored.state.funding_ids), 5)
                with FuturesAssetPublisher(Path(folder) / "status", restored,
                                            clock=lambda: provider.now) as pub:
                    pub.publish(expected_revision=restored.state.revision)
                    result = FuturesSourceWorker(restored, archive, pub, lambda: provider.now).run_once()
                    self.assertEqual(result.entries, 0)
                    self.assertEqual(len(restored.state.funding_ids), 5)
                    self.assertIsNone(restored.source_checkpoint()[2].pending)

    def test_publication_failure_after_source_commit_stops_fetch_until_anchored_restart(self):
        with TemporaryDirectory() as folder:
            saved, archive, publisher, worker, provider = configured(folder)
            try:
                opened(worker, provider)
                provider.now += timedelta(seconds=1)
                real_sync = os.fsync
                calls = []

                def fail_status(fd):
                    calls.append(fd)
                    if len(calls) == 2:
                        raise OSError("publication ack lost")
                    return real_sync(fd)

                # Patch only publication write after the source cohort is fully captured.
                original = publisher.publish
                with patch.object(publisher, "publish", side_effect=lambda **kw: _failed_publish(
                        original, fail_status, kw)), self.assertRaises(PaperStatusCommitUnknown):
                    worker.run_once()
                count = len(provider.urls)
                with self.assertRaises(PaperStatusCommitUnknown):
                    worker.run_once()
                self.assertEqual(len(provider.urls), count)
                self.assertEqual(saved.state.revision, 3)
                self.assertIsNotNone(saved.source_checkpoint()[2].market)
            finally:
                publisher.close()
                saved.close()

    def test_corrupt_native_archive_and_self_consistent_fake_observation_fail_before_more_http(self):
        with TemporaryDirectory() as folder:
            saved, archive, publisher, worker, provider = configured(folder)
            try:
                opened(worker, provider)
                ref = saved.source_checkpoint()[2].market
                cohort = Path(folder) / "archive" / ref.key
                observation = json.loads((cohort / "observation.json").read_bytes())
                observation["observation"]["quotes"][0]["quote"]["mark"] = "101"
                raw = canonical(observation).encode()
                (cohort / "observation.json").write_bytes(raw)
                receipt = json.loads((cohort / "receipt.json").read_bytes())
                receipt["data_digest"] = hashlib.sha256(raw).hexdigest()
                raw_receipt = canonical(receipt).encode()
                (cohort / "receipt.json").write_bytes(raw_receipt)
                changed = replace(ref, data_digest=receipt["data_digest"],
                                  receipt_digest=hashlib.sha256(raw_receipt).hexdigest())
                with self.assertRaisesRegex(ValueError, "replay differs"):
                    archive.load(changed)
                provider.now += timedelta(seconds=1)
                count, journal_receipt = len(provider.urls), saved.receipt
                with self.assertRaises(ValueError):
                    worker.run_once()
                self.assertEqual((len(provider.urls), saved.receipt), (count, journal_receipt))
            finally:
                publisher.close()
                saved.close()

    def test_archive_fsync_unknown_preserves_partial_cohort_and_stops_same_writer_without_journal(self):
        with TemporaryDirectory() as folder:
            saved, archive, publisher, worker, provider = configured(folder)
            try:
                # Parent directory fsync is first, first response fsync second.
                real_sync, calls = os.fsync, []

                def fail(fd):
                    calls.append(fd)
                    if len(calls) == 2:
                        raise OSError("native write lost")
                    return real_sync(fd)

                with patch("investalo_marketdata.futures_paper_archive.os.fsync", side_effect=fail):
                    with self.assertRaises(PaperArchiveCommitUnknown):
                        worker.run_once()
                self.assertEqual(saved.state.revision, 0)
                cohort = next((Path(folder) / "archive").iterdir())
                self.assertTrue((cohort / "response-01.json").exists())
                self.assertFalse((cohort / "receipt.json").exists())
                count = len(provider.urls)
                with self.assertRaises(PaperArchiveCommitUnknown):
                    worker.run_once()
                self.assertEqual(len(provider.urls), count)
            finally:
                publisher.close()
                saved.close()

    def test_gap_stale_funding_and_legacy_unbound_runtime_stop_before_http(self):
        with TemporaryDirectory() as folder:
            saved, archive, publisher, worker, provider = configured(folder)
            try:
                opened(worker, provider)
                count = len(provider.urls)
                for now in (provider.target + timedelta(hours=2), END + timedelta(hours=3)):
                    provider.now = now
                    with self.subTest(now=now), self.assertRaisesRegex(ValueError, "reconciliation"):
                        worker.run_once()
                self.assertEqual(len(provider.urls), count)
                cursor = saved.source_checkpoint()[2]
                with self.assertRaisesRegex(ValueError, "bound source"):
                    saved.append("batch", batch=archive.load(cursor.market).paper_batch(
                        saved.state, previous=archive.load(cursor.market)), expected_revision=2,
                        at=saved.state.observed_at)
            finally:
                publisher.close()
                saved.close()
        with TemporaryDirectory() as folder:
            saved, _, publisher, worker, provider = configured(folder)
            try:
                saved.append("warmup", hours=frames(saved.state, range(130, 98, -2)),
                             expected_revision=0, at=NOW)
                before = saved.receipt
                with self.assertRaisesRegex(ValueError, "separate source migration"):
                    worker.run_once()
                self.assertEqual(provider.urls, [])
                self.assertEqual(saved.receipt, before)
            finally:
                publisher.close()
                saved.close()

    def test_command_predecessor_and_future_archive_knowledge_reject_atomically(self):
        with TemporaryDirectory() as folder:
            saved, archive, publisher, worker, provider = configured(folder)
            try:
                opened(worker, provider)
                cursor = saved.source_checkpoint()[2]
                provider.now += timedelta(seconds=1)
                ref, value = archive.market(start=END - H1, end=END,
                                             funding_start=saved.state.signal.as_of)
                batch = value.paper_batch(saved.state, previous=archive.load(cursor.market))
                before = (Path(folder) / "paper.jsonl").read_bytes()
                for source, prior, at in ((ref, None, provider.now),
                                         (replace(ref, collected_at=provider.now + H1), cursor.market, provider.now)):
                    with self.subTest(prior=prior), self.assertRaises(ValueError):
                        saved.append("source_batch", batch=batch, source=source, prior=prior,
                                     expected_revision=2, at=at)
                self.assertEqual((Path(folder) / "paper.jsonl").read_bytes(), before)
            finally:
                publisher.close()
                saved.close()

    def test_launcher_disabled_and_unbounded_config_stop_without_http_or_journal_read(self):
        args = ["--journal", "/invalid/journal", "--config-digest", "a" * 64,
                "--archive-root", "/invalid/archive", "--status-root", "/invalid/status",
                "--tenant-id", "00000000-0000-0000-0000-000000000001",
                "--account-id", "00000000-0000-0000-0000-000000000002"]
        with patch.dict(os.environ, {}, clear=True), patch.object(FuturesPaperJournal, "restore") as restore:
            with self.assertRaisesRegex(SystemExit, "disabled"):
                main(args)
            restore.assert_not_called()
        with patch.dict(os.environ, {"FUTURES_PAPER_WORKER_ENABLED": "1"}):
            with self.assertRaisesRegex(SystemExit, "bounded"):
                main([*args, "--cycles", "101"])

    def test_bounded_launcher_restores_trusted_genesis_and_published_cursor_between_invocations(self):
        genesis = initial()
        tenant, account = ("00000000-0000-0000-0000-000000000001",
                           "00000000-0000-0000-0000-000000000002")
        plan = replace(genesis.config.profile.plan, tenant_id=tenant, account_id=account)
        profile = replace(genesis.config.profile, plan=plan)
        marks = genesis.signal.trade_prices
        economic = start_capital_research(plan, marks, AT, "launcher-fixture-genesis")
        genesis = start_paper(replace(genesis.config, profile=profile),
                              start_capital_signals(profile, economic, marks))
        with TemporaryDirectory() as folder:
            saved, archive, publisher, _, provider = configured(folder, genesis)
            saved.close()
            publisher.close()
            args = ["--journal", str(Path(folder) / "paper.jsonl"),
                    "--config-digest", genesis.config.config_digest,
                    "--archive-root", str(Path(folder) / "archive"),
                    "--status-root", str(Path(folder) / "status"),
                    "--tenant-id", tenant, "--account-id", account]
            with patch.dict(os.environ, {"FUTURES_PAPER_WORKER_ENABLED": "1"}), \
                    patch("investalo_workers.futures_paper_main.signal.signal"), \
                    patch("investalo_workers.futures_paper_main.FuturesPaperArchive", return_value=archive), \
                    patch("investalo_workers.futures_paper_main.FuturesAssetPublisher",
                          side_effect=lambda root, journal: FuturesAssetPublisher(
                              root, journal, clock=lambda: provider.now)), \
                    patch("investalo_workers.futures_paper_main.FuturesSourceWorker",
                          side_effect=lambda journal, archive, pub: FuturesSourceWorker(
                              journal, archive, pub, clock=lambda: provider.now)), \
                    patch("builtins.print") as output:
                main(args)
                provider.now += timedelta(seconds=1)
                main(args)
                self.assertEqual(output.call_count, 2)
                self.assertIn("outcome=quotes revision=2 entries=3", output.call_args.args[0])
            published = FuturesAssetReader(Path(folder) / "status").publication(tenant, account)
            with FuturesPaperJournal.restore(
                    Path(folder) / "paper.jsonl", config_digest=genesis.config.config_digest,
                    minimum_receipt=published.journal_receipt) as restored:
                self.assertEqual(restored.state.revision, 2)
                self.assertEqual(sum(bool(b.quantity) for b in restored.state.signal.economic.ledger.baskets), 3)
                self.assertIsNotNone(restored.source_checkpoint()[2].market)
                self.assertEqual(len(provider.urls), 50)

    def test_stop_guard_after_native_response_prevents_archive_receipt_and_journal_commit(self):
        with TemporaryDirectory() as folder:
            saved, _, publisher, worker, provider = configured(folder)
            try:
                def stopping():
                    if provider.urls:
                        raise RuntimeError("shutdown requested")

                with self.assertRaisesRegex(RuntimeError, "shutdown"):
                    worker.run_once(guard=stopping)
                self.assertEqual(len(provider.urls), 1)
                self.assertEqual(saved.state.revision, 0)
                cohort = next((Path(folder) / "archive").iterdir())
                self.assertFalse((cohort / "receipt.json").exists())
                self.assertFalse((cohort / "response-01.json").exists())
            finally:
                publisher.close()
                saved.close()


def _failed_publish(original, failure, arguments):
    with patch("investalo_trading.futures_paper_status.os.fsync", side_effect=failure):
        return original(**arguments)
