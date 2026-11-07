"""Actual PostgreSQL checks; root applies 005 and runs in the isolated API profile."""
import base64
from time import time
from uuid import uuid4

from fastapi import HTTPException
from fastapi.testclient import TestClient
import psycopg
from psycopg.types.json import Jsonb
import pytest

from investalo_api.auth import Assertion
from investalo_api.credential_action import action_context
from investalo_api.database import connect, transaction
from investalo_api.main import create_app
from test_postgres import database, headers


@pytest.fixture
def credential_database(database):
    runtime, admin, tenant_a, tenant_b, user_a, user_b, subject_a, subject_b = database
    account_a, account_b, connection_a = uuid4(), uuid4(), uuid4()
    # Opaque structural test bytes; no AEAD validity or real credential claimed.
    encode = lambda count: base64.b64encode(b"\x01" * count).decode("ascii")
    envelope = {
        "schema_version": "credential-envelope/1", "kek_id": "metadata-test-only",
        "payload_nonce": encode(12), "wrap_nonce": encode(12),
        "wrapped_dek": encode(48), "ciphertext": encode(32),
    }
    with connect(admin) as db:
        assert db.execute(
            "SELECT 1 FROM platform.schema_migrations WHERE version='005_credential_action_context'"
        ).fetchone(), "Root must apply additive migration005 before metadata PG tests"
        db.execute(
            "INSERT INTO platform.accounts(tenant_id,id,name,broker,mode,currency) "
            "VALUES (%s,%s,'Metadata A','bitget','read_only','USDT'),"
            "(%s,%s,'Metadata B','bitget','read_only','USDT')",
            (tenant_a, account_a, tenant_b, account_b),
        )
        db.execute(
            "INSERT INTO platform.credential_connections"
            "(tenant_id,user_id,platform_account_id,connection_id,broker_uid,"
            "credential_revision,storage_version,status,envelope) "
            "VALUES(%s,%s,%s,%s,%s,1,1,'active',%s)",
            (tenant_a, user_a, account_a, connection_a,
             str(10**19 + uuid4().int % (10**19)), Jsonb(envelope)),
        )
    return {
        "runtime": runtime, "admin": admin, "tenant_a": tenant_a, "tenant_b": tenant_b,
        "user_a": user_a, "user_b": user_b, "subject_a": subject_a, "subject_b": subject_b,
        "account_a": account_a, "account_b": account_b, "connection_a": connection_a,
    }


def identity(fixture, *, user="a", tenant="a"):
    now = int(time())
    return Assertion(
        subject=fixture["subject_" + user], oidc_issuer=fixture["runtime"].oidc_issuer,
        oidc_auth_time=now, nonce=uuid4(), expires_at=now + 30,
        tenant_id=fixture["tenant_" + tenant], auth_epoch=0,
    )


def metadata(fixture, account=None, assertion=None):
    assertion = assertion or identity(fixture)
    with transaction(fixture["runtime"], assertion) as (db, _user):
        return action_context(db, account or fixture["account_a"], assertion)


def test_metadata_actual_runtime_wire_and_no_private_fields(credential_database):
    f = credential_database
    result = metadata(f)
    assert result == {
        "tenant_id": str(f["tenant_a"]), "auth_epoch": 0,
        "account": {"id": str(f["account_a"]), "name": "Metadata A",
                    "broker": "bitget", "mode": "read_only", "status": "disconnected"},
        "connection": {"connection_id": str(f["connection_a"]), "credential_revision": 1,
                       "storage_version": 1, "status": "active"},
    }


def test_metadata_unconnected_account_is_null(credential_database):
    f = credential_database
    with connect(f["admin"]) as db:
        db.execute(
            "INSERT INTO platform.memberships(tenant_id,user_id,role) VALUES(%s,%s,'trader')",
            (f["tenant_b"], f["user_a"]),
        )
    result = metadata(f, f["account_b"], identity(f, tenant="b"))
    assert result["connection"] is None and result["account"]["id"] == str(f["account_b"])


@pytest.mark.parametrize("status", ["active", "revoked"])
def test_paused_own_connection_visible_including_terminal_revoke(credential_database, status):
    f = credential_database
    with connect(f["admin"]) as db:
        db.execute("UPDATE platform.accounts SET status='paused' WHERE tenant_id=%s AND id=%s",
                   (f["tenant_a"], f["account_a"]))
        if status == "revoked":
            db.execute(
                "UPDATE platform.credential_connections SET status='revoked',storage_version=storage_version+1 "
                "WHERE tenant_id=%s AND connection_id=%s", (f["tenant_a"], f["connection_a"]),
            )
    result = metadata(f)
    assert result["account"]["status"] == "paused"
    assert result["connection"]["status"] == status
    assert result["connection"]["storage_version"] == (2 if status == "revoked" else 1)


def test_same_tenant_other_user_binding_is_denied_instead_of_registration_slot(credential_database):
    f = credential_database
    with connect(f["admin"]) as db:
        db.execute(
            "INSERT INTO platform.memberships(tenant_id,user_id,role) VALUES(%s,%s,'owner')",
            (f["tenant_a"], f["user_b"]),
        )
    with pytest.raises(HTTPException) as error:
        metadata(f, assertion=identity(f, user="b"))
    assert (error.value.status_code, error.value.detail) == (403, "Access denied")


@pytest.mark.parametrize("foreign", [True, False])
def test_absent_and_cross_tenant_accounts_have_identical_denial(credential_database, foreign):
    f = credential_database
    with pytest.raises(HTTPException) as error:
        metadata(f, f["account_b"] if foreign else uuid4())
    assert (error.value.status_code, error.value.detail) == (403, "Access denied")


@pytest.mark.parametrize("change", ["viewer", "researcher", "inactive_user", "inactive_membership"])
def test_sql_rechecks_current_user_and_membership_authority(credential_database, change):
    f = credential_database
    assertion = identity(f)
    # Establish the ordinary transaction first, then change authority through
    # a separate admin transaction before the new helper's recheck.
    with transaction(f["runtime"], assertion) as (db, _user):
        with connect(f["admin"]) as admin:
            if change == "inactive_user":
                admin.execute("UPDATE platform.users SET active=false WHERE id=%s", (f["user_a"],))
            elif change == "inactive_membership":
                admin.execute("UPDATE platform.memberships SET active=false WHERE tenant_id=%s AND user_id=%s",
                              (f["tenant_a"], f["user_a"]))
            else:
                admin.execute("UPDATE platform.memberships SET role=%s WHERE tenant_id=%s AND user_id=%s",
                              (change, f["tenant_a"], f["user_a"]))
        with pytest.raises(HTTPException) as error:
            action_context(db, f["account_a"], assertion)
        assert error.value.status_code == 403
        # A denied SQL statement aborts this test's manually caught transaction.
        db.rollback()


@pytest.mark.parametrize(("broker", "mode"), [("bitget", "paper"), ("mt5", "mt5_demo")])
def test_wrong_account_family_is_denied(credential_database, broker, mode):
    f = credential_database
    with connect(f["admin"]) as db:
        db.execute("UPDATE platform.accounts SET broker=%s,mode=%s WHERE tenant_id=%s AND id=%s",
                   (broker, mode, f["tenant_a"], f["account_a"]))
    with pytest.raises(HTTPException) as error:
        metadata(f)
    assert error.value.status_code == 403


@pytest.mark.parametrize("setting", ["app.user_id", "app.tenant_id", "app.oidc_subject", "app.oidc_issuer"])
def test_forged_partial_guc_context_is_denied(credential_database, setting):
    f = credential_database
    assertion = identity(f)
    with transaction(f["runtime"], assertion) as (db, _user):
        db.execute("SELECT set_config(%s,%s,true)", (setting, "malformed-or-foreign"))
        with pytest.raises(HTTPException) as error:
            action_context(db, f["account_a"], assertion)
        assert error.value.status_code == 403
        db.rollback()


def test_recovery_racing_metadata_read_rejects_new_epoch(credential_database):
    f = credential_database
    assertion = identity(f)
    with transaction(f["runtime"], assertion) as (db, _user):
        with connect(f["admin"]) as admin:
            admin.execute("UPDATE platform.users SET auth_epoch=auth_epoch+1 WHERE id=%s", (f["user_a"],))
        with pytest.raises(HTTPException) as error:
            action_context(db, f["account_a"], assertion)
        assert error.value.status_code == 401


def test_only_metadata_execute_granted_and_private_access_remains_denied(credential_database):
    f = credential_database
    with connect(f["admin"]) as db:
        row = db.execute(
            "SELECT p.prosecdef,p.proconfig,r.rolname AS owner FROM pg_catalog.pg_proc p "
            "JOIN pg_catalog.pg_roles r ON r.oid=p.proowner "
            "WHERE p.oid='platform.credential_action_context(uuid)'::regprocedure"
        ).fetchone()
        assert row == {"prosecdef": True, "proconfig": ["search_path=pg_catalog"], "owner": "investalo_migration"}
        for role in ("investalo_runtime", "investalo_research_worker", "investalo_credentials_worker"):
            granted = db.execute(
                "SELECT has_function_privilege(%s,'platform.credential_action_context(uuid)','EXECUTE') AS allowed",
                (role,),
            ).fetchone()["allowed"]
            assert granted is (role == "investalo_runtime")
            for table in (
                "credential_connections", "credential_role_bindings",
                "credential_onboarding_requests", "credential_onboarding_audit",
            ):
                assert not db.execute(
                    "SELECT has_table_privilege(%s,%s,'SELECT') AS allowed", (role, "platform." + table),
                ).fetchone()["allowed"]
        for function in ("platform.credential_context()", "platform.credential_read(uuid)"):
            assert not db.execute(
                "SELECT has_function_privilege('investalo_runtime',%s,'EXECUTE') AS allowed", (function,),
            ).fetchone()["allowed"]
    with connect(f["runtime"]) as db:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute("SELECT envelope FROM platform.credential_connections")
    with connect(f["runtime"]) as db:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute("SELECT platform.credential_read(%s)", (f["connection_a"],))


def test_http_route_requires_signed_bound_context_and_preserves_no_store(credential_database):
    f = credential_database
    target = "/v1/credential-actions/" + str(f["account_a"])
    client = TestClient(create_app(f["runtime"]))
    assert client.get(target).status_code == 401
    assert client.get(target, headers={"x-tenant-id": str(f["tenant_a"])}).status_code == 401
    response = client.get(target, headers=headers(
        f["runtime"], f["subject_a"], f["tenant_a"], target=target,
    ))
    assert response.status_code == 200
    assert response.json()["connection"]["connection_id"] == str(f["connection_a"])
    assert response.headers["cache-control"] == "no-store"
    assert not any(field in response.text for field in ("broker_uid", "parent_uid", "envelope", "kek_id"))
