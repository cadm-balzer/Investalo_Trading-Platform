#!/usr/bin/env python3
"""Native unsigned source/restore acceptance in a new private synthetic Paper folder."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import os
from pathlib import Path
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / p) for p in (
    "packages/marketdata/src", "packages/trading/src", "services/workers/src")]

from investalo_marketdata.futures_broker_calibration import fetch_contracts, parse_contracts
from investalo_marketdata.futures_paper_archive import FuturesPaperArchive, _write
from investalo_marketdata.futures_paper_feed import hour_boundary
from investalo_marketdata.futures_paper_universe import SEVEN_SYMBOLS
from investalo_marketdata.snapshot import canonical, decode_json
from investalo_trading.futures_ledger import LedgerMark
from investalo_trading.futures_paper_account import PaperAccountBinding
from investalo_trading.futures_paper_journal import FuturesPaperJournal
from investalo_trading.futures_paper_status import FuturesAssetPublisher, FuturesAssetReader, _directory
from investalo_workers.futures_capacity_source import FuturesPaperCapacitySource
from investalo_workers.futures_local_profile import local_seven_profit_config
from investalo_workers.futures_paper_bootstrap import PaperBootstrapSpec, save_spec
from investalo_workers.futures_source_worker import FuturesSourceWorker


def check(output):
    """No existing account, DB, service, native performance job or broker execution."""
    output = Path(output)
    parent = _directory(output.absolute().parent)
    try:
        output.mkdir(mode=0o700, exist_ok=False)
        os.fsync(parent)
    finally:
        os.close(parent)
    fd = _directory(output)
    try:
        raw = fetch_contracts()
        contracts_sha = _write(fd, "contracts.json", decode_json(raw), 2 * 1024 * 1024)
        rules = parse_contracts((output / "contracts.json").read_bytes(), symbols=SEVEN_SYMBOLS)
        now = datetime.now(timezone.utc)
        end = hour_boundary(now)
        start = (end - timedelta(hours=16)).replace(hour=0)
        for name in ("archive", "status"):
            (output / name).mkdir(mode=0o700)
        archive = FuturesPaperArchive(output / "archive", symbols=SEVEN_SYMBOLS)
        ref, warm = archive.market(start=start, end=end, funding_start=start)
        # Evidence at a genuine common native funding time; no invented rate or shifted time.
        common = set.intersection(*(
            {f.settled_at for f in warm.funding if f.symbol == "BITGET:" + symbol}
            for symbol in SEVEN_SYMBOLS))
        eligible = [at for at in common if at + timedelta(minutes=1) <= now]
        if not eligible:
            raise ValueError("no common native closed funding minute in current evidence")
        minute_ref, minute = archive.minute(max(eligible))
        tenant, account, actor = (str(uuid4()) for _ in range(3))
        config = local_seven_profit_config(tenant, account, rules, contracts_sha, end)
        spec = PaperBootstrapSpec(PaperAccountBinding(
            tenant, account, actor, "https://seven-acceptance.invalid",
            "synthetic-native-source-acceptance", 0, now), config)
        save_spec(output / "allocation.json", spec)
        plan = config.profile.plan
        trade = tuple(LedgerMark(s, c.open) for s, c in zip(plan.symbols, warm.hours[0].trade, strict=True))
        mark = tuple(LedgerMark(s, c.open) for s, c in zip(plan.symbols, warm.hours[0].mark, strict=True))
        with FuturesPaperJournal.create(output / "paper.jsonl", config, trade, mark, start,
                                        spec.spec_digest) as journal:
            journal.append("source_warmup", hours=warm.hours, source=ref,
                           expected_revision=0, at=datetime.now(timezone.utc))
            with FuturesAssetPublisher(output / "status", journal,
                    capacity_reader=FuturesPaperCapacitySource(journal, archive)) as publisher:
                result = FuturesSourceWorker(journal, archive, publisher).run_once()
                actual, receipt, cursor = journal.source_checkpoint()
                published = FuturesAssetReader(output / "status").publication(tenant, account)
                capacity = published.capacity
                if (len(published.state.assets) != 7 or capacity.evidence is None
                        or capacity.evidence.funded_capacity != 3
                        or actual.config.profile.plan.funded_slots != 3
                        or result.execution_enabled or len(archive.load(cursor.market).quotes) != 7):
                    raise ValueError("native own source/publication/capacity acceptance failed")
        with FuturesPaperJournal.restore(output / "paper.jsonl", config_digest=config.config_digest,
                                          minimum_receipt=receipt) as restored:
            if restored.state != actual or restored.source_checkpoint()[2] != cursor:
                raise ValueError("full native source/journal restore mismatch")
            if archive.load(ref) != warm or archive.load(minute_ref) != minute:
                raise ValueError("native original response replay mismatch")
        value = {
            "schema_version": "futures-seven-candidate-acceptance/1",
            "symbols": list(SEVEN_SYMBOLS), "synthetic_account": True,
            "allocation_digest": spec.spec_digest, "config_digest": config.config_digest,
            "contracts_sha256": contracts_sha, "native_contracts": [r.record() for r in rules],
            "warmup": {"data_digest": ref.data_digest, "receipt_digest": ref.receipt_digest,
                       "closed_hours": len(warm.hours), "native_reads": len(warm.reads)},
            "minute": {"data_digest": minute_ref.data_digest,
                       "receipt_digest": minute_ref.receipt_digest,
                       "settled_at": minute.settled_at.isoformat(), "native_reads": len(minute.reads)},
            "journal_receipt": receipt, "full_restore_verified": True,
            "outcome": result.outcome, "entries": result.entries, "closures": result.closures,
            "funded_slots": 3, "configured_limit": 7,
            "eligible_assets": capacity.evidence.eligible_assets,
            "asset_count": len(published.state.assets),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "market_performance_computed": False, "execution_enabled": False,
            "running_service_changed": False,
        }
        sha = _write(fd, "receipt.json", value, 256 * 1024)
        os.fsync(fd)
        return {"directory": str(output), "receipt_sha256": sha, "asset_count": 7,
                "funded_slots": 3, "entries": result.entries, "closures": result.closures,
                "execution_enabled": False}
    finally:
        os.close(fd)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="new folder under an existing owned private parent")
    args = parser.parse_args()
    print(canonical(check(args.output.absolute())))
