"""Exercise the actual CredentialStore client and real 13-column SQL wire."""
import json
import os
import secrets
from uuid import uuid4

import pytest

from investalo_credentials import AADBinding, KEKRing, SecretPayload, dump_envelope
from investalo_credential_store import CredentialStore, ErrorCode, StoreContext, StoreRejected
from conftest import connect_as


def store(context, ring, *, who="a", expected_context=None):
    expected = expected_context or context
    return CredentialStore(
        StoreContext(tenant_id=expected[f"tenant_{who}"], user_id=expected[f"user_{who}"],
                     expected_login_role=os.environ[f"CREDENTIAL_TEST_USER_{who.upper()}"]),
        ring, connect=lambda: connect_as(who, tuple_rows=True),
    )


def bound(context, *, who="a", uid=None, account=None):
    return AADBinding(
        tenant_id=context[f"tenant_{who}"], user_id=context[f"user_{who}"],
        platform_account_id=account or context[f"account_{who}"], connection_id=uuid4(),
        broker_uid=uid or str(secrets.randbelow(10**18) + 1), parent_uid=None,
        credential_revision=1,
    )


def rejected(code, action):
    with pytest.raises(StoreRejected) as failure:
        action()
    assert failure.value.code is code
    assert str(failure.value) == code.value
    assert failure.value.__cause__ is None and failure.value.__suppress_context__


def test_actual_store_roundtrip_replace_rewrap_and_keyless_paused_revoke(credential_database):
    context = credential_database
    key_a, key_b = secrets.token_bytes(32), secrets.token_bytes(32)
    ring_a = KEKRing((("synthetic-a", key_a),), active_version="synthetic-a")
    ring_b = KEKRing((("synthetic-a", key_a), ("synthetic-b", key_b)), active_version="synthetic-b")
    client_a, client_b = store(context, ring_a), store(context, ring_b)
    initial_binding = bound(context)
    snapshot = client_a.register(initial_binding, SecretPayload(b"synthetic-store-initial"))
    assert snapshot.binding.connection_id == initial_binding.connection_id
    assert snapshot.binding.credential_revision == 1 and snapshot.storage_version == 1
    # Fresh connections validate both the tuple-row wire and successful commit.
    opened = client_a.read(initial_binding.connection_id)
    assert opened.payload.reveal() == b"synthetic-store-initial"
    with connect_as("a") as database:
        persisted = database.execute("SELECT * FROM platform.credential_read(%s)", (initial_binding.connection_id,)).fetchone()
    assert persisted["envelope"] == json.loads(dump_envelope(snapshot.envelope))
    replaced = client_a.replace(initial_binding.connection_id, expected_revision=1, expected_storage=1,
                                payload=SecretPayload(b"synthetic-store-replaced"))
    assert replaced.binding.credential_revision == 2 and replaced.storage_version == 2
    assert client_a.read(initial_binding.connection_id).payload.reveal() == b"synthetic-store-replaced"
    rotated = client_b.rewrap(initial_binding.connection_id, expected_revision=2, expected_storage=2)
    assert rotated.binding.credential_revision == 2 and rotated.storage_version == 3
    assert rotated.envelope.ciphertext == replaced.envelope.ciphertext
    assert rotated.envelope.payload_nonce == replaced.envelope.payload_nonce
    assert rotated.envelope.kek_id == "synthetic-b"
    assert client_b.read(initial_binding.connection_id).payload.reveal() == b"synthetic-store-replaced"
    rejected(ErrorCode.KEY_UNAVAILABLE, lambda: client_a.read(initial_binding.connection_id))
    # Revocation needs neither usable account status nor the original KEK.
    unrelated = KEKRing((("synthetic-unrelated", secrets.token_bytes(32)),), active_version="synthetic-unrelated")
    keyless_client = store(context, unrelated)
    rejected(ErrorCode.KEY_UNAVAILABLE, lambda: keyless_client.read(initial_binding.connection_id))
    with connect_as("admin") as database:
        database.execute("UPDATE platform.accounts SET status='paused' WHERE tenant_id=%s AND id=%s",
                         (context["tenant_a"], context["account_a"]))
    rejected(ErrorCode.ACCESS_DENIED, lambda: client_b.read(initial_binding.connection_id))
    assert keyless_client.revoke(initial_binding.connection_id, expected_revision=2, expected_storage=3) == 4
    rejected(ErrorCode.ACCESS_DENIED, lambda: client_b.read(initial_binding.connection_id))
    with connect_as("admin") as database:
        terminal = database.execute(
            "SELECT status,credential_revision,storage_version,envelope FROM platform.credential_connections WHERE tenant_id=%s AND connection_id=%s",
            (context["tenant_a"], initial_binding.connection_id),
        ).fetchone()
    assert (terminal["status"], terminal["credential_revision"], terminal["storage_version"]) == ("revoked", 2, 4)
    assert terminal["envelope"] == json.loads(dump_envelope(rotated.envelope))


def test_actual_store_maps_unique_access_and_sql_cas_rejections_without_partial_writes(credential_database):
    context = credential_database
    ring = KEKRing((("synthetic-service", secrets.token_bytes(32)),), active_version="synthetic-service")
    client_a, client_b = store(context, ring), store(context, ring, who="b")
    owned = bound(context)
    client_a.register(owned, SecretPayload(b"synthetic-store-owner"))
    duplicate_uid = bound(context, who="b", uid=owned.broker_uid)
    rejected(ErrorCode.IDENTITY_CONFLICT, lambda: client_b.register(duplicate_uid, SecretPayload(b"synthetic-duplicate")))
    duplicate_account = bound(context)
    rejected(ErrorCode.IDENTITY_CONFLICT, lambda: client_a.register(duplicate_account, SecretPayload(b"synthetic-duplicate")))
    rejected(ErrorCode.ACCESS_DENIED, lambda: client_b.read(owned.connection_id))
    rejected(ErrorCode.ACCESS_DENIED, lambda: client_b.revoke(owned.connection_id, expected_revision=1, expected_storage=1))
    wrong_context = {**context, "tenant_a": context["tenant_b"], "user_a": context["user_b"]}
    forged = store(context, ring, expected_context=wrong_context)
    rejected(ErrorCode.ACCESS_DENIED, lambda: forged.read(owned.connection_id))
    # Revoke directly reaches SQL; this proves real 40001 -> static client code,
    # rather than only the client's earlier local revision comparison.
    rejected(ErrorCode.CONCURRENT_CHANGE, lambda: client_a.revoke(owned.connection_id, expected_revision=1, expected_storage=2))
    with connect_as("a") as database:
        unchanged = database.execute("SELECT * FROM platform.credential_read(%s)", (owned.connection_id,)).fetchone()
    assert unchanged["status"] == "active" and unchanged["storage_version"] == unchanged["credential_revision"] == 1
    with connect_as("admin") as database:
        assert database.execute(
            "SELECT count(*) AS n FROM platform.credential_connections WHERE tenant_id=%s",
            (context["tenant_b"],),
        ).fetchone()["n"] == 0
    assert client_a.read(owned.connection_id).payload.reveal() == b"synthetic-store-owner"
