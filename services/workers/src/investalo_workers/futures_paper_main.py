"""Explicit bounded local Futures Paper run; no keys, broker orders or new wallet."""
import argparse
import os
from pathlib import Path
import signal
from threading import Event
from uuid import UUID

from investalo_marketdata.futures_paper_archive import FuturesPaperArchive
from investalo_marketdata.futures_paper_universe import native_symbols
from investalo_trading.futures_paper_journal import FuturesPaperJournal
from investalo_trading.futures_paper_status import FuturesAssetPublisher, FuturesAssetReader
from investalo_trading.futures_replay_journal import _sha
from .futures_source_worker import FuturesSourceWorker


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--journal", type=Path, required=True)
    parser.add_argument("--config-digest", required=True)
    parser.add_argument("--archive-root", type=Path, required=True)
    parser.add_argument("--status-root", type=Path, required=True)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--cycles", type=int, default=1, help="bounded 1..100 cycles, default1")
    parser.add_argument("--interval", type=int, default=15, help="5..300 seconds, default15")
    args = parser.parse_args(argv)
    if os.getenv("FUTURES_PAPER_WORKER_ENABLED") != "1":
        raise SystemExit("Futures Paper worker disabled")
    if not 1 <= args.cycles <= 100 or not 5 <= args.interval <= 300:
        raise SystemExit("bounded local Futures Paper run required")
    stopped = Event()
    signal.signal(signal.SIGTERM, lambda *_: stopped.set())
    signal.signal(signal.SIGINT, lambda *_: stopped.set())
    try:
        tenant, account = str(UUID(args.tenant_id)), str(UUID(args.account_id))
        _sha(args.config_digest)
        reader = FuturesAssetReader(args.status_root)
        published = reader.publication(tenant, account)
        minimum = published.journal_receipt if published is not None else None
        with FuturesPaperJournal.restore(args.journal, config_digest=args.config_digest,
                                         minimum_receipt=minimum) as journal:
            plan = journal.state.config.profile.plan
            if (plan.tenant_id, plan.account_id) != (tenant, account):
                raise ValueError("foreign configured own Paper account")
            with FuturesAssetPublisher(args.status_root, journal) as publisher:
                publisher.publish(expected_revision=journal.state.revision)
                worker = FuturesSourceWorker(journal, FuturesPaperArchive(
                    args.archive_root, symbols=native_symbols(plan.symbols)), publisher)
                for i in range(args.cycles):
                    if stopped.is_set():
                        break
                    cycle = worker.run_once(guard=lambda: _running(stopped))
                    print(f"Futures Paper outcome={cycle.outcome} revision={cycle.revision} "
                          f"entries={cycle.entries} closures={cycle.closures}", flush=True)
                    if cycle.outcome == "liquidation_reconciliation_required":
                        break
                    if i + 1 < args.cycles:
                        stopped.wait(args.interval)
    except Exception as error:
        # No private paths, IDs, native payloads or secrets in logs; no retries.
        raise SystemExit(f"Futures Paper stopped ({type(error).__name__}); readback/reconciliation required") from None


def _running(stopped):
    if stopped.is_set():
        raise RuntimeError("Futures Paper stopping")


if __name__ == "__main__":
    main()
