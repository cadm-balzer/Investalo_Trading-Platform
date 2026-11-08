"""Gated purpose-bound API contracts and fail-closed transaction projections."""
import asyncio
from contextlib import contextmanager
from dataclasses import replace
import json
from time import time
from uuid import uuid4

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest

import investalo_api.passkey_credential_authorizations as authorizations
from investalo_api.main import create_app
from investalo_api.settings import Settings
from test_passkey_action_api import Body, grant_row, prepare, wire


@pytest.fixture
def purpose(wire):
    settings, identity, user, attempt = wire
    settings.passkey_credential_authorizations = True
    settings.passkey_origin = "https://" + settings.passkey_rp_id
    row = {"authorization_id": uuid4(), **attempt, "metadata_sha256": "d" * 64}
    request = authorizations.PrepareRequest.model_validate({
        **prepare(), "target": attempt["target"], "session_expires_at": attempt["session_expires_at"],
        "body_sha256": "e" * 64,
    })
    grant_db = {**grant_row(attempt), "metadata_sha256": row["metadata_sha256"]}
    grant = authorizations.publish_grant(
        {field: grant_db[field] for field in authorizations.GRANT_COLUMNS},
        identity, user, settings.passkey_rp_id,
    )
    consent_request = authorizations.AuthorizeRequest.model_validate({
        "authorization_id": str(row["authorization_id"]), "grant_id": grant["grant_id"],
        "session_binding": grant["session_binding"], "confirmation_hash": grant["confirmation_hash"],
    })
    receipt = {
        "kind": "passkey-credential-authorization/1",
        "authorization_id": consent_request.authorization_id,
        "proof_id": grant["attempt_id"], "grant_id": grant["grant_id"],
        "tenant_id": str(identity.tenant_id), "user_id": str(user), "subject": identity.subject,
        "auth_epoch": identity.auth_epoch, "oidc_issuer": identity.oidc_issuer,
        "oidc_auth_time": identity.oidc_auth_time, "rp_id": settings.passkey_rp_id,
        "origin": settings.passkey_origin, "session_binding": grant["session_binding"],
        "session_expires_at": grant["session_expires_at"], "passkey_id": grant["passkey_id"],
        "passkey_version": grant["passkey_version"], "target": grant["target"],
        "prepared_at": attempt["prepared_at"], "checked_at": grant["checked_at"],
        "authorized_at": int(time()), "expires_at": grant["expires_at"],
        "metadata_sha256": row["metadata_sha256"], "body_sha256": request.body_sha256,
    }
    return settings, identity, user, row, request, grant_db, grant, consent_request, receipt


def install(monkeypatch, purpose, rows):
    settings, identity, user, *_ = purpose
    events = []
    class DB:
        def execute(self, query, values):
            events.append(("sql", query, values))
            return self
        def fetchone(self):
            return rows.pop(0) if rows else None
    @contextmanager
    def transaction(configuration, assertion):
        assert configuration is settings and assertion is identity
        events.append("begin")
        try:
            yield DB(), {"id": user}
        except Exception:
            events.append("rollback")
            raise
        else:
            events.append("commit")
    monkeypatch.setattr(authorizations, "transaction", transaction)
    endpoints = {route.path.rsplit("/", 1)[1]: route.endpoint
                 for route in authorizations.create_passkey_credential_authorization_router(settings).routes}
    return events, endpoints


@pytest.mark.parametrize("enabled", [False, None, 1, "1", "true"])
def test_gate_requires_actual_true_and_defaults_to_404_before_authentication(settings, enabled):
    configuration = replace(settings, passkey_credential_authorizations=enabled)
    client = TestClient(create_app(configuration))
    for operation in ("prepare", "authorize"):
        response = client.post("/v1/passkey-credential-authorizations/" + operation, content=b"not-json")
        assert response.status_code == 404
        assert response.headers["cache-control"] == "no-store"
    assert Settings().passkey_credential_authorizations is False


@pytest.mark.parametrize("value,enabled", [(None, False), ("0", False), ("true", False), ("01", False), ("1", True)])
def test_environment_gate_is_explicit_exact_opt_in(monkeypatch, value, enabled):
    monkeypatch.delenv("API_INTERNAL_AUTH_SECRET_FILE", raising=False)
    monkeypatch.delenv("PGPASSWORD_FILE", raising=False)
    if value is None:
        monkeypatch.delenv("API_PASSKEY_CREDENTIAL_AUTHORIZATIONS", raising=False)
    else:
        monkeypatch.setenv("API_PASSKEY_CREDENTIAL_AUTHORIZATIONS", value)
    monkeypatch.setenv("API_PASSKEY_ORIGIN", "https://cockpit.local.test")
    settings = Settings.from_environment()
    assert settings.passkey_credential_authorizations is enabled
    assert settings.passkey_origin == "https://cockpit.local.test"


@pytest.mark.parametrize("origin", [
    None, "", "http://cockpit.local.test", "https://foreign.test", "https://cockpit.local.test/",
    "https://cockpit.local.test:443", "https://cockpit.local.test:0443", "https://cockpit.local.test:0",
    "https://cockpit.local.test:65536", "https://COCKPIT.local.test", "https://user@cockpit.local.test",
    "https://cockpit.local.test?x=1", "https://cockpit.local.test#x", "https://127.0.0.1",
    "https://localhost", "https://xn--caf-dma.test.", "https://cockpit.local.test\n",
    "https://\ud800.test", "https://bad..host", "https://-bad.host", "https://bad-.host",
    "https://" + "a" * 64 + ".test",
])
def test_invalid_configured_origin_is_static_unavailable_before_transaction(monkeypatch, purpose, origin):
    settings, identity, _user, row, request, *_ = purpose
    settings.passkey_origin = origin
    events, endpoints = install(monkeypatch, purpose, [row])
    with pytest.raises(HTTPException) as error:
        asyncio.run(endpoints["prepare"](Body(request.model_dump(exclude_unset=True)), identity))
    assert (error.value.status_code, error.value.detail) == (503, "Service unavailable")
    assert events == []


def test_canonical_nondefault_https_port_is_allowed(purpose):
    settings, identity, *_ = purpose
    settings.passkey_origin += ":8443"
    assert authorizations._purpose_configuration(settings, identity) == (
        settings.passkey_rp_id, settings.passkey_origin,
    )


@pytest.mark.parametrize("issuer", [
    "https://bad..host", "https://-bad.host", "https://bad-.host", "https://auth.test/",
    "https://auth.test:443", "https://auth.test:65536", "http://auth.test",
])
def test_invalid_authenticated_issuer_is_static_unavailable_before_transaction(monkeypatch, purpose, issuer):
    from dataclasses import replace
    identity = replace(purpose[1], oidc_issuer=issuer)
    revised = (purpose[0], identity, *purpose[2:])
    events, endpoints = install(monkeypatch, revised, [purpose[3]])
    with pytest.raises(HTTPException) as error:
        asyncio.run(endpoints["prepare"](Body(purpose[4].model_dump(exclude_unset=True)), identity))
    assert (error.value.status_code, error.value.detail) == (503, "Service unavailable")
    assert events == []


@pytest.mark.parametrize("extra", [
    {"origin": "https://foreign.test"}, {"rp_id": "foreign.test"}, {"auth_epoch": 0},
    {"authorization_id": str(uuid4())}, {"credentials": {"secret": "PRIVATE_SENTINEL"}},
    {"body": "PRIVATE_SENTINEL"}, {"oidc_auth_time": 1}, {"amr": ["mfa"]},
    {"body_sha256": "A" * 64}, {"body_sha256": "e" * 63}, {"body_sha256": None},
])
def test_prepare_accepts_only_digest_and_exact_bound_request(extra):
    request = {**prepare(), "body_sha256": "e" * 64, **extra}
    with pytest.raises(HTTPException) as error:
        authorizations.parse_request(json.dumps(request).encode(), authorizations.PrepareRequest)
    assert (error.value.status_code, error.value.detail) == (422, "Invalid request")
    assert "PRIVATE_SENTINEL" not in str(error.value)


def test_prepare_redacts_hashes_and_rejects_nested_duplicate_keys():
    value = {**prepare(), "body_sha256": "e" * 64}
    request = authorizations.parse_request(json.dumps(value).encode(), authorizations.PrepareRequest)
    assert value["body_sha256"] not in repr(request)
    raw = json.dumps(value).replace('"body_sha256":', '"body_sha256":"d' + "d" * 63 + '","body_sha256":')
    with pytest.raises(HTTPException):
        authorizations.parse_request(raw.encode(), authorizations.PrepareRequest)


def test_prepare_only_calls_purpose_wrapper_and_commits_authoritative_attempt(monkeypatch, purpose):
    settings, identity, user, row, request, *_ = purpose
    events, endpoints = install(monkeypatch, purpose, [row])
    result = asyncio.run(endpoints["prepare"](Body(request.model_dump(exclude_unset=True)), identity))
    assert events[-1] == "commit"
    _, query, values = events[1]
    assert "FROM platform.passkey_credential_prepare(" in query
    assert values[3:5] == (settings.passkey_rp_id, settings.passkey_origin)
    assert values[8] == request.body_sha256
    assert values[-2:] == (identity.auth_epoch, identity.oidc_auth_time)
    assert set(result) == {"authorization_id", "metadata_sha256", "attempt"}
    assert result["authorization_id"] == str(row["authorization_id"])
    assert result["attempt"]["prepared_at"] != identity.oidc_auth_time
    assert "body_sha256" not in result["attempt"]


@pytest.mark.parametrize("patch", [
    {"authorization_id": "invalid"}, {"metadata_sha256": "A" * 64},
    {"private_secret": "PRIVATE_SENTINEL"}, {"session_expires_at": 1},
    {"confirmation_hash": b"\xcc" * 32}, {"challenge": b"\xff" * 32},
])
def test_preparation_invalid_projection_rolls_back_purpose(monkeypatch, purpose, patch):
    _settings, identity, _user, row, request, *_ = purpose
    events, endpoints = install(monkeypatch, purpose, [{**row, **patch}])
    with pytest.raises(HTTPException):
        asyncio.run(endpoints["prepare"](Body(request.model_dump(exclude_unset=True)), identity))
    assert events[-1] == "rollback"


def test_stale_target_does_not_upgrade_preview(monkeypatch, purpose):
    _settings, identity, _user, row, request, *_ = purpose
    value = request.model_dump(exclude_unset=True)
    value["target"]["connection_id"] = str(uuid4())
    events, endpoints = install(monkeypatch, purpose, [row])
    with pytest.raises(HTTPException) as error:
        asyncio.run(endpoints["prepare"](Body(value), identity))
    assert error.value.status_code == 409
    assert events[-1] == "rollback"


def test_authorize_checks_grant_before_atomic_issuance_and_preserves_old_oidc(monkeypatch, purpose):
    settings, identity, _user, _row, _request, grant_db, _grant, consent, receipt = purpose
    events, endpoints = install(monkeypatch, purpose, [grant_db, {"receipt": receipt}])
    result = asyncio.run(endpoints["authorize"](Body(consent.model_dump()), identity))
    queries = [event for event in events if isinstance(event, tuple)]
    assert len(queries) == 2
    assert "FROM platform.passkey_action_read_grant(" in queries[0][1]
    assert "sha256(convert_to(metadata::text,'UTF8'))" in queries[0][1]
    assert "platform.passkey_credential_authorize(" in queries[1][1]
    assert queries[1][2][-2:] == (identity.auth_epoch, identity.oidc_auth_time)
    assert queries[1][2][2:4] == (settings.passkey_rp_id, settings.passkey_origin)
    assert events[-1] == "commit"
    assert result == {"status": "authorized", "execution_enabled": False, "authorization": receipt}
    assert receipt["oidc_auth_time"] < receipt["checked_at"]


@pytest.mark.parametrize("field,value", [
    ("authorization_id", str(uuid4())), ("proof_id", str(uuid4())), ("grant_id", str(uuid4())),
    ("tenant_id", str(uuid4())), ("user_id", str(uuid4())), ("subject", "foreign"),
    ("auth_epoch", True), ("oidc_issuer", "https://foreign.test"), ("oidc_auth_time", 1),
    ("rp_id", "foreign.test"), ("origin", "https://foreign.test"), ("session_binding", "f" * 64),
    ("session_expires_at", 1), ("passkey_id", str(uuid4())), ("passkey_version", 1),
    ("prepared_at", True), ("checked_at", 1), ("authorized_at", 1), ("expires_at", 1),
    ("metadata_sha256", "f" * 64), ("body_sha256", "A" * 64),
    ("kind", "proof-only"), ("secret", "PRIVATE_SENTINEL"),
])
def test_authorization_bad_durable_receipt_rolls_back_confirmation(monkeypatch, purpose, field, value):
    _settings, identity, *_head, consent, receipt = purpose
    grant_db = purpose[5]
    events, endpoints = install(monkeypatch, purpose, [grant_db, {"receipt": {**receipt, field: value}}])
    with pytest.raises(HTTPException) as error:
        asyncio.run(endpoints["authorize"](Body(consent.model_dump()), identity))
    assert (error.value.status_code, error.value.detail) == (503, "Service unavailable")
    assert "PRIVATE_SENTINEL" not in str(error.value)
    assert events[-1] == "rollback"


def test_wrong_confirmation_leaves_grant_unconsumed(monkeypatch, purpose):
    _settings, identity, *_head, consent, receipt = purpose
    events, endpoints = install(monkeypatch, purpose, [purpose[5], {"receipt": receipt}])
    with pytest.raises(HTTPException) as error:
        asyncio.run(endpoints["authorize"](Body({**consent.model_dump(), "confirmation_hash": "f" * 64}), identity))
    assert error.value.status_code == 403
    assert len([event for event in events if isinstance(event, tuple)]) == 1
    assert events[-1] == "rollback"


def test_transport_expiry_after_database_wait_rolls_back_prepared_authority(monkeypatch, purpose):
    _settings, identity, _user, row, request, *_ = purpose
    events, endpoints = install(monkeypatch, purpose, [row])
    monkeypatch.setattr(authorizations, "time", lambda: identity.expires_at)
    with pytest.raises(HTTPException) as error:
        asyncio.run(endpoints["prepare"](Body(request.model_dump(exclude_unset=True)), identity))
    assert error.value.status_code == 401
    assert events[-1] == "rollback"


def test_grant_expiry_during_issuance_rolls_back_consent(monkeypatch, purpose):
    _settings, identity, *_head, consent, receipt = purpose
    events, endpoints = install(monkeypatch, purpose, [purpose[5], {"receipt": receipt}])
    ticks = iter([receipt["authorized_at"], receipt["expires_at"]])
    monkeypatch.setattr(authorizations, "time", lambda: next(ticks))
    with pytest.raises(HTTPException) as error:
        asyncio.run(endpoints["authorize"](Body(consent.model_dump()), identity))
    assert error.value.status_code == 503
    assert events[-1] == "rollback"
