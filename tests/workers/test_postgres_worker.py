"""Exercise real LOGIN/session_user isolation, leases and once-only publication."""
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
import os
from uuid import uuid4

import psycopg
from psycopg.types.json import Jsonb
import pytest

from investalo_api.database import connect
from investalo_api.import_dataset import import_dataset
from investalo_api.research_spec import specification
from investalo_api.settings import Settings, secret_file
from investalo_marketdata import SnapshotSource, dump_snapshot, synthetic_snapshot
from investalo_workers.research import compute_result, run_once
from investalo_workers.settings import WorkerSettings


@pytest.fixture
def research_database(monkeypatch, tmp_path):
    if not os.getenv("API_TEST_ADMIN_USER") or not os.getenv("API_TEST_RESEARCH_USER"):
        pytest.skip("Requires dedicated isolated Compose research LOGIN and migration identity")
    runtime = Settings.from_environment()
    admin = replace(
        runtime, database_parameters={**runtime.database_parameters, "user": os.environ["API_TEST_ADMIN_USER"]},
        database_password=secret_file("API_TEST_ADMIN_PASSWORD_FILE"),
    )
    worker = WorkerSettings({
        **runtime.connection_parameters(), "user": os.environ["API_TEST_RESEARCH_USER"],
        "password": secret_file("API_TEST_RESEARCH_PASSWORD_FILE"),
    })
    tenant, foreign, user = uuid4(), uuid4(), uuid4()
    with connect(admin) as db:
        db.execute("INSERT INTO platform.tenants(id,name) VALUES(%s,'Worker test'),(%s,'Foreign worker test')",
                   (tenant, foreign))
        db.execute("INSERT INTO platform.users(id,oidc_issuer,oidc_subject) VALUES(%s,%s,%s)",
                   (user, runtime.oidc_issuer, "worker-test-" + uuid4().hex))
        db.execute("INSERT INTO platform.memberships(tenant_id,user_id,role) VALUES(%s,%s,'researcher')",
                   (tenant, user))
        # A real separate LOGIN is rebound only for isolated tests. The running
        # local worker's different role and binding remain untouched.
        db.execute(
            "INSERT INTO platform.research_role_bindings(database_role,tenant_id) VALUES(%s,%s) "
            "ON CONFLICT(database_role) DO UPDATE SET tenant_id=excluded.tenant_id",
            (os.environ["API_TEST_RESEARCH_USER"], tenant),
        )
    snapshot = synthetic_snapshot("BTC/USDT", bars=60)
    dataset = import_dataset(admin, tenant_id=tenant, purpose="test", payload=dump_snapshot(snapshot))
    foreign_dataset = import_dataset(admin, tenant_id=foreign, purpose="test", payload=dump_snapshot(snapshot))
    holdout_snapshot = replace(
        snapshot, synthetic=False, source=SnapshotSource("csv", "csv-v1", None, snapshot.source.retrieved_at),
    )
    holdout = import_dataset(admin, tenant_id=tenant, purpose="holdout", payload=dump_snapshot(holdout_snapshot))
    monkeypatch.setenv("WORKER_HEALTH_FILE", str(tmp_path / "worker-health"))
    return {
        "runtime": runtime, "admin": admin, "worker": worker, "tenant": tenant,
        "foreign": foreign, "user": user, "dataset": dataset,
        "foreign_dataset": foreign_dataset, "holdout": holdout, "snapshot": snapshot,
    }


def enqueue(context, **overrides):
    spec = specification()
    job_id = uuid4()
    payload = {"symbol": "BTC/USDT", "timeframe": "4h",
               "dataset_id": str(context["dataset"]), "data_digest": context["snapshot"].data_digest}
    with connect(context["admin"]) as db:
        db.execute(
            "INSERT INTO platform.jobs(tenant_id,id,created_by,kind,payload,payload_hash,idempotency_key,"
            "dataset_id,strategy_version,configuration_digest,cost_digest,frozen_specification) "
            "VALUES(%s,%s,%s,'backtest',%s,%s,%s,%s,%s,%s,%s,%s)",
            (context["tenant"], job_id, context["user"], Jsonb(payload),
             hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(), uuid4(),
             context["dataset"], spec["strategy_version"], spec["configuration_digest"],
             overrides.get("cost_digest", spec["cost_digest"]), Jsonb(spec)),
        )
    return job_id


def claim(context):
    with context["worker"].connect() as db:
        return db.execute("SELECT * FROM platform.research_claim(5)").fetchone()


def expire(context, job_id):
    with connect(context["admin"]) as db:
        db.execute("UPDATE platform.jobs SET lease_until=clock_timestamp()-interval '1 second' WHERE id=%s",
                   (job_id,))


def test_session_user_cannot_be_replaced_by_tenant_guc_or_group_role(research_database):
    context = research_database
    with context["worker"].connect() as db:
        assert db.execute("SELECT session_user AS role").fetchone()["role"] == os.environ["API_TEST_RESEARCH_USER"]
        db.execute("SELECT set_config('app.tenant_id',%s,true)", (str(context["foreign"]),))
        db.execute("SET LOCAL ROLE investalo_research_worker")
        rows = db.execute("SELECT id FROM platform.research_datasets").fetchall()
        assert [row["id"] for row in rows] == [context["dataset"]]
        assert db.execute("SELECT platform.research_tenant() AS tenant").fetchone()["tenant"] == context["tenant"]
    for statement in (
        "SELECT * FROM platform.users",
        "UPDATE platform.jobs SET status='failed'",
        "UPDATE platform.research_role_bindings SET tenant_id=tenant_id",
        "SET SESSION AUTHORIZATION investalo_migration",
    ):
        with context["worker"].connect() as db:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                db.execute(statement)
    with connect(context["runtime"]) as db:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute("SELECT * FROM platform.research_claim(5)")


def test_lease_fencing_rejects_old_attempt_and_double_publication(research_database):
    context = research_database
    job_id = enqueue(context)
    first = claim(context)
    assert first["job_id"] == job_id and first["attempt_number"] == 1
    with context["worker"].connect() as db:
        assert db.execute("SELECT * FROM platform.research_claim(5)").fetchone() is None
        dataset = db.execute(
            "SELECT snapshot,content_digest,data_digest,purpose FROM platform.research_datasets WHERE id=%s",
            (context["dataset"],),
        ).fetchone()
    result = compute_result(first, dataset)
    expire(context, job_id)
    second = claim(context)
    assert second["attempt_number"] == 2 and second["attempt_token"] != first["attempt_token"]
    with context["worker"].connect() as db:
        assert db.execute("SELECT platform.research_heartbeat(%s,%s,5) AS ok",
                          (job_id, first["attempt_token"])).fetchone()["ok"] is False
        assert db.execute("SELECT platform.research_complete(%s,%s,%s) AS ok",
                          (job_id, first["attempt_token"], Jsonb(result))).fetchone()["ok"] is False
        assert db.execute("SELECT platform.research_heartbeat(%s,%s,5) AS ok",
                          (job_id, second["attempt_token"])).fetchone()["ok"] is True
        assert db.execute("SELECT platform.research_complete(%s,%s,%s) AS ok",
                          (job_id, second["attempt_token"], Jsonb(result))).fetchone()["ok"] is True
        assert db.execute("SELECT platform.research_complete(%s,%s,%s) AS ok",
                          (job_id, second["attempt_token"], Jsonb(result))).fetchone()["ok"] is False
        row = db.execute("SELECT status,result,result_summary FROM platform.jobs WHERE id=%s", (job_id,)).fetchone()
        assert row["status"] == "succeeded"
        assert row["result"] == result
        assert row["result_summary"] == {key: value for key, value in result.items() if key != "equity_curve"}
    with connect(context["admin"]) as db:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute("UPDATE platform.jobs SET status='queued',result=NULL,result_summary=NULL WHERE id=%s",
                       (job_id,))


def test_expired_attempts_are_bounded_and_null_lease_rejected(research_database):
    context = research_database
    job_id = enqueue(context)
    for attempt in range(1, 4):
        row = claim(context)
        assert row["attempt_number"] == attempt
        expire(context, job_id)
    assert claim(context) is None
    with context["worker"].connect() as db:
        row = db.execute("SELECT status,failure_code FROM platform.jobs WHERE id=%s", (job_id,)).fetchone()
        assert row == {"status": "failed", "failure_code": "attempts_exhausted"}
    with context["worker"].connect() as db:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute("SELECT * FROM platform.research_claim(NULL)")


def test_worker_processes_frozen_job_and_reports_configuration_mismatch(research_database):
    context = research_database
    first = enqueue(context)
    assert run_once(context["worker"]) is True
    with context["worker"].connect() as db:
        row = db.execute("SELECT status,result FROM platform.jobs WHERE id=%s", (first,)).fetchone()
        assert row["status"] == "succeeded"
        assert row["result"]["synthetic"] is True
    second = enqueue(context, cost_digest="0" * 64)
    assert run_once(context["worker"]) is True
    with context["worker"].connect() as db:
        row = db.execute("SELECT status,failure_code,result FROM platform.jobs WHERE id=%s", (second,)).fetchone()
        assert row == {"status": "failed", "failure_code": "configuration_mismatch", "result": None}
    assert run_once(context["worker"]) is False


def test_snapshots_are_immutable_even_for_operators(research_database):
    context = research_database
    with connect(context["admin"]) as db:
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.execute("UPDATE platform.research_datasets SET source='{}' WHERE id=%s", (context["dataset"],))


def test_completion_rejects_changed_frozen_costs_and_invalid_numeric_output(research_database):
    context = research_database
    job_id = enqueue(context)
    job = claim(context)
    with context["worker"].connect() as db:
        dataset = db.execute(
            "SELECT snapshot,content_digest,data_digest,purpose FROM platform.research_datasets WHERE id=%s",
            (context["dataset"],),
        ).fetchone()
    result = compute_result(job, dataset)
    variants = [
        {**result, "cost_assumptions": {**result["cost_assumptions"], "fee_rate": "0"}},
        {**result, "simulation_data_digest": "invalid"},
        {**result, "net_pnl": "NaN"},
        {**result, "private_diagnostic": "not-publishable"},
    ]
    for variant in variants:
        with context["worker"].connect() as db:
            with pytest.raises(psycopg.errors.InvalidParameterValue):
                db.execute("SELECT platform.research_complete(%s,%s,%s)",
                           (job_id, job["attempt_token"], Jsonb(variant)))
    with context["worker"].connect() as db:
        assert db.execute("SELECT platform.research_complete(%s,%s,%s) AS ok",
                          (job_id, job["attempt_token"], Jsonb(result))).fetchone()["ok"] is True
