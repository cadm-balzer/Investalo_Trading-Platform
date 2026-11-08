"""Real008 issuance/HS256/private-client consumption; synthetic fixtures only.

SQL receives a synthetic trusted WebAuthn verdict. These checks do not exercise
a physical device, broker probe, browser route or003 credential mutation.
"""
import base64
from datetime import timedelta
from hashlib import sha256
import hmac
import json
import os
import secrets
from time import time
from uuid import UUID, uuid4

import pytest
from psycopg.types.json import Jsonb

from investalo_credential_store.models import StoreContext
from investalo_credential_store.passkey_authorization import PasskeyAuthorizationClient
from investalo_credential_store.passkey_request_assertion import (
    PasskeyRequestContext, PasskeyRequestVerifier,
)
from investalo_credential_store.request_assertion import OnboardingRejected
from conftest import connect_as

RP, ORIGIN = "cockpit.local.test", "https://cockpit.local.test:8443"
KEY = b"synthetic-authorization-contract-key"
PREPARE = "SELECT * FROM platform.passkey_credential_prepare(" + ",".join(["%s"] * 12) + ")"
AUTHORIZE = "SELECT platform.passkey_credential_authorize(" + ",".join(["%s"] * 8) + ") AS receipt"


def clock(db):
    return db.execute(
        "SELECT floor(extract(epoch FROM clock_timestamp()))::bigint AS n"
    ).fetchone()["n"]


def actor(db, f):
    for name, value in {
        "app.tenant_id": str(f["tenant_a"]), "app.user_id": str(f["user_a"]),
        "app.oidc_issuer": f["issuer"], "app.oidc_subject": f["subject_a"],
    }.items():
        db.execute("SELECT set_config(%s,%s,true)", (name, value))


def enroll(f):
    token_hash, handle = secrets.token_bytes(32), secrets.token_bytes(32)
    with connect_as("admin") as db:
        db.execute(
            "SELECT platform.passkey_issue_enrollment(%s,%s,%s,%s,%s,%s,%s,%s)",
            (f["tenant_a"], f["user_a"], RP, token_hash, handle, 0,
             db.execute("SELECT clock_timestamp() AS n").fetchone()["n"]
             + timedelta(seconds=300), uuid4()),
        )
    binding = secrets.token_bytes(32)
    with connect_as("runtime") as db:
        actor(db, f)
        claim = db.execute(
            "SELECT * FROM platform.passkey_claim_enrollment(%s,%s,%s,%s,%s)",
            (token_hash, RP, binding, 0, clock(db)),
        ).fetchone()
    with connect_as("runtime") as db:
        actor(db, f)
        db.execute(
            "SELECT * FROM platform.passkey_finish_enrollment(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (claim["claim_id"], binding, secrets.token_bytes(32),
             b"synthetic-key-not-a-WebAuthn-verification", 0, True, False, 0, clock(db)),
        ).fetchone()


def receipt(f, action):
    enroll(f)
    connection = uuid4()
    if action != "register":
        encode = lambda n: base64.b64encode(b"\x01" * n).decode("ascii")
        envelope = dict(
            schema_version="credential-envelope/1", kek_id="synthetic-contract-only",
            payload_nonce=encode(12), wrap_nonce=encode(12),
            wrapped_dek=encode(48), ciphertext=encode(32),
        )
        with connect_as("admin") as db:
            db.execute(
                "INSERT INTO platform.credential_connections"
                "(tenant_id,user_id,platform_account_id,connection_id,broker_uid,"
                "credential_revision,storage_version,status,envelope)"
                "VALUES(%s,%s,%s,%s,%s,1,1,'active',%s)",
                (f["tenant_a"], f["user_a"], f["account_a"], connection,
                 str(10**19 + uuid4().int % 10**19), Jsonb(envelope)),
            )
    payload = dict(platform_account_id=str(f["account_a"]), connection_id=str(connection))
    if action != "register":
        payload.update(expected_revision=1, expected_storage=1)
    if action != "revoke":
        payload["credentials"] = dict(api_key="synthetic-api", secret="synthetic-päß-1e0",
                                      passphrase="synthetic-passphrase")
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    binding, confirmation = secrets.token_bytes(32), secrets.token_bytes(32)
    with connect_as("runtime") as db:
        actor(db, f)
        oidc_time, session_expiry = clock(db) - 600, clock(db) + 600
        prepared = db.execute(PREPARE, (
            f["account_a"], action, connection if action == "register" else None,
            RP, ORIGIN, secrets.token_bytes(32), binding, confirmation,
            sha256(body).hexdigest(), session_expiry, 0, oidc_time,
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
        issued = db.execute(AUTHORIZE, (
            prepared["authorization_id"], granted["grant_id"], RP, ORIGIN,
            binding, confirmation, 0, oidc_time,
        )).fetchone()["receipt"]
    return issued, body


def token(r, *, nonce=None):
    # Real authenticated HS256 assertion from the actual DB receipt. TS/Jose
    # interoperability of this exact contract is independently tested in IP038.
    now = int(time())
    claims = dict(
        iss="investalo-bff", aud="investalo-credentials-passkey", sub=r["subject"],
        authorization_kind=r["kind"], authorization_id=r["authorization_id"],
        proof_id=r["proof_id"], grant_id=r["grant_id"], tenant_id=r["tenant_id"],
        user_id=r["user_id"], auth_epoch=r["auth_epoch"], oidc_iss=r["oidc_issuer"],
        oidc_auth_time=r["oidc_auth_time"], rp_id=r["rp_id"], origin=r["origin"],
        session_binding=r["session_binding"], session_expires_at=r["session_expires_at"],
        passkey_id=r["passkey_id"], passkey_version=r["passkey_version"],
        passkey_started_at=r["prepared_at"], passkey_checked_at=r["checked_at"],
        passkey_authorized_at=r["authorized_at"], authorization_expires_at=r["expires_at"],
        metadata_sha256=r["metadata_sha256"], target=r["target"], iat=now,
        exp=min(now + 60, r["expires_at"]), jti=str(nonce or uuid4()), htm="POST",
        htu="/v1/credentials/bitget/" + r["target"]["action"], body_sha256=r["body_sha256"],
    )
    b64 = lambda raw: base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
    wire = b64(b'{"alg":"HS256","typ":"JWT"}') + "." + b64(
        json.dumps(claims, separators=(",", ":")).encode())
    return wire + "." + b64(hmac.digest(KEY, wire.encode("ascii"), "sha256"))


def client(f, r):
    context = PasskeyRequestContext(
        tenant_id=f["tenant_a"], user_id=f["user_a"], subject=r["subject"],
        auth_epoch=r["auth_epoch"], oidc_auth_time=r["oidc_auth_time"],
        session_binding=r["session_binding"], session_expires_at=r["session_expires_at"],
    )
    return PasskeyAuthorizationClient(
        StoreContext(tenant_id=f["tenant_a"], user_id=f["user_a"],
                     expected_login_role=os.environ["CREDENTIAL_TEST_USER_A"]),
        context,
        verifier=PasskeyRequestVerifier(key=KEY, oidc_issuer=f["issuer"],
                                       origin=ORIGIN, clock=lambda: int(time())),
        connect=lambda: connect_as("a", tuple_rows=True),
    )


def denied(callback, code="access_denied"):
    with pytest.raises(OnboardingRejected) as failure:
        callback()
    assert failure.value.code == code


@pytest.mark.parametrize("action", ["register", "replace", "revoke"])
def test_actual_purpose_receipt_private_client_and_committed_final_lock(credential_database, action):
    f = credential_database
    r, body = receipt(f, action)
    service, assertion = client(f, r), token(r)
    authorization = service.consume(action, token=assertion, body=body)
    denied(lambda: service.consume(action, token=assertion, body=body))
    # New JWT ID is not a new purpose authorization.
    denied(lambda: service.consume(action, token=token(r), body=body))
    with service.lock(authorization) as db:
        assert db.autocommit is False
    denied(lambda: service.lock(authorization).__enter__())
    with connect_as("admin") as db:
        row = db.execute(
            "SELECT status,credential_revision,storage_version FROM platform.credential_connections "
            "WHERE tenant_id=%s AND connection_id=%s",
            (f["tenant_a"], UUID(r["target"]["connection_id"])),
        ).fetchone()
    assert row == (None if action == "register" else {
        "status": "active", "credential_revision": 1, "storage_version": 1,
    })


def test_final_lock_rechecks_actor_after_committed_consume(credential_database):
    f = credential_database
    r, body = receipt(f, "register")
    service = client(f, r)
    authorization = service.consume("register", token=token(r), body=body)
    with connect_as("admin") as db:
        db.execute("UPDATE platform.users SET active=false WHERE id=%s", (f["user_a"],))
    denied(lambda: service.lock(authorization).__enter__())


def test_failed_final_transaction_leaves_consume_and_rolls_back_lock(credential_database):
    f = credential_database
    r, body = receipt(f, "register")
    service = client(f, r)
    authorization = service.consume("register", token=token(r), body=body)
    with pytest.raises(OnboardingRejected):
        with service.lock(authorization):
            raise OnboardingRejected("unavailable")
    # Explicit recovery transaction; client supplies no automatic retry.
    with service.lock(authorization):
        pass
    denied(lambda: service.consume("register", token=token(r), body=body))
