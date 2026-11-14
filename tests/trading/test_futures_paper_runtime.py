"""Own injected Paper flow: real reducers, durable replay, no broker claims."""
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from investalo_trading.futures_capital_grid import CapitalGridRule
from investalo_trading.futures_capital_research import freeze_basket_leverage, prepare_capital_entry, start_capital_research
from investalo_trading.futures_capital_signals import CapitalH1SignalProfile, start_capital_signals
from investalo_trading.futures_paper import (
    FuturesPaperConfig, PaperBatch, PaperFunding, PaperQuote, paper_settings, run_paper_batch,
    start_paper, warm_paper,
)
from investalo_trading.futures_paper_journal import FuturesPaperJournal
from investalo_trading.futures_paper_plan import paper_pool_plan
from investalo_trading.futures_ledger import LedgerMark
from investalo_trading.futures_replay_journal import JournalCommitUnknown
from test_futures_capital_signals import hour
from test_futures_ledger import AT, fixture

D = Decimal


def initial(slots=3, candidates=5, limit=None, insurance=True):
    contracts = fixture(candidates).plan.contracts
    plan = paper_pool_plan(
        "tenant", "account", "synthetic-paper",
        contracts, tuple(CapitalGridRule(c.symbol, D(".01"), D("100000")) for c in contracts),
        "a" * 64, initial_slots=slots, configured_limit=limit or slots,
    )
    prices = tuple(LedgerMark(s, D(100)) for s in plan.symbols)
    economic = start_capital_research(plan, prices, AT, "synthetic-paper-genesis")
    profile = CapitalH1SignalProfile(plan, 1, D(0), "synthetic-paper-assumptions")
    config = FuturesPaperConfig(profile, AT + timedelta(hours=16), D(".001"), insurance)
    return start_paper(config, start_capital_signals(profile, economic, prices))


def frames(state, prices):
    result = []
    close = state.signal.last_hour.close_time if state.signal.last_hour else AT
    for price in prices:
        close += timedelta(hours=1)
        result.append(hour(state.signal, str(price), all_assets=True, close=close))
    return tuple(result)


def warmed(**kwargs):
    state = initial(**kwargs)
    return warm_paper(state, frames(state, range(130, 98, -2)), 0, state.config.trading_from)


def packet(state, price="100", *, at=None, hours=(), funding=(), prices=None, input_id=None):
    values = prices or (D(price),) * len(state.signal.profile.plan.symbols)
    return PaperBatch(
        input_id or f"input-{state.revision}", at or state.signal.as_of + timedelta(seconds=1),
        tuple(PaperQuote(s, p, p, p) for s, p in zip(state.signal.profile.plan.symbols, values, strict=True)),
        hours, funding,
    )


def step(state, **kwargs):
    batch = packet(state, **kwargs)
    return run_paper_batch(state, batch, state.revision, batch.quoted_at)


def journal(path, state=None, **kwargs):
    state = state or initial()
    return FuturesPaperJournal.create(path, state.config, state.signal.trade_prices,
                                     state.signal.trade_prices, AT, "synthetic-paper-genesis", **kwargs)


class FuturesPaperTests(unittest.TestCase):
    def test_five_causal_buys_keep_manual_sixth_and_cross_midnight(self):
        state = step(warmed())
        def walk(price):
            nonlocal state
            frame = hour(state.signal, str(price), all_assets=True)
            state = step(state, price=str(price), hours=(frame,), at=frame.close_time)
        for price in (*range(90, 58, -2), 82, *range(80, 63, -2)):
            walk(price)
        self.assertEqual(len(state.signal.economic.stages), 6)
        current = D(64)
        for count in (9, 12, 15):
            for _ in range(40):
                if state.signal.signals[0].rearmed:
                    break
                current += D(".5")
                walk(current)
            self.assertTrue(state.signal.signals[0].rearmed)
            current = (state.signal.economic.stages[-3].price * D(".94")).quantize(D(".01"))
            walk(current)
            self.assertEqual(len(state.signal.economic.stages), count)
        self.assertEqual(tuple(r.stage for r in state.signal.economic.stages if r.symbol == "SYNTH0"),
                         (1, 2, 3, 4, 5))
        basket = state.signal.economic.ledger.baskets[0]
        stages = state.config.profile.plan.stage_capital("SYNTH0")
        self.assertEqual(basket.margin_committed, sum(stages[:5]))
        self.assertGreaterEqual(state.config.profile.plan.budgets[0].margin_capital
                                - basket.margin_committed, stages[5])
        self.assertTrue(state.signal.signals[0].manual_notice)
        self.assertFalse(state.signal.economic.stopped)
        self.assertGreater(state.signal.economic.ledger.day_started_at, AT)
        self.assertEqual(len(step(state, price=str(current)).signal.economic.stages), 15)

    def test_three_full_ranges_can_wait_for_five_candidates(self):
        state = warmed()
        self.assertFalse(state.signal.economic.stages)  # Historical warmup never buys.
        plan = state.config.profile.plan
        self.assertEqual(plan.stage_capital("SYNTH4"), tuple(map(D, (
            "293.13365892", "366.41707366", "458.02134207",
            "572.52667759", "715.65834699", "894.57293374"))))
        state = step(state)
        self.assertEqual(len(state.signal.economic.stages), 3)
        self.assertEqual([a.reasons for a in state.attempts[3:]],
                         [("paper_simultaneous_limit",), ("paper_simultaneous_limit",)])
        self.assertEqual(len(state.signal.economic.decisions), 3)
        self.assertTrue(all(d.leverage == 2 for d in state.signal.economic.decisions))
        self.assertEqual(sum(bool(b.quantity) for b in state.signal.economic.ledger.baskets), 3)

    def test_candidates_can_win_any_free_place(self):
        state = warmed()
        # First three no longer have an oversold RSI; later two remain eligible.
        signals = tuple(replace(s, entry_indicator=replace(s.entry_indicator, rsi=D(50)))
                        if i < 3 else s for i, s in enumerate(state.signal.signals))
        state = replace(state, signal=replace(state.signal, signals=signals))
        state = step(state)
        self.assertEqual(tuple(s.symbol for s in state.signal.economic.stages), ("SYNTH3", "SYNTH4"))
        self.assertTrue(all(s.own_capital == D("293.13365892") for s in state.signal.economic.stages))

    def test_five_slots_budget_and_lower_limit_preserve_open_ranges(self):
        state = step(warmed(slots=5))
        budgets = state.config.profile.plan.budgets
        self.assertEqual(len(state.signal.economic.stages), 5)
        reduced = paper_settings(state, 3, 1, state.revision, state.signal.as_of)
        self.assertEqual(reduced.config.profile.plan.budgets, budgets)
        self.assertEqual(sum(bool(b.quantity) for b in reduced.signal.economic.ledger.baskets), 5)
        self.assertEqual(reduced.config.profile.plan.simultaneous_limit, 3)
        # Direct admission: cap counts first entries only, never active ladders.
        assessment = prepare_capital_entry(reduced.signal.economic, "SYNTH4", D(90), reduced.signal.as_of)
        self.assertNotIn("paper_simultaneous_limit", assessment.reasons)
        with self.assertRaisesRegex(ValueError, "contiguous"):
            paper_settings(reduced, 4, 1, reduced.revision, reduced.signal.as_of)

    def test_raise_ceiling_does_not_fabricate_profit_funded_slots(self):
        state = warmed()
        state = paper_settings(state, 7, 1, state.revision, state.signal.as_of)
        self.assertEqual(state.config.profile.plan.simultaneous_limit, 3)
        self.assertEqual(len(step(state).signal.economic.stages), 3)

    def test_command_clock_and_boolean_revision_rejected(self):
        state = warmed()
        state = paper_settings(state, 4, 1, state.revision, state.observed_at + timedelta(seconds=2))
        batch = packet(state)
        with self.assertRaisesRegex(ValueError, "clock regressed"):
            run_paper_batch(state, batch, state.revision, batch.quoted_at)
        with self.assertRaises(ValueError):
            paper_settings(state, 4, 2, True, state.observed_at)

    def test_no_rearm_no_buy_and_protection_exits_wait_for_fresh_reentry(self):
        state = step(warmed())
        self.assertEqual(len(step(state, price="90").signal.economic.stages), 3)
        state = step(state, price="106")
        self.assertTrue(all(s.protected for s in state.signal.signals[:3]))
        state = step(state, price="100", at=state.signal.as_of + timedelta(seconds=1))
        self.assertEqual(state.signal.economic.ledger.closed_baskets, 3)
        self.assertEqual(len(state.signal.economic.stages), 3)
        self.assertTrue(all(not b.quantity for b in state.signal.economic.ledger.baskets))
        state = step(state, at=state.signal.as_of + timedelta(seconds=1))
        self.assertEqual(tuple(s.symbol for s in state.signal.economic.stages[3:]), ("SYNTH3", "SYNTH4"))

    def test_native_funding_spends_own_isolated_cash_and_duplicate_id_rejects(self):
        state = step(warmed())
        at = state.signal.as_of + timedelta(seconds=1)
        funding = (PaperFunding("SYNTH0", "native-123", at, D(".001")),)
        before = state.signal.economic.ledger.baskets[0]
        state = step(state, at=at, funding=funding)
        after = state.signal.economic.ledger.baskets[0]
        self.assertLess(after.funding_net, 0)
        self.assertEqual(after.margin_committed, before.margin_committed)
        self.assertEqual(after.cost_restored, -after.funding_net)
        duplicate = replace(funding[0], settled_at=at + timedelta(seconds=1))
        with self.assertRaisesRegex(ValueError, "duplicate evidence"):
            step(state, at=duplicate.settled_at, funding=(duplicate,))
        with self.assertRaisesRegex(ValueError, "exact settlement"):
            step(state, at=at + timedelta(seconds=1), funding=funding)

    def test_liquidation_books_loss_and_never_automatically_revives(self):
        state = step(warmed())
        state = step(state, price="40")
        self.assertEqual(len(state.signal.economic.stopped), 3)
        self.assertLess(state.signal.economic.ledger.realized_net_pnl, 0)
        state = step(state, price="100")
        self.assertEqual(len(state.signal.economic.stages), 3)  # Cash remains reserved after liquidation.
        self.assertEqual(tuple(s.exit_reasons for s in state.signal.signals[:3]),
                         (("liquidated",),) * 3)

    def test_liquidation_gap_requires_explicit_insurance_model(self):
        state = step(warmed(insurance=False))
        with self.assertRaisesRegex(ValueError, "insurance assumption"):
            step(state, price="40")
        self.assertFalse(state.signal.economic.stopped)

    def test_earlier_boundary_liquidation_cannot_use_recovered_quote(self):
        state = step(warmed())
        frame = hour(state.signal, "40", all_assets=True)
        with self.assertRaisesRegex(ValueError, "reconciliation before newer quotes"):
            step(state, price="100", hours=(frame,),
                 at=frame.close_time + timedelta(seconds=1))
        self.assertFalse(state.signal.economic.stopped)
        self.assertEqual(len(state.signal.economic.stages), 3)
        self.assertEqual(state.signal.economic.ledger.closed_baskets, 0)

    def test_open_feed_gap_and_warmup_cannot_trade_historical_signals(self):
        state = step(warmed())
        rows = frames(state, (98, 96))
        with self.assertRaisesRegex(ValueError, "feed gap"):
            step(state, price="96", hours=rows, at=rows[-1].close_time)
        initial_state = initial()
        with self.assertRaisesRegex(ValueError, "warmed"):
            step(initial_state, at=initial_state.config.trading_from)
        with self.assertRaisesRegex(ValueError, "once-only"):
            warm_paper(state, frames(initial_state, range(130, 98, -2)),
                       state.revision, state.signal.as_of)

    def test_missing_fresh_time_grid_and_full_batch_rejection(self):
        state = warmed()
        for bad in (
            replace(packet(state), quoted_at=state.signal.as_of + timedelta(hours=1)),
            replace(packet(state), quotes=tuple(reversed(packet(state).quotes))),
            replace(packet(state), funding=(PaperFunding("FOREIGN", "native", state.signal.as_of, D(".001")),)),
        ):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    run_paper_batch(state, bad, state.revision, bad.quoted_at)
        batch = packet(state)
        for now in (batch.quoted_at - timedelta(seconds=1), batch.quoted_at + timedelta(seconds=31)):
            with self.assertRaisesRegex(ValueError, "fresh causal"):
                run_paper_batch(state, batch, state.revision, now)
        plan = state.config.profile.plan
        with self.assertRaisesRegex(ValueError, "fixed2"):
            plan.entry_quantity("SYNTH0", D(100), D(3), D(100))

    def test_unfunded_first_buy_cannot_bypass_core_capacity(self):
        state = step(warmed()).signal.economic
        state = freeze_basket_leverage(state, "SYNTH4", D(2), "synthetic", "manual-core-call",
                                       state.revision, state.as_of)
        result = prepare_capital_entry(state, "SYNTH4", D(100), state.as_of)
        self.assertFalse(result.allowed)
        self.assertEqual(result.reasons, ("paper_simultaneous_limit",))


class FuturesPaperJournalTests(unittest.TestCase):
    def test_same_process_competing_commands_commit_exactly_once(self):
        from concurrent.futures import ThreadPoolExecutor
        genesis = initial()
        with TemporaryDirectory() as directory:
            path = Path(directory) / "paper.jsonl"
            with journal(path, genesis) as saved:
                def change(limit):
                    try:
                        saved.append("settings", limit=limit, settings_revision=1,
                                     expected_revision=0, at=AT)
                        return "committed"
                    except ValueError:
                        return "stale"
                with ThreadPoolExecutor(max_workers=2) as pool:
                    self.assertCountEqual(list(pool.map(change, (3, 4))), ("committed", "stale"))
                self.assertEqual(saved.receipt["sequence"], 1)
                expected, receipt = saved.state, saved.receipt
            with FuturesPaperJournal.restore(path, config_digest=genesis.config.config_digest,
                                              minimum_receipt=receipt) as restored:
                self.assertEqual(restored.state, expected)

    def test_injected_worker_runs_and_restarts_without_duplicate_buy(self):
        from investalo_workers.futures_paper_worker import FuturesPaperWorker
        class Feed:
            def warmup(self, state):
                return frames(state, range(130, 98, -2))
            def batch(self, state):
                return packet(state)
        genesis = initial()
        with TemporaryDirectory() as directory:
            path = Path(directory) / "paper.jsonl"
            with journal(path, genesis) as saved:
                worker = FuturesPaperWorker(saved, Feed(), lambda: saved.state.signal.as_of + timedelta(seconds=1))
                worker = replace(worker, clock=lambda: genesis.config.trading_from)
                worker.warmup()
                worker = replace(worker, clock=lambda: saved.state.signal.as_of + timedelta(seconds=1))
                cycle = worker.run_once()
                self.assertEqual(cycle.entries, 3)
                self.assertFalse(cycle.execution_enabled)
                receipt = saved.receipt
            with FuturesPaperJournal.restore(path, config_digest=genesis.config.config_digest,
                                              minimum_receipt=receipt) as saved:
                worker = FuturesPaperWorker(saved, Feed(), lambda: saved.state.signal.as_of + timedelta(seconds=1))
                self.assertEqual(worker.run_once().entries, 0)
                self.assertEqual(len(saved.state.signal.economic.stages), 3)

    def test_full_restore_and_continuation_after_settings_and_fills(self):
        genesis = initial()
        with TemporaryDirectory() as directory:
            path = Path(directory) / "paper.jsonl"
            with journal(path, genesis) as saved:
                hours = frames(genesis, range(130, 98, -2))
                saved.append("warmup", hours=hours, expected_revision=0, at=genesis.config.trading_from)
                batch = packet(saved.state)
                saved.append("batch", batch=batch, expected_revision=1, at=batch.quoted_at)
                saved.append("settings", limit=7, settings_revision=1, expected_revision=2, at=batch.quoted_at)
                expected, receipt = saved.state, saved.receipt
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
            with FuturesPaperJournal.restore(path, config_digest=genesis.config.config_digest,
                                              minimum_receipt=receipt) as restored:
                self.assertEqual(restored.state, expected)
                self.assertEqual(restored.receipt, receipt)
                batch = packet(expected, price="90")
                actual = restored.append("batch", batch=batch, expected_revision=expected.revision, at=batch.quoted_at)
                self.assertEqual(actual, run_paper_batch(expected, batch, expected.revision, batch.quoted_at))

    def test_invalid_batch_never_changes_disk_and_duplicate_is_not_replayed(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "paper.jsonl"
            with journal(path) as saved:
                saved.append("warmup", hours=frames(saved.state, range(130, 98, -2)), expected_revision=0,
                             at=saved.state.config.trading_from)
                batch = packet(saved.state)
                saved.append("batch", batch=batch, expected_revision=1, at=batch.quoted_at)
                data, receipt = path.read_bytes(), saved.receipt
                for bad in (batch, replace(packet(saved.state), quotes=tuple(reversed(batch.quotes)))):
                    with self.assertRaises(ValueError):
                        saved.append("batch", batch=bad, expected_revision=saved.state.revision, at=bad.quoted_at)
                self.assertEqual(path.read_bytes(), data)
                self.assertEqual(saved.receipt, receipt)

    def test_exclusive_create_restore_foreign_and_truncated_anchor(self):
        genesis = initial()
        with TemporaryDirectory() as directory:
            path = Path(directory) / "paper.jsonl"
            with journal(path) as saved:
                with self.assertRaises((FileExistsError, ValueError)):
                    journal(path)
                with self.assertRaises((BlockingIOError, ValueError)):
                    FuturesPaperJournal.restore(path, config_digest=genesis.config.config_digest)
                saved.append("warmup", hours=frames(saved.state, range(130, 98, -2)), expected_revision=0,
                             at=saved.state.config.trading_from)
                receipt = saved.receipt
            with self.assertRaisesRegex(ValueError, "foreign"):
                FuturesPaperJournal.restore(path, config_digest=replace(
                    genesis.config, assume_insurance_credit=False).config_digest)
            data = path.read_bytes()
            path.write_bytes(data.splitlines(keepends=True)[0])
            with self.assertRaisesRegex(ValueError, "truncated"):
                FuturesPaperJournal.restore(path, config_digest=genesis.config.config_digest, minimum_receipt=receipt)
            path.write_bytes(data[:-1])
            with self.assertRaisesRegex(ValueError, "incomplete"):
                FuturesPaperJournal.restore(path, config_digest=genesis.config.config_digest)

    def test_unknown_fsync_poison_requires_full_readback_without_retry(self):
        genesis = initial()
        with TemporaryDirectory() as directory:
            path = Path(directory) / "paper.jsonl"
            saved = journal(path)
            try:
                with patch("os.fsync", side_effect=OSError("synthetic lost acknowledgement")):
                    with self.assertRaises(JournalCommitUnknown):
                        saved.append("warmup", hours=frames(saved.state, range(130, 98, -2)), expected_revision=0,
                                     at=genesis.config.trading_from)
                for read in (lambda: saved.state, lambda: saved.receipt):
                    with self.assertRaises(JournalCommitUnknown):
                        read()
            finally:
                saved.close()
            with FuturesPaperJournal.restore(path, config_digest=genesis.config.config_digest) as restored:
                self.assertTrue(restored.state.warmed)
                self.assertEqual(restored.state.revision, 1)
