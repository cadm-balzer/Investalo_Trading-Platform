#!/usr/bin/env python3
"""Read-only local research audit and deterministic replay; never run holdouts."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from uuid import UUID

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / path) for path in (
    "packages/marketdata/src", "packages/trading/src", "services/api/src",
)]
from investalo_marketdata import MAX_BYTES, dump_snapshot, load_snapshot, to_trading_candles
from investalo_api.research_spec import simulator, specification


def main():
    if os.geteuid() != 0 or not (ROOT / "infra/local/READY").exists():
        raise ValueError()
    binding = json.loads((ROOT / "infra/local/research-binding.json").read_text())
    if binding.get("database_role") != "investalo_research_local":
        raise ValueError()
    tenant = UUID(binding["tenant_id"])
    protocol = json.loads((ROOT / "docs/research-protocols/crypto-h4-20261108.json").read_text())
    if (protocol["schema_version"] != "crypto-research-protocol/1"
            or protocol["holdout_status"] != "reserved_not_evaluated"
            or protocol["frozen_specification"] != specification()
            or [item["symbol"] for item in protocol["assets"]] != ["BTC/USDT", "ETH/USDT"]):
        raise ValueError()
    digests = [
        asset[kind]["data_digest"]
        for asset in protocol["assets"] for kind in ("source", "research", "holdout")
    ]
    if any(not isinstance(value, str) or not re.fullmatch("[a-f0-9]{64}", value) for value in digests):
        raise ValueError()
    # Only parsed UUID and strict hexadecimal literals enter the fixed query.
    chosen = ",".join("'" + value + "'" for value in digests)
    statement = f"""
BEGIN READ ONLY;
SELECT jsonb_build_object(
 'datasets', COALESCE((
   SELECT jsonb_agg(jsonb_build_object(
     'id',id,'data_digest',data_digest,'content_digest',content_digest,
     'purpose',purpose,'bar_count',bar_count,'coverage_complete',coverage_complete))
   FROM platform.research_datasets
   WHERE tenant_id='{tenant}' AND data_digest IN ({chosen})), '[]'::jsonb),
 'jobs', COALESCE((
   SELECT jsonb_agg(row_to_json(selected)) FROM (
     SELECT DISTINCT ON (dataset_id) dataset_id,frozen_specification,result
     FROM platform.jobs WHERE tenant_id='{tenant}' AND status='succeeded'
     AND dataset_id IN (SELECT id FROM platform.research_datasets
       WHERE tenant_id='{tenant}' AND purpose='research' AND data_digest IN ({chosen}))
     ORDER BY dataset_id,created_at DESC,id DESC
   ) selected), '[]'::jsonb),
 'holdout_jobs', (SELECT count(*) FROM platform.jobs WHERE tenant_id='{tenant}'
   AND dataset_id IN (SELECT id FROM platform.research_datasets
     WHERE tenant_id='{tenant}' AND purpose='holdout' AND data_digest IN ({chosen})))
);
ROLLBACK;
"""
    completed = subprocess.run([
        "bash", str(ROOT / "infra/scripts/compose.sh"), "exec", "-T", "postgres",
        "psql", "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1",
        "-U", "investalo_admin", "-d", "investalo",
    ], input=statement, text=True, capture_output=True, timeout=20)
    if completed.returncode or len(completed.stdout.encode()) > 2 * 1024 * 1024:
        raise ValueError()
    audit = json.loads(completed.stdout)
    if len(audit["datasets"]) != 4 or len(audit["jobs"]) != 2 or audit["holdout_jobs"] != 0:
        raise ValueError()
    datasets = {item["data_digest"]: item for item in audit["datasets"]}
    jobs = {item["dataset_id"]: item for item in audit["jobs"]}
    reports = []
    for asset in protocol["assets"]:
        for kind in ("research", "holdout"):
            expected = asset[kind]
            actual = datasets[expected["data_digest"]]
            if (actual["purpose"] != kind or actual["bar_count"] != expected["bar_count"]
                    or actual["content_digest"] != expected["content_digest"]
                    or actual["coverage_complete"] is not True):
                raise ValueError()
        # Deliberately read and simulate ONLY research; no holdout file or rows.
        name = asset["symbol"].split("/")[0].lower()
        path = ROOT / f"infra/local/research-data/{name}-research-three-year-20261108.json"
        with path.open("rb") as source:
            payload = source.read(MAX_BYTES + 1)
        snapshot = load_snapshot(payload)
        if (snapshot.data_digest != asset["research"]["data_digest"]
                or hashlib.sha256(dump_snapshot(snapshot).encode()).hexdigest()
                != asset["research"]["content_digest"]):
            raise ValueError()
        job = jobs[datasets[snapshot.data_digest]["id"]]
        result = job["result"]
        if job["frozen_specification"] != protocol["frozen_specification"]:
            raise ValueError()
        replay = simulator().run(to_trading_candles(snapshot),
                                 tenant_id=str(tenant), account_id="local-research-replay")
        expected = {
            "data_digest": snapshot.data_digest,
            "simulation_data_digest": replay.data_digest,
            "configuration_digest": replay.configuration_digest, "cost_digest": replay.cost_digest,
            "net_pnl": format(replay.net_pnl, "f"),
            "maximum_drawdown_fraction": format(replay.maximum_drawdown_fraction, "f"),
            "profit_factor": format(replay.profit_factor, "f") if replay.profit_factor is not None else None,
            "closed_basket_count": replay.closed_basket_count, "bar_count": len(snapshot.candles),
        }
        if (any(result[key] != value for key, value in expected.items())
                or replay.manual_fills_fabricated
                or result["validation"]["status"] != "not_evaluated"):
            raise ValueError()
        reports.append({
            "symbol": snapshot.symbol, "bar_count": len(snapshot.candles),
            "net_pnl": expected["net_pnl"], "profit_factor": expected["profit_factor"],
            "closed_baskets": expected["closed_basket_count"],
            "maximum_drawdown_fraction": expected["maximum_drawdown_fraction"],
        })
    print("PASS: both three-year worker results match independent deterministic replay")
    print("PASS: two reserved holdout datasets, zero holdout jobs; full sources not imported")
    print(json.dumps({"research_only": True, "assets": reports}, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("Local long-history research audit rejected; no private rows emitted.", file=sys.stderr)
        sys.exit(1)
