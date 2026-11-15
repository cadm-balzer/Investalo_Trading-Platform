"""Own metadata boundary: strict domain/projection, current actor and commit."""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
from time import time
from uuid import uuid4

from fastapi import HTTPException
from fastapi.testclient import TestClient
import psycopg
import pytest

from investalo_api.auth import Assertion
from investalo_api.main import create_app
import investalo_api.demo_credential_action as demo


@pytest.fixture
def context():
    tenant, account = uuid4(), uuid4()
    identity = Assertion(subject="synthetic-subject", oidc_issuer="https://idp.test",
        oidc_auth_time=int(time()) - 3600, nonce=uuid4(), expires_at=int(time()) + 30,
        tenant_id=tenant, auth_epoch=0)
    return identity, account, {"metadata": {
        "tenant_id": str(tenant), "auth_epoch": 0, "purpose": "demo_read_only",
        "profile": "bitget-classic-demo-read-secret/1", "environment": "demo",
        "account": {"id": str(account), "name": "Demo", "broker": "bitget",
                    "mode": "bitget_demo", "currency": "USDT", "status": "paused"},
        "connection": {"connection_id": str(uuid4()), "credential_revision": 1,
                       "storage_version": 2, "status": "revoked"},
    }}


class Database:
    def __init__(self, row):
        self.row = row
        self.calls = []

    def execute(self, query, values):
        self.calls.append((query, values))
        if isinstance(self.row, Exception):
            raise self.row
        return self

    def fetchone(self):
        return deepcopy(self.row)


def test_exact_current_actor_query_and_only_own_safe_projection(context):
    identity, account, row = context
    db = Database(row)
    assert demo.action_context(db, account, identity) == row["metadata"]
    assert db.calls == [(
        "SELECT platform.demo_credential_action_context(%s,%s,%s) AS metadata",
        (account, 0, identity.oidc_auth_time))]


@pytest.mark.parametrize("change", ["private", "account", "tenant", "normal", "epoch", "revision", "row"])
def test_malformed_or_foreign_projection_never_published(context, change):
    identity, account, row = context
    value = row["metadata"]
    if change == "private":
        value["broker_uid"] = "synthetic-private"
    elif change == "account":
        value["account"]["id"] = str(uuid4())
    elif change == "tenant":
        value["tenant_id"] = str(uuid4())
    elif change == "normal":
        value["account"]["mode"] = "read_only"
    elif change == "epoch":
        value["auth_epoch"] = 1
    elif change == "revision":
        value["connection"]["credential_revision"] = 2
    else:
        row["envelope"] = "synthetic-private"
    with pytest.raises(HTTPException) as error:
        demo.action_context(Database(row), account, identity)
    assert (error.value.status_code, error.value.detail) == (503, "Service unavailable")


@pytest.mark.parametrize(("error", "status"), [
    (psycopg.errors.InsufficientPrivilege("sensitive"), 403),
    (psycopg.errors.UndefinedFunction("sensitive"), 503),
    (psycopg.OperationalError("sensitive"), 503),
])
def test_no_private_fallback_or_sensitive_database_error(context, error, status):
    identity, account, _ = context
    db = Database(error)
    with pytest.raises(HTTPException) as caught:
        demo.action_context(db, account, identity)
    assert caught.value.status_code == status and "sensitive" not in caught.value.detail
    assert len(db.calls) == 1


def test_metadata_flag_is_independent_and_default_off(settings, monkeypatch):
    path = "/v1/bitget-demo/credential-actions/{account_id}"
    for configuration in (settings, replace(settings, demo_passkey_authorizations=True)):
        assert demo.create_demo_credential_action_router(configuration).routes == []
        assert TestClient(create_app(configuration)).get(path.replace("{account_id}", str(uuid4()))).status_code == 404
    enabled = replace(settings, demo_credential_metadata=True)
    assert any(getattr(route, "path", None) == path for route in
               demo.create_demo_credential_action_router(enabled).routes)
    assert TestClient(create_app(enabled)).get(path.replace("{account_id}", str(uuid4()))).status_code == 401
    monkeypatch.setenv("API_DEMO_CREDENTIAL_METADATA", "true")
    assert settings.from_environment().demo_credential_metadata is False
    monkeypatch.setenv("API_DEMO_CREDENTIAL_METADATA", "1")
    assert settings.from_environment().demo_credential_metadata is True


@pytest.mark.parametrize("outcome", ["owner", "trader", "viewer", "researcher", "commit_unknown", "expired"])
def test_role_gate_and_committed_read_do_not_extend_original_assertion(context, settings, monkeypatch, outcome):
    identity, account, row = context
    db = Database(row)
    @contextmanager
    def tx(configuration, actual):
        assert actual is identity
        yield db, {"role": outcome if outcome in ("viewer", "researcher", "trader") else "owner"}
        if outcome == "commit_unknown":
            raise HTTPException(503, "Service unavailable")
        if outcome == "expired":
            monkeypatch.setattr("investalo_api.passkey_credential_authorizations.time",
                                lambda: identity.expires_at)
    monkeypatch.setattr(demo, "transaction", tx)
    endpoint = next(route.endpoint for route in demo.create_demo_credential_action_router(
        replace(settings, demo_credential_metadata=True)).routes
        if getattr(route, "path", None) == "/v1/bitget-demo/credential-actions/{account_id}")
    if outcome in ("owner", "trader"):
        assert endpoint(account, identity) == row["metadata"]
    else:
        with pytest.raises(HTTPException):
            endpoint(account, identity)
    assert len(db.calls) == (0 if outcome in ("viewer", "researcher") else 1)
