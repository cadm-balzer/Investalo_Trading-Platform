"""Actual009 completion fencing around synthetic003 writes in the fixture DB.

Envelope bytes here test only the SQL structure; parent's executor flow tests
separately verify actual AEAD and injected Classic probes. No real keys/transport.
"""
import base64
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import os
from threading import Barrier, Event
from time import sleep
from uuid import UUID, uuid4

import psycopg
from psycopg.types.json import Jsonb
import pytest

from conftest import connect_as
from test_passkey_authorization_flow import clock, receipt
from test_passkey_authorization_postgres import CONSUME, LOCK, claims, state, worker

FINISH = "SELECT platform.credential_finish_passkey_authorization(%s::jsonb,%s) AS valid"


def envelope():
    encoded = lambda count: base64.b64encode(b"\x02" * count).decode("ascii")
    return dict(schema_version="credential-envelope/1", kek_id="synthetic-completion-only",
                payload_nonce=encoded(12), wrap_nonce=encoded(12),
                wrapped_dek=encoded(48), ciphertext=encoded(32))


def write(db, c, *, action=None, connection=None, account=None, revision=None, storage=None):
    target = c["target"]
    action = action or target["action"]
    connection = connection or UUID(target["connection_id"])
    account = account or UUID(target["platform_account_id"])
    revision = target.get("expected_revision", 1) if revision is None else revision
    storage = target.get("expected_storage", 1) if storage is None else storage
    if action == "register":
        return db.execute("SELECT * FROM platform.credential_create(%s,%s,%s,%s,%s)",
                          (account, connection, str(10**19 + uuid4().int % 10**19), None,
                           Jsonb(envelope()))).fetchone()
    if action == "replace":
        return db.execute("SELECT * FROM platform.credential_replace(%s,%s,%s,%s)",
                          (connection, revision, storage, Jsonb(envelope()))).fetchone()
    return db.execute("SELECT platform.credential_revoke(%s,%s,%s) AS version",
                      (connection, revision, storage)).fetchone()


def finish(c, outcome="completed", *, identity="a"):
    with connect_as(identity) as db:
        return db.execute(FINISH, (Jsonb(c), outcome)).fetchone()["valid"]


def complete(c, *, mutation=True, lock=True, finish_claims=None):
    with connect_as("a") as db:
        if lock:
            assert db.execute(LOCK, (Jsonb(c),)).fetchone()["valid"] is True
        if mutation:
            write(db, c)
        return db.execute(FINISH, (Jsonb(finish_claims or c), "completed")).fetchone()["valid"]


def rejected(callback, code="42501"):
    with pytest.raises(psycopg.Error) as error:
        callback()
    assert error.value.sqlstate == code
    assert error.value.diag.message_primary in {"access_denied", "concurrent_change", "invalid_record"}
    assert error.value.diag.message_detail is None


def observe(r):
    with connect_as("admin") as db:
        terminal = db.execute("SELECT * FROM platform.passkey_credential_completion_audit WHERE authorization_id=%s",
                              (UUID(r["authorization_id"]),)).fetchone()
        stored = db.execute("SELECT connection_id,credential_revision,storage_version,status FROM platform.credential_connections "
                            "WHERE tenant_id=%s AND platform_account_id=%s",
                            (UUID(r["tenant_id"]), UUID(r["target"]["platform_account_id"]))).fetchone()
    return terminal, stored


def assert_unchanged(r):
    terminal, stored = observe(r)
    if r["target"]["action"] == "register":
        assert stored is None
    else:
        assert stored == {"connection_id": UUID(r["target"]["connection_id"]),
                          "credential_revision": r["target"]["expected_revision"],
                          "storage_version": r["target"]["expected_storage"], "status": "active"}
    assert state(r)["state"] == "consumed"
    return terminal


@pytest.mark.parametrize("action", ["register", "replace", "revoke"])
def test_expected003_mutation_and_terminal_audit_commit_together(credential_database, action):
    r, _ = receipt(credential_database, action)
    c = claims(r)
    worker(CONSUME, c)
    assert complete(c) is True
    terminal, stored = observe(r)
    revision = 2 if action == "replace" else 1
    storage = 1 if action == "register" else 2
    status = "revoked" if action == "revoke" else "active"
    assert stored == {"connection_id": UUID(r["target"]["connection_id"]),
                      "credential_revision": revision, "storage_version": storage, "status": status}
    assert terminal["outcome"] == "completed" and terminal["action"] == action
    assert (terminal["credential_revision"], terminal["storage_version"], terminal["connection_status"]) == (revision, storage, status)
    assert terminal["database_role"] == os.environ["CREDENTIAL_TEST_USER_A"]
    assert terminal["transaction_id"] == state(r)["lock_transaction"]
    assert set(terminal) == {"authorization_id", "outcome", "tenant_id", "user_id", "platform_account_id",
                             "connection_id", "action", "credential_revision", "storage_version",
                             "connection_status", "database_role", "transaction_id", "occurred_at"}
    rejected(lambda: finish(c))
    rejected(lambda: finish(c, "failed"))
    assert observe(r)[0] == terminal


@pytest.mark.parametrize("action", ["register", "replace", "revoke"])
def test_missing_mutation_cannot_finish_and_lock_marker_rolls_back(credential_database, action):
    r, _ = receipt(credential_database, action)
    c = claims(r)
    worker(CONSUME, c)
    rejected(lambda: complete(c, mutation=False), "40001")
    assert assert_unchanged(r) is None


@pytest.mark.parametrize("action", ["register", "replace", "revoke"])
def test_mutation_without_current008_lock_cannot_finish(credential_database, action):
    r, _ = receipt(credential_database, action)
    c = claims(r)
    worker(CONSUME, c)
    rejected(lambda: complete(c, lock=False))
    assert assert_unchanged(r) is None


def test_a_committed_lock_is_not_a_final_transaction_authorization(credential_database):
    r, _ = receipt(credential_database, "register")
    c = claims(r)
    worker(CONSUME, c)
    worker(LOCK, c)
    rejected(lambda: complete(c, lock=False))
    terminal, stored = observe(r)
    assert terminal is None and stored is None and state(r)["state"] == "locked"


@pytest.mark.parametrize("change", ["jti", "iat", "exp", "body_sha256", "target"])
def test_completion_requires_exact_original_authenticated_claims(credential_database, change):
    r, _ = receipt(credential_database, "register")
    c = claims(r)
    worker(CONSUME, c)
    changed = deepcopy(c)
    if change == "jti":
        changed[change] = str(uuid4())
    elif change in {"iat", "exp"}:
        changed[change] -= 1
    elif change == "body_sha256":
        changed[change] = "b" * 64
    else:
        changed["target"]["connection_id"] = str(uuid4())
    rejected(lambda: complete(c, finish_claims=changed))
    assert assert_unchanged(r) is None


@pytest.mark.parametrize("action", ["register", "replace", "revoke"])
def test_matching_versions_also_require_matching_final_status(credential_database, action):
    r, _ = receipt(credential_database, action)
    c = claims(r)
    worker(CONSUME, c)
    def wrong_write():
        with connect_as("a") as db:
            db.execute(LOCK, (Jsonb(c),))
            if action == "register":
                write(db, c)
                write(db, c, action="revoke", revision=1, storage=1)
            else:
                write(db, c, action="replace" if action == "revoke" else "revoke")
            db.execute(FINISH, (Jsonb(c), "completed"))
    rejected(wrong_write, "40001")
    assert assert_unchanged(r) is None


@pytest.mark.parametrize("target", ["connection", "account"])
def test_register_result_must_match_exact_frozen_target(credential_database, target):
    f = credential_database
    r, _ = receipt(f, "register")
    c = claims(r)
    worker(CONSUME, c)
    def wrong_write():
        with connect_as("a") as db:
            db.execute(LOCK, (Jsonb(c),))
            write(db, c, **({"connection": uuid4()} if target == "connection" else {"account": f["account_a2"]}))
            db.execute(FINISH, (Jsonb(c), "completed"))
    rejected(wrong_write, "40001")
    assert assert_unchanged(r) is None
    with connect_as("admin") as db:
        assert db.execute("SELECT 1 FROM platform.credential_connections WHERE platform_account_id=%s",
                          (f["account_a2"],)).fetchone() is None


@pytest.mark.parametrize("action", ["register", "replace", "revoke"])
def test_completed_audit_and_mutation_roll_back_as_one_unit(credential_database, action):
    r, _ = receipt(credential_database, action)
    c = claims(r)
    worker(CONSUME, c)
    with pytest.raises(RuntimeError):
        with connect_as("a") as db:
            db.execute(LOCK, (Jsonb(c),))
            write(db, c)
            assert db.execute(FINISH, (Jsonb(c), "completed")).fetchone()["valid"] is True
            raise RuntimeError("Synthetic rollback after finish")
    assert assert_unchanged(r) is None
    assert finish(c, "failed") is True
    terminal = observe(r)[0]
    assert terminal["outcome"] == "failed"
    assert terminal["credential_revision"] is terminal["storage_version"] is terminal["connection_status"] is None


@pytest.mark.parametrize("phase", ["consume", "lock", "write"])
def test_failure_cannot_commit_inside_the_authority_or_final_transaction(credential_database, phase):
    r, _ = receipt(credential_database, "register")
    c = claims(r)
    if phase != "consume":
        worker(CONSUME, c)
    def failure_in_wrong_transaction():
        with connect_as("a") as db:
            if phase == "consume":
                db.execute(CONSUME, (Jsonb(c),))
            else:
                db.execute(LOCK, (Jsonb(c),))
                if phase == "write":
                    write(db, c)
            db.execute(FINISH, (Jsonb(c), "failed"))
    rejected(failure_in_wrong_transaction)
    assert observe(r) == (None, None)
    assert state(r)["state"] == ("authorized" if phase == "consume" else "consumed")


@pytest.mark.parametrize("action", ["register", "replace", "revoke"])
def test_failed_tombstone_prevents_later_guarded_write_completion(credential_database, action):
    r, _ = receipt(credential_database, action)
    c = claims(r)
    worker(CONSUME, c)
    assert finish(c, "failed") is True
    failed = observe(r)[0]
    rejected(lambda: finish(c, "failed"))
    # Unchanged008 does not know009's terminal table. The new executor's
    # mandatory finish fails and rolls back this attempted008lock/003write.
    rejected(lambda: complete(c))
    assert assert_unchanged(r) == failed


@pytest.mark.parametrize("stale", ["clock", "epoch", "factor"])
def test_failure_evidence_needs_owner_not_fresh_proof(credential_database, stale):
    f = credential_database
    r, _ = receipt(f, "register")
    c = claims(r)
    if stale == "clock":
        with connect_as("admin") as db:
            c["exp"] = clock(db) + 2
    worker(CONSUME, c)
    if stale == "clock":
        with connect_as("admin") as db:
            sleep(max(0, c["exp"] - clock(db)) + 0.1)
    else:
        with connect_as("admin") as db:
            if stale == "epoch":
                db.execute("UPDATE platform.users SET auth_epoch=auth_epoch+1 WHERE id=%s", (f["user_a"],))
            else:
                db.execute("SELECT * FROM platform.passkey_admin_revoke(%s,%s,%s)",
                           (UUID(r["passkey_id"]), r["passkey_version"], uuid4()))
    assert finish(c, "failed") is True
    assert observe(r)[0]["outcome"] == "failed"


@pytest.mark.parametrize("identity", ["b", "unbound", "runtime", "research"])
def test_other_login_cannot_finalize_owned_consent(credential_database, identity):
    r, _ = receipt(credential_database, "register")
    c = claims(r)
    worker(CONSUME, c)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        finish(c, "failed", identity=identity)
    assert assert_unchanged(r) is None


@pytest.mark.parametrize("outcome", [None, "authorized", "locked", "COMPLETED"])
def test_terminal_outcome_is_explicit_and_bounded(credential_database, outcome):
    r, _ = receipt(credential_database, "register")
    c = claims(r)
    worker(CONSUME, c)
    rejected(lambda: finish(c, outcome), "22023")
    assert assert_unchanged(r) is None


def test_two_failure_finalizers_have_one_global_terminal_winner(credential_database):
    r, _ = receipt(credential_database, "register")
    c = claims(r)
    worker(CONSUME, c)
    barrier = Barrier(2)
    def contender():
        barrier.wait(timeout=5)
        try:
            return finish(c, "failed")
        except psycopg.errors.InsufficientPrivilege:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: contender(), range(2))) == [False, True]
    assert observe(r)[0]["outcome"] == "failed"


@pytest.mark.parametrize("action", ["register", "replace", "revoke"])
def test_deadline_after_mutation_and_waiting_on_audit_insert_rolls_back_everything(credential_database, action):
    r, _ = receipt(credential_database, action)
    c = claims(r)
    with connect_as("admin") as db:
        c["exp"] = clock(db) + 4
    worker(CONSUME, c)
    entered = Event()
    def contender():
        entered.set()
        complete(c)
    with ThreadPoolExecutor(max_workers=1) as pool:
        with connect_as("admin") as blocker:
            blocker.execute("LOCK TABLE platform.passkey_credential_completion_audit IN SHARE MODE")
            pending = pool.submit(contender)
            assert entered.wait(3)
            blocked = False
            for _ in range(50):
                blocked = blocker.execute(
                    "SELECT EXISTS(SELECT 1 FROM pg_locks WHERE locktype='relation' "
                    "AND relation='platform.passkey_credential_completion_audit'::regclass "
                    "AND mode='RowExclusiveLock' AND NOT granted) AS blocked",
                ).fetchone()["blocked"]
                if blocked:
                    break
                blocker.execute("SELECT pg_sleep(0.02)")
            assert blocked and not pending.done() and clock(blocker) < c["exp"]
            sleep(max(0, c["exp"] - clock(blocker)) + 0.05)
        rejected(lambda: pending.result(timeout=5))
    assert assert_unchanged(r) is None
    # Durable one-use consumption survives the failed final transaction.
    rejected(lambda: worker(CONSUME, c))
    assert finish(c, "failed") is True


@pytest.mark.parametrize("command", [
    "UPDATE platform.passkey_credential_completion_audit SET outcome='completed'",
    "DELETE FROM platform.passkey_credential_completion_audit",
    "TRUNCATE platform.passkey_credential_completion_audit",
])
def test_terminal_audit_is_immutable(credential_database, command):
    r, _ = receipt(credential_database, "register")
    c = claims(r)
    worker(CONSUME, c)
    finish(c, "failed")
    def mutate_audit():
        with connect_as("admin") as db:
            db.execute(command)
    rejected(mutate_audit)


def test_force_rls_and_only_credential_finalizer_grant(credential_database):
    with connect_as("admin") as db:
        assert db.execute("SELECT relrowsecurity,relforcerowsecurity FROM pg_class "
                          "WHERE oid='platform.passkey_credential_completion_audit'::regclass").fetchone() == {
            "relrowsecurity": True, "relforcerowsecurity": True,
        }
        for role in ("investalo_runtime", "investalo_research_worker", "investalo_credentials_worker"):
            assert db.execute("SELECT has_table_privilege(%s,'platform.passkey_credential_completion_audit',"
                              "'SELECT,INSERT,UPDATE,DELETE,TRUNCATE') AS allowed", (role,)).fetchone()["allowed"] is False
            assert db.execute("SELECT has_function_privilege(%s,'platform.credential_passkey_completion_locked(jsonb,text)',"
                              "'EXECUTE') AS allowed", (role,)).fetchone()["allowed"] is False
            assert db.execute("SELECT has_function_privilege(%s,'platform.credential_finish_passkey_authorization(jsonb,text)',"
                              "'EXECUTE') AS allowed", (role,)).fetchone()["allowed"] is (role == "investalo_credentials_worker")
        assert db.execute("SELECT p.prosecdef,p.proconfig,r.rolname AS owner FROM pg_proc p "
                          "JOIN pg_roles r ON r.oid=p.proowner WHERE p.oid="
                          "'platform.credential_finish_passkey_authorization(jsonb,text)'::regprocedure").fetchone() == {
            "prosecdef": True, "proconfig": ["search_path=pg_catalog"], "owner": "investalo_migration",
        }
