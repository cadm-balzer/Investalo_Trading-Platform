"""Q36 from actual synthetic Paper fills; no market performance claim."""
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from investalo_trading.futures_capital_research import prepare_capital_entry, start_capital_research
from investalo_trading.futures_capital_signals import start_capital_signals, record_signal_economic_event
from investalo_trading.futures_ledger import ExitFill
from investalo_trading.models import floor_step
from investalo_trading.futures_paper import start_paper, warm_paper, paper_settings
from investalo_trading.futures_paper_journal import FuturesPaperJournal
from investalo_trading.futures_paper_profit import assess_profit_epoch, apply_profit_epoch
from investalo_trading.futures_paper_profit_plan import paper_profit_plan
from investalo_trading.futures_replay_journal import JournalCommitUnknown
from test_futures_paper_runtime import initial, frames, packet, step, journal
from test_futures_capital_signals import hour


def genesis(candidates=7, limit=7):
    old = initial(candidates=candidates, limit=limit)
    p = old.config.profile.plan
    plan = paper_profit_plan(
        p.tenant_id, p.account_id, p.policy_digest, p.contracts, p.grid_rules,
        p.grid_source_digest, initial_slots=p.initial_slots, configured_limit=limit)
    profile = replace(old.config.profile, plan=plan)
    economic = start_capital_research(plan, old.signal.trade_prices, old.signal.as_of,
                                      "synthetic-paper-genesis")
    return start_paper(replace(old.config, profile=profile),
                       start_capital_signals(profile, economic, old.signal.trade_prices))


def warmed(candidates=7, limit=7):
    state = genesis(candidates, limit)
    return warm_paper(state, frames(state, range(130, 98, -2)), 0, state.config.trading_from)


def cycle(state, keep_first=False):
    if state.signal.economic.ledger.closed_baskets:
        hours = frames(state, range(2000, 200, -30))
        state = step(state, hours=hours, at=hours[-1].close_time + timedelta(seconds=1))
    else:
        state = step(state)
    frame = hour(state.signal, "2000", all_assets=True)
    state = step(state, price="2000", hours=(frame,), at=frame.close_time)
    prices = tuple(D(2000) if keep_first and i == 0 else D(1000)
                   for i in range(len(state.config.profile.plan.symbols)))
    return step(state, prices=prices)


def grant(state):
    return apply_profit_epoch(state, state.revision, state.observed_at)


class FuturesPaperProfitTests(unittest.TestCase):
    def test_actual_three_full_exits_fund_one_range_without_credit_or_risk_reset(self):
        state = cycle(warmed())
        old = state.signal.economic.ledger
        self.assertEqual(old.closed_baskets, 3)
        self.assertGreater(old.realized_net_pnl, D("3333.33333333"))
        after = grant(state)
        plan = after.config.profile.plan
        self.assertEqual(plan.funded_slots, 4)
        self.assertEqual(plan.target_range, D("3333.33333333"))
        self.assertEqual(plan.epochs[0].closed_count, 3)
        self.assertEqual(after.signal.economic.ledger, replace(old, plan=plan))
        self.assertEqual(after.signal.trade_at, state.signal.trade_at)
        self.assertEqual(after.signal.economic.stages, state.signal.economic.stages)
        self.assertEqual(assess_profit_epoch(after, now=after.observed_at).reasons[0],
                         "three_new_closures_required")
        with self.assertRaises(ValueError):
            grant(after)

    def test_slots_to_seven_then_volume_and_frozen_open_ladder(self):
        state = warmed()
        for capacity in (4, 5, 6, 7, 7):
            state = grant(cycle(state))
            plan = state.config.profile.plan
            self.assertEqual(plan.funded_slots, capacity)
            self.assertEqual(len(plan.epochs), capacity - 3 if capacity < 7 else
                             (4 if plan.target_range == plan.original_range else 5))
        self.assertEqual(plan.target_range, D("3809.52380952"))
        state = cycle(state, keep_first=True)
        before = state.config.profile.plan
        basket = state.signal.economic.ledger.baskets[0]
        self.assertGreater(basket.quantity, 0)
        after = grant(state)
        plan = after.config.profile.plan
        self.assertEqual(plan.target_range, D("4285.71428571"))
        self.assertEqual(plan.budgets[0], before.budgets[0])
        self.assertEqual(plan.stage_capital(plan.symbols[0]), before.stage_capital(plan.symbols[0]))
        self.assertEqual(after.signal.economic.ledger.baskets[0], basket)
        self.assertEqual(plan.budget_indices[0], 5)
        self.assertTrue(all(i == 6 for i in plan.budget_indices[1:]))
        self.assertEqual(plan.remainder, D("476.19047620"))
        reduced = paper_settings(after, 3, 1, after.revision, after.observed_at)
        self.assertEqual(reduced.config.profile.plan.budgets, plan.budgets)
        # An existing regular ladder is never blocked by the reduced UI ceiling.
        assessment = prepare_capital_entry(reduced.signal.economic, plan.symbols[0],
                                           D(90), reduced.signal.as_of)
        self.assertNotIn("paper_simultaneous_limit", assessment.reasons)
        closed = step(after, price="1000")
        self.assertEqual(closed.config.profile.plan.budget_indices[0], 6)
        self.assertEqual(closed.config.profile.plan.budgets[0].capital, plan.target_range)
        self.assertLess(closed.config.profile.plan.remainder, D(".0000001"))

    def test_ceiling_and_actual_candidate_pool_limit_slots_without_early_volume_growth(self):
        state = cycle(warmed(candidates=5, limit=3))
        self.assertIn("configured_ceiling_reached", assess_profit_epoch(state, now=state.observed_at).reasons)
        state = paper_settings(state, 7, 1, state.revision, state.observed_at)
        for capacity in (4, 5):
            state = grant(state)
            self.assertEqual(state.config.profile.plan.funded_slots, capacity)
            state = cycle(state)
        self.assertIn("candidate_pool_expansion_required",
                      assess_profit_epoch(state, now=state.observed_at).reasons)
        self.assertEqual(state.config.profile.plan.target_range, D("3333.33333333"))

    def test_unrealized_gains_and_losing_full_closures_do_not_fund(self):
        state = step(warmed())
        state = step(state, price="1000")
        self.assertGreater(state.signal.economic.ledger.equity, D(10000))
        self.assertIn("three_new_closures_required",
                      assess_profit_epoch(state, now=state.observed_at).reasons)
        state = step(state, price="100")
        self.assertEqual(state.signal.economic.ledger.closed_baskets, 3)
        self.assertLess(state.signal.economic.ledger.realized_net_pnl, 0)
        self.assertIn("full_realized_range_required",
                      assess_profit_epoch(state, now=state.observed_at).reasons)

    def test_realized_profit_still_needs_cash_alongside_open_margin_and_manual_reserves(self):
        state = cycle(warmed())
        hours = frames(state, range(2000, 200, -30))
        state = step(state, hours=hours, at=hours[-1].close_time + timedelta(seconds=1))
        state = step(state, price="1000")
        ledger = state.signal.economic.ledger
        self.assertTrue(any(b.quantity for b in ledger.baskets))
        changed = replace(ledger, unposted_cash=D(5000))
        value = replace(state, signal=replace(state.signal,
            economic=replace(state.signal.economic, ledger=changed)))
        self.assertGreater(changed.equity, D("13333.33333333"))
        self.assertEqual(assess_profit_epoch(value, now=value.observed_at).reasons,
                         ("insufficient_liquid_profit",))

    def test_actual_partial_exit_does_not_count_and_diagnostics_do_not_gate_growth(self):
        state = step(step(warmed()), price="1000")
        basket = state.signal.economic.ledger.baskets[0]
        contract = state.config.profile.plan.contracts[0]
        quantity = floor_step(basket.quantity / 2, contract.quantity_step)
        payload = ExitFill(basket.symbol, quantity, D(1000),
                           quantity * D(1000) * contract.protective_exit_fee_rate)
        signal = record_signal_economic_event(state.signal, payload, "synthetic-partial-exit",
                                              state.signal.revision, state.observed_at)
        partial = replace(state, signal=signal)
        self.assertEqual(partial.signal.economic.ledger.closed_baskets, 0)
        self.assertEqual(partial.signal.economic.ledger.realized_net_pnl, 0)
        self.assertIn("three_new_closures_required",
                      assess_profit_epoch(partial, now=partial.observed_at).reasons)
        complete = cycle(warmed())
        ledger = replace(complete.signal.economic.ledger, day_start_equity=D(40000))
        warned = replace(complete, signal=replace(complete.signal,
            economic=replace(complete.signal.economic, ledger=ledger)))
        self.assertTrue(warned.signal.economic.warnings)
        self.assertFalse(assess_profit_epoch(warned, now=warned.observed_at).reasons)

    def test_stale_future_cash_shortage_and_open_loss_backing_reject(self):
        state = cycle(warmed())
        for now in (state.observed_at - timedelta(seconds=1), state.observed_at + timedelta(seconds=31)):
            self.assertIn("fresh_complete_valuation_required", assess_profit_epoch(state, now=now).reasons)
        ledger = state.signal.economic.ledger
        # Actual debit scenarios: no new cash inferred from a large recorded realized prefix.
        for cash, reason in ((D(1000), "profit_no_longer_equity_backed"),):
            changed = replace(ledger, unposted_cash=cash)
            value = replace(state, signal=replace(state.signal,
                economic=replace(state.signal.economic, ledger=changed)))
            self.assertIn(reason, assess_profit_epoch(value, now=value.observed_at).reasons)
        stopped = step(step(warmed()), price="40")
        self.assertIn("paper_reconciliation_required",
                      assess_profit_epoch(stopped, now=stopped.observed_at).reasons)
        self.assertTrue(stopped.signal.economic.stopped)

    def test_fixed_profile_and_forged_genesis_cannot_import_growth(self):
        fixed = initial()
        self.assertEqual(assess_profit_epoch(fixed, now=fixed.observed_at).reasons,
                         ("profit_profile_required",))
        grown = grant(cycle(warmed()))
        old = genesis()
        with self.assertRaisesRegex(ValueError, "cannot import"):
            start_paper(grown.config, replace(old.signal, profile=grown.config.profile,
                economic=replace(old.signal.economic, ledger=replace(
                    old.signal.economic.ledger, plan=grown.config.profile.plan))))

    def test_actual_journal_full_profit_restore_and_unknown_write_readback(self):
        original = genesis()
        with TemporaryDirectory() as folder:
            path = Path(folder) / "profit.jsonl"
            saved = journal(path, original)
            saved.append("warmup", hours=frames(original, range(130, 98, -2)),
                         expected_revision=0, at=original.config.trading_from)
            for kwargs in ({}, {"price": "2000"}, {"price": "1000"}):
                if kwargs.get("price") == "2000":
                    frame = hour(saved.state.signal, "2000", all_assets=True)
                    kwargs.update(hours=(frame,), at=frame.close_time)
                batch = packet(saved.state, **kwargs)
                saved.append("batch", batch=batch, expected_revision=saved.state.revision,
                             at=batch.quoted_at)
            before = saved.receipt
            with patch("investalo_trading.futures_capital_journal.os.fsync",
                       side_effect=OSError("synthetic fsync unknown")):
                with self.assertRaises(JournalCommitUnknown):
                    saved.append("profit_epoch", expected_revision=saved.state.revision,
                                 at=saved.state.observed_at)
            with self.assertRaises(JournalCommitUnknown):
                saved.checkpoint()
            saved.close()
            with FuturesPaperJournal.restore(path, config_digest=original.config.config_digest,
                                              minimum_receipt=before) as restored:
                self.assertEqual(restored.state.config.profile.plan.funded_slots, 4)
                self.assertEqual(restored.state.revision, before["sequence"] + 1)
                self.assertEqual(restored.state.signal.economic.ledger.closed_baskets, 3)
                actual = restored.state
                with self.assertRaises(ValueError):
                    restored.append("profit_epoch", expected_revision=actual.revision,
                                    at=actual.observed_at)
                self.assertEqual(restored.state, actual)
            with self.assertRaises(ValueError):
                FuturesPaperJournal.restore(path, config_digest=initial().config.config_digest)
