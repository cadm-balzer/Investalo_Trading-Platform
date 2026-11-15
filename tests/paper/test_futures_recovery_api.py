"""Normal API/executor with genuine restricted PostgreSQL and durable own journal."""
import base64
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
import hashlib
import hmac
import json
import os
import time
from uuid import uuid4
from unittest.mock import patch

from fastapi.testclient import TestClient
import pytest
from investalo_api import main
from investalo_trading.futures_paper_journal import FuturesPaperJournal
from investalo_trading.futures_paper_status import FuturesAssetPublisher, FuturesAssetReader
from investalo_workers.futures_paper_bootstrap import PaperBootstrapSpec, save_spec
from investalo_workers.futures_recovery_executor import register_recovery, FuturesPaperRecoveryExecutor
from test_postgres_store import context
from test_futures_settings_postgres import actor, request as planning
from test_futures_account_binding import reader

PATH = "/v1/futures-recovery"


def call(a, client, body=None, *, tenant=None):
    raw = b"" if body is None else json.dumps(body).encode()
    now = int(time.time())
    claims = dict(iss="investalo-bff", aud="investalo-api", sub=a["subject"],
        oidc_iss=a["settings"].oidc_issuer, iat=now, exp=now+30, oidc_auth_time=now,
        jti=str(uuid4()), tenant_id=str(tenant or a["tenant"]), auth_epoch=0,
        htm="GET" if body is None else "POST", htu=PATH, body_sha256=hashlib.sha256(raw).hexdigest())
    encode = lambda v: base64.urlsafe_b64encode(json.dumps(v).encode()).rstrip(b"=").decode()
    prefix = encode({"alg": "HS256", "typ": "JWT"}) + "." + encode(claims)
    sig = base64.urlsafe_b64encode(hmac.digest(a["settings"].internal_key.encode(),
        prefix.encode(), "sha256")).rstrip(b"=").decode()
    return client.request(claims["htm"], PATH, content=raw,
        headers={"Authorization": "Bearer " + prefix + "." + sig, "Content-Type": "application/json"})


@pytest.fixture
def recovery(actor, tmp_path):
    from test_futures_paper_recovery import prepared, recovery_request
    assert planning(actor, {"expected_revision": 0, "basket_limit": 3}).status_code == 200
    for name in ("status", "registry"):
        (tmp_path / name).mkdir(mode=0o700)
    saved = prepared(tmp_path / "paper.jsonl", str(actor["tenant"]), str(actor["account"]))
    at = [saved.state.observed_at]
    clock = lambda: at[0]
    bound = reader(actor, clock)
    spec = PaperBootstrapSpec(bound.binding, saved.state.config)
    sha = save_spec(tmp_path / "allocation.json", spec)
    register_recovery(tmp_path / "registry", tmp_path / "allocation.json", sha, tmp_path / "paper.jsonl")
    saved.append("account_settings", evidence=bound(), expected_revision=saved.state.revision, at=clock())
    before, receipt = saved.checkpoint()
    with FuturesAssetPublisher(tmp_path / "status", saved, clock=clock, recovery_enabled=True) as pub:
        pub.publish(expected_revision=before.revision)
    saved.close()
    settings = replace(actor["settings"], futures_recovery_preview=True,
        futures_recovery_root=str(tmp_path / "registry"), futures_paper_status_root=str(tmp_path / "status"))
    client = TestClient(main.create_app(settings))
    assert type(client.app.state.futures_recovery_executor) is FuturesPaperRecoveryExecutor
    client.app.state.futures_recovery_executor = replace(client.app.state.futures_recovery_executor, clock=clock)
    client.app.state.futures_paper_state_reader = FuturesAssetReader(tmp_path / "status", clock)
    req = recovery_request(before, str(actor["user"]))
    body = dict(account_id=req.account_id, symbol=req.symbol.removeprefix("BITGET:"), cycle=req.cycle,
        revision=req.expected_revision, state_digest=req.state_digest, event_id=req.event_id, consent=True)
    with patch("investalo_api.futures_paper_recovery.datetime") as api_clock:
        api_clock.now.side_effect = lambda _: clock()
        yield dict(actor=actor, client=client, root=tmp_path, state=before, receipt=receipt,
                   body=body, clock=clock, at=at, settings=settings)


def restored(r):
    return FuturesPaperJournal.restore(r["root"] / "paper.jsonl",
        config_digest=r["state"].config.config_digest, minimum_receipt=r["receipt"])


def test_actual_recovery_api_commits_restores_and_preserves_all_losses(recovery):
    r, a = recovery, recovery["actor"]
    view = call(a, r["client"])
    assert view.status_code == 200
    assert view.headers["cache-control"] == "no-store"
    card = view.json()["assets"][0]
    assert card["allowed"] and card["leverage"] == "2" and float(card["net_loss"]) > 0
    assert r["root"].as_posix() not in view.text
    assert "journal_receipt" not in view.text and "actor_id" not in view.text
    before = r["state"].signal.economic.ledger
    response = call(a, r["client"], r["body"])
    assert response.status_code == 200 and response.json()["assets"] == []
    with restored(r) as saved:
        after = saved.state.signal.economic.ledger
        assert saved.state.revision == r["state"].revision + 1
        assert (after.unposted_cash, after.realized_net_pnl, after.day_start_equity, after.closed_baskets) == (
            before.unposted_cash, before.realized_net_pnl, before.day_start_equity, before.closed_baskets)
    assert call(a, r["client"], r["body"]).status_code == 409
    assert call(a, r["client"]).json()["assets"] == []


def test_busy_feed_writer_and_concurrent_actions_do_not_double_release(recovery):
    r, a = recovery, recovery["actor"]
    with restored(r) as saved:
        assert call(a, r["client"], r["body"]).status_code == 503
        assert saved.receipt == r["receipt"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: call(a, r["client"], r["body"]).status_code, range(2)))
    assert results.count(200) == 1 and all(n in (200, 409, 503) for n in results)
    with restored(r) as saved:
        assert saved.state.revision == r["state"].revision + 1


def test_actual_reader_rechecks_permission_and_settings_before_manual_append(recovery):
    r, a = recovery, recovery["actor"]
    actual = reader(a, r["clock"])
    def changed():
        value = actual()
        with a["admin"]() as db:
            db.execute("UPDATE platform.accounts SET status='paused' WHERE id=%s", (a["account"],))
        return value
    with patch("investalo_workers.futures_recovery_executor.FuturesPaperAccountReader", return_value=changed):
        assert call(a, r["client"], r["body"]).status_code == 503
    with restored(r) as saved:
        assert saved.receipt == r["receipt"]
    view = call(a, r["client"])
    assert not view.json()["assets"][0]["allowed"]
    assert "account_blocked" in view.json()["assets"][0]["reasons"]


def test_real_clock_advancement_is_not_a_fictitious_settings_change(recovery):
    r, a = recovery, recovery["actor"]
    def clock():
        r["at"][0] += timedelta(milliseconds=1)
        return r["at"][0]
    r["client"].app.state.futures_recovery_executor = replace(
        r["client"].app.state.futures_recovery_executor, clock=clock)
    assert call(a, r["client"], r["body"]).status_code == 200


def test_scope_stale_consent_and_current_role_cannot_release(recovery):
    r, a = recovery, recovery["actor"]
    assert call(a, r["client"], tenant=a["foreign"]).status_code == 403
    assert call(a, r["client"], {**r["body"], "account_id": str(a["foreign_account"])}).status_code == 404
    for changes in ({"consent": False}, {"consent": 1}, {"revision": True}, {"cash": "100000"},
                    {"actor_id": str(a["user"])}, {"orders_reconciled": True}):
        assert call(a, r["client"], {**r["body"], **changes}).status_code == 422
    r["at"][0] += timedelta(seconds=31)
    assert "reconciliation_stale" in call(a, r["client"]).json()["assets"][0]["reasons"]
    assert call(a, r["client"], r["body"]).status_code == 409
    with a["admin"]() as db:
        db.execute("UPDATE platform.memberships SET role='viewer' WHERE tenant_id=%s AND user_id=%s",
                   (a["tenant"], a["user"]))
    assert call(a, r["client"], r["body"]).status_code == 403
    with restored(r) as saved:
        assert saved.receipt == r["receipt"]


def test_missing_own_registration_and_pending_planning_remain_visible_blockers(recovery):
    r, a = recovery, recovery["actor"]
    r["client"].app.state.futures_recovery_executor = replace(
        r["client"].app.state.futures_recovery_executor, root=r["root"] / "status")
    view = call(a, r["client"])
    assert view.status_code == 200
    assert "runtime_unavailable" in view.json()["assets"][0]["reasons"]
    assert not view.json()["assets"][0]["allowed"]
    r["client"].app.state.futures_recovery_executor = FuturesPaperRecoveryExecutor(
        r["root"] / "registry", r["root"] / "status", r["settings"].connection_parameters(), r["clock"])
    assert planning(a, {"expected_revision": 1, "basket_limit": 7}).status_code == 200
    card = call(a, r["client"]).json()["assets"][0]
    assert "account_blocked" in card["reasons"] and not card["allowed"]
    assert call(a, r["client"], r["body"]).status_code == 409
    with restored(r) as saved:
        assert saved.receipt == r["receipt"]


def test_unknown_durable_append_needs_full_restore_then_publication_repair(recovery):
    r, a = recovery, recovery["actor"]
    with patch("os.fsync", side_effect=OSError("lost actual acknowledgement")):
        response = call(a, r["client"], r["body"])
    assert response.status_code == 503
    with restored(r) as saved:
        assert saved.state.revision == r["state"].revision + 1
        assert not saved.state.signal.economic.stopped
        with FuturesAssetPublisher(r["root"] / "status", saved, clock=r["clock"], recovery_enabled=True) as pub:
            pub.publish(expected_revision=saved.state.revision)
    assert call(a, r["client"]).json()["assets"] == []
    assert call(a, r["client"], r["body"]).status_code == 409


def test_recovery_routes_default_off_before_any_db_or_executor(actor):
    client = TestClient(main.create_app(actor["settings"], futures_recovery_executor=lambda _: 1/0))
    with patch.object(main, "transaction", side_effect=AssertionError("disabled DB")):
        assert call(actor, client).status_code == 404
        # Valid strict body, so the route's default-off gate is exercised.
        body = dict(account_id=str(actor["account"]), symbol="BTCUSDT", cycle=1, revision=0,
                    state_digest="a"*64, event_id=str(uuid4()), consent=True)
        assert call(actor, client, body).status_code == 404


def test_bound_launcher_explicit_opt_in_registers_original_own_allocation(actor, tmp_path):
    from investalo_workers.futures_account_main import main as launch
    from test_futures_account_binding import configuration
    assert planning(actor, {"expected_revision": 0, "basket_limit": 3}).status_code == 200
    old, archive, publisher, _, provider = configuration(tmp_path, actor)
    spec = PaperBootstrapSpec(reader(actor).binding, old.state.config)
    old.close()
    publisher.close()
    (tmp_path / "registry").mkdir(mode=0o700)
    sha = save_spec(tmp_path / "allocation.json", spec)
    args = ["--spec", str(tmp_path / "allocation.json"), "--spec-digest", sha,
            "--journal", str(tmp_path / "allocated.jsonl"), "--archive-root", str(tmp_path / "archive"),
            "--status-root", str(tmp_path / "status"), "--recovery-root", str(tmp_path / "registry"),
            "--initialize"]
    with patch.dict(os.environ, {"FUTURES_PAPER_ACCOUNT_WORKER_ENABLED": "1",
                                "FUTURES_PAPER_RECOVERY_ENABLED": "0"}):
        with pytest.raises(SystemExit):
            launch(args)
    assert not list((tmp_path / "registry").iterdir())
    with patch.dict(os.environ, {"FUTURES_PAPER_ACCOUNT_WORKER_ENABLED": "1",
                                "FUTURES_PAPER_RECOVERY_ENABLED": "1"}), \
            patch("investalo_workers.futures_account_main.signal.signal"), \
            patch("investalo_workers.futures_account_main.datetime") as clock, \
            patch("investalo_workers.futures_account_main.FuturesPaperArchive", return_value=archive), \
            patch("builtins.print"):
        clock.now.side_effect = lambda _: provider.now
        launch(args)
    pub = FuturesAssetReader(tmp_path / "status").publication(str(actor["tenant"]), str(actor["account"]))
    assert pub.recovery is not None and pub.recovery.rows == ()
    executor = FuturesPaperRecoveryExecutor(tmp_path / "registry", tmp_path / "status",
        actor["settings"].connection_parameters(), lambda: provider.now)
    assert executor.available(str(actor["tenant"]), str(actor["account"]), str(actor["user"]))
    assert not executor.available(str(actor["tenant"]), str(actor["account"]), str(uuid4()))
