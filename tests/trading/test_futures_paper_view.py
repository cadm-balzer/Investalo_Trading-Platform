"""Causal display: actual fills, tick-safe thresholds and no order forecasts."""
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
import unittest

from investalo_trading.futures_paper_view import asset_snapshot
from investalo_trading.futures_capital_research import start_capital_research
from investalo_trading.futures_capital_signals import start_capital_signals
from investalo_trading.futures_ledger import LedgerMark
from investalo_trading.futures_paper import PaperBatch, PaperQuote, start_paper, warm_paper, run_paper_batch
from test_futures_paper_runtime import initial as synthetic_initial, frames
from test_futures_ledger import AT

D = Decimal
END = AT + timedelta(hours=16)
NOW = END + timedelta(seconds=1)


def initial(tenant="tenant", account="account"):
    state = synthetic_initial()
    symbols = tuple("BITGET:" + s for s in ("BNBUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"))
    old = state.config.profile.plan
    plan = replace(old, tenant_id=tenant, account_id=account,
                   contracts=tuple(replace(c, symbol=s) for c, s in zip(old.contracts, symbols, strict=True)),
                   budgets=tuple(replace(b, symbol=s) for b, s in zip(old.budgets, symbols, strict=True)),
                   grid_rules=tuple(replace(g, symbol=s) for g, s in zip(old.grid_rules, symbols, strict=True)))
    profile = replace(state.config.profile, plan=plan)
    config = replace(state.config, profile=profile)
    prices = tuple(LedgerMark(s, D(100)) for s in symbols)
    economic = start_capital_research(plan, prices, AT, "synthetic-status-genesis")
    return start_paper(config, start_capital_signals(profile, economic, prices))


def warmed(state=None):
    state = state or initial()
    return warm_paper(state, frames(state, range(130, 98, -2)), state.revision, END)


def opened(state=None):
    state = warmed(state)
    batch = PaperBatch("synthetic-status-quotes", NOW, tuple(
        PaperQuote(s, D(100), D("100.01"), D("100.005")) for s in state.signal.profile.plan.symbols))
    return run_paper_batch(state, batch, state.revision, NOW)


def view(state=None, now=NOW, ready=True):
    return asset_snapshot(state or opened(), tenant_id="tenant", account_id="account",
                          now=now, account_ready=ready)


class FuturesPaperViewTests(unittest.TestCase):
    def test_selected_pool_shows_flat_candidates_and_actual_open_baskets(self):
        snapshot = view()
        self.assertEqual(len(snapshot["assets"]), 5)
        self.assertEqual(sum(a["position"] is not None for a in snapshot["assets"]), 3)
        self.assertEqual(snapshot["rsi_period"], 14)
        self.assertEqual(snapshot["timeframe"], "H1")
        self.assertTrue(snapshot["data_fresh"])
        self.assertEqual(snapshot["indicator_at"], "2026-11-01T16:00:00+00:00")
        self.assertEqual(snapshot["next_signal_check"], "2026-11-01T17:00:00+00:00")
        first = snapshot["assets"][0]
        self.assertEqual(D(first["rsi"]), 0)
        self.assertEqual(first["position"]["last_entry_price"], "100.01")
        self.assertEqual(first["position"]["leverage"], "2")
        self.assertEqual(first["next_buy"]["maximum_fill_price"], "95.00")
        self.assertEqual(first["next_buy"]["status"], "waiting_rearm")
        self.assertEqual(first["next_buy"]["stage"], 2)
        self.assertIn("capacity_full", snapshot["assets"][-1]["next_buy"]["reasons"])

    def test_signal_does_not_promise_purchase_before_price_and_execution_checks(self):
        state = opened()
        signals = tuple(replace(s, rearmed=True) for s in state.signal.signals)
        state = replace(state, signal=replace(state.signal, signals=signals))
        self.assertEqual(view(state)["assets"][0]["next_buy"]["status"], "waiting_price")
        prices = tuple(LedgerMark(p.symbol, D(94)) for p in state.signal.trade_prices)
        state = replace(state, signal=replace(state.signal, trade_prices=prices))
        self.assertEqual(view(state)["assets"][0]["next_buy"]["status"], "signal_confirmed")
        self.assertEqual(view(state)["assets"][0]["next_buy"]["maximum_fill_price"], "95.00")

    def test_next_ceiling_uses_last_actual_dca_fill_instead_of_average_entry(self):
        from test_futures_paper_runtime import step
        from test_futures_capital_signals import hour
        state = opened()
        for price in (*range(90, 58, -2), 82, *range(80, 63, -2)):
            frame = hour(state.signal, str(price), all_assets=True)
            state = step(state, price=str(price), hours=(frame,), at=frame.close_time)
        asset = view(state, now=state.signal.as_of)["assets"][0]
        self.assertEqual(asset["position"]["regular_entries"], 2)
        self.assertNotEqual(asset["position"]["average_entry"], asset["position"]["last_entry_price"])
        self.assertEqual(asset["position"]["last_entry_price"], "64")
        self.assertEqual(asset["next_buy"]["maximum_fill_price"], "60.80")

    def test_rsiexact30_and_first_confirmations_match_trading_contract(self):
        state = warmed()
        # Freed candidates: two cold confirmations, followed by exact30.
        signals = tuple(replace(s, below_count=1) for s in state.signal.signals)
        state = replace(state, signal=replace(state.signal, signals=signals))
        self.assertEqual(view(state)["assets"][0]["next_buy"]["status"], "waiting_confirmation")
        signals = tuple(replace(s, entry_indicator=replace(s.entry_indicator, rsi=D(30)))
                        for s in signals)
        state = replace(state, signal=replace(state.signal, signals=signals))
        self.assertEqual(view(state)["assets"][0]["next_buy"]["status"], "waiting_rsi")

    def test_stale_quotes_or_missing_last_hour_keep_values_but_block_signal(self):
        for later in (NOW + timedelta(seconds=31), NOW + timedelta(hours=1)):
            with self.subTest(later=later):
                snapshot = view(now=later)
                self.assertFalse(snapshot["data_fresh"])
                self.assertIsNotNone(snapshot["assets"][0]["position"])
                self.assertEqual(snapshot["assets"][0]["next_buy"]["status"], "blocked")
                self.assertIn("data_stale", snapshot["assets"][0]["next_buy"]["reasons"])

    def test_fresh_quote_does_not_extend_closed_rsi_entry_window(self):
        from test_futures_paper_runtime import step
        later = NOW + timedelta(seconds=35)
        state = step(opened(), at=later)
        snapshot = view(state, now=later)
        self.assertTrue(snapshot["data_fresh"])
        self.assertEqual(snapshot["assets"][0]["next_buy"]["status"], "waiting_signal_check")

    def test_protected_paused_and_halted_states_cannot_advertise_signal(self):
        state = opened()
        signals = tuple(replace(s, protected=True, stop=D(101)) for s in state.signal.signals)
        state = replace(state, signal=replace(state.signal, signals=signals))
        self.assertIn("exit_protection", view(state)["assets"][0]["next_buy"]["reasons"])
        self.assertIn("account_unavailable", view(ready=False)["assets"][0]["next_buy"]["reasons"])
        ledger = replace(state.signal.economic.ledger, halt_reasons=("synthetic_halt",))
        economic = replace(state.signal.economic, ledger=ledger)
        state = replace(state, signal=replace(state.signal, economic=economic))
        self.assertIn("account_halt", view(state)["assets"][0]["next_buy"]["reasons"])

    def test_liquidation_stays_visible_without_invented_open_position_or_buy(self):
        from test_futures_paper_runtime import step
        state = step(opened(), price="40", at=NOW + timedelta(seconds=1))
        snapshot = view(state, now=NOW + timedelta(seconds=1))
        self.assertIsNone(snapshot["assets"][0]["position"])
        self.assertIn("liquidation_stop", snapshot["assets"][0]["next_buy"]["reasons"])
        self.assertEqual(snapshot["assets"][0]["next_buy"]["status"], "blocked")

    def test_foreign_account_tenant_and_future_state_fail(self):
        state = opened()
        for tenant, account, now in (("other", "account", NOW), ("tenant", "other", NOW),
                                     ("tenant", "account", NOW - timedelta(seconds=1))):
            with self.subTest(tenant=tenant, account=account), self.assertRaises(ValueError):
                asset_snapshot(state, tenant_id=tenant, account_id=account, now=now)
