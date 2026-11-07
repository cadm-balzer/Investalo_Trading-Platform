"""Actual PostgreSQL verification proofs; no WebAuthn verdict or broker activation.

Root applies reviewed 007 to the isolated fixture DB first. All identities,
public-key bytes and encrypted envelope shapes here are synthetic. Claims commit
before the simulated trusted cryptographic result; no password/factor is read.
"""
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
import secrets
from threading import Barrier
from time import monotonic, sleep
from uuid import uuid4

import psycopg
from psycopg.types.json import Jsonb
import pytest

from investalo_api.database import connect
from test_postgres import database
from test_credential_action_postgres import credential_database
from test_passkey_postgres import (
    RP, REVOKE, actor, claim as enrollment_claim, denied, finish as enrollment_finish,
    issue, read as read_key, update_counter,
)

PREPARE = "SELECT * FROM platform.passkey_action_prepare(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
CLAIM = "SELECT * FROM platform.passkey_action_claim(%s,%s,%s,%s,%s)"
FINISH = "SELECT * FROM platform.passkey_action_finish(%s,%s,%s,%s,%s,%s,%s,%s,%s)"
READ_GRANT = "SELECT * FROM platform.passkey_action_read_grant(%s,%s,%s,%s,%s)"
CONFIRM = "SELECT * FROM platform.passkey_action_confirm(%s,%s,%s,%s,%s,%s)"
ATTEMPT_COLUMNS = (
    "attempt_id", "tenant_id", "user_id", "auth_epoch", "rp_id", "target", "metadata",
    "passkey_id", "passkey_storage", "sign_count", "backup_eligible", "backed_up",
    "credential_id", "user_handle", "public_key", "enrollment_epoch", "session_binding",
    "challenge", "confirmation_hash", "prepared_at", "expires_at", "session_expires_at",
)
GRANT_COLUMNS = (
    "grant_id", "attempt_id", "tenant_id", "user_id", "auth_epoch", "rp_id", "target",
    "metadata", "passkey_id", "passkey_version", "session_binding", "confirmation_hash",
    "checked_at", "expires_at", "session_expires_at",
)


def clock(db):
    return db.execute("SELECT floor(extract(epoch FROM clock_timestamp()))::bigint AS n").fetchone()["n"]


@pytest.fixture
def proof_database(credential_database):
    f = credential_database
    with connect(f["admin"]) as db:
        assert db.execute(
            "SELECT 1 FROM platform.schema_migrations WHERE version='007_passkey_action_proofs'"
        ).fetchone(), "Root must apply reviewed additive007 in the isolated fixture DB"
        db.execute("UPDATE platform.memberships SET role='trader' WHERE user_id=%s", (f["user_b"],))
        f["empty_account"] = db.execute(
            "INSERT INTO platform.accounts(tenant_id,name,broker,mode,currency) "
            "VALUES(%s,'Unconnected proof account','bitget','read_only','USDT') RETURNING id",
            (f["tenant_a"],),
        ).fetchone()["id"]
        # Deliberately old OIDC login time: fresh passkey time must not replace it.
        f["oidc_auth_time"] = clock(db) - 600
    f["key"] = enrollment_finish(f, enrollment_claim(f, issue(f)))
    return f


def prepare(f, *, action="replace", account=None, new_connection=None, binding=None,
            challenge=None, confirmation=None, session_expires=None, user="a", rp=RP, epoch=0):
    with connect(f["runtime"]) as db:
        actor(db, f, user)
        if action == "register" and new_connection is None:
            new_connection = uuid4()
        return db.execute(PREPARE, (
            account or (f["empty_account"] if action == "register" else f["account_a"]),
            action, new_connection, rp, challenge or secrets.token_bytes(32),
            binding or secrets.token_bytes(32), confirmation or secrets.token_bytes(32),
            session_expires or clock(db) + 600, epoch, f["oidc_auth_time"],
        )).fetchone()


def claim(f, attempt, *, user="a", rp=None, binding=None, oidc_time=None, epoch=0):
    with connect(f["runtime"]) as db:
        actor(db, f, user)
        return db.execute(CLAIM, (
            attempt["attempt_id"], rp or attempt["rp_id"], binding or attempt["session_binding"],
            epoch, f["oidc_auth_time"] if oidc_time is None else oidc_time,
        )).fetchone()


def finish(f, attempt, *, counter=0, be=True, bs=False, checked_at=None, user="a", epoch=0):
    with connect(f["runtime"]) as db:
        actor(db, f, user)
        return db.execute(FINISH, (
            attempt["attempt_id"], attempt["rp_id"], attempt["session_binding"],
            counter, be, bs, clock(db) if checked_at is None else checked_at,
            epoch, f["oidc_auth_time"],
        )).fetchone()


def read_grant(f, grant, *, user="a", binding=None, oidc_time=None, epoch=0):
    with connect(f["runtime"]) as db:
        actor(db, f, user)
        return db.execute(READ_GRANT, (
            grant["grant_id"], grant["rp_id"], binding or grant["session_binding"], epoch,
            f["oidc_auth_time"] if oidc_time is None else oidc_time,
        )).fetchone()


def confirm(f, grant, *, confirmation=None, user="a", binding=None, epoch=0):
    with connect(f["runtime"]) as db:
        actor(db, f, user)
        return db.execute(CONFIRM, (
            grant["grant_id"], grant["rp_id"], binding or grant["session_binding"],
            confirmation or grant["confirmation_hash"], epoch, f["oidc_auth_time"],
        )).fetchone()


def state(f, attempt):
    with connect(f["admin"]) as db:
        return db.execute(
            "SELECT state FROM platform.passkey_action_proofs WHERE proof_id=%s",
            (attempt["attempt_id"],),
        ).fetchone()["state"]


def test_complete_one_use_verification_receipts_keep_original_oidc_claims(proof_database):
    f = proof_database
    attempt = prepare(f)
    assert tuple(attempt) == ATTEMPT_COLUMNS
    assert attempt["target"] == {
        "action": "replace", "platform_account_id": str(f["account_a"]),
        "connection_id": str(f["connection_a"]), "expected_revision": 1, "expected_storage": 1,
    }
    assert set(attempt["metadata"]) == {"tenant_id", "auth_epoch", "account", "connection"}
    assert attempt["metadata"]["account"]["name"] == "Metadata A"
    assert attempt["expires_at"] <= attempt["prepared_at"] + 120
    assert attempt["public_key"] == f["key"]["public_key"]
    assert claim(f, attempt) == attempt
    grant = finish(f, attempt, bs=True)
    assert tuple(grant) == GRANT_COLUMNS
    assert grant["passkey_version"] == 2 and grant["checked_at"] > f["oidc_auth_time"]
    assert grant["expires_at"] <= min(grant["checked_at"] + 120, grant["session_expires_at"])
    assert read_grant(f, grant) == confirm(f, grant) == grant
    denied(lambda: confirm(f, grant))
    denied(lambda: read_grant(f, grant))
    denied(lambda: finish(f, attempt))
    denied(lambda: claim(f, attempt))
    with connect(f["admin"]) as db:
        proof = db.execute(
            "SELECT oidc_auth_time,state FROM platform.passkey_action_proofs WHERE proof_id=%s",
            (attempt["attempt_id"],),
        ).fetchone()
        assert proof == {"oidc_auth_time": f["oidc_auth_time"], "state": "confirmed"}
        assert db.execute(
            "SELECT event FROM platform.passkey_action_audit WHERE proof_id=%s ORDER BY occurred_at",
            (attempt["attempt_id"],),
        ).fetchall() == [{"event": event} for event in ("prepared", "claimed", "granted", "confirmed")]
        current = db.execute(
            "SELECT credential_revision,storage_version,status FROM platform.credential_connections "
            "WHERE tenant_id=%s AND connection_id=%s", (f["tenant_a"], f["connection_a"]),
        ).fetchone()
        assert current == {"credential_revision": 1, "storage_version": 1, "status": "active"}


def test_claim_commit_precedes_crypto_and_failed_crypto_cannot_reclaim(proof_database):
    f, binding = proof_database, secrets.token_bytes(32)
    attempt = prepare(f, binding=binding)
    with connect(f["runtime"]) as db:
        actor(db, f)
        db.execute(CLAIM, (attempt["attempt_id"], RP, binding, 0, f["oidc_auth_time"]))
        denied(lambda: db.execute(FINISH, (
            attempt["attempt_id"], RP, binding, 0, True, False, clock(db), 0, f["oidc_auth_time"],
        )))
    assert state(f, attempt) == "prepared"  # Same-transaction error rolled back the claim.
    claim(f, attempt)  # This one is committed separately before crypto.
    denied(lambda: finish(f, attempt, be=False))
    assert state(f, attempt) == "claimed"
    denied(lambda: claim(f, attempt))
    assert read_key(f)["storage_version"] == 1


@pytest.mark.parametrize("phase", ["claim", "finish", "read", "confirm"])
def test_actor_epoch_and_revocation_rechecked_at_every_phase(proof_database, phase):
    f = proof_database
    attempt = prepare(f)
    if phase != "claim":
        claim(f, attempt)
    if phase in ("read", "confirm"):
        grant = finish(f, attempt)
    with connect(f["admin"]) as db:
        version = 2 if phase in ("read", "confirm") else 1
        db.execute(REVOKE, (attempt["passkey_id"], version, uuid4()))
    operation = {
        "claim": lambda: claim(f, attempt, epoch=1),
        "finish": lambda: finish(f, attempt, epoch=1),
        "read": lambda: read_grant(f, grant, epoch=1),
        "confirm": lambda: confirm(f, grant, epoch=1),
    }[phase]
    denied(operation)


@pytest.mark.parametrize("change", ["name", "status", "connection", "role", "reauth", "inactive"])
def test_target_metadata_and_actor_changes_reject_grant_publication(proof_database, change):
    f = proof_database
    attempt = prepare(f)
    claim(f, attempt)
    with connect(f["admin"]) as db:
        if change in ("name", "status"):
            db.execute("UPDATE platform.accounts SET " + change + "=%s WHERE tenant_id=%s AND id=%s",
                       ("Changed" if change == "name" else "paused", f["tenant_a"], f["account_a"]))
        elif change == "connection":
            db.execute("UPDATE platform.credential_connections SET status='revoked',storage_version=2 "
                       "WHERE tenant_id=%s AND connection_id=%s", (f["tenant_a"], f["connection_a"]))
        elif change == "role":
            db.execute("UPDATE platform.memberships SET role='viewer' WHERE tenant_id=%s AND user_id=%s",
                       (f["tenant_a"], f["user_a"]))
        elif change == "reauth":
            db.execute("UPDATE platform.users SET reauth_after=clock_timestamp() WHERE id=%s", (f["user_a"],))
        else:
            db.execute("UPDATE platform.users SET active=false WHERE id=%s", (f["user_a"],))
    denied(lambda: finish(f, attempt), "40001" if change in ("name", "status", "connection") else "42501")
    assert state(f, attempt) == "claimed"
    with connect(f["admin"]) as db:
        assert db.execute("SELECT storage_version FROM platform.passkey_credentials WHERE passkey_id=%s",
                          (attempt["passkey_id"],)).fetchone()["storage_version"] == 1


def test_changed_metadata_after_grant_rejects_read_and_confirm(proof_database):
    f = proof_database
    attempt = prepare(f)
    claim(f, attempt)
    grant = finish(f, attempt)
    with connect(f["admin"]) as db:
        db.execute("UPDATE platform.accounts SET name='New preview name' WHERE tenant_id=%s AND id=%s",
                   (f["tenant_a"], f["account_a"]))
    denied(lambda: read_grant(f, grant), "40001")
    denied(lambda: confirm(f, grant), "40001")
    assert state(f, attempt) == "granted"


def test_preview_nonce_and_session_binding_cannot_cross_tabs_or_users(proof_database):
    f = proof_database
    attempt = prepare(f)
    denied(lambda: claim(f, attempt, binding=secrets.token_bytes(32)))
    denied(lambda: claim(f, attempt, user="b"))
    denied(lambda: claim(f, attempt, rp="other.local.test"))
    denied(lambda: claim(f, attempt, oidc_time=f["oidc_auth_time"] + 1))
    assert state(f, attempt) == "prepared"
    claim(f, attempt)
    grant = finish(f, attempt)
    denied(lambda: confirm(f, grant, confirmation=secrets.token_bytes(32)))
    denied(lambda: confirm(f, grant, binding=secrets.token_bytes(32)))
    denied(lambda: confirm(f, grant, user="b"))
    denied(lambda: read_grant(f, grant, oidc_time=f["oidc_auth_time"] + 1))
    assert state(f, attempt) == "granted"
    assert confirm(f, grant) == grant


def test_same_tenant_peer_cannot_use_factor_or_existing_other_owner_connection(proof_database):
    f = proof_database
    with connect(f["admin"]) as db:
        db.execute("INSERT INTO platform.memberships(tenant_id,user_id,role) VALUES(%s,%s,'owner')",
                   (f["tenant_a"], f["user_b"]))
    attempt = prepare(f)
    with connect(f["runtime"]) as db:
        actor(db, f, user="b", tenant="a")
        denied(lambda: db.execute(CLAIM, (
            attempt["attempt_id"], RP, attempt["session_binding"], 0, f["oidc_auth_time"],
        )))
    denied(lambda: prepare(f, account=f["account_b"]))  # Cross tenant.
    denied(lambda: prepare(f, account=uuid4()))  # Same indistinguishable denied result.


@pytest.mark.parametrize("change", ["backup_eligibility", "old_time", "future_time", "counter"])
def test_verified_result_must_match_current_key_and_actual_fresh_clock(proof_database, change):
    f = proof_database
    attempt = prepare(f)
    claim(f, attempt)
    options = {
        "backup_eligibility": {"be": False},
        "old_time": {"checked_at": f["oidc_auth_time"]},
        "future_time": {"checked_at": attempt["prepared_at"] + 130},
        "counter": {"counter": 4294967296},
    }[change]
    denied(lambda: finish(f, attempt, **options), "22023" if change == "counter" else "42501")
    assert state(f, attempt) == "claimed"
    assert read_key(f)["storage_version"] == 1


def test_zero_counter_replay_uses_persistent_challenge_and_factor_version(proof_database):
    f = proof_database
    first = prepare(f)
    second = prepare(f)
    claim(f, first)
    claim(f, second)
    grant = finish(f, first)
    denied(lambda: finish(f, second), "40001")
    denied(lambda: prepare(f, challenge=first["challenge"]))
    assert read_grant(f, grant) == grant
    assert read_key(f)["storage_version"] == 2
    confirm(f, grant)
    # Terminal rows still reserve this RP-wide challenge.
    denied(lambda: prepare(f, challenge=first["challenge"]))


def test_another_assertion_cas_invalidates_a_previously_published_preview(proof_database):
    f = proof_database
    attempt = prepare(f)
    claim(f, attempt)
    grant = finish(f, attempt)
    update_counter(f, read_key(f))
    denied(lambda: read_grant(f, grant), "40001")
    denied(lambda: confirm(f, grant), "40001")
    assert state(f, attempt) == "granted"


@pytest.mark.parametrize("counter", [0, 2, 3])
def test_counter_regression_rolls_back_grant_and_keeps_committed_claim(proof_database, counter):
    f = proof_database
    update_counter(f, f["key"], counter=3)
    attempt = prepare(f)
    claim(f, attempt)
    denied(lambda: finish(f, attempt, counter=counter))
    assert state(f, attempt) == "claimed"
    assert read_key(f)["sign_count"] == 3 and read_key(f)["storage_version"] == 2


@pytest.mark.parametrize("mutation", ["challenge", "binding", "confirmation", "rp", "action",
                                     "extra_new_connection", "session_expired", "session_overflow"])
def test_prepare_input_bounds_fail_before_a_proof_is_published(proof_database, mutation):
    f = proof_database
    with connect(f["runtime"]) as db:
        actor(db, f)
        values = [f["account_a"], "replace", None, RP, secrets.token_bytes(32),
                  secrets.token_bytes(32), secrets.token_bytes(32), clock(db) + 600,
                  0, f["oidc_auth_time"]]
        index, value, code = {
            "challenge": (4, b"x" * 31, "22023"),
            "binding": (5, b"x" * 33, "22023"),
            "confirmation": (6, b"x" * 31, "22023"),
            "rp": (3, "Cockpit.local.test", "22023"),
            "action": (1, "live", "22023"),
            "extra_new_connection": (2, uuid4(), "22023"),
            "session_expired": (7, clock(db) - 1, "42501"),
            "session_overflow": (7, 9007199254740992, "22023"),
        }[mutation]
        values[index] = value
        denied(lambda: db.execute(PREPARE, values), code)
    with connect(f["admin"]) as db:
        assert db.execute("SELECT count(*) AS n FROM platform.passkey_action_proofs WHERE user_id=%s",
                          (f["user_a"],)).fetchone()["n"] == 0


@pytest.mark.parametrize("action", ["register", "replace", "revoke"])
def test_targets_match_action_policy_and_preserve_paused_revoke(proof_database, action):
    f = proof_database
    if action == "revoke":
        with connect(f["admin"]) as db:
            db.execute("UPDATE platform.accounts SET status='paused' WHERE tenant_id=%s AND id=%s",
                       (f["tenant_a"], f["account_a"]))
        denied(lambda: prepare(f))
    attempt = prepare(f, action=action)
    assert attempt["target"]["action"] == action
    assert ("expected_revision" in attempt["target"]) is (action != "register")
    claim(f, attempt)
    assert confirm(f, finish(f, attempt))["target"] == attempt["target"]


@pytest.mark.parametrize("phase", ["claim", "finish", "confirm"])
def test_concurrent_identical_requests_publish_one_result(proof_database, phase):
    f, barrier = proof_database, Barrier(2)
    attempt = prepare(f)
    if phase != "claim":
        claim(f, attempt)
    if phase == "confirm":
        grant = finish(f, attempt)
    def run():
        barrier.wait(timeout=5)
        try:
            operation = {"claim": lambda: claim(f, attempt),
                         "finish": lambda: finish(f, attempt),
                         "confirm": lambda: confirm(f, grant)}[phase]
            return "ok", operation()
        except psycopg.Error as error:
            return "error", error.sqlstate
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: run(), range(2)))
    assert sorted(result[0] for result in outcomes) == ["error", "ok"]
    assert next(value for label, value in outcomes if label == "error") == "42501"


@pytest.mark.parametrize("phase", ["claim", "finish", "read", "confirm"])
def test_lock_wait_past_session_deadline_cannot_publish_or_mutate(proof_database, phase):
    f = proof_database
    with connect(f["admin"]) as db:
        deadline = clock(db) + 3
    attempt = prepare(f, session_expires=deadline)
    if phase != "claim":
        claim(f, attempt)
    if phase in ("read", "confirm"):
        grant = finish(f, attempt)
    pids = Queue()
    with ThreadPoolExecutor(max_workers=1) as pool:
        with connect(f["admin"]) as blocking:
            blocking.execute("SELECT platform.passkey_slot(%s,%s,%s)", (f["tenant_a"], f["user_a"], RP))
            def run():
                with connect(f["runtime"]) as db:
                    actor(db, f)
                    pids.put(db.info.backend_pid)
                    statement, values = {
                        "claim": (CLAIM, (attempt["attempt_id"], RP, attempt["session_binding"], 0, f["oidc_auth_time"])),
                        "finish": (FINISH, (attempt["attempt_id"], RP, attempt["session_binding"],
                                           0, True, False, deadline - 1, 0, f["oidc_auth_time"])),
                        "read": (READ_GRANT, (grant["grant_id"], RP, grant["session_binding"], 0, f["oidc_auth_time"])) if phase == "read" else (None, None),
                        "confirm": (CONFIRM, (grant["grant_id"], RP, grant["session_binding"],
                                             grant["confirmation_hash"], 0, f["oidc_auth_time"])) if phase == "confirm" else (None, None),
                    }[phase]
                    try:
                        db.execute(statement, values)
                    except psycopg.Error as error:
                        return error.sqlstate
                    return "unexpected_success"
            future = pool.submit(run)
            pid, stop = pids.get(timeout=5), monotonic() + 1
            while not blocking.execute(
                "SELECT 1 FROM pg_catalog.pg_locks WHERE pid=%s AND locktype='advisory' AND NOT granted",
                (pid,),
            ).fetchone():
                assert monotonic() < stop
                sleep(0.02)
            remaining = blocking.execute(
                "SELECT %s-extract(epoch FROM clock_timestamp()) AS n", (deadline,),
            ).fetchone()["n"]
            sleep(max(0, float(remaining)) + 0.05)
        assert future.result(timeout=5) == "42501"
    assert state(f, attempt) == {"claim": "prepared", "finish": "claimed",
                                 "read": "granted", "confirm": "granted"}[phase]
    assert read_key(f)["storage_version"] == (1 if phase in ("claim", "finish") else 2)


def test_bounded_live_prepared_claimed_and_granted_capacity(proof_database):
    f = proof_database
    attempts = [prepare(f) for _ in range(8)]
    denied(lambda: prepare(f))
    claim(f, attempts[0])
    denied(lambda: prepare(f))
    grant = finish(f, attempts[0])
    denied(lambda: prepare(f))  # Grants count too; a quick finish does not free capacity.
    confirm(f, grant)
    assert prepare(f)["attempt_id"] not in {attempt["attempt_id"] for attempt in attempts}


def test_registration_account_slot_blocks_real_missing_row_insertion_until_confirm_commits(proof_database):
    f = proof_database
    attempt = prepare(f, action="register")
    claim(f, attempt)
    grant = finish(f, attempt)
    pids = Queue()
    with connect(f["admin"]) as db:
        envelope = db.execute(
            "SELECT envelope FROM platform.credential_connections WHERE tenant_id=%s AND connection_id=%s",
            (f["tenant_a"], f["connection_a"]),
        ).fetchone()["envelope"]
    with ThreadPoolExecutor(max_workers=1) as pool:
        with connect(f["runtime"]) as confirming:
            actor(confirming, f)
            confirming.execute(CONFIRM, (
                grant["grant_id"], RP, grant["session_binding"], grant["confirmation_hash"],
                0, f["oidc_auth_time"],
            ))
            def insert():
                with connect(f["admin"]) as db:
                    pids.put(db.info.backend_pid)
                    # The actual 003/004 registration writer uses this account
                    # SHARE boundary before inserting a missing connection row.
                    db.execute("SELECT 1 FROM platform.accounts WHERE tenant_id=%s AND id=%s FOR SHARE",
                               (f["tenant_a"], f["empty_account"]))
                    db.execute(
                        "INSERT INTO platform.credential_connections"
                        "(tenant_id,user_id,platform_account_id,connection_id,broker_uid,"
                        "credential_revision,storage_version,status,envelope) "
                        "VALUES(%s,%s,%s,%s,%s,1,1,'active',%s)",
                        (f["tenant_a"], f["user_a"], f["empty_account"], uuid4(),
                         str(10**19 + uuid4().int % 10**19), Jsonb(envelope)),
                    )
                return "inserted"
            future = pool.submit(insert)
            pid, stop = pids.get(timeout=5), monotonic() + 2
            while not confirming.execute(
                "SELECT 1 FROM pg_catalog.pg_locks WHERE pid=%s AND NOT granted", (pid,),
            ).fetchone():
                assert monotonic() < stop
                sleep(0.02)
            assert not future.done()
        assert future.result(timeout=5) == "inserted"
    assert state(f, attempt) == "confirmed"


def test_private_storage_helpers_and_research_execution_are_denied(proof_database):
    f = proof_database
    public = (
        "passkey_action_prepare(uuid,text,uuid,text,bytea,bytea,bytea,bigint,bigint,bigint)",
        "passkey_action_claim(uuid,text,bytea,bigint,bigint)",
        "passkey_action_finish(uuid,text,bytea,bigint,boolean,boolean,bigint,bigint,bigint)",
        "passkey_action_read_grant(uuid,text,bytea,bigint,bigint)",
        "passkey_action_confirm(uuid,text,bytea,bytea,bigint,bigint)",
    )
    private = (
        "passkey_action_metadata(uuid)", "passkey_action_locked(uuid,text,bytea,bigint,bigint)",
        "passkey_action_clock(platform.passkey_action_proofs)",
        "passkey_action_attempt_view(platform.passkey_action_proofs)",
        "passkey_action_grant_view(platform.passkey_action_proofs)", "guard_passkey_action_proof()",
    )
    with connect(f["admin"]) as db:
        for role in ("investalo_runtime", "investalo_research_worker", "investalo_credentials_worker"):
            for table in ("passkey_action_proofs", "passkey_action_audit"):
                assert not db.execute(
                    "SELECT has_table_privilege(%s,%s,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE') AS allowed",
                    (role, "platform." + table),
                ).fetchone()["allowed"]
                assert db.execute(
                    "SELECT relrowsecurity,relforcerowsecurity FROM pg_catalog.pg_class WHERE oid=%s::regclass",
                    ("platform." + table,),
                ).fetchone() == {"relrowsecurity": True, "relforcerowsecurity": True}
            for function in public + private:
                assert db.execute("SELECT has_function_privilege(%s,%s,'EXECUTE') AS allowed",
                                  (role, "platform." + function)).fetchone()["allowed"] is (
                    role == "investalo_runtime" and function in public
                )
        for function in public:
            assert db.execute(
                "SELECT p.prosecdef,p.proconfig,r.rolname AS owner FROM pg_catalog.pg_proc p "
                "JOIN pg_catalog.pg_roles r ON r.oid=p.proowner WHERE p.oid=%s::regprocedure",
                ("platform." + function,),
            ).fetchone() == {"prosecdef": True, "proconfig": ["search_path=pg_catalog"], "owner": "investalo_migration"}
    for table in ("passkey_action_proofs", "passkey_action_audit"):
        with connect(f["runtime"]) as db:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                db.execute("SELECT * FROM platform." + table)
    with connect(f["admin"]) as db:
        actor(db, f)
        denied(lambda: db.execute(CLAIM, (uuid4(), RP, secrets.token_bytes(32), 0, f["oidc_auth_time"])))


def test_proof_snapshots_transitions_and_audit_are_immutable(proof_database):
    f = proof_database
    attempt = prepare(f)
    for field, value in (("session_binding", secrets.token_bytes(32)),
                         ("confirmation_hash", secrets.token_bytes(32)),
                         ("oidc_auth_time", f["oidc_auth_time"] + 1),
                         ("expires_at", attempt["expires_at"] + 1),
                         ("target", Jsonb({"action": "register"}))):
        with connect(f["admin"]) as db:
            denied(lambda: db.execute(
                "UPDATE platform.passkey_action_proofs SET " + field + "=%s WHERE proof_id=%s",
                (value, attempt["attempt_id"]),
            ))
    for table in ("passkey_action_proofs", "passkey_action_audit"):
        for operation in ("DELETE FROM ", "TRUNCATE "):
            with connect(f["admin"]) as db:
                with pytest.raises(psycopg.Error) as failure:
                    db.execute(operation + "platform." + table)
                assert failure.value.sqlstate in ("42501", "0A000")
