#!/usr/bin/env python3
"""Audit the acknowledged IP-082 journal; no sources, orders or performance run."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / p) for p in ("packages/trading/src", "packages/marketdata/src")]

from investalo_marketdata.futures_admission_audit import audit_admissions, audit_json

BASELINE_SHA = "4e7d902c7127b317932c75e3b3878ffcaa3971c7863f077f477d2ca490713cec"
SOURCE_SHA = "2252c6f78054a482a2eb67ecdc344d517aeb46083ce518141ccf0c00b549064c"
PROTOCOL_SHA = "b1892df1eac4a66f157b0576b1efef7017f0e62bccc10c2bedb110441316be21"
AUDIT_FILES = (
    "packages/marketdata/src/investalo_marketdata/futures_admission_audit.py",
    "infra/scripts/audit-futures-admissions.py",
)


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def frozen(name, expected):
    path = ROOT / "docs/research-protocols" / name
    if sha(path) != expected:
        raise ValueError("frozen receipt/protocol changed")
    return json.loads(path.read_bytes())


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: audit-futures-admissions.py NEW_OUTPUT_DIRECTORY")
    baseline = frozen("futures-capital-h1-reserved-cash-market-receipt-20261113.json", BASELINE_SHA)
    preflight = frozen("futures-capital-preflight-receipt-20261112.json", SOURCE_SHA)
    frozen("futures-capital-h1-reserved-cash-20261113.json", PROTOCOL_SHA)
    start_hashes = {p: sha(ROOT / p) for p in (*baseline["implementation_files"], *AUDIT_FILES)}
    for p, expected in baseline["implementation_files"].items():
        if start_hashes[p] != expected:
            raise ValueError("baseline implementation changed; no silent recalculation")
    source = ROOT / "infra/local/futures-capital-research/20261113-h1-reserved-cash"
    for artifact in baseline["artifacts"]:
        path = source / artifact["file"]
        if path.stat().st_size != artifact["bytes"] or sha(path) != artifact["sha256"]:
            raise ValueError("baseline artifact changed")
    output = Path(sys.argv[1]).resolve()
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    report = baseline["reports"][0]
    audited = audit_admissions(
        source / "base-h1-2x/journal.jsonl",
        profile_digest=report["profile_digest"], protocol_digest=PROTOCOL_SHA,
        dataset_digests=tuple(sorted(a["data_digest"] for a in preflight["artifacts"])),
        receipt=report["journal_receipt"], expected_rejections=report["capital_rejections"],
        progress=lambda sequence, rows: print(f"{sequence}/109440 commands; {rows} rejected attempts", flush=True))
    if (audited["accepted_entries"] != sum(report["stage_fill_counts"].values())
            or audited["accepted_entries"] + audited["rejected_attempts"]
            != report["eligible_closed_h1_candidates"]):
        raise ValueError("entry/candidate count differs from frozen report")
    if start_hashes != {p: sha(ROOT / p) for p in start_hashes}:
        raise ValueError("implementation changed during audit")
    for artifact in baseline["artifacts"]:
        if sha(source / artifact["file"]) != artifact["sha256"]:
            raise ValueError("baseline artifact changed during audit")
    audited["baseline_receipt_sha256"] = BASELINE_SHA
    audited["historical_broker_rules_verified"] = False
    audited["summed_shortfalls_are_a_funding_requirement"] = False
    result = output / "audit.json"
    with result.open("xb") as handle:
        handle.write(audit_json(audited))
    result.chmod(0o600)
    receipt = {
        "schema_version": "futures-capital-admission-audit-receipt/1",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "baseline_receipt_sha256": BASELINE_SHA, "protocol_sha256": PROTOCOL_SHA,
        "preflight_sha256": SOURCE_SHA, "implementation_files": start_hashes,
        "artifact": {"file": result.name, "bytes": result.stat().st_size, "sha256": sha(result)},
        "journal_receipt": audited["journal_receipt"], "reason_counts": audited["reason_counts"],
        "accepted_entries": audited["accepted_entries"], "rejected_attempts": audited["rejected_attempts"],
        "full_journal_restore_verified": True, "counterfactual_performance_evaluated": False,
        "execution_enabled": False, "historical_broker_rules_verified": False,
        "python_version": sys.version.split()[0],
    }
    with (output / "receipt.json").open("xb") as handle:
        handle.write(audit_json(receipt))
    print(f"Verified {audited['accepted_entries']} fills / {audited['rejected_attempts']} rejected attempts; {sha(result)}")


if __name__ == "__main__":
    main()
