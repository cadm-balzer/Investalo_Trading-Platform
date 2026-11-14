#!/usr/bin/env python3
"""Archive public native funding/minute references; never enable a Paper policy."""
import argparse
import hashlib
import os
from pathlib import Path
import runpy
import stat
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "packages/marketdata/src"), str(ROOT / "packages/trading/src")]
from investalo_marketdata.futures_settlement_source import (
    BitgetSettlementSource, SettlementEvidence, fetch_settlement_json,
)
from investalo_marketdata.snapshot import canonical, decode_json, parse_time
from investalo_trading.snapshot import _decode

write_new = runpy.run_path(str(ROOT / "infra/scripts/capture-futures-paper-feed.py"))["write_new"]


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def capture(output, settled_at):
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    sync_directory(output.parent)
    paths = []

    def fetch(url):
        payload = fetch_settlement_json(url)
        path = output / f"response-{len(paths) + 1:02}.json"
        sha = write_new(path, payload)
        paths.append((url, path, sha))
        return payload

    evidence = BitgetSettlementSource(fetch).collect(settled_at)
    if len(paths) != 10:
        raise ValueError("complete ten-response native cohort required")
    for (url, path, sha), read in zip(paths, evidence.reads, strict=True):
        if url != read.url or sha != read.response_digest or hashlib.sha256(path.read_bytes()).hexdigest() != sha:
            raise ValueError("native source response hash mismatch")
    data_digest = write_new(output / "observation.json", evidence.record())
    restored = _decode(SettlementEvidence, decode_json((output / "observation.json").read_bytes())["observation"])
    if restored != evidence or restored.data_digest != data_digest:
        raise ValueError("native reference roundtrip mismatch")
    receipt = {
        "schema_version": "bitget-classic-futures-settlement-capture/1",
        "settled_at": evidence.settled_at.isoformat(), "collected_at": evidence.collected_at.isoformat(),
        "data_digest": data_digest, "native_funding": len(evidence.funding),
        "mark_minutes": len(evidence.minutes), "reference_policy": evidence.record()["reference_policy"],
        "reference_enabled": False, "exact_settlement_mark_available": False,
        "paper_worker_enabled": False, "execution_enabled": False,
        "response_hashes": [{"file": p.name, "sha256": sha} for _, p, sha in paths],
    }
    receipt_digest = write_new(output / "receipt.json", receipt)
    sync_directory(output)
    return {"directory": str(output), "receipt_sha256": receipt_digest, **receipt}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="new directory under an existing owned protected parent")
    parser.add_argument("--settled-at", required=True, type=parse_time, help="exact native UTC settlement time")
    args = parser.parse_args()
    parent = args.output.absolute().parent
    st = parent.stat(follow_symlinks=False)
    if (not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid() or stat.S_IMODE(st.st_mode) & 0o022):
        raise ValueError("owned non-writable source parent required")
    result = capture(parent / args.output.name, args.settled_at)
    print(canonical({k: v for k, v in result.items() if k != "response_hashes"}))
