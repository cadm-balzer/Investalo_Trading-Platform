"""Pure contract/lifecycle tests; no browser proof or PostgreSQL substituted."""
import asyncio
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
from time import time
from types import SimpleNamespace
from uuid import uuid4

from fastapi import HTTPException
import psycopg
import pytest

from investalo_api.auth import Assertion
import investalo_api.passkeys as passkeys
from investalo_api.passkeys import (
    ClaimRequest, FinishRequest, create_passkey_router, decode_b64url, encode_b64url,
    parse_request, publish_credential,
)


def finish_body():
    return {
        "claim_id": str(uuid4()), "session_binding": "a" * 64,
        "credential_id": encode_b64url(b"synthetic-credential"),
        "public_key": encode_b64url(b"synthetic-public-key"),
        "sign_count": 0, "backup_eligible": True, "backed_up": False,
    }


@pytest.fixture
def wire():
    tenant, user = uuid4(), uuid4()
    now = int(time())
    identity = Assertion("opaque-test-subject", "https://identity.fixture.invalid",
                         now, uuid4(), now + 30, tenant, 3)
    settings = SimpleNamespace(passkey_rp_id="cockpit.local.test")
    row = {
        "passkey_id": uuid4(), "tenant_id": tenant, "user_id": user, "rp_id": settings.passkey_rp_id,
        "credential_id": b"synthetic-credential", "user_handle": b"h" * 32,
        "public_key": b"synthetic-public-key", "sign_count": 0, "backup_eligible": True,
        "backed_up": False, "storage_version": 1, "status": "active", "enrollment_epoch": 3,
    }
    return settings, identity, user, row


def test_ticket_request_strict_canonical_and_redacted():
    token = encode_b64url(b"t" * 32)
    request = parse_request(json.dumps({"token": token, "session_binding": "b" * 64}).encode(), ClaimRequest)
    assert decode_b64url(request.token, 32, 32) == b"t" * 32
    assert token not in repr(request) and "b" * 64 not in repr(request)


@pytest.mark.parametrize("patch", [
    {"token": "A" * 42}, {"token": "A" * 44}, {"token": "A" * 42 + "B"},
    {"token": "!" * 43}, {"token": None}, {"token": 123},
    {"session_binding": "a" * 63}, {"session_binding": "A" * 64}, {"session_binding": "!" * 64},
    {"tenant_id": str(uuid4())}, {"user_id": str(uuid4())}, {"auth_epoch": 0},
    {"rp_id": "attacker.invalid"}, {"credential_id": "private-marker"},
])
def test_ticket_request_rejects_client_authority_and_bad_encoding_without_echo(patch):
    value = {"token": encode_b64url(b"t" * 32), "session_binding": "b" * 64, **patch}
    with pytest.raises(HTTPException) as error:
        parse_request(json.dumps(value).encode(), ClaimRequest)
    assert (error.value.status_code, error.value.detail) == (422, "Invalid request")


@pytest.mark.parametrize("wire", [
    b'{"token":"private-marker","token":"again","session_binding":"' + b"a" * 64 + b'"}',
    b'{"token":"private-marker","nested":{"x":1,"x":2}}',
    b'{"token":NaN}', b'{"token":Infinity}', b'{"token":-Infinity}', b"[]", b"null",
    b"\xff", b"{", b" " * 16385,
])
def test_duplicate_or_resource_invalid_json_is_static(wire):
    with pytest.raises(HTTPException) as error:
        parse_request(wire, ClaimRequest)
    assert (error.value.status_code, error.value.detail) == (422, "Invalid request")


def test_registration_public_bytes_exact_bounds_and_flags():
    value = finish_body()
    value.update(credential_id=encode_b64url(b"x" * 1023), public_key=encode_b64url(b"x" * 2048),
                 sign_count=0xffff_ffff, backup_eligible=False, backed_up=False)
    parsed = parse_request(json.dumps(value).encode(), FinishRequest)
    assert len(decode_b64url(parsed.credential_id, 1, 1023)) == 1023
    assert len(decode_b64url(parsed.public_key, 1, 2048)) == 2048


@pytest.mark.parametrize("patch", [
    {"claim_id": "not-a-uuid"}, {"claim_id": "{" + str(uuid4()) + "}"},
    {"credential_id": ""}, {"credential_id": encode_b64url(b"x" * 1024)},
    {"credential_id": "eA=="}, {"public_key": ""}, {"public_key": encode_b64url(b"x" * 2049)},
    {"sign_count": True}, {"sign_count": 0.5}, {"sign_count": "0"}, {"sign_count": -1},
    {"sign_count": 0x1_0000_0000}, {"backup_eligible": 1}, {"backed_up": "false"},
    {"backup_eligible": False, "backed_up": True}, {"user_handle": "attacker-selected"},
    {"rp_id": "attacker.invalid"}, {"verified": True}, {"user_id": str(uuid4())},
])
def test_finish_never_accepts_extra_crypto_claims_unsafe_counters_or_backup_state(patch):
    with pytest.raises(HTTPException) as error:
        parse_request(json.dumps({**finish_body(), **patch}).encode(), FinishRequest)
    assert (error.value.status_code, error.value.detail) == (422, "Invalid request")


def test_registry_projection_exact_owner_binding_and_canonical_bytes(wire):
    settings, identity, user, row = wire
    result = publish_credential(row, tenant_id=identity.tenant_id, user_id=user, rp_id=settings.passkey_rp_id)
    assert set(result) == set(passkeys.REGISTRY_COLUMNS)
    assert result["user_handle"] == encode_b64url(b"h" * 32)
    assert result["public_key"] == encode_b64url(row["public_key"])
    row["status"] = "revoked"
    assert publish_credential(row, tenant_id=identity.tenant_id, user_id=user, rp_id=settings.passkey_rp_id)["status"] == "revoked"


@pytest.mark.parametrize("patch", [
    {"tenant_id": uuid4()}, {"user_id": uuid4()}, {"rp_id": "other.invalid"},
    {"passkey_id": "not-uuid"}, {"credential_id": b""}, {"credential_id": b"x" * 1024},
    {"user_handle": b"h" * 31}, {"public_key": b"x" * 2049}, {"public_key": "not-bytes"},
    {"sign_count": True}, {"sign_count": 0x1_0000_0000}, {"storage_version": 0},
    {"storage_version": passkeys.SAFE_INTEGER + 1}, {"enrollment_epoch": True},
    {"enrollment_epoch": passkeys.SAFE_INTEGER + 1}, {"backup_eligible": 1},
    {"backup_eligible": False, "backed_up": True}, {"status": "live"},
    {"token_hash": b"private-token-marker"}, {"oidc_subject": "private-subject-marker"},
])
def test_registry_rejects_foreign_or_invalid_rows_before_publication(wire, patch):
    settings, identity, user, row = wire
    with pytest.raises(HTTPException) as error:
        publish_credential({**row, **patch}, tenant_id=identity.tenant_id, user_id=user, rp_id=settings.passkey_rp_id)
    assert (error.value.status_code, error.value.detail) == (503, "Service unavailable")


def install_transaction(monkeypatch, wire, rows):
    settings, identity, user, _row = wire
    events = []
    class DB:
        def execute(self, query, values):
            events.append(("sql", query, values))
            return self
        def fetchall(self):
            return rows
        def fetchone(self):
            return rows[0] if rows else None
    @contextmanager
    def fake_transaction(configuration, assertion):
        assert configuration is settings and assertion is identity
        events.append("begin")
        try:
            yield DB(), {"id": user, "auth_epoch": 3, "role": "owner"}
        except Exception:
            events.append("rollback")
            raise
        else:
            events.append("commit")
    monkeypatch.setattr(passkeys, "transaction", fake_transaction)
    endpoints = {route.path: route.endpoint for route in create_passkey_router(settings).routes}
    return events, endpoints


class Body:
    def __init__(self, value):
        self.value = json.dumps(value).encode()
    async def body(self):
        return self.value


def test_context_is_authoritative_and_no_missing_registry_is_fabricated(monkeypatch, wire):
    settings, identity, user, row = wire
    for rows in ([], [row]):
        events, endpoints = install_transaction(monkeypatch, wire, rows)
        result = endpoints["/v1/passkeys/context"](identity)
        assert result["user_id"] == str(user) and result["auth_epoch"] == 3
        assert result["credential"] is None if not rows else result["credential"]["status"] == "active"
        assert events[-1] == "commit"
    events, endpoints = install_transaction(monkeypatch, wire, [row, row])
    with pytest.raises(HTTPException):
        endpoints["/v1/passkeys/context"](identity)
    assert events[-1] == "rollback"


def test_claim_commits_before_reply_and_sends_only_decoded_token_digest_to_sql(monkeypatch, wire):
    settings, identity, user, _row = wire
    claim = {
        "claim_id": uuid4(), "user_handle": b"h" * 32,
        "expires_at": datetime.now(timezone.utc) + timedelta(seconds=119),
        "tenant_id": identity.tenant_id, "user_id": user, "auth_epoch": 3,
    }
    events, endpoints = install_transaction(monkeypatch, wire, [claim])
    token = encode_b64url(b"t" * 32)
    result = asyncio.run(endpoints["/v1/passkeys/enrollment/claim"](
        Body({"token": token, "session_binding": "b" * 64}), identity,
    ))
    assert events[-1] == "commit"
    _sql, query, values = events[1]
    assert "passkey_claim_enrollment" in query
    assert values == (hashlib.sha256(b"t" * 32).digest(), settings.passkey_rp_id, b"\xbb" * 32, 3, identity.oidc_auth_time)
    assert token not in repr(values)
    assert set(result) == {"claim_id", "user_handle", "expires_at", "tenant_id", "user_id", "auth_epoch", "rp_id"}
    assert result["rp_id"] == settings.passkey_rp_id


@pytest.mark.parametrize("patch", [
    {"rp_id": "other.invalid"}, {"credential_id": b"wrong-id"}, {"public_key": b"wrong-key"},
    {"sign_count": 2}, {"backed_up": True}, {"status": "revoked"},
    {"storage_version": 2}, {"enrollment_epoch": 2},
])
def test_finish_wrong_rp_or_receipt_rolls_back_entire_write_before_reply(monkeypatch, wire, patch):
    _settings, identity, _user, row = wire
    events, endpoints = install_transaction(monkeypatch, wire, [{**row, **patch}])
    with pytest.raises(HTTPException):
        asyncio.run(endpoints["/v1/passkeys/enrollment/finish"](Body(finish_body()), identity))
    assert events[-1] == "rollback"


def test_finish_receipt_bound_to_exact_public_material_and_no_cas_http_route(monkeypatch, wire):
    _settings, identity, _user, row = wire
    events, endpoints = install_transaction(monkeypatch, wire, [row])
    result = asyncio.run(endpoints["/v1/passkeys/enrollment/finish"](Body(finish_body()), identity))
    assert events[-1] == "commit"
    assert result["credential_id"] == finish_body()["credential_id"]
    assert set(endpoints) == {"/v1/passkeys/context", "/v1/passkeys/enrollment/claim", "/v1/passkeys/enrollment/finish"}


@pytest.mark.parametrize("error,status,detail", [
    (psycopg.errors.InsufficientPrivilege("private-driver-marker"), 403, "Access denied"),
    (psycopg.errors.SerializationFailure("private-driver-marker"), 409, "Concurrent change"),
    (psycopg.errors.InvalidParameterValue("private-driver-marker"), 422, "Invalid request"),
    (psycopg.errors.UndefinedFunction("private-driver-marker"), 503, "Service unavailable"),
])
def test_driver_errors_never_publish_sql_or_inputs(error, status, detail):
    class DB:
        def execute(self, *_args):
            raise error
    with pytest.raises(HTTPException) as result:
        passkeys._execute(DB(), "private sql", ("private-input",))
    assert (result.value.status_code, result.value.detail) == (status, detail)


@pytest.mark.parametrize("rp", [None, "", "https://cockpit.local.test", "UPPER.invalid",
                               "127.0.0.1", "cockpit.local.test:8443", "a..invalid"])
def test_missing_or_invalid_fixed_rp_fails_closed_before_database(monkeypatch, wire, rp):
    settings, identity, _user, row = wire
    settings.passkey_rp_id = rp
    events, endpoints = install_transaction(monkeypatch, wire, [row])
    with pytest.raises(HTTPException) as error:
        endpoints["/v1/passkeys/context"](identity)
    assert error.value.status_code == 503 and events == []
