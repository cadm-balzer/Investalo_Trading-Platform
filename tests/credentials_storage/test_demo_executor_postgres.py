"""Actual own consume/AEAD/write/completion; synthetic provisioning only."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from hashlib import sha256
import json
import os
import secrets
from threading import Barrier
from time import time
from uuid import UUID, uuid4

import psycopg
from psycopg.types.json import Jsonb
import pytest

from investalo_bitget import Credentials, OwnerContext
from investalo_bitget.futures_demo import DemoBinding
from investalo_credential_store.bitget_payload import encode_credentials
from investalo_credential_store.demo_passkey_assertion import DemoPasskeyRequestVerifier
from investalo_credential_store.demo_passkey_onboarding import DemoPasskeyOnboarding, LOCK_SQL, FINISH_SQL
from investalo_credential_store.demo_secret_provider import DemoSecretSpec, open_demo_secret
from investalo_credential_store.demo_store import CREATE_SQL
from investalo_credential_store.models import StoreContext
from investalo_credential_store.request_assertion import OnboardingRejected
from conftest import connect_as
from test_demo_passkey_postgres import claims, token, context, issued, state, PREPARE, grant, authorize
from test_demo_store_postgres import ring, store
from test_passkey_authorization_flow import actor, clock, RP, ORIGIN, KEY


@pytest.fixture
def own(credential_database):
    f = credential_database
    with connect_as("admin") as db:
        assert db.execute("SELECT 1 FROM platform.schema_migrations WHERE version='016_demo_passkey_completions'").fetchone()
        db.execute("UPDATE platform.accounts SET mode='bitget_demo',status='ready' WHERE tenant_id=%s AND id=%s",
                   (f["tenant_a"], f["account_a"]))
    return f


class Provision:
    """Synthetic trusted adapter, not a native identity/provenance receipt."""
    def __init__(self, hook=None):
        self.uid = str(secrets.randbelow(10**18)+1)
        self.calls, self.spec, self.hook = [], None, hook

    def __call__(self, credentials, **args):
        self.calls.append(True)
        assert type(credentials) is Credentials and args["expires_ms"] > int(time()*1000)
        spec = DemoSecretSpec(binding=DemoBinding(args["owner"], args["account_id"], args["connection_id"], self.uid),
            parent_uid="0", egress_ip="192.0.2.8", provisioning_digest="d"*64, credential_revision=1)
        self.spec = spec
        return self.hook(spec) if self.hook else spec


def service(f, r, provision=None, *, connect=None, keys=None):
    return DemoPasskeyOnboarding(StoreContext(tenant_id=f["tenant_a"], user_id=f["user_a"],
        expected_login_role=os.environ["CREDENTIAL_TEST_USER_A"]),
        connect=connect or (lambda: connect_as("a", tuple_rows=True)),
        verifier=DemoPasskeyRequestVerifier(key=KEY, oidc_issuer=f["issuer"], origin=ORIGIN, clock=lambda: int(time())),
        request_context=context(r), provision=provision or Provision(), load_keyring=keys or ring,
        expected_egress_ip="192.0.2.8")


def rejected(code, operation):
    with pytest.raises(OnboardingRejected) as error:
        operation()
    assert str(error.value) == code and error.value.__suppress_context__


def apply(executor, r, raw, **changes):
    return executor.apply(r["target"]["action"], token=token(claims(r, **changes)), body=raw)


def completion(r):
    with connect_as("admin") as db:
        return db.execute("SELECT outcome,action,credential_revision,storage_version,connection_status,transaction_id "
                          "FROM platform.demo_passkey_credential_completion_audit WHERE authorization_id=%s",
                          (UUID(r["authorization_id"]),)).fetchone()


def stored(f, r):
    with connect_as("admin") as db:
        return db.execute("SELECT status,storage_version,envelope FROM platform.demo_credential_connections "
                          "WHERE tenant_id=%s AND connection_id=%s",
                          (f["tenant_a"], UUID(r["target"]["connection_id"]))).fetchone()


def revoke_issue(f, connection, storage=1):
    raw = json.dumps(dict(platform_account_id=str(f["account_a"]), connection_id=str(connection),
                          expected_revision=1, expected_storage=storage), separators=(",", ":")).encode()
    with connect_as("runtime") as db:
        actor(db, f)
        oidc = clock(db)-600
        p = db.execute(PREPARE, (f["account_a"], "revoke", None, RP, ORIGIN, secrets.token_bytes(32),
            secrets.token_bytes(32), secrets.token_bytes(32), sha256(raw).hexdigest(), clock(db)+600, 0, oidc)).fetchone()
    return authorize(f, p, grant(f, p, oidc), oidc), raw


class Cursor:
    def __init__(self, inner, db, hook):
        self.inner, self.db, self.hook = inner, db, hook
    def __getattr__(self, name):
        return getattr(self.inner, name)
    def execute(self, sql, args=None):
        self.inner.execute(sql, args)
        self.hook(self.db, sql, args)
        return self
    def __enter__(self):
        self.inner.__enter__()
        return self
    def __exit__(self, *args):
        return self.inner.__exit__(*args)


class Connection:
    def __init__(self, inner, hook):
        self.inner, self.hook = inner, hook
    def __getattr__(self, name):
        return getattr(self.inner, name)
    def cursor(self):
        return Cursor(self.inner.cursor(), self.inner, self.hook)


def factory(hook):
    @contextmanager
    def connect():
        with connect_as("a", tuple_rows=True) as db:
            yield Connection(db, hook)
    return connect


def test_actual_roundtrip_atomic_completion_restart_and_paused_keyless_revoke(own):
    f, provision = own, Provision()
    r, raw = issued(f)
    result = apply(service(f, r, provision), r, raw)
    assert result.public() == dict(connection_id=r["target"]["connection_id"],
        credential_revision=1, storage_version=1, status="active")
    assert completion(r)["outcome"] == "completed" and state(r)["state"] == "locked"
    with connect_as("admin") as db:
        row = db.execute("SELECT lock_transaction FROM platform.demo_passkey_credential_authorizations "
                         "WHERE authorization_id=%s", (UUID(r["authorization_id"]),)).fetchone()
        assert row["lock_transaction"] == completion(r)["transaction_id"]
    snapshot = store(f).read_snapshot(provision.spec.binding, provision.spec.binding.owner)
    opened = open_demo_secret(snapshot.envelope, provision.spec, ring())
    assert encode_credentials(opened).reveal() == encode_credentials(Credentials(**{
        "api_key": "synthetic-demo-api", "secret_key": "synthetic-demo-päß", "passphrase": "synthetic-demo-phrase"})).reveal()
    assert "synthetic-demo-päß" not in json.dumps(stored(f, r), ensure_ascii=False)
    original_envelope = stored(f, r)["envelope"]
    with connect_as("admin") as db:
        db.execute("UPDATE platform.accounts SET status='paused' WHERE tenant_id=%s AND id=%s",
                   (f["tenant_a"], f["account_a"]))
    rev, body = revoke_issue(f, result.connection_id)
    calls = []
    def forbidden(*args, **kwargs):
        calls.append(True)
        raise RuntimeError("synthetic-private-key-or-probe-canary")
    revoked = apply(service(f, rev, forbidden, keys=forbidden), rev, body)
    assert revoked.public() == dict(connection_id=str(result.connection_id), credential_revision=1,
                                   storage_version=2, status="revoked")
    assert calls == [] and completion(rev)["outcome"] == "completed"
    assert stored(f, rev)["envelope"] == original_envelope


@pytest.mark.parametrize("fault", ("token", "body", "mode"))
def test_invalid_input_or_account_never_reaches_provisioning_or_keyring(own, fault):
    f, provision, keys = own, Provision(), []
    r, raw = issued(f)
    executor = service(f, r, provision, keys=lambda: keys.append(True))
    if fault == "mode":
        with connect_as("admin") as db:
            db.execute("UPDATE platform.accounts SET mode='read_only' WHERE tenant_id=%s AND id=%s",
                       (f["tenant_a"], f["account_a"]))
    rejected("authentication_required" if fault != "mode" else "access_denied",
        lambda: executor.apply("register", token="bad" if fault == "token" else token(claims(r)),
                               body=raw+b" " if fault == "body" else raw))
    assert provision.calls == [] and keys == [] and state(r)["state"] == "authorized"
    assert stored(f, r) is None and completion(r) is None


@pytest.mark.parametrize("wrong", ("owner", "account", "connection", "ip", "type"))
def test_provisioning_scope_cannot_replace_signed_own_target(own, wrong):
    f = own
    r, raw = issued(f)
    def drift(spec):
        if wrong == "type":
            return {"synthetic": "not-a-private-spec"}
        b = spec.binding
        owner = OwnerContext(f["tenant_b"], f["user_b"]) if wrong == "owner" else b.owner
        return DemoSecretSpec(binding=DemoBinding(owner, uuid4() if wrong == "account" else b.account_id,
            uuid4() if wrong == "connection" else b.credential_ref, b.broker_uid), parent_uid="0",
            egress_ip="192.0.2.9" if wrong == "ip" else spec.egress_ip,
            provisioning_digest=spec.provisioning_digest, credential_revision=1)
    keys = []
    rejected("broker_rejected", lambda: apply(service(f, r, Provision(drift), keys=lambda: keys.append(True)), r, raw))
    assert keys == [] and stored(f, r) is None
    assert state(r)["state"] == "consumed" and completion(r)["outcome"] == "failed"


@pytest.mark.parametrize("change", ("pause", "epoch", "role", "reauth", "factor", "metadata"))
def test_changes_during_provisioning_deny_actual_write(own, change):
    f = own
    r, raw = issued(f)
    def changed(spec):
        with connect_as("admin") as db:
            if change in ("pause", "metadata"):
                db.execute("UPDATE platform.accounts SET "+("status='paused'" if change == "pause" else "name='Changed'")+
                    " WHERE tenant_id=%s AND id=%s", (f["tenant_a"], f["account_a"]))
            elif change == "epoch":
                db.execute("UPDATE platform.users SET auth_epoch=1 WHERE id=%s", (f["user_a"],))
            elif change == "role":
                db.execute("UPDATE platform.memberships SET role='viewer' WHERE tenant_id=%s AND user_id=%s",
                           (f["tenant_a"], f["user_a"]))
            elif change == "reauth":
                db.execute("UPDATE platform.users SET reauth_after=clock_timestamp() WHERE id=%s", (f["user_a"],))
            else:
                db.execute("UPDATE platform.passkey_credentials SET status='revoked',revoked_at=clock_timestamp(),"
                           "storage_version=storage_version+1 WHERE passkey_id=%s", (UUID(r["passkey_id"]),))
        return spec
    with pytest.raises(OnboardingRejected):
        apply(service(f, r, Provision(changed)), r, raw)
    assert stored(f, r) is None and state(r)["state"] == "consumed"
    audit = completion(r)
    assert audit is None if change == "role" else audit["outcome"] == "failed"


@pytest.mark.parametrize("change", ("metadata", "expiry", "finish_error"))
def test_after_actual_write_failure_rolls_back_ciphertext_and_both_audits(own, change):
    f, writes = own, []
    r, raw = issued(f)
    def after(db, sql, args):
        if sql == CREATE_SQL:
            writes.append(True)
            if change == "metadata":
                db.execute("UPDATE platform.accounts SET name='Changed' WHERE tenant_id=%s AND id=%s",
                           (f["tenant_a"], f["account_a"]))
            if change == "expiry":
                db.execute("SELECT pg_sleep(3.1)")
        if sql == FINISH_SQL and args[1] == "completed" and change == "finish_error":
            raise RuntimeError("synthetic-private-completion-canary")
    with pytest.raises(OnboardingRejected):
        apply(service(f, r, connect=factory(after)), r, raw,
              **({"exp": int(time())+3} if change == "expiry" else {}))
    assert writes == [True] and stored(f, r) is None and state(r)["state"] == "consumed"
    assert completion(r)["outcome"] == "failed"
    with connect_as("admin") as db:
        assert db.execute("SELECT count(*) AS n FROM platform.demo_credential_audit WHERE tenant_id=%s AND connection_id=%s",
                         (f["tenant_a"], UUID(r["target"]["connection_id"]))).fetchone()["n"] == 0


@pytest.mark.parametrize("when", ("consume", "final"))
def test_unknown_actual_commit_has_no_success_or_command_retry(own, when):
    f, provision, calls = own, Provision(), []
    r, raw = issued(f)
    @contextmanager
    def lost_ack():
        calls.append(True)
        with connect_as("a", tuple_rows=True) as db:
            yield db
        if len(calls) == (1 if when == "consume" else 2):
            raise RuntimeError("synthetic-private-commit-ack-canary")
    executor = service(f, r, provision, connect=lost_ack)
    rejected("unavailable", lambda: apply(executor, r, raw))
    assert len(provision.calls) == (when == "final")
    assert state(r)["state"] == ("locked" if when == "final" else "consumed")
    assert (stored(f, r) is not None) == (when == "final")
    assert completion(r)["outcome"] == "completed" if when == "final" else completion(r) is None
    rejected("concurrent_change" if when == "final" else "access_denied",
             lambda: apply(executor, r, raw))
    assert len(provision.calls) == (when == "final")


def test_failed_completion_tombstone_blocks_direct_executor_lock(own):
    f = own
    r, raw = issued(f)
    rejected("broker_rejected", lambda: apply(service(f, r, lambda *a, **k: None), r, raw))
    with connect_as("a") as db:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute(LOCK_SQL, (Jsonb(state(r)["consumed_claims"]),))
    assert state(r)["state"] == "consumed" and completion(r)["outcome"] == "failed"


def test_actual_revoke_rollback_preserves_original_ciphertext_and_version(own):
    f, provision = own, Provision()
    initial, raw = issued(f)
    result = apply(service(f, initial, provision), initial, raw)
    before = stored(f, initial)
    r, raw = revoke_issue(f, result.connection_id)
    def failed_finish(db, sql, args):
        if sql == FINISH_SQL and args[1] == "completed":
            raise RuntimeError("synthetic-private-revoke-completion")
    def forbidden(*args, **kwargs):
        raise RuntimeError("synthetic-private-key-or-probe")
    rejected("unavailable", lambda: apply(service(f, r, forbidden, keys=forbidden,
        connect=factory(failed_finish)), r, raw))
    assert stored(f, r) == before and state(r)["state"] == "consumed"
    assert completion(r)["outcome"] == "failed"


@pytest.mark.parametrize("failure", ("missing", "error"))
def test_missing_server_keyring_consumes_without_secret_write(own, failure):
    f, provision = own, Provision()
    r, raw = issued(f)
    def keys():
        if failure == "error":
            raise RuntimeError("synthetic-private-keyloader-canary")
        return None
    rejected("key_unavailable" if failure == "missing" else "unavailable",
             lambda: apply(service(f, r, provision, keys=keys), r, raw))
    assert provision.calls == [True] and stored(f, r) is None
    assert state(r)["state"] == "consumed" and completion(r)["outcome"] == "failed"


def test_actual_concurrent_executor_has_one_provision_and_completion(own):
    f, provision, barrier = own, Provision(), Barrier(2)
    r, raw = issued(f)
    def contender():
        executor = service(f, r, provision)
        barrier.wait(timeout=5)
        try:
            return apply(executor, r, raw).status
        except OnboardingRejected as error:
            return error.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(contender) for _ in range(2)]
        results = [future.result(timeout=15) for future in futures]
    assert sorted(results) == ["access_denied", "active"] and provision.calls == [True]
    assert completion(r)["outcome"] == "completed"


def test_completion_requires_actual_postwrite_state_and_same_final_transaction(own):
    f = own
    r, raw = issued(f)
    executor = service(f, r)
    handle = executor._authorization.consume("register", token=token(claims(r)), body=raw)
    data = state(r)["consumed_claims"]
    with connect_as("a") as db:
        db.execute(LOCK_SQL, (Jsonb(data),))
        with pytest.raises(psycopg.errors.SerializationFailure):
            db.execute(FINISH_SQL, (Jsonb(data), "completed"))
    assert state(r)["state"] == "consumed" and completion(r) is None
    with executor._authorization.lock(handle):
        pass
    with connect_as("a") as db:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute(FINISH_SQL, (Jsonb(data), "completed"))
    assert completion(r) is None and stored(f, r) is None


def test_completion_privileges_and_terminal_audit_guards(own):
    f = own
    r, raw = issued(f)
    apply(service(f, r), r, raw)
    for who in ("runtime", "a", "research"):
        with connect_as(who) as db:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                db.execute("SELECT * FROM platform.demo_passkey_credential_completion_audit")
    for statement in ("DELETE FROM platform.demo_passkey_credential_completion_audit WHERE authorization_id=%s",
                      "UPDATE platform.demo_passkey_credential_completion_audit SET outcome='failed' WHERE authorization_id=%s"):
        with connect_as("admin") as db:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                db.execute(statement, (UUID(r["authorization_id"]),))
    with connect_as("admin") as db:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute("TRUNCATE platform.demo_passkey_credential_completion_audit")
