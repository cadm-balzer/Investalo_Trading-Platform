"""Actual purpose authority/AEAD writes; synthetic broker and keys only."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from hashlib import sha256
import json
import os
import secrets
from threading import Barrier
from time import time
from uuid import UUID, uuid4

import pytest

from investalo_credential_store import CredentialStore, StoreContext
from investalo_credential_store.bitget_payload import decode_credentials
from investalo_credential_store.passkey_onboarding import PasskeyBitgetOnboarding
from investalo_credential_store.passkey_request_assertion import (
    PasskeyRequestContext, PasskeyRequestVerifier,
)
from investalo_credential_store.request_assertion import OnboardingRejected
from conftest import connect_as
from test_onboarding_flow import Broker, IP, keyring, request
from test_passkey_authorization_flow import (
    AUTHORIZE, KEY, ORIGIN, PREPARE, RP, actor, clock, enroll, token,
)


def issue(f, action, body):
    """One enrolled synthetic factor; purpose frozen before synthetic verdict."""
    target = json.loads(body)
    binding, confirmation = secrets.token_bytes(32), secrets.token_bytes(32)
    with connect_as("runtime") as db:
        actor(db, f)
        oidc_time = clock(db) - 600
        prepared = db.execute(PREPARE, (
            f["account_a"], action,
            UUID(target["connection_id"]) if action == "register" else None,
            RP, ORIGIN, secrets.token_bytes(32), binding, confirmation,
            sha256(body).hexdigest(), clock(db) + 600, 0, oidc_time,
        )).fetchone()
    with connect_as("runtime") as db:
        actor(db, f)
        db.execute("SELECT * FROM platform.passkey_action_claim(%s,%s,%s,%s,%s)",
                   (prepared["attempt_id"], RP, binding, 0, oidc_time)).fetchone()
    with connect_as("runtime") as db:
        actor(db, f)
        granted = db.execute(
            "SELECT * FROM platform.passkey_action_finish(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (prepared["attempt_id"], RP, binding, 0, True, False, clock(db), 0, oidc_time),
        ).fetchone()
    with connect_as("runtime") as db:
        actor(db, f)
        return db.execute(AUTHORIZE, (
            prepared["authorization_id"], granted["grant_id"], RP, ORIGIN,
            binding, confirmation, 0, oidc_time,
        )).fetchone()["receipt"]


def services(f, ring, broker, r, *, connect=None):
    context = StoreContext(tenant_id=f["tenant_a"], user_id=f["user_a"],
                           expected_login_role=os.environ["CREDENTIAL_TEST_USER_A"])
    factory = connect or (lambda: connect_as("a", tuple_rows=True))
    store = CredentialStore(context, ring, connect=factory)
    service = PasskeyBitgetOnboarding(
        context, ring, connect=factory, transport=broker, expected_egress_ip=IP,
        request_context=PasskeyRequestContext(
            tenant_id=f["tenant_a"], user_id=f["user_a"], subject=r["subject"],
            auth_epoch=r["auth_epoch"], oidc_auth_time=r["oidc_auth_time"],
            session_binding=r["session_binding"], session_expires_at=r["session_expires_at"],
        ),
        verifier=PasskeyRequestVerifier(key=KEY, oidc_issuer=f["issuer"],
                                       origin=ORIGIN, clock=lambda: int(time())),
    )
    return store, service


def apply(f, ring, broker, action, body):
    r = issue(f, action, body)
    store, service = services(f, ring, broker, r)
    return store, service.apply(action, token=token(r), body=body), r


def denied(code, callback):
    with pytest.raises(OnboardingRejected) as failure:
        callback()
    assert failure.value.code == code
    assert str(failure.value) == code and failure.value.__suppress_context__


def state(f, r):
    with connect_as("admin") as db:
        authority = db.execute(
            "SELECT state FROM platform.passkey_credential_authorizations "
            "WHERE authorization_id=%s", (UUID(r["authorization_id"]),),
        ).fetchone()["state"]
        stored = db.execute(
            "SELECT status,credential_revision,storage_version FROM platform.credential_connections "
            "WHERE tenant_id=%s AND connection_id=%s",
            (f["tenant_a"], UUID(r["target"]["connection_id"])),
        ).fetchone()
    return authority, stored


def completion(r):
    with connect_as("admin") as db:
        rows = db.execute(
            "SELECT outcome FROM platform.passkey_credential_completion_audit "
            "WHERE authorization_id=%s", (UUID(r["authorization_id"]),),
        ).fetchall()
    return [row["outcome"] for row in rows]


def test_roundtrip_restart_replace_and_paused_keyless_revoke(credential_database, tmp_path):
    f, broker = credential_database, Broker()
    enroll(f)
    ring, provider = keyring(tmp_path / "keys")
    store, initial, r = apply(f, ring, broker, "register", request(f, "register"))
    assert initial.public() == dict(connection_id=str(initial.connection_id),
                                    credential_revision=1, storage_version=1, status="active")
    assert state(f, r) == ("locked", dict(status="active", credential_revision=1, storage_version=1))
    assert completion(r) == ["completed"]
    opened = store.read(initial.connection_id)
    assert opened.snapshot.binding.broker_uid == broker.uid
    assert decode_credentials(opened.payload)._api_key == "synthetic-onboarding-api-key"
    changed = request(f, "replace", initial.connection_id, triple={
        "api_key": "synthetic-passkey-replacement",
        "secret": "synthetic-passkey-secret", "passphrase": "synthetic-passkey-phrase",
    })
    store, replaced, r = apply(f, provider.load(), broker, "replace", changed)
    assert replaced.credential_revision == replaced.storage_version == 2
    assert completion(r) == ["completed"]
    assert decode_credentials(store.read(initial.connection_id).payload)._api_key == "synthetic-passkey-replacement"
    with connect_as("admin") as db:
        db.execute("UPDATE platform.accounts SET status='paused' WHERE tenant_id=%s AND id=%s",
                   (f["tenant_a"], f["account_a"]))
        raw = db.execute("SELECT envelope FROM platform.credential_connections WHERE connection_id=%s",
                         (initial.connection_id,)).fetchone()["envelope"]
    assert "synthetic-passkey-secret" not in json.dumps(raw)
    other, _ = keyring(tmp_path / "unrelated-keys", key_id="unrelated-synthetic")
    _, revoked, r = apply(f, other, broker, "revoke",
                          request(f, "revoke", initial.connection_id, revision=2, storage=2))
    assert revoked.public() == dict(connection_id=str(initial.connection_id),
                                    credential_revision=2, storage_version=3, status="revoked")
    assert state(f, r) == ("locked", dict(status="revoked", credential_revision=2, storage_version=3))
    assert completion(r) == ["completed"]
    assert len(broker.calls) == 2


@pytest.mark.parametrize("patch", [
    {"userId": "99999999999999999999"}, {"parentId": 0},
    {"authorities": ["stow"]}, {"ips": IP + ",203.0.113.20"},
])
def test_failed_replacement_probe_consumes_authority_without_write(credential_database, tmp_path, patch):
    f, broker = credential_database, Broker()
    enroll(f)
    ring, _ = keyring(tmp_path / "keys")
    _, initial, _ = apply(f, ring, broker, "register", request(f, "register"))
    changed = request(f, "replace", initial.connection_id)
    r = issue(f, "replace", changed)
    _, service = services(f, ring, broker, r)
    signed = token(r)
    broker.patch = patch
    denied("broker_rejected", lambda: service.apply("replace", token=signed, body=changed))
    assert state(f, r) == ("consumed", dict(status="active", credential_revision=1, storage_version=1))
    assert completion(r) == ["failed"]
    calls = len(broker.calls)
    denied("access_denied", lambda: service.apply("replace", token=signed, body=changed))
    denied("access_denied", lambda: service.apply("replace", token=token(r), body=changed))
    assert len(broker.calls) == calls


@pytest.mark.parametrize("change", ["epoch", "paused", "factor", "metadata", "expired"])
def test_authority_change_during_probe_blocks_write(credential_database, tmp_path, change):
    f, broker = credential_database, Broker()
    enroll(f)
    ring, _ = keyring(tmp_path / "keys")
    raw = request(f, "register")
    r = issue(f, "register", raw)
    if change == "expired":
        # Issuer already fixed receipt times. Shortening the JWT is legitimate.
        import base64
        import hmac
        signed = token(r)
        header, payload, _ = signed.split(".")
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        claims["exp"] = int(time()) + 2
        encode = lambda data: base64.urlsafe_b64encode(data).rstrip(b"=").decode()
        wire = header + "." + encode(json.dumps(claims, separators=(",", ":")).encode())
        signed = wire + "." + encode(hmac.digest(KEY, wire.encode(), "sha256"))
    else:
        signed = token(r)
    _, service = services(f, ring, broker, r)
    def during_probe():
        with connect_as("admin") as db:
            if change == "epoch":
                db.execute("UPDATE platform.users SET auth_epoch=auth_epoch+1 WHERE id=%s", (f["user_a"],))
            elif change == "paused":
                db.execute("UPDATE platform.accounts SET status='paused' WHERE tenant_id=%s AND id=%s",
                           (f["tenant_a"], f["account_a"]))
            elif change == "metadata":
                db.execute("UPDATE platform.accounts SET name='Changed synthetic account' WHERE tenant_id=%s AND id=%s",
                           (f["tenant_a"], f["account_a"]))
            elif change == "factor":
                db.execute("SELECT * FROM platform.passkey_admin_revoke(%s,%s,%s)",
                           (UUID(r["passkey_id"]), r["passkey_version"], uuid4()))
            else:
                db.execute("SELECT pg_sleep(2.1)")
    broker.before_response = during_probe
    denied("concurrent_change" if change in ("metadata", "paused") else "access_denied",
           lambda: service.apply("register", token=signed, body=raw))
    assert len(broker.calls) == 1
    assert state(f, r) == ("consumed", None)
    assert completion(r) == ["failed"]


def test_concurrent_replay_dispatches_probe_and_persists_only_once(credential_database, tmp_path):
    f, broker = credential_database, Broker()
    enroll(f)
    ring, _ = keyring(tmp_path / "keys")
    raw = request(f, "register")
    r = issue(f, "register", raw)
    _, service = services(f, ring, broker, r)
    signed, barrier = token(r), Barrier(2)
    def contender():
        barrier.wait(timeout=5)
        try:
            return service.apply("register", token=signed, body=raw).status
        except OnboardingRejected as error:
            return error.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [pool.submit(contender) for _ in range(2)]
        outcomes = [future.result(timeout=15) for future in results]
        assert outcomes.count("active") == 1
        assert next(value for value in outcomes if value != "active") in (
            "access_denied", "concurrent_change",
        )
    assert len(broker.calls) == 1
    assert state(f, r) == ("locked", dict(status="active", credential_revision=1, storage_version=1))
    assert completion(r) == ["completed"]


def test_storage_rewrap_during_probe_prevents_stale_replacement(credential_database, tmp_path):
    f, broker = credential_database, Broker()
    enroll(f)
    ring, _ = keyring(tmp_path / "keys")
    store, initial, _ = apply(f, ring, broker, "register", request(f, "register"))
    raw = request(f, "replace", initial.connection_id)
    r = issue(f, "replace", raw)
    _, service = services(f, ring, broker, r)
    broker.before_response = lambda: store.rewrap(initial.connection_id, expected_revision=1, expected_storage=1)
    denied("concurrent_change", lambda: service.apply("replace", token=token(r), body=raw))
    assert state(f, r) == ("consumed", dict(status="active", credential_revision=1, storage_version=2))
    assert completion(r) == ["failed"]


@pytest.mark.parametrize("phase", ["consume", "final"])
def test_lost_commit_ack_does_not_retry_or_overwrite_completion(credential_database, tmp_path, phase):
    f, broker = credential_database, Broker()
    enroll(f)
    ring, _ = keyring(tmp_path / "keys")
    raw = request(f, "register")
    r = issue(f, "register", raw)
    calls = 0
    @contextmanager
    def unknown_commit():
        nonlocal calls
        calls += 1
        fail = calls == (1 if phase == "consume" else 2)
        with connect_as("a", tuple_rows=True) as db:
            yield db
        if fail:
            raise RuntimeError("synthetic lost acknowledgement, must stay redacted")
    _, service = services(f, ring, broker, r, connect=unknown_commit)
    signed = token(r)
    denied("unavailable", lambda: service.apply("register", token=signed, body=raw))
    if phase == "consume":
        assert state(f, r) == ("consumed", None)
        assert completion(r) == []
        assert len(broker.calls) == 0
    else:
        assert state(f, r) == ("locked", dict(status="active", credential_revision=1, storage_version=1))
        assert completion(r) == ["completed"]
        assert len(broker.calls) == 1
    count = len(broker.calls)
    code = "concurrent_change" if phase == "final" else "access_denied"
    # A completed registration changed the frozen account metadata; its stale
    # target is rejected before consume. Neither rejection permits a new probe.
    denied(code, lambda: service.apply("register", token=signed, body=raw))
    denied(code, lambda: service.apply("register", token=token(r), body=raw))
    assert len(broker.calls) == count


def test_final_transaction_rollback_removes_write_lock_and_completion(credential_database, tmp_path):
    f, broker = credential_database, Broker()
    enroll(f)
    ring, _ = keyring(tmp_path / "keys")
    raw = request(f, "register")
    r = issue(f, "register", raw)
    calls = 0
    @contextmanager
    def abort_final():
        nonlocal calls
        calls += 1
        fail = calls == 2
        with connect_as("a", tuple_rows=True) as db:
            yield db
            if fail:
                raise RuntimeError("synthetic final rollback, never log driver detail")
    _, service = services(f, ring, broker, r, connect=abort_final)
    denied("unavailable", lambda: service.apply("register", token=token(r), body=raw))
    assert state(f, r) == ("consumed", None)
    assert completion(r) == ["failed"]
    assert len(broker.calls) == 1


def test_signature_or_body_mismatch_never_consumes_or_dispatches(credential_database, tmp_path):
    f, broker = credential_database, Broker()
    enroll(f)
    ring, _ = keyring(tmp_path / "keys")
    raw = request(f, "register")
    r = issue(f, "register", raw)
    _, service = services(f, ring, broker, r)
    signed = token(r)
    denied("authentication_required", lambda: service.apply("register", token=signed, body=raw + b" "))
    denied("authentication_required", lambda: service.apply("register", token=signed[:-6] + "AAAAAA", body=raw))
    assert state(f, r) == ("authorized", None)
    assert completion(r) == [] and not broker.calls
