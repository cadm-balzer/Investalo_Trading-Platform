"""Actual008 lifecycle checks using fixture LOGINs, synthetic consent and keys.

No HTTP, physical WebAuthn, broker probe or credential write executor is enabled.
"""
import base64
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from hashlib import sha256
import json
import os
import secrets
from threading import Barrier, Event
from time import sleep
from uuid import UUID, uuid4

import psycopg
from psycopg.types.json import Jsonb
import pytest

from conftest import connect_as
from test_passkey_authorization_flow import (
    AUTHORIZE, ORIGIN, PREPARE, RP, actor, clock, enroll, receipt, token,
)

CONSUME = "SELECT platform.credential_consume_passkey_authorization(%s::jsonb) AS id"
LOCK = "SELECT platform.credential_lock_passkey_authorization(%s::jsonb) AS valid"


def claims(r):
    part = token(r).split(".")[1]
    return json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))


def worker(statement, c, identity="a"):
    with connect_as(identity) as db:
        return db.execute(statement, (Jsonb(c),)).fetchone()


def rejected(callback, code="42501"):
    with pytest.raises(psycopg.Error) as failure:
        callback()
    assert failure.value.sqlstate == code
    assert str(failure.value).splitlines()[0] in {"access_denied", "invalid_record", "concurrent_change"}


def state(r):
    with connect_as("admin") as db:
        return db.execute(
            "SELECT state,consumed_claims,consumed_by,consume_transaction,lock_transaction "
            "FROM platform.passkey_credential_authorizations WHERE authorization_id=%s",
            (UUID(r["authorization_id"]),),
        ).fetchone()


def purpose_prepare(f, *, origin=ORIGIN, body_hash=None, session_seconds=600, enrolled=False):
    if not enrolled:
        enroll(f)
    with connect_as("runtime") as db:
        actor(db, f)
        old_time = clock(db) - 600
        prepared = db.execute(PREPARE, (
            f["account_a"], "register", uuid4(), RP, origin, secrets.token_bytes(32),
            secrets.token_bytes(32), secrets.token_bytes(32), body_hash or sha256(b"synthetic-body").hexdigest(),
            clock(db) + session_seconds, 0, old_time,
        )).fetchone()
    return prepared, old_time


def purpose_grant(f, p, old_time, *, checked_offset=0):
    with connect_as("runtime") as db:
        actor(db, f)
        db.execute("SELECT * FROM platform.passkey_action_claim(%s,%s,%s,%s,%s)",
                   (p["attempt_id"], RP, p["session_binding"], 0, old_time)).fetchone()
    with connect_as("runtime") as db:
        actor(db, f)
        return db.execute("SELECT * FROM platform.passkey_action_finish(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                          (p["attempt_id"], RP, p["session_binding"], 0, True, False,
                           clock(db) + checked_offset, 0, old_time)).fetchone()


def authorize(f, p, g, old_time, **changes):
    values = dict(authorization=p["authorization_id"], grant=g["grant_id"], rp=RP, origin=ORIGIN,
                  binding=p["session_binding"], confirmation=p["confirmation_hash"], epoch=0, oidc_time=old_time)
    values.update(changes)
    with connect_as("runtime") as db:
        actor(db, f)
        return db.execute(AUTHORIZE, tuple(values.values())).fetchone()["receipt"]


def test_receipt_digest_and_purpose_frozen_before_assertion(credential_database):
    f = credential_database
    p, old_time = purpose_prepare(f)
    with connect_as("admin") as db:
        row = db.execute(
            "SELECT a.state,a.receipt,a.body_sha256,a.metadata_sha256,"
            "encode(sha256(convert_to(p.metadata::text,'UTF8')),'hex') AS digest "
            "FROM platform.passkey_credential_authorizations a JOIN platform.passkey_action_proofs p USING(proof_id) "
            "WHERE a.authorization_id=%s", (p["authorization_id"],),
        ).fetchone()
    assert row["state"] == "prepared" and row["receipt"] is None
    assert row["metadata_sha256"] == p["metadata_sha256"] == row["digest"]
    assert row["body_sha256"] == sha256(b"synthetic-body").hexdigest()
    g = purpose_grant(f, p, old_time)
    r = authorize(f, p, g, old_time)
    assert len(r) == 23 and r["oidc_auth_time"] == old_time < r["checked_at"]
    assert len({r[k] for k in ("authorization_id", "proof_id", "grant_id")}) == 3
    assert r["kind"] == "passkey-credential-authorization/1"
    assert r["prepared_at"] <= r["checked_at"] <= r["authorized_at"] < r["expires_at"]
    assert r["expires_at"] <= min(r["checked_at"] + 120, r["session_expires_at"])
    assert "synthetic-body" not in json.dumps(r)


@pytest.mark.parametrize("origin", [
    "http://cockpit.local.test", "https://cockpit.local.test/", "https://Cockpit.local.test",
    "https://cockpit.local.test:443", "https://cockpit.local.test:08443", "https://other.local.test",
    "https://cockpit.local.test:65536", "https://cockpit.local.test?x=1", "https://u@cockpit.local.test",
])
def test_prepare_rejects_noncanonical_or_wrong_origin(credential_database, origin):
    rejected(lambda: purpose_prepare(credential_database, origin=origin), "22023")


@pytest.mark.parametrize("field,value", [
    ("authorization", uuid4()), ("grant", uuid4()), ("origin", "https://other.local.test:8443"),
    ("binding", b"x" * 32), ("confirmation", b"x" * 32), ("oidc_time", 1), ("epoch", 1),
])
def test_authorize_context_mismatch_does_not_consume_grant(credential_database, field, value):
    f = credential_database
    p, old_time = purpose_prepare(f)
    g = purpose_grant(f, p, old_time)
    rejected(lambda: authorize(f, p, g, old_time, **{field: value}))
    r = authorize(f, p, g, old_time)
    assert r["grant_id"] == str(g["grant_id"])
    rejected(lambda: authorize(f, p, g, old_time))


def test_verification_only_confirm_cannot_become_purpose_authority(credential_database):
    f = credential_database
    p, old_time = purpose_prepare(f)
    g = purpose_grant(f, p, old_time)
    with connect_as("runtime") as db:
        actor(db, f)
        db.execute("SELECT * FROM platform.passkey_action_confirm(%s,%s,%s,%s,%s,%s)",
                   (g["grant_id"], RP, p["session_binding"], p["confirmation_hash"], 0, old_time)).fetchone()
    rejected(lambda: authorize(f, p, g, old_time))
    with connect_as("admin") as db:
        assert db.execute("SELECT state,receipt FROM platform.passkey_credential_authorizations WHERE authorization_id=%s",
                          (p["authorization_id"],)).fetchone() == {"state": "prepared", "receipt": None}


def test_future_007_check_cannot_issue_invalid_ip038_purpose_receipt(credential_database):
    f = credential_database
    p, old_time = purpose_prepare(f)
    g = purpose_grant(f, p, old_time, checked_offset=5)
    rejected(lambda: authorize(f, p, g, old_time))
    with connect_as("admin") as db:
        assert db.execute("SELECT state FROM platform.passkey_action_proofs WHERE proof_id=%s",
                          (p["attempt_id"],)).fetchone()["state"] == "granted"
        assert db.execute("SELECT state,receipt FROM platform.passkey_credential_authorizations WHERE authorization_id=%s",
                          (p["authorization_id"],)).fetchone() == {"state": "prepared", "receipt": None}


def test_ordinary007_prepare_has_no_purpose_row_or_attach_authority(credential_database):
    f = credential_database
    enroll(f)
    with connect_as("runtime") as db:
        actor(db, f)
        p = db.execute("SELECT * FROM platform.passkey_action_prepare(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                       (f["account_a"], "register", uuid4(), RP, secrets.token_bytes(32),
                        secrets.token_bytes(32), secrets.token_bytes(32), clock(db) + 600, 0, clock(db) - 600)).fetchone()
    with connect_as("admin") as db:
        assert db.execute("SELECT count(*) AS n FROM platform.passkey_credential_authorizations WHERE proof_id=%s",
                          (p["attempt_id"],)).fetchone()["n"] == 0
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with connect_as("runtime") as db:
            db.execute("INSERT INTO platform.passkey_credential_authorizations(proof_id,origin,metadata_sha256,body_sha256) "
                       "VALUES(%s,%s,%s,%s)", (p["attempt_id"], ORIGIN, "a" * 64, "b" * 64))


@pytest.mark.parametrize("action", ["register", "replace", "revoke"])
def test_global_consume_and_same_claims_later_lock(credential_database, action):
    r, _ = receipt(credential_database, action)
    c = claims(r)
    assert worker(CONSUME, c)["id"] == UUID(r["authorization_id"])
    rejected(lambda: worker(CONSUME, c))
    other = deepcopy(c)
    other["jti"] = str(uuid4())
    rejected(lambda: worker(CONSUME, other))
    rejected(lambda: worker(LOCK, other))
    with connect_as("a") as db:
        assert db.execute(LOCK, (Jsonb(c),)).fetchone()["valid"] is True
        assert db.execute(LOCK, (Jsonb(c),)).fetchone()["valid"] is True
    rejected(lambda: worker(LOCK, c))
    s = state(r)
    assert s["state"] == "locked" and s["consumed_claims"] == c
    assert s["consumed_by"] == os.environ["CREDENTIAL_TEST_USER_A"]
    assert s["consume_transaction"] != s["lock_transaction"]


def test_same_transaction_consume_then_lock_rejected_and_rolls_back(credential_database):
    r, _ = receipt(credential_database, "register")
    c = claims(r)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with connect_as("a") as db:
            db.execute(CONSUME, (Jsonb(c),))
            db.execute(LOCK, (Jsonb(c),))
    assert state(r)["state"] == "authorized"
    assert worker(CONSUME, c)["id"] == UUID(r["authorization_id"])


@pytest.mark.parametrize("field", ["jti", "iat", "exp"])
def test_later_lock_cannot_replace_authenticated_claims(credential_database, field):
    r, _ = receipt(credential_database, "register")
    c = claims(r)
    worker(CONSUME, c)
    changed = deepcopy(c)
    changed[field] = str(uuid4()) if field == "jti" else changed[field] - 1
    rejected(lambda: worker(LOCK, changed))
    assert state(r)["state"] == "consumed"
    worker(LOCK, c)


@pytest.mark.parametrize("identity", ["b", "unbound", "runtime", "research"])
def test_wrong_login_and_forged_gucs_cannot_consume(credential_database, identity):
    f = credential_database
    r, _ = receipt(f, "register")
    c = claims(r)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with connect_as(identity) as db:
            actor(db, f)
            db.execute(CONSUME, (Jsonb(c),))
    assert state(r)["state"] == "authorized"


@pytest.mark.parametrize("field,value,code", [
    ("authorization_kind", "credential-authorization/1", "22023"), ("aud", "investalo-credentials", "22023"),
    ("iss", "other", "22023"), ("htm", "GET", "22023"), ("htu", "/v1/credentials/bitget/replace", "22023"),
    ("origin", "https://cockpit.local.test:9443", "42501"), ("body_sha256", "b" * 64, "42501"),
    ("metadata_sha256", "b" * 64, "42501"), ("sub", "different", "42501"),
    ("oidc_auth_time", 1, "42501"), ("session_binding", "b" * 64, "42501"),
    ("proof_id", str(uuid4()), "42501"), ("grant_id", str(uuid4()), "42501"),
    ("passkey_id", str(uuid4()), "42501"), ("passkey_version", 3, "42501"),
    ("auth_epoch", True, "22023"), ("iat", 1.0, "22023"), ("exp", 9007199254740992, "22023"),
    ("jti", "INVALID", "22023"), ("body_sha256", "B" * 64, "22023"),
    ("origin", "https://cockpit.local.test:443", "22023"),
])
def test_exact_claims_context_schema_and_body_reject_before_consumption(credential_database, field, value, code):
    r, _ = receipt(credential_database, "register")
    c = claims(r)
    c[field] = value
    rejected(lambda: worker(CONSUME, c), code)
    assert state(r)["state"] == "authorized"
    worker(CONSUME, claims(r))


@pytest.mark.parametrize("change", ["missing", "extra", "null", "array", "target_extra", "target_cas", "id_collision"])
def test_exact_claims_and_target_shapes(credential_database, change):
    r, _ = receipt(credential_database, "register")
    c = claims(r)
    if change == "missing":
        del c["jti"]
    elif change == "extra":
        c["amr"] = ["mfa"]
    elif change == "null":
        c["target"] = None
    elif change == "array":
        c = [c]
    elif change == "target_extra":
        c["target"]["credentials"] = {"secret": "synthetic"}
    elif change == "target_cas":
        c["target"]["expected_storage"] = 1
    else:
        c["proof_id"] = c["authorization_id"]
    rejected(lambda: worker(CONSUME, c), "22023")
    assert state(r)["state"] == "authorized"


@pytest.mark.parametrize("phase", ["consume", "lock"])
@pytest.mark.parametrize("change", ["actor", "membership", "epoch", "reauth", "name", "status", "factor", "cas"])
def test_current_authority_rechecked_at_both_phases(credential_database, phase, change):
    f = credential_database
    r, _ = receipt(f, "replace")
    c = claims(r)
    if phase == "lock":
        worker(CONSUME, c)
    with connect_as("admin") as db:
        if change == "actor":
            db.execute("UPDATE platform.users SET active=false WHERE id=%s", (f["user_a"],))
        elif change == "membership":
            db.execute("UPDATE platform.memberships SET active=false WHERE tenant_id=%s AND user_id=%s",
                       (f["tenant_a"], f["user_a"]))
        elif change == "epoch":
            db.execute("UPDATE platform.users SET auth_epoch=auth_epoch+1 WHERE id=%s", (f["user_a"],))
        elif change == "reauth":
            db.execute("UPDATE platform.users SET reauth_after=clock_timestamp() WHERE id=%s", (f["user_a"],))
        elif change == "name":
            db.execute("UPDATE platform.accounts SET name='Changed frozen metadata' WHERE id=%s", (f["account_a"],))
        elif change == "status":
            db.execute("UPDATE platform.accounts SET status='paused' WHERE id=%s", (f["account_a"],))
        elif change == "cas":
            db.execute("UPDATE platform.credential_connections SET storage_version=storage_version+1 WHERE connection_id=%s",
                       (UUID(r["target"]["connection_id"]),))
    if change == "factor":
        with connect_as("runtime") as db:
            actor(db, f)
            db.execute("SELECT * FROM platform.passkey_assertion_cas(%s,%s,%s,%s,%s,%s)",
                       (UUID(r["passkey_id"]), r["passkey_version"], 0, False, 0, r["oidc_auth_time"]))
    rejected(lambda: worker(CONSUME if phase == "consume" else LOCK, c),
             "40001" if change in {"name", "status", "factor", "cas"} else "42501")
    assert state(r)["state"] == ("authorized" if phase == "consume" else "consumed")


def test_concurrent_new_jtis_share_one_durable_consume(credential_database):
    r, _ = receipt(credential_database, "register")
    barrier = Barrier(2)
    def attempt():
        c = claims(r)
        barrier.wait(timeout=5)
        try:
            return worker(CONSUME, c)["id"]
        except psycopg.errors.InsufficientPrivilege:
            return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: attempt(), range(2)))
    assert results.count(UUID(r["authorization_id"])) == 1 and results.count(None) == 1
    assert state(r)["state"] == "consumed"


@pytest.mark.parametrize("phase", ["consume", "lock"])
def test_administrative_factor_revocation_invalidates_durable_authority(credential_database, phase):
    f = credential_database
    r, _ = receipt(f, "register")
    c = claims(r)
    if phase == "lock":
        worker(CONSUME, c)
    with connect_as("admin") as db:
        revoked = db.execute("SELECT * FROM platform.passkey_admin_revoke(%s,%s,%s)",
                             (UUID(r["passkey_id"]), r["passkey_version"], uuid4())).fetchone()
        assert revoked["status"] == "revoked"
    rejected(lambda: worker(CONSUME if phase == "consume" else LOCK, c))
    assert state(r)["state"] == ("authorized" if phase == "consume" else "consumed")


def test_jti_cannot_move_between_two_durable_authorizations(credential_database):
    f = credential_database
    first, _ = receipt(f, "register")
    first_claims = claims(first)
    worker(CONSUME, first_claims)
    p, old_time = purpose_prepare(f, enrolled=True)
    second = authorize(f, p, purpose_grant(f, p, old_time), old_time)
    second_claims = claims(second)
    second_claims["jti"] = first_claims["jti"]
    rejected(lambda: worker(CONSUME, second_claims))
    assert state(first)["state"] == "consumed" and state(second)["state"] == "authorized"
    second_claims["jti"] = str(uuid4())
    worker(CONSUME, second_claims)


def test_concurrent_final_lock_commits_once(credential_database):
    r, _ = receipt(credential_database, "register")
    c = claims(r)
    worker(CONSUME, c)
    barrier = Barrier(2)
    def attempt():
        barrier.wait(timeout=5)
        try:
            return worker(LOCK, c)["valid"]
        except psycopg.errors.InsufficientPrivilege:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: attempt(), range(2))) == [False, True]
    assert state(r)["state"] == "locked"


def test_register_final_lock_holds_the_missing_connection_account_slot(credential_database):
    f = credential_database
    r, _ = receipt(f, "register")
    c = claims(r)
    worker(CONSUME, c)
    entered = Event()
    # Credential LOGINs cannot read accounts directly. Use the actual trusted
    # primitive inside a savepoint then roll it back after proving it waits.
    def registration_primitive():
        encode = lambda n: base64.b64encode(b"\x01" * n).decode("ascii")
        envelope = dict(schema_version="credential-envelope/1", kek_id="synthetic-lock-only",
                        payload_nonce=encode(12), wrap_nonce=encode(12),
                        wrapped_dek=encode(48), ciphertext=encode(32))
        with connect_as("a") as db:
            db.execute("SAVEPOINT synthetic_registration")
            entered.set()
            db.execute("SELECT connection_id FROM platform.credential_create(%s,%s,%s,%s,%s)",
                       (f["account_a"], uuid4(), str(10**19 + uuid4().int % 10**19), None, Jsonb(envelope)))
            db.execute("ROLLBACK TO SAVEPOINT synthetic_registration")
            return True
    with ThreadPoolExecutor(max_workers=1) as pool:
        with connect_as("a") as db:
            assert db.execute(LOCK, (Jsonb(c),)).fetchone()["valid"] is True
            pending = pool.submit(registration_primitive)
            assert entered.wait(3)
            sleep(0.1)
            assert not pending.done()
        assert pending.result(timeout=5) is True
    with connect_as("admin") as db:
        assert db.execute("SELECT 1 FROM platform.credential_connections WHERE platform_account_id=%s",
                          (f["account_a"],)).fetchone() is None


def test_expiry_rechecked_after_rp_lock_wait(credential_database):
    f = credential_database
    p, old_time = purpose_prepare(f, session_seconds=4)
    g = purpose_grant(f, p, old_time)
    r = authorize(f, p, g, old_time)
    c = claims(r)
    started = Event()
    def waiting():
        started.set()
        try:
            worker(CONSUME, c)
        except psycopg.errors.InsufficientPrivilege:
            return "denied"
        return "unexpected"
    with ThreadPoolExecutor(max_workers=1) as pool:
        with connect_as("admin") as db:
            db.execute("SELECT platform.passkey_slot(%s,%s,%s)", (f["tenant_a"], f["user_a"], RP))
            future = pool.submit(waiting)
            assert started.wait(3)
            sleep(0.1)
            assert clock(db) < r["expires_at"] and not future.done()
            # Synthetic proof deadline only; statement and lock waits are bounded.
            sleep(max(0, r["expires_at"] - clock(db)) + 0.05)
        assert future.result(timeout=5) == "denied"
    assert state(r)["state"] == "authorized"


@pytest.mark.parametrize("table,command", [
    ("passkey_credential_authorizations", "UPDATE {table} SET origin='https://changed.invalid'"),
    ("passkey_credential_authorizations", "UPDATE {table} SET body_sha256='" + "a" * 64 + "'"),
    ("passkey_credential_authorizations", "UPDATE {table} SET state='prepared'"),
    ("passkey_credential_authorizations", "UPDATE {table} SET receipt='{}'::jsonb"),
    ("passkey_credential_authorizations", "DELETE FROM {table}"),
    ("passkey_credential_authorizations", "TRUNCATE {table} CASCADE"),
    ("passkey_credential_authorization_audit", "UPDATE {table} SET event='locked'"),
    ("passkey_credential_authorization_audit", "DELETE FROM {table}"),
    ("passkey_credential_authorization_audit", "TRUNCATE {table}"),
])
def test_immutable_purpose_and_append_only_audit(credential_database, table, command):
    receipt(credential_database, "register")
    rejected(lambda: _admin_execute(command.replace("{table}", "platform." + table)))


def _admin_execute(statement):
    with connect_as("admin") as db:
        db.execute(statement)


def test_new_private_tables_force_rls_and_only_boundary_functions_granted(credential_database):
    receipt(credential_database, "register")
    with connect_as("admin") as db:
        for table in ("passkey_credential_authorizations", "passkey_credential_authorization_audit"):
            assert db.execute("SELECT relrowsecurity,relforcerowsecurity FROM pg_class "
                              "WHERE oid=%s::regclass", ("platform." + table,)).fetchone() == {
                "relrowsecurity": True, "relforcerowsecurity": True,
            }
        for role in ("investalo_runtime", "investalo_research_worker", "investalo_credentials_worker"):
            for table in ("passkey_credential_authorizations", "passkey_credential_authorization_audit"):
                assert db.execute("SELECT has_table_privilege(%s,%s,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE') AS p",
                                  (role, "platform." + table)).fetchone()["p"] is False
            assert db.execute("SELECT has_function_privilege(%s,'platform.credential_passkey_authorization_locked(jsonb)','EXECUTE') AS p",
                              (role,)).fetchone()["p"] is False
        assert db.execute("SELECT has_function_privilege('investalo_credentials_worker',"
                          "'platform.credential_consume_passkey_authorization(jsonb)','EXECUTE') AS p").fetchone()["p"] is True
        assert db.execute("SELECT has_function_privilege('investalo_runtime',"
                          "'platform.credential_consume_passkey_authorization(jsonb)','EXECUTE') AS p").fetchone()["p"] is False
