"""Actual isolated015 HTTP/API/PG lifecycle; keys and WebAuthn verdicts synthetic."""
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
import json
from threading import Barrier
from time import time
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from conftest import token
from investalo_api.database import connect
from investalo_api.main import create_app
import investalo_api.demo_passkey_authorizations as demo
from test_passkey_action_api_postgres import (
    database, credential_database, proof_database, prepare_payload, claim_payload,
    finish_payload, grant_payload,
)
from test_passkey_postgres import RP

BASE = "/v1/bitget-demo/passkey-authorizations"


@pytest.fixture
def demo_database(proof_database):
    f = proof_database
    # Fixture-only opt-in; retain original normal connection on its own account.
    with connect(f["admin"]) as db:
        assert db.execute("SELECT 1 FROM platform.schema_migrations "
                          "WHERE version='016_demo_passkey_completions'").fetchone()
        db.execute("UPDATE platform.accounts SET mode='bitget_demo',status='ready' "
                   "WHERE tenant_id=%s AND id=%s", (f["tenant_a"], f["unconnected"]))
    return f


def api(f):
    settings = replace(f["runtime"], passkey_rp_id=RP, passkey_origin="https://" + RP,
                       demo_passkey_authorizations=True, passkey_credential_authorizations=True)
    return settings, TestClient(create_app(settings))


def post(client, settings, f, operation, value, *, base=BASE, claims=None, bearer=None):
    body = json.dumps(value, separators=(",", ":")).encode()
    assertion = bearer or token(settings, method="POST", target=base + "/" + operation, body=body,
        claims={"sub": f["subject_a"], "tenant_id": str(f["tenant_a"]), "auth_epoch": 0,
                "oidc_auth_time": f["original_auth_time"], **(claims or {})})
    return client.post(base + "/" + operation, content=body, headers={
        "Content-Type": "application/json", "Authorization": "Bearer " + assertion})


def prepare(f, client, settings, action="register"):
    value = {**prepare_payload(f, "register"), "body_sha256": "e" * 64}
    if action == "revoke":
        # Structural fixture ciphertext only; API never decrypts or writes it.
        with connect(f["admin"]) as db:
            envelope = db.execute("SELECT envelope FROM platform.credential_connections "
                                 "WHERE connection_id=%s", (f["connection_a"],)).fetchone()["envelope"]
            from psycopg.types.json import Jsonb
            connection = uuid4()
            db.execute("INSERT INTO platform.demo_credential_connections"
                "(tenant_id,user_id,platform_account_id,connection_id,broker_uid,parent_uid,"
                "egress_ip,provisioning_digest,credential_revision,storage_version,status,envelope)"
                " VALUES(%s,%s,%s,%s,%s,'0','192.0.2.8',%s,1,1,'active',%s)",
                (f["tenant_a"], f["user_a"], f["unconnected"], connection,
                 str(10**18 + uuid4().int % (10**18)), "d" * 64, Jsonb(envelope)))
        value["target"].update(action="revoke", connection_id=str(connection), expected_revision=1, expected_storage=1)
    response = post(client, settings, f, "prepare", value)
    assert response.status_code == 200, response.text
    return value, response.json()


def grant(f, client, settings, action="register"):
    value, prepared = prepare(f, client, settings, action)
    attempt = prepared["attempt"]
    response = post(client, settings, f, "claim", claim_payload(value, attempt))
    assert response.status_code == 200, response.text
    response = post(client, settings, f, "finish", finish_payload(value, attempt))
    assert response.status_code == 200, response.text
    return value, prepared, response.json()


def consent(value, prepared, granted):
    return {"authorization_id": prepared["authorization_id"], "grant_id": granted["grant_id"],
            "session_binding": value["session_binding"], "confirmation_hash": value["confirmation_hash"]}


def state(f, prepared):
    with connect(f["admin"]) as db:
        return db.execute("SELECT state,receipt,consumed_jti FROM platform.demo_passkey_credential_authorizations "
                          "WHERE authorization_id=%s", (prepared["authorization_id"],)).fetchone()


@pytest.mark.parametrize("action", ("register", "revoke"))
def test_actual_complete_own_api_and_atomic_explicit_consent(demo_database, action):
    f = demo_database
    settings, client = api(f)
    value, prepared, granted = grant(f, client, settings, action)
    assert prepared["attempt"]["metadata"]["account"]["mode"] == "bitget_demo"
    assert prepared["attempt"]["metadata"]["environment"] == "demo"
    assert state(f, prepared)["state"] == "prepared"
    read = post(client, settings, f, "grant", grant_payload(value, granted))
    assert read.status_code == 200
    response = post(client, settings, f, "authorize", consent(value, prepared, granted))
    assert response.status_code == 200, response.text
    public = response.json()
    receipt = public["authorization"]
    assert public["execution_enabled"] is False and receipt["kind"] == "passkey-demo-credential-authorization/1"
    assert receipt["oidc_auth_time"] == f["original_auth_time"] < receipt["checked_at"]
    assert receipt["body_sha256"] == value["body_sha256"]
    assert state(f, prepared) == {"state": "authorized", "receipt": receipt, "consumed_jti": None}
    for r in (read, response):
        assert r.headers["cache-control"] == "no-store" and r.headers["x-content-type-options"] == "nosniff"
        assert all(word not in r.text for word in ("envelope", "broker_uid", "parent_uid", "egress_ip", "provisioning_digest"))
    assert post(client, settings, f, "authorize", consent(value, prepared, granted)).status_code == 403
    with connect(f["admin"]) as db:
        assert db.execute("SELECT count(*) AS n FROM platform.demo_passkey_credential_completion_audit "
                          "WHERE authorization_id=%s", (prepared["authorization_id"],)).fetchone()["n"] == 0
        assert db.execute("SELECT count(*) AS n FROM platform.demo_credential_connections "
                          "WHERE platform_account_id=%s", (f["unconnected"],)).fetchone()["n"] == (action == "revoke")
        assert db.execute("SELECT event FROM platform.demo_passkey_credential_authorization_audit "
                          "WHERE authorization_id=%s ORDER BY occurred_at", (prepared["authorization_id"],)).fetchall() == [
                              {"event": "prepared"}, {"event": "authorized"}]


def test_claim_commit_required_and_replay_cannot_verify_again(demo_database):
    f = demo_database
    settings, client = api(f)
    value, prepared = prepare(f, client, settings)
    attempt = prepared["attempt"]
    verdict = finish_payload(value, attempt)
    assert post(client, settings, f, "finish", verdict).status_code == 403
    assert post(client, settings, f, "claim", claim_payload(value, attempt)).status_code == 200
    assert post(client, settings, f, "claim", claim_payload(value, attempt)).status_code == 403
    verdict = finish_payload(value, attempt)  # Verification time must follow the committed claim.
    assert post(client, settings, f, "finish", verdict).status_code == 200
    assert post(client, settings, f, "finish", verdict).status_code == 403


@pytest.mark.parametrize("direction", ("demo_to_normal", "normal_to_demo"))
def test_existing_proof_and_purpose_routes_never_cross(demo_database, direction):
    f = demo_database
    settings, client = api(f)
    value, prepared = prepare(f, client, settings)
    normal = "/v1/passkey-action-proofs"
    if direction == "normal_to_demo":
        value = prepare_payload(f, "replace")
        response = post(client, settings, f, "prepare", value, base=normal)
        assert response.status_code == 200, response.text
        attempt, target_base = response.json(), BASE
    else:
        attempt, target_base = prepared["attempt"], normal
    assert post(client, settings, f, "claim", claim_payload(value, attempt), base=target_base).status_code == 403
    if direction == "demo_to_normal":
        assert post(client, settings, f, "claim", claim_payload(value, attempt)).status_code == 200
        finished = post(client, settings, f, "finish", finish_payload(value, attempt))
        assert finished.status_code == 200
        assert post(client, settings, f, "authorize", consent(value, prepared, finished.json()),
                    base="/v1/passkey-credential-authorizations").status_code == 403


@pytest.mark.parametrize("change", ("pause", "name", "role", "epoch", "reauth", "factor"))
def test_current_db_changes_reject_consent_without_issuing_receipt(demo_database, change):
    f = demo_database
    settings, client = api(f)
    value, prepared, granted = grant(f, client, settings)
    with connect(f["admin"]) as db:
        queries = {
            "pause": ("UPDATE platform.accounts SET status='paused' WHERE id=%s", (f["unconnected"],)),
            "name": ("UPDATE platform.accounts SET name='Changed' WHERE id=%s", (f["unconnected"],)),
            "role": ("UPDATE platform.memberships SET role='viewer' WHERE tenant_id=%s AND user_id=%s",
                     (f["tenant_a"], f["user_a"])),
            "epoch": ("UPDATE platform.users SET auth_epoch=auth_epoch+1 WHERE id=%s", (f["user_a"],)),
            "reauth": ("UPDATE platform.users SET reauth_after=clock_timestamp() WHERE id=%s", (f["user_a"],)),
            "factor": ("UPDATE platform.passkey_credentials SET storage_version=storage_version+1 "
                       "WHERE passkey_id=%s", (f["key"]["passkey_id"],)),
        }
        db.execute(*queries[change])
    response = post(client, settings, f, "authorize", consent(value, prepared, granted))
    assert response.status_code in (401, 403, 409), response.text
    assert state(f, prepared)["state"] == "prepared" and state(f, prepared)["receipt"] is None


@pytest.mark.parametrize("change", ("hash", "binding", "grant", "authorization"))
def test_wrong_explicit_consent_preserves_original_grant(demo_database, change):
    f = demo_database
    settings, client = api(f)
    value, prepared, granted = grant(f, client, settings)
    body = consent(value, prepared, granted)
    field = {"hash": "confirmation_hash", "binding": "session_binding",
             "grant": "grant_id", "authorization": "authorization_id"}[change]
    body[field] = "f" * 64 if change in ("hash", "binding") else str(uuid4())
    assert post(client, settings, f, "authorize", body).status_code in (403, 503)
    assert state(f, prepared)["state"] == "prepared"
    assert post(client, settings, f, "authorize", consent(value, prepared, granted)).status_code == 200


@pytest.mark.parametrize("claims", (
    {"sub": "unknown-subject"}, {"tenant_id": str(uuid4())}, {"auth_epoch": 1},
))
def test_signed_identity_cannot_access_another_actor(demo_database, claims):
    f = demo_database
    settings, client = api(f)
    value, prepared = prepare(f, client, settings)
    response = post(client, settings, f, "claim", claim_payload(value, prepared["attempt"]), claims=claims)
    assert response.status_code in (401, 403)
    assert state(f, prepared)["state"] == "prepared"


def test_signed_request_is_bound_to_exact_path_body_and_nonce(demo_database):
    f = demo_database
    settings, client = api(f)
    value = {**prepare_payload(f, "register"), "body_sha256": "e" * 64}
    body = json.dumps(value, separators=(",", ":")).encode()
    bearer = token(settings, method="POST", target=BASE + "/prepare", body=body,
                   claims={"sub": f["subject_a"], "tenant_id": str(f["tenant_a"]), "auth_epoch": 0,
                           "oidc_auth_time": f["original_auth_time"]})
    assert post(client, settings, f, "prepare", {**value, "body_sha256": "f" * 64}, bearer=bearer).status_code == 401
    assert post(client, settings, f, "claim", value, bearer=bearer).status_code == 401
    assert post(client, settings, f, "prepare", value, bearer=bearer).status_code == 200
    assert post(client, settings, f, "prepare", value, bearer=bearer).status_code == 401


def test_paused_account_supports_fresh_keyless_revoke(demo_database):
    f = demo_database
    settings, client = api(f)
    value, _old = prepare(f, client, settings, "revoke")
    with connect(f["admin"]) as db:
        db.execute("UPDATE platform.accounts SET status='paused' WHERE id=%s", (f["unconnected"],))
    fresh = prepare_payload(f, "register")
    value.update(challenge=fresh["challenge"], confirmation_hash=fresh["confirmation_hash"])
    response = post(client, settings, f, "prepare", value)
    assert response.status_code == 200, response.text
    p = response.json()
    assert post(client, settings, f, "claim", claim_payload(value, p["attempt"])).status_code == 200
    g = post(client, settings, f, "finish", finish_payload(value, p["attempt"]))
    assert g.status_code == 200
    assert post(client, settings, f, "authorize", consent(value, p, g.json())).status_code == 200


def test_public_projection_failure_rolls_back_real_preparation(demo_database, monkeypatch):
    f = demo_database
    settings, client = api(f)
    value = {**prepare_payload(f, "register"), "body_sha256": "e" * 64}
    query = demo._query
    captured = None
    def corrupt(*args):
        nonlocal captured
        row = query(*args)
        captured = row["authorization_id"]
        row["metadata"]["account"]["broker_uid"] = "synthetic-private-sentinel"
        return row
    monkeypatch.setattr(demo, "_query", corrupt)
    response = post(client, settings, f, "prepare", value)
    assert response.status_code == 503 and "sentinel" not in response.text
    with connect(f["admin"]) as db:
        assert db.execute("SELECT 1 FROM platform.demo_passkey_credential_authorizations "
                          "WHERE authorization_id=%s", (captured,)).fetchone() is None


@pytest.mark.parametrize("operation", ("claim", "authorize"))
def test_unknown_ack_after_actual_commit_never_retries(demo_database, monkeypatch, operation):
    import psycopg
    import investalo_api.database as database_module
    f = demo_database
    settings, client = api(f)
    if operation == "claim":
        value, prepared = prepare(f, client, settings)
        payload = claim_payload(value, prepared["attempt"])
    else:
        value, prepared, granted = grant(f, client, settings)
        payload = consent(value, prepared, granted)
    original = database_module.connect
    count = 0
    class UnknownCommit:
        def __init__(self, connection): self.connection = connection
        def __enter__(self): return self.connection.__enter__()
        def __exit__(self, kind, value, trace):
            nonlocal count
            result = self.connection.__exit__(kind, value, trace)
            if kind is None:
                count += 1
                raise psycopg.OperationalError("synthetic-private-commit-sentinel")
            return result
    monkeypatch.setattr(database_module, "connect", lambda s: UnknownCommit(original(s)))
    response = post(client, settings, f, operation, payload)
    assert response.status_code == 503 and response.json() == {"detail": "Service unavailable"}
    assert count == 1
    monkeypatch.setattr(database_module, "connect", original)
    if operation == "claim":
        with connect(f["admin"]) as db:
            assert db.execute("SELECT state FROM platform.passkey_action_proofs WHERE proof_id=%s",
                              (prepared["attempt"]["attempt_id"],)).fetchone()["state"] == "claimed"
    else:
        assert state(f, prepared)["state"] == "authorized"
    assert post(client, settings, f, operation, payload).status_code == 403


def test_concurrent_claims_have_one_actual_committed_winner(demo_database):
    f = demo_database
    settings, client = api(f)
    value, prepared = prepare(f, client, settings)
    payload = claim_payload(value, prepared["attempt"])
    barrier = Barrier(2)
    def run(_):
        with TestClient(create_app(settings)) as caller:
            barrier.wait(timeout=10)
            return post(caller, settings, f, "claim", payload).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(run, range(2))) == [200, 403]


def test_secret_fields_and_replace_fail_before_database(demo_database, monkeypatch):
    f = demo_database
    settings, client = api(f)
    value = {**prepare_payload(f, "register"), "body_sha256": "e" * 64}
    monkeypatch.setattr(demo, "transaction", lambda *_: pytest.fail("Invalid body reached DB"))
    for body in (
        {**value, "credentials": {"api_key": "synthetic-private-sentinel"}},
        {**value, "target": {**value["target"], "action": "replace",
                            "expected_revision": 1, "expected_storage": 1}},
    ):
        response = post(client, settings, f, "prepare", body)
        assert response.status_code == 422 and response.json() == {"detail": "Invalid request"}
