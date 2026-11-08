"""Real fixture PostgreSQL purpose API; no credentials or broker execution."""
from dataclasses import replace
import json
from time import time
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from conftest import token
from investalo_api.database import connect
from investalo_api.main import create_app
import investalo_api.passkey_credential_authorizations as authorizations
from test_passkey_action_api_postgres import (
    database, credential_database, proof_database, prepare_payload,
    claim_payload, finish_payload,
)
from test_passkey_postgres import RP


BASE = "/v1/passkey-credential-authorizations"
PROOFS = "/v1/passkey-action-proofs"
ORIGIN = "https://" + RP


@pytest.fixture
def authorization_database(proof_database):
    f = proof_database
    with connect(f["admin"]) as db:
        assert db.execute(
            "SELECT 1 FROM platform.schema_migrations WHERE version='008_passkey_credential_authorizations'"
        ).fetchone(), "Reviewed008 must exist only in the isolated fixture database"
    return f


def api(f, *, enabled=True, origin=ORIGIN):
    settings = replace(f["runtime"], passkey_rp_id=RP, passkey_origin=origin,
                       passkey_credential_authorizations=enabled)
    return settings, TestClient(create_app(settings))


def post(client, settings, f, operation, value, *, base=BASE, user="a", tenant="a",
         auth_time=None, epoch=0, bearer=None):
    body = json.dumps(value, separators=(",", ":")).encode()
    assertion = bearer or token(
        settings, method="POST", target=base + "/" + operation, body=body,
        claims={"sub": f["subject_" + user], "tenant_id": str(f["tenant_" + tenant]),
                "auth_epoch": epoch, "oidc_auth_time": f["original_auth_time"] if auth_time is None else auth_time},
    )
    return client.post(base + "/" + operation, content=body, headers={
        "Content-Type": "application/json", "Authorization": "Bearer " + assertion,
    })


def prepare(f, client, settings, action="replace"):
    value = {**prepare_payload(f, action), "body_sha256": "e" * 64}
    response = post(client, settings, f, "prepare", value)
    assert response.status_code == 200, response.text
    return value, response.json()


def grant(f, client, settings, action="replace"):
    value, prepared = prepare(f, client, settings, action)
    attempt = prepared["attempt"]
    claimed = post(client, settings, f, "claim", claim_payload(value, attempt), base=PROOFS)
    assert claimed.status_code == 200, claimed.text
    finished = post(client, settings, f, "finish", finish_payload(value, attempt), base=PROOFS)
    assert finished.status_code == 200, finished.text
    return value, prepared, finished.json()


def consent(value, prepared, granted):
    return {"authorization_id": prepared["authorization_id"], "grant_id": granted["grant_id"],
            "session_binding": value["session_binding"], "confirmation_hash": value["confirmation_hash"]}


def state(f, prepared):
    with connect(f["admin"]) as db:
        purpose = db.execute(
            "SELECT state,origin,body_sha256,metadata_sha256,receipt,consumed_jti "
            "FROM platform.passkey_credential_authorizations WHERE authorization_id=%s",
            (prepared["authorization_id"],),
        ).fetchone()
        proof = db.execute(
            "SELECT state,oidc_auth_time,checked_at FROM platform.passkey_action_proofs WHERE proof_id=%s",
            (prepared["attempt"]["attempt_id"],),
        ).fetchone()
        audit = db.execute(
            "SELECT event FROM platform.passkey_credential_authorization_audit "
            "WHERE authorization_id=%s ORDER BY occurred_at,event", (prepared["authorization_id"],),
        ).fetchall()
        snapshot_digest = db.execute(
            "SELECT encode(sha256(convert_to(metadata::text,'UTF8')),'hex') AS value "
            "FROM platform.passkey_action_proofs WHERE proof_id=%s", (prepared["attempt"]["attempt_id"],),
        ).fetchone()["value"]
        stored = db.execute(
            "SELECT credential_revision,storage_version,status FROM platform.credential_connections "
            "WHERE connection_id=%s", (f["connection_a"],),
        ).fetchone()
    return purpose, proof, [row["event"] for row in audit], snapshot_digest, stored


@pytest.mark.parametrize("action", ["register", "replace", "revoke"])
def test_three_actions_issue_explicit_receipt_without_executing_credentials(authorization_database, action):
    f = authorization_database
    settings, client = api(f)
    value, prepared, granted = grant(f, client, settings, action)
    assert set(prepared) == {"authorization_id", "metadata_sha256", "attempt"}
    assert set(prepared["attempt"]) == {
        "attempt_id", "tenant_id", "user_id", "auth_epoch", "rp_id", "target", "metadata",
        "credential", "session_binding", "challenge", "confirmation_hash", "prepared_at",
        "expires_at", "session_expires_at",
    }
    result = post(client, settings, f, "authorize", consent(value, prepared, granted))
    assert result.status_code == 200, result.text
    wrapper = result.json()
    assert set(wrapper) == {"status", "execution_enabled", "authorization"}
    assert wrapper["status"] == "authorized" and wrapper["execution_enabled"] is False
    receipt = wrapper["authorization"]
    assert set(receipt) == authorizations.RECEIPT_FIELDS
    assert receipt["oidc_auth_time"] == f["original_auth_time"] < receipt["checked_at"]
    assert receipt["prepared_at"] <= receipt["checked_at"] <= receipt["authorized_at"] <= int(time())
    assert receipt["target"] == value["target"]
    assert receipt["origin"] == ORIGIN and receipt["body_sha256"] == value["body_sha256"]
    assert receipt["metadata_sha256"] == prepared["metadata_sha256"]
    purpose, proof, events, digest, stored = state(f, prepared)
    assert purpose["state"] == "authorized" and purpose["receipt"] == receipt and purpose["consumed_jti"] is None
    assert proof["state"] == "confirmed"
    assert events == ["prepared", "authorized"]
    assert digest == receipt["metadata_sha256"]
    assert stored == {"credential_revision": 1, "storage_version": 1, "status": "active"}
    if action == "register":
        with connect(f["admin"]) as db:
            assert db.execute(
                "SELECT count(*) AS n FROM platform.credential_connections WHERE connection_id=%s",
                (value["target"]["connection_id"],),
            ).fetchone()["n"] == 0
    # New transport nonce cannot make the explicit consent repeatable.
    replay = post(client, settings, f, "authorize", consent(value, prepared, granted))
    assert replay.status_code == 403
    assert state(f, prepared)[2] == ["prepared", "authorized"]
    for path in ("/v1/credentials/bitget/register", "/v1/credentials/bitget/replace",
                 "/v1/credentials/bitget/revoke"):
        assert client.post(path, content=b"PRIVATE_SENTINEL").status_code == 404
    assert "secret" not in json.dumps(wrapper).lower()


@pytest.mark.parametrize("enabled,origin", [(False, ORIGIN), (True, None), (True, "https://foreign.test")])
def test_default_disabled_or_invalid_origin_never_prepares_database(authorization_database, enabled, origin):
    f = authorization_database
    settings, client = api(f, enabled=enabled, origin=origin)
    value = {**prepare_payload(f), "body_sha256": "e" * 64}
    result = post(client, settings, f, "prepare", value)
    assert result.status_code == (503 if enabled else 404)
    with connect(f["admin"]) as db:
        assert db.execute(
            "SELECT count(*) AS n FROM platform.passkey_action_proofs WHERE user_id=%s", (f["user_a"],),
        ).fetchone()["n"] == 0


def test_prepare_transport_nonce_replay_cannot_create_second_purpose(authorization_database):
    f = authorization_database
    settings, client = api(f)
    value = {**prepare_payload(f), "body_sha256": "e" * 64}
    body = json.dumps(value, separators=(",", ":")).encode()
    bearer = token(settings, method="POST", target=BASE + "/prepare", body=body, claims={
        "sub": f["subject_a"], "tenant_id": str(f["tenant_a"]), "auth_epoch": 0,
        "oidc_auth_time": f["original_auth_time"],
    })
    result = post(client, settings, f, "prepare", value, bearer=bearer)
    assert result.status_code == 200, result.text
    assert post(client, settings, f, "prepare", value, bearer=bearer).status_code == 401
    assert state(f, result.json())[2] == ["prepared"]


@pytest.mark.parametrize("field,value", [
    ("authorization_id", str(uuid4())), ("grant_id", str(uuid4())),
    ("session_binding", "f" * 64), ("confirmation_hash", "f" * 64),
])
def test_wrong_consent_context_preserves_granted_authority(authorization_database, field, value):
    f = authorization_database
    settings, client = api(f)
    body, prepared, granted = grant(f, client, settings)
    result = post(client, settings, f, "authorize", {**consent(body, prepared, granted), field: value})
    assert result.status_code == 403, result.text
    purpose, proof, events, *_ = state(f, prepared)
    assert purpose["state"] == "prepared" and proof["state"] == "granted" and events == ["prepared"]
    assert post(client, settings, f, "authorize", consent(body, prepared, granted)).status_code == 200


def test_proof_only_confirmation_cannot_be_retrofitted_into_credential_consent(authorization_database):
    f = authorization_database
    settings, client = api(f)
    body, prepared, granted = grant(f, client, settings)
    response = post(client, settings, f, "confirm", {
        "grant_id": granted["grant_id"], "session_binding": body["session_binding"],
        "confirmation_hash": body["confirmation_hash"],
    }, base=PROOFS)
    assert response.status_code == 200
    assert response.json()["status"] == "verified" and response.json()["execution_enabled"] is False
    denied = post(client, settings, f, "authorize", consent(body, prepared, granted))
    assert denied.status_code == 403
    purpose, proof, events, *_ = state(f, prepared)
    assert purpose["state"] == "prepared" and purpose["receipt"] is None
    assert proof["state"] == "confirmed" and events == ["prepared"]


def test_purpose_prepare_checks_current_cas_and_rolls_back_new_target_on_stale_preview(authorization_database):
    f = authorization_database
    settings, client = api(f)
    value = {**prepare_payload(f), "body_sha256": "e" * 64}
    with connect(f["admin"]) as db:
        db.execute("UPDATE platform.credential_connections SET storage_version=2 WHERE connection_id=%s",
                   (f["connection_a"],))
    result = post(client, settings, f, "prepare", value)
    assert result.status_code == 409, result.text
    with connect(f["admin"]) as db:
        assert db.execute(
            "SELECT count(*) AS n FROM platform.passkey_action_proofs WHERE user_id=%s", (f["user_a"],),
        ).fetchone()["n"] == 0


@pytest.mark.parametrize("change", ["account", "connection", "factor", "epoch", "membership"])
def test_current_state_changed_before_authorize_cannot_issue_receipt(authorization_database, change):
    f = authorization_database
    settings, client = api(f)
    body, prepared, granted = grant(f, client, settings)
    with connect(f["admin"]) as db:
        if change == "account":
            db.execute("UPDATE platform.accounts SET name='Changed preview' WHERE id=%s", (f["account_a"],))
        elif change == "connection":
            db.execute("UPDATE platform.credential_connections SET storage_version=2 WHERE connection_id=%s",
                       (f["connection_a"],))
        elif change == "factor":
            db.execute("UPDATE platform.passkey_credentials SET storage_version=storage_version+1 WHERE passkey_id=%s",
                       (granted["passkey_id"],))
        elif change == "epoch":
            db.execute("UPDATE platform.users SET auth_epoch=auth_epoch+1 WHERE id=%s", (f["user_a"],))
        else:
            db.execute("UPDATE platform.memberships SET active=false WHERE tenant_id=%s AND user_id=%s",
                       (f["tenant_a"], f["user_a"]))
    result = post(client, settings, f, "authorize", consent(body, prepared, granted))
    assert result.status_code in (401, 403, 409), result.text
    purpose, proof, events, *_ = state(f, prepared)
    assert purpose["state"] == "prepared" and purpose["receipt"] is None
    assert proof["state"] == "granted" and events == ["prepared"]


@pytest.mark.parametrize("identity", [
    {"user": "b", "tenant": "b"}, {"tenant": "b"}, {"auth_time": 1}, {"epoch": 1},
])
def test_foreign_actor_or_changed_original_oidc_cannot_authorize(authorization_database, identity):
    f = authorization_database
    settings, client = api(f)
    body, prepared, granted = grant(f, client, settings)
    result = post(client, settings, f, "authorize", consent(body, prepared, granted), **identity)
    assert result.status_code in (401, 403)
    assert state(f, prepared)[2] == ["prepared"]


def test_changed_configured_origin_cannot_consume_grant(authorization_database):
    f = authorization_database
    settings, client = api(f)
    body, prepared, granted = grant(f, client, settings)
    changed_settings, changed_client = api(f, origin=ORIGIN + ":8443")
    result = post(changed_client, changed_settings, f, "authorize", consent(body, prepared, granted))
    assert result.status_code == 403
    assert state(f, prepared)[1]["state"] == "granted"


def test_invalid_projection_after_sql_authorization_rolls_back_confirmation_and_audit(
    authorization_database, monkeypatch,
):
    f = authorization_database
    settings, client = api(f)
    body, prepared, granted = grant(f, client, settings)
    original = authorizations.publish_authorization
    def tampered(receipt, *args):
        return original({**receipt, "body_sha256": "PRIVATE_SENTINEL"}, *args)
    monkeypatch.setattr(authorizations, "publish_authorization", tampered)
    result = post(client, settings, f, "authorize", consent(body, prepared, granted))
    assert result.status_code == 503 and "PRIVATE_SENTINEL" not in result.text
    purpose, proof, events, *_ = state(f, prepared)
    assert purpose["state"] == "prepared" and proof["state"] == "granted" and events == ["prepared"]
