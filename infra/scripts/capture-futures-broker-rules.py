#!/usr/bin/env python3
"""Capture current public Classic contract metadata; no account/broker actions."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / name) for name in ("packages/trading/src", "packages/marketdata/src")]

from investalo_marketdata.futures_broker_calibration import capture_contracts


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: capture-futures-broker-rules.py NEW_OUTPUT_DIRECTORY (create-only)")
    try:
        receipt = capture_contracts(Path(sys.argv[1]).resolve())
    except (OSError, ValueError):
        raise SystemExit("capture failed; preserve output and inspect before a new run") from None
    print(f"{receipt['get_count']} unsigned GET; five current Classic contracts saved.")
