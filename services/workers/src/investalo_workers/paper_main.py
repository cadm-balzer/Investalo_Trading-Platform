"""Explicit opt-in Paper polling; no broker keys, orders, HTTP listener or retries."""
import argparse
import os
import signal
from threading import Event
from uuid import UUID

from investalo_marketdata.paper_feed import BitgetPaperFeed
from investalo_trading import PaperRunner
from .health import mark_healthy
from .paper_store import PaperCommitUnknown, PaperStore
from .paper_worker import PaperWorker
from .settings import WorkerSettings


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
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--cycles", type=int, default=0, help="Bounded development run: 1..100 attempts")
    args = parser.parse_args()
    if not args.once and not 1 <= args.cycles <= 100:
        raise SystemExit("Bounded development run required; continuous operational acceptance pending")
    stopped = Event()
    signal.signal(signal.SIGTERM, lambda *_: stopped.set())
    signal.signal(signal.SIGINT, lambda *_: stopped.set())
    try:
        worker = configured_worker()
    except Exception:
        raise SystemExit("Paper worker configuration rejected") from None
    attempted = succeeded = 0
    while not stopped.is_set():
        attempted += 1
        try:
            result = worker.run_once()
            mark_healthy()
            succeeded += 1
            print(f"Paper cycle committed revision={result.revision} updates={result.updates} fills={result.fills}",
                  flush=True)
        except PaperCommitUnknown:
            # A supervisor/operator must start a fresh process for readback.
            raise SystemExit("Paper commit unknown; restart/readback required") from None
        except Exception:
            if args.once:
                raise SystemExit("Paper cycle rejected; no diagnostic secrets emitted") from None
            print("Paper cycle unavailable; next cycle reads state and fetches fresh inputs", flush=True)
        if args.once or args.cycles and attempted >= args.cycles:
            break
        stopped.wait(5)
    if args.cycles and not succeeded:
        raise SystemExit("No Paper cycle committed")


if __name__ == "__main__":
    main()
