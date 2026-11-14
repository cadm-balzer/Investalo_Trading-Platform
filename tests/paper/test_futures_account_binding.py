"""Actual runtime LOGIN/RLS and existing013; private delegation, no broker orders."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import os

import pytest

from investalo_trading.futures_paper_account import PaperAccountBinding
from investalo_trading.futures_paper_journal import FuturesPaperJournal
from investalo_trading.futures_paper_status import FuturesAssetPublisher, FuturesAssetReader
from investalo_workers.futures_account_reader import FuturesPaperAccountReader, PaperAccountRejected
from investalo_workers.futures_account_worker import FuturesAccountWorker
from investalo_workers.futures_paper_bootstrap import PaperBootstrapSpec, initialize_paper, save_spec
from investalo_workers.futures_source_worker import FuturesSourceWorker
from test_postgres_store import context
from test_futures_settings_postgres import actor, request

AT = datetime(2026, 11, 1, tzinfo=timezone.utc)


def configuration(folder, actor):
    # Pytest adds the marketdata fixture path later during collection.
    from test_futures_account_worker import own_genesis
    from test_futures_source_worker import configured
    return configured(folder, own_genesis(str(actor["tenant"]), str(actor["account"])))


def reader(actor, clock=lambda: AT + timedelta(hours=16, seconds=1)):
    binding = PaperAccountBinding(str(actor["tenant"]), str(actor["account"]), str(actor["user"]),
                                 actor["settings"].oidc_issuer, actor["subject"], 0, AT)
    return FuturesPaperAccountReader(binding, actor["settings"].connection_parameters(), clock)


def test_restricted_own_reader_uses_default_and_committed_settings_without_nonce_or_audit_writes(actor):
    read = reader(actor)
    assert (read().settings_revision, read().basket_limit) == (0, 5)
    assert request(actor, {"expected_revision": 0, "basket_limit": 3}).status_code == 200
    with actor["admin"]() as db:
        before = db.execute("SELECT count(*) n FROM platform.request_nonces WHERE user_id=%s",
                            (actor["user"],)).fetchone()["n"]
    current = read()
    assert (current.settings_revision, current.basket_limit) == (1, 3)
    assert current.binding_digest == read.binding.binding_digest
    with actor["admin"]() as db:
        assert db.execute("SELECT count(*) n FROM platform.request_nonces WHERE user_id=%s",
                          (actor["user"],)).fetchone()["n"] == before
        assert db.execute("SELECT count(*) n FROM platform.futures_paper_settings_audit WHERE tenant_id=%s",
                          (actor["tenant"],)).fetchone()["n"] == 1


def test_foreign_account_user_scope_and_elevated_login_fail_closed(actor):
    read = reader(actor)
    for binding in (replace(read.binding, account_id=str(actor["foreign_account"])),
                    replace(read.binding, tenant_id=str(actor["foreign"])),
                    replace(read.binding, user_id=str(actor["foreign_account"]))):
        with pytest.raises(PaperAccountRejected):
            replace(read, binding=binding)()
    with actor["admin"]() as db:
        # Same connection parameters, actual admin LOGIN must never pass worker role checks.
        elevated = {**read.connection_parameters, "user": db.info.user, "password": db.info.password}
    with pytest.raises(PaperAccountRejected):
        replace(read, connection_parameters=elevated)()


@pytest.mark.parametrize("sql", [
    "UPDATE platform.memberships SET active=false WHERE tenant_id=%s",
    "UPDATE platform.memberships SET role='viewer' WHERE tenant_id=%s",
    "UPDATE platform.accounts SET status='paused' WHERE tenant_id=%s",
    "UPDATE platform.accounts SET mode='read_only' WHERE tenant_id=%s",
    "UPDATE platform.accounts SET currency='EUR' WHERE tenant_id=%s",
])
def test_revoked_membership_or_ineligible_account_stops_before_native_http(actor, sql):
    assert request(actor, {"expected_revision": 0, "basket_limit": 3}).status_code == 200
    with TemporaryDirectory() as folder:
        saved, _, publisher, source, provider = configuration(folder, actor)
        try:
            worker = FuturesAccountWorker(source, reader(actor, lambda: provider.now))
            worker.run_once()
            before, count = saved.receipt, len(provider.urls)
            with actor["admin"]() as db:
                db.execute(sql, (actor["tenant"],))
            with pytest.raises(PaperAccountRejected):
                worker.run_once()
            assert (saved.receipt, len(provider.urls)) == (before, count)
        finally:
            publisher.close()
            saved.close()


@pytest.mark.parametrize("change", ["epoch", "inactive", "reauth"])
def test_delegated_actor_revocation_is_rechecked_on_each_read(actor, change):
    read = reader(actor)
    read()
    with actor["admin"]() as db:
        statement = {
            "epoch": "UPDATE platform.users SET auth_epoch=auth_epoch+1 WHERE id=%s",
            "inactive": "UPDATE platform.users SET active=false WHERE id=%s",
            "reauth": "UPDATE platform.users SET reauth_after=now() WHERE id=%s",
        }[change]
        db.execute(statement, (actor["user"],))
    with pytest.raises(PaperAccountRejected):
        read()


def test_actual_own_db_planning_initialization_quotes_lower_ceiling_and_complete_restart(actor):
    assert request(actor, {"expected_revision": 0, "basket_limit": 3}).status_code == 200
    with TemporaryDirectory() as folder:
        old, archive, publisher, _, provider = configuration(folder, actor)
        config = old.state.config
        old.close()
        publisher.close()
        read = reader(actor, lambda: provider.now)
        spec = PaperBootstrapSpec(read.binding, config)
        path, status = Path(folder) / "own.jsonl", Path(folder) / "status"
        initialize_paper(path, spec, archive, status, read, lambda: provider.now)
        published = FuturesAssetReader(status).publication(str(actor["tenant"]), str(actor["account"]))
        with FuturesPaperJournal.restore(path, config_digest=spec.config.config_digest,
                                         minimum_receipt=published.journal_receipt) as saved:
            with FuturesAssetPublisher(status, saved, clock=lambda: provider.now) as pub:
                worker = FuturesAccountWorker(FuturesSourceWorker(saved, archive, pub, lambda: provider.now), read)
                provider.now += timedelta(seconds=1)
                assert worker.run_once().entries == 3
                before = saved.state
                assert request(actor, {"expected_revision": 1, "basket_limit": 7}).status_code == 200
                assert request(actor, {"expected_revision": 2, "basket_limit": 4}).status_code == 200
                provider.now += timedelta(seconds=1)
                assert worker.run_once().entries == 0
                assert saved.state.settings_revision == 3
                assert saved.state.config.profile.plan.configured_limit == 4
                assert saved.state.config.profile.plan.simultaneous_limit == 3
                assert saved.state.config.profile.plan.budgets == before.config.profile.plan.budgets
                assert saved.state.signal.economic.stages == before.signal.economic.stages
                receipt = saved.receipt
        with FuturesPaperJournal.restore(path, config_digest=spec.config.config_digest,
                                         minimum_receipt=receipt) as restored:
            assert restored.state.settings_revision == 3
            assert len(restored.state.signal.economic.stages) == 3


def test_bound_cli_uses_actual_rls_settings_and_trusted_allocation_on_init_and_restart(actor):
    from investalo_workers.futures_account_main import main
    assert request(actor, {"expected_revision": 0, "basket_limit": 3}).status_code == 200
    with TemporaryDirectory() as folder:
        old, archive, publisher, _, provider = configuration(folder, actor)
        spec = PaperBootstrapSpec(reader(actor).binding, old.state.config)
        old.close()
        publisher.close()
        root = Path(folder)
        path = root / "cli.jsonl"
        sha = save_spec(root / "allocation.json", spec)
        args = ["--journal", str(path), "--spec", str(root / "allocation.json"),
                "--spec-digest", sha, "--archive-root", str(root / "archive"),
                "--status-root", str(root / "status")]
        with patch.dict(os.environ, {"FUTURES_PAPER_ACCOUNT_WORKER_ENABLED": "1"}), \
                patch("investalo_workers.futures_account_main.signal.signal"), \
                patch("investalo_workers.futures_account_main.datetime") as clock, \
                patch("investalo_workers.futures_account_main.FuturesPaperArchive", return_value=archive), \
                patch("builtins.print") as output:
            clock.now.side_effect = lambda _: provider.now
            main([*args, "--initialize"])
            assert "entries=3" in output.call_args.args[0]
            assert request(actor, {"expected_revision": 1, "basket_limit": 7}).status_code == 200
            provider.now += timedelta(seconds=1)
            main(args)
            assert "entries=0" in output.call_args.args[0]
        publication = FuturesAssetReader(root / "status").publication(
            str(actor["tenant"]), str(actor["account"]))
        with FuturesPaperJournal.restore(path, config_digest=spec.config.config_digest,
                                         minimum_receipt=publication.journal_receipt) as restored:
            assert restored.state.settings_revision == 2
            assert restored.state.config.profile.plan.initial_slots == 3
            assert restored.state.config.profile.plan.configured_limit == 7
            assert restored.state.config.profile.plan.simultaneous_limit == 3
            assert len(restored.state.signal.economic.stages) == 3


def test_actual_account_pause_during_native_capture_rejects_quote_commit(actor):
    assert request(actor, {"expected_revision": 0, "basket_limit": 3}).status_code == 200
    with TemporaryDirectory() as folder:
        saved, _, publisher, source, provider = configuration(folder, actor)
        try:
            read = reader(actor, lambda: provider.now)
            worker = FuturesAccountWorker(source, read)
            worker.run_once()
            provider.now += timedelta(seconds=1)
            worker.run_once()
            before, count = saved.receipt, len(provider.urls)
            native_fetch = provider.fetch
            changed = []

            def pausing(url):
                response = native_fetch(url)
                if not changed:
                    with actor["admin"]() as db:
                        db.execute("UPDATE platform.accounts SET status='paused' WHERE tenant_id=%s AND id=%s",
                                   (actor["tenant"], actor["account"]))
                    changed.append(True)
                return response

            provider.now += timedelta(seconds=1)
            changed_source = replace(source, archive=replace(source.archive, market_fetch=pausing))
            with pytest.raises(PaperAccountRejected):
                FuturesAccountWorker(changed_source, read).run_once()
            assert saved.receipt == before
            assert len(provider.urls) == count + 25
        finally:
            publisher.close()
            saved.close()
