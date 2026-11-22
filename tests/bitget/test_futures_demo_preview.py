"""Exact public-only Demo test sizing; native packets mocked."""
from decimal import Decimal, localcontext
import unittest
from unittest.mock import patch

from investalo_bitget.futures_demo import DemoRejected
from investalo_bitget.futures_demo_preview import btc_test_preview, public_demo_btc_get
from test_futures_demo import AT, response


class BTCPreviewTests(unittest.TestCase):
    def setUp(self):
        self.config = dict(symbol="BTCUSDT", baseCoin="BTC", quoteCoin="USDT",
            symbolStatus="normal", symbolType="perpetual", supportMarginCoins=["USDT"],
            pricePlace="1", volumePlace="4", priceEndStep="1", sizeMultiplier="0.0001",
            minTradeNum="0.0001", minTradeUSDT="5", maxOrderQty="10")
        self.quote = dict(symbol="BTCUSDT", askPr="60000.1", bidPr="60000.0", ts=str(AT+100))

    def preview(self, **changes):
        return btc_test_preview(response([self.config]), response([self.quote]), now_ms=AT+100, **changes)

    def test_exact_grid_slippage_and_notional_with_caller_low_decimal_precision(self):
        with localcontext() as context:
            context.prec = 2
            data = self.preview().public()
        self.assertEqual(data["quantity_btc"], "0.0003")
        self.assertEqual(data["limit_price_usdt"], "60060.1")
        self.assertEqual(data["maximum_notional_usdt"], "18.01803")
        self.assertEqual(data["initial_margin_estimate_usdt"], "9.009015")
        self.assertIs(data["fees_verified"], False)
        self.assertIs(data["account_verified"], False)
        self.assertIs(data["submission_enabled"], False)
        self.assertEqual((data["leverage"], data["force"]), (2, "ioc"))

    def test_stale_quote_source_cannot_be_hidden_by_fresh_response_time(self):
        self.quote["ts"] = str(AT-5001)
        with self.assertRaises(DemoRejected): self.preview()

    def test_empty_native_maximum_remains_unknown_and_preview_cannot_enable_submission(self):
        self.config["maxOrderQty"] = ""
        data = self.preview().public()
        self.assertIsNone(data["native_max_quantity_btc"])
        self.assertIs(data["maximum_quantity_verified"], False)
        self.assertIs(data["submission_enabled"], False)
        self.assertLessEqual(Decimal(data["maximum_notional_usdt"]), Decimal(20))

    def test_unsupported_contract_and_minimum_exceeding_cap_are_not_scaled_up(self):
        for field, value in (("symbolStatus","maintenance"), ("supportMarginCoins", ["SUSDT"]),
            ("symbolType","delivery"), ("minTradeNum","0.001"), ("minTradeUSDT","25"),
            ("pricePlace","100000"), ("sizeMultiplier","0.00001")):
            with self.subTest(field=field):
                before = dict(self.config); self.config[field] = value
                with self.assertRaises(DemoRejected): self.preview()
                self.config = before

    def test_wrong_or_duplicate_symbol_packets_reject(self):
        for data in ([], [self.config, self.config], [{**self.config, "symbol": "SBTCSUSDT"}]):
            with self.subTest(data=len(data)), self.assertRaises(DemoRejected):
                btc_test_preview(response(data), response([self.quote]), now_ms=AT+100)

    def test_empty_crossed_or_malformed_market_quotes_reject(self):
        for change in (dict(askPr=""), dict(askPr="NaN"), dict(bidPr="60001"),
                       dict(askPr="0.00001", bidPr="0.00001")):
            with self.subTest(change=change):
                old = dict(self.quote); self.quote.update(change)
                with self.assertRaises(Exception): self.preview()
                self.quote = old

    def test_public_transport_allows_two_fixed_gets_demo_header_no_credentials(self):
        class Reply:
            status=200
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def read(self, maximum): return b'{"code":"00000","data":[]}'
        class Opener:
            def open(_self, request, timeout):
                self.assertEqual(request.method, "GET")
                self.assertTrue(request.full_url.startswith("https://api.bitget.com/api/v2/mix/market/"))
                self.assertEqual(request.get_header("Paptrading"), "1")
                self.assertFalse(any(k.lower().startswith("access-") for k in request.headers))
                self.assertIsNone(request.data)
                return Reply()
        with patch("investalo_bitget.futures_demo_preview.build_opener", return_value=Opener()) as opened:
            public_demo_btc_get("contracts"); public_demo_btc_get("ticker")
            self.assertEqual(opened.call_count, 2)
            with self.assertRaises(DemoRejected): public_demo_btc_get("place-order")
            self.assertEqual(opened.call_count, 2)
