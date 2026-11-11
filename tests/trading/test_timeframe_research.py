from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext
import unittest

from investalo_trading import Candle, CryptoEngine, TradingRejected
from investalo_trading.models import OrderIntent, OrderRecord, OrderStatus, Side
from investalo_trading.pool_research import PoolInstrumentRules, PoolPlan, PoolResearchSimulator
from investalo_trading.simulator import SimulationCosts
from investalo_trading.timeframe_research import (
    GAP_END, GAP_START, ResearchCandle, TimeframeReplay, aggregate_h4,
)

D = Decimal
AT = datetime(2022, 8, 1, tzinfo=timezone.utc)
SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")


def plan():
    return PoolPlan("research", "comparison", SYMBOLS, D("10000"), D("0.01"), 3)


def bars(hours=1, count=72):
    sequence = []
    for index in range(count):
        # RSI enters oversold, then exits and falls again.
        price = D(120 - index) if index < 28 else D(92 + (index - 28) * 2) if index < 40 else D(116 - (index - 40))
        opened = AT + timedelta(hours=index * hours)
        for symbol in SYMBOLS:
            sequence.append(ResearchCandle(symbol, opened, opened + timedelta(hours=hours),
                                           price, price + 1, price - 1, price))
    return tuple(sequence)


class TimeframeTests(unittest.TestCase):
    def test_default_candle_and_engine_remain_h4_only(self):
        hourly = bars()[0]
        with self.assertRaises(ValueError):
            Candle(**hourly.__dict__)
        engine = CryptoEngine()
        state = engine.start("tenant", "account", AT)
        with self.assertRaises(ValueError):
            engine.on_bar(state, hourly)
        self.assertEqual(state.processed_bars, ())

    def test_h4_economic_parity_with_existing_full_budget_pool(self):
        cohort = bars(4)
        old = PoolResearchSimulator(plan(), tuple(PoolInstrumentRules(s) for s in SYMBOLS)).run(cohort)
        new = TimeframeReplay(plan(), 4).run(cohort)
        self.assertEqual(new["net_pnl"], old.simulation.net_pnl)
        self.assertEqual(new["maximum_drawdown_fraction"], old.simulation.maximum_drawdown_fraction)
        self.assertEqual(new["curve"], old.simulation.equity_curve)
        self.assertEqual(new["capital"], old.capital_curve)
        self.assertTrue(new["fills"])
        self.assertEqual(
            [(f.occurred_at, f.quantity, f.price, f.fee) for f in new["fills"]],
            [(f.occurred_at, f.quantity, f.price, f.fee) for f in old.simulation.fills],
        )

    def test_hourly_buys_wait_for_next_open_and_never_spend_manual_reserve(self):
        result = TimeframeReplay(plan(), 1).run(bars())
        state = result["state"]
        orders = {o.intent.intent_id: o for o in state.orders}
        buys = [f for f in result["fills"] if orders[f.intent_id].intent.side.value == "buy"]
        self.assertTrue(buys)
        for fill in buys:
            order = orders[fill.intent_id]
            self.assertEqual(fill.occurred_at, order.intent.created_at + timedelta(microseconds=1))
            self.assertEqual(fill.occurred_at.minute, 0)
            self.assertLessEqual(order.intent.stage, 5)
            self.assertLessEqual(order.filled_principal, order.intent.maximum_quote)
        self.assertEqual({s: len(h) for s, h in zip(SYMBOLS, state.bar_evidence)},
                         {s: 72 for s in SYMBOLS})

    def test_utc_midnight_uses_previous_close_before_same_time_open_gap(self):
        values = list(bars(count=28))
        for index, bar in enumerate(values):
            if bar.open_time == AT + timedelta(days=1):
                values[index] = replace(bar, open=bar.open + 4, high=bar.high + 4)
        result = TimeframeReplay(plan(), 1).run(values)
        midnight = AT + timedelta(days=1)
        points = [p for p in result["curve"] if p.at == midnight]
        self.assertEqual(len(points), 2)
        self.assertNotEqual(points[0].equity, points[1].equity)

    def test_complete_earlier_duplicate_retained_beyond_1024(self):
        runner = TimeframeReplay(plan(), 1)
        engine = runner.engine()
        state = engine.start("research", "comparison", AT)
        first = None
        for index in range(1030):
            opened = AT + timedelta(hours=index)
            bar = ResearchCandle("BTCUSDT", opened, opened + timedelta(hours=1),
                                 D("100"), D("100"), D("100"), D("100"))
            first = first or bar
            state = engine.on_bar(state, bar).state
        self.assertEqual(len(state.bar_evidence[0]), 1030)
        self.assertEqual(engine.on_bar(state, first).state, state)
        with self.assertRaises(TradingRejected):
            engine.on_bar(state, replace(first, close=D("99"), low=D("99")))

    def test_wrong_timeframe_revised_latest_and_gap_fail_closed(self):
        engine = TimeframeReplay(plan(), 1).engine()
        state = engine.start("research", "comparison", AT)
        first = bars()[0]
        state = engine.on_bar(state, first).state
        with self.assertRaises(TradingRejected):
            engine.on_bar(state, replace(first, close=first.close - 1, low=first.low - 1))
        gap = replace(first, open_time=AT + timedelta(hours=2), close_time=AT + timedelta(hours=3))
        self.assertEqual(engine.on_bar(state, gap).events[0].reason, "candle_gap")
        self.assertEqual(len(engine.on_bar(state, gap).state.bar_evidence[0]), 1)
        with self.assertRaises(ValueError):
            engine.on_bar(state, bars(4)[0])

    def test_history_requires_same_complete_window_and_timeframe(self):
        runner = TimeframeReplay(plan(), 1)
        cohort = bars()
        for invalid in (cohort[:-1], cohort + cohort[:1], bars(4), cohort[1:]):
            with self.subTest(length=len(invalid)), self.assertRaises(ValueError):
                runner.history(invalid)
        self.assertEqual(runner.history(reversed(cohort)), runner.history(cohort))

    def test_aggregate_uses_four_complete_closed_hours(self):
        hourly = tuple(b for b in bars(count=4) if b.symbol == "BTCUSDT")
        h4, = aggregate_h4(hourly)
        self.assertEqual(h4.open_time, AT)
        self.assertEqual(h4.close_time, AT + timedelta(hours=4))
        self.assertEqual((h4.open, h4.high, h4.low, h4.close),
                         (hourly[0].open, max(b.high for b in hourly),
                          min(b.low for b in hourly), hourly[-1].close))
        for invalid in (hourly[:3], tuple(reversed(hourly)), hourly[:2] + hourly[1:3]):
            with self.assertRaises(ValueError):
                aggregate_h4(invalid)

    def test_plan_assigns_full_capital_and_cost_stress_is_separately_bound(self):
        runner = TimeframeReplay(plan(), 1)
        self.assertLessEqual(3 * (plan().slot_principal + plan().slot_costs), D("10000"))
        self.assertLess(D("10000") - 3 * (plan().slot_principal + plan().slot_costs), D("0.000001"))
        self.assertGreater(plan().stages[0], D("290"))
        self.assertNotEqual(runner.policy(), TimeframeReplay(plan(), 4).policy())
        doubled = SimulationCosts(D("0.002"), D("0.002"), D("0.002"))
        self.assertNotEqual(runner.policy(), TimeframeReplay(plan(), 1, doubled).policy())

    def test_declared_gap_restarts_signals_without_releasing_positions_or_stops(self):
        runner = TimeframeReplay(plan(), 1)
        state = runner.run(bars(count=24))["state"]
        basket = next(b for b in state.baskets if b.quantity)
        basket = replace(basket, protected=True, stop_price=basket.average_price, rearmed=True)
        intent = OrderIntent("gap-pending", basket.basket_id, basket.symbol, Side.BUY,
                             AT + timedelta(hours=24), state.version, "fixture",
                             stage=2, maximum_quote=D("10"))
        state = replace(state, baskets=tuple(basket if b.symbol == basket.symbol else b
                                             for b in state.baskets),
                        orders=state.orders + (OrderRecord(intent),))
        restarted = runner.engine().restart_after_gap(state)
        kept = restarted.basket(basket.symbol)
        self.assertEqual(kept.quantity, basket.quantity)
        self.assertEqual(kept.entries, basket.entries)
        self.assertEqual(kept.stop_price, basket.stop_price)
        self.assertTrue(kept.protected)
        self.assertIsNone(kept.indicators.previous_close)
        self.assertFalse(kept.rearmed)
        self.assertEqual(restarted.account, state.account)
        self.assertEqual(restarted.bar_evidence, state.bar_evidence)
        self.assertEqual(restarted.orders[-1].status, OrderStatus.CANCELLED)

    def test_only_exact_shared_declared_gap_can_be_replayed(self):
        origin = GAP_START - timedelta(hours=24)
        cohort = tuple(replace(
            b, open_time=origin + (b.open_time - AT), close_time=origin + (b.close_time - AT)
        ) for b in bars(count=48))
        shared = tuple(b for b in cohort if not GAP_START <= b.open_time < GAP_END)
        result = TimeframeReplay(plan(), 1).run(shared)
        self.assertEqual(sum(e.kind == "research_source_gap" for e in result["events"]), 1)
        self.assertEqual([len(h) for h in result["state"].bar_evidence], [44] * 3)
        with self.assertRaises(ValueError):
            TimeframeReplay(plan(), 1).history(tuple(
                b for b in cohort if not GAP_START <= b.open_time < GAP_END + timedelta(hours=1)
            ))

    def test_doubled_costs_charge_real_fills_and_reduce_same_short_holding_equity(self):
        with localcontext() as context:
            context.prec = 36
            costs = SimulationCosts(D("0.002"), D("0.002"), D("0.002"))
            base = TimeframeReplay(plan(), 1).run(bars(count=17))
            stress = TimeframeReplay(plan(), 1, costs).run(bars(count=17))
            self.assertEqual(len(base["fills"]), len(stress["fills"]))
            self.assertTrue(stress["fills"])
            self.assertLess(stress["state"].equity, base["state"].equity)
            for fill in stress["fills"]:
                opened = fill.occurred_at.replace(microsecond=0)
                bar = next(b for b in bars(count=17)
                           if b.open_time == opened and b.symbol == next(
                               o.intent.symbol for o in stress["state"].orders
                               if o.intent.intent_id == fill.intent_id))
                self.assertEqual(fill.price, bar.open * D("1.001") * D("1.002"))
                self.assertEqual(fill.fee, fill.quantity * fill.price * D("0.002"))


if __name__ == "__main__":
    unittest.main()
