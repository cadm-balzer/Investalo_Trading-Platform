"""Isolated real LOGIN/SQL/client tests; no broker, feed or public activation."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import os
from uuid import uuid4
from urllib.parse import parse_qs, urlsplit

import psycopg
from psycopg.rows import dict_row
import pytest

from investalo_api.settings import Settings, secret_file
from investalo_trading import Candle, PaperRunner, Quote
from investalo_workers.paper_store import (
    PaperCommitUnknown, PaperConflict, PaperStorageRejected, PaperStore, checksum,
)
from investalo_marketdata.paper_feed import BitgetPaperFeed, H4, boundary
from investalo_workers.paper_worker import PaperWorker, WARMUP_BARS
from fastapi.testclient import TestClient
from investalo_api.main import create_app
import base64
import hashlib
import hmac
import time

START = datetime(2026, 1, 1, tzinfo=timezone.utc)
D = Decimal


@pytest.fixture
def context():
    if not os.getenv("PAPER_TEST_PASSWORD_FILE"):
        pytest.skip("Requires isolated paper fixture LOGIN")
    settings = Settings.from_environment()
    assert settings.connection_parameters()["dbname"] == "investalo_credentials_checks"
    admin_params = {**settings.connection_parameters(),
                    "user": os.environ["API_TEST_ADMIN_USER"],
                    "password": secret_file("API_TEST_ADMIN_PASSWORD_FILE")}
    worker_params = {**settings.connection_parameters(), "user": "investalo_paper_tests",
                     "password": secret_file("PAPER_TEST_PASSWORD_FILE")}
    tenant, account, other, foreign, foreign_account = [uuid4() for _ in range(5)]
    admin = lambda: psycopg.connect(**admin_params, row_factory=dict_row)
    def worker(database=None):
        try:
            params = {**worker_params, **({"dbname": database} if database else {})}
            return psycopg.connect(**params, row_factory=dict_row)
        except psycopg.Error:
            # pytest must never render libpq's password-bearing conninfo frames.
            raise PaperStorageRejected("Isolated paper fixture LOGIN unavailable") from None
    with admin() as db:
        db.execute("INSERT INTO platform.tenants(id,name) VALUES(%s,'Paper fixture'),(%s,'Foreign paper fixture')",
                   (tenant, foreign))
        for t, a in ((tenant, account), (tenant, other), (foreign, foreign_account)):
            db.execute("INSERT INTO platform.accounts(tenant_id,id,name,broker,mode,currency,status)"
                       " VALUES(%s,%s,'Synthetic paper','bitget','paper','USDT','ready')", (t, a))
        db.execute("INSERT INTO platform.paper_role_bindings(database_role,tenant_id,account_id)"
                   " VALUES('investalo_paper_tests',%s,%s) ON CONFLICT(database_role) DO UPDATE"
                   " SET tenant_id=excluded.tenant_id,account_id=excluded.account_id,active=true", (tenant, account))
    runner = PaperRunner(str(tenant), str(account))
    return dict(admin=admin, worker=worker, tenant=tenant, account=account, other=other,
                foreign=foreign, foreign_account=foreign_account, runner=runner,
                store=PaperStore(runner, worker, "investalo_paper_tests"))


def initial(context):
    return context["store"].initialize(context["runner"].start(START))


def update(context, old, price="100"):
    at = old.observed_at + timedelta(seconds=1)
    return context["runner"].quote(old, Quote("BTCUSDT", at, D(price), D(price)), now=at)


def journal(context):
    with context["admin"]() as db:
        return db.execute("SELECT * FROM platform.paper_journal WHERE tenant_id=%s AND account_id=%s"
                          " ORDER BY revision", (context["tenant"], context["account"])).fetchall()


def raw_commit(context, old, after, previous=None):
    payload = context["runner"].dump(after)
    with context["worker"]() as db:
        return db.execute("SELECT platform.paper_commit(%s,%s,%s,%s)",
                          (old.revision, previous or checksum(context["runner"].dump(old)),
                           payload, checksum(payload))).fetchone()


def test_initialize_read_and_atomic_journal(context):
    assert context["store"].read() is None
    old = initial(context)
    assert context["store"].initialize(old) == old
    step = update(context, old)
    assert context["store"].commit(old, step) == step.checkpoint
    assert context["store"].read() == step.checkpoint
    rows = journal(context)
    assert len(rows) == 1 and rows[0]["revision"] == 1
    assert rows[0]["previous_checksum"] == checksum(context["runner"].dump(old))
    assert rows[0]["checkpoint_checksum"] == checksum(context["runner"].dump(step.checkpoint))


def test_exact_commit_duplicate_and_input_duplicate_create_no_extra_rows(context):
    old = initial(context)
    step = update(context, old)
    context["store"].commit(old, step)
    assert context["store"].commit(old, step) == step.checkpoint
    at = step.checkpoint.observed_at
    duplicate = context["runner"].quote(step.checkpoint, step.checkpoint.state.quote("BTCUSDT"), now=at)
    assert context["store"].commit(step.checkpoint, duplicate) == step.checkpoint
    assert len(journal(context)) == 1


def test_stale_revision_and_forged_previous_state_conflict(context):
    old = initial(context)
    step = update(context, old)
    with pytest.raises(psycopg.errors.SerializationFailure):
        raw_commit(context, old, step.checkpoint, previous="0"*64)
    assert journal(context) == []
    context["store"].commit(old, step)
    with pytest.raises(PaperConflict):
        context["store"].commit(old, update(context, old, "101"))
    assert len(journal(context)) == 1


def test_concurrent_writers_only_one_revision_wins(context):
    old = initial(context)
    steps = [update(context, old, price) for price in ("100", "101")]
    def commit(step):
        try:
            context["store"].commit(old, step)
            return "committed"
        except PaperConflict:
            return "conflict"
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(commit, steps))
    assert sorted(outcomes) == ["committed", "conflict"]
    assert len(journal(context)) == 1 and context["store"].read().revision == 1


@pytest.mark.parametrize("kind", ["quote", "day"])
@pytest.mark.parametrize("fault", ["journal_insert", "checkpoint_update"])
def test_failure_between_journal_and_checkpoint_rolls_back_both(context, fault, kind):
    old = initial(context)
    name = "test_paper_failure_" + uuid4().hex
    table = "paper_journal" if fault == "journal_insert" else "paper_checkpoints"
    operation = "INSERT" if fault == "journal_insert" else "UPDATE"
    with context["admin"]() as admin:
        admin.execute(f"CREATE FUNCTION platform.{name}() RETURNS trigger LANGUAGE plpgsql AS "
                      "'BEGIN RAISE EXCEPTION ''Synthetic paper failure''; END'")
        admin.execute(f"CREATE TRIGGER {name} BEFORE {operation} ON platform.{table}"
                      f" FOR EACH ROW WHEN (NEW.account_id='{context['account']}'::uuid)"
                      f" EXECUTE FUNCTION platform.{name}()")
    try:
        with pytest.raises(PaperStorageRejected):
            context["store"].commit(old, update(context, old) if kind == "quote" else day_update(context, old))
    finally:
        # Only these fresh UUID-named fixture hooks are removed.
        with context["admin"]() as admin:
            admin.execute(f"DROP TRIGGER {name} ON platform.{table}")
            admin.execute(f"DROP FUNCTION platform.{name}()")
    assert context["store"].read() == old and journal(context) == []


class CommitFault:
    def __init__(self, db, after):
        self.db, self.after = db, after
    def __getattr__(self, name):
        return getattr(self.db, name)
    def commit(self):
        if self.after:
            self.db.commit()
        raise psycopg.OperationalError("Synthetic lost commit reply")


@pytest.mark.parametrize("kind", ["quote", "day"])
@pytest.mark.parametrize("after", [False, True])
def test_unknown_commit_never_retries_and_fresh_readback_resolves(context, after, kind):
    old = initial(context)
    step = update(context, old) if kind == "quote" else day_update(context, old)
    calls = []
    def connection():
        calls.append(1)
        return CommitFault(context["worker"](), after)
    store = replace(context["store"], connect=connection)
    with pytest.raises(PaperCommitUnknown):
        store.commit(old, step)
    assert len(calls) == 1
    assert context["store"].read() == (step.checkpoint if after else old)
    assert len(journal(context)) == int(after)


def day_bars():
    at = START+timedelta(days=1)
    return tuple(Candle(s, at-H4, at, D(100), D(100), D(100), D(100)) for s in ("BTCUSDT", "ETHUSDT"))


def day_update(context, old):
    return context["runner"].day(old, day_bars(), now=START+timedelta(days=1, seconds=7))


def test_day_commit_restore_and_model_source_survive_public_journal_window(context):
    old = initial(context)
    step = day_update(context, old)
    saved = context["store"].commit(old, step)
    assert context["store"].read() == saved
    assert context["store"].commit(old, step) == saved
    assert context["runner"].day(saved, day_bars(), now=saved.observed_at).entry is None
    for _ in range(21):
        saved = context["store"].commit(saved, update(context, saved))
    settings, user, subject = status_actor(context)
    response = TestClient(create_app(settings)).get("/v1/paper-status",
        headers=status_headers(settings, subject, context["tenant"]))
    assert response.status_code == 200
    account = next(a for a in response.json()["accounts"] if a["id"] == str(context["account"]))
    assert account["snapshot"]["day_basis_model"] is True
    assert all(j["input_kind"] == "quote" for j in account["journal"])
    assert not any(text in response.text for text in ("bar_digests", "quantities", "paper-h4-close"))


def test_restart_revised_midnight_candle_is_rejected_against_committed_day_evidence(context):
    old = initial(context)
    saved = context["store"].commit(old, day_update(context, old))
    # Simulate restart + a quote replacing last_entry before boundary bar processing.
    saved = context["store"].commit(saved, update(context, saved))
    changed = replace(day_bars()[0], high=D(101), close=D(101))
    with pytest.raises(PaperStorageRejected):
        context["store"].commit(saved, context["runner"].bar(saved, changed, now=saved.observed_at))
    assert context["store"].read() == saved
    correct = context["runner"].bar(saved, day_bars()[0], now=saved.observed_at)
    assert context["store"].commit(saved, correct) == correct.checkpoint


@pytest.mark.parametrize("mode", ["autocommit", "active_transaction"])
def test_nonfresh_or_autocommit_connection_rejected_before_write(context, mode):
    old = initial(context)
    calls = []
    def connection():
        db = context["worker"]()
        if mode == "autocommit": db.autocommit = True
        else: db.execute("SELECT 1")
        calls.append(1)
        return db
    store = replace(context["store"], connect=connection)
    with pytest.raises(PaperStorageRejected):
        store.commit(old, update(context, old))
    assert len(calls) == 1 and journal(context) == []


@pytest.mark.parametrize("field", ["tenant", "account", "mode", "cost", "configuration", "time", "entry"])
def test_sql_rejects_cross_actor_or_mutated_bindings(context, field):
    old = initial(context)
    step = update(context, old)
    d = json.loads(context["runner"].dump(step.checkpoint))
    c = d["checkpoint"]
    if field == "tenant": c["state"]["account"]["tenant_id"] = str(context["foreign"])
    if field == "account": c["state"]["account"]["account_id"] = str(context["other"])
    if field == "mode": d["mode"] = "live"
    if field == "cost": c["cost_digest"] = "0"*64
    if field == "configuration": c["state"]["configuration_digest"] = "0"*64
    if field == "time":
        c["observed_at"] = (START-timedelta(seconds=1)).isoformat()
        c["last_entry"]["at"] = c["observed_at"]
    if field == "entry": c["last_entry"]["revision"] = 2
    payload = json.dumps(d)
    with context["worker"]() as db, pytest.raises(psycopg.Error):
        db.execute("SELECT platform.paper_commit(%s,%s,%s,%s)",
                   (0, checksum(context["runner"].dump(old)), payload, checksum(payload)))
    assert context["store"].read() == old and journal(context) == []


@pytest.mark.parametrize("change", ["paused", "inactive", "read_only"])
def test_current_binding_and_account_status_are_authoritative(context, change):
    old = initial(context)
    with context["admin"]() as db:
        if change == "inactive":
            db.execute("UPDATE platform.paper_role_bindings SET active=false WHERE database_role='investalo_paper_tests'")
        else:
            db.execute("UPDATE platform.accounts SET "+("status='paused'" if change=="paused" else "mode='read_only'")
                       +" WHERE tenant_id=%s AND id=%s", (context["tenant"], context["account"]))
    with pytest.raises(PaperStorageRejected):
        context["store"].commit(old, update(context, old))
    if change == "paused": assert context["store"].read() == old
    else:
        with pytest.raises(PaperStorageRejected): context["store"].read()
    assert journal(context) == []


def test_guc_forgery_does_not_change_session_user_binding(context):
    old = initial(context)
    with context["worker"]() as db:
        db.execute("SELECT set_config('app.tenant_id',%s,true),set_config('app.user_id',%s,true)",
                   (str(context["foreign"]), str(uuid4())))
        record = db.execute("SELECT platform.paper_read() AS record").fetchone()["record"]
    assert context["runner"].restore(record["checkpoint"]) == old


@pytest.mark.parametrize("role", ["investalo_runtime", "investalo_research_worker"])
def test_runtime_and_research_have_no_table_or_executor_rights(context, role):
    with context["admin"]() as db:
        for table in ("paper_role_bindings", "paper_checkpoints", "paper_journal"):
            assert not db.execute("SELECT has_table_privilege(%s,%s,'SELECT') AS allowed",
                                  (role, "platform."+table)).fetchone()["allowed"]
        for fn in ("paper_read()", "paper_initialize(text,text)", "paper_commit(bigint,text,text,text)"):
            assert not db.execute("SELECT has_function_privilege(%s,%s,'EXECUTE') AS allowed",
                                  (role, "platform."+fn)).fetchone()["allowed"]


def test_worker_has_no_direct_table_or_credential_access(context):
    with context["worker"]() as db:
        for table in ("paper_role_bindings", "paper_checkpoints", "paper_journal"):
            for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE"):
                assert not db.execute("SELECT has_table_privilege(current_user,%s,%s) AS allowed",
                                      ("platform."+table, privilege)).fetchone()["allowed"]
        assert not db.execute("SELECT has_table_privilege(current_user,'platform.credential_connections','SELECT')"
                              " AS allowed").fetchone()["allowed"]

def test_paper_login_cannot_connect_normal_development_database(context):
    with pytest.raises(PaperStorageRejected):
        context["worker"]("investalo")


@pytest.mark.parametrize("operation", ["UPDATE", "DELETE", "TRUNCATE"])
def test_journal_immutable_even_to_ordinary_migration_dml(context, operation):
    old = initial(context)
    context["store"].commit(old, update(context, old))
    with context["admin"]() as db, pytest.raises(psycopg.errors.InsufficientPrivilege):
        if operation == "TRUNCATE": db.execute("TRUNCATE platform.paper_journal")
        elif operation == "DELETE":
            db.execute("DELETE FROM platform.paper_journal WHERE tenant_id=%s", (context["tenant"],))
        else:
            db.execute("UPDATE platform.paper_journal SET entry='{}' WHERE tenant_id=%s", (context["tenant"],))
    assert len(journal(context)) == 1


def test_actual_runner_fill_restart_and_duplicate_durable(context):
    state = initial(context)
    for index in range(16):
        opened = START+timedelta(hours=4*index)
        bar = Candle("BTCUSDT", opened, opened+timedelta(hours=4), D(100-index),
                     D(100-index), D(99-index), D(99-index))
        if state.state.account.trading_day != bar.close_time.date():
            eth = Candle("ETHUSDT", opened, bar.close_time, D(100), D(100), D(100), D(100))
            step = context["runner"].day(state, (bar, eth), now=bar.close_time)
            state = context["store"].commit(state, step)
        q = Quote("BTCUSDT", bar.close_time, bar.close, bar.close)
        step = context["runner"].quote(state, q, now=bar.close_time)
        state = context["store"].commit(state, step)
        step = context["runner"].bar(state, bar, now=bar.close_time)
        state = context["store"].commit(state, step)
    assert not state.state.processed_fills
    at = state.observed_at+timedelta(seconds=1)
    q = Quote("BTCUSDT", at, D(84), D(84))
    step = context["runner"].quote(state, q, now=at)
    persisted = context["store"].commit(state, step)
    restarted = context["store"].read()
    assert restarted == persisted and len(restarted.state.processed_fills) == 1
    duplicate = context["runner"].quote(restarted, q, now=at)
    assert context["store"].commit(restarted, duplicate) == persisted
    assert len(journal(context)) == 35


def test_public_feed_contract_to_real_sql_worker_restart_has_one_simulated_fill(context):
    now = datetime(2026, 1, 9, 12, 0, 10, tzinfo=timezone.utc)
    start = boundary(now)-WARMUP_BARS*H4
    clock = [now]

    def response(url):
        query = parse_qs(urlsplit(url).query)
        symbol = query["symbol"][0]
        if urlsplit(url).path.endswith("tickers"):
            value = "60" if symbol == "BTCUSDT" else "100"
            return {"code": "00000", "data": [{
                "category": "SPOT", "symbol": symbol, "bid1Price": value,
                "ask1Price": value, "ts": str(int((clock[0]-timedelta(seconds=1)).timestamp()*1000)),
            }]}
        requested = datetime.fromtimestamp(int(query["startTime"][0])/1000, timezone.utc)+H4
        rows = []
        while requested < boundary(clock[0]):
            index = (requested-start)//H4
            opened = D(100-index) if symbol == "BTCUSDT" else D(100)
            closed = opened-1 if symbol == "BTCUSDT" else opened
            rows.append([str(int(requested.timestamp()*1000)), str(opened), str(opened),
                         str(closed), str(closed), "1", "100"])
            requested += H4
        return {"code": "00000", "data": rows}

    # Fixed synthetic receipt clock; same public parser and actual restricted PG LOGIN.
    class Feed(BitgetPaperFeed):
        def quote(self, symbol, **kwargs):
            return super().quote(symbol, now=clock[0])

    feed = Feed(response)
    worker = PaperWorker(context["runner"], context["store"], feed, lambda: clock[0])
    first = worker.run_once()
    assert first.updates == 82 and first.fills == 0
    assert any(order.unresolved for order in context["store"].read().state.orders)
    clock[0] += timedelta(seconds=3)
    second = worker.run_once()
    assert second.fills == 1
    restarted = PaperWorker(context["runner"], context["store"], feed, lambda: clock[0])
    third = restarted.run_once()
    assert third.updates == third.fills == 0
    restored = context["store"].read()
    assert len(restored.state.processed_fills) == 1
    assert len(journal(context)) == 84


def status_actor(context):
    runtime = replace(Settings.from_environment(), paper_status_preview=True,
                      internal_key=uuid4().hex+uuid4().hex)
    user, subject = uuid4(), "paper-status-"+uuid4().hex
    with context["admin"]() as db:
        db.execute("INSERT INTO platform.users(id,oidc_issuer,oidc_subject) VALUES(%s,%s,%s)",
                   (user, runtime.oidc_issuer, subject))
        db.execute("INSERT INTO platform.memberships(tenant_id,user_id,role) VALUES(%s,%s,'viewer')",
                   (context["tenant"], user))
    return runtime, user, subject


def status_headers(settings, subject, tenant):
    now = int(time.time())
    claims = {"iss": "investalo-bff", "aud": "investalo-api", "sub": subject,
              "oidc_iss": settings.oidc_issuer, "iat": now, "exp": now+30,
              "oidc_auth_time": now, "jti": str(uuid4()), "tenant_id": str(tenant), "auth_epoch": 0,
              "htm": "GET", "htu": "/v1/paper-status", "body_sha256": hashlib.sha256(b"").hexdigest()}
    encode = lambda value: base64.urlsafe_b64encode(json.dumps(value).encode()).rstrip(b"=").decode()
    prefix = encode({"alg": "HS256", "typ": "JWT"})+"."+encode(claims)
    signature = base64.urlsafe_b64encode(hmac.digest(settings.internal_key.encode(), prefix.encode(), "sha256")).rstrip(b"=").decode()
    return {"Authorization": "Bearer "+prefix+"."+signature}


def test_actual_status_api_viewer_reads_only_confirmed_own_paper_and_safe_journal(context):
    before = initial(context)
    context["store"].commit(before, update(context, before))
    settings, user, subject = status_actor(context)
    client = TestClient(create_app(settings))
    result = client.get("/v1/paper-status", headers=status_headers(settings, subject, context["tenant"]))
    assert result.status_code == 200
    data = result.json()
    assert data["tenant_id"] == str(context["tenant"])
    assert {a["id"] for a in data["accounts"]} == {str(context["account"]), str(context["other"])}
    account = next(a for a in data["accounts"] if a["id"] == str(context["account"]))
    assert account["snapshot"]["revision"] == 1
    assert account["snapshot"]["cash"] == "10000"
    assert account["snapshot"]["daily_baseline_ready"] is False
    assert account["journal"][0]["revision"] == 1
    assert not any(field in result.text for field in ("input_digest", "checkpoint", "checksum", "manual_authorization"))
    assert context["store"].read().revision == 1 and len(journal(context)) == 1
    foreign = client.get("/v1/paper-status", headers=status_headers(settings, subject, context["foreign"]))
    assert foreign.status_code == 403


def test_paper_status_flag_off_rejects_without_storage_query(context):
    settings, user, subject = status_actor(context)
    client = TestClient(create_app(replace(settings, paper_status_preview=False)))
    assert client.get("/v1/paper-status", headers=status_headers(settings, subject, context["tenant"])).status_code == 404


def test_status_replay_and_revoked_actor_are_rejected(context):
    settings, user, subject = status_actor(context)
    client = TestClient(create_app(settings))
    headers = status_headers(settings, subject, context["tenant"])
    assert client.get("/v1/paper-status", headers=headers).status_code == 200
    assert client.get("/v1/paper-status", headers=headers).status_code == 401
    with context["admin"]() as db:
        db.execute("UPDATE platform.memberships SET active=false WHERE user_id=%s", (user,))
    assert client.get("/v1/paper-status", headers=status_headers(settings, subject, context["tenant"])).status_code == 403


def test_status_runtime_keeps_no_direct_paper_write_or_table_rights(context):
    settings, user, subject = status_actor(context)
    with psycopg.connect(**settings.connection_parameters(), row_factory=dict_row) as db:
        for table in ("paper_checkpoints", "paper_journal", "paper_role_bindings"):
            assert not db.execute("SELECT has_table_privilege(current_user,%s,'SELECT') AS allowed",
                                  ("platform."+table,)).fetchone()["allowed"]
        for fn in ("paper_initialize(text,text)", "paper_commit(bigint,text,text,text)"):
            assert not db.execute("SELECT has_function_privilege(current_user,%s,'EXECUTE') AS allowed",
                                  ("platform."+fn,)).fetchone()["allowed"]
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute("SELECT * FROM platform.paper_status_rows(0,clock_timestamp())")


@pytest.mark.parametrize("mode", ["missing_epoch", "old_epoch", "wrong_subject"])
def test_status_sql_current_identity_epoch_context_rechecked(context, mode):
    settings, user, subject = status_actor(context)
    with context["admin"]() as db:
        epoch = db.execute("SELECT auth_epoch FROM platform.users WHERE id=%s", (user,)).fetchone()["auth_epoch"]
    with psycopg.connect(**settings.connection_parameters(), row_factory=dict_row) as db:
        db.execute("SELECT set_config('app.user_id',%s,true),set_config('app.tenant_id',%s,true),"
                   "set_config('app.oidc_issuer',%s,true),set_config('app.oidc_subject',%s,true)",
                   (str(user), str(context["tenant"]), settings.oidc_issuer,
                    subject if mode != "wrong_subject" else "foreign-subject"))
        supplied = None if mode == "missing_epoch" else epoch-1 if mode == "old_epoch" else epoch
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute("SELECT * FROM platform.paper_status_rows(%s,clock_timestamp())", (supplied,))
