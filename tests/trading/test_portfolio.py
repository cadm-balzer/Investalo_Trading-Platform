"""Joint valuation, causality and capital accounting, using synthetic data only."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext
import unittest

from investalo_trading import (
    Candle, CryptoEngine, Fill, InstrumentRules, OrderIntent, OrderRecord,
    PaperSimulator, PortfolioSimulator, Quote, Side,
    StrategyConfig, TradingRejected, dump_state, load_state, primitive,
)
from investalo_trading.snapshot import digest

D = Decimal
START = datetime(2026, 1, 1, tzinfo=timezone.utc)
SYMBOLS = ("BTCUSDT", "ETHUSDT")


def history(count=24, *, falling=False):
    bars = []
    for index in range(count):
        opened = START + timedelta(hours=4 * index)
        price = D(100 - index) if falling else D("100")
        previous = D(100 - max(0, index - 1)) if falling else price
        for symbol in SYMBOLS:
            bars.append(Candle(symbol, opened, opened + timedelta(hours=4),
                               previous, max(previous, price), min(previous, price), price))
    return tuple(bars)


def holdings():
    # Known confirmed fills in a small account, not generated strategy returns.
    engine = CryptoEngine(StrategyConfig(initial_equity=D("1010")))
    state = engine.start("tenant-test", "joint-test", START)
    state = engine.on_quotes(state, tuple(Quote(s, START, D("100"), D("100"))
                                         for s in SYMBOLS)).state
    for symbol in SYMBOLS:
        intent = OrderIntent(symbol, state.basket(symbol).basket_id, symbol, Side.BUY,
                             START, engine.config.version, "synthetic_confirmed_fill",
                             stage=1, maximum_quote=D("500"))
        state = replace(state, orders=state.orders + (OrderRecord(intent),))
        state = engine.apply_fill(state, Fill(
            f"fill-{symbol}", intent.intent_id, START + timedelta(microseconds=1),
            D("5"), D("100"),
        )).state
    return engine, state


class JointQuoteTests(unittest.TestCase):
    def test_offsetting_prices_do_not_create_transient_account_stop(self):
        engine, state = holdings()
        at = START + timedelta(hours=1)
        batch = (Quote("BTCUSDT", at, D("80"), D("80")),
                 Quote("ETHUSDT", at, D("120"), D("120")))
        sequential = engine.on_quote(state, batch[0]).state
        self.assertTrue(sequential.account.halted)
        joint = engine.on_quotes(state, batch)
        self.assertFalse(joint.state.account.halted)
        self.assertEqual(joint.state.equity, D("1010"))
        self.assertEqual(joint, engine.on_quotes(state, tuple(reversed(batch))))
        duplicate = engine.on_quotes(joint.state, batch)
        self.assertEqual(duplicate.state, joint.state)
        self.assertEqual(duplicate.events, ())
        self.assertEqual(load_state(dump_state(joint.state)), joint.state)

    def test_correlated_gap_exits_both_positions_and_cancels_pending_buy(self):
        engine, state = holdings()
        pending = OrderIntent("pending", state.basket("BTCUSDT").basket_id, "BTCUSDT",
                              Side.BUY, START, engine.config.version, "synthetic_pending",
                              stage=2, maximum_quote=D("1"))
        state = replace(state, orders=state.orders + (OrderRecord(pending),))
        at = START + timedelta(hours=1)
        batch = tuple(Quote(s, at, D("80"), D("80")) for s in SYMBOLS)
        update = engine.on_quotes(state, batch)
        self.assertTrue(update.state.account.halted)
        self.assertIn("initial_loss_limit", update.state.account.halt_reasons)
        self.assertEqual({i.symbol for i in update.intents if i.side == Side.SELL}, set(SYMBOLS))
        simulator = PaperSimulator(engine)
        settled, fills, _ = simulator.settle(update.state, at)
        self.assertEqual({settled.basket(s).quantity for s in SYMBOLS}, {D("0")})
        self.assertEqual(len(fills), 2)
        self.assertTrue(all(not o.unresolved for o in settled.orders))
        self.assertFalse(any(o.intent.side == Side.BUY and o.filled_quantity
                             for o in settled.orders if o.intent.intent_id == "pending"))

    def test_midnight_close_enforces_old_daily_limit_then_resets_without_resume(self):
        engine, state = holdings()
        midnight = START + timedelta(days=1)
        batch = tuple(Quote(s, midnight, D("93"), D("93")) for s in SYMBOLS)
        update = engine.on_quotes(state, batch, closing_day=True)
        self.assertTrue(update.state.account.halted)
        self.assertEqual(update.state.account.halt_reasons, ("daily_loss_limit",))
        reset = engine.reset_day(update.state, midnight)
        self.assertEqual(reset.account.day_start_equity, D("940"))
        self.assertTrue(reset.account.halted)
        self.assertEqual(reset.account.trading_day, midnight.date())
        with self.assertRaises(ValueError):
            engine.on_quotes(reset, batch, closing_day=True)
        with self.assertRaises(TradingRejected):
            engine.on_quotes(state, tuple(replace(q, observed_at=midnight - timedelta(seconds=1))
                                          for q in batch), now=midnight, closing_day=True)

    def test_batch_validation_rejects_partial_duplicate_mixed_and_unfresh_quotes(self):
        engine, state = holdings()
        at = START + timedelta(hours=1)
        good = tuple(Quote(s, at, D("100"), D("100")) for s in SYMBOLS)
        invalid = (good[:1], (good[0], good[0]),
                   (good[0], replace(good[1], observed_at=at + timedelta(seconds=1))),
                   (good[0], replace(good[1], symbol="SOLUSDT")))
        before = dump_state(state)
        for batch in invalid:
            with self.subTest(batch=batch), self.assertRaises(TradingRejected):
                engine.on_quotes(state, batch)
        with self.assertRaises(TradingRejected):
            engine.on_quotes(state, good, now=at - timedelta(seconds=1))
        with self.assertRaises(TradingRejected):
            engine.on_quotes(state, good, now=at + timedelta(seconds=31))
        updated = engine.on_quotes(state, good).state
        with self.assertRaises(TradingRejected):
            engine.on_quotes(updated, tuple(replace(q, observed_at=START) for q in good))
        self.assertEqual(dump_state(state), before)

    def test_midnight_open_gap_does_not_replace_held_position_close_baseline(self):
        engine, state = holdings()
        midnight = START + timedelta(days=1)
        closing = tuple(Quote(s, midnight, D("100"), D("100")) for s in SYMBOLS)
        state = engine.on_quotes(state, closing, closing_day=True).state
        state = engine.reset_day(state, midnight)
        opening = tuple(Quote(s, midnight, D("110"), D("110")) for s in SYMBOLS)
        state = engine.on_quotes(state, opening).state
        self.assertEqual(state.account.day_start_equity, D("1010"))
        self.assertEqual(state.equity, D("1110"))
        at = midnight + timedelta(seconds=1)
        fallen = tuple(Quote(s, at, D("93"), D("93")) for s in SYMBOLS)
        state = engine.on_quotes(state, fallen).state
        self.assertTrue(state.account.halted)
        self.assertIn("daily_loss_limit", state.account.halt_reasons)


class PortfolioTests(unittest.TestCase):
    def test_canonical_inputs_reproduce_identical_result_in_one_account(self):
        runner, bars = PortfolioSimulator(), history(falling=True)
        result = runner.run(bars, tenant_id="tenant-test", account_id="joint-test")
        self.assertEqual(result, runner.run(reversed(bars), tenant_id="tenant-test", account_id="joint-test"))
        self.assertEqual(result.simulation.state.account.initial_equity, D("10000"))
        self.assertEqual(result.peak_active_baskets, 2)
        self.assertEqual(result.initially_unassigned_capital, D("8990"))
        self.assertFalse(result.simulation.manual_fills_fabricated)
        self.assertEqual(result.validation_status, "not_evaluated")
        self.assertEqual(result.simulation.state.account.tenant_id, "tenant-test")
        self.assertTrue(primitive(result)["policy_digest"])
        self.assertEqual(result.policy_digest, digest(runner.policy()))

    def test_missing_windows_gaps_duplicates_unknown_and_excess_history_fail(self):
        bars, runner = history(), PortfolioSimulator()
        invalid = ((), bars[:-1], bars[1:], bars[:4] + bars[6:],
                   bars + bars[:1], (replace(bars[0], symbol="SOLUSDT"),) + bars[1:],
                   tuple(b for b in bars if b.symbol == "BTCUSDT"))
        for value in invalid:
            with self.subTest(length=len(value)), self.assertRaises(ValueError):
                runner.run(value)
        with self.assertRaises(ValueError):
            runner.run((bars[0] for _ in range(20001)))

    def test_signal_buys_wait_for_following_open_and_final_signals_are_not_fills(self):
        runner = PortfolioSimulator()
        last_signal = runner.run(history(16, falling=True))
        self.assertEqual(last_signal.simulation.fills, ())
        self.assertEqual(len(last_signal.simulation.state.orders), 2)
        self.assertTrue(all(not o.unresolved for o in last_signal.simulation.state.orders))
        entered = runner.run(history(17, falling=True))
        buys = {o.intent.intent_id: o.intent for o in entered.simulation.state.orders
                if o.intent.side == Side.BUY}
        self.assertEqual(len(entered.simulation.fills), 2)
        for fill in entered.simulation.fills:
            self.assertGreater(fill.occurred_at, buys[fill.intent_id].created_at)
            self.assertEqual(fill.occurred_at, START + timedelta(hours=64, microseconds=1))
        self.assertGreater(entered.capital_curve[-1].position_principal, 0)

    def test_flat_benchmark_has_hand_computed_costs_rounding_and_shared_cash(self):
        with localcontext() as ctx:
            ctx.prec = 36
            result = PortfolioSimulator().run(history(2))
            quantity = (D("500") / (D("100") * D("1.0005") * D("1.001"))).quantize(
                D(".00000001"), rounding="ROUND_DOWN",
            )
            principal = quantity * D("100") * D("1.0005") * D("1.001") * 2
            fees = principal * D(".001")
            cash = D("10000") - principal - fees
            equity = cash + 2 * quantity * D("99.95")
            benchmark = result.benchmark
            self.assertEqual(benchmark.entry_principal, principal)
            self.assertEqual(benchmark.entry_fees, fees)
            self.assertEqual(benchmark.cash, cash)
            self.assertEqual(benchmark.quantities, tuple((s, quantity) for s in SYMBOLS))
            self.assertEqual(benchmark.net_pnl, equity - D("10000"))
            self.assertEqual(result.simulation.net_pnl, 0)
            self.assertEqual(benchmark.equity_curve[0].equity, D("10000"))
            self.assertEqual(tuple(p.at for p in benchmark.equity_curve),
                             tuple(p.at for p in result.simulation.equity_curve))
            self.assertEqual(result.time_weighted_position_principal, 0)
            self.assertEqual(benchmark.maximum_initial_loss_fraction, (D("10000") - equity) / D("10000"))
            self.assertEqual(benchmark.maximum_daily_loss_fraction, benchmark.maximum_initial_loss_fraction)

    def test_benchmark_peak_drawdown_is_not_initial_capital_loss(self):
        from investalo_trading.portfolio import _loss_limits
        from investalo_trading import EquityPoint
        curve = (
            EquityPoint(START, D("10000")),
            EquityPoint(START + timedelta(hours=1), D("12000")),
            EquityPoint(START + timedelta(hours=2), D("10800")),
            EquityPoint(START + timedelta(days=1), D("11000")),
            EquityPoint(START + timedelta(days=1, hours=1), D("9900")),
        )
        initial, daily = _loss_limits(curve, D("10000"))
        self.assertEqual(initial, D(".01"))
        self.assertEqual(daily, D(".10"))

    def test_principal_metric_is_time_weighted_and_exit_fee_totals_are_not_fabricated(self):
        with localcontext() as ctx:
            ctx.prec = 36
            result = PortfolioSimulator().run(history(26, falling=True))
            points = result.capital_curve
            expected = sum((a.position_principal * D(str((b.at - a.at).total_seconds()))
                            for a, b in zip(points, points[1:])), D("0")) / D("374400")
            self.assertEqual(result.time_weighted_position_principal, expected)
            self.assertEqual(result.time_weighted_principal_fraction, expected / D("10000"))
            self.assertLess(expected, result.maximum_position_principal)
            self.assertEqual(result.total_exit_fees, 0)
            self.assertEqual(result.total_entry_fees,
                             sum((f.fee for f in result.simulation.fills), D("0")))
            for point, equity in zip(points, result.simulation.equity_curve):
                self.assertEqual(point.at, equity.at)
                self.assertEqual(point.cash + point.position_market_value, equity.equity)

    def test_partial_sales_reduce_held_cost_basis_without_releasing_cycle_budget(self):
        engine, state = holdings()
        basket = state.basket("BTCUSDT")
        sale = OrderIntent("sale", basket.basket_id, "BTCUSDT", Side.SELL,
                           START, engine.config.version, "synthetic_confirmed_sale",
                           quantity=D("2"))
        state = replace(state, orders=state.orders + (OrderRecord(sale),))
        state = engine.apply_fill(state, Fill(
            "sale-fill", sale.intent_id, START + timedelta(seconds=1), D("2"), D("100"),
        )).state
        point = PortfolioSimulator(PaperSimulator(engine))._capital(state, START)
        self.assertEqual(point.position_principal, D("800"))
        self.assertEqual(state.basket("BTCUSDT").principal_spent, D("500"))
        self.assertEqual(point.remaining_manual_principal, 0)

    def test_nonzero_exit_fees_equal_confirmed_sell_fills(self):
        bars = list(history(19, falling=True))
        for i, bar in enumerate(bars):
            if bar.open_time == START + timedelta(hours=68):
                bars[i] = replace(bar, open=D("84"), high=D("110"), low=D("84"), close=D("108"))
            elif bar.open_time == START + timedelta(hours=72):
                bars[i] = replace(bar, open=D("108"), high=D("108"), low=D("80"), close=D("80"))
        result = PortfolioSimulator().run(bars)
        orders = {o.intent.intent_id: o.intent for o in result.simulation.state.orders}
        sells = [f for f in result.simulation.fills if orders[f.intent_id].side == Side.SELL]
        self.assertEqual(len(sells), 2)
        self.assertGreater(result.total_exit_fees, 0)
        self.assertEqual(result.total_exit_fees, sum((f.fee for f in sells), D("0")))
        self.assertEqual(result.simulation.closed_basket_count, 2)
        self.assertEqual(result.capital_curve[-1].position_principal, 0)

    def test_quote_step_and_minimum_apply_to_benchmark(self):
        cfg = StrategyConfig(basket_principal=D("501"))
        rules = tuple(InstrumentRules(s, quote_step=D("100")) for s in SYMBOLS)
        result = PortfolioSimulator(PaperSimulator(CryptoEngine(cfg, rules))).run(history(1))
        self.assertLessEqual(result.benchmark.entry_principal, D("1000"))
        rules = tuple(InstrumentRules(s, minimum_quote=D("501")) for s in SYMBOLS)
        with self.assertRaises(ValueError):
            PortfolioSimulator(PaperSimulator(CryptoEngine(instrument_rules=rules))).run(history(1))

    def test_midnight_open_gap_keeps_previous_close_baseline(self):
        bars = list(history(7, falling=True))
        # Position-free fixture still proves closed-bar baseline before an open
        # gap; held-position behavior is separately exercised by batch tests.
        for i, bar in enumerate(bars):
            if bar.open_time == START + timedelta(days=1):
                bars[i] = replace(bar, open=D("105"), high=D("105"))
        result = PortfolioSimulator().run(bars)
        midnight = START + timedelta(days=1)
        points = [p for p in result.capital_curve if p.at == midnight]
        self.assertEqual(len(points), 2)
        self.assertEqual(result.simulation.state.account.trading_day, midnight.date())
        self.assertEqual(result.simulation.state.account.day_start_equity, D("10000"))
        self.assertEqual(result.simulation.fills, ())

    def test_policy_digest_binds_configuration_costs_and_priority(self):
        runner = PortfolioSimulator()
        reversed_cfg = replace(runner.simulator.engine.config, symbols=tuple(reversed(SYMBOLS)))
        other = PortfolioSimulator(PaperSimulator(CryptoEngine(reversed_cfg)))
        self.assertNotEqual(digest(runner.policy()), digest(other.policy()))
        result = other.run(history(2))
        self.assertEqual(result.symbols, tuple(reversed(SYMBOLS)))
        self.assertEqual(result.simulation.state.configuration_digest,
                         digest((other.simulator.engine.config, other.simulator.engine.instrument_rules)))
        with self.assertRaises(ValueError):
            PortfolioSimulator(PaperSimulator(CryptoEngine(
                StrategyConfig(symbols=("BTCUSDT",)),
            ))).run(tuple(b for b in history(1) if b.symbol == "BTCUSDT"))


if __name__ == "__main__":
    unittest.main()
