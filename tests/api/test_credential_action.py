"""Metadata publication rejects foreign, malformed and unsafe wire values."""
from contextlib import contextmanager
from copy import deepcopy
from time import time
from uuid import uuid4

from fastapi import HTTPException
import psycopg
import pytest

from investalo_api.auth import Assertion
from investalo_api.credential_action import JS_SAFE_INTEGER, action_context, publish_context
from investalo_api.main import create_app
import investalo_api.main as main


@pytest.fixture
def context():
    tenant, account = uuid4(), uuid4()
    identity = Assertion(
        subject="synthetic-subject", oidc_issuer="https://idp.test",
        oidc_auth_time=int(time()), nonce=uuid4(), expires_at=int(time()) + 30,
        tenant_id=tenant, auth_epoch=0,
    )
    row = {
        "tenant_id": tenant, "auth_epoch": 0, "account_id": account,
        "account_name": "Eigenes Lesekonto", "account_broker": "bitget",
        "account_mode": "read_only", "account_status": "disconnected",
        "connection_id": uuid4(), "credential_revision": 1,
        "storage_version": 2, "connection_status": "active",
    }
    return identity, account, row


def test_metadata_has_only_the_reviewed_public_fields(context):
    identity, account, row = context
    result = publish_context(row, account, identity)
    assert set(result) == {"tenant_id", "auth_epoch", "account", "connection"}
    assert set(result["account"]) == {"id", "name", "broker", "mode", "status"}
    assert set(result["connection"]) == {
        "connection_id", "credential_revision", "storage_version", "status",
    }
    assert result["tenant_id"] == str(identity.tenant_id)
    assert result["connection"]["storage_version"] == 2


def test_unconnected_account_returns_null_and_paused_revoked_remain_visible(context):
    identity, account, row = context
    row.update(account_status="paused", connection_status="revoked")
    assert publish_context(row, account, identity)["connection"]["status"] == "revoked"
    row.update(connection_id=None, credential_revision=None, storage_version=None, connection_status=None)
    assert publish_context(row, account, identity)["connection"] is None


@pytest.mark.parametrize(("field", "value"), [
    ("tenant_id", uuid4()), ("account_id", uuid4()), ("tenant_id", "not-a-uuid"),
    ("auth_epoch", True), ("auth_epoch", -1), ("auth_epoch", JS_SAFE_INTEGER + 1),
    ("credential_revision", True), ("credential_revision", 0),
    ("credential_revision", JS_SAFE_INTEGER + 1), ("storage_version", 0),
    ("storage_version", JS_SAFE_INTEGER + 1), ("storage_version", "2"),
    ("connection_id", None), ("connection_id", "not-a-uuid"),
    ("connection_status", "unknown"), ("account_broker", "mt5"),
    ("account_mode", "paper"), ("account_status", "unknown"),
    ("account_name", "x" * 121), ("account_name", ""), ("account_name", "name\nprivate"),
])
def test_malformed_metadata_fails_closed_without_echoing_values(context, field, value):
    identity, account, row = context
    row[field] = value
    with pytest.raises(HTTPException) as error:
        publish_context(row, account, identity)
    assert error.value.status_code == 503
    assert error.value.detail == "Service unavailable"


@pytest.mark.parametrize("malformation", ["empty", "missing", "private", "not_dict"])
def test_extra_private_columns_and_incomplete_rows_never_cross_boundary(context, malformation):
    identity, account, row = context
    if malformation == "empty":
        row = None
    elif malformation == "missing":
        del row["storage_version"]
    elif malformation == "private":
        row["broker_uid"] = "synthetic-private-uid"
    else:
        row = tuple(row.values())
    with pytest.raises(HTTPException, match="Service unavailable"):
        publish_context(row, account, identity)


def test_concurrent_recovery_epoch_requires_reauthentication(context):
    identity, account, row = context
    row["auth_epoch"] = 1
    with pytest.raises(HTTPException) as error:
        publish_context(row, account, identity)
    assert error.value.status_code == 401
    assert error.value.detail == "Reauthentication required"


def test_largest_exact_js_integer_is_preserved(context):
    identity, account, row = context
    row.update(credential_revision=JS_SAFE_INTEGER, storage_version=JS_SAFE_INTEGER)
    assert publish_context(row, account, identity)["connection"]["storage_version"] == JS_SAFE_INTEGER


@pytest.mark.parametrize(("driver_error", "status", "detail"), [
    (psycopg.errors.InsufficientPrivilege("sensitive sql parameters"), 403, "Access denied"),
    (psycopg.errors.UndefinedFunction("private schema text"), 503, "Service unavailable"),
    (psycopg.OperationalError("private database location"), 503, "Service unavailable"),
])
def test_database_errors_are_static_and_never_fall_back_to_private_select(context, driver_error, status, detail):
    identity, account, _row = context
    class Database:
        def execute(self, query, values):
            assert "platform.credential_action_context(%s)" in query
            assert "credential_connections" not in query
            assert values == (account,)
            raise driver_error
    with pytest.raises(HTTPException) as error:
        action_context(Database(), account, identity)
    assert (error.value.status_code, error.value.detail) == (status, detail)


@pytest.mark.parametrize("role", ["owner", "trader", "viewer", "researcher"])
def test_route_uses_authenticated_transaction_and_gates_role_before_metadata(context, settings, monkeypatch, role):
    identity, account, row = context
    called = []
    class Database:
        def execute(self, _query, _values):
            called.append(True)
            return self
        def fetchone(self):
            return deepcopy(row)
    @contextmanager
    def authenticated_transaction(configuration, assertion):
        assert configuration is settings and assertion is identity
        yield Database(), {"role": role}
    monkeypatch.setattr(main, "transaction", authenticated_transaction)
    endpoint = next(
        route.endpoint for route in create_app(settings).routes
        if route.path == "/v1/credential-actions/{account_id}"
    )
    if role in ("owner", "trader"):
        assert endpoint(account, identity)["account"]["id"] == str(account)
        assert called == [True]
    else:
        with pytest.raises(HTTPException) as error:
            endpoint(account, identity)
        assert error.value.status_code == 403 and not called
