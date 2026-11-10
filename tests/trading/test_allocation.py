"""Economic boundaries and fail-closed evidence for the offline proposal."""

from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext
import unittest

from investalo_trading.allocation import (
    AllocationPlan, AllocationView, AssetUse, BuyReservation, PurchaseRequest,
    assess_purchase, reserve_purchase,
)
from investalo_trading.snapshot import digest

D = Decimal
AT = datetime(2026, 11, 10, 12, tzinfo=timezone.utc)
DAY = AT.replace(hour=0)


def plan(count=5, **kwargs):
    return AllocationPlan("tenant-test", "account-test", tuple(f"ASSET{i}" for i in range(count)),
                          kwargs.get("initial_capital", D("10000")),
                          kwargs.get("cost_ratio", D("0.01")),
                          kwargs.get("quantum", D("0.00000001")))


def view(p):
    return AllocationView(p.tenant_id, p.account_id, p.plan_digest, 0, AT, DAY,
                          p.initial_capital, p.initial_capital,
                          tuple(AssetUse(s, D("0"), D("0"), D("0"), D("100"), AT)
                                for s in p.symbols))


def request(p, v, symbol=None, principal="100", **kwargs):
    return PurchaseRequest(p.tenant_id, p.account_id, p.plan_digest, v.revision,
                           kwargs.get("intent_id", f"intent-{symbol or p.symbols[0]}"),
                           symbol or p.symbols[0], D(principal), kwargs.get("fee", D("0.1")),
                           kwargs.get("price", D("100")))


def held(v, index=0, **kwargs):
    a = replace(v.assets[index], principal_spent=kwargs.get("spent", D("500")),
                quantity=kwargs.get("quantity", D("5")), first_fill=D("100"),
                fees_spent=kwargs.get("fees", D("0")), bid=kwargs.get("bid", D("100")))
    return replace(v, assets=v.assets[:index] + (a,) + v.assets[index + 1:],
                   cash=kwargs.get("cash", D("9500")))


class AllocationTests(unittest.TestCase):
    def test_equal_plans_conserve_money_and_keep_manual_reserve(self):
        for count in (3, 4, 5):
            with self.subTest(count=count):
                p = plan(count)
                self.assertEqual(count * (p.slot_principal + p.slot_costs) + p.remainder,
                                 p.initial_capital)
                self.assertGreaterEqual(p.slot_costs, p.slot_principal * p.cost_ratio)
                self.assertLess(p.remainder, count * p.quantum)
                self.assertLessEqual(sum(p.stages), p.slot_principal)
                self.assertLess(p.slot_principal - sum(p.stages), 6 * p.quantum)
                self.assertGreater(p.stages[5], p.stages[4])
                self.assertAlmostEqual(p.stages[5] / p.slot_principal, D("0.2710556"), places=6)
        self.assertEqual(plan().slot_principal, D("1980.19801980"))
        self.assertEqual(plan(3).slot_principal, D("3300.33003300"))

    def test_digest_binds_policy_context_and_canonical_asset_order(self):
        p = plan()
        self.assertEqual(p.plan_digest, replace(p, symbols=tuple(reversed(p.symbols))).plan_digest)
        for change in ({"tenant_id": "another"}, {"account_id": "another"},
                       {"cost_ratio": D("0.02")}, {"quantum": D("0.01")}):
            with self.subTest(change=change):
                self.assertNotEqual(p.plan_digest, replace(p, **change).plan_digest)
        v = view(p)
        self.assertEqual(digest(v), digest(replace(v, assets=tuple(reversed(v.assets)))))
        with self.assertRaises(FrozenInstanceError):
            p.cost_ratio = D("0.02")

    def test_full_planning_does_not_authorize_full_principal(self):
        p = plan()
        v = view(p)
        result = assess_purchase(p, v, request(p, v, principal=str(p.slot_principal)), AT)
        self.assertFalse(result.allowed)
        self.assertEqual(result.daily_headroom, D("600"))
        self.assertEqual(result.initial_headroom, D("800"))
        self.assertEqual(result.maximum_principal, D("1001.980198"))
        self.assertEqual(result.reasons, ("correlated_stress",))

    def test_exact_risk_boundary_and_one_quantum_excess(self):
        p = plan()
        v = view(p)
        cap = assess_purchase(p, v, request(p, v), AT).maximum_principal
        self.assertTrue(assess_purchase(p, v, request(p, v, principal=str(cap)), AT).allowed)
        result = assess_purchase(p, v, request(p, v, principal=str(cap + p.quantum)), AT)
        self.assertFalse(result.allowed)
        self.assertIn("correlated_stress", result.reasons)

    def test_all_first_stages_fit_and_share_reservations(self):
        for count in (3, 4, 5):
            p = plan(count)
            v = view(p)
            old = v
            for symbol in p.symbols:
                v = reserve_purchase(p, v, request(p, v, symbol, str(p.stages[0])), AT)
            self.assertEqual(v.revision, count)
            self.assertEqual(len(v.reservations), count)
            self.assertEqual(old.reservations, ())
            result = assess_purchase(p, v, request(p, v), AT)
            self.assertFalse(result.allowed)
            self.assertIn("overlapping_reservation", result.reasons)
            self.assertEqual(result.maximum_principal, 0)

    def test_two_different_assets_compete_for_same_headroom(self):
        p = plan()
        v = view(p)
        v = reserve_purchase(p, v, request(p, v, principal="900"), AT)
        result = assess_purchase(p, v, request(p, v, p.symbols[1], "103"), AT)
        self.assertEqual(result.pending_stress, D("450"))
        self.assertEqual(result.maximum_principal, D("101.980198"))
        self.assertIn("correlated_stress", result.reasons)

    def test_paid_and_pending_fees_are_not_counted_twice(self):
        p = plan()
        v = held(view(p), fees=D("1"), cash=D("9499"))
        r = request(p, v, p.symbols[1], fee=D("10"))
        result = assess_purchase(p, v, r, AT)
        self.assertEqual(result.equity, D("9999"))
        self.assertEqual(result.unused_costs, D("98.009901"))
        self.assertEqual(result.projected_loss, D("398.009901"))
        reserved = reserve_purchase(p, v, r, AT)
        next_result = assess_purchase(p, reserved, request(p, reserved, p.symbols[2]), AT)
        self.assertEqual(next_result.unused_costs, result.unused_costs)
        self.assertEqual(next_result.projected_loss, result.projected_loss + D("50"))

    def test_stress_sums_positive_asset_losses_without_offsets(self):
        p = plan()
        v = held(view(p), bid=D("40"))
        v = held(v, index=1, bid=D("110"), cash=D("9350"))
        result = assess_purchase(p, v, request(p, v, p.symbols[2]), AT)
        self.assertEqual(result.equity, D("10100"))
        self.assertEqual(result.holding_stress, D("300"))
        self.assertTrue(result.allowed)

    def test_first_reference_price_bounds_for_candidate_and_pending(self):
        p = plan()
        v = held(view(p))
        self.assertTrue(assess_purchase(p, v, request(p, v), AT).allowed)
        result = assess_purchase(p, v, request(p, v, price=D("100.0001")), AT)
        self.assertIn("unbounded_purchase_price", result.reasons)
        pending = BuyReservation(request(p, v, price=D("101")))
        v = replace(v, revision=1, reservations=(pending,))
        result = assess_purchase(p, v, request(p, v, p.symbols[1]), AT)
        self.assertIn("unbounded_pending_price", result.reasons)
        self.assertEqual(result.maximum_principal, 0)

    def test_partial_sales_never_replenish_lifetime_principal(self):
        p = plan()
        v = held(view(p), spent=p.slot_principal, quantity=D("0.1"), cash=D("9990"))
        result = assess_purchase(p, v, request(p, v), AT)
        self.assertIn("basket_budget", result.reasons)
        self.assertEqual(result.maximum_principal, 0)
        v = held(v, spent=p.slot_principal, quantity=D("0"), cash=D("10000"))
        self.assertIn("basket_budget", assess_purchase(p, v, request(p, v), AT).reasons)

    def test_budget_and_cash_are_independent_caps(self):
        p = plan()
        v = held(view(p), spent=p.slot_principal - D("20"), quantity=D("0.01"),
                 cash=D("9999"))
        self.assertEqual(assess_purchase(p, v, request(p, v), AT).maximum_principal, D("20"))
        v = held(view(p), quantity=D("99"), cash=D("100"))
        result = assess_purchase(p, v, request(p, v, p.symbols[1], "10"), AT)
        self.assertIn("cash_budget", result.reasons)
        self.assertEqual(result.maximum_principal, 0)

    def test_fee_budget_and_existing_overruns_fail_closed(self):
        p = plan()
        v = view(p)
        invalid_fee = assess_purchase(p, v, request(p, v, fee=p.slot_costs + D("0.01")), AT)
        self.assertIn("fee_budget", invalid_fee.reasons)
        self.assertEqual(invalid_fee.maximum_principal, 0)
        for change in ({"spent": p.slot_principal + D("1")}, {"fees": p.slot_costs + D("1")}):
            v = held(view(p), **change)
            result = assess_purchase(p, v, request(p, v, p.symbols[1]), AT)
            self.assertIn("existing_budget_overrun", result.reasons)
            self.assertEqual(result.maximum_principal, 0)

    def test_pending_budget_overrun_denies_other_asset(self):
        p = plan()
        v = view(p)
        for change in ({"principal": p.slot_principal + D("1")},
                       {"estimated_fee": p.slot_costs + D("1")}):
            pending = BuyReservation(replace(request(p, v), **change))
            changed = replace(v, revision=1, reservations=(pending,))
            result = assess_purchase(p, changed, request(p, changed, p.symbols[1]), AT)
            self.assertIn("existing_budget_overrun", result.reasons)
            self.assertEqual(result.maximum_principal, 0)

    def test_rounding_remainder_is_not_spendable_cash(self):
        p = plan(3, quantum=D("1"))
        self.assertEqual(p.remainder, D("1"))
        v = held(view(p), quantity=D("10000"), bid=D("1"), cash=D("1"))
        v = replace(v, assets=tuple(replace(a, fees_spent=p.slot_costs) for a in v.assets))
        result = assess_purchase(p, v, request(p, v, principal="1", fee=D("0")), AT)
        self.assertEqual(result.maximum_principal, 0)
        self.assertEqual(result.reasons, ("cash_budget",))
        v = replace(v, cash=D("2"))
        self.assertTrue(assess_purchase(p, v, request(p, v, principal="1", fee=D("0")), AT).allowed)

    def test_initial_basis_is_not_peak_equity_and_daily_basis_is_separate(self):
        p = plan()
        v = replace(view(p), cash=D("9250"), day_start_equity=D("9500"))
        result = assess_purchase(p, v, request(p, v), AT)
        self.assertEqual(result.initial_headroom, D("50"))
        self.assertEqual(result.daily_headroom, D("320"))
        self.assertIn("correlated_stress", result.reasons)
        for cash, basis in (("9200", "9500"), ("9400", "10000")):
            v = replace(view(p), cash=D(cash), day_start_equity=D(basis))
            self.assertIn("account_loss_limit", assess_purchase(p, v, request(p, v), AT).reasons)

    def test_stale_future_marks_day_and_halt_deny(self):
        p = plan()
        v = view(p)
        for now, change, reason in (
            (AT + timedelta(seconds=31), {}, "stale_or_future_view"),
            (AT - timedelta(seconds=1), {}, "stale_or_future_view"),
            (AT, {"day_started_at": DAY - timedelta(days=1)}, "invalid_day_basis"),
            (AT, {"day_started_at": DAY + timedelta(seconds=1)}, "invalid_day_basis"),
            (AT, {"halted": True}, "account_halted"),
            (AT, {"assets": (replace(v.assets[0], marked_at=AT - timedelta(seconds=1)),)
                           + v.assets[1:]}, "incomplete_mark_batch"),
        ):
            with self.subTest(reason=reason):
                changed = replace(v, **change)
                result = assess_purchase(p, changed, request(p, changed), now)
                self.assertIn(reason, result.reasons)
                self.assertEqual(result.maximum_principal, 0)
        self.assertTrue(assess_purchase(p, v, request(p, v), AT + timedelta(seconds=30)).allowed)

    def test_context_completeness_and_reservation_binding(self):
        p = plan()
        v = view(p)
        r = request(p, v)
        for change in ({"tenant_id": "foreign"}, {"account_id": "foreign"},
                       {"plan_digest": "foreign"}, {"assets": v.assets[:-1]}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                assess_purchase(p, replace(v, **change), r, AT)
        for change in ({"tenant_id": "foreign"}, {"account_id": "foreign"},
                       {"plan_digest": "foreign"}, {"symbol": "foreign"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                assess_purchase(p, v, replace(r, **change), AT)
        for change in ({}, {"tenant_id": "foreign"}, {"account_id": "foreign"},
                       {"plan_digest": "foreign"}, {"symbol": "foreign"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                assess_purchase(p, replace(v, reservations=(BuyReservation(replace(r, **change)),)),
                                request(p, v, p.symbols[1]), AT)
        with self.assertRaises(ValueError):
            replace(v, assets=v.assets + (v.assets[0],))

    def test_replay_overlap_and_unknown_outcomes_cannot_authorize_buys(self):
        p = plan()
        v = view(p)
        r = request(p, v)
        reserved = reserve_purchase(p, v, r, AT)
        with self.assertRaisesRegex(ValueError, "stale_revision"):
            reserve_purchase(p, reserved, r, AT)
        for status in ("unknown", "cancel_requested"):
            pending = replace(reserved.reservations[0], status=status)
            changed = replace(reserved, reservations=(pending,))
            result = assess_purchase(p, changed, request(p, changed, p.symbols[1]), AT)
            self.assertIn("unresolved_order_outcome", result.reasons)
            self.assertEqual(result.pending_stress, D("50"))
            self.assertEqual(result.maximum_principal, 0)
        reused = request(p, reserved, p.symbols[1], intent_id=r.intent_id)
        self.assertIn("overlapping_reservation", assess_purchase(p, reserved, reused, AT).reasons)
        with self.assertRaises(ValueError):
            replace(reserved, reservations=reserved.reservations * 2)
        with self.assertRaises(ValueError):
            replace(reserved, reservations=reserved.reservations + (
                BuyReservation(replace(r, intent_id="another")),))

    def test_decimal_context_independence_and_off_quantum_rejection(self):
        p = plan()
        v = view(p)
        r = request(p, v)
        expected = assess_purchase(p, v, r, AT)
        with localcontext() as context:
            context.prec = 6
            low_precision_plan = plan()
            self.assertEqual(low_precision_plan.plan_digest, p.plan_digest)
            self.assertEqual(assess_purchase(low_precision_plan, v, r, AT), expected)
            self.assertEqual(low_precision_plan.stages, p.stages)
        result = assess_purchase(p, v, request(p, v, principal="1.000000001"), AT)
        self.assertIn("principal_precision", result.reasons)
        with self.assertRaises(ValueError):
            reserve_purchase(p, v, request(p, v, principal="2000"), AT)

    def test_invalid_inputs_fail_before_money_calculation(self):
        p = plan()
        for change in ({"symbols": ("A", "B")}, {"symbols": ("A", "A", "B")},
                       {"initial_capital": D("NaN")}, {"cost_ratio": D("Infinity")},
                       {"quantum": D("0")}, {"quantum": D("100000")},
                       {"cost_ratio": D("1")}, {"tenant_id": ""}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                replace(p, **change)
        v = view(p)
        for change in ({"revision": True}, {"cash": D("-1")}, {"halted": 1},
                       {"as_of": AT.replace(tzinfo=None)}, {"assets": list(v.assets)}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                replace(v, **change)
        with self.assertRaises(ValueError):
            replace(v.assets[0], quantity=D("1"))
        with self.assertRaises(ValueError):
            BuyReservation(request(p, v), "complete")
