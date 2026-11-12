"""Frozen model assumptions/native provenance, no historical performance."""
from dataclasses import FrozenInstanceError, replace
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
import unittest

from investalo_marketdata.binance_futures import FundingObservation
from investalo_marketdata.futures_research_profile import (
    boundary_valuation, declared_exit,
    funding_batch, funding_reference, load_economic_protocol,
)
from investalo_trading.futures_capital_research import start_capital_research
from investalo_trading.futures_capital_signals import (
    assess_capital_signal, declare_signal_leverage, observe_capital_prices,
    record_signal_economic_event, replay_capital_hour, simulate_signal_entry, start_capital_signals,
)
from investalo_trading.futures_ledger import FundingSettlement, LedgerMark, LiquidationSettlement
from investalo_trading.timeframe_research import ResearchCandle
from test_futures_capital_signals import hour
from test_futures_ledger import AT

D = Decimal
ROOT = Path(__file__).resolve().parents[2]


def scenarios():
    return load_economic_protocol(
        (ROOT / "docs/research-protocols/futures-capital-economics-20261112.json").read_bytes())


def start(scenario=None):
    scenario = scenario or scenarios()[0]
    profile = scenario.profile()
    marks = tuple(LedgerMark(s, D(100)) for s in profile.plan.symbols)
    economic = start_capital_research(profile.plan, marks, AT, "synthetic-initial")
    return start_capital_signals(profile, economic, marks)


def entered(scenario):
    state = start(scenario)
    for i in range(64):
        frame = hour(state, D(130) - (i // 4) * 2, all_assets=True)
        state = replay_capital_hour(state, frame, state.revision, frame.close_time)
    symbol = state.profile.plan.symbols[0]
    state = declare_signal_leverage(
        state, symbol, scenario.leverage, scenario.assumptions_digest,
        "model-decision", state.revision, state.as_of)
    maximum = state.trade_prices[0].price * (1 + scenario.costs.slippage)
    assessment = assess_capital_signal(state, symbol, maximum, state.as_of)
    return simulate_signal_entry(state, assessment, maximum, "model-entry", state.revision, state.as_of)


def quote(state, trade, mark=None):
    prices = tuple(LedgerMark(s, D(trade)) for s in state.profile.plan.symbols)
    marks = tuple(LedgerMark(s, D(mark or trade)) for s in state.profile.plan.symbols)
    return observe_capital_prices(
        state, prices, marks, f"quote-{state.revision}",
        state.revision, state.as_of + timedelta(milliseconds=1))


def mark_hour(symbol="BNBUSDT", opened=AT):
    return ResearchCandle(
        f"BINANCE:{symbol}:USDT-M:mark", opened, opened + timedelta(hours=1),
        D(100), D(110), D(90), D(99))


def reference(scenario=None, symbol="BNBUSDT", at=AT, rate=".001", native="103"):
    scenario = scenario or scenarios()[0]
    symbol = symbol.removeprefix("BINANCE:")
    row = FundingObservation(at, D(rate), D(native) if native is not None else None, "Regular")
    return funding_reference(symbol, row, mark_hour(symbol), "a" * 64, scenario)


class EconomicProfileTests(unittest.TestCase):
    def test_complete_frozen_cases_and_all_declared_cost_axes(self):
        values = scenarios()
        self.assertEqual(len(values), 10)
        self.assertEqual(len({s.assumptions_digest for s in values}), 10)
        self.assertEqual(len({s.profile().profile_digest for s in values}), 10)
        self.assertEqual(tuple(s.leverage for s in values[:6]), (D(2), D(2), D(5), D(5), D(10), D(10)))
        self.assertEqual(values[0].costs.entry_fee_rate, D(".001"))
        self.assertEqual(values[6].costs.entry_fee_rate, D(".002"))
        self.assertEqual(values[6].costs.positive_funding_multiplier, 2)
        self.assertEqual(values[8].path, "open-high-low-close")
        with self.assertRaises(FrozenInstanceError):
            values[0].leverage = D(10)

    def test_protocol_change_and_resource_bound_fail_before_decode(self):
        raw = (ROOT / "docs/research-protocols/futures-capital-economics-20261112.json").read_bytes()
        for value in (raw + b"\n", raw.replace(b'"slots": 5', b'"slots": 3'),
                      b"x" * 65537, raw.decode()):
            with self.subTest(kind=type(value).__name__), self.assertRaises(ValueError):
                load_economic_protocol(value)

    def test_same_capital_ladder_and_own_budgets_for_both_protection_intervals(self):
        a, b = scenarios()[:2]
        left, right = a.profile().plan, b.profile().plan
        self.assertEqual(left.symbols, tuple(f"BINANCE:{s}" for s in (
            "BNBUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT")))
        self.assertEqual(sum(p.capital for p in left.budgets) + left.remainder, D(10000))
        for symbol in left.symbols:
            self.assertEqual(left.stage_capital(symbol), right.stage_capital(symbol))
            self.assertEqual(len(left.stage_capital(symbol)), 6)
        self.assertTrue(all(c.minimum_notional == 5 and c.quantity_step == D(".00000001")
                            for c in left.contracts))
        self.assertEqual(left.contracts[0].schedule.tier_for(D(100)).maintenance_rate, D(".005"))
        with self.assertRaises(ValueError):
            left.contracts[0].schedule.tier_for(D(1000000))
        self.assertNotEqual(a.profile("tenant", "account").profile_digest,
                            a.profile("tenant", "other").profile_digest)

    def test_invalid_or_mislabelled_scenario_does_not_gain_authority(self):
        value = scenarios()[0]
        for changes in ({"scenario_id": "AI-perfect-regime"}, {"leverage": D(1)},
                        {"protection_hours": True}, {"cost_kind": "broker-calibrated"},
                        {"path": "hindsight-best-path"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(value, **changes)
        with self.assertRaises(ValueError):
            replace(value.costs, positive_funding_multiplier=True)
        with self.assertRaises(ValueError):
            replace(value.costs, slippage=D("NaN"))

    def test_native_settlement_mark_and_millisecond_timestamp_preserved(self):
        at = AT + timedelta(milliseconds=18)
        ref = reference(at=at)
        self.assertEqual(ref.timestamp, at)
        self.assertEqual(ref.mark, 103)
        self.assertEqual(ref.reference_kind, "native-settlement-mark")
        self.assertEqual(ref.applied_rate, D(".001"))
        self.assertEqual(ref.payload, FundingSettlement("BINANCE:BNBUSDT", D(103), D(".001")))

    def test_missing_mark_uses_open_not_unavailable_future_high_low_or_close(self):
        scenario = scenarios()[0]
        row = FundingObservation(AT + timedelta(milliseconds=29), D(".001"), None, None)
        original = mark_hour()
        changed = replace(original, high=D(200), low=D(50), close=D(190))
        a = funding_reference("BNBUSDT", row, original, "a" * 64, scenario)
        b = funding_reference("BNBUSDT", row, changed, "a" * 64, scenario)
        self.assertEqual(a.mark, 100)
        self.assertEqual(b.mark, 100)
        self.assertEqual(a.reference_kind, "containing-H1-mark-open-approximation")
        self.assertNotEqual(a.evidence_digest, b.evidence_digest)

    def test_positive_cost_stress_negative_credit_and_zero_are_distinct(self):
        stress = scenarios()[6]
        for rate, expected in ((".001", ".002"), ("-.001", "-.001"), ("0", "0")):
            with self.subTest(rate=rate):
                ref = reference(stress, rate=rate, native=None)
                self.assertEqual(ref.native_rate, D(rate))
                self.assertEqual(ref.applied_rate, D(expected))
                self.assertEqual(ref.mark, 100)

    def test_foreign_price_kind_source_window_and_unsupported_timestamp_rejected(self):
        row = FundingObservation(AT, D(".001"), None, None)
        for symbol, value, source in (
            ("OTHER", mark_hour(), "a" * 64),
            ("BNBUSDT", replace(mark_hour(), symbol="BNBUSDT:USDT-M:trade"), "a" * 64),
            ("BNBUSDT", replace(mark_hour(), symbol="BNBUSDT:USDT-M:mark"), "a" * 64),
            ("BNBUSDT", mark_hour(opened=AT + timedelta(hours=1)), "a" * 64),
            ("BNBUSDT", mark_hour(), "short"),
        ):
            with self.subTest(symbol=symbol, source=source), self.assertRaises(ValueError):
                funding_reference(symbol, row, value, source, scenarios()[0])
        delayed = replace(row, timestamp=AT + timedelta(seconds=1))
        with self.assertRaises(ValueError):
            funding_reference("BNBUSDT", delayed, mark_hour(), "a" * 64, scenarios()[0])

    def test_source_and_scenario_bindings_change_funding_evidence_digest(self):
        row = FundingObservation(AT, D(".001"), None, "Regular")
        a = funding_reference("BNBUSDT", row, mark_hour(), "a" * 64, scenarios()[0])
        b = funding_reference("BNBUSDT", row, mark_hour(), "b" * 64, scenarios()[0])
        c = funding_reference("BNBUSDT", row, mark_hour(), "a" * 64, scenarios()[1])
        self.assertEqual(len({a.evidence_digest, b.evidence_digest, c.evidence_digest}), 3)

    def test_same_time_batch_preserves_all_native_symbols_and_rejects_mixture(self):
        value = scenarios()[0]
        refs = tuple(reference(value, symbol=s) for s in value.profile().plan.symbols)
        batch = funding_batch(refs, value.profile(), AT)
        self.assertEqual(len(batch.settlements), 5)
        with self.assertRaises(ValueError):
            funding_batch(refs[::-1], value.profile(), AT)
        with self.assertRaises(ValueError):
            funding_batch(refs, scenarios()[1].profile(), AT)
        with self.assertRaises(ValueError):
            funding_batch(refs, value.profile(), AT + timedelta(milliseconds=1))
        with self.assertRaises(ValueError):
            funding_batch((refs[0], refs[0]), value.profile(), AT)

    def test_boundary_valuation_binds_only_exact_timestamp_native_marks(self):
        value = scenarios()[0]
        state = start(value)
        frame = hour(state, "99", all_assets=True)
        row = FundingObservation(frame.close_time, D(".001"), D(103), "Regular")
        bar = mark_hour(opened=frame.close_time)
        ref = funding_reference("BNBUSDT", row, bar, "a" * 64, value)
        marks, evidence = boundary_valuation(frame, (ref,), value.profile())
        self.assertEqual(marks[0].price, 103)
        self.assertTrue(all(m.price == 99 for m in marks[1:]))
        self.assertEqual(len(evidence), 64)
        self.assertEqual(frame.mark[0].close, 99)
        with self.assertRaises(ValueError):
            boundary_valuation(frame, (replace(ref, timestamp=frame.close_time + timedelta(milliseconds=1)),),
                               value.profile())

    def test_regular_exit_uses_actual_observed_gap_not_guaranteed_net_stop(self):
        scenario = scenarios()[0]
        state = quote(entered(scenario), "110")
        stop = state.signals[0].stop
        state = quote(state, "99")
        payload = declared_exit(state, state.profile.plan.symbols[0], scenario)
        self.assertLess(payload.price, stop)
        self.assertEqual(payload.price, D(99) * (1 - scenario.costs.slippage))
        self.assertEqual(payload.fee, payload.quantity * payload.price * D(".001"))
        changed = record_signal_economic_event(
            state, payload, "model-gap-exit", state.revision, state.as_of)
        self.assertLess(changed.economic.ledger.realized_net_pnl, 0)

    def test_liquidation_is_explicit_terminal_model_with_separate_insurance_credit(self):
        scenario = scenarios()[4]
        state = quote(entered(scenario), "100", mark="80")
        symbol = state.profile.plan.symbols[0]
        before = state.economic.ledger.baskets[0]
        payload = declared_exit(state, symbol, scenario)
        with self.assertRaises(ValueError):
            declared_exit(state, symbol, scenario, unsafe_state="unverified")
        with self.assertRaises(ValueError):
            declared_exit(state, symbol, scenario, unsafe_state=entered(scenario))
        self.assertIs(type(payload), LiquidationSettlement)
        self.assertEqual(payload.price, D(80) * (1 - scenario.costs.slippage))
        self.assertEqual(payload.returned_margin, 0)
        self.assertGreater(payload.insurance_credit, 0)
        changed = record_signal_economic_event(state, payload, "model-liquidation", state.revision, state.as_of)
        self.assertEqual(changed.economic.ledger.baskets[0].quantity, 0)
        self.assertEqual(changed.signals[0].exit_reasons, ("liquidated",))
        self.assertEqual(changed.economic.stopped[0].unposted_stage_capital,
                         state.profile.plan.budgets[0].margin_capital - before.margin_committed)
        self.assertEqual(changed.economic.ledger.realized_net_pnl, -before.margin_committed - before.entry_fees)

    def test_recovery_cannot_replace_unsafe_price_with_a_profitable_liquidation(self):
        scenario = scenarios()[4]
        unsafe = quote(entered(scenario), "80")
        recovered = quote(unsafe, "110")
        with self.assertRaises(ValueError):
            declared_exit(recovered, recovered.profile.plan.symbols[0], scenario, unsafe_state=unsafe)

    def test_native_credit_without_price_recovery_retains_original_terminal_obligation(self):
        scenario = scenarios()[4]
        unsafe = quote(entered(scenario), "80")
        symbol = unsafe.profile.plan.symbols[0]
        state = record_signal_economic_event(
            unsafe, FundingSettlement(symbol, D(80), D("-.2")),
            "synthetic-credit", unsafe.revision, unsafe.as_of)
        self.assertFalse(state.economic.liquidation_required)
        with self.assertRaises(ValueError):
            declared_exit(state, symbol, scenario)
        payload = declared_exit(state, symbol, scenario, unsafe_state=unsafe)
        self.assertIs(type(payload), LiquidationSettlement)
        self.assertEqual(payload.insurance_credit, 0)
        changed = record_signal_economic_event(state, payload, "terminal", state.revision, state.as_of)
        self.assertEqual(changed.signals[0].exit_reasons, ("liquidated",))

    def test_foreign_scenario_and_absent_exit_cannot_create_a_fill(self):
        with self.assertRaises(ValueError):
            declared_exit(start(), "BINANCE:BNBUSDT", scenarios()[0])
        state = quote(entered(scenarios()[0]), "110")
        with self.assertRaises(ValueError):
            declared_exit(state, "BINANCE:BNBUSDT", scenarios()[6])


if __name__ == "__main__":
    unittest.main()
