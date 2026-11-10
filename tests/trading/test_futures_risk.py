"""Synthetic collateral snapshots; these are not historical performance claims."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext
import json
import unittest

from investalo_trading.futures_economics import LongPosition, MarginSchedule, MarginTier
from investalo_trading.futures_risk import (
    FuturesAssessment, FuturesBudget, FuturesContract, FuturesExposure, FuturesPlan,
    FuturesPurchase, FuturesView, RISK_VERSION, assess_futures_purchase,
)
from investalo_trading.snapshot import primitive

D = Decimal
NOW = datetime(2026, 11, 1, 12, tzinfo=timezone.utc)


def fixtures(capacity=5, capital="2000", costs="20", cash="10000", day="10000"):
    symbols = tuple(f"SYNTH{i}" for i in range(capacity))
    contracts = tuple(FuturesContract(s, D(".0001"), D(".0001"), D(".01"), D(".001"),
                      D(".001"), MarginSchedule((MarginTier(D("100000"), D(".005"), D("20")),)),
                      "synthetic-assumptions-only") for s in symbols)
    plan = FuturesPlan("tenant", "account", "synthetic-policy", D("10000"), D(".00000001"),
                       D("0"), contracts, tuple(FuturesBudget(s, D(capital), D(costs)) for s in symbols))
    view = FuturesView(plan.tenant_id, plan.account_id, plan.plan_digest, 0, NOW,
                       NOW.replace(hour=0), D(day), D(cash),
                       tuple(FuturesExposure(s, D("100"), NOW) for s in symbols))
    request = FuturesPurchase(plan.tenant_id, plan.account_id, plan.plan_digest, 0,
                              symbols[0], D("1"), D("100"), D("60"), D("10"))
    return plan, view, request


def exposure(view, index=0, **changes):
    return replace(view, exposures=tuple(replace(e, **changes) if i == index else e
                                         for i, e in enumerate(view.exposures)))


class FuturesRiskTests(unittest.TestCase):
    def assess(self, plan, view, request, now=NOW):
        return assess_futures_purchase(plan, view, request, now)

    def test_full_nominal_and_cash_collateral_are_distinct(self):
        plan, view, request = fixtures()
        result = self.assess(plan, view, request)
        self.assertTrue(result.allowed, result.reasons)
        self.assertEqual(result.current_equity, D("10000"))
        self.assertEqual(result.projected_equity, D("9999.9"))
        self.assertEqual(result.unposted_cash_after, D("9939.9"))
        self.assertEqual(result.stress_loss, D("50"))
        self.assertEqual(result.minimum_posted_margin, D("50.30000001"))
        self.assertLess(result.effective_entry_leverage, 2)
        self.assertFalse(result.execution_enabled)
        with self.assertRaises(ValueError):
            replace(result, execution_enabled=True)

    def test_unposted_basket_reserve_cannot_rescue_ten_or_two_times(self):
        plan, view, request = fixtures()
        for setting, collateral in ((D("10"), D("10")), (D("2"), D("50"))):
            with self.subTest(setting=setting):
                rejected = self.assess(plan, view, replace(request, requested_leverage=setting,
                                                         posted_margin=collateral))
                self.assertFalse(rejected.allowed)
                self.assertIn("isolated_stress_liquidation", rejected.reasons)
                self.assertGreater(rejected.remaining_margin_reserve, 9800)
        self.assertTrue(self.assess(plan, view, request).allowed)

    def test_exact_liquidation_surplus_boundary_is_unsafe(self):
        plan, view, request = fixtures()
        unsafe = self.assess(plan, view, replace(request, posted_margin=D("50.3")))
        self.assertIn("isolated_stress_liquidation", unsafe.reasons)
        safe = self.assess(plan, view, replace(request, posted_margin=unsafe.minimum_posted_margin))
        self.assertTrue(safe.allowed, safe.reasons)
        self.assertLess(safe.conservative_liquidation_bound, D("50"))

    def test_adding_margin_never_credits_account_equity(self):
        plan, view, request = fixtures()
        low = self.assess(plan, view, request)
        high = self.assess(plan, view, replace(request, posted_margin=D("100")))
        self.assertEqual(low.projected_equity, high.projected_equity)
        self.assertEqual(low.unposted_cash_after - high.unposted_cash_after, D("40"))
        self.assertEqual(low.remaining_margin_reserve - high.remaining_margin_reserve, D("40"))

    def test_account_stress_exact_boundary_and_other_baskets_count(self):
        plan, view, request = fixtures()
        boundary = self.assess(plan, view, replace(request, quantity=D("10"), posted_margin=D("600")))
        self.assertTrue(boundary.allowed, boundary.reasons)
        self.assertEqual(boundary.stress_loss + boundary.unused_cost_reserve, boundary.headroom)
        too_big = self.assess(plan, view, replace(request, quantity=D("10.0001"), posted_margin=D("600")))
        self.assertIn("correlated_account_stress", too_big.reasons)
        filled = replace(view, unposted_cash=D("9399"), exposures=tuple(
            replace(e, position=LongPosition(D("2"), D("100"), D("100"), D("120")),
                    fees_spent=D(".2")) for e in view.exposures))
        addition = self.assess(plan, filled, replace(request, quantity=D(".0001"), posted_margin=D(".006")))
        self.assertIn("correlated_account_stress", addition.reasons)
        self.assertNotIn("insufficient_unposted_cash", addition.reasons)

    def test_original_initial_basis_is_not_replaced_by_current_capital(self):
        plan, view, request = fixtures(capacity=3, capital="3000", costs="30", cash="9300", day="9000")
        result = self.assess(plan, view, replace(request, quantity=D(".5"), posted_margin=D("30")))
        self.assertEqual(result.headroom, D("99.95"))
        self.assertIn("correlated_account_stress", result.reasons)
        self.assertNotIn("insufficient_unposted_cash", result.reasons)

    def test_daily_basis_cannot_be_reset_by_a_purchase(self):
        plan, view, request = fixtures(day="11000")
        self.assertIn("account_loss_limit", self.assess(plan, view, request).reasons)
        halted = replace(fixtures()[1], halted=True)
        self.assertIn("account_halted", self.assess(plan, halted, request).reasons)

    def test_existing_liquidation_cannot_be_repaired_with_a_new_purchase(self):
        plan, view, request = fixtures()
        unsafe = exposure(view, position=LongPosition(D("1"), D("100"), D("100"), D("1")),
                          mark=D("90"))
        result = self.assess(plan, unsafe, replace(request, maximum_fill_price=D("90")))
        self.assertIn("isolated_position_already_unsafe", result.reasons)

    def test_first_actual_fill_keeps_stress_anchor_after_averaging_down(self):
        plan, view, request = fixtures()
        held = exposure(view, position=LongPosition(D("1"), D("80"), D("100"), D("60")), mark=D("80"))
        held = replace(held, unposted_cash=D("9940"))
        result = self.assess(plan, held, replace(request, maximum_fill_price=D("80"), posted_margin=D("60")))
        self.assertTrue(result.allowed, result.reasons)
        self.assertEqual(result.stress_loss, D("60"))
        self.assertEqual(result.minimum_posted_margin, D("60.60000001"))

    def test_current_mark_below_half_first_fill_is_not_a_profit_in_stress(self):
        plan, view, request = fixtures()
        held = exposure(view, position=LongPosition(D("1"), D("80"), D("100"), D("60")), mark=D("40"))
        held = replace(held, unposted_cash=D("9940"))
        result = self.assess(plan, held, replace(request, maximum_fill_price=D("40")))
        self.assertEqual(result.stress_loss, 0)
        self.assertGreater(result.minimum_posted_margin, 40)
        self.assertFalse(result.execution_enabled)

    def test_lower_fill_bound_cannot_mint_immediate_mark_profit(self):
        plan, view, request = fixtures()
        result = self.assess(plan, view, replace(request, maximum_fill_price=D("80")))
        self.assertFalse(result.allowed)
        self.assertIn("fill_bound_below_mark", result.reasons)

    def test_unposted_cash_backs_all_slot_and_fee_reservations(self):
        plan, view, request = fixtures(cash="9900")
        result = self.assess(plan, view, request)
        self.assertIn("insufficient_unposted_cash", result.reasons)
        plan = replace(plan, remainder=D(".01"))
        view = replace(fixtures()[1], plan_digest=plan.plan_digest)
        request = replace(request, plan_digest=plan.plan_digest)
        self.assertIn("insufficient_unposted_cash", self.assess(plan, view, request).reasons)

    def test_mixed_seven_budgets_use_each_own_cash_and_cost_limit(self):
        plan, view, request = fixtures(capacity=7, capital="2000", cash="15000", day="15000")
        plan = replace(plan, budgets=(replace(plan.budgets[0], capital=D("2500")),) + plan.budgets[1:])
        view = replace(view, plan_digest=plan.plan_digest)
        request = replace(request, plan_digest=plan.plan_digest)
        accepted = self.assess(plan, view, request)
        self.assertTrue(accepted.allowed, accepted.reasons)
        self.assertEqual(accepted.remaining_margin_reserve, D("14300"))
        oversized = self.assess(plan, view, replace(request, posted_margin=D("2481")))
        self.assertIn("basket_capital_or_cost_limit", oversized.reasons)

    def test_already_booked_fees_are_not_debited_twice(self):
        plan, view, request = fixtures()
        held = exposure(view, position=LongPosition(D("1"), D("100"), D("100"), D("60")), fees_spent=D("2"))
        held = replace(held, unposted_cash=D("9938"))
        result = self.assess(plan, held, request)
        self.assertEqual(result.current_equity, D("9998"))
        self.assertEqual(result.projected_equity, D("9997.9"))
        self.assertEqual(result.unused_cost_reserve, D("97.9"))

    def test_cost_and_total_margin_budgets_are_separate(self):
        plan, view, request = fixtures()
        fees = exposure(view, fees_spent=D("20"))
        self.assertIn("basket_capital_or_cost_limit", self.assess(plan, fees, request).reasons)
        margin = self.assess(plan, view, replace(request, posted_margin=D("1981")))
        self.assertIn("basket_capital_or_cost_limit", margin.reasons)

    def test_unresolved_orders_and_pending_margin_block_account(self):
        plan, view, request = fixtures()
        for index in (0, 4):
            pending = exposure(view, index, pending_margin=D("20"), unresolved_order=True)
            result = self.assess(plan, pending, request)
            self.assertIn("orders_require_reconciliation", result.reasons)
        with self.assertRaises(ValueError):
            replace(view.exposures[0], pending_margin=D("20"))

    def test_missing_margin_coverage_and_leverage_tiers_fail_closed(self):
        plan, view, request = fixtures()
        for schedule, reason in (
            (MarginSchedule((MarginTier(D("99"), D(".005"), D("20")),)), "missing_or_invalid_margin_coverage"),
            (MarginSchedule((MarginTier(D("1000"), D(".005"), D("5")),)), "contract_leverage_limit"),
        ):
            changed = replace(plan, contracts=(replace(plan.contracts[0], schedule=schedule),) + plan.contracts[1:])
            result = self.assess(changed, replace(view, plan_digest=changed.plan_digest),
                                  replace(request, plan_digest=changed.plan_digest))
            self.assertIn(reason, result.reasons)

    def test_initial_margin_uses_worst_covered_nominal(self):
        plan, view, request = fixtures()
        result = self.assess(plan, view, replace(request, maximum_fill_price=D("101"),
                                                requested_leverage=D("2"), posted_margin=D("50")))
        self.assertIn("initial_margin_requirement", result.reasons)
        self.assertEqual(result.projected_equity, D("9998.899"))

    def test_quote_and_day_freshness_revision_and_mark_batch(self):
        plan, view, request = fixtures()
        for changed, reason in (
            (replace(view, revision=1), "stale_revision"),
            (replace(view, as_of=NOW - timedelta(seconds=31)), "stale_or_future_marks"),
            (replace(view, as_of=NOW + timedelta(seconds=1)), "stale_or_future_marks"),
            (replace(view, day_started_at=NOW - timedelta(days=1)), "invalid_day_basis"),
            (exposure(view, marked_at=NOW - timedelta(seconds=1)), "incomplete_mark_batch"),
        ):
            self.assertIn(reason, self.assess(plan, changed, request).reasons)

    def test_tenant_account_complete_exposure_and_plan_digests_are_bound(self):
        plan, view, request = fixtures()
        for changed in (replace(view, tenant_id="other"), replace(view, account_id="other"),
                        replace(view, exposures=tuple(reversed(view.exposures)))):
            with self.assertRaises(ValueError):
                self.assess(plan, changed, request)
        with self.assertRaises(ValueError):
            self.assess(plan, view, replace(request, symbol="OUTSIDE"))
        change = replace(plan, contracts=(replace(plan.contracts[0], assumptions_digest="different"),) + plan.contracts[1:])
        self.assertNotEqual(change.plan_digest, plan.plan_digest)
        with self.assertRaises(ValueError):
            self.assess(change, view, request)

    def test_quantity_minimum_and_numeric_input_validation(self):
        plan, view, request = fixtures()
        self.assertIn("invalid_quantity_step", self.assess(plan, view, replace(request, quantity=D(".00001"))).reasons)
        self.assertIn("below_contract_minimum", self.assess(plan, view, replace(request, quantity=D(".00001"))).reasons)
        for field, value in (("quantity", D("NaN")), ("posted_margin", D("Infinity")),
                             ("quantity", 1.0), ("requested_leverage", D("11")),
                             ("requested_leverage", D("1"))):
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                replace(request, **{field: value})
        with self.assertRaises(ValueError):
            replace(view, halted=1)

    def test_decimal_context_immutable_replay_and_safe_record(self):
        plan, view, request = fixtures()
        expected = self.assess(plan, view, request)
        with localcontext() as context:
            context.prec = 8
            self.assertEqual(self.assess(plan, view, request), expected)
        self.assertIsInstance(expected, FuturesAssessment)
        self.assertEqual(RISK_VERSION, "isolated-usdt-long-stress/1")
        self.assertEqual(view.unposted_cash, D("10000"))
        json.dumps(primitive(expected), allow_nan=False)
