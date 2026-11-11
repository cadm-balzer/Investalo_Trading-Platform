#!/usr/bin/env python3
"""Complete synthetic three-year journal/restart acceptance; never a net backtest."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "packages/trading/src"), str(ROOT / "tests/trading")]

from investalo_trading.futures_ledger import LedgerMark, start_futures_ledger
from investalo_trading.futures_replay_journal import FuturesReplayJournal
from investalo_trading.futures_signals import FIRST_FILL_MODEL, H4Frame, ReplayProfile
from investalo_trading.models import Candle
from investalo_trading.snapshot import digest
from test_futures_ledger import fixture

D = Decimal


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: check_futures_long_journal.py NEW_OUTPUT_DIRECTORY")
    output = Path(sys.argv[1]).resolve()
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    start = datetime(2022, 8, 1, tzinfo=timezone.utc)
    end = datetime(2025, 8, 1, tzinfo=timezone.utc)
    bars = (end - start) // timedelta(hours=4)
    specification = {
        "schema_version": "futures-long-journal-acceptance/1", "kind": "synthetic-mechanics-only",
        "start": start.isoformat(), "end_exclusive": end.isoformat(), "bars": bars,
        "symbols": fixture().plan.symbols, "price_model": "all-symbols-alternate-100-101",
        "orders": "none", "fees_and_funding_performance": "not-evaluated",
        "historical_market_data_used": False, "performance_evaluated": False, "execution_enabled": False,
    }
    protocol = digest(specification)
    plan = fixture().plan
    ledger = start_futures_ledger(plan, tuple(LedgerMark(s, D(100)) for s in plan.symbols),
                                 start, "synthetic-midnight")
    profile = ReplayProfile(plan, tuple((s, D(2420)) for s in plan.symbols), D(0),
                            "synthetic-three-year-mechanics", FIRST_FILL_MODEL)
    path = output / "journal.jsonl"
    begun = time.monotonic()
    first_event = None
    with FuturesReplayJournal.create(path, profile, ledger, protocol_digest=protocol,
                                    dataset_digests=(digest(("synthetic-price-model", specification)),)) as journal:
        for i in range(bars):
            opened, closed = start + timedelta(hours=4 * i), start + timedelta(hours=4 * (i + 1))
            price = D(100 + i % 2)
            def candles(kind):
                return tuple(Candle(f"{s}:USDT-M:{kind}", opened, closed, price,
                                    price + 1, price - 1, price) for s in plan.symbols)
            frame = H4Frame(candles("trade"), candles("mark"))
            first_event = first_event or "mark-" + frame.frame_digest
            journal.append("frame", expected_revision=journal.state.revision, at=closed, frame=frame)
            if (i + 1) % 1000 == 0:
                print(f"synthetic frames committed: {i + 1}/{bars}", flush=True)
        before = journal.receipt
        evidence_count = len(journal.state.economic.event_ids)
    written_seconds = time.monotonic() - begun
    restored_at = time.monotonic()
    with FuturesReplayJournal.restore(
        path, profile_digest=profile.profile_digest, protocol_digest=protocol,
        dataset_digests=(digest(("synthetic-price-model", specification)),),
        minimum_receipt=before,
    ) as journal:
        assert journal.receipt == before
        assert first_event in journal.state.economic.event_ids
        assert journal.state.revision == bars
        assert journal.state.economic.pending is None
        assert len(journal.state.economic.fill_ids) == 0
        assert all(s.indicator.rsi is not None for s in journal.state.signals)
        restored = journal.receipt
    receipt = {**specification, "journal_receipt": restored, "event_identities_retained": evidence_count,
               "first_event_retained_after_restore": True, "same_receipt_after_full_restore": True,
               "minimum_acknowledged_anchor_checked": True,
               "file_bytes": path.stat().st_size, "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
               "write_seconds": round(written_seconds, 3),
               "full_restore_seconds": round(time.monotonic() - restored_at, 3)}
    with (output / "receipt.json").open("x") as handle:
        handle.write(json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n")
    print(f"synthetic acceptance: {bars} frames, {evidence_count} retained event IDs, exact restart", flush=True)


if __name__ == "__main__":
    main()
