"""Own explicit Paper capital, latest planning and guarded real file commits."""
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import os

from investalo_trading.futures_capital_research import start_capital_research
from investalo_trading.futures_capital_signals import start_capital_signals
from investalo_trading.futures_paper import start_paper
from investalo_trading.futures_paper_account import PaperAccountBinding, PaperSettingsEvidence
from investalo_trading.futures_paper_journal import FuturesPaperJournal
from investalo_trading.futures_paper_status import FuturesAssetReader
from investalo_trading.futures_replay_journal import JournalCommitUnknown
from investalo_workers.futures_account_worker import FuturesAccountWorker
from investalo_workers.futures_paper_bootstrap import PaperBootstrapSpec, save_spec, load_spec, initialize_paper
from test_futures_source_worker import configured
from test_futures_paper_feed import initial, AT

TENANT = "00000000-0000-0000-0000-000000000001"
ACCOUNT = "00000000-0000-0000-0000-000000000002"
USER = "00000000-0000-0000-0000-000000000003"
BINDING = PaperAccountBinding(TENANT, ACCOUNT, USER, "https://paper.invalid", "own-fixture", 0, AT)


def own_genesis(tenant=TENANT, account=ACCOUNT):
    old = initial()
    plan = replace(old.config.profile.plan, tenant_id=tenant, account_id=account)
    profile = replace(old.config.profile, plan=plan)
    marks = old.signal.trade_prices
    economic = start_capital_research(plan, marks, AT, "own-allocation-fixture")
    return start_paper(replace(old.config, profile=profile), start_capital_signals(profile, economic, marks))


def evidence(provider, revision=0, limit=5):
    return PaperSettingsEvidence(TENANT, ACCOUNT, BINDING.binding_digest, revision, limit, provider.now)


class FuturesAccountWorkerTests(unittest.TestCase):
    def test_private_allocation_roundtrip_hash_scope_permissions_and_create_only(self):
        spec = PaperBootstrapSpec(BINDING, own_genesis().config)
        with TemporaryDirectory() as folder:
            path = Path(folder) / "allocation.json"
            self.assertEqual(save_spec(path, spec), spec.spec_digest)
            self.assertEqual(load_spec(path, spec.spec_digest), spec)
            with self.assertRaises(FileExistsError):
                save_spec(path, spec)
            with self.assertRaises(ValueError):
                load_spec(path, "a" * 64)
            path.chmod(0o644)
            with self.assertRaises(ValueError):
                load_spec(path, spec.spec_digest)
        with self.assertRaises(ValueError):
            PaperBootstrapSpec(replace(BINDING, account_id=USER), own_genesis().config)

    def test_initialization_uses_own_capital_native_warmup_and_never_reinitializes(self):
        with TemporaryDirectory() as folder:
            # Obtain private roots and the synthetic native HTTP provider.
            saved, archive, publisher, _, provider = configured(folder, own_genesis())
            publisher.close()
            saved.close()
            target = Path(folder) / "allocated.jsonl"
            spec = PaperBootstrapSpec(BINDING, own_genesis().config)
            receipt = initialize_paper(target, spec, archive, Path(folder) / "status",
                                      lambda: evidence(provider, 1, 3), lambda: provider.now)
            self.assertEqual(receipt["sequence"], 1)
            self.assertEqual(len(provider.urls), 25)
            with FuturesPaperJournal.restore(target, config_digest=spec.config.config_digest,
                                              minimum_receipt=receipt) as restored:
                self.assertEqual(restored.state.signal.economic.ledger.unposted_cash, 10000)
                self.assertTrue(restored.state.warmed)
                self.assertFalse(any(b.quantity for b in restored.state.signal.economic.ledger.baskets))
                self.assertEqual(restored.state.config.profile.plan.initial_slots, 3)
                self.assertIsNotNone(restored.source_checkpoint()[2].warmup)
            with self.assertRaisesRegex(ValueError, "never reinitialization"):
                initialize_paper(target, spec, archive, Path(folder) / "status",
                                 lambda: evidence(provider, 1, 3), lambda: provider.now)
            with self.assertRaisesRegex(ValueError, "never a second allocation"):
                initialize_paper(Path(folder) / "second.jsonl", spec, archive, Path(folder) / "status",
                                 lambda: evidence(provider, 1, 3), lambda: provider.now)
            self.assertFalse((Path(folder) / "second.jsonl").exists())
            self.assertEqual(len(provider.urls), 25)

    def test_latest_saved_revision_applies_without_inventing_intermediate_values_and_restores(self):
        with TemporaryDirectory() as folder:
            saved, archive, publisher, source, provider = configured(folder, own_genesis())
            latest = [1, 3]
            worker = FuturesAccountWorker(source, lambda: evidence(provider, *latest))
            try:
                self.assertEqual(worker.run_once().outcome, "warmed")
                provider.now += timedelta(seconds=1)
                self.assertEqual(worker.run_once().entries, 3)
                before = saved.state
                latest[:] = [4, 7]  # Only revision4 was actually read; no fake2/3 settings.
                provider.now += timedelta(seconds=1)
                self.assertEqual(worker.run_once().entries, 0)
                after = saved.state
                self.assertEqual((after.settings_revision, after.config.profile.plan.configured_limit), (4, 7))
                self.assertEqual(after.config.profile.plan.simultaneous_limit, 3)
                self.assertEqual(after.config.profile.plan.budgets, before.config.profile.plan.budgets)
                self.assertEqual(after.signal.economic.stages, before.signal.economic.stages)
                self.assertEqual(after.signal.economic.ledger.baskets, tuple(
                    replace(b, marked_at=a.marked_at) for a, b in zip(
                        after.signal.economic.ledger.baskets, before.signal.economic.ledger.baskets, strict=True)))
                receipt = saved.receipt
                published = FuturesAssetReader(Path(folder) / "status").publication(TENANT, ACCOUNT)
                self.assertEqual(published.journal_receipt, receipt)
            finally:
                publisher.close()
                saved.close()
            with FuturesPaperJournal.restore(Path(folder) / "paper.jsonl",
                    config_digest=own_genesis().config.config_digest, minimum_receipt=receipt) as restored:
                self.assertEqual(restored.state, after)
                self.assertEqual(restored.source_checkpoint()[2].market, source.journal._source_cursor.market)

    def test_account_or_setting_change_during_capture_stops_before_financial_commit(self):
        with TemporaryDirectory() as folder:
            saved, _, publisher, source, provider = configured(folder, own_genesis())
            latest = [1, 3]
            worker = FuturesAccountWorker(source, lambda: evidence(provider, *latest))
            try:
                worker.run_once()
                worker.run_once()  # Apply saved revision1 and first quotes.
                before, count = saved.receipt, len(provider.urls)
                original = provider.fetch

                def changed(url):
                    result = original(url)
                    latest[:] = [2, 4]
                    return result

                provider.now += timedelta(seconds=1)
                changed_archive = replace(source.archive, market_fetch=changed)
                commits = []
                changed_source = replace(source, archive=changed_archive,
                                         commit_guard=lambda: commits.append(True))
                with self.assertRaisesRegex(ValueError, "changed during"):
                    FuturesAccountWorker(changed_source, lambda: evidence(provider, *latest)).run_once()
                self.assertEqual(saved.receipt, before)
                self.assertEqual(len(provider.urls), count + 25)
                self.assertEqual(commits, [True])
            finally:
                publisher.close()
                saved.close()

    def test_foreign_stale_regressed_or_same_revision_different_settings_reject_before_http(self):
        with TemporaryDirectory() as folder:
            saved, _, publisher, source, provider = configured(folder, own_genesis())
            try:
                worker = FuturesAccountWorker(source, lambda: evidence(provider, 2, 3))
                worker.run_once()
                provider.now += timedelta(seconds=1)
                worker.run_once()
                before, count = saved.receipt, len(provider.urls)
                current = evidence(provider, 2, 3)
                for value in (replace(current, tenant_id=USER),
                              replace(current, observed_at=provider.now - timedelta(seconds=31)),
                              replace(current, observed_at=provider.now + timedelta(seconds=1)),
                              replace(current, settings_revision=1),
                              replace(current, basket_limit=7)):
                    with self.subTest(value=value), self.assertRaises(ValueError):
                        FuturesAccountWorker(source, lambda: value).run_once()
                self.assertEqual((saved.receipt, len(provider.urls)), (before, count))
            finally:
                publisher.close()
                saved.close()

    def test_unknown_settings_write_stops_source_and_full_readback_acknowledges_latest_once(self):
        with TemporaryDirectory() as folder:
            saved, archive, publisher, source, provider = configured(folder, own_genesis())
            try:
                FuturesAccountWorker(source, lambda: evidence(provider, 1, 3)).run_once()
                count = len(provider.urls)
                with patch("investalo_trading.futures_capital_journal.os.fsync",
                           side_effect=OSError("settings ack lost")), self.assertRaises(JournalCommitUnknown):
                    FuturesAccountWorker(source, lambda: evidence(provider, 5, 7)).run_once()
                self.assertEqual(len(provider.urls), count)
                published = FuturesAssetReader(Path(folder) / "status").publication(TENANT, ACCOUNT)
            finally:
                publisher.close()
                saved.close()
            with FuturesPaperJournal.restore(Path(folder) / "paper.jsonl",
                    config_digest=own_genesis().config.config_digest,
                    minimum_receipt=published.journal_receipt) as restored:
                self.assertEqual(restored.state.settings_revision, 5)
                self.assertEqual(restored.state.config.profile.plan.configured_limit, 7)
                self.assertEqual(restored.receipt["sequence"], 2)

    def test_invalid_initial_planning_rejects_before_provider_or_journal_creation(self):
        with TemporaryDirectory() as folder:
            saved, archive, publisher, _, provider = configured(folder, own_genesis())
            publisher.close()
            saved.close()
            target = Path(folder) / "new.jsonl"
            with self.assertRaises(ValueError):
                initialize_paper(target, PaperBootstrapSpec(BINDING, own_genesis().config), archive,
                                 Path(folder) / "status", lambda: evidence(provider), lambda: provider.now)
            self.assertFalse(target.exists())
            self.assertEqual(provider.urls, [])

    def test_initialization_selects_midnight_genesis_when_trading_start_is_nineteen_utc(self):
        with TemporaryDirectory() as folder:
            saved, archive, publisher, _, provider = configured(folder, own_genesis())
            publisher.close()
            saved.close()
            provider.now = AT + timedelta(hours=19, seconds=1)
            config = replace(own_genesis().config, trading_from=AT + timedelta(hours=19))
            spec = PaperBootstrapSpec(BINDING, config)
            target = Path(folder) / "evening.jsonl"
            receipt = initialize_paper(target, spec, archive, Path(folder) / "status",
                                      lambda: evidence(provider, 1, 3), lambda: provider.now)
            with FuturesPaperJournal.restore(target, config_digest=config.config_digest,
                                              minimum_receipt=receipt) as restored:
                self.assertEqual(restored.state.signal.last_hour.close_time, config.trading_from)
                self.assertEqual(restored.state.signal.economic.ledger.day_started_at, AT)
                self.assertFalse(restored.state.signal.economic.stages)

    def test_bound_launcher_disabled_or_unbounded_stops_before_spec_and_database_access(self):
        from investalo_workers.futures_account_main import main
        args = ["--journal", "/invalid/journal", "--spec", "/invalid/spec",
                "--spec-digest", "a" * 64, "--archive-root", "/invalid/archive",
                "--status-root", "/invalid/status"]
        with patch("investalo_workers.futures_account_main.load_spec") as load:
            with patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(SystemExit, "disabled"):
                main(args)
            with patch.dict(os.environ, {"FUTURES_PAPER_ACCOUNT_WORKER_ENABLED": "1"}), \
                    self.assertRaisesRegex(SystemExit, "bounded"):
                main([*args, "--cycles", "101"])
            load.assert_not_called()
