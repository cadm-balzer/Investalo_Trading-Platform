"""Offline broker-reference boundaries; no live order or private account."""
from dataclasses import replace
from decimal import Decimal, localcontext
from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib
import json
import unittest
from unittest.mock import patch

from investalo_marketdata.futures_broker_calibration import (
    MAX_BYTES, SYMBOLS, URL, bounded_limit_quantity, capture_contracts,
    classic_long_opening_loss, fetch_contracts, floor_grid, parse_contracts, quantity_grid_probe,
)

D = Decimal


def response():
    return {"code": "00000", "requestTime": 1794574252565, "data": [{
        "symbol": symbol, "baseCoin": symbol[:-4], "quoteCoin": "USDT",
        "symbolType": "perpetual", "supportMarginCoins": ["USDT"],
        "symbolStatus": "normal", "volumePlace": "0", "pricePlace": "1",
        "priceEndStep": "5", "sizeMultiplier": "1", "minTradeNum": "1",
        "minTradeUSDT": "5", "maxMarketOrderQty": "10", "maxOrderQty": "100",
        "makerFeeRate": "0.0002", "takerFeeRate": "0.0006",
        "openCostUpRatio": "0.01", "feeRateUpRatio": "0.005",
        "minLever": "1", "maxLever": "50",
    } for symbol in SYMBOLS]}


def payload(value=None):
    return json.dumps(response() if value is None else value).encode()


class FuturesBrokerCalibrationTests(unittest.TestCase):
    def test_non_decimal_power_tick_and_explicit_venue_leverage(self):
        rules = parse_contracts(payload())
        self.assertEqual(tuple(r.symbol for r in rules), SYMBOLS)
        self.assertEqual(rules[0].price_tick, D(".5"))
        self.assertEqual(rules[0].quantity_step, D(1))
        self.assertEqual(rules[0].min_leverage, D(1))
        self.assertEqual(rules[0].record()["taker_fee_rate"], "0.0006")

    def test_wrong_wallet_product_identity_and_status_rejected(self):
        for key, value in (
            ("quoteCoin", "USDC"), ("baseCoin", "BTC"), ("symbolType", "delivery"),
            ("supportMarginCoins", ["USDT", "BTC"]), ("symbolStatus", "unknown"),
        ):
            with self.subTest(key=key):
                data = response()
                data["data"][0][key] = value
                with self.assertRaises(ValueError):
                    parse_contracts(payload(data))

    def test_incomplete_duplicate_error_and_oversized_sources_rejected(self):
        for mode in ("missing", "duplicate", "error"):
            with self.subTest(mode=mode):
                data = response()
                if mode == "missing":
                    data["data"].pop()
                elif mode == "duplicate":
                    data["data"].append(data["data"][0])
                else:
                    data["code"] = "40000"
                with self.assertRaises(ValueError):
                    parse_contracts(payload(data))
        with self.assertRaises(ValueError):
            parse_contracts(b" " * (MAX_BYTES + 1))
        with self.assertRaises(ValueError):
            parse_contracts(b'{"code":"00000","code":"00000","data":[]}')

    def test_no_defaults_or_float_nan_boolean_precision(self):
        for key, value in (
            ("minTradeUSDT", None), ("sizeMultiplier", 0.1), ("takerFeeRate", "NaN"),
            ("pricePlace", True), ("volumePlace", "99"), ("priceEndStep", "0.5"),
            ("maxLever", "1.5"), ("maxOrderQty", "0.1"),
        ):
            with self.subTest(key=key):
                data = response()
                data["data"][0][key] = value
                with self.assertRaises(ValueError):
                    parse_contracts(payload(data))
        data = response()
        del data["data"][0]["feeRateUpRatio"]
        with self.assertRaises(ValueError):
            parse_contracts(payload(data))

    def test_quantity_multiplier_must_fit_volume_precision(self):
        data = response()
        data["data"][0].update(sizeMultiplier="0.25", volumePlace="1")
        with self.assertRaises(ValueError):
            parse_contracts(payload(data))
        data["data"][0]["volumePlace"] = "2"
        rules = parse_contracts(payload(data))
        self.assertEqual(rules[0].quantity_step, D(".25"))

    def test_floor_is_multiple_and_ignores_ambient_precision(self):
        with localcontext() as context:
            context.prec = 4
            self.assertEqual(floor_grid(D("123456789.12345678"), D(".25")),
                             D("123456789"))
            self.assertEqual(floor_grid(D(".999999999999999999"), D("1")), D(0))

    def test_limit_quantity_never_rounds_budget_or_price_up(self):
        rules = parse_contracts(payload())[0]
        self.assertEqual(bounded_limit_quantity(
            rules, notional_cap=D("19.999999999"), limit_price=D(5)), D(3))
        self.assertEqual(bounded_limit_quantity(
            rules, notional_cap=D(20), limit_price=D(5)), D(4))
        with self.assertRaises(ValueError):
            bounded_limit_quantity(rules, notional_cap=D(20), limit_price=D("5.2"))

    def test_minimum_maximum_and_disabled_openings(self):
        rules = parse_contracts(payload())[0]
        self.assertEqual(bounded_limit_quantity(
            rules, notional_cap=D("4.999"), limit_price=D(5)), D(0))
        self.assertEqual(bounded_limit_quantity(
            rules, notional_cap=D(5), limit_price=D(5)), D(1))
        # Limit and market maximums differ: this function sizes LIMIT only.
        self.assertEqual(bounded_limit_quantity(
            rules, notional_cap=D(10000), limit_price=D(5)), D(100))
        for status in ("maintain", "limit_open", "restrictedAPI", "off"):
            with self.subTest(status=status), self.assertRaises(ValueError):
                bounded_limit_quantity(replace(rules, status=status),
                                       notional_cap=D(20), limit_price=D(5))

    def test_xrp_repeating_division_stays_below_cap_with_low_caller_precision(self):
        rules = replace(parse_contracts(payload())[-1], price_tick=D(".0001"),
                        max_limit_quantity=D(100000))
        with localcontext() as context:
            context.prec = 4
            quantity = bounded_limit_quantity(
                rules, notional_cap=D("351.76039070"), limit_price=D(".4549"))
        self.assertEqual(quantity, D(773))
        self.assertLessEqual(quantity * D(".4549"), D("351.76039070"))

    def test_long_opening_loss_sign_and_margin_coin_conversion(self):
        args = dict(quantity=D(2), order_price=D(100), margin_coin_index=D(1))
        self.assertEqual(classic_long_opening_loss(**args, mark_price=D(101)), D(0))
        self.assertEqual(classic_long_opening_loss(**args, mark_price=D(100)), D(0))
        self.assertEqual(classic_long_opening_loss(**args, mark_price=D(99)), D(2))
        args["margin_coin_index"] = D(2)
        self.assertEqual(classic_long_opening_loss(**args, mark_price=D(99)), D(1))

    def test_quantity_probe_covers_small_rest_without_cash_credit(self):
        row = dict(symbol="BINANCE:XRPUSDT", execution_enabled=False,
                   quantity="10.25", frozen_leverage="2", maximum_fill_price="1",
                   mark_price="1", basis_initial_margin="15.125",
                   mark_initial_margin="15.125", available_isolated_after_entry="15.124999999")
        probe = quantity_grid_probe(row, parse_contracts(payload())[-1])
        self.assertEqual(probe["grid_quantity"], "10")
        self.assertEqual(probe["old_model_margin_headroom_after_quantity_floor"], "0.124999999")
        self.assertTrue(probe["old_model_margin_covered"])
        self.assertFalse(probe["price_grid_applied"])
        self.assertFalse(probe["broker_admission_verified"])
        row["available_isolated_after_entry"] = "14.9"
        self.assertFalse(quantity_grid_probe(row, parse_contracts(payload())[-1])[
            "old_model_margin_covered"])

    def test_quantity_probe_does_not_accept_wrong_symbol_or_inconsistent_margin(self):
        rules = parse_contracts(payload())[-1]
        with self.assertRaises(ValueError):
            quantity_grid_probe({"symbol": "XRPUSDT", "execution_enabled": False}, rules)
        row = dict(symbol="BINANCE:XRPUSDT", execution_enabled=False,
                   quantity="0.25", frozen_leverage="2", maximum_fill_price="1",
                   mark_price="1", basis_initial_margin="0.01",
                   mark_initial_margin="0.01", available_isolated_after_entry="1")
        with self.assertRaises(ValueError):
            quantity_grid_probe(row, rules)

    def test_native_audit_precision_is_retained_without_broadening_api_prices(self):
        row = dict(symbol="BINANCE:XRPUSDT", execution_enabled=False,
                   quantity="956.01641941", frozen_leverage="2",
                   maximum_fill_price="0.45992985", mark_price="0.4598",
                   basis_initial_margin="395.73043953777908925000000000000000",
                   mark_initial_margin="383.841958406819",
                   available_isolated_after_entry="395.730439536590930706662840")
        rules = parse_contracts(payload())[-1]
        probe = quantity_grid_probe(row, rules)
        self.assertEqual(probe["grid_quantity"], "956")
        self.assertTrue(probe["old_model_margin_covered"])
        row["available_isolated_after_entry"] = "NaN"
        with self.assertRaises(ValueError):
            quantity_grid_probe(row, rules)

    def test_capture_one_call_hashes_roundtrip_unknown_money_and_create_only(self):
        calls = []
        raw = payload()
        with TemporaryDirectory() as directory:
            output = Path(directory) / "capture"
            receipt = capture_contracts(output, fetch=lambda: calls.append(1) or raw)
            self.assertEqual(calls, [1])
            self.assertEqual(receipt["raw_sha256"], hashlib.sha256(raw).hexdigest())
            selected = (output / "contracts.selected.json").read_bytes()
            self.assertEqual(receipt["selected_sha256"], hashlib.sha256(selected).hexdigest())
            self.assertEqual(parse_contracts(selected), parse_contracts(raw))
            self.assertEqual(json.loads((output / "receipt.json").read_bytes()), receipt)
            self.assertIsNone(receipt["money_quantum"])
            self.assertIsNone(receipt["money_rounding_mode"])
            self.assertFalse(receipt["historical_rules_verified"])
            self.assertFalse(receipt["broker_admission_verified"])
            self.assertFalse(receipt["execution_enabled"])
            with self.assertRaises(FileExistsError):
                capture_contracts(output, fetch=lambda: calls.append(2) or raw)
            self.assertEqual(calls, [1])

    def test_failed_source_keeps_raw_without_success_receipt(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / "failed"
            with self.assertRaises(ValueError):
                capture_contracts(output, fetch=lambda: b'{"code":"40000"}')
            self.assertEqual((output / "contracts.raw.json").read_bytes(), b'{"code":"40000"}')
            self.assertFalse((output / "receipt.json").exists())

    def test_transport_fixed_unsigned_get_no_retry_and_bounded_read(self):
        with patch("investalo_marketdata.futures_broker_calibration.build_opener") as build:
            result = build.return_value.open.return_value.__enter__.return_value
            result.read.return_value = payload()
            self.assertEqual(fetch_contracts(), payload())
            request = build.return_value.open.call_args.args[0]
            self.assertEqual(request.full_url, URL)
            self.assertEqual(request.method, "GET")
            self.assertIsNone(request.data)
            self.assertFalse(any("auth" in k.lower() or "access" in k.lower()
                                 for k in request.headers))
            result.read.assert_called_once_with(MAX_BYTES + 1)
            build.return_value.open.side_effect = OSError("network")
            with self.assertRaises(OSError):
                fetch_contracts()
            self.assertEqual(build.return_value.open.call_count, 2)
