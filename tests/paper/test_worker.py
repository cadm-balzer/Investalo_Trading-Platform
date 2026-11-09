from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import Mock

import pytest

from investalo_marketdata.paper_feed import H4, SYMBOLS, boundary
from investalo_trading import Candle, EntryStage, PaperRunner, Quote
from investalo_workers.paper_store import PaperCommitUnknown
from investalo_workers.paper_worker import PaperWorker, WARMUP_BARS
from investalo_workers import paper_main

NOW = datetime(2026, 1, 9, 12, 0, 10, tzinfo=timezone.utc)
D = Decimal


class MemoryStore:
    def __init__(self):
        self.value = None
        self.entries = []

    def read(self):
        return self.value

    def initialize(self, value):
        assert self.value is None
        self.value = value
        return value

    def commit(self, previous, update):
        assert previous == self.value
        self.value = update.checkpoint
        if update.entry:
            self.entries.append(update.entry)
        return self.value


class Feed:
    def __init__(self, now=NOW):
        self.now = now
        self.calls = []

    def quote(self, symbol):
        return Quote(symbol, self.now-timedelta(seconds=1), D(100), D(101))

    def closed_bars(self, symbol, *, start, end, now):
        self.calls.append(symbol)
        return tuple(Candle(symbol, opened, opened+H4, D(100), D(101), D(99), D(100))
                     for opened in (start+index*H4 for index in range(int((end-start)//H4))))


def setup():
    runner = PaperRunner("tenant", "account")
    store, feed = MemoryStore(), Feed()
    worker = PaperWorker(runner, store, feed, lambda: feed.now)
    return worker, store, feed


def test_warmup_uses_closed_bars_both_assets_without_historical_fills_and_restart_idempotent():
    worker, store, feed = setup()
    first = worker.run_once()
    assert first.updates == 2+2*WARMUP_BARS and first.fills == 0
    assert not store.value.state.processed_fills
    assert feed.calls == list(SYMBOLS)
    assert all(b.last_bar_open == boundary(NOW)-H4 for b in store.value.state.baskets)
    restarted = PaperWorker(worker.runner, store, feed, worker.clock)
    second = restarted.run_once()
    assert second.updates == second.fills == 0
    assert len(store.entries) == first.updates


def test_next_boundary_advances_exactly_one_closed_bar_per_asset():
    worker, store, feed = setup()
    worker.run_once()
    feed.now += H4
    result = worker.run_once()
    assert result.updates == 4
    assert len(store.value.state.processed_bars) == 2*(WARMUP_BARS+1)


def test_authority_is_checked_before_public_network_io():
    runner, store, feed = PaperRunner("tenant", "account"), Mock(), Mock()
    store.read.side_effect = ValueError("disabled")
    with pytest.raises(ValueError):
        PaperWorker(runner, store, feed, lambda: NOW).run_once()
    feed.closed_bars.assert_not_called()
    feed.quote.assert_not_called()


def test_invalid_second_asset_leaves_initial_state_and_journal_unwritten():
    worker, store, feed = setup()
    original = feed.closed_bars
    feed.closed_bars = lambda symbol, **kwargs: (
        original(symbol, **kwargs) if symbol == SYMBOLS[0] else ())
    with pytest.raises((ValueError, IndexError)):
        worker.run_once()
    assert store.value is None and not store.entries


def test_stale_quote_leaves_no_partial_batch_commits():
    worker, store, feed = setup()
    feed.quote = lambda symbol: Quote(symbol, NOW-timedelta(seconds=31), D(100), D(101))
    with pytest.raises(ValueError):
        worker.run_once()
    assert store.value is None and not store.entries


def test_revised_overlap_does_not_append_or_replace_persisted_state():
    worker, store, feed = setup()
    worker.run_once()
    before = store.value
    original = feed.closed_bars
    feed.closed_bars = lambda *a, **kw: tuple(
        replace(bar, close=D("100.5")) for bar in original(*a, **kw))
    with pytest.raises(ValueError):
        worker.run_once()
    assert store.value == before


def test_unknown_commit_stops_cycle_without_second_write():
    worker, store, feed = setup()
    store.commit = Mock(side_effect=PaperCommitUnknown())
    with pytest.raises(PaperCommitUnknown):
        worker.run_once()
    assert store.commit.call_count == 1


def test_clock_regression_rejects_before_fetch():
    worker, store, feed = setup()
    worker.run_once()
    feed.now -= timedelta(seconds=1)
    feed.calls.clear()
    with pytest.raises(ValueError):
        worker.run_once()
    assert not feed.calls


def test_fetch_crossing_h4_boundary_leaves_batch_unwritten():
    worker, store, feed = setup()
    times = iter((NOW, NOW+H4))
    with pytest.raises(ValueError):
        replace(worker, clock=lambda: next(times)).run_once()
    assert store.value is None


@pytest.mark.parametrize("enabled,role,tls", [
    ("0", "investalo_paper_tests", "verify-full"),
    ("1", "investalo_runtime", "verify-full"),
    ("1", "investalo_migration", "verify-full"),
    ("1", "investalo_research_tests", "verify-full"),
    ("1", "investalo_paper_worker", "verify-full"),
    ("1", "investalo_paper_tests", "require"),
])
def test_startup_requires_explicit_enable_dedicated_identity_and_verified_tls(monkeypatch, enabled, role, tls):
    for key, value in {
        "PAPER_WORKER_ENABLED": enabled, "PGUSER": role, "PGSSLMODE": tls,
        "PAPER_TENANT_ID": "00000000-0000-4000-8000-000000000001",
        "PAPER_ACCOUNT_ID": "00000000-0000-4000-8000-000000000002",
        "PGDATABASE": "investalo_credentials_checks",
    }.items():
        monkeypatch.setenv(key, value)
    with pytest.raises(ValueError):
        paper_main.configured_worker()


def test_cli_unknown_commit_terminates_without_repeating_cycle(monkeypatch):
    worker = Mock()
    worker.run_once.side_effect = PaperCommitUnknown("sensitive detail")
    monkeypatch.setattr(paper_main, "configured_worker", lambda: worker)
    monkeypatch.setattr("sys.argv", ["paper", "--cycles", "3"])
    with pytest.raises(SystemExit, match="restart/readback required") as error:
        paper_main.main()
    assert "sensitive detail" not in str(error.value)
    assert worker.run_once.call_count == 1


def test_cli_continuous_operation_stays_gated_before_operational_acceptance(monkeypatch):
    configure = Mock()
    monkeypatch.setattr(paper_main, "configured_worker", configure)
    monkeypatch.setattr("sys.argv", ["paper"])
    with pytest.raises(SystemExit) as error:
        paper_main.main()
    assert error.value.code == 2
    configure.assert_not_called()


def test_next_utc_day_commits_model_basis_before_quotes_and_keeps_rsi_core():
    worker, store, feed = setup()
    worker.run_once()
    feed.now += timedelta(days=1)
    old = store.value
    count = len(store.entries)
    worker.run_once()
    state = store.value.state
    assert state.account.trading_day == feed.now.date()
    assert state.account.day_start_equity == old.state.account.cash
    assert store.entries[count].input_kind == "day"
    assert store.entries[count].fills == ()
    assert store.entries[count+1].input_kind == "quote"
    assert worker.runner.simulator.engine.config.rsi_period == 14


def test_held_midnight_inventory_is_frozen_before_sell_and_survives_restart():
    worker, store, feed = setup()
    worker.run_once()
    old = store.value
    baskets = tuple(replace(b, quantity=D(q), principal_spent=D(100),
                            entries=(EntryStage(1, D(100), D(q), complete=True),),
                            protected=True, started_at=NOW,
                            stop_price=D(150) if b.symbol == "BTCUSDT" else None)
                    for b, q in zip(old.state.baskets, ("1", "2")))
    store.value = replace(old, state=replace(old.state, baskets=baskets,
                          account=replace(old.state.account, cash=D(9700))))
    feed.now = NOW.replace(day=10, hour=0, minute=0, second=7)
    count = len(store.entries)
    result = worker.run_once()
    assert store.entries[count].input_kind == "day" and store.entries[count].fills == ()
    assert store.value.state.account.day_start_equity == D(10000)
    assert store.value.state.basket("BTCUSDT").quantity == 0 and result.fills == 1
    assert store.value.state.account.cash > D(9700)
    feed.now += timedelta(seconds=1)
    PaperWorker(worker.runner, store, feed, worker.clock).run_once()
    assert store.value.state.account.day_start_equity == D(10000)
    assert sum(e.input_kind == "day" for e in store.entries) == 1


def test_crash_after_day_commit_before_quotes_restarts_without_second_baseline():
    worker, store, feed = setup()
    worker.run_once()
    feed.now = NOW.replace(day=10, hour=0, minute=0, second=7)
    commit = store.commit
    def interrupted(previous, update):
        if update.entry and update.entry.input_kind == "quote":
            raise RuntimeError("Synthetic crash")
        return commit(previous, update)
    store.commit = interrupted
    with pytest.raises(RuntimeError):
        worker.run_once()
    assert store.value.last_entry.input_kind == "day"
    store.commit = commit
    worker.run_once()
    assert sum(e.input_kind == "day" for e in store.entries) == 1


def test_missing_midnight_candle_cannot_commit_a_partial_day():
    worker, store, feed = setup()
    worker.run_once()
    old = store.value
    feed.now = NOW.replace(day=10, hour=0, minute=0, second=7)
    original = feed.closed_bars
    feed.closed_bars = lambda *args, **kwargs: tuple(
        b for b in original(*args, **kwargs) if b.close_time.hour != 0)
    with pytest.raises(ValueError):
        worker.run_once()
    assert store.value == old


def test_midnight_crossed_during_commit_is_rejected_before_day_write():
    worker, store, feed = setup()
    worker.run_once()
    old = store.value
    feed.now = NOW.replace(day=10, hour=0, minute=0, second=7)
    values = iter((feed.now, feed.now, feed.now+timedelta(days=1)))
    with pytest.raises(ValueError):
        replace(worker, clock=lambda: next(values)).run_once()
    assert store.value == old


def test_runtime_guard_loss_after_fetch_prevents_first_write():
    from investalo_workers.paper_runtime import PaperLeaseLost
    worker, store, feed = setup()
    guard = Mock(side_effect=[None, PaperLeaseLost("lost")])
    with pytest.raises(PaperLeaseLost):
        worker.run_once(guard=guard)
    assert store.value is None and not store.entries
