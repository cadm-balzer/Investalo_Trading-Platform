"""Real PostgreSQL request consumption, fresh authorization and write fencing."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
import secrets
from threading import Barrier, Event
import time
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb
import pytest

from investalo_credentials import AADBinding, KEKRing, SecretPayload, dump_envelope, seal
from conftest import connect_as

BEGIN_SQL = "SELECT platform.credential_begin_request(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) AS nonce"
LOCK_SQL = "SELECT platform.credential_lock_request(%s,%s,%s,%s,%s,%s) AS ok"
FINISH_SQL = "SELECT platform.credential_finish_request(%s,%s) AS ok"


def request(context, *, who="a", **overrides):
    now = int(time.time())
    values = dict(jti=uuid4(), issuer=context["issuer"], subject=context[f"subject_{who}"],
                  epoch=0, auth_time=now, started_at=now, expires_at=now+30,
                  action="register", account=context[f"account_{who}"], connection=uuid4(),
                  revision=None, storage=None)
    values.update(overrides)
    return values


def begin_args(values):
    return tuple(values[name] for name in ("jti", "issuer", "subject", "epoch", "auth_time", "started_at", "expires_at",
                                          "action", "account", "connection", "revision", "storage"))


def lock_args(values):
    return tuple(values[name] for name in ("jti", "action", "account", "connection", "revision", "storage"))


def begin(values, *, who="a"):
    with connect_as(who) as database:
        assert database.execute(BEGIN_SQL, begin_args(values)).fetchone()["nonce"] == values["jti"]


def lock(database, values):
    assert database.execute(LOCK_SQL, lock_args(values)).fetchone()["ok"] is True


def finish(database, values, outcome):
    assert database.execute(FINISH_SQL, (values["jti"], outcome)).fetchone()["ok"] is True


def envelope(context, values, *, revision=1):
    bound = AADBinding(
        tenant_id=context["tenant_a"], user_id=context["user_a"], platform_account_id=values["account"],
        connection_id=values["connection"], broker_uid=values.get("uid", str(secrets.randbelow(10**18)+1)),
        parent_uid=None, credential_revision=revision,
    )
    ring = KEKRing((("synthetic-onboarding", secrets.token_bytes(32)),), active_version="synthetic-onboarding")
    raw = json.loads(dump_envelope(seal(SecretPayload(b"SYNTHETIC_PRIVATE_SENTINEL"), bound, ring)))
    return bound, raw


def write_register(database, context, values):
    bound, ciphertext = envelope(context, values)
    return database.execute(
        "SELECT * FROM platform.credential_create(%s,%s,%s,NULL,%s)",
        (values["account"], values["connection"], bound.broker_uid, Jsonb(ciphertext)),
    ).fetchone()


def observe(values):
    with connect_as("admin") as database:
        current = database.execute("SELECT * FROM platform.credential_onboarding_requests WHERE jti=%s", (values["jti"],)).fetchone()
        events = database.execute("SELECT * FROM platform.credential_onboarding_audit WHERE jti=%s ORDER BY occurred_at,event", (values["jti"],)).fetchall()
    return current, events


def denied_call(callback, state="42501"):
    with pytest.raises(psycopg.Error) as failure:
        callback()
    assert failure.value.sqlstate == state
    assert failure.value.diag.message_detail is None


def test_begin_is_committed_once_and_audit_has_only_static_ids_versions(credential_database):
    values = request(credential_database)
    begin(values)
    current, events = observe(values)
    assert current["state"] == "authorized" and current["locked_transaction"] is None
    assert current["user_id"] == credential_database["user_a"]
    assert [event["event"] for event in events] == ["authorized"]
    assert set(events[0]) == {"jti", "event", "tenant_id", "user_id", "platform_account_id", "connection_id",
                              "action", "credential_revision", "storage_version", "occurred_at"}
    denied_call(lambda: begin(values))
    # Same UUID cannot authorize a different LOGIN/tenant, action or body later.
    foreign = request(credential_database, who="b", jti=values["jti"])
    denied_call(lambda: begin(foreign, who="b"))
    assert len(observe(values)[1]) == 1


def test_duplicate_jti_race_across_owner_logins_has_one_winner(credential_database):
    nonce, barrier = uuid4(), Barrier(2)
    def contender(who):
        values = request(credential_database, who=who, jti=nonce)
        barrier.wait(timeout=5)
        try:
            begin(values, who=who)
            return "accepted"
        except psycopg.errors.InsufficientPrivilege as failure:
            assert failure.diag.message_primary == "access_denied"
            return failure.sqlstate
    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.submit(contender, "a"), pool.submit(contender, "b")
        assert sorted((first.result(timeout=15), second.result(timeout=15))) == ["42501", "accepted"]
    current, events = observe({"jti": nonce})
    assert current["state"] == "authorized" and len(events) == 1


def test_begin_rechecks_clock_after_waiting_for_account_lock_before_publishing_nonce(credential_database):
    values, started = request(credential_database, expires_at=int(time.time())+2), Event()
    def contender():
        with connect_as("a") as database:
            started.set()
            database.execute(BEGIN_SQL, begin_args(values))
    with ThreadPoolExecutor(max_workers=1) as pool:
        with connect_as("admin") as blocker:
            blocker.execute("UPDATE platform.accounts SET name=name WHERE tenant_id=%s AND id=%s",
                            (credential_database["tenant_a"], values["account"]))
            pending = pool.submit(contender)
            assert started.wait(timeout=2)
            # Observe the actual conflicting fixture transaction, not a guessed
            # scheduling delay. pg_locks exposes no credentials or broker data.
            waiting = False
            for _ in range(30):
                waiting = blocker.execute(
                    "SELECT EXISTS(SELECT 1 FROM pg_locks WHERE NOT granted AND locktype='transactionid' "
                    "AND transactionid=pg_current_xact_id()::text::xid) AS waiting",
                ).fetchone()["waiting"]
                if waiting:
                    break
                blocker.execute("SELECT pg_sleep(0.02)")
            assert waiting
            blocker.execute("SELECT pg_sleep(2.1)")
        denied_call(lambda: pending.result(timeout=10))
    assert observe(values) == (None, [])


@pytest.mark.parametrize("patch", [
    {"issuer": "https://other.invalid"}, {"subject": "other-owner"}, {"epoch": 1},
    {"auth_delta": -121}, {"auth_delta": 20}, {"start_delta": 1},
    {"start_delta": -301}, {"expires_delta": 0}, {"expires_delta": 90},
])
def test_begin_rejects_wrong_identity_generation_stale_mfa_and_bad_time_relationship(credential_database, patch):
    now = int(time.time())
    values = request(credential_database, auth_time=now, started_at=now, expires_at=now+30)
    for name, value in patch.items():
        if name.endswith("_delta"):
            field = {"auth_delta": "auth_time", "start_delta": "started_at", "expires_delta": "expires_at"}[name]
            values[field] = now + value
            if name == "auth_delta" and value < 0:
                values["started_at"] = values[field]
        else:
            values[name] = value
    denied_call(lambda: begin(values))
    assert observe(values) == (None, [])


def test_begin_shape_and_account_authority_fail_without_consuming_nonce(credential_database):
    context = credential_database
    for patch in ({"action": "trade"}, {"epoch": None}, {"auth_time": None},
                  {"revision": 1}, {"storage": 1}, {"connection": None}):
        values = request(context, **patch)
        denied_call(lambda: begin(values), "22023")
        assert observe(values) == (None, [])
    values = request(context, account=context["account_b"])
    denied_call(lambda: begin(values))
    with connect_as("admin") as database:
        database.execute("UPDATE platform.accounts SET mode='paper' WHERE tenant_id=%s AND id=%s",
                         (context["tenant_a"], context["account_a"]))
    denied_call(lambda: begin(request(context)))


@pytest.mark.parametrize("change", ["epoch", "recovery", "issuer", "subject", "user_inactive",
                                    "membership_inactive", "viewer", "binding", "account_paused", "account_paper"])
def test_current_identity_and_rights_are_rechecked_after_consumed_begin(credential_database, change):
    context, values = credential_database, request(credential_database)
    begin(values)
    with connect_as("admin") as database:
        if change == "epoch":
            database.execute("UPDATE platform.users SET auth_epoch=1 WHERE id=%s", (context["user_a"],))
        elif change == "recovery":
            database.execute("UPDATE platform.users SET reauth_after=clock_timestamp()+interval '1 second' WHERE id=%s", (context["user_a"],))
        elif change in ("issuer", "subject"):
            database.execute(sql.SQL("UPDATE platform.users SET {}=%s WHERE id=%s").format(sql.Identifier("oidc_" + change)),
                             ("changed-synthetic-" + uuid4().hex, context["user_a"]))
        elif change == "user_inactive":
            database.execute("UPDATE platform.users SET active=false WHERE id=%s", (context["user_a"],))
        elif change == "membership_inactive":
            database.execute("UPDATE platform.memberships SET active=false WHERE tenant_id=%s AND user_id=%s",
                             (context["tenant_a"], context["user_a"]))
        elif change == "viewer":
            database.execute("UPDATE platform.memberships SET role='viewer' WHERE tenant_id=%s AND user_id=%s",
                             (context["tenant_a"], context["user_a"]))
        elif change in ("account_paused", "account_paper"):
            field, value = ("status", "paused") if change == "account_paused" else ("mode", "paper")
            database.execute(sql.SQL("UPDATE platform.accounts SET {}=%s WHERE tenant_id=%s AND id=%s").format(sql.Identifier(field)),
                             (value, context["tenant_a"], context["account_a"]))
        else:
            database.execute("UPDATE platform.credential_role_bindings SET user_id=%s WHERE database_role=%s",
                             (context["user_b"], os.environ["CREDENTIAL_TEST_USER_A"]))
    with connect_as("a") as database:
        denied_call(lambda: lock(database, values))
    current, events = observe(values)
    assert current["state"] == "authorized" and current["locked_transaction"] is None and len(events) == 1


def test_final_argument_binding_rejects_other_ids_action_and_versions(credential_database):
    values = request(credential_database)
    begin(values)
    for patch in ({"action": "replace"}, {"account": credential_database["account_a2"]},
                  {"connection": uuid4()}, {"revision": 1}, {"storage": 1}):
        with connect_as("a") as database:
            denied_call(lambda: lock(database, {**values, **patch}))
    with connect_as("b") as database:
        denied_call(lambda: lock(database, values))
    assert observe(values)[0]["locked_transaction"] is None


def test_register_replace_and_paused_revoke_complete_atomically_with_real_versions(credential_database):
    context, registered = credential_database, request(credential_database)
    begin(registered)
    with connect_as("a") as database:
        lock(database, registered)
        row = write_register(database, context, registered)
        finish(database, registered, "completed")
    assert row["credential_revision"] == row["storage_version"] == 1
    assert observe(registered)[0]["state"] == "completed"
    denied_call(lambda: begin(registered))
    replacement = request(context, action="replace", connection=registered["connection"], revision=1, storage=1)
    begin(replacement)
    _, ciphertext = envelope(context, {**replacement, "uid": row["broker_uid"]}, revision=2)
    with connect_as("a") as database:
        lock(database, replacement)
        updated = database.execute("SELECT * FROM platform.credential_replace(%s,1,1,%s)",
                                   (replacement["connection"], Jsonb(ciphertext))).fetchone()
        finish(database, replacement, "completed")
    assert updated["credential_revision"] == updated["storage_version"] == 2
    with connect_as("admin") as database:
        database.execute("UPDATE platform.accounts SET status='paused' WHERE tenant_id=%s AND id=%s", (context["tenant_a"], context["account_a"]))
    revoked = request(context, action="revoke", connection=registered["connection"], revision=2, storage=2)
    begin(revoked)
    with connect_as("a") as database:
        lock(database, revoked)
        assert database.execute("SELECT platform.credential_revoke(%s,2,2) AS version", (revoked["connection"],)).fetchone()["version"] == 3
        finish(database, revoked, "completed")
    assert observe(revoked)[0]["state"] == "completed"
    assert observe(revoked)[1][-1]["storage_version"] == 3
    for grant in (registered, replacement, revoked):
        with connect_as("a") as database:
            denied_call(lambda: lock(database, grant))


def test_stale_versions_after_begin_fail_final_cas_and_leave_nonce_consumed(credential_database):
    context, registered = credential_database, request(credential_database)
    with connect_as("a") as database:
        original = write_register(database, context, registered)
    values = request(context, action="replace", connection=registered["connection"], revision=1, storage=1)
    begin(values)
    with connect_as("a") as database:
        database.execute("SELECT * FROM platform.credential_rewrap(%s,1,1,%s)",
                         (values["connection"], Jsonb(original["envelope"])))
    with connect_as("a") as database:
        denied_call(lambda: lock(database, values), "40001")
    denied_call(lambda: begin(values))
    with connect_as("a") as database:
        finish(database, values, "failed")
    assert observe(values)[0]["state"] == "failed"


def test_completed_requires_lock_and_write_in_same_transaction(credential_database):
    context, values = credential_database, request(credential_database)
    begin(values)
    with connect_as("a") as database:
        denied_call(lambda: finish(database, values, "completed"))
    with connect_as("a") as database:
        lock(database, values)
        denied_call(lambda: finish(database, values, "completed"))  # No credential write.
    assert observe(values)[0]["locked_transaction"] is None  # Failed transaction rolled back.
    with connect_as("a") as database:
        lock(database, values)  # Deliberately commit lock without a write.
    # Migration 003 remains a trusted primitive; 004 does not claim to forbid
    # direct server-side writes. Such a separate write cannot complete this grant.
    with connect_as("a") as database:
        write_register(database, context, values)
    with connect_as("a") as database:
        denied_call(lambda: finish(database, values, "completed"))
    with connect_as("a") as database:
        finish(database, values, "failed")
    assert observe(values)[0]["state"] == "failed"


def test_expiry_after_lock_and_write_rolls_back_credential_and_completed_audit(credential_database):
    context = credential_database
    values = request(context, expires_at=int(time.time())+2)
    begin(values)  # One-use nonce is committed independently before any probe.
    with connect_as("a") as database:
        lock(database, values)
        write_register(database, context, values)
        database.execute("SELECT pg_sleep(2.1)")
        denied_call(lambda: finish(database, values, "completed"))
    with connect_as("admin") as database:
        assert database.execute("SELECT 1 FROM platform.credential_connections WHERE tenant_id=%s AND connection_id=%s",
                                (context["tenant_a"], values["connection"])).fetchone() is None
    current, events = observe(values)
    assert current["state"] == "authorized" and current["locked_transaction"] is None
    assert [event["event"] for event in events] == ["authorized"]
    denied_call(lambda: begin(values))
    # Expired requests may be terminally failed; this never authorizes storage.
    with connect_as("a") as database:
        finish(database, values, "failed")
    assert [event["event"] for event in observe(values)[1]] == ["authorized", "failed"]
    with connect_as("a") as database:
        denied_call(lambda: finish(database, values, "failed"))


def test_final_user_liveness_lock_prevents_recovery_change_until_write_finishes(credential_database):
    values = request(credential_database)
    begin(values)
    with connect_as("a") as database:
        lock(database, values)
        def attempt_recovery():
            with connect_as("admin") as other:
                other.execute("SET LOCAL lock_timeout='100ms'")
                with pytest.raises(psycopg.errors.LockNotAvailable):
                    other.execute("UPDATE platform.users SET auth_epoch=auth_epoch+1 WHERE id=%s", (credential_database["user_a"],))
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(attempt_recovery).result(timeout=5)
        write_register(database, credential_database, values)
        finish(database, values, "completed")


def test_request_and_audit_are_private_immutable_and_functions_are_narrowly_granted(credential_database):
    values = request(credential_database)
    begin(values)
    for who in ("a", "runtime", "research"):
        for table in ("credential_onboarding_requests", "credential_onboarding_audit"):
            with connect_as(who) as database:
                denied_call(lambda: database.execute(sql.SQL("SELECT * FROM platform.{}").format(sql.Identifier(table))))
            with connect_as(who) as database:
                denied_call(lambda: database.execute(sql.SQL("UPDATE platform.{} SET action='revoke'").format(sql.Identifier(table))))
        with connect_as(who) as database:
            denied_call(lambda: database.execute("SELECT platform.credential_request_clock(1,1,1)"))
    for who in ("runtime", "research"):
        for statement, parameters in ((BEGIN_SQL, begin_args(values)), (LOCK_SQL, lock_args(values)), (FINISH_SQL, (values["jti"], "failed"))):
            with connect_as(who) as database:
                denied_call(lambda: database.execute(statement, parameters))
    for statement in (
        "UPDATE platform.credential_onboarding_requests SET auth_epoch=1 WHERE jti=%s",
        "DELETE FROM platform.credential_onboarding_requests WHERE jti=%s",
        "UPDATE platform.credential_onboarding_audit SET event='failed' WHERE jti=%s",
        "DELETE FROM platform.credential_onboarding_audit WHERE jti=%s",
    ):
        with connect_as("admin") as database:
            denied_call(lambda: database.execute(statement, (values["jti"],)))
    with connect_as("admin") as database:
        functions = database.execute(
            "SELECT p.proname,p.prosecdef,p.proconfig,pg_get_userbyid(p.proowner) AS owner "
            "FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
            "WHERE n.nspname='platform' AND p.proname IN "
            "('credential_begin_request','credential_lock_request','credential_finish_request',"
            "'credential_request_clock','credential_request_scope','credential_request_identity')",
        ).fetchall()
        assert len(functions) == 6
        for function in functions:
            assert function["owner"] == "investalo_migration" and function["proconfig"] == ["search_path=pg_catalog"]
            assert function["prosecdef"] == (function["proname"] != "credential_request_clock")
        tables = database.execute(
            "SELECT c.relrowsecurity,c.relforcerowsecurity FROM pg_class c "
            "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='platform' "
            "AND c.relname IN ('credential_onboarding_requests','credential_onboarding_audit')",
        ).fetchall()
        assert len(tables) == 2 and all(row["relrowsecurity"] and row["relforcerowsecurity"] for row in tables)
    assert "SYNTHETIC_PRIVATE_SENTINEL" not in json.dumps(observe(values)[1], default=str)
