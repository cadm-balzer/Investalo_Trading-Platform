"""Actual restricted PostgreSQL and AEAD; only synthetic keys/accounts."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import json
import os
from threading import Barrier
import time
from uuid import uuid4

import psycopg
from psycopg.types.json import Jsonb
import pytest

from conftest import connect_as
from test_demo_store_postgres import authority, credentials, rejected, ring
from investalo_bitget import OwnerContext
from investalo_bitget.futures_demo import DemoBinding
from investalo_credentials import dump_envelope
from investalo_credential_store import StoreRejected, ErrorCode
from investalo_credential_store.demo_store import DemoCredentialStore
from investalo_credential_store.demo_secret_provider import DemoSecretSpec
from investalo_credential_store.demo_trading_secret import (
    DemoTradingSecretRejected, DemoTradingSecretSpec, open_demo_trading_secret,
)
from investalo_credential_store.demo_trading_store import DemoTradingCredentialStore


@pytest.fixture
def trading_database(credential_database):
    f = credential_database
    with connect_as("admin") as db:
        assert db.execute("SELECT 1 FROM platform.schema_migrations WHERE version='018_demo_trading_credentials'").fetchone()
        db.execute("UPDATE platform.accounts SET mode='bitget_demo',status='ready' "
                   "WHERE id IN (%s,%s,%s)", (f["account_a"], f["account_a2"], f["account_b"]))
    return f


def spec(f, *, account=None, uid=None, who="a"):
    return DemoTradingSecretSpec(binding=DemoBinding(OwnerContext(f[f"tenant_{who}"], f[f"user_{who}"]),
        account or f[f"account_{who}"], uuid4(), uid or str(10**18+uuid4().int % 10**18)),
        parent_uid="0", egress_ip="192.0.2.8", authorities=("coow", "cpow", "stow"),
        provisioning_digest="d"*64, credential_revision=1)


def store(f, who="a", *, auth=None, connect=None):
    return DemoTradingCredentialStore(auth or authority(f, who),
        connect=connect or (lambda: connect_as(who, tuple_rows=True)))


def registered(f):
    expected = spec(f)
    client = store(f)
    return client, expected, client.register(expected, credentials(), ring())


def test_actual_roundtrip_restart_provider_rewrap_paused_keyless_revoke(trading_database):
    f = trading_database
    client, expected, original = registered(f)
    fresh = store(f)
    current = fresh.read_snapshot(expected.binding, expected.binding.owner)
    assert current.spec.record() == expected.record()
    assert dump_envelope(current.envelope) == dump_envelope(original.envelope)
    provider = fresh.provider(expected, expected_storage=1, load_keyring=ring)
    lease = provider(expected.binding, expected.binding.owner)
    assert lease.spec.record() == expected.record() and lease.credentials._api_key == credentials()._api_key
    rotated = fresh.rewrap(expected, expected_storage=1, keyring=ring("synthetic-b"))
    assert rotated.storage_version == 2 and rotated.envelope.ciphertext == original.envelope.ciphertext
    assert open_demo_trading_secret(rotated.envelope, expected, ring("synthetic-b"))._api_key == credentials()._api_key
    with pytest.raises(DemoTradingSecretRejected):
        provider(expected.binding, expected.binding.owner)
    with connect_as("admin") as db:
        db.execute("UPDATE platform.accounts SET status='paused' WHERE id=%s", (f["account_a"],))
    rejected(ErrorCode.ACCESS_DENIED, lambda: store(f).read_snapshot(expected.binding, expected.binding.owner))
    assert store(f).revoke(expected.binding.credential_ref, expected_revision=1, expected_storage=2) == 3
    with connect_as("admin") as db:
        rows = db.execute("SELECT action,storage_version FROM platform.demo_credential_audit "
                          "WHERE connection_id=%s ORDER BY storage_version", (expected.binding.credential_ref,)).fetchall()
        assert rows == [dict(action=action, storage_version=n)
                        for n, action in enumerate(("register", "rewrap", "revoke"), 1)]
        row = db.execute("SELECT * FROM platform.demo_credential_connections WHERE connection_id=%s",
                         (expected.binding.credential_ref,)).fetchone()
        assert row["envelope"] == json.loads(dump_envelope(rotated.envelope))
        assert row["authorities"] == ["coow", "cpow", "stow"] and row["status"] == "revoked"


@pytest.mark.parametrize("action", ["read", "rewrap", "revoke"])
def test_old_and_new_sql_functions_cannot_operate_on_other_profile(trading_database, action):
    f = trading_database
    client, expected, _ = registered(f)
    old = DemoCredentialStore(authority(f), connect=lambda: connect_as("a", tuple_rows=True))
    read_spec = DemoSecretSpec(binding=spec(f, account=f["account_a2"]).binding,
        parent_uid="0", egress_ip="192.0.2.8", provisioning_digest="d"*64, credential_revision=1)
    old.register(read_spec, credentials(), ring())
    for adapter, wrong in ((old, expected), (client, read_spec)):
        if action == "read":
            operation = lambda: adapter.read_snapshot(wrong.binding, wrong.binding.owner)
        elif action == "rewrap":
            # Exact spec classes prevent a request before SQL for foreign types.
            with pytest.raises(StoreRejected):
                adapter.rewrap(wrong, expected_storage=1, keyring=ring())
            continue
        else:
            operation = lambda: adapter.revoke(wrong.binding.credential_ref, expected_revision=1, expected_storage=1)
        rejected(ErrorCode.ACCESS_DENIED, operation)
    if action == "rewrap":
        envelope = json.loads(dump_envelope(client.read_snapshot(expected.binding, expected.binding.owner).envelope))
        for name, wrong in (("demo_credential_rewrap", expected), ("demo_trading_credential_rewrap", read_spec)):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with connect_as("a") as db:
                    db.execute(f"SELECT 1 FROM platform.{name}(%s,1,1,%s,%s,%s,%s)",
                               (wrong.binding.credential_ref, Jsonb(envelope), *authority(f).arguments()))


@pytest.mark.parametrize("old_first", [False, True])
def test_shared_uid_and_account_registry_rejects_other_profile_even_after_revoke(trading_database, old_first):
    f = trading_database
    uid = str(10**18+uuid4().int % 10**18)
    trading = spec(f, uid=uid)
    other = spec(f, account=f["account_a2"], uid=uid)
    read = DemoSecretSpec(binding=other.binding if not old_first else trading.binding,
        parent_uid="0", egress_ip="192.0.2.8", provisioning_digest="d"*64, credential_revision=1)
    old = DemoCredentialStore(authority(f), connect=lambda: connect_as("a", tuple_rows=True))
    new = store(f)
    first, first_spec, second, second_spec = (old, read, new, other) if old_first else (new, trading, old, read)
    first.register(first_spec, credentials(), ring())
    rejected(ErrorCode.IDENTITY_CONFLICT, lambda: second.register(second_spec, credentials(), ring()))
    first.revoke(first_spec.binding.credential_ref, expected_revision=1, expected_storage=1)
    rejected(ErrorCode.IDENTITY_CONFLICT, lambda: second.register(second_spec, credentials(), ring()))
    account_alias = spec(f, account=first_spec.binding.account_id)
    if not old_first:
        account_alias = DemoSecretSpec(binding=account_alias.binding, parent_uid="0", egress_ip="192.0.2.8",
                                      provisioning_digest="d"*64, credential_revision=1)
    rejected(ErrorCode.IDENTITY_CONFLICT, lambda: second.register(account_alias, credentials(), ring()))
    with connect_as("admin") as db:
        assert db.execute("SELECT count(*) AS n FROM platform.demo_credential_connections WHERE broker_uid=%s",
                          (uid,)).fetchone()["n"] == 1


@pytest.mark.parametrize("change", ["epoch", "inactive", "viewer", "reauth", "binding", "paused"])
def test_current_actor_and_account_drift_stops_provider_without_cached_secret(trading_database, change):
    f = trading_database
    _, expected, _ = registered(f)
    provider = store(f).provider(expected, expected_storage=1, load_keyring=ring)
    assert provider(expected.binding, expected.binding.owner).credentials._api_key
    with connect_as("admin") as db:
        if change == "epoch":
            db.execute("UPDATE platform.users SET auth_epoch=1 WHERE id=%s", (f["user_a"],))
        elif change == "inactive":
            db.execute("UPDATE platform.users SET active=false WHERE id=%s", (f["user_a"],))
        elif change == "viewer":
            db.execute("UPDATE platform.memberships SET role='viewer' WHERE tenant_id=%s AND user_id=%s",
                       (f["tenant_a"], f["user_a"]))
        elif change == "reauth":
            db.execute("UPDATE platform.users SET reauth_after=clock_timestamp()+interval '1 hour' WHERE id=%s",
                       (f["user_a"],))
        elif change == "paused":
            db.execute("UPDATE platform.accounts SET status='paused' WHERE id=%s", (f["account_a"],))
        else:
            db.execute("UPDATE platform.credential_role_bindings SET user_id=%s WHERE database_role=%s",
                       (f["user_b"], os.environ["CREDENTIAL_TEST_USER_A"]))
    with pytest.raises(DemoTradingSecretRejected):
        provider(expected.binding, expected.binding.owner)


def test_actual_concurrent_storage_cas_and_unknown_committed_create(trading_database):
    f = trading_database
    client, expected, _ = registered(f)
    barrier = Barrier(2)
    def rewrap():
        barrier.wait(timeout=5)
        try:
            return store(f).rewrap(expected, expected_storage=1, keyring=ring("synthetic-b")).storage_version
        except StoreRejected as error:
            return error.code
    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(lambda _: rewrap(), range(2)))
    assert sorted(map(str, outcomes)) == sorted(map(str, (2, ErrorCode.CONCURRENT_CHANGE)))
    next_spec = spec(f, account=f["account_a2"])
    @contextmanager
    def uncertain():
        with connect_as("a", tuple_rows=True) as db:
            yield db
        raise RuntimeError("synthetic missing commit acknowledgement")
    rejected(ErrorCode.UNAVAILABLE, lambda: store(f, connect=uncertain).register(next_spec, credentials(), ring()))
    persisted = store(f).read_snapshot(next_spec.binding, next_spec.binding.owner)
    assert persisted.storage_version == 1 and persisted.spec.record() == next_spec.record()
    rejected(ErrorCode.IDENTITY_CONFLICT, lambda: store(f).register(next_spec, credentials(), ring()))
    with connect_as("admin") as db:
        assert db.execute("SELECT count(*) AS n FROM platform.demo_credential_audit WHERE connection_id=%s",
                          (next_spec.binding.credential_ref,)).fetchone()["n"] == 1


def test_database_rights_guard_and_immutable_metadata(trading_database):
    f = trading_database
    client, expected, snapshot = registered(f)
    for rights in (["coow","cpow"], ["stow","cpow","coow"], ["coow","cpow","stow","wwow"],
                   ["coow","cpow","stow","stow"], None):
        candidate = spec(f, account=f["account_a2"])
        args = (candidate.binding.account_id, candidate.binding.credential_ref, candidate.binding.broker_uid,
            candidate.parent_uid, candidate.egress_ip, candidate.provisioning_digest, Jsonb(rights),
            Jsonb(json.loads(dump_envelope(snapshot.envelope))), *authority(f).arguments())
        with pytest.raises(psycopg.errors.InvalidParameterValue):
            with connect_as("a") as db:
                db.execute("SELECT 1 FROM platform.demo_trading_credential_create(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", args)
    for column, value in (("authorities", Jsonb(["coor","coow","cpow","stow"])),
                          ("profile", "bitget-classic-demo-read-secret/1")):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            with connect_as("admin") as db:
                db.execute(f"UPDATE platform.demo_credential_connections SET {column}=%s,storage_version=2 "
                           "WHERE connection_id=%s", (value, expected.binding.credential_ref))


def metadata(f, account, *, trading=True, who="a", epoch=0):
    name = "demo_trading_credential_action_context" if trading else "demo_credential_action_context"
    with connect_as("runtime") as db:
        for key, value in (("tenant_id", str(f["tenant_a"])), ("user_id", str(f[f"user_{who}"])),
                           ("oidc_issuer", f["issuer"]), ("oidc_subject", f[f"subject_{who}"])):
            db.execute("SELECT set_config(%s,%s,true)", ("app."+key, value))
        return db.execute(f"SELECT platform.{name}(%s,%s,%s) AS result",
                          (account, epoch, int(time.time()))).fetchone()["result"]


def test_actual_runtime_metadata_keeps_profile_private_fields_and_revoked_slot_distinct(trading_database):
    f = trading_database
    empty = metadata(f, f["account_a"])
    assert empty["connection"] is None and empty["key_authorities"] is None
    client, expected, _ = registered(f)
    shown = metadata(f, f["account_a"])
    assert shown["purpose"] == "demo_futures_spot_trading"
    assert shown["profile"] == "bitget-classic-demo-trading-secret/1"
    assert shown["key_authorities"] == ["coow","cpow","stow"]
    for private in ("envelope", "broker_uid", "parent_uid", "egress_ip", "provisioning_digest"):
        assert private not in shown
    for call in (lambda: metadata(f, f["account_a"], trading=False),
                 lambda: metadata(f, f["account_a"], who="b"),
                 lambda: metadata(f, f["account_b"]),
                 lambda: metadata(f, f["account_a"], epoch=1)):
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            call()
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with connect_as("admin") as db:
            db.execute("SELECT platform.demo_credential_passkey_metadata(%s,%s,0,%s,'revoke')",
                       (f["tenant_a"], f["user_a"], f["account_a"]))
    client.revoke(expected.binding.credential_ref, expected_revision=1, expected_storage=1)
    terminal = metadata(f, f["account_a"])
    assert terminal["connection"]["status"] == "revoked" and terminal["connection"]["storage_version"] == 2
    assert terminal["key_authorities"] == ["coow","cpow","stow"]


def test_cross_tenant_uid_conflict_and_unbound_role_cannot_get_secret(trading_database):
    f = trading_database
    _, expected, _ = registered(f)
    other = spec(f, who="b", uid=expected.binding.broker_uid)
    rejected(ErrorCode.IDENTITY_CONFLICT, lambda: store(f, "b").register(other, credentials(), ring()))
    rejected(ErrorCode.ACCESS_DENIED, lambda: store(f, "b").read_snapshot(expected.binding, expected.binding.owner))
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with connect_as("b") as db:
            db.execute("SELECT 1 FROM platform.demo_trading_credential_read(%s,%s,%s,%s)",
                       (expected.binding.credential_ref, *authority(f, "b").arguments()))
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with connect_as("unbound") as db:
            db.execute("SELECT 1 FROM platform.demo_trading_credential_read(%s,%s,%s,%s)",
                       (expected.binding.credential_ref, *authority(f).arguments()))


def test_actual_revoke_during_key_loading_withholds_decrypted_lease(trading_database):
    f = trading_database
    _, expected, _ = registered(f)
    def changed_keyring():
        store(f).revoke(expected.binding.credential_ref, expected_revision=1, expected_storage=1)
        return ring()
    provider = store(f).provider(expected, expected_storage=1, load_keyring=changed_keyring)
    with pytest.raises(DemoTradingSecretRejected):
        provider(expected.binding, expected.binding.owner)
    with connect_as("admin") as db:
        row = db.execute("SELECT status,storage_version FROM platform.demo_credential_connections "
                         "WHERE connection_id=%s", (expected.binding.credential_ref,)).fetchone()
        assert row == dict(status="revoked", storage_version=2)
