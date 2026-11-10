"""RSI averaging-down integration and shared risk at both order boundaries."""

import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext
import unittest

from investalo_trading import (
    Candle, CryptoEngine, Fill, InstrumentRules, PaperSimulator, Quote,
    OrderStatus, Side, StrategyConfig, TradingRejected, dump_state, load_state,
)
from investalo_trading.allocation import AllocationPlan
from investalo_trading.models import IndicatorState, floor_step
from investalo_trading.snapshot import digest, primitive
from investalo_trading.staged_research import (
    ADMISSION_PREFIX, RESEARCH_VERSION, ResearchState, StagedResearchSimulator,
)

D = Decimal
START = datetime(2026, 11, 1, tzinfo=timezone.utc)


def adapter(count=5):
    plan = AllocationPlan("tenant-research", "account-research",
                          tuple(f"SYNTH{i}" for i in range(count)), D("10000"), D("0.01"))
    return StagedResearchSimulator(plan, tuple(InstrumentRules(s, quantity_step=D("0.000000000001"))
                                               for s in plan.symbols))


def quotes(engine, state, at, price=D("100")):
    result = engine.on_quotes(state, tuple(Quote(s, at, price, price)
                                          for s in engine.config.symbols),
                              closing_day=at.hour == 0 and state.account.trading_day != at.date())
    state = result.state
    if at.hour == 0 and at.minute == 0 and at.second == 0 and at.microsecond == 0:
        state = engine.reset_day(state, at)
    return state


def seeded(state, symbol, *, below=True, price=D("100")):
    indicator = IndicatorState(previous_close=price, changes=14,
                               average_gain=D("0.01"),
                               average_loss=D("1") if below else D("0.01"))
    basket = replace(state.basket(symbol), indicators=indicator)
    return replace(state, baskets=tuple(basket if b.symbol == symbol else b for b in state.baskets))


def bar_step(engine, state, symbol, opened, close):
    at = opened + timedelta(hours=4)
    state = quotes(engine, state, at, close)
    return engine.on_bar(state, Candle(symbol, opened, at, close, close, close, close))


def fill_one(engine, state, intent, at, price):
    state = quotes(engine, state, at, price)
    engine.validate_dispatch(state, intent.intent_id, at)
    # Synthetic authoritative exact fill; no live dispatch or real instrument claim.
    quantity = floor_step(intent.maximum_quote / price, engine.rules(intent.symbol).quantity_step)
    fill = Fill(f"fill-{intent.intent_id}", intent.intent_id, at,
                quantity, price, quantity * price * D("0.001"))
    result = engine.apply_fill(state, fill)
    return result.state, fill


def first_entry(research, *, cash=D("10000"), symbol=None):
    engine = research.engine()
    symbol = symbol or research.plan.symbols[0]
    state = engine.start(research.plan.tenant_id, research.plan.account_id, START)
    state = replace(state, account=replace(state.account, cash=cash, day_start_equity=cash))
    state = seeded(state, symbol)
    first = bar_step(engine, state, symbol, START, D("100"))
    assert not first.intents
    second = bar_step(engine, first.state, symbol, START + timedelta(hours=4), D("99"))
    assert second.intents
    at = START + timedelta(hours=8, microseconds=1)
    state, fill = fill_one(engine, second.state, second.intents[0], at, D("99"))
    return engine, state, fill


def histories(research, count=18):
    return tuple(Candle(s, START + timedelta(hours=4*i), START + timedelta(hours=4*(i+1)),
                        D(100-i), D(100-i), D(100-i), D(100-i))
                 for i in range(count) for s in research.plan.symbols)


class StagedResearchTests(unittest.TestCase):
    def test_first_entry_requires_two_closed_rsi_signals(self):
        research = adapter()
        engine, state, fill = first_entry(research)
        basket = state.baskets[0]
        self.assertEqual(basket.completed_regular_stages, 1)
        self.assertEqual(basket.average_price, D("99"))
        self.assertAlmostEqual(basket.principal_spent, research.plan.stages[0], places=8)
        self.assertEqual(state.spending[0].principal, fill.quantity * fill.price)
        self.assertIsInstance(state, ResearchState)

    def test_all_five_stages_lower_average_with_rearm_and_price_drop(self):
        research = adapter()
        # Pre-existing synthetic realized profit creates sufficient common headroom.
        engine, state, _ = first_entry(research, cash=D("20000"))
        symbol = research.plan.symbols[0]
        opened = START + timedelta(hours=8)
        averages = [state.basket(symbol).average_price]
        amounts = [state.basket(symbol).entries[0].principal]
        for stage in range(2, 6):
            last = state.basket(symbol).last_regular_price
            state = seeded(state, symbol, below=False, price=last)
            up = bar_step(engine, state, symbol, opened, last * D("1.01"))
            self.assertFalse(up.intents)
            self.assertTrue(up.state.basket(symbol).rearmed)
            down = bar_step(engine, up.state, symbol, opened + timedelta(hours=4), last * D("0.95"))
            self.assertEqual(down.intents[0].stage, stage)
            self.assertEqual(down.intents[0].maximum_quote, research.plan.stages[stage - 1])
            at = opened + timedelta(hours=8, microseconds=1)
            state, _ = fill_one(engine, down.state, down.intents[0], at, last * D("0.95"))
            self.assertEqual(state.basket(symbol).completed_regular_stages, stage)
            self.assertFalse(state.basket(symbol).rearmed)
            averages.append(state.basket(symbol).average_price)
            amounts.append(state.basket(symbol).entries[-1].principal)
            opened += timedelta(hours=8)
        self.assertTrue(all(b < a for a, b in zip(averages, averages[1:])))
        for a, b in zip(amounts, amounts[1:]):
            self.assertLessEqual(abs(b - a * D("1.25")), research.plan.quantum * 2)
        notice = engine._notice(state, symbol)
        self.assertTrue(notice.state.basket(symbol).reserve_notified)
        self.assertFalse(state.basket(symbol).manual_used)
        down = bar_step(engine, state, symbol, opened, state.basket(symbol).last_regular_price * D("0.90"))
        self.assertFalse(any(i.side == Side.BUY for i in down.intents))
        self.assertEqual(state.basket(symbol).completed_regular_stages, 5)
        at = opened + timedelta(hours=4)
        preview = engine.preview_manual(down.state, symbol, at)
        with self.assertRaises(TradingRejected):
            engine.confirm_manual(down.state, preview, at, authorization_reference="")
        manual = engine.confirm_manual(down.state, preview, at,
                                       authorization_reference="synthetic-explicit-confirmation")
        self.assertEqual(manual.intents[0].stage, 6)
        self.assertEqual(manual.intents[0].maximum_quote, research.plan.stages[5])
        before = manual.state.spending[0]
        filled, fill = fill_one(engine, manual.state, manual.intents[0],
                               at + timedelta(microseconds=1),
                               state.basket(symbol).last_regular_price * D("0.90"))
        self.assertTrue(filled.basket(symbol).manual_used)
        self.assertEqual(filled.spending[0].principal, before.principal + fill.quantity * fill.price)
        self.assertEqual(filled.spending[0].fees, before.fees + fill.fee)
        self.assertLess(filled.basket(symbol).average_price, averages[-1])

    def test_price_drop_alone_does_not_rearm_a_second_entry(self):
        research = adapter()
        engine, state, _ = first_entry(research)
        down = bar_step(engine, state, research.plan.symbols[0],
                        START + timedelta(hours=8), D("90"))
        self.assertFalse(any(i.side == Side.BUY for i in down.intents))
        self.assertEqual(down.state.baskets[0].completed_regular_stages, 1)

    def test_natural_synthetic_portfolio_is_canonical_and_versioned(self):
        for count in (3, 5):
            research = adapter(count)
            bars = histories(research)
            result = research.run(bars)
            simulation = result.portfolio.simulation
            self.assertEqual(result, research.run(tuple(reversed(bars))))
            self.assertEqual(result.version, RESEARCH_VERSION)
            self.assertEqual(result.portfolio.schema_version, RESEARCH_VERSION)
            self.assertEqual(simulation.strategy_version, RESEARCH_VERSION)
            self.assertEqual(result.plan_digest, research.plan.plan_digest)
            self.assertEqual(result.policy_digest, digest(research.policy()))
            self.assertEqual(simulation.data_digest, digest(bars))
            self.assertEqual(result.validation_status, "not_evaluated")
            self.assertEqual(result.portfolio.peak_active_baskets, count)
            self.assertTrue(result.admissions)
            self.assertFalse(simulation.manual_fills_fabricated)
            self.assertTrue(all(o.intent.stage != 6 for o in simulation.state.orders
                                if o.intent.side == Side.BUY))
            json.dumps(primitive(result), allow_nan=False)

    def test_prepare_reserves_other_assets_and_logs_full_rejection(self):
        research = adapter()
        engine, state, _ = first_entry(research)
        at = START + timedelta(hours=8, microseconds=1)
        for symbol in research.plan.symbols[1:]:
            prepared = engine._buy(state, symbol, 1, at, "competing-first-stage")
            self.assertTrue(prepared.intents)
            state = prepared.state
        at = START + timedelta(hours=12)
        state = quotes(engine, state, at, D("94.05"))
        attempted = engine._buy(state, research.plan.symbols[0], 2, at, "synthetic-second-stage")
        self.assertFalse(attempted.intents)
        self.assertEqual(attempted.state, state)
        payload = json.loads(attempted.events[0].reason[len(ADMISSION_PREFIX):])
        self.assertEqual(payload["stage"], 2)
        self.assertEqual(payload["principal"], str(research.plan.stages[1]))
        self.assertIn("correlated_stress", payload["assessment"]["reasons"])
        self.assertGreater(D(payload["assessment"]["pending_stress"]), 0)

    def test_dispatch_rechecks_shared_headroom_and_excludes_own_reservation(self):
        research = adapter()
        engine = research.engine()
        state = quotes(engine, engine.start(research.plan.tenant_id,
                                            research.plan.account_id, START), START)
        proposed = engine._buy(state, research.plan.symbols[0], 1, START, "synthetic")
        self.assertTrue(proposed.intents)
        engine.validate_dispatch(proposed.state, proposed.intents[0].intent_id, START)
        state = replace(proposed.state, account=replace(proposed.state.account, cash=D("9500")))
        with self.assertRaises(TradingRejected):
            engine.validate_dispatch(state, proposed.intents[0].intent_id, START)
        sim = PaperSimulator(engine, research.costs)
        state, fills, events = sim.settle(state, START)
        self.assertEqual(fills, ())
        rejection = next(e for e in events if e.reason.startswith(ADMISSION_PREFIX))
        payload = json.loads(rejection.reason[len(ADMISSION_PREFIX):])
        self.assertEqual(payload["boundary"], "dispatch")
        self.assertIn("correlated_stress", payload["assessment"]["reasons"])
        self.assertEqual(payload["assessment"]["pending_stress"], "0.0")
        self.assertEqual(payload["principal"], str(research.plan.stages[0]))

    def test_lifetime_fill_ledger_is_idempotent_and_partial_sell_preserves_budget(self):
        research = adapter()
        engine, state, fill = first_entry(research)
        self.assertEqual(engine.apply_fill(state, fill).state, state)
        spent = state.spending[0]
        at = START + timedelta(hours=9)
        exit_transition = engine._exit(state, state.baskets[0], at, "synthetic_exit")
        intent = exit_transition.intents[0]
        sold = Fill("partial-sell", intent.intent_id, at, intent.quantity / 2, D("99"), D("0.1"),
                    final=False)
        state = engine.apply_fill(exit_transition.state, sold).state
        self.assertEqual(state.spending[0].principal, spent.principal)
        self.assertEqual(state.spending[0].fees, spent.fees + D("0.1"))
        self.assertEqual(state.baskets[0].principal_spent, spent.principal)
        final = Fill("final-sell", intent.intent_id, at + timedelta(seconds=1),
                     intent.quantity / 2, D("99"), D("0.1"))
        state = engine.apply_fill(state, final).state
        self.assertEqual(state.baskets[0].cycle, 1)
        self.assertEqual(state.spending[0].principal, spent.principal)
        self.assertEqual(state.spending[0].fees, spent.fees + D("0.2"))
        self.assertEqual(state.spending[0].first_fill, D("99"))
        blocked = engine._buy(state, research.plan.symbols[0], 1, at, "reopen")
        self.assertFalse(blocked.intents)
        self.assertEqual(blocked.events[0].reason, "research_cycle_reuse_not_enabled")

    def test_v1_configuration_runtime_restore_and_identity_stay_separate(self):
        research = adapter()
        engine, state, _ = first_entry(research)
        self.assertEqual(StrategyConfig().symbols, ("BTCUSDT", "ETHUSDT"))
        with self.assertRaises(ValueError):
            StrategyConfig(symbols=research.plan.symbols)
        with self.assertRaises(ValueError):
            load_state(dump_state(state))
        with self.assertRaises(ValueError):
            CryptoEngine()._validate(state)
        with self.assertRaises(ValueError):
            engine.start("foreign", research.plan.account_id, START)
        with self.assertRaises(ValueError):
            engine._validate(replace(state, account=replace(state.account, tenant_id="foreign")))

    def test_unknown_cancel_requested_and_partial_buys_block_other_assets(self):
        research = adapter()
        engine = research.engine()
        state = quotes(engine, engine.start(research.plan.tenant_id,
                                            research.plan.account_id, START), START)
        first = engine._buy(state, research.plan.symbols[0], 1, START, "synthetic")
        for status in (OrderStatus.UNKNOWN, OrderStatus.CANCEL_REQUESTED):
            changed = replace(first.state, orders=(replace(first.state.orders[0], status=status),))
            blocked = engine._buy(changed, research.plan.symbols[1], 1, START, "competing")
            self.assertFalse(blocked.intents)
            evidence = json.loads(blocked.events[0].reason[len(ADMISSION_PREFIX):])
            self.assertIn("unresolved_order_outcome", evidence["assessment"]["reasons"])
        intent = first.intents[0]
        partial = Fill("partial-buy", intent.intent_id, START, D("0.5"), D("100"), D("0.05"),
                       final=False)
        changed = engine.apply_fill(first.state, partial).state
        blocked = engine._buy(changed, research.plan.symbols[1], 1, START, "competing")
        self.assertFalse(blocked.intents)
        evidence = json.loads(blocked.events[0].reason[len(ADMISSION_PREFIX):])
        self.assertEqual(D(evidence["assessment"]["pending_stress"]),
                         (intent.maximum_quote - D("50")) / 2)

    def test_first_fill_emergency_exit_remains_independent_of_admission(self):
        research = adapter()
        engine, state, _ = first_entry(research)
        at = START + timedelta(hours=9)
        state = quotes(engine, state, at, D("40"))
        self.assertTrue(any(o.intent.side == Side.SELL and o.unresolved for o in state.orders))
        closed, fills, _ = PaperSimulator(engine, research.costs).settle(state, at, buys=False)
        self.assertTrue(fills)
        self.assertEqual(closed.baskets[0].quantity, 0)
        self.assertTrue(closed.baskets[0].risk_stopped)
        self.assertEqual(closed.spending[0].principal, state.spending[0].principal)

    def test_missing_complete_rules_or_marks_fail_closed(self):
        research = adapter()
        with self.assertRaises(ValueError):
            replace(research, instrument_rules=research.instrument_rules[:-1])
        engine = research.engine()
        state = engine.start(research.plan.tenant_id, research.plan.account_id, START)
        state = engine.on_quote(state, Quote(research.plan.symbols[0], START, D("100"), D("100"))).state
        blocked = engine._buy(state, research.plan.symbols[0], 1, START, "missing")
        self.assertFalse(blocked.intents)
        self.assertEqual(blocked.events[0].reason, "complete_allocation_quotes_required")
        with self.assertRaises(ValueError):
            replace(research, plan=replace(research.plan, cost_ratio=D("0.02"))).engine()

    def test_policy_and_decimals_bind_configuration_and_costs(self):
        research = adapter()
        expected = research.run(histories(research))
        with localcontext() as context:
            context.prec = 8
            self.assertEqual(research.run(histories(research)), expected)
        self.assertNotEqual(digest(research.policy()), digest(adapter(3).policy()))
