"""Manual recovery preserves real losses, peers, capital admission and identities."""
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
import unittest

from investalo_trading.futures_capital_recovery import (
    RecoveryRequest, RecoveryReconciliation, assess_recovery, recover_candidate,
    recover_signal_candidate,
)
from investalo_trading.futures_capital_research import freeze_basket_leverage
from test_futures_capital_research import start, choose, buy, mark, event, liquidation

D = Decimal


def stopped_state():
    state = buy(choose(start(), "10"))
    state = mark(state, "80")
    return event(state, liquidation(state))


def request(state):
    p = state.ledger.plan
    return RecoveryRequest(p.tenant_id, p.account_id, "manual-user", "SYNTH0",
                           state.stopped[0].cycle, state.revision, state.state_digest,
                           "manual-recovery", True)


def evidence(state):
    return RecoveryReconciliation(state.state_digest, state.as_of, True, True, 0, 0,
                                  True, "trusted-own-broker-reconciliation")


class ManualFuturesRecoveryTests(unittest.TestCase):
    def test_real_liquidation_loss_blocks_unfunded_full_range_recovery(self):
        state = stopped_state()
        a = assess_recovery(state, request(state), evidence(state), state.as_of)
        self.assertIn("new_basket_budget_missing", a.reasons)
        self.assertLess(a.available_capital, a.required_capital)
        with self.assertRaises(ValueError):
            recover_candidate(state, a, at=state.as_of)

    def funded(self):
        state = stopped_state()
        # Explicit synthetic earlier realized gains, no recovery-created credit.
        ledger = replace(state.ledger, unposted_cash=state.ledger.unposted_cash + D(1000),
                         realized_net_pnl=state.ledger.realized_net_pnl + D(1000))
        return replace(state, ledger=ledger)

    def test_success_retains_entire_ledger_history_and_requires_new_leverage(self):
        state = self.funded()
        a = assess_recovery(state, request(state), evidence(state), state.as_of)
        self.assertTrue(a.allowed, a.reasons)
        new, receipt = recover_candidate(state, a, at=state.as_of)
        self.assertEqual(new.ledger, state.ledger)
        self.assertEqual(new.decisions, state.decisions)
        self.assertEqual(new.stages, state.stages)
        self.assertEqual(new.stopped, ())
        self.assertEqual(new.revision, state.revision + 1)
        self.assertIn("manual-recovery", new.event_ids)
        self.assertTrue(receipt["loss_retained"])
        self.assertFalse(receipt["order_submitted"])
        chosen = freeze_basket_leverage(new, "SYNTH0", D(3), "new-regime",
                                       "new-choice", new.revision, new.as_of)
        self.assertEqual(chosen.decisions[-1].cycle, receipt["next_cycle"])
        with self.assertRaises(ValueError):
            recover_candidate(new, a, at=new.as_of)
        with self.assertRaises(ValueError):
            recover_candidate(state, a, at=state.as_of + timedelta(seconds=31))

    def test_trusted_flat_complete_orders_settlement_freshness_and_consent_required(self):
        state = self.funded()
        r, proof = request(state), evidence(state)
        for change, reason in (
            (dict(position_flat=False), "position_not_flat"),
            (dict(orders_complete=False), "orders_unresolved"),
            (dict(unknown_orders=1), "orders_unresolved"),
            (dict(open_orders=1), "open_orders"),
            (dict(liquidation_booked=False), "liquidation_unbooked"),
            (dict(checked_at=state.as_of - timedelta(seconds=31)), "reconciliation_stale"),
            (dict(checked_at=state.as_of + timedelta(seconds=1)), "reconciliation_stale"),
        ):
            with self.subTest(reason=reason):
                a = assess_recovery(state, r, replace(proof, **change), state.as_of)
                self.assertIn(reason, a.reasons)
                with self.assertRaises(ValueError):
                    recover_candidate(state, a, at=state.as_of)
        self.assertIn("manual_consent_required",
                      assess_recovery(state, replace(r, consent=False), proof, state.as_of).reasons)

    def test_foreign_owner_target_revision_cycle_and_evidence_never_clear_stop(self):
        state = self.funded()
        r, proof = request(state), evidence(state)
        for change in (dict(tenant_id="other"), dict(account_id="other"),
                       dict(expected_revision=0), dict(cycle=2), dict(symbol="SYNTH1"),
                       dict(state_digest="foreign")):
            with self.subTest(change=change), self.assertRaises(ValueError):
                assess_recovery(state, replace(r, **change), proof, state.as_of)
        with self.assertRaises(ValueError):
            assess_recovery(state, r, replace(proof, state_digest="foreign"), state.as_of)

    def test_signal_recovery_keeps_peers_and_clears_old_entry_and_exit_authority(self):
        from test_futures_capital_signals import ready, buy as signal_buy, quote
        from investalo_trading.futures_capital_signals import (
            record_signal_economic_event, declare_signal_leverage, assess_capital_signal,
        )
        signal = quote(signal_buy(ready(), leverage="10"), "80")
        signal = record_signal_economic_event(
            signal, liquidation(signal.economic), "settle-liquidation",
            signal.revision, signal.as_of)
        ledger = replace(signal.economic.ledger,
                         unposted_cash=signal.economic.ledger.unposted_cash + D(1000),
                         realized_net_pnl=signal.economic.ledger.realized_net_pnl + D(1000))
        signal = replace(signal, economic=replace(signal.economic, ledger=ledger))
        a = assess_recovery(signal.economic, request(signal.economic),
                            evidence(signal.economic), signal.as_of)
        recovered, receipt = recover_signal_candidate(signal, a, at=signal.as_of)
        self.assertEqual(recovered.economic.ledger, signal.economic.ledger)
        self.assertEqual(recovered.signals[1:], signal.signals[1:])
        self.assertEqual(recovered.signals[0].cycle, signal.signals[0].cycle + 1)
        self.assertEqual(recovered.signals[0].below_count, 0)
        self.assertEqual(recovered.signals[0].exit_reasons, ())
        self.assertEqual(recovered.signals[0].entry_indicator, signal.signals[0].entry_indicator)
        with self.assertRaises(ValueError):
            declare_signal_leverage(
                recovered, "SYNTH0", D(3), "new-choice-proof", "next-basket-choice",
                recovered.revision, recovered.as_of)
        with self.assertRaises(ValueError):
            assess_capital_signal(recovered, "SYNTH0", D(80), recovered.as_of)
        self.assertFalse(receipt["order_submitted"])
