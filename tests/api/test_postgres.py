"""Real PostgreSQL tests. Root runs these in the local Compose API test container."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
import os
from uuid import uuid4

from fastapi.testclient import TestClient
import psycopg
from psycopg.rows import dict_row
import pytest

from investalo_api.database import connect
from investalo_api.main import create_app
from investalo_api.provision import provision
from investalo_api.import_dataset import import_dataset
from investalo_marketdata import dump_snapshot, synthetic_snapshot, SnapshotSource
from investalo_api.settings import Settings, secret_file
from conftest import token


@pytest.fixture
def database():
    if not os.getenv("API_TEST_ADMIN_USER"):
        pytest.skip("Requires isolated Compose PostgreSQL and API_TEST_ADMIN_USER")
    runtime = Settings.from_environment()
    admin = replace(
        runtime, database_parameters={
            **runtime.database_parameters, "user": os.environ["API_TEST_ADMIN_USER"],
        }, database_password=secret_file("API_TEST_ADMIN_PASSWORD_FILE"),
    )
    tenant_a, tenant_b, user_a, user_b = (uuid4() for _ in range(4))
    subject_a, subject_b = "test-" + uuid4().hex, "test-" + uuid4().hex
    with connect(admin) as db:
        db.execute(
            "INSERT INTO platform.users(id,oidc_issuer,oidc_subject) VALUES (%s,%s,%s),(%s,%s,%s)",
            (user_a, runtime.oidc_issuer, subject_a, user_b, runtime.oidc_issuer, subject_b),
        )
        db.execute(
            "INSERT INTO platform.tenants(id,name) VALUES (%s,'Test A'),(%s,'Test B')",
            (tenant_a, tenant_b),
        )
        db.execute(
            "INSERT INTO platform.memberships(tenant_id,user_id,role) VALUES (%s,%s,'owner'),(%s,%s,'viewer')",
            (tenant_a, user_a, tenant_b, user_b),
        )
        db.execute(
            "INSERT INTO platform.accounts(tenant_id,name,broker,mode,currency) "
            "VALUES (%s,'Account A','bitget','paper','USDT'),(%s,'Account B','bitget','paper','USDT')",
            (tenant_a, tenant_b),
        )
    # Append-only test records remain in the isolated test database, no destructive cleanup.
    return runtime, admin, tenant_a, tenant_b, user_a, user_b, subject_a, subject_b


def headers(settings, subject, tenant=None, *, method="GET", target="/v1/me", body=b"", **claims):
    values = {"sub": subject, **claims}
    if tenant:
        values.update(tenant_id=str(tenant), auth_epoch=0)
    return {"Authorization": "Bearer " + token(settings, method=method, target=target, body=body, claims=values)}


def test_rls_default_denies_and_transaction_context_cannot_leak(database):
    runtime, _admin, tenant_a, _b, *_rest = database
    with connect(runtime) as db:
        assert db.execute("SELECT * FROM platform.accounts").fetchall() == []
        db.execute("SELECT set_config('app.tenant_id',%s,true)", (str(tenant_a),))
        rows = db.execute("SELECT * FROM platform.accounts").fetchall()
        assert len(rows) == 1 and rows[0]["tenant_id"] == tenant_a
        db.commit()
        assert db.execute("SELECT * FROM platform.accounts").fetchall() == []
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute("TRUNCATE platform.accounts")


def test_authenticated_memberships_and_cross_tenant_denial(database):
    runtime, _admin, tenant_a, tenant_b, _ua, _ub, subject_a, _sb = database
    client = TestClient(create_app(runtime))
    response = client.get("/v1/me", headers=headers(runtime, subject_a))
    assert response.status_code == 200
    assert [row["tenant_id"] for row in response.json()["memberships"]] == [str(tenant_a)]
    response = client.get(
        "/v1/overview", headers=headers(runtime, subject_a, tenant_b, target="/v1/overview"),
    )
    assert response.status_code == 403
    response = client.get(
        "/v1/overview", headers=headers(runtime, subject_a, tenant_a, target="/v1/overview"),
    )
    assert response.status_code == 200
    assert [row["name"] for row in response.json()["accounts"]] == ["Account A"]


def test_signed_assertion_replay_rejected_across_requests(database):
    runtime, *_others, subject_a, _sb = database
    client = TestClient(create_app(runtime))
    assertion = headers(runtime, subject_a)
    assert client.get("/v1/me", headers=assertion).status_code == 200
    assert client.get("/v1/me", headers=assertion).status_code == 401


def test_persistent_backtest_is_idempotent_and_viewer_cannot_enqueue(database):
    runtime, admin, tenant_a, tenant_b, _ua, _ub, subject_a, subject_b = database
    dataset = import_dataset(admin, tenant_id=tenant_a, purpose="test",
                             payload=dump_snapshot(synthetic_snapshot("BTC/USDT", bars=30)))
    client = TestClient(create_app(runtime))
    body = json.dumps({"symbol": "BTC/USDT", "timeframe": "4h", "dataset_id": str(dataset)}).encode()
    key = str(uuid4())
    def submit(subject, tenant, payload=body, idempotency=key):
        auth = headers(runtime, subject, tenant, method="POST", target="/v1/backtests", body=payload)
        return client.post("/v1/backtests", content=payload, headers={
            **auth, "Content-Type": "application/json", "Idempotency-Key": idempotency,
        })
    first = submit(subject_a, tenant_a)
    again = submit(subject_a, tenant_a)
    assert first.status_code == again.status_code == 202
    assert first.json()["id"] == again.json()["id"]
    assert first.json()["status"] == "queued"
    detail_target = "/v1/jobs/" + first.json()["id"]
    detail = client.get(detail_target, headers=headers(
        runtime, subject_a, tenant_a, target=detail_target,
    ))
    assert detail.status_code == 200
    assert detail.json()["tenant_id"] == str(tenant_a)
    assert detail.json()["result"] is None and detail.json()["failure_code"] is None
    assert client.get(detail_target, headers=headers(
        runtime, subject_b, tenant_b, target=detail_target,
    )).status_code == 404
    assert submit(subject_b, tenant_b, idempotency=str(uuid4())).status_code == 403
    assert submit(subject_a, tenant_a, payload=b'{"symbol":"ETH/USDT"}').status_code == 409


def test_recovery_generation_and_oidc_freshness_reject_old_identity(database):
    runtime, admin, tenant_a, _b, user_a, _ub, subject_a, _sb = database
    with connect(admin) as db:
        db.execute(
            "UPDATE platform.users SET auth_epoch=1,reauth_after=%s WHERE id=%s",
            (datetime.now(timezone.utc) + timedelta(seconds=1), user_a),
        )
    client = TestClient(create_app(runtime))
    assert client.get("/v1/me", headers=headers(runtime, subject_a)).status_code == 401
    assert client.get("/v1/overview", headers=headers(
        runtime, subject_a, tenant_a, target="/v1/overview",
    )).status_code == 401


def test_composite_tenant_foreign_key_rejects_cross_account(database):
    runtime, admin, tenant_a, tenant_b, *_rest = database
    with connect(admin) as db:
        foreign = db.execute("SELECT id FROM platform.accounts WHERE tenant_id=%s", (tenant_b,)).fetchone()["id"]
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            db.execute(
                "INSERT INTO platform.positions(tenant_id,account_id,symbol,quantity,average_price,observed_at) "
                "VALUES (%s,%s,'BTC/USDT',1,100,now())", (tenant_a, foreign),
            )


def test_invitation_is_idempotent_and_never_silently_escalates(database):
    runtime, admin, *_rest = database
    subject = "invitation-" + uuid4().hex
    args = dict(issuer=runtime.oidc_issuer, subject=subject, tenant_name="Invitation test", role="viewer")
    first = provision(admin, **args)
    assert provision(admin, **args) == first
    with pytest.raises(ValueError, match="membership differs"):
        provision(admin, **{**args, "role": "owner"})
    with pytest.raises(ValueError, match="requires investalo_migration"):
        provision(runtime, **args)


def test_overview_preserves_decimal_precision_and_removes_private_journal_payload(database):
    runtime, admin, tenant_a, _b, _ua, _ub, subject_a, _sb = database
    with connect(admin) as db:
        account = db.execute(
            "SELECT id FROM platform.accounts WHERE tenant_id=%s", (tenant_a,),
        ).fetchone()["id"]
        db.execute(
            "INSERT INTO platform.positions(tenant_id,account_id,symbol,quantity,average_price,observed_at) "
            "VALUES(%s,%s,'BTC/USDT',0.123456789012345678,12345.123456789012345678,now())",
            (tenant_a, account),
        )
        db.execute(
            "INSERT INTO platform.journal(tenant_id,account_id,event_type,payload) VALUES "
            "(%s,%s,'paper_fill','{\"symbol\":\"BTC/USDT\",\"apikey\":\"private-do-not-display\"}')",
            (tenant_a, account),
        )
    response = TestClient(create_app(runtime)).get(
        "/v1/overview", headers=headers(runtime, subject_a, tenant_a, target="/v1/overview"),
    )
    assert response.status_code == 200
    position = response.json()["positions"][0]
    assert position["quantity"] == "0.123456789012345678"
    assert position["average_price"] == "12345.123456789012345678"
    assert position["account_id"] == str(account)
    assert response.json()["journal"][0]["symbol"] == "BTC/USDT"
    assert "private-do-not-display" not in response.text
    assert "apikey" not in response.text


def test_dataset_selection_excludes_synthetic_defaults_holdout_and_other_tenants(database):
    runtime, admin, tenant_a, tenant_b, _ua, _ub, subject_a, _sb = database
    fixture = synthetic_snapshot("BTC/USDT", bars=30)
    test_id = import_dataset(admin, tenant_id=tenant_a, purpose="test", payload=dump_snapshot(fixture))
    nonsynthetic = replace(
        fixture, synthetic=False, source=SnapshotSource("csv", "csv-v1", None, fixture.source.retrieved_at),
    )
    holdout = import_dataset(admin, tenant_id=tenant_a, purpose="holdout", payload=dump_snapshot(nonsynthetic))
    foreign = import_dataset(admin, tenant_id=tenant_b, purpose="research", payload=dump_snapshot(nonsynthetic))
    client = TestClient(create_app(runtime))
    response = client.get("/v1/datasets", headers=headers(runtime, subject_a, tenant_a, target="/v1/datasets"))
    assert response.status_code == 200
    assert [row["id"] for row in response.json()["datasets"]] == [str(test_id)]
    assert "candles" not in response.text
    for dataset in (None, holdout, foreign):
        values = {"symbol": "BTC/USDT"}
        if dataset:
            values["dataset_id"] = str(dataset)
        body = json.dumps(values).encode()
        response = client.post("/v1/backtests", content=body, headers={
            **headers(runtime, subject_a, tenant_a, method="POST", target="/v1/backtests", body=body),
            "Content-Type": "application/json", "Idempotency-Key": str(uuid4()),
        })
        assert response.status_code == 409
        assert response.json()["detail"] == "dataset_unavailable"


def test_idempotent_retry_keeps_original_snapshot_after_new_latest_import(database):
    runtime, admin, tenant_a, _b, _ua, _ub, subject_a, _sb = database
    fixture = synthetic_snapshot("BTC/USDT", bars=30)
    source = SnapshotSource("csv", "csv-v1", None, fixture.source.retrieved_at)
    first_dataset = import_dataset(admin, tenant_id=tenant_a, purpose="research",
                                   payload=dump_snapshot(replace(fixture, source=source, synthetic=False)))
    client = TestClient(create_app(runtime))
    key, body = str(uuid4()), b'{"symbol":"BTC/USDT"}'
    def submit():
        return client.post("/v1/backtests", content=body, headers={
            **headers(runtime, subject_a, tenant_a, method="POST", target="/v1/backtests", body=body),
            "Content-Type": "application/json", "Idempotency-Key": key,
        })
    first = submit()
    assert first.status_code == 202
    fixture = synthetic_snapshot("BTC/USDT", bars=31)
    import_dataset(admin, tenant_id=tenant_a, purpose="research",
                   payload=dump_snapshot(replace(fixture, source=source, synthetic=False)))
    again = submit()
    assert again.status_code == 202
    assert again.json()["id"] == first.json()["id"]
    assert again.json()["payload"]["dataset_id"] == str(first_dataset)


def test_import_is_exactly_idempotent_and_rejects_changed_coverage(database):
    _runtime, admin, tenant_a, *_others = database
    fixture = synthetic_snapshot("BTC/USDT", bars=30)
    payload = dump_snapshot(fixture)
    identifier = import_dataset(admin, tenant_id=tenant_a, purpose="test", payload=payload)
    assert import_dataset(admin, tenant_id=tenant_a, purpose="test", payload=payload) == identifier
    changed = replace(fixture, coverage=replace(
        fixture.coverage,
        requested_start=fixture.coverage.actual_start - timedelta(hours=4),
        requested_end=fixture.coverage.actual_end,
    ))
    assert changed.data_digest == fixture.data_digest
    with pytest.raises(ValueError, match="provenance differs"):
        import_dataset(admin, tenant_id=tenant_a, purpose="test", payload=dump_snapshot(changed))
    with connect(admin) as db:
        persisted = db.execute(
            "SELECT snapshot FROM platform.research_datasets WHERE tenant_id=%s AND id=%s",
            (tenant_a, identifier),
        ).fetchone()
    assert persisted["snapshot"] == json.loads(payload)
