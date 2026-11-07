import json
import time
from uuid import uuid4

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest

from investalo_api.auth import verify
from investalo_api.main import create_app
from investalo_api.settings import Settings
from conftest import token


def test_no_identity_headers_can_authenticate():
    client = TestClient(create_app(Settings()))
    for target in ("/v1/me", "/v1/overview", "/v1/jobs"):
        response = client.get(target, headers={
            "X-Tenant-Id": str(uuid4()), "X-User-Id": str(uuid4()),
            "Remote-User": "admin", "X-Role": "owner",
        })
        assert response.status_code == 401
        assert response.json() == {"detail": "Authentication required"}
        assert response.headers["cache-control"] == "no-store"


def test_public_information_is_paper_only():
    client = TestClient(create_app(Settings()))
    assert client.get("/health/live").json() == {"status": "ok"}
    assert client.get("/health/ready").status_code == 503
    configuration = client.get("/v1/trading-config").json()
    assert configuration["mode"] == "paper"
    assert configuration["live_enabled"] is False
    assert configuration["assets"] == ["BTC/USDT", "ETH/USDT"]
    assert client.post("/v1/orders/live").status_code == 404
    assert client.get("/docs").status_code == 404


def test_valid_assertion_keeps_opaque_subject(settings):
    identity = verify(token(settings), settings=settings, method="GET", target="/v1/me", body=b"")
    assert identity.subject == "opaque-subject"
    assert identity.tenant_id is None


@pytest.mark.parametrize("claims", [
    {"iss": "attacker"}, {"aud": "different-api"}, {"oidc_iss": "https://other.test"},
    {"exp": 0}, {"exp": int(time.time()) + 600}, {"iat": int(time.time()) + 60},
    {"iat": True}, {"oidc_auth_time": True}, {"oidc_auth_time": int(time.time()) + 60},
    {"sub": ""}, {"jti": "invalid"}, {"tenant_id": str(uuid4())},
    {"tenant_id": str(uuid4()), "auth_epoch": True},
])
def test_bad_claims_rejected(settings, claims):
    with pytest.raises(HTTPException) as error:
        verify(token(settings, claims=claims), settings=settings, method="GET", target="/v1/me", body=b"")
    assert error.value.status_code == 401


@pytest.mark.parametrize("header", [
    {"alg": "none", "typ": "JWT"}, {"alg": "HS384", "typ": "JWT"},
    {"alg": "HS256", "typ": "JWT", "jku": "https://attacker.test"},
])
def test_algorithm_and_remote_key_confusion_rejected(settings, header):
    with pytest.raises(HTTPException):
        verify(token(settings, header=header), settings=settings, method="GET", target="/v1/me", body=b"")


@pytest.mark.parametrize("method,target,body", [
    ("POST", "/v1/me", b""), ("GET", "/v1/jobs", b""),
    ("GET", "/v1/me?admin=true", b""), ("GET", "/v1/me", b"modified"),
])
def test_signature_binds_method_target_and_exact_body(settings, method, target, body):
    with pytest.raises(HTTPException):
        verify(token(settings), settings=settings, method=method, target=target, body=body)


def test_signature_tampering_rejected(settings):
    value = token(settings)
    with pytest.raises(HTTPException):
        verify(value[:-2] + "AA", settings=settings, method="GET", target="/v1/me", body=b"")


@pytest.mark.parametrize("claims", [
    {"jti": 4}, {"tenant_id": True}, {"tenant_id": ""}, {"jti": None},
])
def test_malformed_identifier_types_fail_closed(settings, claims):
    with pytest.raises(HTTPException) as error:
        verify(token(settings, claims=claims), settings=settings, method="GET", target="/v1/me", body=b"")
    assert error.value.status_code == 401


def test_invalid_request_does_not_echo_submitted_private_fields(settings):
    client = TestClient(create_app(settings))
    body = json.dumps({"symbol": "BTC/USDT", "apikey": "do-not-echo-this"}).encode()
    response = client.post(
        "/v1/backtests", content=body,
        headers={
            "Content-Type": "application/json", "Idempotency-Key": str(uuid4()),
            "Authorization": "Bearer " + token(settings, method="POST", target="/v1/backtests", body=body),
        },
    )
    assert response.status_code == 422
    assert "do-not-echo" not in response.text
