"""Shared pool capacity, reconciled lifecycle, RSI stages and actual cash gates."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext
import json
import unittest

from investalo_trading import Candle, Fill, Quote, Side, OrderStatus, TradingRejected, dump_state, load_state
from investalo_trading.models import IndicatorState, floor_step
from investalo_trading.pool_research import (
    APPROVED_CANDIDATES, POOL_VERSION, PoolPlan, PoolResearchSimulator, PoolInstrumentRules,
)
from investalo_trading.simulator import PaperSimulator
from investalo_trading.snapshot import digest, primitive
from investalo_trading.staged_research import ADMISSION_PREFIX

D = Decimal
START = datetime(2026, 11, 1, tzinfo=timezone.utc)


def adapter(capacity=5, count=14):
    plan = PoolPlan("pool-tenant", "pool-account", tuple(f"SYNTH{i:02}" for i in range(count)),
                    D("10000"), D("0.01"), capacity)
    return PoolResearchSimulator(plan, tuple(PoolInstrumentRules(s, D("0.000000000001"))
                                             for s in plan.symbols))


def marks(engine, state, at=START, price=D("100")):
    state = engine.on_quotes(state, tuple(Quote(s, at, price, price)
                                         for s in engine.config.symbols),
                             closing_day=at.hour == 0 and state.account.trading_day != at.date()).state
    if at.time().replace(tzinfo=None) == datetime.min.time():
        state = engine.reset_day(state, at)
    return state


def started(research, cash=D("10000")):
    engine = research.engine()
    state = engine.start(research.plan.tenant_id, research.plan.account_id, START)
    state = replace(state, account=replace(state.account, cash=cash, day_start_equity=cash))
    return engine, marks(engine, state)


def buy(engine, state, symbol, event="fixture", at=START):
    prepared = engine._buy(state, symbol, 1, at, event)
    assert prepared.intents
    return prepared


def fill_buy(engine, prepared, at=START, price=D("100")):
    intent = prepared.intents[0]
    engine.validate_dispatch(prepared.state, intent.intent_id, at)
    quantity = floor_step(intent.maximum_quote / price, engine.rules(intent.symbol).quantity_step)
    fill = Fill("buy-" + intent.intent_id, intent.intent_id, at, quantity, price,
                quantity * price * D("0.001"))
    return engine.apply_fill(prepared.state, fill).state, fill


def sell(engine, state, symbol, at, price=D("100"), reason="trailing_stop"):
    exited = engine._exit(state, state.basket(symbol), at, reason)
    intent = exited.intents[0]
    fill = Fill("sell-" + intent.intent_id, intent.intent_id, at, intent.quantity, price,
                intent.quantity * price * D("0.001"))
    return engine.apply_fill(exited.state, fill).state, fill


def seeded(state, symbol, price, below):
    basket = replace(state.basket(symbol), indicators=IndicatorState(
        previous_close=price, changes=14, average_gain=D("0.01"),
        average_loss=D("1") if below else D("0.01"),
    ))
    return replace(state, baskets=tuple(basket if b.symbol == symbol else b for b in state.baskets))


def bar(engine, state, symbol, opened, price):
    at = opened + timedelta(hours=4)
    state = marks(engine, state, at, price)
    return engine.on_bar(state, Candle(symbol, opened, at, price, price, price, price))


class PoolResearchTests(unittest.TestCase):
    def test_candidate_count_never_divides_slot_budget(self):
        self.assertEqual(len(APPROVED_CANDIDATES), 14)
        for capacity in (3, 4, 5):
            pool = adapter(capacity)
            equal = adapter(capacity, capacity)
            self.assertEqual(pool.plan.stages, equal.plan.stages)
            self.assertEqual(pool.plan.slot_principal, equal.plan.slot_principal)
            self.assertEqual(pool.plan.capacity * (pool.plan.slot_principal + pool.plan.slot_costs)
                             + pool.plan.remainder, D("10000"))
        with self.assertRaises(ValueError):
            adapter(True)
        with self.assertRaises(ValueError):
            adapter(2)
        with self.assertRaises(ValueError):
            replace(adapter().plan, symbols=("ONE",) * 14)

    def test_first_intents_claim_capacity_before_filling(self):
        for capacity in (3, 5):
            research = adapter(capacity)
            engine, state = started(research)
            for symbol in research.plan.symbols[:capacity]:
                state = buy(engine, state, symbol).state
            blocked = engine._buy(state, research.plan.symbols[capacity], 1, START, "extra")
            self.assertFalse(blocked.intents)
            self.assertEqual(blocked.events[0].reason, "no_free_funded_slot")
            self.assertEqual(sum(s.symbol is not None for s in state.slots), capacity)
            assessment = json.loads(buy(engine, started(research)[1],
                                        research.plan.symbols[0]).events[-1].reason[len(ADMISSION_PREFIX):])
            self.assertEqual(D(assessment["assessment"]["unused_costs"]),
                             research.plan.slot_costs * capacity)

    def test_unknown_partial_and_cancel_requested_keep_their_slot(self):
        research = adapter()
        engine, state = started(research)
        symbol, other = research.plan.symbols[:2]
        prepared = buy(engine, state, symbol)
        for status in (OrderStatus.UNKNOWN, OrderStatus.CANCEL_REQUESTED):
            changed = replace(prepared.state, orders=(replace(prepared.state.orders[0], status=status),))
            blocked = engine._buy(changed, other, 1, START, "other")
            self.assertFalse(blocked.intents)
            self.assertIsNotNone(engine._slot(blocked.state, symbol))
            self.assertIn("unresolved_order_outcome", blocked.events[0].reason)
        intent = prepared.intents[0]
        partial = Fill("partial", intent.intent_id, START, D("0.5"), D("100"), D("0.05"), final=False)
        changed = engine.apply_fill(prepared.state, partial).state
        blocked = engine._buy(changed, other, 1, START, "other")
        self.assertFalse(blocked.intents)
        reconciled = engine.reconcile_cancelled(changed, intent.intent_id).state
        self.assertIsNotNone(engine._slot(reconciled, symbol))
        self.assertEqual(reconciled.basket(symbol).principal_spent, D("50"))

    def test_authoritative_zero_fill_cancellation_releases_only_its_slot(self):
        research = adapter()
        engine, state = started(research)
        prepared = buy(engine, state, research.plan.symbols[0])
        state = buy(engine, prepared.state, research.plan.symbols[1]).state
        cancelled = engine.reconcile_cancelled(state, prepared.intents[0].intent_id).state
        self.assertIsNone(engine._slot(cancelled, research.plan.symbols[0]))
        self.assertIsNotNone(engine._slot(cancelled, research.plan.symbols[1]))
        self.assertEqual(engine.reconcile_cancelled(cancelled, prepared.intents[0].intent_id).state, cancelled)

    def test_partial_exit_and_zero_quantity_unresolved_sell_hold_slot(self):
        research = adapter()
        engine, state = started(research)
        symbol = research.plan.symbols[0]
        state, _ = fill_buy(engine, buy(engine, state, symbol))
        exited = engine._exit(state, state.basket(symbol), START, "trailing_stop")
        intent = exited.intents[0]
        partial = Fill("partial-sell", intent.intent_id, START, intent.quantity / 2, D("100"), D("0.1"),
                       final=False)
        state = engine.apply_fill(exited.state, partial).state
        self.assertIsNotNone(engine._slot(state, symbol))
        # Quantity zero alone does not prove the order is terminal.
        remaining = Fill("remaining-sell", intent.intent_id, START + timedelta(seconds=1),
                         intent.quantity / 2, D("100"), D("0.1"), final=False)
        state = engine.apply_fill(state, remaining).state
        self.assertEqual(state.basket(symbol).quantity, 0)
        self.assertEqual(state.basket(symbol).cycle, 0)
        self.assertIsNotNone(engine._slot(state, symbol))
        reconciled = engine.reconcile_cancelled(state, intent.intent_id).state
        self.assertEqual(reconciled.basket(symbol).cycle, 1)
        self.assertIsNone(engine._slot(reconciled, symbol))
        self.assertEqual(reconciled.cycles[0].fees, exited.state.basket(symbol).costs_spent + D("0.2"))

    def test_normal_exit_reuses_fixed_budget_for_another_coin_and_keeps_paid_fees(self):
        research = adapter()
        engine, state = started(research)
        symbol, other = research.plan.symbols[:2]
        state, entry = fill_buy(engine, buy(engine, state, symbol))
        closed, exit_fill = sell(engine, state, symbol, START + timedelta(seconds=1), price=D("102"))
        self.assertTrue(closed.cycles[0].released)
        self.assertEqual(closed.cycles[0].fees, entry.fee + exit_fill.fee)
        self.assertEqual(closed.spending[0].fees, entry.fee + exit_fill.fee)
        self.assertEqual(closed.cycles[0].principal, entry.quantity * entry.price)
        self.assertIsNone(engine._slot(closed, symbol))
        at = START + timedelta(seconds=2)
        closed = marks(engine, closed, at)
        reopened = buy(engine, closed, other, "new-coin", at)
        self.assertEqual(reopened.intents[0].maximum_quote, research.plan.stages[0])
        evidence = json.loads(reopened.events[-1].reason[len(ADMISSION_PREFIX):])
        self.assertEqual(D(evidence["assessment"]["unused_costs"]), research.plan.slot_costs * 5)
        self.assertEqual(reopened.state.account.cash, closed.account.cash)
        self.assertEqual(engine._slot(reopened.state, other).index, 0)
        self.assertEqual(engine.apply_fill(closed, exit_fill).state, closed)

    def test_same_coin_reentry_requires_two_new_closed_rsi_signals(self):
        research = adapter()
        engine, state = started(research)
        symbol = research.plan.symbols[0]
        state, _ = fill_buy(engine, buy(engine, state, symbol))
        state, _ = sell(engine, state, symbol, START + timedelta(seconds=1))
        state = seeded(state, symbol, D("100"), True)
        first = bar(engine, state, symbol, START, D("100"))
        self.assertFalse(first.intents)
        second = bar(engine, first.state, symbol, START + timedelta(hours=4), D("99"))
        self.assertEqual(second.intents[0].basket_id, symbol + ":1")
        self.assertEqual(second.intents[0].maximum_quote, research.plan.stages[0])
        filled, _ = fill_buy(engine, second, START + timedelta(hours=8), D("99"))
        self.assertGreater(filled.spending[0].principal, filled.basket(symbol).principal_spent)
        self.assertEqual(filled.basket(symbol).completed_regular_stages, 1)

    def test_actual_cash_and_stress_still_gate_reuse(self):
        research = adapter()
        engine, state = started(research)
        symbol, other = research.plan.symbols[:2]
        state, _ = fill_buy(engine, buy(engine, state, symbol))
        state, _ = sell(engine, state, symbol, START + timedelta(seconds=1))
        state = marks(engine, state, START + timedelta(seconds=2))
        reduced = replace(state, account=replace(state.account, cash=D("9500")))
        denied = engine._buy(reduced, other, 1, START + timedelta(seconds=2), "low-headroom")
        self.assertFalse(denied.intents)
        self.assertIn("correlated_stress", denied.events[0].reason)
        self.assertIsNone(engine._slot(denied.state, other))

    def test_risk_exit_is_quarantined_until_explicit_resume(self):
        research = adapter()
        engine, state = started(research)
        symbol = research.plan.symbols[0]
        state, _ = fill_buy(engine, buy(engine, state, symbol))
        state = marks(engine, state, START + timedelta(seconds=1), D("40"))
        state, fills, _ = PaperSimulator(engine, research.costs).settle(
            state, START + timedelta(seconds=1), buys=False)
        self.assertTrue(fills)
        self.assertTrue(engine._slot(state, symbol).quarantined)
        self.assertFalse(state.cycles[0].released)
        self.assertTrue(state.basket(symbol).risk_stopped)
        blocked = engine._buy(state, symbol, 1, START + timedelta(seconds=1), "auto-reopen")
        self.assertEqual(blocked.events[0].reason, "slot_requires_explicit_resume")
        with self.assertRaises(TradingRejected):
            engine.resume_slot(state, 0, START + timedelta(seconds=1), authorization_reference="")
        resumed = engine.resume_slot(state, 0, START + timedelta(seconds=1),
                                     authorization_reference="synthetic-mfa")
        self.assertIsNone(engine._slot(resumed, symbol))
        self.assertFalse(resumed.basket(symbol).risk_stopped)
        self.assertEqual(resumed.basket(symbol).sub30_count, 0)

    def test_account_risk_or_unknown_exit_reason_never_auto_releases(self):
        for reason in ("account_risk", "operator_unclassified_exit"):
            research = adapter()
            engine, state = started(research)
            symbol = research.plan.symbols[0]
            state, _ = fill_buy(engine, buy(engine, state, symbol))
            state, _ = sell(engine, state, symbol, START + timedelta(seconds=1), reason=reason)
            self.assertTrue(engine._slot(state, symbol).quarantined)
            self.assertFalse(state.cycles[0].released)
            halted = replace(state, account=replace(state.account, halted=True))
            with self.assertRaises(TradingRejected):
                engine.resume_slot(halted, 0, START, authorization_reference="synthetic-mfa")

    def test_final_sell_fee_crossing_daily_limit_quarantines_before_release(self):
        research = adapter()
        engine, state = started(research)
        symbol = research.plan.symbols[0]
        state, _ = fill_buy(engine, buy(engine, state, symbol))
        # Current marked equity is just above the daily floor; the final fee
        # crosses it without exhausting the slot's own cost allowance.
        state = replace(state, account=replace(
            state.account, cash=D("9400.1") - state.basket(symbol).quantity * D("100")))
        self.assertGreater(state.equity, D("9400"))
        exited = engine._exit(state, state.basket(symbol), START, "trailing_stop")
        intent = exited.intents[0]
        final = Fill("fee-crossing-limit", intent.intent_id, START,
                     intent.quantity, D("100"), D("0.2"))
        closed = engine.apply_fill(exited.state, final).state
        self.assertEqual(closed.equity, D("9399.9"))
        self.assertTrue(closed.account.halted)
        self.assertIn("daily_loss_limit", closed.account.halt_reasons)
        self.assertTrue(engine._slot(closed, symbol).quarantined)
        self.assertFalse(closed.cycles[0].released)

    def test_shared_dispatch_recheck_cancels_and_releases_unfilled_reservation(self):
        research = adapter()
        engine, state = started(research)
        prepared = buy(engine, state, research.plan.symbols[0])
        state = replace(prepared.state, account=replace(prepared.state.account, cash=D("9500")))
        with self.assertRaises(TradingRejected):
            engine.validate_dispatch(state, prepared.intents[0].intent_id, START)
        state, fills, events = PaperSimulator(engine, research.costs).settle(state, START)
        self.assertFalse(fills)
        self.assertTrue(any("correlated_stress" in e.reason for e in events))
        self.assertEqual(sum(s.symbol is not None for s in state.slots), 0)

    def test_separate_minimum_quantity_and_rounded_minimum_quote_at_dispatch(self):
        for quantity, minimum_quote in ((D("2"), D("0")), (D("0"), D("175.88019535"))):
            research = adapter()
            rules = replace(research.instrument_rules[0], quantity_step=D("0.1"),
                            minimum_quantity=quantity, minimum_quote=minimum_quote)
            research = replace(research, instrument_rules=(rules,) + research.instrument_rules[1:])
            engine, state = started(research)
            prepared = buy(engine, state, research.plan.symbols[0])
            state, fills, events = PaperSimulator(engine, research.costs).settle(prepared.state, START)
            self.assertFalse(fills)
            self.assertTrue(any(e.reason == "rounded_order_below_instrument_minimum" for e in events))
            self.assertIsNone(engine._slot(state, research.plan.symbols[0]))

    def test_five_regular_averaging_stages_and_separate_manual_sixth(self):
        research = adapter()
        engine, state = started(research, D("20000"))
        symbol = research.plan.symbols[0]
        state, _ = fill_buy(engine, buy(engine, state, symbol))
        opened = START
        average = state.basket(symbol).average_price
        for stage in range(2, 6):
            last = state.basket(symbol).last_regular_price
            state = seeded(state, symbol, last, False)
            up = bar(engine, state, symbol, opened, last * D("1.01"))
            self.assertFalse(up.intents)
            down = bar(engine, up.state, symbol, opened + timedelta(hours=4), last * D("0.95"))
            self.assertEqual(down.intents[0].stage, stage)
            self.assertEqual(down.intents[0].maximum_quote, research.plan.stages[stage - 1])
            state, _ = fill_buy(engine, down, opened + timedelta(hours=8), last * D("0.95"))
            self.assertLess(state.basket(symbol).average_price, average)
            average = state.basket(symbol).average_price
            opened += timedelta(hours=8)
        at = opened + timedelta(hours=4)
        state = marks(engine, state, at, state.basket(symbol).last_regular_price * D("0.95"))
        self.assertFalse(state.basket(symbol).manual_used)
        preview = engine.preview_manual(state, symbol, at)
        with self.assertRaises(TradingRejected):
            engine.confirm_manual(state, preview, at, authorization_reference="")
        manual = engine.confirm_manual(state, preview, at, authorization_reference="synthetic-mfa")
        state, _ = fill_buy(engine, manual, at, state.basket(symbol).last_regular_price * D("0.95"))
        self.assertTrue(state.basket(symbol).manual_used)
        self.assertLess(state.basket(symbol).average_price, average)
        self.assertEqual(sum(s.symbol is not None for s in state.slots), 1)

    def test_complete_marks_identity_and_slot_integrity_fail_closed(self):
        research = adapter()
        engine, state = started(research)
        with self.assertRaises(ValueError):
            engine.start("foreign", research.plan.account_id, START)
        with self.assertRaises(ValueError):
            replace(research, instrument_rules=research.instrument_rules[:-1])
        with self.assertRaises(ValueError):
            engine._validate(replace(state, slots=state.slots[:-1]))
        with self.assertRaises(ValueError):
            load_state(dump_state(state))
        stale = replace(state, quotes=state.quotes[:-1])
        self.assertFalse(engine._buy(stale, research.plan.symbols[0], 1, START, "missing").intents)
        changed = replace(state, quotes=(replace(state.quotes[0], observed_at=START - timedelta(seconds=1)),)
                          + state.quotes[1:])
        self.assertFalse(engine._buy(changed, research.plan.symbols[1], 1, START, "mixed").intents)

    def test_bounded_pool_replay_canonical_priority_and_capacity_report(self):
        for capacity in (3, 5):
            research = adapter(capacity)
            bars = tuple(Candle(s, START + timedelta(hours=4*i), START + timedelta(hours=4*(i+1)),
                                D(100-i), D(100-i), D(100-i), D(100-i))
                         for i in range(18) for s in research.plan.symbols)
            result = research.run(bars)
            self.assertEqual(result, research.run(reversed(bars)))
            self.assertEqual(result.version, POOL_VERSION)
            self.assertEqual(result.benchmark_status, "not_computed")
            self.assertEqual(result.validation_status, "not_evaluated")
            self.assertEqual(result.policy_digest, digest(research.policy()))
            self.assertEqual(result.planned_principal, research.plan.slot_principal * capacity)
            self.assertEqual(result.planned_cost_reserve, research.plan.slot_costs * capacity)
            self.assertEqual(result.initially_unassigned_capital, research.plan.remainder)
            self.assertEqual(max(p.active_baskets for p in result.capital_curve), capacity)
            self.assertEqual(max(p.occupied for p in result.occupancy_curve), capacity)
            self.assertEqual(tuple(o.intent.symbol for o in result.simulation.state.orders
                                   if o.intent.side == Side.BUY), research.plan.symbols[:capacity])
            self.assertFalse(result.simulation.manual_fills_fabricated)
            self.assertTrue(all(o.intent.stage != 6 for o in result.simulation.state.orders))
            json.dumps(primitive(result), allow_nan=False)
            with localcontext() as context:
                context.prec = 8
                self.assertEqual(research.run(bars), result)
            with self.assertRaises(ValueError):
                research.run(bars[:-1])

    def test_natural_ohlc_replay_reuses_slots_across_three_rsi_cycles(self):
        research = adapter(count=7)
        prices = ([100] * 15 + list(range(99, 79, -1)) + list(range(80, 111, 2))
                  + list(range(109, 79, -1)) + list(range(80, 111, 2))
                  + list(range(109, 79, -1)))
        bars = tuple(Candle(s, START + timedelta(hours=4*i), START + timedelta(hours=4*(i+1)),
                            D(price), D(price), D(price), D(price))
                     for i, price in enumerate(prices) for s in research.plan.symbols)
        result = research.run(bars)
        state = result.simulation.state
        self.assertEqual(len(state.cycles), 10)
        self.assertTrue(all(c.released and c.exit_reason == "trailing_stop" for c in state.cycles))
        buys = tuple(o for o in state.orders if o.intent.side == Side.BUY)
        self.assertEqual(len(buys), 15)
        self.assertEqual({o.intent.basket_id.split(":")[1] for o in buys}, {"0", "1", "2"})
        self.assertTrue(all(o.intent.stage == 1 for o in buys))
        self.assertTrue(all(o.intent.maximum_quote == research.plan.stages[0] for o in buys))
        self.assertEqual(max(p.occupied for p in result.occupancy_curve), research.plan.capacity)
        self.assertFalse(state.account.halted)
        self.assertFalse(result.simulation.manual_fills_fabricated)
        self.assertEqual(sum(s.fees for s in state.spending),
                         sum(f.fee for f in result.simulation.fills))
