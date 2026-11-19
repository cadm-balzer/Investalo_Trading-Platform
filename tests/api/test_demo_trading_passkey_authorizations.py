"""Own Demo projections reject Normal/private/malformed snapshots before publish."""
from copy import deepcopy
import asyncio
import json
from uuid import uuid4

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest

from investalo_api.main import create_app
import investalo_api.demo_trading_passkey_authorizations as demo
from investalo_api.settings import Settings
from test_passkey_credential_authorizations import purpose, wire


@pytest.fixture
def own(purpose):
    settings, identity, user, row, request, grant_db, _grant, _consent, receipt = purpose
    row = deepcopy(row)
    metadata = row["metadata"]
    metadata.update(purpose="demo_futures_spot_trading", profile="bitget-classic-demo-trading-secret/1", environment="demo")
    metadata["account"].update(mode="bitget_demo", currency="USDT", status="ready")
    metadata["connection"] = None
    metadata["key_authorities"] = None
    target = dict(action="register", platform_account_id=metadata["account"]["id"], connection_id=str(uuid4()))
    row["target"] = target
    request = demo.PrepareRequest.model_validate({**request.model_dump(exclude_unset=True), "target": target})
    grant = deepcopy({key: grant_db[key] for key in demo.GRANT_COLUMNS})
    grant.update(metadata=metadata, target=target)
    receipt = deepcopy(receipt)
    receipt.update(kind="passkey-demo-trading-credential-authorization/1", target=target)
    return settings, identity, user, row, request, grant, receipt


def test_default_off_even_with_normal_flag_and_invalid_bearer(monkeypatch):
    monkeypatch.setattr(demo, "transaction", lambda *_: pytest.fail("Disabled route reached DB"))
    client = TestClient(create_app(Settings(passkey_credential_authorizations=True,
        demo_passkey_authorizations=True, demo_credential_metadata=True)))
    for operation in ("prepare", "claim", "finish", "grant", "authorize"):
        response = client.post("/v1/bitget-demo-trading/passkey-authorizations/" + operation,
                               content=b"not-json", headers={"Authorization": "Bearer invalid"})
        assert response.status_code == 404
        assert response.headers["cache-control"] == "no-store"
    assert demo.create_demo_trading_passkey_authorization_router(
        Settings(demo_trading_passkey_authorizations="1")).routes == []


def test_environment_flag_is_exact_and_independent(monkeypatch):
    monkeypatch.delenv("API_INTERNAL_AUTH_SECRET_FILE", raising=False)
    monkeypatch.delenv("PGPASSWORD_FILE", raising=False)
    monkeypatch.setenv("API_PASSKEY_CREDENTIAL_AUTHORIZATIONS", "1")
    monkeypatch.setenv("API_DEMO_PASSKEY_AUTHORIZATIONS", "1")
    for value, expected in (("true", False), ("0", False), ("1", True)):
        monkeypatch.setenv("API_DEMO_TRADING_PASSKEY_AUTHORIZATIONS", value)
        assert Settings.from_environment().demo_trading_passkey_authorizations is expected


def test_expired_grant_after_commit_is_not_published(own, monkeypatch):
    identity = own[1]
    monkeypatch.setattr(demo, "_live_assertion", lambda *_: None)
    monkeypatch.setattr(demo, "time", lambda: 500)
    with pytest.raises(HTTPException) as error:
        demo._after_commit(identity, 500)
    assert error.value.status_code == 503


@pytest.mark.parametrize("field,value", [
    ("purpose", "real_read_only"), ("profile", "normal"), ("environment", "live"),
    ("purpose", "demo_read_only"), ("profile", "bitget-classic-demo-read-secret/1"),
    ("tenant_id", str(uuid4())), ("auth_epoch", True),
    ("private", "synthetic-secret-sentinel"),
    ("account.mode", "read_only"), ("account.currency", "USD"),
    ("account.broker", "other"), ("account.status", "unexpected"),
    ("account.id", "non-uuid"), ("account.name", "unsafe\nname"),
    ("account.broker_uid", "synthetic-private-sentinel"),
    ("connection", {"connection_id": str(uuid4()), "credential_revision": 1,
                    "storage_version": 1, "status": "active", "envelope": {}}),
    ("key_authorities", ["coow", "cpow", "stow"]),
])
def test_public_projection_rejects_wrong_domain_and_extra_private_fields(own, field, value):
    _, identity, user, row, _, _, _ = own
    path = field.split(".")
    parent = row["metadata"]
    if len(path) == 2:
        parent = parent[path[0]]
    parent[path[-1]] = value
    with pytest.raises(HTTPException) as error:
        demo.publish_attempt({key: row[key] for key in demo.ATTEMPT_COLUMNS}, identity, user, "cockpit.local.test")
    assert error.value.status_code == 503 and error.value.detail == "Service unavailable"


@pytest.mark.parametrize("target", [
    {"action": "replace", "expected_revision": 1, "expected_storage": 1},
    {"action": "revoke", "expected_revision": 2, "expected_storage": 1},
    {"action": "register", "expected_revision": None},
    {"action": "revoke", "expected_revision": True, "expected_storage": 1},
])
def test_request_rejects_replace_revision_change_and_nonexact_versions(own, target):
    request = own[4].model_dump(exclude_unset=True)
    request["target"].update(target)
    with pytest.raises(ValueError):
        demo.PrepareRequest.model_validate(request)


def test_normal_and_demo_receipt_domains_do_not_cross(own):
    _, identity, user, row, request, grant, receipt = own
    rp = receipt["rp_id"]
    prepared = demo.publish_preparation(row, identity, user, rp, request)
    assert prepared["attempt"]["metadata"]["purpose"] == "demo_futures_spot_trading"
    assert demo.publish_grant(grant, identity, user, rp)["target"]["action"] == "register"
    consent = demo.AuthorizeRequest(authorization_id=receipt["authorization_id"],
        grant_id=receipt["grant_id"], session_binding=receipt["session_binding"],
        confirmation_hash=grant["confirmation_hash"].hex())
    public_grant = demo.publish_grant(grant, identity, user, rp)
    assert demo.publish_authorization(receipt, identity, user, rp, receipt["origin"],
                                     consent, public_grant, row["metadata_sha256"])["execution_enabled"] is False
    receipt["kind"] = "passkey-credential-authorization/1"
    with pytest.raises(HTTPException):
        demo.publish_authorization(receipt, identity, user, rp, receipt["origin"],
                                   consent, public_grant, row["metadata_sha256"])


@pytest.mark.parametrize("operation", ("prepare", "claim", "finish", "grant", "authorize"))
def test_live_assertion_is_rechecked_after_commit(own, monkeypatch, operation):
    """A response delayed by commit cannot release an expired transport assertion."""
    settings, identity, user, row, request, grant, receipt = own
    settings = Settings(demo_trading_passkey_authorizations=True, passkey_rp_id=receipt["rp_id"],
                        passkey_origin=receipt["origin"])
    committed = False
    from contextlib import contextmanager

    @contextmanager
    def tx(*_):
        nonlocal committed
        yield object(), {"id": user}
        committed = True

    original = demo._live_assertion
    def live(value):
        if committed:
            raise HTTPException(401, "Authentication required")
        original(value)
    monkeypatch.setattr(demo, "transaction", tx)
    monkeypatch.setattr(demo, "_live_assertion", live)
    monkeypatch.setattr(demo, "_query", lambda _db, function, *_: (
        row if function.endswith("prepare") else
        {key: row[key] for key in demo.ATTEMPT_COLUMNS} if function.endswith("claim") else
        {**grant, "metadata_sha256": row["metadata_sha256"]} if operation == "authorize" else grant))
    class Result:
        def fetchone(self): return {"receipt": receipt}
    monkeypatch.setattr(demo, "_execute", lambda *_: Result())
    bodies = {
        "prepare": request.model_dump(exclude_unset=True),
        "claim": dict(attempt_id=str(row["attempt_id"]), session_binding=request.session_binding),
        "finish": dict(attempt_id=str(row["attempt_id"]), session_binding=request.session_binding,
                       new_counter=0, backup_eligible=True, backed_up=False, checked_at=grant["checked_at"]),
        "grant": dict(grant_id=str(grant["grant_id"]), session_binding=request.session_binding),
        "authorize": dict(authorization_id=receipt["authorization_id"], grant_id=str(grant["grant_id"]),
                          session_binding=request.session_binding,
                          confirmation_hash=grant["confirmation_hash"].hex()),
    }
    class Request:
        async def body(self): return json.dumps(bodies[operation]).encode()
    endpoint = next(route.endpoint for route in demo.create_demo_trading_passkey_authorization_router(settings).routes
                    if route.path.endswith("/" + operation))
    with pytest.raises(HTTPException) as error:
        asyncio.run(endpoint(Request(), identity))
    assert committed and error.value.status_code == 401
