"""Approved native minute-open model: source binding, causal cash and replay."""
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from investalo_marketdata.bitget import milliseconds
from investalo_marketdata.futures_settlement_source import BitgetSettlementSource
from investalo_trading.futures_paper import run_paper_batch
from investalo_trading.futures_paper_journal import FuturesPaperJournal
from investalo_trading.futures_paper_minute import (
    PaperMarkMinute, PaperMinuteSettlement, settle_paper_minute,
)
from investalo_trading.futures_paper_settlement import settle_paper_funding
from investalo_trading.futures_paper_view import asset_snapshot
from investalo_trading.futures_replay_journal import JournalCommitUnknown
from investalo_workers.futures_paper_worker import FuturesPaperWorker
from test_futures_paper_feed import crossing, initial as bitget_initial, END, H1
from test_futures_settlement_source import AT as SOURCE_AT, Provider
from test_futures_capital_signals import hour
from test_futures_paper_runtime import initial, frames, journal, packet, step, warmed
from test_futures_paper_settlement import settlement

D = Decimal


def joined():
    state, old, current, _ = crossing()
    target, known = END + H1, END + H1 + timedelta(seconds=65)
    delta_ms = milliseconds(target) - milliseconds(SOURCE_AT)

    def translate_fixture(kind, payload):
        payload["requestTime"] = milliseconds(known)
        for row in payload["data"]:
            if kind == "funding":
                row["fundingTime"] = str(int(row["fundingTime"]) + delta_ms)
            else:
                row[0] = str(int(row[0]) + delta_ms)

    provider = Provider(translate_fixture)
    reference = BitgetSettlementSource(provider.fetch, lambda: known, lambda _: None).collect(target)
    current = replace(current, collected_at=known,
                      quotes=tuple(replace(q, native_at=known - timedelta(milliseconds=1))
                                   for q in current.quotes),
                      funding=(*current.funding[:-5], *reference.funding))
    value = reference.paper_minute_settlement(state, observation=current, previous=old)
    return state, old, current, reference, value


def modeled(state, **kwargs):
    exact = settlement(state, **kwargs)
    return PaperMinuteSettlement(
        exact.input_id, exact.settled_at,
        tuple(PaperMarkMinute(m.symbol, exact.settled_at, exact.settled_at + timedelta(minutes=1),
                              m.price, m.price + 1, m.price - 1, m.price + D(".25"))
              for m in exact.marks), exact.valuation_digest,
        exact.settled_at + timedelta(seconds=65), exact.funding, exact.hours)


def apply(state, value):
    return settle_paper_minute(state, value, state.revision, value.source_collected_at)


class FuturesMinuteFundingTests(unittest.TestCase):
    def test_open_only_native_signed_costs_preserve_budgets_fills_and_real_quote_clock(self):
        state, old, current, reference, value = joined()
        after = apply(state, value)
        self.assertEqual(value.valuation_digest, reference.data_digest)
        self.assertEqual(value.reference_policy, "native-minute-mark-open/1")
        self.assertFalse(reference.record()["exact_settlement_mark_available"])
        self.assertFalse(reference.record()["reference_enabled"])  # Passive archive unchanged.
        self.assertEqual(after.signal.trade_at, old.collected_at)
        self.assertEqual(after.signal.trade_prices, state.signal.trade_prices)
        self.assertEqual(after.config, state.config)
        self.assertEqual(after.signal.economic.stages, state.signal.economic.stages)
        self.assertEqual(after.signal.economic.decisions, state.signal.economic.decisions)
        self.assertEqual(after.signal.economic.ledger.closed_baskets, 0)
        for old_basket, new_basket, minute, funding in zip(
                state.signal.economic.ledger.baskets, after.signal.economic.ledger.baskets,
                value.minutes, value.funding, strict=True):
            expected = -old_basket.quantity * minute.open * funding.rate
            self.assertEqual(new_basket.funding_net - old_basket.funding_net, expected)
            self.assertEqual(new_basket.isolated_balance - old_basket.isolated_balance, expected)
            self.assertEqual(new_basket.quantity, old_basket.quantity)
            self.assertNotEqual(minute.open, minute.close)
            self.assertEqual(new_basket.mark, minute.open)
        snapshot = asset_snapshot(after, tenant_id="tenant", account_id="account", now=current.collected_at)
        self.assertFalse(snapshot["data_fresh"])
        self.assertEqual(snapshot["observed_at"], old.collected_at.isoformat())
        self.assertFalse(after.execution_enabled)

    def test_closed_minute_does_not_extend_rsi_window_or_authorize_funding_as_quotes(self):
        state, old, current, _, value = joined()
        after = apply(state, value)
        with self.assertRaises(ValueError):
            current.paper_batch(after, previous=old)
        quote = current.paper_batch(after, previous=old, settlement=value)
        resumed = run_paper_batch(after, quote, after.revision, current.collected_at)
        self.assertEqual(resumed.signal.trade_at, current.collected_at)
        self.assertEqual(resumed.signal.economic.stages, state.signal.economic.stages)
        self.assertEqual(len(resumed.funding_ids), 5)
        self.assertLess(resumed.signal.last_entry_at + timedelta(seconds=30), quote.quoted_at)
        with self.assertRaises(ValueError):
            current.paper_batch(state, previous=old, settlement=value)

    def test_native_source_disagreement_missing_predecessor_and_revised_rates_stop(self):
        state, old, current, reference, value = joined()
        changed = replace(current, funding=(*current.funding[:-1],
                          replace(current.funding[-1], rate=D(".002"))))
        with self.assertRaisesRegex(ValueError, "disagree"):
            reference.paper_minute_settlement(state, observation=changed, previous=old)
        with self.assertRaises(ValueError):
            reference.paper_minute_settlement(state, observation=current, previous=None)
        after = apply(state, value)
        for bad in (changed, replace(current, funding=current.funding[:-1])):
            with self.subTest(digest=bad.data_digest), self.assertRaises(ValueError):
                bad.paper_batch(after, previous=old, settlement=value)
        with self.assertRaises(ValueError):
            reference.paper_minute_settlement(state, observation=object(), previous=old)

    def test_entire_minute_evidence_and_policy_bound_to_own_acknowledged_receipt(self):
        state, old, current, _, value = joined()
        after = apply(state, value)
        for changed in (
                replace(value, valuation_digest="e" * 64),
                replace(value, source_collected_at=value.source_collected_at + timedelta(seconds=1)),
                replace(value, minutes=(replace(value.minutes[0], high=value.minutes[0].high + 1),
                                       *value.minutes[1:]))):
            self.assertNotEqual(changed.receipt_id, value.receipt_id)
            with self.assertRaises(ValueError):
                current.paper_batch(after, previous=old, settlement=changed)
        self.assertIn(value.receipt_id, after.inputs)
        self.assertTrue(value.receipt_id.startswith("paper-minute-settlement-"))
        with self.assertRaises(ValueError):
            replace(value, reference_policy="current-ticker")

    def test_closed_canonical_ohlc_future_knowledge_and_stale_commit_reject_atomically(self):
        state, _, _, _, value = joined()
        for changes in (
                {"minutes": value.minutes[::-1]}, {"minutes": value.minutes[:-1]},
                {"minutes": list(value.minutes)},
                {"source_collected_at": value.settled_at + timedelta(seconds=59)}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                bad = replace(value, **changes)
                apply(state, bad)
        for changes in ({"high": D(1)}, {"low": D(1000)}, {"open": D(0)},
                        {"close_time": value.minutes[0].close_time + timedelta(seconds=1)}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(value.minutes[0], **changes)
        for at in (value.source_collected_at - timedelta(seconds=1),
                   value.settled_at + timedelta(hours=1, seconds=1)):
            with self.subTest(at=at), self.assertRaises(ValueError):
                settle_paper_minute(state, value, state.revision, at)
        with self.assertRaises(ValueError):
            settle_paper_minute(state, value, state.revision - 1, value.source_collected_at)
        self.assertEqual(state.revision, 2)
        self.assertFalse(state.funding_ids)

    def test_midnight_day_basis_uses_open_before_signed_funding(self):
        state = step(warmed())
        for _ in range(7):
            frame = hour(state.signal, "100", all_assets=True)
            state = step(state, hours=(frame,), at=frame.close_time + timedelta(seconds=1))
        value = modeled(state, price="101", rates=(".001",) * 3)
        after = apply(state, value)
        ledger = after.signal.economic.ledger
        self.assertEqual(value.settled_at.hour, 0)
        self.assertEqual(ledger.day_started_at, value.settled_at)
        self.assertEqual(ledger.equity - ledger.day_start_equity,
                         sum(-b.quantity * D(101) * D(".001")
                             for b in state.signal.economic.ledger.baskets))

    def test_duplicate_native_ids_and_prior_liquidation_cannot_resume_after_recovery(self):
        state = step(warmed())
        value = modeled(state, price="51", rates=(".1",) * 3)
        after = apply(state, value)
        self.assertTrue(after.signal.economic.liquidation_required)
        with self.assertRaisesRegex(ValueError, "reconciliation"):
            step(after, price="100", at=after.observed_at + timedelta(seconds=1))
        with self.assertRaisesRegex(ValueError, "reconciliation"):
            apply(after, modeled(after))
        normal = modeled(state)
        funded = apply(state, normal)
        repeated = replace(modeled(funded), funding=tuple(
            replace(new, native_id=old.native_id)
            for new, old in zip(modeled(funded).funding, normal.funding, strict=True)))
        with self.assertRaises(ValueError):
            apply(funded, repeated)

    def test_exact_and_minute_journal_commands_cannot_be_substituted(self):
        genesis = initial()
        with TemporaryDirectory() as folder:
            with journal(Path(folder) / "paper.jsonl", genesis) as saved:
                saved.append("warmup", hours=frames(genesis, range(130, 98, -2)),
                             expected_revision=0, at=genesis.config.trading_from)
                quote = packet(saved.state)
                saved.append("batch", batch=quote, expected_revision=1, at=quote.quoted_at)
                value, exact = modeled(saved.state), settlement(saved.state)
                with self.assertRaises(ValueError):
                    settle_paper_funding(saved.state, value, 2, value.source_collected_at)
                with self.assertRaises(ValueError):
                    settle_paper_minute(saved.state, exact, 2, value.source_collected_at)
                receipt = saved.receipt
                for kind, argument in (("settlement", value), ("minute_settlement", exact)):
                    with self.subTest(kind=kind), self.assertRaises(ValueError):
                        saved.append(kind, settlement=argument, expected_revision=2,
                                     at=value.source_collected_at)
                self.assertEqual(saved.receipt, receipt)

    def test_previous_exact_funding_journal_bytes_remain_identical(self):
        genesis = initial()
        with TemporaryDirectory() as folder:
            with journal(Path(folder) / "exact.jsonl", genesis) as saved:
                saved.append("warmup", hours=frames(genesis, range(130, 98, -2)),
                             expected_revision=0, at=genesis.config.trading_from)
                quote = packet(saved.state)
                saved.append("batch", batch=quote, expected_revision=1, at=quote.quoted_at)
                value = settlement(saved.state)
                saved.append("settlement", settlement=value, expected_revision=2,
                             at=value.settled_at + timedelta(seconds=5))
                self.assertEqual(saved.receipt["head"],
                                 "387f7e151db6d945f69fc9f8e03f0c130d64d9c6d1790db8617ee575bd4eea29")
                self.assertEqual(saved.state.state_digest,
                                 "a928d153f341c95ed91a05c3ec7616fbba81db9a66516233e52b0af58027d8a4")

    def test_full_journal_restore_binds_sources_before_fresh_quote_continuation(self):
        _, old, current, reference, value = joined()
        genesis = bitget_initial()
        with TemporaryDirectory() as folder:
            path = Path(folder) / "minute.jsonl"
            prices = tuple(b.mark for b in genesis.signal.economic.ledger.baskets)
            # Genesis marks must retain the original plan/identity, not minute marks.
            from investalo_trading.futures_ledger import LedgerMark
            genesis_marks = tuple(LedgerMark(s, p) for s, p in zip(
                genesis.config.profile.plan.symbols, prices, strict=True))
            with FuturesPaperJournal.create(path, genesis.config, genesis_marks, genesis_marks,
                                            genesis.signal.as_of, "source-fixture-genesis") as saved:
                saved.append("warmup", hours=old.hours, expected_revision=0, at=END)
                quote = old.paper_batch(saved.state)
                saved.append("batch", batch=quote, expected_revision=1, at=old.collected_at)
                value = reference.paper_minute_settlement(saved.state, observation=current, previous=old)
                expected = saved.append("minute_settlement", settlement=value, expected_revision=2,
                                        at=current.collected_at)
                receipt = saved.receipt
            with FuturesPaperJournal.restore(path, config_digest=genesis.config.config_digest,
                                              minimum_receipt=receipt) as saved:
                self.assertEqual(saved.state, expected)
                self.assertEqual(saved.receipt, receipt)
                self.assertEqual(saved.state.signal.economic.ledger.baskets[0].mark, value.marks[0].price)
                quote = current.paper_batch(saved.state, previous=old, settlement=value)
                after = saved.append("batch", batch=quote, expected_revision=3, at=current.collected_at)
                self.assertEqual(after.signal.trade_at, current.collected_at)
                self.assertEqual(len(after.funding_ids), 5)

    def test_unknown_write_stops_and_readback_books_model_funding_once(self):
        genesis = initial()
        with TemporaryDirectory() as folder:
            path = Path(folder) / "minute.jsonl"
            with journal(path, genesis) as saved:
                saved.append("warmup", hours=frames(genesis, range(130, 98, -2)),
                             expected_revision=0, at=genesis.config.trading_from)
                quote = packet(saved.state)
                saved.append("batch", batch=quote, expected_revision=1, at=quote.quoted_at)
                value = modeled(saved.state)
                receipt = saved.receipt
                with patch("investalo_trading.futures_capital_journal.os.fsync",
                           side_effect=OSError("ack lost")), self.assertRaises(JournalCommitUnknown):
                    saved.append("minute_settlement", settlement=value, expected_revision=2,
                                 at=value.source_collected_at)
                with self.assertRaises(JournalCommitUnknown):
                    saved.append("minute_settlement", settlement=value, expected_revision=2,
                                 at=value.source_collected_at)
            with FuturesPaperJournal.restore(path, config_digest=genesis.config.config_digest,
                                              minimum_receipt=receipt) as saved:
                self.assertEqual(saved.state.revision, 3)
                self.assertEqual(len(saved.state.funding_ids), 3)
                with self.assertRaises(ValueError):
                    saved.append("minute_settlement", settlement=value, expected_revision=3,
                                 at=value.source_collected_at)

    def test_injected_worker_model_dispatch_requires_both_archive_guards(self):
        genesis = initial()
        with TemporaryDirectory() as folder:
            with journal(Path(folder) / "minute.jsonl", genesis) as saved:
                saved.append("warmup", hours=frames(genesis, range(130, 98, -2)),
                             expected_revision=0, at=genesis.config.trading_from)
                quote = packet(saved.state)
                saved.append("batch", batch=quote, expected_revision=1, at=quote.quoted_at)
                value = modeled(saved.state)

                class Feed:
                    def settlement(self, state):
                        return value

                worker = FuturesPaperWorker(saved, Feed(), lambda: value.source_collected_at)
                guards = []

                def guard():
                    guards.append(True)
                    if len(guards) == 2:
                        raise RuntimeError("source archive unacknowledged")

                receipt = saved.receipt
                with self.assertRaisesRegex(RuntimeError, "archive"):
                    worker.settle_once(guard=guard)
                self.assertEqual(saved.receipt, receipt)
                cycle = worker.settle_once()
                self.assertEqual((cycle.entries, cycle.closures), (0, 0))
                self.assertFalse(cycle.execution_enabled)
                self.assertIn(value.receipt_id, saved.state.inputs)
