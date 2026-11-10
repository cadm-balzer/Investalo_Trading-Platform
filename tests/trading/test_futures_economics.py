from __future__ import annotations

from decimal import Decimal, ROUND_DOWN, ROUND_UP, localcontext
import unittest

from investalo_trading.futures_economics import (
    ECONOMICS_VERSION,
    LongPosition,
    MarginSchedule,
    MarginTier,
    funding_payment,
    liquidation_bound,
    net_breakeven,
    realized_pnl,
)

D = Decimal


def position(*, margin: str = "20") -> LongPosition:
    return LongPosition(D("2"), D("100"), D("95"), D(margin))


def schedule() -> MarginSchedule:
    return MarginSchedule((
        MarginTier(D("200"), D("0.05"), D("10")),
        MarginTier(D("1000"), D("0.10"), D("5")),
    ))


class FuturesEconomicsTests(unittest.TestCase):
    def test_version(self) -> None:
        self.assertEqual(ECONOMICS_VERSION, "isolated-usdt-long-economics/1")

    def test_same_nominal_has_no_leverage_pnl_multiplier(self) -> None:
        low_margin = position(margin="20")
        high_margin = position(margin="100")
        self.assertEqual(low_margin.notional(D("110")), D("220"))
        self.assertEqual(low_margin.unrealized_pnl(D("110")), D("20"))
        self.assertEqual(high_margin.unrealized_pnl(D("110")), D("20"))
        self.assertEqual(low_margin.equity(D("110")), D("40"))
        self.assertEqual(high_margin.equity(D("110")), D("120"))

    def test_first_fill_does_not_replace_average_entry(self) -> None:
        self.assertEqual(position().unrealized_pnl(D("95")), D("-10"))

    def test_fees_and_funding_are_booked_outside_position_equity(self) -> None:
        p = position()
        self.assertEqual(p.equity(D("100")), D("20"))
        self.assertEqual(realized_pnl(p, D("100"), D("1"), D("0.01"), D("-2")), D("-5"))
        self.assertEqual(p.equity(D("100")), D("20"))

    def test_full_quantity_close_subtracts_entry_and_exit_costs(self) -> None:
        self.assertEqual(
            realized_pnl(position(), D("110"), D("1"), D("0.01"), D("-2")),
            D("14.8"),
        )

    def test_positive_and_negative_funding_have_opposite_cash_signs(self) -> None:
        self.assertEqual(funding_payment(position(), D("100"), D("0.001")), D("-0.200"))
        self.assertEqual(funding_payment(position(), D("100"), D("-0.001")), D("0.200"))
        self.assertEqual(funding_payment(position(), D("100"), D("0")), D("0"))

    def test_breakeven_reconciles_to_zero_realized_pnl(self) -> None:
        p = position()
        price = net_breakeven(p, D("1"), D("0.01"), D("-2"))
        self.assertLess(abs(price * D("1.98") - D("203")), D("1e-25"))
        self.assertLess(abs(realized_pnl(p, price, D("1"), D("0.01"), D("-2"))), D("1e-30"))

    def test_funding_credit_can_remove_positive_breakeven(self) -> None:
        self.assertEqual(net_breakeven(position(), D("1"), D("0.01"), D("201")), D("0"))

    def test_exact_cap_moves_to_next_tier(self) -> None:
        s = schedule()
        self.assertEqual(s.tier_for(D("199.999")).maintenance_rate, D("0.05"))
        self.assertEqual(s.tier_for(D("200")).maintenance_rate, D("0.10"))
        self.assertEqual(s.margin(D("200")), D("20.00"))

    def test_final_cap_is_outside_coverage(self) -> None:
        with self.assertRaises(ValueError):
            schedule().tier_for(D("1000"))
        with self.assertRaises(ValueError):
            schedule().margin(D("1001"))

    def test_schedule_rejects_invalid_order_and_rates(self) -> None:
        good = MarginTier(D("200"), D("0.05"), D("10"))
        for bad in (
            MarginTier(D("200"), D("0.06"), D("5")),
            MarginTier(D("300"), D("0.04"), D("5")),
            MarginTier(D("300"), D("0.06"), D("11")),
        ):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                MarginSchedule((good, bad))

    def test_schedule_size_and_type_are_bounded(self) -> None:
        with self.assertRaises(ValueError):
            MarginSchedule(())
        with self.assertRaises(ValueError):
            MarginSchedule(tuple(MarginTier(D(i), D("0"), D("1")) for i in range(1, 34)))
        with self.assertRaises(ValueError):
            MarginSchedule(("not a tier",))  # type: ignore[arg-type]

    def test_tier_fields_require_finite_decimal_and_valid_ranges(self) -> None:
        for args in (
            (D("0"), D("0"), D("1")),
            (D("NaN"), D("0"), D("1")),
            (D("100"), D("-0.1"), D("1")),
            (D("100"), D("1"), D("1")),
            (D("100"), D("0"), D("0.9")),
            (100, D("0"), D("1")),
        ):
            with self.subTest(args=args), self.assertRaises(ValueError):
                MarginTier(*args)  # type: ignore[arg-type]

    def test_near_one_maintenance_rate_ignores_caller_rounding(self) -> None:
        near_one = D("0.999999999999999999999")
        with localcontext() as ctx:
            ctx.prec = 2
            ctx.rounding = ROUND_UP
            tier = MarginTier(D("100"), near_one, D("1"))
            self.assertEqual(tier.maintenance_rate, near_one)
            with self.assertRaises(ValueError):
                MarginTier(D("100"), D("1.000000000000000000001"), D("1"))

    def test_position_fields_require_finite_decimal(self) -> None:
        for args in (
            (D("0"), D("1"), D("1"), D("0")),
            (D("1"), D("Infinity"), D("1"), D("0")),
            (D("1"), D("1"), D("NaN"), D("0")),
            (D("1"), D("1"), D("1"), D("-1")),
            (1.0, D("1"), D("1"), D("0")),
        ):
            with self.subTest(args=args), self.assertRaises(ValueError):
                LongPosition(*args)  # type: ignore[arg-type]
        LongPosition(D("1"), D("1"), D("1"), D("0"))

    def test_market_inputs_reject_nonpositive_nonfinite_and_float(self) -> None:
        p = position()
        for mark in (D("0"), D("-1"), D("NaN"), D("Infinity"), 1.0):
            with self.subTest(mark=mark), self.assertRaises(ValueError):
                p.notional(mark)  # type: ignore[arg-type]
            with self.subTest(mark=mark), self.assertRaises(ValueError):
                funding_payment(p, mark, D("0"))  # type: ignore[arg-type]
            with self.subTest(mark=mark), self.assertRaises(ValueError):
                schedule().tier_for(mark)  # type: ignore[arg-type]

    def test_rates_fees_and_funding_reject_invalid_values(self) -> None:
        p = position()
        for rate in (D("1"), D("-1"), D("NaN"), D("Infinity"), 0.01):
            with self.subTest(rate=rate), self.assertRaises(ValueError):
                funding_payment(p, D("100"), rate)  # type: ignore[arg-type]
        for bad in (D("-1"), D("1"), D("NaN"), 0.01):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                realized_pnl(p, D("100"), D("0"), bad, D("0"))  # type: ignore[arg-type]
        for bad in (D("-1"), D("NaN"), 1.0):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                net_breakeven(p, bad, D("0"), D("0"))  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            realized_pnl(p, D("100"), D("0"), D("0"), D("NaN"))

    def test_liquidation_equality_is_unsafe(self) -> None:
        s = MarginSchedule((MarginTier(D("1000"), D("0.1"), D("5")),))
        p = position(margin="40")
        bound = liquidation_bound(p, s, D("0.1"), D("200"))
        self.assertEqual(bound, D("100"))
        self.assertEqual(p.equity(bound), p.notional(bound) * D("0.2"))

    def test_more_posted_margin_lowers_liquidation_bound(self) -> None:
        s = schedule()
        self.assertLess(
            liquidation_bound(position(margin="100"), s, D("0.01"), D("200")),
            liquidation_bound(position(margin="20"), s, D("0.01"), D("200")),
        )
        self.assertEqual(liquidation_bound(position(margin="200"), s, D("0.01"), D("200")), D("0"))

    def test_liquidation_uses_highest_encountered_tier(self) -> None:
        s = schedule()
        self.assertLess(
            abs(liquidation_bound(position(), s, D("0"), D("99")) * D("1.9") - D("180")),
            D("1e-25"),
        )
        self.assertEqual(liquidation_bound(position(), s, D("0"), D("100")), D("100"))

    def test_liquidation_rejects_missing_coverage_or_exhausted_denominator(self) -> None:
        with self.assertRaises(ValueError):
            liquidation_bound(position(), schedule(), D("0"), D("500"))
        s = MarginSchedule((MarginTier(D("1000"), D("0.6"), D("1")),))
        with self.assertRaises(ValueError):
            liquidation_bound(position(), s, D("0.4"), D("200"))

    def test_caller_decimal_context_does_not_change_arithmetic(self) -> None:
        p = LongPosition(D("1.234567890123"), D("101.123456789012"), D("100"), D("12"))
        expected = (p.notional(D("102.345678901234")),
                    funding_payment(p, D("102.345678901234"), D("0.001")),
                    net_breakeven(p, D("0.25"), D("0.001"), D("-0.2")))
        with localcontext() as ctx:
            ctx.prec = 6
            ctx.rounding = ROUND_DOWN
            observed = (p.notional(D("102.345678901234")),
                        funding_payment(p, D("102.345678901234"), D("0.001")),
                        net_breakeven(p, D("0.25"), D("0.001"), D("-0.2")))
        self.assertEqual(observed, expected)


if __name__ == "__main__":
    unittest.main()
