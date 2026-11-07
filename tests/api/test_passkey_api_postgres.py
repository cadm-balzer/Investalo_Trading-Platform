"""Signed BFF API lifecycle against actual isolated PostgreSQL, never WebAuthn.

All tickets and public material are synthetic. Root applies migration006 and
runs these in the Compose API check profile; no browser proof is substituted.
"""
from dataclasses import replace
from datetime import datetime
from hashlib import sha256
import json
import secrets
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import pytest

from conftest import token
from investalo_api.database import connect
from investalo_api.main import create_app
from investalo_api.passkeys import REGISTRY_COLUMNS, encode_b64url
from test_postgres import database
from test_passkey_postgres import RP, REVOKE, issue, now, passkey_database


CONTEXT = "/v1/passkeys/context"
CLAIM = "/v1/passkeys/enrollment/claim"
FINISH = "/v1/passkeys/enrollment/finish"


def api(f, *, rp=RP):
    settings = replace(f["runtime"], passkey_rp_id=rp)
    return settings, TestClient(create_app(settings))


def signed(settings, f, *, method="GET", target=CONTEXT, body=b"",
           user="a", tenant=None, epoch=0, auth_time=None):
    values = {
        "sub": f["subject_" + user], "tenant_id": str(f["tenant_" + (tenant or user)]),
        "auth_epoch": epoch,
    }
    if auth_time is not None:
        values["oidc_auth_time"] = auth_time
    return {
        "Authorization": "Bearer " + token(
            settings, method=method, target=target, body=body, claims=values,
        ),
    }


def request(client, settings, f, target=CONTEXT, payload=None, **identity):
    if payload is None:
        return client.get(target, headers=signed(settings, f, target=target, **identity))
    body = json.dumps(payload, separators=(",", ":")).encode()
    return client.post(
        target, content=body, headers={
            **signed(settings, f, method="POST", target=target, body=body, **identity),
            "Content-Type": "application/json",
        },
    )


def ticket(f):
    raw = secrets.token_bytes(32)
    issued = issue(f, token_hash=sha256(raw).digest())
    payload = {"token": encode_b64url(raw), "session_binding": secrets.token_hex(32)}
    return issued, payload


def finish_payload(claimed, claim_payload):
    return {
        "claim_id": claimed["claim_id"], "session_binding": claim_payload["session_binding"],
        "credential_id": encode_b64url(secrets.token_bytes(32)),
        "public_key": encode_b64url(b"synthetic-public-key-not-a-WebAuthn-proof"),
        "sign_count": 0, "backup_eligible": True, "backed_up": False,
    }


def claimed_ticket(client, settings, f):
    issued, payload = ticket(f)
    response = request(client, settings, f, CLAIM, payload)
    assert response.status_code == 200
    return issued, payload, response.json()


def audit(f, issued):
    with connect(f["admin"]) as db:
        state = db.execute(
            "SELECT state FROM platform.passkey_enrollment_tickets WHERE ticket_id=%s",
            (issued["ticket_id"],),
        ).fetchone()["state"]
        events = db.execute(
            "SELECT event FROM platform.passkey_audit WHERE ticket_id=%s ORDER BY occurred_at",
            (issued["ticket_id"],),
        ).fetchall()
    return state, [row["event"] for row in events]


def test_signed_api_empty_claim_commit_finish_and_read_exact_owner_receipt(passkey_database):
    f = passkey_database
    settings, client = api(f)
    empty = request(client, settings, f)
    assert empty.status_code == 200
    assert empty.json() == {
        "tenant_id": str(f["tenant_a"]), "user_id": str(f["user_a"]),
        "auth_epoch": 0, "rp_id": RP, "credential": None,
    }
    issued, payload = ticket(f)
    observed_before_response = []
    application = create_app(settings)

    async def observe_commit(scope, receive, send):
        async def observed_send(message):
            if (
                scope.get("path") == CLAIM and message["type"] == "http.response.start"
                and message["status"] == 200
            ):
                observed_before_response.append(audit(f, issued))
            await send(message)
        await application(scope, receive, observed_send)

    client = TestClient(observe_commit)
    claim = request(client, settings, f, CLAIM, payload)
    assert claim.status_code == 200
    claimed = claim.json()
    assert set(claimed) == {
        "claim_id", "user_handle", "expires_at", "tenant_id", "user_id", "auth_epoch", "rp_id",
    }
    assert claimed["tenant_id"] == str(f["tenant_a"])
    assert claimed["user_id"] == str(f["user_a"])
    assert claimed["auth_epoch"] == 0 and claimed["rp_id"] == RP
    assert claimed["user_handle"] == encode_b64url(issued["user_handle"])
    assert datetime.fromisoformat(claimed["expires_at"]).tzinfo is not None
    # An independent admin transaction sees the irrevocable claim before ASGI
    # sends response headers, before any trusted BFF cryptographic verdict.
    assert observed_before_response == [("claimed", ["issued", "claimed"])]
    assert audit(f, issued) == ("claimed", ["issued", "claimed"])
    assert request(client, settings, f).json()["credential"] is None
    body = finish_payload(claimed, payload)
    finished = request(client, settings, f, FINISH, body)
    assert finished.status_code == 200
    row = finished.json()
    assert set(row) == set(REGISTRY_COLUMNS)
    assert row["tenant_id"] == str(f["tenant_a"]) and row["user_id"] == str(f["user_a"])
    assert row["rp_id"] == RP and row["user_handle"] == claimed["user_handle"]
    assert (row["storage_version"], row["status"], row["enrollment_epoch"]) == (1, "active", 0)
    for field in ("credential_id", "public_key", "sign_count", "backup_eligible", "backed_up"):
        assert row[field] == body[field]
    context = request(client, settings, f)
    assert context.status_code == 200 and context.json()["credential"] == row
    assert audit(f, issued) == ("finished", ["issued", "claimed", "enrolled"])
    for response in (empty, finished, context):
        assert payload["token"] not in response.text
        assert payload["session_binding"] not in response.text


@pytest.mark.parametrize("operation", ["context", "claim", "finish"])
def test_signed_assertion_replay_rejected_after_successful_commit(passkey_database, operation):
    f = passkey_database
    settings, client = api(f)
    target, body = CONTEXT, b""
    if operation == "claim":
        _issued, payload = ticket(f)
        target, body = CLAIM, json.dumps(payload).encode()
    elif operation == "finish":
        _issued, payload, claimed = claimed_ticket(client, settings, f)
        target, body = FINISH, json.dumps(finish_payload(claimed, payload)).encode()
    method = "GET" if operation == "context" else "POST"
    headers = signed(settings, f, method=method, target=target, body=body)
    first = client.request(method, target, content=body, headers=headers)
    replay = client.request(method, target, content=body, headers=headers)
    assert first.status_code == 200
    assert replay.status_code == 401
    assert replay.json() == {"detail": "Authentication required"}


def test_ceremony_replay_with_fresh_assertions_never_reenrolls(passkey_database):
    f = passkey_database
    settings, client = api(f)
    issued, payload, claimed = claimed_ticket(client, settings, f)
    replay = request(client, settings, f, CLAIM, payload)
    assert replay.status_code == 403 and replay.json() == {"detail": "Access denied"}
    assert audit(f, issued) == ("claimed", ["issued", "claimed"])
    body = finish_payload(claimed, payload)
    first = request(client, settings, f, FINISH, body)
    assert first.status_code == 200
    replay = request(client, settings, f, FINISH, body)
    assert replay.status_code == 403 and replay.json() == {"detail": "Access denied"}
    assert request(client, settings, f).json()["credential"] == first.json()
    assert audit(f, issued) == ("finished", ["issued", "claimed", "enrolled"])


@pytest.mark.parametrize("operation", ["context", "claim", "finish"])
def test_membership_downgrade_to_viewer_is_rechecked_for_every_api_step(passkey_database, operation):
    f = passkey_database
    settings, client = api(f)
    issued, payload, claimed = claimed_ticket(client, settings, f)
    with connect(f["admin"]) as db:
        db.execute(
            "UPDATE platform.memberships SET role='viewer' WHERE tenant_id=%s AND user_id=%s",
            (f["tenant_a"], f["user_a"]),
        )
    target, body = {
        "context": (CONTEXT, None), "claim": (CLAIM, payload),
        "finish": (FINISH, finish_payload(claimed, payload)),
    }[operation]
    response = request(client, settings, f, target, body)
    assert response.status_code == 403 and response.json() == {"detail": "Access denied"}
    assert audit(f, issued) == ("claimed", ["issued", "claimed"])


@pytest.mark.parametrize("actor", ["foreign_owner", "wrong_tenant", "same_tenant_peer"])
def test_foreign_actor_cannot_claim_finish_or_read_another_owners_key(passkey_database, actor):
    f = passkey_database
    settings, client = api(f)
    issued, payload = ticket(f)
    if actor == "same_tenant_peer":
        with connect(f["admin"]) as db:
            db.execute(
                "INSERT INTO platform.memberships(tenant_id,user_id,role) VALUES(%s,%s,'owner')",
                (f["tenant_a"], f["user_b"]),
            )
    identity = {
        "foreign_owner": {"user": "b"},
        "wrong_tenant": {"user": "a", "tenant": "b"},
        "same_tenant_peer": {"user": "b", "tenant": "a"},
    }[actor]
    rejected = request(client, settings, f, CLAIM, payload, **identity)
    assert rejected.status_code == 403 and rejected.json() == {"detail": "Access denied"}
    assert audit(f, issued) == ("issued", ["issued"])
    claim = request(client, settings, f, CLAIM, payload)
    assert claim.status_code == 200
    body = finish_payload(claim.json(), payload)
    rejected = request(client, settings, f, FINISH, body, **identity)
    assert rejected.status_code == 403 and rejected.json() == {"detail": "Access denied"}
    assert audit(f, issued) == ("claimed", ["issued", "claimed"])
    finished = request(client, settings, f, FINISH, body)
    assert finished.status_code == 200
    context = request(client, settings, f, **identity)
    if actor == "wrong_tenant":
        assert context.status_code == 403 and context.json() == {"detail": "Access denied"}
    else:
        assert context.status_code == 200 and context.json()["credential"] is None
        assert context.json()["user_id"] == str(f["user_b"])
    assert request(client, settings, f).json()["credential"] == finished.json()


def test_admin_revocation_rejects_old_epoch_and_fresh_context_keeps_tombstone(passkey_database):
    f = passkey_database
    settings, client = api(f)
    issued, payload, claimed = claimed_ticket(client, settings, f)
    body = finish_payload(claimed, payload)
    enrolled = request(client, settings, f, FINISH, body)
    assert enrolled.status_code == 200
    with connect(f["admin"]) as db:
        db.execute(REVOKE, (UUID(enrolled.json()["passkey_id"]), 1, uuid4()))
        fresh_auth_time = now(db)
    for target, value in ((CONTEXT, None), (CLAIM, payload), (FINISH, body)):
        response = request(client, settings, f, target, value)
        assert response.status_code == 401
        assert response.json() == {"detail": "Reauthentication required"}
    fresh = request(client, settings, f, epoch=1, auth_time=fresh_auth_time)
    assert fresh.status_code == 200 and fresh.json()["auth_epoch"] == 1
    revoked = fresh.json()["credential"]
    assert revoked["passkey_id"] == enrolled.json()["passkey_id"]
    assert (revoked["status"], revoked["storage_version"], revoked["enrollment_epoch"]) == ("revoked", 2, 0)
    rejected = request(client, settings, f, FINISH, body, epoch=1, auth_time=fresh_auth_time)
    assert rejected.status_code == 403 and rejected.json() == {"detail": "Access denied"}
    assert request(client, settings, f, epoch=1, auth_time=fresh_auth_time).json()["credential"] == revoked


def test_different_configured_rp_finish_rolls_back_registry_ticket_and_audit(passkey_database):
    f = passkey_database
    settings, client = api(f)
    issued, payload, claimed = claimed_ticket(client, settings, f)
    body = finish_payload(claimed, payload)
    other_settings, other_client = api(f, rp="other.local.test")
    rejected = request(other_client, other_settings, f, FINISH, body)
    assert rejected.status_code == 403 and rejected.json() == {"detail": "Access denied"}
    assert audit(f, issued) == ("claimed", ["issued", "claimed"])
    with connect(f["admin"]) as db:
        assert db.execute(
            "SELECT 1 FROM platform.passkey_credentials WHERE tenant_id=%s AND user_id=%s",
            (f["tenant_a"], f["user_a"]),
        ).fetchall() == []
    assert request(client, settings, f).json()["credential"] is None
    retry = request(client, settings, f, FINISH, body)
    assert retry.status_code == 200 and retry.json()["rp_id"] == RP
    assert audit(f, issued) == ("finished", ["issued", "claimed", "enrolled"])
