"""Actual restricted017 HTTP/API/PG reads; synthetic structural credentials only."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb
import pytest

from conftest import token
from investalo_api.database import connect
from investalo_api.main import create_app
from test_demo_passkey_authorizations_postgres import (
    demo_database, proof_database, credential_database, database,
)

BASE = "/v1/bitget-demo/credential-actions/"


def api(f, **changes):
    settings = replace(f["runtime"], demo_credential_metadata=True, **changes)
    return settings, TestClient(create_app(settings))


def read(client, settings, f, *, account=None, claims=None, assertion=None, base=BASE):
    path = base + str(account or f["unconnected"])
    bearer = assertion or token(settings, target=path, claims={
        "sub": f["subject_a"], "tenant_id": str(f["tenant_a"]), "auth_epoch": 0,
        "oidc_auth_time": f["original_auth_time"], **(claims or {}),
    })
    return client.get(path, headers={"Authorization": "Bearer " + bearer})


def connection(f):
    connection_id = uuid4()
    with connect(f["admin"]) as db:
        envelope = db.execute("SELECT envelope FROM platform.credential_connections "
                              "WHERE connection_id=%s", (f["connection_a"],)).fetchone()["envelope"]
        db.execute("INSERT INTO platform.demo_credential_connections"
            "(tenant_id,user_id,platform_account_id,connection_id,broker_uid,parent_uid,"
            "egress_ip,provisioning_digest,credential_revision,storage_version,status,envelope)"
            " VALUES(%s,%s,%s,%s,%s,'0','192.0.2.8',%s,1,1,'active',%s)",
            (f["tenant_a"], f["user_a"], f["unconnected"], connection_id,
             str(10**18 + uuid4().int % 10**18), "d" * 64, Jsonb(envelope)))
    return connection_id


def test_current_demo_read_has_no_private_fields_or_purpose_write(demo_database):
    f = demo_database
    settings, client = api(f)
    response = read(client, settings, f)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["connection"] is None and result["account"]["id"] == str(f["unconnected"])
    assert result["purpose"] == "demo_read_only" and result["account"]["currency"] == "USDT"
    assert result["account"]["mode"] == "bitget_demo"
    assert response.headers["cache-control"] == "no-store"
    for private in ("envelope", "broker_uid", "parent_uid", "egress_ip", "provisioning_digest"):
        assert private not in response.text
    with connect(f["admin"]) as db:
        assert db.execute("SELECT count(*) AS n FROM platform.demo_passkey_credential_authorizations a "
                          "JOIN platform.passkey_action_proofs p ON p.proof_id=a.proof_id "
                          "WHERE p.tenant_id=%s", (f["tenant_a"],)).fetchone()["n"] == 0
        assert db.execute("SELECT count(*) AS n FROM platform.demo_credential_connections "
                          "WHERE tenant_id=%s", (f["tenant_a"],)).fetchone()["n"] == 0
        assert db.execute("SELECT count(*) AS n FROM platform.demo_credential_audit "
                          "WHERE tenant_id=%s", (f["tenant_a"],)).fetchone()["n"] == 0


@pytest.mark.parametrize("status", ["active", "revoked"])
def test_paused_connection_retains_actual_storage_and_terminal_status(demo_database, status):
    f = demo_database
    cid = connection(f)
    with connect(f["admin"]) as db:
        db.execute("UPDATE platform.accounts SET status='paused' WHERE id=%s", (f["unconnected"],))
        if status == "revoked":
            db.execute("UPDATE platform.demo_credential_connections SET status='revoked',storage_version=2 "
                       "WHERE connection_id=%s", (cid,))
    settings, client = api(f)
    response = read(client, settings, f)
    assert response.status_code == 200
    assert response.json()["account"]["status"] == "paused"
    assert response.json()["connection"] == {"connection_id": str(cid), "credential_revision": 1,
        "storage_version": 2 if status == "revoked" else 1, "status": status}


@pytest.mark.parametrize("role", ["owner", "trader"])
def test_same_tenant_peer_cannot_discover_foreign_connection_as_empty_slot(demo_database, role):
    f = demo_database
    connection(f)
    with connect(f["admin"]) as db:
        db.execute("INSERT INTO platform.memberships(tenant_id,user_id,role) VALUES(%s,%s,%s)",
                   (f["tenant_a"], f["user_b"], role))
    settings, client = api(f)
    response = read(client, settings, f, claims={"sub": f["subject_b"]})
    assert response.status_code == 403 and response.json() == {"detail": "Access denied"}


@pytest.mark.parametrize("change", ["missing", "tenant", "normal", "paper", "inactive", "viewer", "researcher"])
def test_absent_foreign_or_ineligible_accounts_and_actors_rejected(demo_database, change):
    f = demo_database
    account = f["unconnected"]
    with connect(f["admin"]) as db:
        if change == "missing":
            account = uuid4()
        elif change == "tenant":
            account = f["account_b"]
        elif change == "normal":
            account = f["account_a"]
        elif change == "paper":
            db.execute("UPDATE platform.accounts SET mode='paper' WHERE id=%s", (account,))
        elif change == "inactive":
            db.execute("UPDATE platform.memberships SET active=false WHERE tenant_id=%s AND user_id=%s",
                       (f["tenant_a"], f["user_a"]))
        else:
            db.execute("UPDATE platform.memberships SET role=%s WHERE tenant_id=%s AND user_id=%s",
                       (change, f["tenant_a"], f["user_a"]))
    settings, client = api(f)
    response = read(client, settings, f, account=account)
    assert response.status_code == 403 and response.json() == {"detail": "Access denied"}


@pytest.mark.parametrize("change", ["epoch", "reauth", "inactive"])
def test_latest_user_state_rejects_original_old_session(demo_database, change):
    f = demo_database
    with connect(f["admin"]) as db:
        if change == "epoch":
            db.execute("UPDATE platform.users SET auth_epoch=1 WHERE id=%s", (f["user_a"],))
        elif change == "reauth":
            db.execute("UPDATE platform.users SET reauth_after=%s WHERE id=%s",
                       (datetime.now(timezone.utc) + timedelta(seconds=1), f["user_a"]))
        else:
            db.execute("UPDATE platform.users SET active=false WHERE id=%s", (f["user_a"],))
    settings, client = api(f)
    assert read(client, settings, f).status_code == (403 if change == "inactive" else 401)


def test_request_nonce_and_both_metadata_domains_remain_separate(demo_database):
    f = demo_database
    settings, client = api(f)
    path = BASE + str(f["unconnected"])
    bearer = token(settings, target=path, claims={"sub": f["subject_a"],
        "tenant_id": str(f["tenant_a"]), "auth_epoch": 0, "oidc_auth_time": f["original_auth_time"]})
    assert read(client, settings, f, assertion=bearer).status_code == 200
    assert read(client, settings, f, assertion=bearer).status_code == 401
    assert read(client, settings, f, base="/v1/credential-actions/").status_code == 403
    assert read(client, settings, f, account=f["account_a"]).status_code == 403
    assert read(client, settings, f, account=f["account_a"], base="/v1/credential-actions/").status_code == 200


def test_own_flag_required_and_research_private_grants_still_absent(demo_database):
    f = demo_database
    settings = replace(f["runtime"], demo_passkey_authorizations=True)
    assert read(TestClient(create_app(settings)), settings, f).status_code == 404
    with connect(f["admin"]) as db:
        row = db.execute("""
          SELECT p.prosecdef,p.proconfig,r.rolname,
            has_function_privilege('investalo_runtime',p.oid,'EXECUTE') AS runtime,
            has_function_privilege('investalo_research_worker',p.oid,'EXECUTE') AS research,
            has_function_privilege('investalo_credentials_worker',p.oid,'EXECUTE') AS credentials,
            has_table_privilege('investalo_runtime','platform.demo_credential_connections','SELECT') AS private
          FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace JOIN pg_roles r ON r.oid=p.proowner
          WHERE n.nspname='platform' AND p.proname='demo_credential_action_context'
        """).fetchone()
        assert row == {"prosecdef": True, "proconfig": ["search_path=pg_catalog"],
            "rolname": "investalo_migration", "runtime": True, "research": False,
            "credentials": False, "private": False}
