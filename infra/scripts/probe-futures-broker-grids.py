#!/usr/bin/env python3
"""Static current-grid probe of frozen IP-083 evidence, without journal replay."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / name) for name in ("packages/trading/src", "packages/marketdata/src")]

from investalo_marketdata.futures_broker_calibration import (
    VERSION, URL, parse_contracts, quantity_grid_probe,
)
from investalo_marketdata.snapshot import canonical, decode_json, iso

EVIDENCE = "docs/research-protocols/futures-capital-admission-audit-evidence-20261113.json"
EVIDENCE_SHA = "198c9a3ac87b92f141b6583113731842980ade9f989a62601c86940ebb9ee305"
AUDIT_RECEIPT = "docs/research-protocols/futures-capital-admission-audit-receipt-20261113.json"
AUDIT_RECEIPT_SHA = "4e4b5bf91f13cd8771c0f18b051d28b79305a34e4e8695ea90f3d0faa8d5c86b"
IMPLEMENTATION = (
    "packages/marketdata/src/investalo_marketdata/futures_broker_calibration.py",
    "infra/scripts/capture-futures-broker-rules.py",
    "infra/scripts/probe-futures-broker-grids.py",
)


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def verified(path, expected):
    payload = path.read_bytes()
    if sha(payload) != expected:
        raise ValueError("source hash mismatch")
    return payload


def write_new(path, value):
    payload = (canonical(value) + "\n").encode()
    with path.open("xb") as handle:
        handle.write(payload)
    verified(path, sha(payload))
    return sha(payload)


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: probe-futures-broker-grids.py CAPTURE_DIRECTORY NEW_OUTPUT_DIRECTORY")
    capture, output = (Path(value).resolve() for value in sys.argv[1:])
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    receipt_bytes = (capture / "receipt.json").read_bytes()
    receipt = decode_json(receipt_bytes)
    if (receipt["schema_version"] != VERSION or receipt["source_url"] != URL
            or receipt["execution_enabled"] is not False
            or receipt["historical_rules_verified"] is not False):
        raise ValueError("current read-only Classic capture required")
    # Fixed artifact names: never follow path fields supplied by a manifest.
    verified(capture / "contracts.raw.json", receipt["raw_sha256"])
    selected = verified(capture / "contracts.selected.json", receipt["selected_sha256"])
    contracts = parse_contracts(selected)
    if [c.record() for c in contracts] != receipt["rules"]:
        raise ValueError("captured rules mismatch")
    rules = {c.symbol: c for c in contracts}
    evidence = decode_json(verified(ROOT / EVIDENCE, EVIDENCE_SHA))
    original = decode_json(verified(ROOT / AUDIT_RECEIPT, AUDIT_RECEIPT_SHA))
    for path, digest in original["implementation_files"].items():
        verified(ROOT / path, digest)
    implementation = {path: sha((ROOT / path).read_bytes()) for path in IMPLEMENTATION}
    probes = []
    for row in evidence["rejections"]:
        probe = quantity_grid_probe(row, rules[row["symbol"].removeprefix("BINANCE:")])
        probe.update({key: row[key] for key in ("at", "after_sequence", "cycle", "stage", "reasons")})
        probes.append(probe)
    margin_only = [p for p in probes if p["reasons"] == ["initial_margin_requirement"]]
    result = {
        "schema_version": "futures-current-quantity-grid-probe/1",
        "completed_at": iso(datetime.now(timezone.utc)),
        "metadata_receipt_sha256": sha(receipt_bytes),
        "selected_metadata_sha256": receipt["selected_sha256"],
        "evidence_sha256": EVIDENCE_SHA, "audit_receipt_sha256": AUDIT_RECEIPT_SHA,
        "probe_count": len(probes), "source_quantities_on_current_grid": sum(
            p["quantity_reduction"] == "0" for p in probes),
        "margin_only_count": len(margin_only),
        "margin_only_old_model_covered_after_quantity_floor": sum(
            p["old_model_margin_covered"] for p in margin_only),
        "source_symbol_counts": dict(sorted(Counter(p["symbol"] for p in probes).items())),
        "probes": probes, "price_grid_applied": False,
        "historical_rules_verified": False, "broker_admission_verified": False,
        "performance_evaluated": False, "execution_enabled": False,
    }
    for path, digest in original["implementation_files"].items():
        verified(ROOT / path, digest)
    for path, digest in implementation.items():
        verified(ROOT / path, digest)
    result_sha = write_new(output / "probe.json", result)
    write_new(output / "receipt.json", {
        "schema_version": "futures-current-quantity-grid-probe-receipt/1",
        "result_file": "probe.json", "result_sha256": result_sha,
        "baseline_implementation_files": original["implementation_files"],
        "probe_implementation_files": implementation,
        "baseline_implementation_unchanged": True, "journal_replayed": False,
        "performance_evaluated": False, "execution_enabled": False,
    })
    print(f"{len(probes)} static quantity probes; {len(margin_only)} margin-only references.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError):
        raise SystemExit("grid probe failed; preserve output without success receipt") from None
