"""Actual native journal/worker restore; account, actor and candle ports synthetic."""
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from uuid import UUID

from investalo_trading.futures_broker_bootstrap import (
    BrokerFlatAccount, BrokerCurrentLedgerState, WARMUP_HOURS, WARMUP_BATCH,
)
from investalo_trading.futures_broker_journal import BrokerEntryJournal, VERSION
from investalo_trading.futures_broker_funding import milliseconds
from investalo_trading.futures_capital_signals import assess_capital_signal
from investalo_trading.futures_ledger import LedgerMark, start_futures_ledger
from investalo_workers.futures_demo_bootstrap import DemoBootstrapWorker
from test_demo_basket_orders import native_profile
from test_futures_capital_signals import hour
from test_futures_ledger import AT

D = Decimal
START = AT + timedelta(hours=13, minutes=37, seconds=20)
JOURNAL = UUID(int=901)


def account(at=START):
    return BrokerFlatAccount(D(10000), D(10000), D(0), D(0), D(0), 0,
        at-timedelta(seconds=2), at-timedelta(seconds=1), "b"*64)


def create(path, *, start=START):
    profile = native_profile()
    quotes = tuple(LedgerMark(s, D(61000)) for s in profile.plan.symbols)
    return BrokerEntryJournal.create_current(
        path, profile, quotes, quotes, account(start), start, journal_id=JOURNAL)


def frames(journal):
    state = journal.state.book.signal
    end = state.economic.ledger.financial_started_at.replace(minute=0, second=0, microsecond=0)
    return tuple(hour(state, D(65000)-i*D(10), all_assets=True,
        close=end-timedelta(hours=WARMUP_HOURS-i-1)) for i in range(WARMUP_HOURS))


def worker(journal, values, guard=lambda: None, clock=lambda: START):
    def source(*, symbols, end, offset, count):
        if symbols != journal.state.book.signal.profile.plan.symbols:
            raise ValueError("foreign native symbols")
        if values[-1].close_time != end:
            raise ValueError("changed original warmup end")
        return values[offset:offset+count]
    return DemoBootstrapWorker(journal, source, guard, clock)


def warmed(journal, values=None, clock=lambda: START):
    values = values or frames(journal)
    w = worker(journal, values, clock=clock)
    while not w.warm_once().ready:
        pass
    return journal


class DemoWorkerBootstrapTests(unittest.TestCase):
    def test_current_cash_and_first_partial_day_are_not_backdated_to_midnight(self):
        with TemporaryDirectory() as root, create(Path(root)/"basket") as journal:
            state = journal.state
            ledger = state.book.signal.economic.ledger
            self.assertIs(type(ledger), BrokerCurrentLedgerState)
            self.assertEqual((ledger.as_of, ledger.day_started_at, ledger.financial_started_at), (START,)*3)
            self.assertEqual((ledger.unposted_cash, ledger.equity, ledger.day_start_equity), (D(10000),)*3)
            self.assertEqual(state.funding_checked_ms, milliseconds(START-timedelta(seconds=1)))
            self.assertFalse(state.execution_enabled)

    def test_legacy_research_still_requires_midnight_and_base_schema_has_no_native_fields(self):
        profile = native_profile()
        prices = tuple(LedgerMark(s, D(61000)) for s in profile.plan.symbols)
        with self.assertRaisesRegex(ValueError, "midnight"):
            start_futures_ledger(profile.plan, prices, START, "synthetic-legacy")
        old = start_futures_ledger(profile.plan, prices, AT, "synthetic-legacy")
        self.assertFalse(hasattr(old, "financial_started_at"))

    def test_warmup_updates_indicators_only_and_never_creates_historical_capital_events(self):
        with TemporaryDirectory() as root, create(Path(root)/"basket") as journal:
            original = journal.state.book.signal.economic
            prices = journal.state.book.signal.trade_prices
            warmed(journal)
            signal = journal.state.book.signal
            self.assertEqual(signal.economic, original)
            self.assertEqual(signal.trade_prices, prices)
            self.assertEqual(signal.trade_at, START)
            self.assertEqual(journal.state.warmed_hours, 300)
            self.assertEqual(journal.state.revision, 13)
            self.assertIsNone(signal.last_entry_at)
            self.assertEqual(signal.last_hour.close_time, START.replace(minute=0, second=0, microsecond=0))
            self.assertTrue(all(s.entry_indicator.rsi == 0 for s in signal.signals))
            self.assertTrue(all(s.below_count == 2 for s in signal.signals))
            with self.assertRaises(ValueError):
                assess_capital_signal(signal, "BTCUSDT", D(61000), START)

    def test_partial_bootstrap_restores_exactly_and_worker_continues_original_window_once(self):
        with TemporaryDirectory() as root:
            path = Path(root)/"basket"
            with create(path) as journal:
                values = frames(journal)
                first = worker(journal, values).warm_once()
                self.assertFalse(first.ready)
                anchor, profile = journal.receipt, journal.state.book.signal.profile.profile_digest
            with BrokerEntryJournal.restore(path, journal_id=JOURNAL, profile_digest=profile,
                                            minimum_receipt=anchor) as restored:
                self.assertEqual(restored.state.warmed_hours, WARMUP_BATCH)
                warmed(restored, values)
                receipt = restored.receipt
                self.assertTrue(worker(restored, values).warm_once().ready)
                self.assertEqual(restored.receipt, receipt)
                self.assertEqual(restored.state.revision, 13)

    def test_partial_warmup_cannot_prepare_orders_or_apply_financial_prices(self):
        with TemporaryDirectory() as root, create(Path(root)/"basket") as journal:
            w = worker(journal, frames(journal)); w.warm_once()
            for kind, kwargs in [
                ("prepare", dict(symbol="BTCUSDT", planning_price=D(61000), command_id="forbidden")),
                ("prices", dict(trade=journal.state.book.signal.trade_prices,
                    marks=journal.state.book.signal.trade_prices, event_id="forbidden-prices")),
            ]:
                before = journal.receipt
                with self.assertRaisesRegex(ValueError, "warmup"):
                    journal.append(kind, expected_revision=journal.state.revision, at=START, **kwargs)
                self.assertEqual(journal.receipt, before)

    def test_first_fresh_close_admits_own_margin_times2_without_invalid_partial_day_block(self):
        with TemporaryDirectory() as root, create(Path(root)/"basket") as journal:
            warmed(journal)
            frame = hour(journal.state.book.signal, D(61990), all_assets=True)
            journal.append("hour", frame=frame, expected_revision=journal.state.revision, at=frame.close_time)
            journal.append("prepare", symbol="BTCUSDT", planning_price=D(61990), command_id="first-real-hour",
                expected_revision=journal.state.revision, at=frame.close_time)
            request = journal.state.book.pending.request
            self.assertEqual(request.posted_margin, journal.state.book.signal.profile.plan.stage_capital("BTCUSDT")[0])
            self.assertEqual(request.quantity, (request.posted_margin*2/D(61990)//D(".0001"))*D(".0001"))
            self.assertGreater(request.quantity*D(61990), D(20))
            self.assertEqual(journal.state.book.signal.economic.stages, ())

    def test_native_midnight_changes_day_basis_using_fresh_real_frame_not_historical_cash(self):
        with TemporaryDirectory() as root, create(Path(root)/"basket", start=AT+timedelta(hours=23, minutes=37)) as journal:
            start = journal.state.as_of
            warmed(journal, clock=lambda: start)
            frame = hour(journal.state.book.signal, D(61990), all_assets=True)
            journal.append("hour", frame=frame, expected_revision=journal.state.revision, at=frame.close_time)
            ledger = journal.state.book.signal.economic.ledger
            self.assertEqual(ledger.day_started_at, AT+timedelta(days=1))
            self.assertEqual(ledger.financial_started_at, start)
            self.assertEqual(ledger.day_start_equity, ledger.equity)
            self.assertIs(type(ledger), BrokerCurrentLedgerState)

    def test_gap_future_foreign_or_revised_warmup_rejected_without_committing(self):
        with TemporaryDirectory() as root, create(Path(root)/"basket") as journal:
            values = frames(journal)
            for changed in (values[1:25], values[:23]+(values[24],), (values[0],)*24,
                            tuple(reversed(values[:24]))):
                before = journal.receipt
                with self.assertRaises(ValueError):
                    journal.append("warmup", frames=changed, expected_revision=0, at=START)
                self.assertEqual(journal.receipt, before)
            with self.assertRaises(ValueError):
                journal.append("warmup", frames=values[:25], expected_revision=0, at=START)

    def test_revoked_actor_after_source_prevents_warmup_write(self):
        with TemporaryDirectory() as root, create(Path(root)/"basket") as journal:
            checks = []
            def guard():
                checks.append(True)
                if len(checks) == 2:
                    raise ValueError("synthetic actor revoked")
            before = journal.receipt
            with self.assertRaisesRegex(ValueError, "revoked"):
                worker(journal, frames(journal), guard).warm_once()
            self.assertEqual(journal.receipt, before)

    def test_missing_worker_ack_retains_committed_batch_and_never_rewarms_it(self):
        with TemporaryDirectory() as root, create(Path(root)/"basket") as journal:
            values, checks = frames(journal), []
            def guard():
                checks.append(True)
                if len(checks) == 3:
                    raise ValueError("synthetic lost acknowledgement")
            with self.assertRaisesRegex(ValueError, "acknowledgement"):
                worker(journal, values, guard).warm_once()
            self.assertEqual(journal.state.warmed_hours, WARMUP_BATCH)
            after = worker(journal, values).warm_once()
            self.assertEqual(after.warmed_hours, 2*WARMUP_BATCH)
            self.assertEqual(after.revision, 2)

    def test_first_native_hours_keep_calendar_alignment_and_no_fake_purchases(self):
        with TemporaryDirectory() as root, create(Path(root)/"basket") as journal:
            warmed(journal)
            for _ in range(15):
                frame = hour(journal.state.book.signal, D(61990), all_assets=True)
                journal.append("hour", frame=frame, expected_revision=journal.state.revision, at=frame.close_time)
            signal = journal.state.book.signal
            self.assertEqual(signal.economic.ledger.financial_started_at, START)
            self.assertEqual(signal.economic.ledger.day_started_at, AT+timedelta(days=1))
            self.assertEqual(signal.economic.ledger.unposted_cash, D(10000))
            self.assertEqual(signal.economic.stages, ())
            self.assertEqual(signal.economic.decisions, ())
            self.assertFalse(any(b.quantity for b in signal.economic.ledger.baskets))

    def test_unknown_nonflat_stale_future_and_wrong_equity_do_not_create_journal(self):
        for patch in ({"locked": D(1)}, {"available": D(9999)}, {"unrealized_pnl": D(1)},
                      {"isolated_margin": D(1)}, {"position_count": 1}, {"available": None}):
            with self.assertRaises((ValueError, TypeError)):
                replace(account(), **patch)
        with TemporaryDirectory() as root:
            profile = native_profile()
            quotes = tuple(LedgerMark(s, D(61000)) for s in profile.plan.symbols)
            for bad in (account(START-timedelta(seconds=10)), account(START+timedelta(seconds=10)),
                        replace(account(), equity=D(9000), available=D(9000))):
                path = Path(root)/"invalid"
                with self.assertRaises(ValueError):
                    BrokerEntryJournal.create_current(path, profile, quotes, quotes, bad, START, journal_id=JOURNAL)
                self.assertFalse(path.exists())

    def test_complete_original_header_and_warmup_are_replayed_not_adopted_from_old_schema(self):
        with TemporaryDirectory() as root:
            path = Path(root)/"basket"
            with create(path) as journal:
                warmed(journal)
                expected, receipt = journal.checkpoint()
                profile = journal.state.book.signal.profile.profile_digest
                self.assertEqual(receipt["schema_version"], VERSION)
            with BrokerEntryJournal.restore(path, journal_id=JOURNAL, profile_digest=profile,
                                            minimum_receipt=receipt) as restored:
                self.assertEqual(restored.state, expected)
            wire = path.read_bytes().replace(VERSION.encode(), b"bitget-demo-h1-basket-entry-journal/6", 1)
            path.write_bytes(wire)
            with self.assertRaises(ValueError):
                BrokerEntryJournal.restore(path, journal_id=JOURNAL, profile_digest=profile, minimum_receipt=receipt)
