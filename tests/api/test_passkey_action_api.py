"""Strict proof contracts and transaction receipts, with synthetic data only."""
import asyncio
from contextlib import contextmanager
import json
from time import time
from types import SimpleNamespace
from uuid import uuid4

from fastapi import HTTPException
import pytest

from investalo_api.auth import Assertion
import investalo_api.passkey_action_proofs as proofs
from investalo_api.passkeys import encode_b64url


def target(action="register"):
    result = {"action": action, "platform_account_id": str(uuid4()), "connection_id": str(uuid4())}
    if action != "register":
        result.update(expected_revision=2, expected_storage=3)
    return result


def prepare():
    return {"target": target(), "session_binding": "a" * 64,
            "challenge": encode_b64url(b"c" * 32), "confirmation_hash": "b" * 64,
            "session_expires_at": int(time()) + 3600}


def parse(value, model=proofs.PrepareRequest):
    return proofs.parse_request(json.dumps(value).encode(), model)


def test_prepare_accepts_only_exact_target_and_redacts_proof_binding_material():
    value = prepare()
    request = parse(value)
    assert request.target.action == "register"
    assert request.target.model_fields_set == {"action", "platform_account_id", "connection_id"}
    assert all(value[field] not in repr(request) for field in ("challenge", "confirmation_hash", "session_binding"))


@pytest.mark.parametrize("change", [
    {"rp_id": "foreign.invalid"}, {"auth_epoch": 0}, {"user_id": str(uuid4())},
    {"oidc_auth_time": 1}, {"checked_at": 1}, {"verified": True},
    {"challenge": "A" * 42}, {"challenge": "A" * 42 + "B"},
    {"session_binding": "A" * 64}, {"confirmation_hash": "B" * 64},
    {"session_expires_at": True}, {"session_expires_at": "123"},
    {"session_expires_at": 1.5}, {"session_expires_at": 0},
])
def test_prepare_rejects_browser_authority_and_noncanonical_values(change):
    with pytest.raises(HTTPException) as error:
        parse({**prepare(), **change})
    assert (error.value.status_code, error.value.detail) == (422, "Invalid request")


@pytest.mark.parametrize("change", [
    {"expected_revision": None}, {"expected_storage": None}, {"expected_storage": 3},
    {"broker_uid": "synthetic-private-sentinel"}, {"platform_account_id": "not-a-uuid"},
    {"connection_id": "{" + str(uuid4()) + "}"}, {"action": "transfer"},
])
def test_registration_target_never_accepts_version_or_private_fields(change):
    value = prepare()
    value["target"].update(change)
    with pytest.raises(HTTPException):
        parse(value)


@pytest.mark.parametrize("action", ["replace", "revoke"])
def test_existing_target_requires_current_exact_versions(action):
    value = prepare()
    value["target"] = target(action)
    assert parse(value).target.action == action
    for field in ("expected_revision", "expected_storage"):
        broken = {**value, "target": {key: item for key, item in value["target"].items() if key != field}}
        with pytest.raises(HTTPException):
            parse(broken)
        for bad in (None, True, "3", 0, 1.5):
            with pytest.raises(HTTPException):
                parse({**value, "target": {**value["target"], field: bad}})


def test_target_versions_must_allow_exact_next_js_version():
    value = prepare()
    value["target"] = {**target("replace"), "expected_revision": proofs.SAFE_INTEGER}
    with pytest.raises(HTTPException):
        parse(value)
    value["target"] = {**target("revoke"), "expected_revision": proofs.SAFE_INTEGER}
    assert parse(value).target.expected_revision == proofs.SAFE_INTEGER
    value["target"]["expected_storage"] = proofs.SAFE_INTEGER
    with pytest.raises(HTTPException):
        parse(value)


@pytest.mark.parametrize("wire", [
    b'{"session_binding":"a","session_binding":"b"}',
    b'{"target":{"action":"register","acti\\u006fn":"revoke"}}',
    b'{"session_expires_at":NaN}', b'{"session_expires_at":Infinity}',
    b"\xff", b"[]", b"null", b"{", b" " * 16385,
])
def test_duplicate_nested_keys_nonfinite_and_unbounded_wire_fail_statically(wire):
    with pytest.raises(HTTPException) as error:
        proofs.parse_request(wire, proofs.PrepareRequest)
    assert (error.value.status_code, error.value.detail) == (422, "Invalid request")


def finish():
    return {"attempt_id": str(uuid4()), "session_binding": "a" * 64, "new_counter": 0,
            "backup_eligible": True, "backed_up": False, "checked_at": int(time())}


@pytest.mark.parametrize("change", [
    {"new_counter": -1}, {"new_counter": True}, {"new_counter": 0x1_0000_0000},
    {"backup_eligible": 1}, {"backed_up": "false"}, {"backup_eligible": False, "backed_up": True},
    {"checked_at": 0}, {"checked_at": True}, {"checked_at": "123"},
    {"oidc_auth_time": 1}, {"signature": "synthetic-private-sentinel"},
    {"credential_id": "synthetic-private-sentinel"}, {"passkey_id": str(uuid4())},
])
def test_finish_accepts_only_trusted_bounded_verdict_not_browser_credential_or_identity(change):
    with pytest.raises(HTTPException) as error:
        parse({**finish(), **change}, proofs.FinishRequest)
    assert (error.value.status_code, error.value.detail) == (422, "Invalid request")


def test_finish_and_grant_contracts_are_strict_and_canonical():
    value = finish()
    assert parse(value, proofs.FinishRequest).new_counter == 0
    grant = {"grant_id": str(uuid4()), "session_binding": "a" * 64}
    assert parse(grant, proofs.GrantRequest).grant_id == grant["grant_id"]
    assert parse({**grant, "confirmation_hash": "b" * 64}, proofs.ConfirmRequest).confirmation_hash == "b" * 64
    for patch in ({"confirmation_token": "raw-secret"}, {"confirmed": True}, {"grant_id": "invalid"}):
        with pytest.raises(HTTPException):
            parse({**grant, "confirmation_hash": "b" * 64, **patch}, proofs.ConfirmRequest)


@pytest.fixture
def wire():
    tenant, user = uuid4(), uuid4()
    now = int(time())
    identity = Assertion("synthetic-subject", "https://identity.fixture.invalid",
                         now - 600, uuid4(), now + 30, tenant, 3)
    settings = SimpleNamespace(passkey_rp_id="cockpit.local.test")
    chosen = target()
    row = {
        "attempt_id": uuid4(), "tenant_id": tenant, "user_id": user, "auth_epoch": 3,
        "rp_id": settings.passkey_rp_id, "target": chosen,
        "metadata": {"tenant_id": str(tenant), "auth_epoch": 3, "account": {
            "id": chosen["platform_account_id"], "name": "Synthetic account", "broker": "bitget",
            "mode": "read_only", "status": "disconnected"}, "connection": None},
        "passkey_id": uuid4(), "passkey_storage": 1, "sign_count": 0,
        "backup_eligible": True, "backed_up": False, "credential_id": b"synthetic-credential",
        "user_handle": b"h" * 32, "public_key": b"synthetic-public-key", "enrollment_epoch": 3,
        "session_binding": b"\xaa" * 32, "challenge": b"c" * 32, "confirmation_hash": b"\xbb" * 32,
        "prepared_at": now - 1, "expires_at": now + 119, "session_expires_at": now + 3600,
    }
    return settings, identity, user, row


def grant_row(attempt):
    result = {key: attempt[key] for key in proofs.GRANT_COLUMNS if key in attempt}
    return {**result, "grant_id": uuid4(), "passkey_version": 2, "checked_at": int(time())}


def install_transaction(monkeypatch, wire, rows):
    settings, identity, user, _row = wire
    events = []
    class DB:
        def execute(self, query, values):
            events.append(("sql", query, values))
            return self
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
    monkeypatch.setattr(proofs, "transaction", fake_transaction)
    endpoints = {route.path.rsplit("/", 1)[1]: route.endpoint
                 for route in proofs.create_passkey_action_router(settings).routes}
    return events, endpoints


class Body:
    def __init__(self, value):
        self.value = json.dumps(value).encode()
    async def body(self):
        return self.value


def runtime_patch(patch, now):
    """Resolve time-dependent rejection cases at invocation, never collection."""
    return {field: value(now) if callable(value) else value for field, value in patch.items()}


def test_prepare_commit_sends_original_oidc_claim_and_checks_exact_receipt(monkeypatch, wire):
    _settings, identity, _user, row = wire
    value = {**prepare(), "target": row["target"], "session_expires_at": row["session_expires_at"]}
    events, endpoints = install_transaction(monkeypatch, wire, [row])
    result = asyncio.run(endpoints["prepare"](Body(value), identity))
    assert events[-1] == "commit"
    _sql, query, values = events[1]
    assert "passkey_action_prepare" in query
    assert values[-2:] == (identity.auth_epoch, identity.oidc_auth_time)
    assert identity.oidc_auth_time != result["prepared_at"]
    assert set(result) == {
        "attempt_id", "tenant_id", "user_id", "auth_epoch", "rp_id", "target", "metadata", "credential",
        "session_binding", "challenge", "confirmation_hash", "prepared_at", "expires_at", "session_expires_at",
    }
    assert result["credential"]["storage_version"] == 1


def test_stale_target_cannot_be_silently_upgraded_to_current_sql_snapshot(monkeypatch, wire):
    _settings, identity, _user, row = wire
    value = {**prepare(), "target": {**row["target"], "connection_id": str(uuid4())},
             "session_expires_at": row["session_expires_at"]}
    events, endpoints = install_transaction(monkeypatch, wire, [row])
    with pytest.raises(HTTPException) as error:
        asyncio.run(endpoints["prepare"](Body(value), identity))
    assert (error.value.status_code, error.value.detail) == (409, "Concurrent change")
    assert events[-1] == "rollback"


@pytest.mark.parametrize("patch", [
    {"session_binding": b"\x01" * 32}, {"challenge": b"\x01" * 32},
    {"confirmation_hash": b"\x01" * 32}, {"session_expires_at": lambda now: now + 2500},
])
def test_mismatched_prepare_material_rolls_back_before_reply(monkeypatch, wire, patch):
    _settings, identity, _user, row = wire
    patch = runtime_patch(patch, int(time()))
    value = {**prepare(), "target": row["target"], "session_expires_at": row["session_expires_at"]}
    events, endpoints = install_transaction(monkeypatch, wire, [{**row, **patch}])
    with pytest.raises(HTTPException):
        asyncio.run(endpoints["prepare"](Body(value), identity))
    assert events[-1] == "rollback"


def test_claim_commits_before_reply_and_no_direct_counter_cas_route(monkeypatch, wire):
    _settings, identity, _user, row = wire
    events, endpoints = install_transaction(monkeypatch, wire, [row])
    result = asyncio.run(endpoints["claim"](Body({
        "attempt_id": str(row["attempt_id"]), "session_binding": "a" * 64,
    }), identity))
    assert events[-1] == "commit" and result["attempt_id"] == str(row["attempt_id"])
    assert events[1][2][-2:] == (identity.auth_epoch, identity.oidc_auth_time)
    assert set(endpoints) == {"prepare", "claim", "finish", "grant", "confirm"}


@pytest.mark.parametrize("operation", ["finish", "grant", "confirm"])
def test_grant_receipts_commit_separate_checked_time_and_confirmation_never_executes(monkeypatch, wire, operation):
    _settings, identity, _user, row = wire
    receipt = grant_row(row)
    events, endpoints = install_transaction(monkeypatch, wire, [receipt])
    value = {"session_binding": "a" * 64}
    if operation == "finish":
        value.update(attempt_id=str(row["attempt_id"]), new_counter=0, backup_eligible=True,
                     backed_up=False, checked_at=receipt["checked_at"])
    else:
        value["grant_id"] = str(receipt["grant_id"])
    if operation == "confirm":
        value["confirmation_hash"] = "b" * 64
    result = asyncio.run(endpoints[operation](Body(value), identity))
    assert events[-1] == "commit"
    assert events[1][2][-2:] == (identity.auth_epoch, identity.oidc_auth_time)
    if operation == "confirm":
        assert set(result) == {"status", "execution_enabled", "proof"}
        assert (result["status"], result["execution_enabled"]) == ("verified", False)
        result = result["proof"]
    assert result["checked_at"] == receipt["checked_at"]
    assert result["checked_at"] != identity.oidc_auth_time
    assert set(result) == set(proofs.GRANT_COLUMNS)


@pytest.mark.parametrize("patch", [
    {"tenant_id": uuid4()}, {"user_id": uuid4()}, {"rp_id": "foreign.invalid"},
    {"auth_epoch": True}, {"auth_epoch": 2}, {"attempt_id": "not-a-uuid"},
    {"passkey_id": "not-a-uuid"}, {"passkey_storage": True},
    {"passkey_storage": proofs.SAFE_INTEGER}, {"enrollment_epoch": 2},
    {"session_binding": b"x" * 31}, {"confirmation_hash": b"x" * 33},
    {"challenge": b"x" * 31}, {"public_key": b"x" * 2049},
    {"prepared_at": True}, {"prepared_at": lambda now: now + 10},
    {"expires_at": lambda now: now}, {"expires_at": lambda now: now + 200},
    {"session_expires_at": lambda now: now + 5},
    {"private_envelope": b"synthetic-private-sentinel"},
])
def test_attempt_db_projection_rejects_foreign_private_malformed_or_expired_receipts(monkeypatch, wire, patch):
    settings, identity, user, row = wire
    now = int(time())
    monkeypatch.setattr(proofs, "time", lambda: now)
    patch = runtime_patch(patch, now)
    with pytest.raises(HTTPException) as error:
        proofs.publish_attempt({**row, **patch}, identity, user, settings.passkey_rp_id)
    assert (error.value.status_code, error.value.detail) == (503, "Service unavailable")


@pytest.mark.parametrize("patch", [
    {"grant_id": "invalid"}, {"passkey_version": 1}, {"passkey_version": True},
    {"checked_at": True}, {"checked_at": lambda now: now + 10}, {"checked_at": lambda now: now - 500},
    {"confirmation_hash": b"x" * 31}, {"private_envelope": b"synthetic-private-sentinel"},
])
def test_grant_db_projection_rejects_private_or_invalid_receipts(monkeypatch, wire, patch):
    settings, identity, user, row = wire
    now = int(time())
    monkeypatch.setattr(proofs, "time", lambda: now)
    patch = runtime_patch(patch, now)
    with pytest.raises(HTTPException) as error:
        proofs.publish_grant({**grant_row(row), **patch}, identity, user, settings.passkey_rp_id)
    assert (error.value.status_code, error.value.detail) == (503, "Service unavailable")


@pytest.mark.parametrize("kind", ["owner", "account", "connection", "private", "target"])
def test_metadata_projection_is_exact_owner_bound_and_matches_target(wire, kind):
    settings, identity, user, row = wire
    row = {**row, "metadata": json.loads(json.dumps(row["metadata"]))}
    if kind == "owner":
        row["metadata"]["tenant_id"] = str(uuid4())
    elif kind == "account":
        row["metadata"]["account"]["id"] = str(uuid4())
    elif kind == "connection":
        row["metadata"]["connection"] = {"connection_id": str(uuid4()), "credential_revision": 2,
                                         "storage_version": 3, "status": "active"}
    elif kind == "private":
        row["metadata"]["account"]["broker_uid"] = "synthetic-private-sentinel"
    else:
        row["target"] = {**row["target"], "broker_uid": "synthetic-private-sentinel"}
    with pytest.raises(HTTPException) as error:
        proofs.publish_attempt(row, identity, user, settings.passkey_rp_id)
    assert (error.value.status_code, error.value.detail) == (503, "Service unavailable")


@pytest.mark.parametrize("rp", [None, "", "https://cockpit.local.test", "UPPER.invalid",
                               "127.0.0.1", "cockpit.local.test:8443", "a..invalid"])
def test_invalid_fixed_rp_fails_closed_before_transaction(monkeypatch, wire, rp):
    settings, identity, _user, row = wire
    settings.passkey_rp_id = rp
    events, endpoints = install_transaction(monkeypatch, wire, [row])
    with pytest.raises(HTTPException) as error:
        asyncio.run(endpoints["claim"](Body({
            "attempt_id": str(row["attempt_id"]), "session_binding": "a" * 64,
        }), identity))
    assert error.value.status_code == 503 and events == []
