#!/usr/bin/env python3
"""Complete interrupted metric export from existing full journals; create-only."""
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / p) for p in ("packages/trading/src", "packages/marketdata/src")]
from investalo_marketdata.futures_journal_metrics import restore_metrics
from investalo_marketdata.futures_research_profile import ModerateEconomicScenario
from investalo_marketdata.snapshot import canonical, iso

spec = importlib.util.spec_from_file_location("frozen_runner", ROOT / "infra/scripts/backtest-futures-capital.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
SOURCE = ROOT / "infra/local/futures-capital-research/20261113-h1-grid-moderate-leverage"
OUTPUT = ROOT / "infra/local/futures-capital-research/20261113-h1-grid-moderate-completed"


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def sources():
    p = ROOT / "docs/research-protocols/futures-capital-preflight-receipt-20261112.json"
    if sha(p) != runner.PREFLIGHT_SHA256:
        raise ValueError("foreign native preflight")
    receipt = json.loads(p.read_bytes())
    for a in receipt["artifacts"]:
        path = ROOT / "infra/local/futures-h1-research-data/20261112-native-network" / a["file"]
        if sha(path) != a["file_sha256"]:
            raise ValueError("native source changed")
    return tuple(sorted(a["data_digest"] for a in receipt["artifacts"]))


def main():
    if len(sys.argv) != 1:
        raise SystemExit("complete-futures-moderate.py takes no arguments")
    protocol = runner.moderate_protocol()
    references = runner.leverage_references()
    bindings = sources()
    originals = runner.implementation_hashes(runner.GRID_IMPLEMENTATION_FILES)
    for name, value in originals.items():
        committed = subprocess.check_output(["git", "show", f"ada2029:{name}"], cwd=ROOT)
        if hashlib.sha256(committed).hexdigest() != value:
            raise ValueError("original native implementation changed")
    files = (*runner.GRID_IMPLEMENTATION_FILES,
             "packages/marketdata/src/investalo_marketdata/futures_journal_metrics.py",
             "infra/scripts/complete-futures-moderate.py")
    before = runner.implementation_hashes(files)
    saved = {str(p.relative_to(SOURCE)): sha(p)
             for p in SOURCE.glob("base-h1-*/*") if p.is_file()}
    report3 = json.loads((SOURCE / "base-h1-3x/report.json").read_bytes())
    if (sha(SOURCE / "base-h1-3x/report.json") != "467aff932b7591cf35fa2d4f22c0ae8e738d5f6d5ace426586d09e93807c8822"
            or not report3["full_journal_restore_verified"] or report3["fixed_cycle_leverage"] != "3"
            or report3["journal_receipt"]["sequence"] != 106752):
        raise ValueError("completed original 3x reference required")
    if (SOURCE / "receipt.json").exists():
        raise ValueError("interrupted directory must remain without success receipt")
    OUTPUT.mkdir(mode=0o700, exist_ok=False)
    for scenario, names in (
        ("base-h1-3x", ("journal.jsonl", "equity.jsonl", "closed-baskets.json", "report.json")),
        ("base-h1-4x", ("journal.jsonl", "equity.jsonl")),
    ):
        target = OUTPUT / scenario
        target.mkdir(mode=0o700)
        for name in names:
            shutil.copyfile(SOURCE / scenario / name, target / name)
            (target / name).chmod(0o600)
    base = runner.load_economic_protocol(
        (ROOT / "docs/research-protocols/futures-capital-economics-20261112.json").read_bytes())[0]
    scenario = ModerateEconomicScenario("base-h1-4x", 1, Decimal(4), "base", base.path, base.costs)
    print("Restoring existing full 4x journal; no repeated native job", flush=True)
    report4, closed = restore_metrics(
        OUTPUT / "base-h1-4x/journal.jsonl", scenario, protocol, bindings,
        datetime(2022, 8, 1, tzinfo=timezone.utc), datetime(2025, 8, 1, tzinfo=timezone.utc))
    # The original curve must finish at the exact fully restored end valuation.
    with (OUTPUT / "base-h1-4x/equity.jsonl").open() as f:
        rows = 0
        for line in f:
            last = json.loads(line)
            rows += 1
    if rows != 26305 or last["at"] != "2025-08-01T00:00:00Z" or last["equity"] != report4["final_equity"]:
        raise ValueError("native curve/final restore do not agree")
    for name, value in (("report.json", report4), ("closed-baskets.json", closed)):
        with (OUTPUT / "base-h1-4x" / name).open("x") as f:
            f.write(canonical(value) + "\n")
    if (sources() != bindings or runner.leverage_references() != references
            or runner.moderate_protocol() != protocol
            or runner.implementation_hashes(files) != before):
        raise ValueError("source/reference/implementation changed; no success receipt")
    for name, expected in saved.items():
        if sha(SOURCE / name) != expected:
            raise ValueError("interrupted original bytes changed")
    artifacts = []
    for scenario in ("base-h1-3x", "base-h1-4x"):
        for name in ("journal.jsonl", "equity.jsonl", "closed-baskets.json", "report.json"):
            p = OUTPUT / scenario / name
            artifacts.append(dict(file=f"{scenario}/{name}", bytes=p.stat().st_size, sha256=sha(p)))
    receipt = dict(
        schema_version="futures-capital-moderate-completion/1", completed_at=iso(datetime.now(timezone.utc)),
        protocol_sha256=protocol, preflight_sha256=runner.PREFLIGHT_SHA256,
        reports=[report3, report4], reference_reports=references, artifacts=artifacts,
        implementation_files=before, implementation_start_end_verified=True,
        original_implementation_checkpoint="ada2029", original_native_implementation_verified=True,
        full_journal_restore_verified=True, reference_artifacts_verified=True,
        reference_native_job_repeated=False, interrupted_native_job_repeated=False,
        interrupted_original_bytes_verified=saved, execution_enabled=False,
        historical_broker_rules_verified=False, holdout_requested=False, parallel_scenarios=1,
        admission_metrics_reconstructed_4x=False)
    with (OUTPUT / "receipt.json").open("x") as f:
        f.write(canonical(receipt) + "\n")
    print("Verified completion receipt:", OUTPUT / "receipt.json", flush=True)


if __name__ == "__main__":
    main()
