#!/usr/bin/env python3
"""Create-only read-only current Classic source acceptance; never a trading launcher."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import os
from pathlib import Path
import stat
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "packages/marketdata/src"), str(ROOT / "packages/trading/src")]

from investalo_marketdata.futures_paper_feed import (
    BitgetFuturesMarketSource, FuturesMarketObservation, SYMBOLS, fetch_paper_source_json,
    hour_boundary,
)
from investalo_marketdata.snapshot import canonical, decode_json
from investalo_trading.snapshot import _decode


def write_new(path, value):
    raw = canonical(value).encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    actual = path.stat(follow_symlinks=False)
    if (not stat.S_ISREG(actual.st_mode) or actual.st_uid != os.getuid()
            or stat.S_IMODE(actual.st_mode) != 0o600 or path.read_bytes() != raw):
        raise ValueError("owned source readback mismatch")
    return hashlib.sha256(raw).hexdigest()


def capture(output):
    # Receipt is last, after verification. Unknown writes require readback.
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    parent_fd = os.open(output.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)
    now = datetime.now(timezone.utc)
    end = hour_boundary(now)
    start = (end - timedelta(days=2)).replace(hour=0)
    paths = []

    def fetch(url):
        payload = fetch_paper_source_json(url)
        path = output / f"response-{len(paths) + 1:02}.json"
        digest = write_new(path, payload)
        paths.append((url, path, digest))
        return payload

    observation = BitgetFuturesMarketSource(fetch).collect(start=start, end=end, funding_start=start)
    if len(paths) != 25 or len(observation.reads) != 25:
        raise ValueError("complete native cohort required")
    for (url, path, digest), read in zip(paths, observation.reads, strict=True):
        if (url != read.url or digest != read.response_digest
                or hashlib.sha256(path.read_bytes()).hexdigest() != digest):
            raise ValueError("native response evidence hash mismatch")
    data_digest = write_new(output / "observation.json", observation.record())
    restored = _decode(FuturesMarketObservation,
                       decode_json((output / "observation.json").read_bytes())["observation"])
    if restored != observation or restored.data_digest != data_digest:
        raise ValueError("native observation roundtrip mismatch")
    receipt = {
        "schema_version": "bitget-classic-futures-paper-source-capture/1",
        "data_digest": data_digest, "start": start.isoformat(), "end": end.isoformat(),
        "collected_at": observation.collected_at.isoformat(), "symbols": list(SYMBOLS),
        "closed_hours_per_axis": len(observation.hours), "native_quotes": len(observation.quotes),
        "native_funding": len(observation.funding), "native_forecasts": len(observation.forecasts),
        "response_hashes": [{"file": p.name, "sha256": d} for _, p, d in paths],
        "settlement_mark_available": False, "paper_worker_enabled": False,
        "market_performance_computed": False, "execution_enabled": False,
    }
    receipt_digest = write_new(output / "receipt.json", receipt)
    fd = os.open(output, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return {"directory": str(output), "receipt_sha256": receipt_digest, **{
        k: receipt[k] for k in ("data_digest", "closed_hours_per_axis", "native_quotes", "native_funding",
                                "native_forecasts", "execution_enabled", "paper_worker_enabled")}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="new directory below an existing owned source parent")
    args = parser.parse_args()
    parent = args.output.absolute().parent
    st = parent.stat(follow_symlinks=False)
    if (not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid()
            or stat.S_IMODE(st.st_mode) & 0o022):
        raise ValueError("owned non-writable source parent required")
    print(canonical(capture(parent / args.output.name)))
