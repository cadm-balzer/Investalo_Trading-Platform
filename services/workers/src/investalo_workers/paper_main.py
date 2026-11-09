"""Explicit opt-in Paper polling; no broker keys, orders, HTTP listener or retries."""
import argparse
import os
import signal
from threading import Event
from contextlib import nullcontext
from time import monotonic
from uuid import UUID

from investalo_marketdata.paper_feed import BitgetPaperFeed
from investalo_trading import PaperRunner
from .health import mark_healthy
from .paper_store import PaperCommitUnknown, PaperStore
from .paper_worker import PaperWorker
from .settings import WorkerSettings
from .paper_runtime import require_development, singleton, PaperLeaseLost, MAX_SECONDS, MAX_FAILURES


def configured_worker():
    if os.getenv("PAPER_WORKER_ENABLED") != "1":
        raise ValueError("Paper worker disabled")
    tenant = str(UUID(os.environ["PAPER_TENANT_ID"]))
    account = str(UUID(os.environ["PAPER_ACCOUNT_ID"]))
    role = os.environ["PGUSER"]
    if (not role.startswith("investalo_paper_") or role == "investalo_paper_worker"
            or not os.environ.get("PGDATABASE")):
        raise ValueError("Dedicated paper identity required")
    settings = WorkerSettings.from_environment()
    runner = PaperRunner(tenant, account)
    return PaperWorker(runner, PaperStore(runner, settings.connect, role), BitgetPaperFeed())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true")
    mode.add_argument("--cycles", type=int, default=0, help="Bounded development run: 1..100 attempts")
    mode.add_argument("--development-loop", action="store_true", help="Explicit local fixture observation, max24h")
    args = parser.parse_args()
    if not args.once and not args.development_loop and not 1 <= args.cycles <= 100:
        raise SystemExit("Bounded development run required; continuous operational acceptance pending")
    stopped = Event()
    signal.signal(signal.SIGTERM, lambda *_: stopped.set())
    signal.signal(signal.SIGINT, lambda *_: stopped.set())
    try:
        if args.development_loop:
            require_development()
        worker = configured_worker()
    except Exception:
        raise SystemExit("Paper worker configuration rejected") from None
    attempted = succeeded = failures = 0
    started = monotonic()
    try:
        context = singleton(worker) if args.development_loop else nullcontext(lambda: None)
        with context as heartbeat:
            while not stopped.is_set():
                if args.development_loop and monotonic()-started >= MAX_SECONDS:
                    break
                heartbeat()  # Lock/connection loss is terminal, outside cycle retry handling.
                attempted += 1
                try:
                    result = worker.run_once(guard=heartbeat)
                    heartbeat()
                    mark_healthy()
                    succeeded += 1
                    failures = 0
                    print(f"Paper cycle committed revision={result.revision} updates={result.updates} fills={result.fills}",
                          flush=True)
                except PaperCommitUnknown:
                    # A supervisor/operator must start a fresh process for readback.
                    raise SystemExit("Paper commit unknown; restart/readback required") from None
                except PaperLeaseLost:
                    raise SystemExit("Paper development session rejected; sensitive details suppressed") from None
                except Exception:
                    failures += 1
                    if args.once or args.development_loop and failures >= MAX_FAILURES:
                        raise SystemExit("Paper cycle rejected; no diagnostic secrets emitted") from None
                    print("Paper cycle unavailable; next cycle reads state and fetches fresh inputs", flush=True)
                if args.once or args.cycles and attempted >= args.cycles:
                    break
                stopped.wait(5)
    except Exception:
        raise SystemExit("Paper development session rejected; sensitive details suppressed") from None
    if args.cycles and not succeeded:
        raise SystemExit("No Paper cycle committed")


if __name__ == "__main__":
    main()
