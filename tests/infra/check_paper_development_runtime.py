"""Run inside the restricted Paper container; actual TLS/LOGIN/session checks."""
from dataclasses import replace
import psycopg

from investalo_workers.paper_main import configured_worker
from investalo_workers.paper_runtime import (
    PaperLeaseLost, require_development, singleton,
)
from investalo_workers.settings import WorkerSettings


def main():
    require_development()
    worker = configured_worker()
    with singleton(worker) as heartbeat:
        heartbeat()
        try:
            with singleton(worker):
                raise AssertionError("Duplicate instance accepted")
        except ValueError:
            pass
        heartbeat()
    with singleton(worker) as heartbeat:
        heartbeat()  # Previous session released its lock.
    captured = []

    def connect():
        db = worker.store.connect()
        captured.append(db)
        return db

    losing = replace(worker, store=replace(worker.store, connect=connect))
    with singleton(losing) as heartbeat:
        captured[-1].close()
        try:
            heartbeat()
        except PaperLeaseLost:
            pass
        else:
            raise AssertionError("Lost session accepted")
    with singleton(worker) as heartbeat:
        heartbeat()  # Loss released its lock; no automatic reacquire.
    settings = WorkerSettings.from_environment()
    try:
        with psycopg.connect(**{**settings.parameters, "dbname": "investalo"}):
            raise AssertionError("Normal database accepted")
    except psycopg.OperationalError:
        pass
    # No feed call or write; initialized state, when present, must restore exactly.
    checkpoint = worker.store.read()
    if checkpoint is not None:
        assert worker.runner.restore(worker.runner.dump(checkpoint)) == checkpoint
    print("PASS: actual restricted TLS identity, duplicate refusal, release, session loss,"
          " normal-DB denial and persisted readback")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("Paper development acceptance rejected; sensitive output suppressed") from None
