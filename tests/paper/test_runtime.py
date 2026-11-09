from contextlib import contextmanager
from unittest.mock import Mock

import pytest

from investalo_workers import paper_main, paper_runtime
from investalo_workers.paper_store import PaperCommitUnknown

ENV = {
    "PAPER_DEVELOPMENT_MODE": "1", "PAPER_WORKER_ENABLED": "1", "PGHOST": "postgres",
    "PGPORT": "5432", "PGDATABASE": paper_runtime.DATABASE, "PGUSER": paper_runtime.ROLE,
    "PGSSLMODE": "verify-full", "PGSSLROOTCERT": "/run/secrets/local_ca_cert",
    "PGPASSWORD_FILE": "/run/secrets/paper_development_password",
}


def environment(monkeypatch):
    import os
    for key in list(os.environ):
        if key.startswith("PG"):
            monkeypatch.delenv(key)
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)


def test_development_environment_requires_exact_fixture_identity(monkeypatch):
    environment(monkeypatch)
    paper_runtime.require_development()


@pytest.mark.parametrize("key,value", [
    ("PAPER_DEVELOPMENT_MODE", "0"), ("PGDATABASE", "investalo"), ("PGUSER", "investalo_paper_tests"),
    ("PGHOST", "attacker.invalid"), ("PGSSLMODE", "require"), ("PGPASSWORD", "unsafe"),
    ("PGSERVICE", "unsafe"), ("PGOPTIONS", "-c role=investalo_admin"), ("PGHOSTADDR", "127.0.0.1"),
])
def test_development_rejects_ambient_overrides(monkeypatch, key, value):
    environment(monkeypatch)
    monkeypatch.setenv(key, value)
    with pytest.raises(ValueError):
        paper_runtime.require_development()


class Database:
    autocommit = False
    def __init__(self, acquired=True):
        self.acquired, self.held, self.closed = acquired, True, False
    def execute(self, query, params=None):
        if "FROM pg_roles" in query:
            value = dict(database=paper_runtime.DATABASE, current=paper_runtime.ROLE,
                         session=paper_runtime.ROLE, rolsuper=False, rolbypassrls=False,
                         rolcreaterole=False, rolcreatedb=False, rolreplication=False)
        elif "pg_try_advisory_lock" in query:
            value = {"acquired": self.acquired}
        else:
            value = {"held": self.held}
        return Mock(fetchone=lambda: value)
    def close(self):
        self.closed = True


def worker(db=None):
    result = Mock()
    result.runner.tenant_id, result.runner.account_id = "tenant", "account"
    result.store.connect = Mock(return_value=db or Database())
    return result


def test_singleton_duplicate_refused_and_connection_closed():
    db = Database(acquired=False)
    with pytest.raises(ValueError, match="already active"):
        with paper_runtime.singleton(worker(db)):
            pytest.fail()
    assert db.closed


def test_singleton_loss_never_reacquires_and_cleanup_closes_session():
    db = Database()
    w = worker(db)
    with paper_runtime.singleton(w) as heartbeat:
        heartbeat()
        db.held = False
        with pytest.raises(paper_runtime.PaperLeaseLost, match="lock lost"):
            heartbeat()
    assert db.closed and w.store.connect.call_count == 1


class Stop:
    def is_set(self):
        return False
    def wait(self, seconds):
        assert seconds == 5


def cli(monkeypatch, fake, *, heartbeat=lambda: None):
    environment(monkeypatch)
    monkeypatch.setattr("sys.argv", ["paper", "--development-loop"])
    monkeypatch.setattr(paper_main, "configured_worker", lambda: fake)
    monkeypatch.setattr(paper_main, "Event", Stop)
    monkeypatch.setattr(paper_main, "mark_healthy", Mock())
    monkeypatch.setattr(paper_main, "monotonic", lambda: 0)
    @contextmanager
    def lease(_):
        yield heartbeat
    monkeypatch.setattr(paper_main, "singleton", lease)


def test_loop_six_consecutive_failures_stop_without_secret_trace(monkeypatch):
    fake = worker()
    fake.run_once.side_effect = ValueError("private")
    cli(monkeypatch, fake)
    with pytest.raises(SystemExit, match="cycle rejected") as error:
        paper_main.main()
    assert "private" not in str(error.value)
    assert fake.run_once.call_count == paper_runtime.MAX_FAILURES


def test_success_resets_consecutive_failure_count_and_duration_budget_exits(monkeypatch):
    fake = worker()
    fake.run_once.side_effect = [ValueError("private")]*5+[Mock(revision=1, updates=2, fills=0)]+[ValueError("private")]*5
    cli(monkeypatch, fake)
    ticks = iter([0]+[0]*11+[paper_runtime.MAX_SECONDS])
    monkeypatch.setattr(paper_main, "monotonic", lambda: next(ticks))
    paper_main.main()
    assert fake.run_once.call_count == 11
    assert paper_main.mark_healthy.call_count == 1


def test_loop_unknown_commit_is_terminal_without_retry(monkeypatch):
    fake = worker()
    fake.run_once.side_effect = PaperCommitUnknown("private")
    cli(monkeypatch, fake)
    with pytest.raises(SystemExit, match="restart/readback required"):
        paper_main.main()
    assert fake.run_once.call_count == 1


def test_loop_lock_loss_stops_before_cycle(monkeypatch):
    fake = worker()
    cli(monkeypatch, fake, heartbeat=Mock(side_effect=ValueError("private")))
    with pytest.raises(SystemExit, match="session rejected") as error:
        paper_main.main()
    fake.run_once.assert_not_called()
    assert "private" not in str(error.value)


def test_loop_midcycle_lock_loss_is_terminal_before_health(monkeypatch):
    fake = worker()
    fake.run_once.side_effect = paper_runtime.PaperLeaseLost("private")
    cli(monkeypatch, fake)
    with pytest.raises(SystemExit, match="session rejected"):
        paper_main.main()
    assert fake.run_once.call_count == 1
    paper_main.mark_healthy.assert_not_called()
