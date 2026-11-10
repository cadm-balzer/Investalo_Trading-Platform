"""Profit grants from actual synthetic fills, fixed risk bases and budget epochs."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext
import json
import unittest

from investalo_trading import (
    Candle, Fill, Quote, Side, TradingRejected, dump_state, load_state,
)
from investalo_trading.models import IndicatorState, floor_step
from investalo_trading.pool_research import PoolInstrumentRules
from investalo_trading.profit_research import (
    CycleBudget, PROFIT_VERSION, ProfitPlan, ProfitResearchSimulator,
)
from investalo_trading.snapshot import digest, primitive

D = Decimal
START = datetime(2026, 11, 1, tzinfo=timezone.utc)


def adapter(capacity=5):
    plan = ProfitPlan("profit-tenant", "profit-account", tuple(f"SYNTH{i}" for i in range(8)),
                      D("10000"), D(".01"), capacity)
    return ProfitResearchSimulator(plan, tuple(PoolInstrumentRules(s, D("0.000000000001"))
                                               for s in plan.symbols))


def marks(engine, state, now, price=D("100")):
    return engine.on_quotes(state, tuple(Quote(s, now, price, price)
                                        for s in engine.config.symbols)).state


def initial(research):
    engine = research.engine()
    return engine, marks(engine, engine.start(research.plan.tenant_id,
                                              research.plan.account_id, START), START)


def purchase(engine, state, symbol, now, stage=1, price=D("100")):
    state = marks(engine, state, now, price)
    proposed = engine._buy(state, symbol, stage, now, now.isoformat())
    assert proposed.intents, proposed.events
    intent = proposed.intents[0]
    engine.validate_dispatch(proposed.state, intent.intent_id, now)
    quantity = floor_step(intent.maximum_quote / price, engine.rules(symbol).quantity_step)
    fill = Fill("buy-" + intent.intent_id, intent.intent_id, now, quantity, price,
                quantity * price * D(".001"))
    return engine.apply_fill(proposed.state, fill).state, intent, fill


def close_cycle(engine, state, symbol, now, exit_price=D("500")):
    state, _, _ = purchase(engine, state, symbol, now)
    exited = engine._exit(state, state.basket(symbol), now + timedelta(seconds=1), "trailing_stop")
    intent = exited.intents[0]
    fill = Fill("sell-" + intent.intent_id, intent.intent_id, now + timedelta(seconds=1),
                intent.quantity, exit_price, intent.quantity * exit_price * D(".001"))
    return engine.apply_fill(exited.state, fill).state


def closures(engine, state, count=3, symbol="SYNTH0", first=0, exit_price=D("500")):
    for index in range(first, first + count):
        state = close_cycle(engine, state, symbol, START + timedelta(seconds=index*3),
                            exit_price=exit_price)
    return state


def grow(engine, state, seconds):
    now = START + timedelta(seconds=seconds)
    state = marks(engine, state, now)
    return engine.evaluate_growth(state, now)


def at_seven(research):
    engine, state = initial(research)
    state = closures(engine, state)
    state = grow(engine, state, 9).state
    state = closures(engine, state, first=4)
    state = grow(engine, state, 21).state
    assert len(state.slots) == 7
    return engine, state


class ProfitResearchTests(unittest.TestCase):
    def test_initial_budget_and_risk_basis_stay_original(self):
        for capacity in (3, 4, 5):
            research = adapter(capacity)
            engine, state = initial(research)
            self.assertEqual(len(state.slots), capacity)
            self.assertEqual(engine.config.initial_equity, D("10000"))
            self.assertEqual(state.account.initial_equity, D("10000"))
            self.assertEqual(state.epochs[0].budget.stages, research.plan.stages)
        with self.assertRaises(ValueError):
            replace(adapter().plan, maximum_capacity=8)
        with self.assertRaises(ValueError):
            replace(adapter().plan, symbols=tuple("ABCDEF"))

    def test_three_closes_and_full_original_budget_are_both_required(self):
        research = adapter()
        engine, state = initial(research)
        state = closures(engine, state, count=2, exit_price=D("1000"))
        self.assertGreater(sum(c.net_pnl for c in state.cycles), research.plan.step)
        self.assertEqual(grow(engine, state, 9).state.epochs, state.epochs)
        engine, state = initial(research)
        state = closures(engine, state, exit_price=D("200"))
        self.assertGreater(sum(c.net_pnl for c in state.cycles), 0)
        self.assertLess(sum(c.net_pnl for c in state.cycles), research.plan.step)
        self.assertEqual(grow(engine, state, 9).state.epochs, state.epochs)

    def test_net_losses_and_all_fees_reduce_surplus(self):
        research = adapter()
        engine, state = initial(research)
        state = close_cycle(engine, state, "SYNTH0", START, D("700"))
        state = close_cycle(engine, state, "SYNTH0", START + timedelta(seconds=3), D("700"))
        state = close_cycle(engine, state, "SYNTH0", START + timedelta(seconds=6), D("1"))
        realized = sum(c.net_pnl for c in state.cycles)
        self.assertLess(realized, research.plan.step)
        self.assertTrue(any(c.net_pnl < 0 for c in state.cycles))
        self.assertEqual(grow(engine, state, 9).state.epochs, state.epochs)
        self.assertEqual(sum(c.fees for c in state.cycles), sum(s.fees for s in state.spending))

    def test_grant_adds_sixth_slot_once_without_crediting_cash(self):
        research = adapter()
        engine, state = initial(research)
        state = closures(engine, state)
        result = grow(engine, state, 9)
        after = result.state
        self.assertEqual(len(after.slots), 6)
        self.assertEqual(after.epochs[-1].allocated_profit, D("2000"))
        self.assertEqual(after.epochs[-1].budget.total, D("2000"))
        self.assertEqual(after.account.cash, state.account.cash)
        self.assertEqual(after.account.initial_equity, D("10000"))
        self.assertEqual(after.account.day_start_equity, state.account.day_start_equity)
        self.assertEqual(engine.evaluate_growth(after, START + timedelta(seconds=9)).state, after)
        self.assertEqual(result.events[0].kind, "profit_etape_granted")
        self.assertEqual(after.epochs[-1].receipts_digest, digest(after.cycles))
        for capacity in (3, 4):
            with self.subTest(capacity=capacity):
                research = adapter(capacity)
                engine, state = initial(research)
                state = closures(engine, state)
                grown = grow(engine, state, 9).state
                self.assertEqual(len(grown.slots), capacity + 1)
                self.assertEqual(grown.epochs[-1].allocated_profit, research.plan.step)
                self.assertEqual(grown.epochs[-1].budget, research.plan.original_budget)

    def test_seven_concurrent_baskets_keep_eighth_candidate_waiting(self):
        research = adapter()
        engine, state = at_seven(research)
        for index in range(7):
            state, _, _ = purchase(engine, state, f"SYNTH{index}",
                                    START + timedelta(seconds=22 + index))
        self.assertEqual(sum(b.quantity > 0 for b in state.baskets), 7)
        self.assertEqual(sum(s.symbol is not None for s in state.slots), 7)
        now = START + timedelta(seconds=29)
        state = marks(engine, state, now)
        denied = engine._buy(state, "SYNTH7", 1, now, "eighth-candidate")
        self.assertFalse(denied.intents)
        self.assertEqual(denied.state, state)
        self.assertIn("no_free_funded_slot", denied.events[0].reason)

    def test_grow_to_seven_then_increase_future_volume(self):
        research = adapter()
        engine, state = at_seven(research)
        state = closures(engine, state, first=8)
        state = grow(engine, state, 33).state
        self.assertEqual(len(state.slots), 7)
        self.assertEqual(state.epochs[-1].allocated_profit, D("6000"))
        self.assertEqual(state.epochs[-1].budget.total, D("2285.71428571"))
        self.assertGreater(state.epochs[-1].budget.stages[0], research.plan.stages[0])
        self.assertEqual(engine._variable_plan(state).remainder, D(".00000003"))
        self.assertEqual(state.account.initial_equity, D("10000"))

    def test_extra_profit_does_not_allow_multiple_grants_for_same_closures(self):
        research = adapter()
        engine, state = initial(research)
        state = closures(engine, state, exit_price=D("1500"))
        self.assertGreater(sum(c.net_pnl for c in state.cycles), D("6000"))
        state = grow(engine, state, 9).state
        self.assertEqual(len(state.slots), 6)
        self.assertEqual(grow(engine, state, 10).state.epochs, state.epochs)
        state = closures(engine, state, first=4, exit_price=D("100"))
        state = grow(engine, state, 21).state
        self.assertEqual(len(state.slots), 7)
        self.assertEqual(state.epochs[-1].closed_count, 6)

    def test_open_cycle_budget_is_frozen_through_new_epoch_and_dispatch(self):
        research = adapter()
        engine, state = at_seven(research)
        state, _, _ = purchase(engine, state, "SYNTH0", START + timedelta(seconds=22))
        frozen = engine._slot(state, "SYNTH0")
        state = closures(engine, state, first=8, symbol="SYNTH1")
        state = grow(engine, state, 33).state
        self.assertEqual(engine._slot(state, "SYNTH0").budget, frozen.budget)
        self.assertEqual(engine._slot(state, "SYNTH0").epoch, frozen.epoch)
        self.assertLess(frozen.budget.total, state.epochs[-1].budget.total)
        self.assertGreater(engine._variable_plan(state).remainder, D("285"))
        state, intent, _ = purchase(engine, state, "SYNTH0", START + timedelta(seconds=34),
                                    stage=2, price=D("95"))
        self.assertEqual(intent.maximum_quote, research.plan.stages[1])
        state, newer, _ = purchase(engine, state, "SYNTH1", START + timedelta(seconds=35))
        self.assertEqual(newer.maximum_quote, state.epochs[-1].budget.stages[0])
        # Mixed reservations include the old slot's own reserve only once.
        self.assertEqual(engine._cycle_budget(state, "SYNTH0")[1], frozen.budget.costs)
        self.assertEqual(engine._cycle_budget(state, "SYNTH1")[1], state.epochs[-1].budget.costs)

    def test_realized_profit_is_not_enough_when_equity_was_lost(self):
        research = adapter()
        engine, state = initial(research)
        state = closures(engine, state)
        changed = replace(state, account=replace(state.account, cash=D("11500")))
        rejected = grow(engine, changed, 9)
        self.assertEqual(len(rejected.state.slots), 5)
        self.assertIn("profit_no_longer_equity_backed", rejected.events[0].reason)

    def test_cash_risk_marks_and_reconciliation_block_grants(self):
        research = adapter()
        engine, state = initial(research)
        state = closures(engine, state)
        now = START + timedelta(seconds=9)
        state = marks(engine, state, now)
        halted = replace(state, account=replace(state.account, halted=True))
        self.assertIn("account_halted", engine.evaluate_growth(halted, now).events[0].reason)
        stale = engine.evaluate_growth(state, now + timedelta(seconds=31))
        self.assertIn("stale_or_future", stale.events[0].reason)
        missing = replace(state, quotes=state.quotes[:-1])
        self.assertFalse(engine.evaluate_growth(missing, now).intents)
        pending = engine._buy(state, "SYNTH1", 1, now, "pending")
        rejected = engine.evaluate_growth(pending.state, now)
        self.assertEqual(len(rejected.state.slots), 5)
        self.assertIn("orders_require_reconciliation", rejected.events[0].reason)
        unknown = engine.mark_order_unknown(pending.state, pending.intents[0].intent_id)
        self.assertIn("orders_require_reconciliation",
                      engine.evaluate_growth(unknown, now).events[0].reason)

    def test_risk_quarantine_blocks_even_when_other_cycles_made_profit(self):
        research = adapter()
        engine, state = initial(research)
        state = closures(engine, state)
        state, _, _ = purchase(engine, state, "SYNTH1", START + timedelta(seconds=9))
        exited = engine._exit(state, state.basket("SYNTH1"), START + timedelta(seconds=10),
                              "account_risk")
        intent = exited.intents[0]
        final = Fill("risk-final", intent.intent_id, START + timedelta(seconds=10),
                     intent.quantity, D("100"), D(".1"))
        state = engine.apply_fill(exited.state, final).state
        result = grow(engine, state, 11)
        self.assertEqual(len(result.state.slots), 5)
        self.assertIn("risk_resume_required", result.events[0].reason)

    def test_equity_backed_profit_still_requires_liquid_cash(self):
        research = adapter()
        engine, state = initial(research)
        state = closures(engine, state)
        state, _, _ = purchase(engine, state, "SYNTH1", START + timedelta(seconds=9))
        now = START + timedelta(seconds=10)
        # Synthetic current account snapshot: most equity is in an open
        # marked holding, while free cash cannot finance a complete etape.
        state = marks(engine, state, now, D("6000"))
        state = replace(state, account=replace(state.account, cash=D("1900")))
        self.assertGreater(state.equity, D("12000"))
        blocked = engine.evaluate_growth(state, now)
        self.assertEqual(len(blocked.state.slots), 5)
        self.assertIn("insufficient_liquid_profit", blocked.events[0].reason)
        self.assertNotIn("profit_no_longer_equity_backed", blocked.events[0].reason)

    def test_correlated_stress_blocks_otherwise_fundable_profit_grant(self):
        research = adapter()
        engine, state = initial(research)
        state = closures(engine, state)
        state, _, _ = purchase(engine, state, "SYNTH1", START + timedelta(seconds=9))
        state = replace(state, account=replace(state.account, day_start_equity=D("12800")))
        now = START + timedelta(seconds=10)
        state = marks(engine, state, now)
        self.assertGreater(state.equity, D("12000"))
        self.assertFalse(engine.risk_reasons(state, now))
        blocked = engine.evaluate_growth(state, now)
        self.assertEqual(len(blocked.state.slots), 5)
        self.assertIn("correlated_stress", blocked.events[0].reason)
        self.assertNotIn("insufficient_liquid_profit", blocked.events[0].reason)

    def test_new_closed_h4_bar_grants_once_and_duplicate_cannot_advance_epoch(self):
        research = adapter()
        engine, state = initial(research)
        state = closures(engine, state)
        at = START + timedelta(hours=4)
        state = marks(engine, state, at)
        bar = Candle("SYNTH1", START, at, D("100"), D("100"), D("100"), D("100"))
        processed = engine.on_bar(state, bar)
        self.assertEqual(len(processed.state.slots), 6)
        self.assertTrue(any(e.kind == "profit_etape_granted" for e in processed.events))
        duplicate = engine.on_bar(processed.state, bar)
        self.assertEqual(duplicate.state, processed.state)
        self.assertFalse(duplicate.events)
        with self.assertRaises(TradingRejected):
            engine.on_bar(processed.state, replace(bar, close=D("99"), low=D("99")))

    def test_raised_budget_uses_all_five_rsi_stages_and_explicit_manual_reserve(self):
        research = adapter()
        engine, state = at_seven(research)
        state = closures(engine, state, first=8)
        state = grow(engine, state, 33).state
        symbol, budget = "SYNTH1", state.epochs[-1].budget
        # Realized synthetic cycles provide headroom; no artificial cash credit.
        state, first, _ = purchase(engine, state, symbol, START + timedelta(seconds=34))
        self.assertEqual(first.maximum_quote, budget.stages[0])
        # Two further real synthetic profit closures supply enough daily
        # headroom for the full manual tranche without another epoch grant.
        state = closures(engine, state, count=2, symbol="SYNTH0", first=12,
                         exit_price=D("1500"))
        opened = START
        previous_average = state.basket(symbol).average_price
        for stage in range(2, 6):
            last = state.basket(symbol).last_regular_price
            basket = replace(state.basket(symbol), indicators=IndicatorState(
                previous_close=last, changes=14, average_gain=D(".01"), average_loss=D(".01")))
            state = replace(state, baskets=tuple(basket if b.symbol == symbol else b
                                                for b in state.baskets))
            for high, price in ((True, last * D("1.01")), (False, last * D(".95"))):
                at = opened + timedelta(hours=4)
                state = marks(engine, state, at, price)
                if at.hour == 0:
                    state = engine.reset_day(state, at)
                bar = Candle(symbol, opened, at, price, price, price, price)
                transition = engine.on_bar(state, bar)
                if high:
                    self.assertFalse(transition.intents)
                    state = transition.state
                else:
                    self.assertEqual(transition.intents[0].maximum_quote, budget.stages[stage - 1])
                    intent = transition.intents[0]
                    engine.validate_dispatch(transition.state, intent.intent_id, at)
                    quantity = floor_step(intent.maximum_quote / price,
                                          engine.rules(symbol).quantity_step)
                    state = engine.apply_fill(transition.state, Fill(
                        "stage-" + intent.intent_id, intent.intent_id, at, quantity, price,
                        quantity * price * D(".001"))).state
                opened += timedelta(hours=4)
            self.assertLess(state.basket(symbol).average_price, previous_average)
            previous_average = state.basket(symbol).average_price
        at = opened + timedelta(hours=4)
        price = state.basket(symbol).last_regular_price * D(".95")
        state = marks(engine, state, at, price)
        preview = engine.preview_manual(state, symbol, at)
        self.assertEqual(preview.maximum_quote, budget.stages[5])
        with self.assertRaises(TradingRejected):
            engine.confirm_manual(state, preview, at, authorization_reference="")
        manual = engine.confirm_manual(state, preview, at, authorization_reference="synthetic-mfa")
        quantity = floor_step(manual.intents[0].maximum_quote / price, engine.rules(symbol).quantity_step)
        state = engine.apply_fill(manual.state, Fill(
            "manual-new-epoch", manual.intents[0].intent_id, at, quantity, price,
            quantity * price * D(".001"))).state
        self.assertTrue(state.basket(symbol).manual_used)
        self.assertLess(state.basket(symbol).average_price, previous_average)

    def test_epoch_receipts_identity_restore_and_decimals_are_bound(self):
        research = adapter()
        engine, state = initial(research)
        state = closures(engine, state)
        expected = grow(engine, state, 9)
        with localcontext() as context:
            context.prec = 8
            self.assertEqual(grow(engine, state, 9), expected)
        epoch = expected.state.epochs[-1]
        with self.assertRaises(ValueError):
            engine._validate(replace(expected.state, epochs=expected.state.epochs[:-1] +
                                     (replace(epoch, allocated_profit=D("4000")),)))
        with self.assertRaises(ValueError):
            engine._validate(replace(expected.state, account=replace(
                expected.state.account, initial_equity=D("12000"))))
        with self.assertRaises(ValueError):
            load_state(dump_state(expected.state))
        json.dumps(primitive(expected), allow_nan=False)

    def test_canonical_h4_replay_has_distinct_version_and_no_fake_growth(self):
        research = adapter()
        prices = [100] * 15 + list(range(99, 79, -1)) + list(range(80, 111, 2)) + list(range(109, 79, -1))
        bars = tuple(Candle(s, START + timedelta(hours=4*i), START + timedelta(hours=4*(i+1)),
                            D(p), D(p), D(p), D(p)) for i, p in enumerate(prices)
                     for s in research.plan.symbols)
        result = research.run(bars)
        self.assertEqual(result, research.run(reversed(bars)))
        self.assertEqual(result.version, PROFIT_VERSION)
        self.assertEqual(result.simulation.strategy_version, PROFIT_VERSION)
        self.assertEqual(result.policy_digest, digest(research.policy()))
        self.assertEqual(result.maximum_capacity, 7)
        self.assertEqual(result.initial_capacity, 5)
        self.assertEqual(result.capacity, 5)
        self.assertEqual(result.allocated_profit, 0)
        self.assertEqual(len(result.budget_epochs), 1)
        self.assertFalse(result.simulation.manual_fills_fabricated)
        self.assertEqual(result.benchmark_status, "not_computed")
        json.dumps(primitive(result), allow_nan=False)
