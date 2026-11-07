from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from uuid import uuid4

from investalo_marketdata import dump_snapshot, synthetic_snapshot
from investalo_trading import EquityPoint
from investalo_api.research_spec import specification
from investalo_api.research_result import publish_result
from investalo_workers.research import (
    compute_result, display_indices, SnapshotInvalid, ConfigurationMismatch,
)
import pytest


def inputs():
    snapshot = synthetic_snapshot(
        "BTC/USDT", bars=150, retrieved_at=datetime(2021, 1, 1, tzinfo=timezone.utc),
    )
    dataset_id = uuid4()
    spec = specification()
    canonical = dump_snapshot(snapshot)
    job = {
        "job_id": uuid4(), "tenant_id": uuid4(), "dataset_id": dataset_id,
        "strategy_version": spec["strategy_version"], "configuration_digest": spec["configuration_digest"],
        "cost_digest": spec["cost_digest"], "frozen_specification": spec,
        "payload": {"symbol": "BTC/USDT", "dataset_id": str(dataset_id), "data_digest": snapshot.data_digest},
    }
    dataset = {"snapshot": json.loads(canonical), "content_digest": hashlib.sha256(canonical.encode()).hexdigest(),
               "data_digest": snapshot.data_digest, "purpose": "test"}
    return job, dataset


def test_actual_snapshot_computation_is_deterministic_and_never_claims_validation():
    job, dataset = inputs()
    result = compute_result(job, dataset)
    assert compute_result(job, dataset) == result
    assert result["synthetic"] is True
    assert result["validation"]["status"] == "not_evaluated"
    assert result["data_digest"] == job["payload"]["data_digest"]
    assert result["source"]["venue"] == "synthetic"
    assert result["coverage"]["complete"] is True
    assert len(result["equity_curve"]) == 601
    assert "state" not in result and "fills" not in result
    assert publish_result(result) == result
    assert "e" not in result["net_pnl"].lower()


def test_frozen_configuration_change_and_snapshot_tampering_fail_closed():
    job, dataset = inputs()
    with pytest.raises(ConfigurationMismatch):
        compute_result({**job, "cost_digest": "0" * 64}, dataset)
    modified = json.loads(json.dumps(dataset["snapshot"]))
    modified["candles"][0]["close"] = "1"
    with pytest.raises(SnapshotInvalid):
        compute_result(job, {**dataset, "snapshot": modified})
    with pytest.raises(SnapshotInvalid):
        compute_result(job, {**dataset, "purpose": "holdout"})
    with pytest.raises(SnapshotInvalid):
        compute_result(job, {**dataset, "content_digest": "0" * 64})


def test_curve_downsampling_preserves_endpoints_extrema_and_worst_drawdown():
    at = datetime(2020, 1, 1, tzinfo=timezone.utc)
    curve = [EquityPoint(at, Decimal("100")) for _ in range(6000)]
    curve[111] = EquityPoint(at, Decimal("200"))
    curve[112] = EquityPoint(at, Decimal("10"))
    curve[5998] = EquityPoint(at, Decimal("300"))
    indices = display_indices(curve)
    assert len(indices) <= 2000
    assert indices == sorted(set(indices))
    assert {0, 5999, 111, 112, 5998}.issubset(indices)


def test_extra_private_result_fields_are_not_publishable():
    from fastapi import HTTPException
    job, dataset = inputs()
    result = compute_result(job, dataset)
    with pytest.raises(HTTPException) as error:
        publish_result({**result, "private_diagnostic": "never-display"})
    assert error.value.status_code == 503
    assert "never-display" not in str(error.value)
