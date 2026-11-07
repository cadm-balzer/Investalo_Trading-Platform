"""Request-bound trusted-BFF proof API against isolated real PostgreSQL.

Keys/verdicts here are synthetic; signature verification belongs to the BFF.
No credential execution, real broker contact or physical device is claimed.
"""
from dataclasses import replace
import json
import secrets
from time import time
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from conftest import token
from investalo_api.database import connect
from investalo_api.main import create_app
from investalo_api.passkeys import encode_b64url
from test_postgres import database
from test_credential_action_postgres import credential_database
from test_passkey_postgres import RP, REVOKE, claim, finish, issue


BASE = "/v1/passkey-action-proofs"


@pytest.fixture
def proof_database(credential_database):
    f = credential_database
    account = uuid4()
    with connect(f["admin"]) as db:
        assert db.execute(
            "SELECT 1 FROM platform.schema_migrations WHERE version='007_passkey_action_proofs'"
        ).fetchone(), "Root must apply reviewed007 before isolated proof API checks"
        db.execute(
            "INSERT INTO platform.accounts(tenant_id,id,name,broker,mode,currency) "
            "VALUES(%s,%s,'Unconnected synthetic account','bitget','read_only','USDT')",
            (f["tenant_a"], account),
        )
    key = finish(f, claim(f, issue(f)), counter=0)
    return {**f, "unconnected": account, "key": key, "original_auth_time": int(time()) - 600}


def api(f, *, rp=RP):
    settings = replace(f["runtime"], passkey_rp_id=rp)
    return settings, TestClient(create_app(settings))


def headers(settings, f, operation, body, *, user="a", tenant="a", auth_time=None, epoch=0):
    return {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + token(
            settings, method="POST", target=BASE + "/" + operation, body=body,
            claims={"sub": f["subject_" + user], "tenant_id": str(f["tenant_" + tenant]),
                    "auth_epoch": epoch,
                    "oidc_auth_time": f["original_auth_time"] if auth_time is None else auth_time},
        ),
    }


def request(client, settings, f, operation, payload, **identity):
    body = json.dumps(payload, separators=(",", ":")).encode()
    return client.post(BASE + "/" + operation, content=body,
                       headers=headers(settings, f, operation, body, **identity))


def prepare_payload(f, action="replace"):
    target = {
        "action": action,
        "platform_account_id": str(f["unconnected"] if action == "register" else f["account_a"]),
        "connection_id": str(uuid4() if action == "register" else f["connection_a"]),
    }
    if action != "register":
        target.update(expected_revision=1, expected_storage=1)
    return {"target": target, "session_binding": secrets.token_hex(32),
            "challenge": encode_b64url(secrets.token_bytes(32)),
            "confirmation_hash": secrets.token_hex(32), "session_expires_at": int(time()) + 3600}


def prepared(client, settings, f, action="replace"):
    body = prepare_payload(f, action)
    response = request(client, settings, f, "prepare", body)
    assert response.status_code == 200, response.text
    return body, response.json()


def claim_payload(body, receipt):
    return {"attempt_id": receipt["attempt_id"], "session_binding": body["session_binding"]}


def finish_payload(body, receipt):
    return {**claim_payload(body, receipt), "new_counter": 0, "backup_eligible": True,
            "backed_up": False, "checked_at": int(time())}


def grant_payload(body, grant):
    return {"grant_id": grant["grant_id"], "session_binding": body["session_binding"]}


def granted(client, settings, f, action="replace"):
    body, attempt = prepared(client, settings, f, action)
    assert request(client, settings, f, "claim", claim_payload(body, attempt)).status_code == 200
    verdict = finish_payload(body, attempt)
    response = request(client, settings, f, "finish", verdict)
    assert response.status_code == 200, response.text
    return body, attempt, verdict, response.json()


def proof_state(f, attempt):
    with connect(f["admin"]) as db:
        row = db.execute(
            "SELECT state,oidc_auth_time,checked_at FROM platform.passkey_action_proofs WHERE proof_id=%s",
            (attempt["attempt_id"],),
        ).fetchone()
        events = db.execute(
            "SELECT event FROM platform.passkey_action_audit WHERE proof_id=%s ORDER BY occurred_at",
            (attempt["attempt_id"],),
        ).fetchall()
    return row, [event["event"] for event in events]


@pytest.mark.parametrize("action", ["register", "replace", "revoke"])
def test_complete_signed_target_bound_api_preserves_oidc_claims_and_never_executes(proof_database, action):
    f = proof_database
    settings, client = api(f)
    body, attempt = prepared(client, settings, f, action)
    assert attempt["target"] == body["target"]
    assert attempt["credential"]["passkey_id"] == str(f["key"]["passkey_id"])
    assert attempt["credential"]["storage_version"] == 1
    observed = []
    application = create_app(settings)
    async def observe_commit(scope, receive, send):
        async def observed_send(message):
            if scope.get("path") == BASE + "/claim" and message["type"] == "http.response.start" and message["status"] == 200:
                observed.append(proof_state(f, attempt))
            await send(message)
        await application(scope, receive, observed_send)
    claim_client = TestClient(observe_commit)
    response = request(claim_client, settings, f, "claim", claim_payload(body, attempt))
    assert response.status_code == 200 and response.json() == attempt
    assert observed[0][0]["state"] == "claimed"
    assert observed[0][1] == ["prepared", "claimed"]
    verdict = finish_payload(body, attempt)
    finished = request(client, settings, f, "finish", verdict)
    assert finished.status_code == 200
    grant = finished.json()
    assert grant["target"] == body["target"] and grant["passkey_version"] == 2
    assert grant["checked_at"] == verdict["checked_at"] != f["original_auth_time"]
    read = request(client, settings, f, "grant", grant_payload(body, grant))
    assert read.status_code == 200 and read.json() == grant
    confirmed = request(client, settings, f, "confirm", {
        **grant_payload(body, grant), "confirmation_hash": body["confirmation_hash"],
    })
    assert confirmed.status_code == 200
    assert confirmed.json() == {"status": "verified", "execution_enabled": False, "proof": grant}
    row, events = proof_state(f, attempt)
    assert row == {"state": "confirmed", "oidc_auth_time": f["original_auth_time"], "checked_at": verdict["checked_at"]}
    assert events == ["prepared", "claimed", "granted", "confirmed"]
    assert request(client, settings, f, "grant", grant_payload(body, grant)).status_code == 403
    with connect(f["admin"]) as db:
        # Counter version changes; credential connection remains untouched.
        saved = db.execute(
            "SELECT storage_version,sign_count FROM platform.passkey_credentials WHERE passkey_id=%s",
            (f["key"]["passkey_id"],),
        ).fetchone()
        connection = db.execute(
            "SELECT storage_version,credential_revision,status FROM platform.credential_connections "
            "WHERE tenant_id=%s AND connection_id=%s", (f["tenant_a"], f["connection_a"]),
        ).fetchone()
    assert saved == {"storage_version": 2, "sign_count": 0}
    assert connection == {"storage_version": 1, "credential_revision": 1, "status": "active"}
    for response in (finished, confirmed):
        assert response.headers["cache-control"] == "no-store"
        assert all(marker not in response.text for marker in ("broker_uid", "envelope", "oidc_subject", "public_key"))


@pytest.mark.parametrize("operation", ["prepare", "claim", "finish", "grant", "confirm"])
def test_signed_internal_request_replay_rejected_after_each_committed_step(proof_database, operation):
    f = proof_database
    settings, client = api(f)
    if operation == "prepare":
        payload = prepare_payload(f)
    elif operation == "claim":
        body, attempt = prepared(client, settings, f)
        payload = claim_payload(body, attempt)
    elif operation == "finish":
        body, attempt = prepared(client, settings, f)
        assert request(client, settings, f, "claim", claim_payload(body, attempt)).status_code == 200
        payload = finish_payload(body, attempt)
    else:
        body, _attempt, _verdict, grant = granted(client, settings, f)
        payload = grant_payload(body, grant)
        if operation == "confirm":
            payload["confirmation_hash"] = body["confirmation_hash"]
    wire = json.dumps(payload).encode()
    auth = headers(settings, f, operation, wire)
    first = client.post(BASE + "/" + operation, content=wire, headers=auth)
    replay = client.post(BASE + "/" + operation, content=wire, headers=auth)
    assert first.status_code == 200
    assert replay.status_code == 401 and replay.json() == {"detail": "Authentication required"}


@pytest.mark.parametrize("operation", ["claim", "finish", "confirm"])
def test_durable_ceremony_replay_rejected_even_with_new_signed_assertion(proof_database, operation):
    f = proof_database
    settings, client = api(f)
    body, attempt = prepared(client, settings, f)
    claimed = claim_payload(body, attempt)
    assert request(client, settings, f, "claim", claimed).status_code == 200
    if operation == "claim":
        payload = claimed
    else:
        verdict = finish_payload(body, attempt)
        finished = request(client, settings, f, "finish", verdict)
        assert finished.status_code == 200
        if operation == "finish":
            payload = verdict
        else:
            payload = {**grant_payload(body, finished.json()), "confirmation_hash": body["confirmation_hash"]}
            assert request(client, settings, f, "confirm", payload).status_code == 200
    replay = request(client, settings, f, operation, payload)
    assert replay.status_code == 403 and replay.json() == {"detail": "Access denied"}


def test_stale_preview_hash_does_not_consume_new_tab_grant(proof_database):
    f = proof_database
    settings, client = api(f)
    body, attempt, _verdict, grant = granted(client, settings, f)
    wrong = request(client, settings, f, "confirm", {
        **grant_payload(body, grant), "confirmation_hash": secrets.token_hex(32),
    })
    assert wrong.status_code == 403 and wrong.json() == {"detail": "Access denied"}
    assert proof_state(f, attempt)[0]["state"] == "granted"
    assert request(client, settings, f, "grant", grant_payload(body, grant)).status_code == 200
    assert request(client, settings, f, "confirm", {
        **grant_payload(body, grant), "confirmation_hash": body["confirmation_hash"],
    }).status_code == 200


@pytest.mark.parametrize("changed", ["revision", "storage"])
def test_stale_client_versions_roll_back_prepare_and_audit(proof_database, changed):
    f = proof_database
    settings, client = api(f)
    body = prepare_payload(f)
    body["target"]["expected_" + changed] = 2
    response = request(client, settings, f, "prepare", body)
    assert response.status_code == 409 and response.json() == {"detail": "Concurrent change"}
    with connect(f["admin"]) as db:
        assert db.execute(
            "SELECT count(*) AS n FROM platform.passkey_action_proofs WHERE tenant_id=%s AND user_id=%s",
            (f["tenant_a"], f["user_a"]),
        ).fetchone()["n"] == 0
        assert db.execute(
            "SELECT count(*) AS n FROM platform.passkey_action_audit WHERE tenant_id=%s AND user_id=%s",
            (f["tenant_a"], f["user_a"]),
        ).fetchone()["n"] == 0


@pytest.mark.parametrize("operation", ["claim", "finish", "grant", "confirm"])
def test_original_oidc_time_cannot_be_replaced_by_fresh_passkey_time(proof_database, operation):
    f = proof_database
    settings, client = api(f)
    body, attempt = prepared(client, settings, f)
    if operation == "claim":
        payload = claim_payload(body, attempt)
    else:
        assert request(client, settings, f, "claim", claim_payload(body, attempt)).status_code == 200
        payload = finish_payload(body, attempt)
        if operation in ("grant", "confirm"):
            finished = request(client, settings, f, "finish", payload)
            assert finished.status_code == 200
            payload = grant_payload(body, finished.json())
            if operation == "confirm":
                payload["confirmation_hash"] = body["confirmation_hash"]
    response = request(client, settings, f, operation, payload, auth_time=int(time()))
    assert response.status_code == 403 and response.json() == {"detail": "Access denied"}


@pytest.mark.parametrize("operation", ["claim", "finish", "grant", "confirm"])
def test_mismatched_session_binding_never_burns_the_matching_proof(proof_database, operation):
    f = proof_database
    settings, client = api(f)
    body, attempt = prepared(client, settings, f)
    if operation == "claim":
        payload = claim_payload(body, attempt)
        expected = "prepared"
    else:
        assert request(client, settings, f, "claim", claim_payload(body, attempt)).status_code == 200
        payload = finish_payload(body, attempt)
        expected = "claimed"
        if operation in ("grant", "confirm"):
            finished = request(client, settings, f, "finish", payload)
            assert finished.status_code == 200
            payload = grant_payload(body, finished.json())
            expected = "granted"
            if operation == "confirm":
                payload["confirmation_hash"] = body["confirmation_hash"]
    response = request(client, settings, f, operation, {**payload, "session_binding": secrets.token_hex(32)})
    assert response.status_code == 403
    assert proof_state(f, attempt)[0]["state"] == expected
    assert request(client, settings, f, operation, payload).status_code == 200


def test_revoked_factor_invalidates_existing_grant_and_session(proof_database):
    f = proof_database
    settings, client = api(f)
    body, attempt, _verdict, grant = granted(client, settings, f)
    with connect(f["admin"]) as db:
        db.execute(REVOKE, (f["key"]["passkey_id"], 2, uuid4()))
    response = request(client, settings, f, "confirm", {
        **grant_payload(body, grant), "confirmation_hash": body["confirmation_hash"],
    })
    assert response.status_code == 401 and response.json() == {"detail": "Reauthentication required"}
    assert proof_state(f, attempt)[0]["state"] == "granted"


def test_foreign_actor_cannot_claim_another_users_proof(proof_database):
    f = proof_database
    settings, client = api(f)
    body, attempt = prepared(client, settings, f)
    response = request(client, settings, f, "claim", claim_payload(body, attempt), user="b")
    assert response.status_code == 403 and response.json() == {"detail": "Access denied"}
    assert proof_state(f, attempt)[0]["state"] == "prepared"
