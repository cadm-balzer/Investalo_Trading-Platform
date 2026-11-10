"""Mixed slot budgets retain the original allocator's economic boundaries."""

from dataclasses import FrozenInstanceError, fields, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal, localcontext
import unittest

from investalo_trading.allocation import (
    AllocationPlan, AllocationView, AssetUse, BuyReservation, PurchaseRequest,
    assess_purchase as assess_equal,
)
from investalo_trading.snapshot import digest
from investalo_trading.variable_budget import (
    SlotLimit, VariablePlan, assess_purchase,
)

D = Decimal
AT = datetime(2026, 11, 10, 12, tzinfo=timezone.utc)
DAY = AT.replace(hour=0)


def plan(count=7):
    return VariablePlan(
        "variable-tenant", "variable-account", "frozen-profit-policy", D("10000"),
        D("0.00000001"), D("0.03"),
        tuple(SlotLimit(f"SLOT{i}", D(200 + 100*i), D(5 + i)) for i in range(count)),
    )


def view(p, *, cash=D("10000"), baseline=D("10000")):
    return AllocationView(
        p.tenant_id, p.account_id, p.plan_digest, 0, AT, DAY, baseline, cash,
        tuple(AssetUse(s, D("0"), D("0"), D("0"), D("100"), AT) for s in p.symbols),
    )


def request(p, v, *, symbol=None, principal=D("100"), fee=D("0.1"),
            price=D("100"), intent_id="candidate"):
    return PurchaseRequest(p.tenant_id, p.account_id, p.plan_digest, v.revision,
                           intent_id, symbol or p.symbols[0], principal, fee, price)


def held(v, index=0, *, spent=D("100"), fees=D("1"), quantity=D("1"),
         bid=D("100"), cash=D("9899")):
    asset = replace(v.assets[index], principal_spent=spent, fees_spent=fees,
                    quantity=quantity, first_fill=D("100"), bid=bid)
    return replace(v, cash=cash, assets=v.assets[:index] + (asset,) + v.assets[index+1:])


def pending(p, v, *, symbol=None, amount=D("100"), fee=D("0.1"),
            price=D("100"), status="open"):
    r = request(p, v, symbol=symbol, principal=amount, fee=fee, price=price,
                intent_id="reserved")
    return replace(v, revision=v.revision + 1,
                   reservations=v.reservations + (BuyReservation(r, status),))


class VariableBudgetTests(unittest.TestCase):
    def test_equal_three_and_five_preserve_all_economic_diagnostics(self):
        for count in (3, 5):
            equal = AllocationPlan("variable-tenant", "variable-account",
                                   tuple(f"SLOT{i}" for i in range(count)),
                                   D("10000"), D("0.01"))
            variable = VariablePlan(
                equal.tenant_id, equal.account_id, "equal-comparison", equal.initial_capital,
                equal.quantum, equal.remainder,
                tuple(SlotLimit(s, equal.slot_principal, equal.slot_costs)
                      for s in equal.symbols),
            )
            base = replace(view(variable), plan_digest=equal.plan_digest)
            scenarios = (
                (base, D("100"), 0),
                (base, equal.slot_principal, 0),
                (held(base), D("100"), 1),
                (held(base, bid=D("40"), cash=D("9950")), D("100"), 1),
                (pending(equal, base, amount=D("900")), D("103"), 1),
                (held(base, spent=equal.slot_principal), D("1"), 0),
            )
            for original, amount, index in scenarios:
                with self.subTest(count=count, amount=amount, index=index,
                                  pending=len(original.reservations)):
                    converted = replace(
                        original, plan_digest=variable.plan_digest,
                        reservations=tuple(replace(
                            reservation, request=replace(reservation.request,
                                                         plan_digest=variable.plan_digest))
                            for reservation in original.reservations),
                    )
                    left = assess_equal(equal, original, request(
                        equal, original, symbol=equal.symbols[index], principal=amount), AT)
                    right = assess_purchase(variable, converted, request(
                        variable, converted, symbol=variable.symbols[index], principal=amount), AT)
                    for field in fields(left):
                        if field.name != "view_digest":
                            self.assertEqual(getattr(left, field.name), getattr(right, field.name))

    def test_seven_mixed_slots_use_original_initial_loss_basis(self):
        p = plan()
        v = view(p, cash=D("10500"))
        result = assess_purchase(p, v, request(p, v, symbol=p.symbols[-1]), AT)
        self.assertTrue(result.allowed)
        self.assertEqual(result.unused_costs, D("56"))
        self.assertEqual(result.daily_headroom, D("1100"))
        self.assertEqual(result.initial_headroom, D("1300"))
        self.assertEqual(result.projected_loss, D("106"))

    def test_growth_budgets_do_not_credit_cash_or_change_risk_basis(self):
        p = plan()
        larger = replace(p, limits=tuple(replace(s, principal=s.principal + D("5000"))
                                         for s in p.limits))
        v = view(larger)
        result = assess_purchase(larger, v, request(larger, v, principal=D("5000")), AT)
        self.assertEqual(result.equity, D("10000"))
        self.assertEqual(result.initial_headroom, D("800"))
        self.assertIn("correlated_stress", result.reasons)

    def test_each_slot_principal_and_fee_budget_is_independent(self):
        p = plan()
        v = view(p)
        excess = assess_purchase(p, v, request(p, v, principal=D("200.00000001")), AT)
        self.assertIn("basket_budget", excess.reasons)
        self.assertEqual(excess.maximum_principal, D("200"))
        self.assertTrue(assess_purchase(p, v, request(
            p, v, symbol=p.symbols[1], principal=D("201")), AT).allowed)
        fee = assess_purchase(p, v, request(p, v, fee=D("5.00000001")), AT)
        self.assertIn("fee_budget", fee.reasons)
        self.assertEqual(fee.maximum_principal, 0)
        self.assertTrue(assess_purchase(p, v, request(
            p, v, symbol=p.symbols[1], fee=D("5.00000001")), AT).allowed)

    def test_paid_and_pending_fees_do_not_double_count_cash_or_stress(self):
        p = plan()
        v = held(view(p))
        before = assess_purchase(p, v, request(p, v, symbol=p.symbols[1]), AT)
        self.assertEqual(before.equity, D("9999"))
        self.assertEqual(before.unused_costs, D("55"))
        v = pending(p, v, symbol=p.symbols[1], fee=D("6"))
        after = assess_purchase(p, v, request(p, v, symbol=p.symbols[2]), AT)
        self.assertEqual(after.unused_costs, before.unused_costs)
        self.assertEqual(after.pending_stress, D("50"))
        self.assertEqual(after.projected_loss, before.projected_loss + D("50"))

    def test_pending_reservations_reduce_remaining_slot_and_shared_headroom(self):
        p = plan()
        v = pending(p, view(p), amount=D("190"))
        result = assess_purchase(p, v, request(p, v, principal=D("11")), AT)
        self.assertIn("overlapping_reservation", result.reasons)
        self.assertIn("basket_budget", result.reasons)
        self.assertEqual(result.maximum_principal, 0)
        other = assess_purchase(p, v, request(p, v, symbol=p.symbols[1]), AT)
        self.assertTrue(other.allowed)
        self.assertEqual(other.pending_stress, D("95"))

    def test_cancel_requested_and_unknown_orders_keep_principal_reserved(self):
        p = plan()
        for status in ("unknown", "cancel_requested"):
            with self.subTest(status=status):
                v = pending(p, view(p), status=status)
                result = assess_purchase(p, v, request(p, v, symbol=p.symbols[1]), AT)
                self.assertIn("unresolved_order_outcome", result.reasons)
                self.assertEqual(result.pending_stress, D("50"))
                self.assertEqual(result.maximum_principal, 0)

    def test_existing_spending_and_reserved_fees_cannot_exceed_slot(self):
        p = plan()
        for changes in ({"spent": D("201")}, {"fees": D("5.01")}):
            v = held(view(p), **changes)
            result = assess_purchase(p, v, request(p, v, symbol=p.symbols[1]), AT)
            self.assertIn("existing_budget_overrun", result.reasons)
            self.assertEqual(result.maximum_principal, 0)
        v = pending(p, held(view(p)), amount=D("101"))
        self.assertIn("existing_budget_overrun", assess_purchase(
            p, v, request(p, v, symbol=p.symbols[1]), AT).reasons)
        v = pending(p, held(view(p)), fee=D("4.01"))
        self.assertIn("existing_budget_overrun", assess_purchase(
            p, v, request(p, v, symbol=p.symbols[1]), AT).reasons)

    def test_partial_sale_does_not_replenish_current_cycle_budget(self):
        p = plan()
        for quantity in (D("0.1"), D("0")):
            v = held(view(p), spent=D("200"), quantity=quantity, cash=D("10000"))
            result = assess_purchase(p, v, request(p, v), AT)
            self.assertIn("basket_budget", result.reasons)
            self.assertEqual(result.maximum_principal, 0)

    def test_candidate_and_pending_price_bounds_remain_enforced(self):
        p = plan()
        v = held(view(p))
        self.assertIn("unbounded_purchase_price", assess_purchase(
            p, v, request(p, v, price=D("101")), AT).reasons)
        v = pending(p, v, price=D("101"))
        result = assess_purchase(p, v, request(p, v, symbol=p.symbols[1]), AT)
        self.assertIn("unbounded_pending_price", result.reasons)
        self.assertEqual(result.maximum_principal, 0)

    def test_cash_remainder_and_loss_limits_are_independent_gates(self):
        p = plan()
        v = replace(view(p), day_start_equity=D("1000"), cash=D("100"))
        result = assess_purchase(p, v, request(p, v, principal=D("100")), AT)
        self.assertIn("cash_budget", result.reasons)
        self.assertIn("account_loss_limit", result.reasons)
        p = replace(p, remainder=D("9950"))
        v = view(p)
        result = assess_purchase(p, v, request(p, v, principal=D("1")), AT)
        self.assertIn("cash_budget", result.reasons)
        self.assertNotIn("account_loss_limit", result.reasons)

    def test_freshness_day_revision_and_halt_fail_closed(self):
        p = plan()
        base = view(p)
        cases = (
            (replace(base, as_of=AT-timedelta(seconds=31)), "stale_or_future_view"),
            (replace(base, as_of=AT+timedelta(seconds=1)), "stale_or_future_view"),
            (replace(base, day_started_at=DAY-timedelta(days=1)), "invalid_day_basis"),
            (replace(base, halted=True), "account_halted"),
            (replace(base, revision=1), "stale_revision"),
            (replace(base, assets=(replace(base.assets[0], marked_at=AT-timedelta(seconds=1)),)
                     + base.assets[1:]), "incomplete_mark_batch"),
        )
        r = request(p, base)
        for v, reason in cases:
            with self.subTest(reason=reason):
                result = assess_purchase(p, v, r, AT)
                self.assertIn(reason, result.reasons)
                self.assertEqual(result.maximum_principal, 0)

    def test_identity_complete_exposure_and_committed_pending_bindings(self):
        p = plan()
        v = view(p)
        r = request(p, v)
        for changed in (replace(v, tenant_id="foreign"), replace(v, account_id="foreign"),
                        replace(v, plan_digest="foreign"), replace(v, assets=v.assets[:-1])):
            with self.assertRaises(ValueError):
                assess_purchase(p, changed, r, AT)
        for changed in (replace(r, tenant_id="foreign"), replace(r, account_id="foreign"),
                        replace(r, plan_digest="foreign"), replace(r, symbol="foreign")):
            with self.assertRaises(ValueError):
                assess_purchase(p, v, changed, AT)
        committed = pending(p, v)
        for changes in ({"tenant_id": "foreign"}, {"account_id": "foreign"},
                        {"plan_digest": "foreign"}, {"symbol": "foreign"},
                        {"expected_revision": committed.revision}):
            changed = replace(committed, reservations=(replace(
                committed.reservations[0], request=replace(
                    committed.reservations[0].request, **changes)),))
            with self.assertRaises(ValueError):
                assess_purchase(p, changed, request(p, changed, symbol=p.symbols[1]), AT)

    def test_policy_budget_order_and_context_bind_plan_digest(self):
        p = plan()
        self.assertEqual(p.plan_digest, replace(p, limits=tuple(reversed(p.limits))).plan_digest)
        for changes in (
            {"policy_digest": "another-policy"}, {"initial_equity": D("9000")},
            {"remainder": D("1")}, {"quantum": D("0.0001")},
            {"tenant_id": "another"}, {"account_id": "another"},
            {"limits": (replace(p.limits[0], costs=D("6")),) + p.limits[1:]},
            {"limits": (replace(p.limits[0], principal=D("201")),) + p.limits[1:]},
        ):
            self.assertNotEqual(p.plan_digest, replace(p, **changes).plan_digest)
        with self.assertRaises(FrozenInstanceError):
            p.initial_equity = D("20000")
        v = view(p)
        self.assertEqual(digest(v), digest(replace(v, assets=tuple(reversed(v.assets)))))

    def test_invalid_plan_limits_and_money_are_rejected(self):
        p = plan()
        for changes in (
            {"limits": p.limits[:2]}, {"limits": p.limits + (SlotLimit("SLOT7", D("1"), D("1")),)},
            {"limits": list(p.limits)}, {"limits": ("invalid",) + p.limits[1:]},
            {"limits": (p.limits[0],) + p.limits[:-1]},
            {"initial_equity": D("0")}, {"quantum": D("0")}, {"remainder": D("-1")},
            {"policy_digest": " "},
        ):
            with self.assertRaises(ValueError):
                replace(p, **changes)
        for principal, costs in ((D("0"), D("1")), (D("1"), D("-1")),
                                 (D("NaN"), D("1")), (D("1"), D("Infinity"))):
            with self.assertRaises(ValueError):
                SlotLimit("SLOT", principal, costs)

    def test_exact_stress_boundary_precision_and_decimal_context(self):
        p = replace(plan(), limits=tuple(replace(s, principal=D("2000")) for s in plan().limits))
        v = view(p)
        bound = assess_purchase(p, v, request(p, v), AT).maximum_principal
        self.assertEqual(bound, D("1088"))
        self.assertTrue(assess_purchase(p, v, request(p, v, principal=bound), AT).allowed)
        self.assertIn("correlated_stress", assess_purchase(
            p, v, request(p, v, principal=bound+p.quantum), AT).reasons)
        imprecise = assess_purchase(p, v, request(p, v, principal=D("0.000000001")), AT)
        self.assertIn("principal_precision", imprecise.reasons)
        expected = assess_purchase(p, v, request(p, v, principal=D("123.45678901")), AT)
        with localcontext() as context:
            context.prec = 8
            self.assertEqual(expected, assess_purchase(
                p, v, request(p, v, principal=D("123.45678901")), AT))
