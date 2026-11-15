"""Actual own Paper liquidation/recovery journal; synthetic prices, retained loss."""
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
import unittest
from unittest.mock import patch

from investalo_trading.futures_paper_journal import FuturesPaperJournal
from investalo_trading.futures_paper_recovery import (
    PaperRecoveryRequest, apply_paper_recovery, assess_paper_recovery, recovery_state, recovery_snapshot,
)
from investalo_trading.futures_paper_status import FuturesAssetPublisher, FuturesAssetReader
from investalo_trading.futures_paper_source import PaperSourceRef
from investalo_trading.capital_digest import digest
from investalo_trading.futures_replay_journal import JournalCommitUnknown
from test_futures_paper_runtime import frames, packet
from test_futures_paper_view import initial
from test_futures_capital_signals import hour

TENANT, ACCOUNT, USER = (str(uuid4()) for _ in range(3))


def prepared(path, tenant=TENANT, account=ACCOUNT, *, profit=True, bound=False):
    from investalo_trading.futures_paper_profit_plan import paper_profit_plan
    base = initial(tenant, account)
    p = base.config.profile.plan
    plan = paper_profit_plan(p.tenant_id, p.account_id, p.policy_digest, p.contracts, p.grid_rules,
        p.grid_source_digest, initial_slots=3, configured_limit=3)
    config = replace(base.config, profile=replace(base.config.profile, plan=plan))
    saved = FuturesPaperJournal.create(path, config, base.signal.trade_prices, base.signal.trade_prices,
                                      base.observed_at, "synthetic-recovery-genesis")
    def source(at):
        sha = digest(("synthetic-source", saved.state.revision, at))
        return PaperSourceRef("market", uuid4().hex, sha, sha, at)
    warm = {"source": source(config.trading_from)} if bound else {}
    saved.append("source_warmup" if bound else "warmup", **warm,
                 hours=frames(saved.state, range(130, 98, -2)),
                 expected_revision=0, at=config.trading_from)
    def feed(price="100", **kwargs):
        batch = packet(saved.state, price=price, **kwargs)
        args = {}
        if bound:
            ref = source(batch.quoted_at)
            batch = replace(batch, input_id="bitget-" + ref.data_digest)
            args = dict(source=ref, prior=saved.source_checkpoint()[2].market)
        return saved.append("source_batch" if bound else "batch", **args,
                            batch=batch, expected_revision=saved.state.revision,
                            at=batch.quoted_at)
    feed()
    if profit:
        h = hour(saved.state.signal, "2000", all_assets=True)
        feed("2000", hours=(h,), at=h.close_time)
        feed("1000")  # Actual full protected exits, substantial synthetic realized gain.
        hours = frames(saved.state, range(2000, 200, -30))
        feed("100", hours=hours, at=hours[-1].close_time + timedelta(seconds=1))
    state = saved.state
    target = next(i for i, b in enumerate(state.signal.economic.ledger.baskets) if b.quantity)
    prices = tuple(D(40) if i == target else b.mark
                   for i, b in enumerate(state.signal.economic.ledger.baskets))
    feed(prices=prices)
    return saved


def recovery_request(state, actor=USER):
    p = state.config.profile.plan
    stopped = state.signal.economic.stopped[0]
    return PaperRecoveryRequest(p.tenant_id, p.account_id, actor, stopped.symbol, stopped.cycle,
                               state.revision, state.state_digest, str(uuid4()), True)


class FuturesOwnPaperRecoveryTests(unittest.TestCase):
    def test_source_cursor_and_original_quote_basis_survive_manual_commit_and_resume(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "paper.jsonl"
            with prepared(path, bound=True) as saved:
                before, _, cursor = saved.source_checkpoint()
                request = recovery_request(before)
                after = saved.append("manual_recovery", request=request,
                    expected_revision=before.revision, at=before.observed_at + timedelta(seconds=1))
                receipt = saved.receipt
                self.assertEqual(saved.source_checkpoint()[2], cursor)
                self.assertEqual(after.signal.as_of, before.signal.as_of)
                self.assertEqual(after.signal.trade_at, cursor.market.collected_at)
            with FuturesPaperJournal.restore(path, config_digest=before.config.config_digest,
                                              minimum_receipt=receipt) as restored:
                batch = packet(restored.state, at=after.observed_at + timedelta(seconds=1),
                    prices=tuple(b.mark for b in after.signal.economic.ledger.baskets))
                sha = digest(("synthetic-next-source", batch.quoted_at))
                source = PaperSourceRef("market", uuid4().hex, sha, sha, batch.quoted_at)
                batch = replace(batch, input_id="bitget-" + sha)
                continued = restored.append("source_batch", batch=batch, source=source,
                    prior=cursor.market, expected_revision=after.revision, at=batch.quoted_at)
                self.assertEqual(continued.revision, after.revision + 1)
                self.assertEqual(restored.source_checkpoint()[2].market, source)

    def test_recovery_adopts_latest_profit_budget_and_retains_deferred_peer_reserves(self):
        from investalo_trading.futures_capital_research import start_capital_research
        from investalo_trading.futures_capital_signals import start_capital_signals
        from investalo_trading.futures_paper import start_paper, warm_paper
        from test_futures_paper_profit import genesis, cycle, grant
        from test_futures_paper_runtime import step
        base = genesis()
        plan = replace(base.config.profile.plan, tenant_id=TENANT, account_id=ACCOUNT)
        profile = replace(base.config.profile, plan=plan)
        config = replace(base.config, profile=profile)
        economic = start_capital_research(plan, base.signal.trade_prices, base.observed_at, "own-seven")
        state = start_paper(config, start_capital_signals(profile, economic, base.signal.trade_prices))
        state = warm_paper(state, frames(state, range(130, 98, -2)), 0, config.trading_from)
        for _ in range(5):
            state = grant(cycle(state))
        state = grant(cycle(state, keep_first=True))
        before = state.config.profile.plan
        self.assertLess(before.budgets[0].capital, before.target_range)
        self.assertGreater(before.remainder, 0)
        state = step(state, prices=tuple(D(40) if i == 0 else b.mark
            for i, b in enumerate(state.signal.economic.ledger.baskets)))
        request = recovery_request(state)
        after = apply_paper_recovery(state, request, state.revision, state.observed_at)
        plan = after.config.profile.plan
        self.assertEqual(plan.budgets[0].capital, before.target_range)
        self.assertEqual(plan.budget_indices[0], len(before.epochs))
        self.assertEqual(plan.epochs, before.epochs)
        self.assertEqual(plan.budgets[1:], state.config.profile.plan.budgets[1:])
        self.assertEqual(after.signal.economic.ledger.unposted_cash,
                         state.signal.economic.ledger.unposted_cash)

    def test_actual_recovery_retains_loss_cash_bases_peers_and_fresh_signal_cycle(self):
        with TemporaryDirectory() as folder, prepared(Path(folder) / "paper.jsonl") as saved:
            before = saved.state
            req = recovery_request(before)
            old = before.signal.economic.ledger
            self.assertFalse(assess_paper_recovery(before, req.symbol, req.cycle, before.observed_at).reasons)
            after = saved.append("manual_recovery", request=req, expected_revision=before.revision,
                                 at=before.observed_at + timedelta(seconds=1))
            ledger = after.signal.economic.ledger
            self.assertEqual((ledger.unposted_cash, ledger.realized_net_pnl, ledger.closed_baskets,
                              ledger.day_start_equity, ledger.day_started_at, ledger.plan.initial_equity),
                             (old.unposted_cash, old.realized_net_pnl, old.closed_baskets,
                              old.day_start_equity, old.day_started_at, old.plan.initial_equity))
            self.assertEqual(after.signal.economic.stages, before.signal.economic.stages)
            self.assertEqual(after.signal.economic.decisions, before.signal.economic.decisions)
            index = before.config.profile.plan.symbols.index(req.symbol)
            for i, row in enumerate(ledger.baskets):
                if i != index:
                    self.assertEqual(row, old.baskets[i])
            self.assertEqual(ledger.baskets[index].charges_in_budget_epoch, 0)
            signal = after.signal.signals[index]
            self.assertEqual((signal.cycle, signal.below_count, signal.rearmed, signal.protected),
                             (req.cycle + 1, 0, False, False))
            self.assertEqual(after.signal.trade_at, before.signal.trade_at)
            self.assertEqual(after.signal.as_of, before.signal.as_of)
            self.assertNotIn(req.symbol, {s.symbol for s in after.signal.economic.stopped})
            batch = packet(after, at=after.observed_at + timedelta(seconds=1),
                prices=tuple(b.mark for b in ledger.baskets))
            later = saved.append("batch", batch=batch, expected_revision=after.revision, at=batch.quoted_at)
            self.assertEqual(tuple(s for s in later.signal.economic.stages if s.symbol == req.symbol),
                             tuple(s for s in after.signal.economic.stages if s.symbol == req.symbol))

    def test_full_range_shortage_blocks_without_reserving_every_candidate(self):
        with TemporaryDirectory() as folder, prepared(Path(folder) / "paper.jsonl", profit=False) as saved:
            state, receipt = saved.checkpoint()
            req = recovery_request(state)
            assessment = assess_paper_recovery(state, req.symbol, req.cycle, state.observed_at)
            self.assertEqual(assessment.reasons, ("new_basket_budget_missing",))
            self.assertGreater(assessment.available, D(2500))
            self.assertLess(assessment.available, assessment.required)
            with self.assertRaisesRegex(ValueError, "budget_missing"):
                saved.append("manual_recovery", request=req, expected_revision=state.revision, at=state.observed_at)
            self.assertEqual(saved.receipt, receipt)

    def test_stale_foreign_and_repeated_manual_commands_never_credit_cash(self):
        with TemporaryDirectory() as folder, prepared(Path(folder) / "paper.jsonl") as saved:
            state, receipt = saved.checkpoint()
            req = recovery_request(state)
            for bad in (replace(req, tenant_id=str(uuid4())), replace(req, state_digest="a" * 64),
                        replace(req, expected_revision=req.expected_revision - 1),
                        replace(req, cycle=req.cycle + 1)):
                with self.subTest(bad=bad), self.assertRaises(ValueError):
                    apply_paper_recovery(state, bad, state.revision, state.observed_at)
            with self.assertRaisesRegex(ValueError, "stale"):
                apply_paper_recovery(state, req, state.revision, state.observed_at + timedelta(seconds=31))
            self.assertEqual(saved.receipt, receipt)
            after = saved.append("manual_recovery", request=req, expected_revision=state.revision, at=state.observed_at)
            with self.assertRaises(ValueError):
                apply_paper_recovery(after, req, after.revision, after.observed_at)
            for changes in ({"consent": False}, {"expected_revision": True}, {"event_id": "old-event"}):
                with self.assertRaises(ValueError):
                    replace(req, **changes)

    def test_actual_status_loss_and_full_restore_include_recovery_without_double_reset(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            status = root / "status"
            status.mkdir(mode=0o700)
            path = root / "paper.jsonl"
            with prepared(path) as saved:
                before, receipt, history = saved.recovery_checkpoint()
                self.assertEqual(len(history), 1)
                loss = history[0]
                self.assertGreater(loss.net_loss, 0)
                with FuturesAssetPublisher(status, saved, clock=lambda: before.observed_at,
                                           recovery_enabled=True) as pub:
                    value = pub.publish(expected_revision=before.revision)
                    self.assertEqual(value.record()["schema_version"], "isolated-usdt-futures-paper-status/3")
                decoded = FuturesAssetReader(status).recovery(TENANT, ACCOUNT)
                self.assertEqual(decoded, recovery_state(before, history))
                self.assertTrue(recovery_snapshot(decoded, before.observed_at)[0]["allowed"])
                self.assertIn("reconciliation_stale", recovery_snapshot(
                    decoded, before.observed_at + timedelta(seconds=31))[0]["reasons"])
            with FuturesPaperJournal.restore(path, config_digest=before.config.config_digest,
                                              minimum_receipt=receipt) as saved:
                self.assertEqual(saved.recovery_checkpoint(), (before, receipt, history))
                req = recovery_request(saved.state)
                saved.append("manual_recovery", request=req, expected_revision=before.revision, at=before.observed_at)
                after, final = saved.checkpoint()
                with FuturesAssetPublisher(status, saved, clock=lambda: after.observed_at,
                                           recovery_enabled=True) as pub:
                    self.assertFalse(pub.publish(expected_revision=after.revision).recovery.rows)
            with FuturesPaperJournal.restore(path, config_digest=before.config.config_digest,
                                              minimum_receipt=final) as saved:
                self.assertEqual(saved.state, after)
                self.assertEqual(saved.recovery_checkpoint()[2], history)

    def test_unknown_fsync_requires_full_readback_and_never_retries_request(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "paper.jsonl"
            with prepared(path) as saved:
                before, receipt = saved.checkpoint()
                req = recovery_request(before)
                with patch("os.fsync", side_effect=OSError("synthetic lost acknowledgement")):
                    with self.assertRaises(JournalCommitUnknown):
                        saved.append("manual_recovery", request=req, expected_revision=before.revision,
                                     at=before.observed_at)
                with self.assertRaises(JournalCommitUnknown):
                    saved.recovery_checkpoint()
            with FuturesPaperJournal.restore(path, config_digest=before.config.config_digest,
                                              minimum_receipt=receipt) as restored:
                self.assertEqual(restored.state.revision, before.revision + 1)
                self.assertEqual(restored.state.signal.economic.ledger.unposted_cash,
                                 before.signal.economic.ledger.unposted_cash)
                self.assertFalse(restored.state.signal.economic.stopped)
                with self.assertRaises(ValueError):
                    restored.append("manual_recovery", request=req, expected_revision=restored.state.revision,
                                    at=restored.state.observed_at)
