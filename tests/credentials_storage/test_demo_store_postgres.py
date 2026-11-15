"""Actual restricted PostgreSQL, real AEAD, synthetic credentials only."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import json
import os
import secrets
from threading import Barrier
import time
from uuid import uuid4

import psycopg
from psycopg.types.json import Jsonb
import pytest

from investalo_bitget import Credentials, OwnerContext
from investalo_bitget.futures_demo import DemoBinding
from investalo_credentials import AADBinding, KEKRing, SecretPayload, dump_envelope, seal
from investalo_credential_store import CredentialStore, StoreContext, StoreRejected, ErrorCode
from investalo_credential_store.bitget_payload import encode_credentials
from investalo_credential_store.demo_secret_provider import DemoSecretSpec, DemoSecretRejected, open_demo_secret
from investalo_credential_store.demo_store import DemoCredentialStore, DemoStoreAuthority, CREATE_SQL
from conftest import connect_as


@pytest.fixture
def demo_database(credential_database):
    context = credential_database
    with connect_as("admin") as db:
        assert db.execute("SELECT 1 FROM platform.schema_migrations WHERE version='014_demo_credentials'").fetchone()
        db.execute("UPDATE platform.accounts SET mode='bitget_demo',status='ready' WHERE "
                   "(tenant_id,id) IN ((%s,%s),(%s,%s))",
                   (context["tenant_a"], context["account_a"], context["tenant_b"], context["account_b"]))
    return context


def authority(context, who="a", **changes):
    now = time.time_ns() // 1_000_000
    return DemoStoreAuthority(StoreContext(tenant_id=context[f"tenant_{who}"],
        user_id=context[f"user_{who}"], expected_login_role=os.environ[f"CREDENTIAL_TEST_USER_{who.upper()}"]),
        **{"auth_epoch": 0, "auth_time_ms": now-1000, "expires_ms": now+30000, **changes})


def store(context, who="a", authority_override=None):
    return DemoCredentialStore(authority_override or authority(context, who),
                               connect=lambda: connect_as(who, tuple_rows=True))


def ring(active="synthetic-a"):
    return KEKRing((("synthetic-a", b"a"*32), ("synthetic-b", b"b"*32)), active_version=active)


def spec(context, who="a", *, uid=None):
    return DemoSecretSpec(binding=DemoBinding(OwnerContext(context[f"tenant_{who}"], context[f"user_{who}"]),
        context[f"account_{who}"], uuid4(), uid or str(secrets.randbelow(10**18)+1)), parent_uid="0",
        egress_ip="192.0.2.8", provisioning_digest="d"*64, credential_revision=1)


def credentials():
    return Credentials("synthetic-demo-key", "synthetic-demo-secret", "synthetic-demo-passphrase")


def registered(context):
    expected = spec(context)
    client = store(context)
    snapshot = client.register(expected, credentials(), ring())
    return client, expected, snapshot


def rejected(code, operation):
    with pytest.raises(StoreRejected) as error:
        operation()
    assert error.value.code is code
    assert str(error.value) == code.value


def test_actual_demo_roundtrip_fresh_provider_rewrap_and_keyless_paused_revoke(demo_database):
    context = demo_database
    client, expected, original = registered(context)
    b = expected.binding
    fresh = store(context)
    current = fresh.read_snapshot(b, b.owner)
    assert current.spec.record() == expected.record()
    assert dump_envelope(current.envelope) == dump_envelope(original.envelope)
    provider = fresh.provider(expected, expected_storage=1, load_keyring=ring)
    assert encode_credentials(provider(b, b.owner).credentials).reveal() == encode_credentials(credentials()).reveal()
    rotated = fresh.rewrap(expected, expected_storage=1, keyring=ring("synthetic-b"))
    assert rotated.storage_version == 2 and rotated.spec.credential_revision == 1
    assert rotated.envelope.ciphertext == original.envelope.ciphertext
    assert rotated.envelope.payload_nonce == original.envelope.payload_nonce
    assert encode_credentials(open_demo_secret(rotated.envelope, expected, ring("synthetic-b"))).reveal() == encode_credentials(credentials()).reveal()
    with pytest.raises(DemoSecretRejected):
        provider(b, b.owner)  # Expected original storage does not silently follow rewrap.
    with connect_as("admin") as db:
        db.execute("UPDATE platform.accounts SET status='paused' WHERE tenant_id=%s AND id=%s",
                   (context["tenant_a"], context["account_a"]))
    rejected(ErrorCode.ACCESS_DENIED, lambda: client.read_snapshot(b, b.owner))
    assert store(context).revoke(b.credential_ref, expected_revision=1, expected_storage=2) == 3
    rejected(ErrorCode.ACCESS_DENIED, lambda: store(context).read_snapshot(b, b.owner))
    with connect_as("admin") as db:
        rows = db.execute("SELECT action,storage_version FROM platform.demo_credential_audit "
                          "WHERE tenant_id=%s AND connection_id=%s ORDER BY storage_version",
                          (context["tenant_a"], b.credential_ref)).fetchall()
        assert rows == [dict(action=action, storage_version=i)
                        for i, action in enumerate(("register", "rewrap", "revoke"), 1)]
        terminal = db.execute("SELECT status,envelope FROM platform.demo_credential_connections "
                              "WHERE tenant_id=%s AND connection_id=%s",
                              (context["tenant_a"], b.credential_ref)).fetchone()
        assert terminal == dict(status="revoked", envelope=json.loads(dump_envelope(rotated.envelope)))


def test_normal_and_demo_profiles_and_ciphertexts_cannot_cross(demo_database):
    context = demo_database
    client, expected, snapshot = registered(context)
    normal = CredentialStore(authority(context).context, ring(), connect=lambda: connect_as("a", tuple_rows=True))
    rejected(ErrorCode.ACCESS_DENIED, lambda: normal.read(expected.binding.credential_ref))
    normal_binding = AADBinding(tenant_id=context["tenant_a"], user_id=context["user_a"],
        platform_account_id=context["account_a2"], connection_id=uuid4(), broker_uid=expected.binding.broker_uid,
        parent_uid="0", credential_revision=1)
    normal.register(normal_binding, SecretPayload(b"synthetic-normal-profile"))
    demo_alias = DemoBinding(expected.binding.owner, normal_binding.platform_account_id,
                             normal_binding.connection_id, normal_binding.broker_uid)
    rejected(ErrorCode.ACCESS_DENIED, lambda: client.read_snapshot(demo_alias, demo_alias.owner))
    # Envelope shape alone is not a SQL crypto verdict. Wrong-purpose ciphertext
    # persisted by a trusted faulty service still cannot release a credential.
    alien = spec(context, "b")
    encrypted = seal(SecretPayload(b"synthetic-normal-profile"), normal_binding, ring())
    auth = authority(context, "b")
    with connect_as("b") as db:
        db.execute("SELECT * FROM platform.demo_credential_create(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (alien.binding.account_id, alien.binding.credential_ref, alien.binding.broker_uid, "0",
             alien.egress_ip, alien.provisioning_digest, Jsonb(json.loads(dump_envelope(encrypted))),
             *auth.arguments()))
    provider = store(context, "b").provider(alien, expected_storage=1, load_keyring=ring)
    with pytest.raises(DemoSecretRejected):
        provider(alien.binding, alien.binding.owner)
    assert "synthetic-demo-secret" not in dump_envelope(snapshot.envelope)


@pytest.mark.parametrize("change", ("paused", "disconnected", "mode", "currency", "membership", "viewer", "user", "epoch", "reauth"))
def test_actual_current_permission_changes_deny_old_provider(demo_database, change):
    context = demo_database
    client, expected, _ = registered(context)
    b = expected.binding
    provider = client.provider(expected, expected_storage=1, load_keyring=ring)
    provider(b, b.owner)
    with connect_as("admin") as db:
        if change in ("paused", "disconnected"):
            db.execute("UPDATE platform.accounts SET status=%s WHERE tenant_id=%s AND id=%s",
                       (change, context["tenant_a"], context["account_a"]))
        elif change in ("mode", "currency"):
            db.execute("UPDATE platform.accounts SET mode='paper',currency=%s WHERE tenant_id=%s AND id=%s",
                       ("EUR" if change == "currency" else "USDT", context["tenant_a"], context["account_a"]))
        elif change == "membership":
            db.execute("UPDATE platform.memberships SET active=false WHERE tenant_id=%s AND user_id=%s",
                       (context["tenant_a"], context["user_a"]))
        elif change == "viewer":
            db.execute("UPDATE platform.memberships SET role='viewer' WHERE tenant_id=%s AND user_id=%s",
                       (context["tenant_a"], context["user_a"]))
        elif change == "user":
            db.execute("UPDATE platform.users SET active=false WHERE id=%s", (context["user_a"],))
        elif change == "epoch":
            db.execute("UPDATE platform.users SET auth_epoch=1 WHERE id=%s", (context["user_a"],))
        else:
            db.execute("UPDATE platform.users SET reauth_after=clock_timestamp() WHERE id=%s", (context["user_a"],))
    rejected(ErrorCode.ACCESS_DENIED, lambda: client.read_snapshot(b, b.owner))
    with pytest.raises(DemoSecretRejected):
        provider(b, b.owner)


def test_current_permission_is_rechecked_after_actual_decryption(demo_database):
    context = demo_database
    client, expected, _ = registered(context)
    def keys():
        with connect_as("admin") as db:
            db.execute("UPDATE platform.accounts SET status='paused' WHERE tenant_id=%s AND id=%s",
                       (context["tenant_a"], context["account_a"]))
        return ring()
    provider = client.provider(expected, expected_storage=1, load_keyring=keys)
    with pytest.raises(DemoSecretRejected):
        provider(expected.binding, expected.binding.owner)


def test_actual_foreign_same_tenant_unbound_and_guc_claims_are_rejected(demo_database):
    context = demo_database
    client, expected, _ = registered(context)
    with connect_as("admin") as db:
        db.execute("UPDATE platform.credential_role_bindings SET tenant_id=%s WHERE database_role=%s",
                   (context["tenant_a"], os.environ["CREDENTIAL_TEST_USER_B"]))
    peer_context = {**context, "tenant_b": context["tenant_a"]}
    peer = store(peer_context, "b")
    rejected(ErrorCode.ACCESS_DENIED, lambda: peer.read_snapshot(expected.binding, expected.binding.owner))
    rejected(ErrorCode.ACCESS_DENIED, lambda: peer.revoke(expected.binding.credential_ref,
                                                        expected_revision=1, expected_storage=1))
    now = time.time_ns() // 1_000_000
    for who in ("b", "unbound"):
        with connect_as(who) as db:
            db.execute("SELECT set_config('app.tenant_id',%s,true),set_config('app.user_id',%s,true)",
                       (str(context["tenant_a"]), str(context["user_a"])))
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                db.execute("SELECT * FROM platform.demo_credential_read(%s,0,%s,%s)",
                           (expected.binding.credential_ref, now-1000, now+30000))


@pytest.mark.parametrize("kind", ("epoch", "expired", "long", "future_auth", "null"))
def test_actual_authority_bounds_cannot_be_chosen_by_caller(demo_database, kind):
    context = demo_database
    _, expected, _ = registered(context)
    now = time.time_ns() // 1_000_000
    values = dict(epoch=(1, now-1000, now+30000), expired=(0, now-1000, now),
                  long=(0, now-1000, now+120000), future_auth=(0, now+6000, now+30000),
                  null=(None, now-1000, now+30000))
    with connect_as("a") as db:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute("SELECT * FROM platform.demo_credential_read(%s,%s,%s,%s)",
                       (expected.binding.credential_ref, *values[kind]))


def test_stale_cas_and_concurrent_rewrap_have_one_actual_winner(demo_database):
    context = demo_database
    client, expected, _ = registered(context)
    rejected(ErrorCode.CONCURRENT_CHANGE, lambda: client.revoke(expected.binding.credential_ref, expected_revision=1, expected_storage=2))
    barrier = Barrier(2)
    def contender():
        contender_store = store(context)
        barrier.wait(timeout=5)
        try:
            return contender_store.rewrap(expected, expected_storage=1, keyring=ring("synthetic-b")).storage_version
        except StoreRejected as error:
            return error.code.value
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [future.result(timeout=15) for future in (pool.submit(contender), pool.submit(contender))]
    assert sorted(results, key=str) == [2, "concurrent_change"]
    with connect_as("admin") as db:
        assert db.execute("SELECT count(*) AS n FROM platform.demo_credential_audit "
                          "WHERE tenant_id=%s AND connection_id=%s",
                          (context["tenant_a"], expected.binding.credential_ref)).fetchone()["n"] == 2


def test_demo_uid_uniqueness_is_atomic_across_owners(demo_database):
    context = demo_database
    uid, barrier = str(secrets.randbelow(10**18)+1), Barrier(2)
    def contender(who):
        client, expected = store(context, who), spec(context, who, uid=uid)
        barrier.wait(timeout=5)
        try:
            client.register(expected, credentials(), ring())
            return "registered"
        except StoreRejected as error:
            return error.code.value
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [future.result(timeout=15) for future in (pool.submit(contender, "a"), pool.submit(contender, "b"))]
    assert sorted(results) == ["identity_conflict", "registered"]


def test_atomic_audit_failure_rolls_back_secret_mutation(demo_database):
    context = demo_database
    client, expected, original = registered(context)
    with connect_as("admin") as db:
        db.execute("INSERT INTO platform.demo_credential_audit"
                   "(tenant_id,connection_id,user_id,storage_version,credential_revision,action) "
                   "VALUES(%s,%s,%s,2,1,'rewrap')",
                   (context["tenant_a"], expected.binding.credential_ref, context["user_a"]))
    rejected(ErrorCode.IDENTITY_CONFLICT, lambda: client.rewrap(expected, expected_storage=1, keyring=ring("synthetic-b")))
    current = client.read_snapshot(expected.binding, expected.binding.owner)
    assert current.storage_version == 1 and dump_envelope(current.envelope) == dump_envelope(original.envelope)


def test_no_table_or_helper_grants_and_demo_guards_cover_metadata_payload_terminal_audit(demo_database):
    context = demo_database
    client, expected, original = registered(context)
    b = expected.binding
    for who in ("a", "runtime", "research"):
        for table in ("demo_credential_connections", "demo_credential_audit"):
            with connect_as(who) as db:
                with pytest.raises(psycopg.errors.InsufficientPrivilege):
                    db.execute(f"SELECT * FROM platform.{table}")  # Fixed test-only identifiers.
    with connect_as("a") as db:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute("SELECT * FROM platform.demo_credential_owned(%s,0,0,0,false)", (b.credential_ref,))
    for assignment in ("egress_ip='192.0.2.9'", "provisioning_digest=repeat('e',64)",
                       "platform_account_id=gen_random_uuid()", "connection_mode='real_read_only'",
                       "envelope=jsonb_set(envelope,'{ciphertext}',to_jsonb(repeat('A',24)))"):
        with connect_as("admin") as db:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                db.execute(f"UPDATE platform.demo_credential_connections SET {assignment},storage_version=2 "
                           "WHERE tenant_id=%s AND connection_id=%s", (context["tenant_a"], b.credential_ref))
    for statement in ("DELETE FROM platform.demo_credential_connections WHERE connection_id=%s",
                      "TRUNCATE platform.demo_credential_connections,platform.demo_credential_audit",
                      "UPDATE platform.demo_credential_audit SET action='revoke' WHERE connection_id=%s",
                      "TRUNCATE platform.demo_credential_audit"):
        with connect_as("admin") as db:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                db.execute(statement, (b.credential_ref,) if "%s" in statement else None)
    client.revoke(b.credential_ref, expected_revision=1, expected_storage=1)
    with connect_as("admin") as db:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute("UPDATE platform.demo_credential_connections SET status='active',storage_version=3 "
                       "WHERE tenant_id=%s AND connection_id=%s", (context["tenant_a"], b.credential_ref))


def test_demo_rls_function_owner_search_path_and_role_metadata(demo_database):
    with connect_as("admin") as db:
        rows = db.execute("SELECT relname,relrowsecurity,relforcerowsecurity FROM pg_class c "
                          "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='platform' "
                          "AND relname IN ('demo_credential_connections','demo_credential_audit')").fetchall()
        assert len(rows) == 2 and all(r["relrowsecurity"] and r["relforcerowsecurity"] for r in rows)
        functions = db.execute("SELECT proname,prosecdef,proconfig,pg_get_userbyid(proowner) AS owner "
                               "FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
                               "WHERE n.nspname='platform' AND proname LIKE 'demo_credential_%'").fetchall()
        assert len(functions) == 7
        assert all(r["proconfig"] == ["search_path=pg_catalog"] and r["owner"] == "investalo_migration"
                   for r in functions)
        assert all(r["prosecdef"] for r in functions if r["proname"] != "demo_credential_audit_write")


def test_demo_account_gate_rejects_normal_mode_and_non_usdt(demo_database):
    context = demo_database
    expected = spec(context)
    with connect_as("admin") as db:
        with pytest.raises(psycopg.errors.CheckViolation):
            db.execute("UPDATE platform.accounts SET currency='EUR' WHERE tenant_id=%s AND id=%s",
                       (context["tenant_a"], context["account_a"]))
    wrong_binding = DemoBinding(expected.binding.owner, context["account_a2"],
                                expected.binding.credential_ref, expected.binding.broker_uid)
    wrong = DemoSecretSpec(binding=wrong_binding, parent_uid="0", egress_ip="192.0.2.8",
                           provisioning_digest="d"*64, credential_revision=1)
    rejected(ErrorCode.ACCESS_DENIED, lambda: store(context).register(wrong, credentials(), ring()))


def test_actual_set_role_and_forged_service_context_are_rejected(demo_database):
    context = demo_database
    client, expected, _ = registered(context)
    @contextmanager
    def changed_role():
        with connect_as("a", tuple_rows=True) as db:
            db.execute("SET LOCAL ROLE investalo_credentials_worker")
            yield db
    forged = DemoCredentialStore(authority(context), connect=changed_role)
    rejected(ErrorCode.ACCESS_DENIED, lambda: forged.read_snapshot(expected.binding, expected.binding.owner))
    alien_context = {**context, "tenant_a": context["tenant_b"], "user_a": context["user_b"]}
    alien = store(alien_context)
    alien_binding = spec(alien_context).binding
    rejected(ErrorCode.ACCESS_DENIED, lambda: alien.read_snapshot(alien_binding, alien_binding.owner))


def test_expiry_at_final_checkpoint_rolls_back_actual_write_and_audit(demo_database):
    context, written = demo_database, []
    expected = spec(context)
    auth = authority(context, expires_ms=time.time_ns() // 1_000_000 + 1000)
    class DelayedCursor:
        def __init__(self, db):
            self.db, self.actual = db, db.cursor()
        def __enter__(self):
            self.actual.__enter__()
            return self
        def __exit__(self, *args):
            return self.actual.__exit__(*args)
        def fetchone(self):
            return self.actual.fetchone()
        def execute(self, query, params=()):
            self.actual.execute(query, params)
            if query == CREATE_SQL:
                written.append(True)
                self.db.execute("SELECT pg_sleep(1.1)")
    class DelayedConnection:
        autocommit = False
        def __init__(self, db):
            self.db = db
        def cursor(self):
            return DelayedCursor(self.db)
    @contextmanager
    def delayed():
        with connect_as("a", tuple_rows=True) as db:
            yield DelayedConnection(db)
    client = DemoCredentialStore(auth, connect=delayed)
    rejected(ErrorCode.ACCESS_DENIED, lambda: client.register(expected, credentials(), ring()))
    assert written == [True]
    with connect_as("admin") as db:
        for table in ("demo_credential_connections", "demo_credential_audit"):
            assert db.execute(f"SELECT count(*) AS n FROM platform.{table} WHERE connection_id=%s",
                              (expected.binding.credential_ref,)).fetchone()["n"] == 0


def test_unknown_commit_returns_no_success_or_retry_and_can_be_reconciled(demo_database):
    context, opens = demo_database, []
    expected = spec(context)
    @contextmanager
    def lost_ack():
        opens.append(True)
        with connect_as("a", tuple_rows=True) as db:
            yield db
        # Actual transaction committed; caller acknowledgement was lost.
        raise RuntimeError("synthetic-private-driver-password")
    client = DemoCredentialStore(authority(context), connect=lost_ack)
    rejected(ErrorCode.UNAVAILABLE, lambda: client.register(expected, credentials(), ring()))
    assert opens == [True]
    recovered = store(context).read_snapshot(expected.binding, expected.binding.owner)
    assert recovered.spec.record() == expected.record() and recovered.storage_version == 1
    assert encode_credentials(open_demo_secret(recovered.envelope, expected, ring())).reveal() == encode_credentials(credentials()).reveal()


@pytest.mark.parametrize("changes", (dict(auth_epoch=True), dict(auth_epoch=-1),
                                   dict(auth_time_ms=True), dict(expires_ms=10**15)))
def test_authority_rejects_noncanonical_internal_values(demo_database, changes):
    rejected(ErrorCode.INVALID_CONTEXT, lambda: authority(demo_database, **changes))
