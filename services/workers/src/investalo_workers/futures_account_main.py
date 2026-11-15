"""Bounded own-account Paper run with explicit allocation and readonly RLS reads."""
import argparse
import os
from pathlib import Path
import signal
from threading import Event
from datetime import datetime, timezone

from investalo_marketdata.futures_paper_archive import FuturesPaperArchive
from investalo_marketdata.futures_paper_universe import native_symbols
from investalo_trading.futures_paper_journal import FuturesPaperJournal
from investalo_trading.futures_paper_status import FuturesAssetPublisher, FuturesAssetReader
from .futures_account_reader import FuturesPaperAccountReader
from .futures_account_worker import FuturesAccountWorker
from .futures_paper_bootstrap import initialize_paper, load_spec
from .futures_paper_main import _running
from .futures_source_worker import FuturesSourceWorker
from .futures_capacity_source import FuturesPaperCapacitySource
from .futures_recovery_executor import register_recovery


def _cycle(args, spec, reader, archive, clock, guard, recovery_enabled):
    """Hold the sole writer through one complete source/commit/publication cycle."""
    published = FuturesAssetReader(args.status_root).publication(
        spec.binding.tenant_id, spec.binding.account_id)
    minimum = published.journal_receipt if published is not None else None
    try:
        journal = FuturesPaperJournal.restore(args.journal, config_digest=spec.config.config_digest,
                                             minimum_receipt=minimum)
    except BlockingIOError:
        return None  # Acquisition only; no source capture, command or retry.
    with journal:
        guard()
        reader()
        capacity_reader = (FuturesPaperCapacitySource(journal, archive, clock)
            if os.getenv("FUTURES_PAPER_CAPACITY_ENABLED") == "1" else None)
        try:
            publisher = FuturesAssetPublisher(args.status_root, journal, clock=clock,
                capacity_reader=capacity_reader, recovery_enabled=recovery_enabled)
        except BlockingIOError:
            return None
        with publisher:
            publisher.publish(expected_revision=journal.state.revision)
            worker = FuturesAccountWorker(FuturesSourceWorker(journal, archive, publisher, clock), reader)
            return worker.run_once(guard=guard)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("journal", "spec", "archive-root", "status-root"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--spec-digest", required=True)
    parser.add_argument("--initialize", action="store_true")
    parser.add_argument("--recovery-root", type=Path)
    parser.add_argument("--cycles", type=int, default=1)
    parser.add_argument("--interval", type=int, default=15)
    args = parser.parse_args(argv)
    if os.getenv("FUTURES_PAPER_ACCOUNT_WORKER_ENABLED") != "1":
        raise SystemExit("Bound own-account Paper worker disabled")
    if not 1 <= args.cycles <= 100 or not 5 <= args.interval <= 300:
        raise SystemExit("bounded own-account Paper run required")
    stopped = Event()
    signal.signal(signal.SIGTERM, lambda *_: stopped.set())
    signal.signal(signal.SIGINT, lambda *_: stopped.set())
    clock = lambda: datetime.now(timezone.utc)
    guard = lambda: _running(stopped)
    try:
        from investalo_api.settings import Settings
        spec = load_spec(args.spec, args.spec_digest)
        recovery_enabled = os.getenv("FUTURES_PAPER_RECOVERY_ENABLED") == "1"
        if args.recovery_root is not None:
            if not recovery_enabled:
                raise ValueError("own recovery registration disabled")
            register_recovery(args.recovery_root, args.spec, args.spec_digest, args.journal)
        reader = FuturesPaperAccountReader(spec.binding, Settings.from_environment().connection_parameters(), clock)
        archive = FuturesPaperArchive(args.archive_root, clock=clock,
                                      symbols=native_symbols(spec.config.profile.plan.symbols))
        if args.initialize:
            initialize_paper(args.journal, spec, archive, args.status_root, reader, clock, guard=guard)
        for i in range(args.cycles):
            guard()
            result = _cycle(args, spec, reader, archive, clock, guard, recovery_enabled)
            if result is None:
                print("Futures Paper outcome=writer_busy; no source or command processed", flush=True)
            else:
                print(f"Futures Paper outcome={result.outcome} revision={result.revision} "
                      f"entries={result.entries} closures={result.closures}", flush=True)
                if result.outcome == "liquidation_reconciliation_required":
                    break
            # Both lifetime locks are closed before waiting. Next cycle restores
            # the latest published minimum receipt, including manual API actions.
            if i + 1 < args.cycles:
                stopped.wait(args.interval)
    except Exception as error:
        raise SystemExit(f"Bound Paper stopped ({type(error).__name__}); readback/reconciliation required") from None


if __name__ == "__main__":
    main()
