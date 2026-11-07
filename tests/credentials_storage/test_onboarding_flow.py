"""Actual PostgreSQL/AEAD onboarding with synthetic assertions and broker responses."""
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
import os
import secrets
from threading import Barrier
import time
from uuid import uuid4

import pytest

from investalo_bitget import Credentials
from investalo_bitget.signing import INFO_PATH
from investalo_bitget.transport import ReadResponse
from investalo_credential_store import CredentialStore, StoreContext
from investalo_credential_store.bitget_payload import decode_credentials, encode_credentials
from investalo_credential_store.keyfiles import DevelopmentKeyFileProvider, KeyFile
from investalo_credential_store.onboarding import BitgetOnboarding
from investalo_credential_store.request_assertion import OnboardingRejected, RequestVerifier
from conftest import connect_as
from test_assertions import SIGNING_KEY, make_claims, sign_assertion

IP = "203.0.113.19"


def keyring(directory, *, key_id="synthetic-onboarding"):
    key = secrets.token_bytes(32)
    directory.mkdir(mode=0o700)
    file = directory / "fixture.kek"
    file.write_bytes(key)
    file.chmod(0o400)
    provider = DevelopmentKeyFileProvider(
        str(directory), (KeyFile(key_id, "fixture.kek", sha256(key).hexdigest()),),
        active_version=key_id, development_mode=True,
    )
    return provider.load(), provider


def request(context, action, connection=None, *, revision=1, storage=1, triple=None):
    body = {"platform_account_id": str(context["account_a"]), "connection_id": str(connection or uuid4())}
    if action != "register":
        body.update(expected_revision=revision, expected_storage=storage)
    if action != "revoke":
        body["credentials"] = triple or {
            "api_key": "synthetic-onboarding-api-key", "secret": "synthetic-onboarding-secret",
            "passphrase": "synthetic-onboarding-passphrase",
        }
    return json.dumps(body, separators=(",", ":")).encode()


def assertion(context, action, body, **overrides):
    overrides = {"jti": str(uuid4()), **overrides}
    return sign_assertion(make_claims(
        body=body, action=action, now=int(time.time()),
        tenant_id=str(context["tenant_a"]), subject=context["subject_a"],
        oidc_issuer=context["issuer"], **overrides,
    ))


class Broker:
    def __init__(self):
        self.uid = str(secrets.randbelow(10**18) + 1)
        self.calls = []
        self.patch = {}
        self.before_response = None

    def __call__(self, signed):
        assert signed.path == INFO_PATH and signed.method == "GET"
        self.calls.append(signed.path)
        if self.before_response:
            self.before_response()
        data = {"userId": self.uid, "parentId": None, "authorities": ["stor"], "ips": IP, **self.patch}
        return ReadResponse(200, json.dumps({
            "code": "00000", "requestTime": time.time_ns() // 1_000_000, "data": data,
        }).encode())


def services(context, ring, broker):
    store_context = StoreContext(
        tenant_id=context["tenant_a"], user_id=context["user_a"],
        expected_login_role=os.environ["CREDENTIAL_TEST_USER_A"],
    )
    connect = lambda: connect_as("a", tuple_rows=True)
    store = CredentialStore(store_context, ring, connect=connect)
    onboarding = BitgetOnboarding(
        store_context, ring, connect=connect, transport=broker, expected_egress_ip=IP,
        verifier=RequestVerifier(key=SIGNING_KEY, oidc_issuer=context["issuer"]),
    )
    return store, onboarding


def apply(service, context, action, body, **claims):
    return service.apply(action, token=assertion(context, action, body, **claims), body=body)


def denied(code, operation):
    with pytest.raises(OnboardingRejected) as failure:
        operation()
    assert failure.value.code == code
    assert str(failure.value) == code and failure.value.__suppress_context__


def test_onboarding_roundtrip_restart_replace_and_paused_keyless_revoke(credential_database, tmp_path):
    context, broker = credential_database, Broker()
    ring, provider = keyring(tmp_path / "keys")
    store, service = services(context, ring, broker)
    initial = request(context, "register")
    registered = apply(service, context, "register", initial)
    assert set(registered.public()) == {"connection_id", "credential_revision", "storage_version", "status"}
    assert registered.public()["status"] == "active" and registered.credential_revision == registered.storage_version == 1
    opened = store.read(registered.connection_id)
    assert opened.snapshot.binding.broker_uid == broker.uid
    assert opened.payload.reveal() == encode_credentials(Credentials(
        "synthetic-onboarding-api-key", "synthetic-onboarding-secret", "synthetic-onboarding-passphrase",
    )).reveal()
    restarted_store, restarted_service = services(context, provider.load(), broker)
    assert decode_credentials(restarted_store.read(registered.connection_id).payload)._api_key == "synthetic-onboarding-api-key"
    changed = request(context, "replace", registered.connection_id, triple={
        "api_key": "synthetic-replacement-key", "secret": "synthetic-replacement-secret",
        "passphrase": "synthetic-replacement-passphrase",
    })
    replaced = apply(restarted_service, context, "replace", changed)
    assert replaced.credential_revision == replaced.storage_version == 2
    assert decode_credentials(restarted_store.read(registered.connection_id).payload)._api_key == "synthetic-replacement-key"
    with connect_as("admin") as db:
        db.execute("UPDATE platform.accounts SET status='paused' WHERE tenant_id=%s AND id=%s",
                   (context["tenant_a"], context["account_a"]))
        rows = db.execute("SELECT envelope FROM platform.credential_connections WHERE connection_id=%s",
                          (registered.connection_id,)).fetchall()
    assert "synthetic-replacement-secret" not in json.dumps(rows)
    missing_ring, _ = keyring(tmp_path / "other-keys", key_id="synthetic-unrelated")
    _, keyless_service = services(context, missing_ring, broker)
    final = apply(keyless_service, context, "revoke", request(context, "revoke", registered.connection_id, revision=2, storage=2))
    assert final.status == "revoked" and final.storage_version == 3
    assert len(broker.calls) == 2  # Revocation performs no private broker request.


@pytest.mark.parametrize("patch", [
    {"userId": "99999999999999999999"}, {"parentId": 0},
    {"authorities": ["stow"]}, {"ips": IP + ",203.0.113.20"},
])
def test_replacement_probe_rejects_identity_permissions_or_extra_ips_and_consumes_nonce(credential_database, tmp_path, patch):
    context, broker = credential_database, Broker()
    ring, _ = keyring(tmp_path / "keys")
    store, service = services(context, ring, broker)
    created = apply(service, context, "register", request(context, "register"))
    broker.patch = patch
    changed = request(context, "replace", created.connection_id)
    token = assertion(context, "replace", changed)
    denied("broker_rejected", lambda: service.apply("replace", token=token, body=changed))
    assert store.read(created.connection_id).snapshot.storage_version == 1
    calls = len(broker.calls)
    denied("access_denied", lambda: service.apply("replace", token=token, body=changed))
    assert len(broker.calls) == calls


def test_onboarding_subject_mismatch_is_denied_before_broker_dispatch(credential_database, tmp_path):
    context, broker = credential_database, Broker()
    ring, _ = keyring(tmp_path / "keys")
    _, service = services(context, ring, broker)
    raw = request(context, "register")
    token = assertion(context, "register", raw, sub=context["subject_b"])
    denied("access_denied", lambda: service.apply("register", token=token, body=raw))
    assert not broker.calls


def test_signed_malformed_or_client_selected_fields_never_reach_broker(credential_database, tmp_path):
    context, broker = credential_database, Broker()
    ring, _ = keyring(tmp_path / "keys")
    _, service = services(context, ring, broker)
    good = json.loads(request(context, "register"))
    variants = (
        {**good, "expected_egress_ip": IP},
        {**good, "broker_uid": "12345"},
        {**good, "platform_account_id": str(uuid4()).replace("-", "")},
        {**good, "credentials": {**good["credentials"], "passphrase": True}},
        {**good, "credentials": {**good["credentials"], "secret": "synthetic\x00secret"}},
        {**good, "credentials": {"api_key": "synthetic"}},
    )
    for variant in variants:
        raw = json.dumps(variant).encode()
        denied("invalid_request", lambda: apply(service, context, "register", raw))
    raw = request(context, "register")
    duplicate = raw[:-1] + b',"connection_id":"' + str(uuid4()).encode() + b'"}'
    denied("invalid_request", lambda: apply(service, context, "register", duplicate))
    assert not broker.calls
    with connect_as("admin") as db:
        assert db.execute("SELECT count(*) AS n FROM platform.credential_onboarding_requests WHERE tenant_id=%s",
                          (context["tenant_a"],)).fetchone()["n"] == 0


@pytest.mark.parametrize("change", ["epoch", "paused", "expired"])
def test_inflight_authorization_change_blocks_final_write(credential_database, tmp_path, change):
    context, broker = credential_database, Broker()
    ring, _ = keyring(tmp_path / "keys")
    _, service = services(context, ring, broker)
    def during_probe():
        with connect_as("admin") as db:
            if change == "epoch":
                db.execute("UPDATE platform.users SET auth_epoch=auth_epoch+1 WHERE id=%s", (context["user_a"],))
            elif change == "paused":
                db.execute("UPDATE platform.accounts SET status='paused' WHERE tenant_id=%s AND id=%s",
                           (context["tenant_a"], context["account_a"]))
            else:
                db.execute("SELECT pg_sleep(2.1)")
    broker.before_response = during_probe
    raw = request(context, "register")
    token = assertion(context, "register", raw, **({"exp": int(time.time()) + 2} if change == "expired" else {}))
    denied("access_denied", lambda: service.apply("register", token=token, body=raw))
    assert len(broker.calls) == 1
    with connect_as("admin") as db:
        assert db.execute("SELECT count(*) AS n FROM platform.credential_connections WHERE tenant_id=%s",
                          (context["tenant_a"],)).fetchone()["n"] == 0


def test_concurrent_replay_dispatches_probe_and_persists_only_once(credential_database, tmp_path):
    context, broker = credential_database, Broker()
    ring, _ = keyring(tmp_path / "keys")
    _, service = services(context, ring, broker)
    raw = request(context, "register")
    token, barrier = assertion(context, "register", raw), Barrier(2)
    def contender():
        barrier.wait(timeout=5)
        try:
            return service.apply("register", token=token, body=raw).status
        except OnboardingRejected as error:
            return error.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [pool.submit(contender) for _ in range(2)]
        assert sorted(future.result(timeout=15) for future in results) == ["access_denied", "active"]
    assert len(broker.calls) == 1


def test_storage_version_change_during_probe_prevents_stale_key_replacement(credential_database, tmp_path):
    context, broker = credential_database, Broker()
    ring, _ = keyring(tmp_path / "keys")
    store, service = services(context, ring, broker)
    created = apply(service, context, "register", request(context, "register"))
    broker.before_response = lambda: store.rewrap(created.connection_id, expected_revision=1, expected_storage=1)
    raw = request(context, "replace", created.connection_id)
    denied("concurrent_change", lambda: apply(service, context, "replace", raw))
    current = store.read(created.connection_id).snapshot
    assert current.binding.credential_revision == 1 and current.storage_version == 2
