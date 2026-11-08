#!/usr/bin/env python3
"""Validate/stage an immutable snapshot for the isolated migration import tool."""
import argparse
import json
import os
from pathlib import Path
import re
import sys
import subprocess
from uuid import UUID

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "packages/marketdata/src"), str(ROOT / "packages/trading/src")]
from investalo_marketdata import MAX_BYTES, dump_snapshot, load_snapshot


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--import-local", action="store_true",
                        help="Import into the already bound local research tenant.")
    parser.add_argument("--purpose", choices=("research", "test", "holdout"), default="research",
                        help="holdout is operator-only; API and worker cannot evaluate it.")
    args = parser.parse_args()
    if os.geteuid() != 0 or not (ROOT / "infra/local/READY").exists():
        raise ValueError("Requires initialized local material and root.")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,80}\.json", args.name):
        raise ValueError("Invalid import filename.")
    with args.file.open("rb") as stream:
        payload = stream.read(MAX_BYTES + 1)
    if len(payload) > MAX_BYTES:
        raise ValueError("Snapshot exceeds resource bound.")
    snapshot = load_snapshot(payload)
    canonical = (dump_snapshot(snapshot) + "\n").encode()
    directory = ROOT / "infra/local/research-data"
    if directory.is_symlink():
        raise ValueError("Unexpected import directory.")
    directory.mkdir(mode=0o700, exist_ok=True)
    os.chown(directory, 10003, 10003)
    os.chmod(directory, 0o700)
    target = directory / args.name
    if target.is_symlink():
        raise ValueError("Unexpected import target.")
    if target.exists():
        if target.read_bytes() != canonical:
            raise ValueError("Existing snapshot differs; no overwrite permitted.")
    else:
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o400)
        with os.fdopen(fd, "wb") as stream:
            stream.write(canonical)
        os.chown(target, 10003, 10003)
    if args.import_local:
        binding = json.loads((ROOT / "infra/local/research-binding.json").read_text())
        if binding.get("database_role") != "investalo_research_local":
            raise ValueError("Unexpected local research binding.")
        tenant_id = str(UUID(binding["tenant_id"]))
        result = subprocess.run(
            ["bash", str(ROOT / "infra/scripts/compose.sh"), "--profile", "tools",
             "run", "--rm", "migrate", "python", "-m", "investalo_api.import_dataset",
             "--tenant-id", tenant_id, "--purpose", args.purpose,
             "--file", "/app/import-data/" + args.name],
            capture_output=True, text=True,
        )
        if result.returncode:
            raise ValueError("Local snapshot import refused.")
        print("Immutable research snapshot imported into the bound local tenant.")
    else:
        print("Validated immutable research snapshot staged for read-only import.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, TypeError):
        print("Snapshot staging refused or failed; no input contents emitted.", file=sys.stderr)
        sys.exit(1)
