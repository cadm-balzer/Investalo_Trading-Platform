"""Market sizing/native payload/journal evidence; all broker replies synthetic."""
from dataclasses import replace
from decimal import Decimal, localcontext
import json
import unittest
from uuid import UUID

from investalo_bitget.futures_demo import DemoIntent, DemoRejected, request_plan
from investalo_bitget.futures_demo_market import BTCMarketGrid, BTCMarketIntent, btc_market_preview
from investalo_bitget.futures_demo_outbox import _intent, _intent_record
from investalo_bitget.futures_demo_reconcile import DemoTrace, observe, check_position
from test_futures_demo import AT, OWNER, BINDING, GRID, response, positions
import test_futures_demo_preview as preview_fixture

D = Decimal


def market_intent(**changes):
    return BTCMarketIntent(**{"binding": BINDING, "command_id": UUID(int=6),
        "grid": BTCMarketGrid("BTCUSDT", D("0.0001"), D("0.0001"), D(5), None),
        "action": "open_long", "quantity": D("0.0003"), "reference_price": D(60000),
        "before_quantity": D(0), "observed_ms": AT+100, **changes})


def market_detail(order, **changes):
    return {"symbol": "btcusdt", "clientOid": order.client_oid, "orderId": "123",
        "marginCoin": "usdt", "marginMode": "isolated", "posMode": "one_way_mode", "posSide": "net",
        "leverage": "2", "size": str(order.quantity), "price": "0", "side": "buy", "reduceOnly": "no",
        "orderType": "market", "force": "gtc", "state": "filled", "baseVolume": str(order.quantity),
        "priceAvg": "70000", "fee": "", "cTime": str(AT+10), "uTime": str(AT+20), **changes}


class MarketTests(unittest.TestCase):
    def setUp(self):
        fixture = preview_fixture.BTCPreviewTests(); fixture.setUp()
        self.config, self.quote = fixture.config, fixture.quote

    def preview(self):
        return btc_market_preview(response([self.config]), response([self.quote]), now_ms=AT+100)

    def test_buffered_sizing_keeps_unknown_market_max_without_limit_substitute(self):
        self.config["maxOrderQty"] = "0.0001"
        with localcontext() as precision:
            precision.prec = 2
            preview = self.preview()
            order = preview.intent(BINDING, UUID(int=6))
            data = preview.public()
        self.assertEqual(order.quantity, D("0.0003"))
        self.assertIsNone(order.grid.max_market_quantity)
        self.assertLessEqual(D(data["planning_notional_usdt"]), D(20))
        self.assertFalse(data["execution_price_guaranteed"])
        self.assertNotIn("maximum_notional_usdt", data)

    def test_known_market_max_caps_quantity_and_malformed_max_rejects(self):
        self.config["maxMarketOrderQty"] = "0.0002"
        self.assertEqual(self.preview().quantity, D("0.0002"))
        for value in ("garbage", "NaN", "0", "-1", True):
            self.config["maxMarketOrderQty"] = value
            with self.subTest(value=value), self.assertRaises(Exception):
                self.preview()

    def test_native_minimum_outside_budget_is_never_enlarged(self):
        for field, value in (("minTradeNum", "0.001"), ("minTradeUSDT", "21"),
                             ("sizeMultiplier", "0.00001")):
            original = dict(self.config); self.config[field] = value
            with self.subTest(field=field), self.assertRaises(Exception): self.preview()
            self.config = original
        self.quote["ts"] = str(AT-5001)
        with self.assertRaises(DemoRejected): self.preview()

    def test_exact_market_body_omits_price_and_force_with_reduce_only_close(self):
        for action, side, reduce in (("open_long", "buy", "NO"), ("reduce_long", "sell", "YES")):
            order = market_intent(action=action, before_quantity=D("0.0003") if reduce == "YES" else D(0))
            plan = request_plan(order, "place", context=OWNER)
            body = json.loads(plan.body)
            self.assertEqual(body, dict(symbol="BTCUSDT", productType="USDT-FUTURES",
                marginMode="isolated", marginCoin="USDT", size="0.0003", side=side,
                orderType="market", reduceOnly=reduce, clientOid=order.client_oid))
            self.assertEqual(dict(plan.headers)["paptrading"], "1")

    def test_price_growth_cannot_block_reducing_existing_quantity_or_enlarge_it(self):
        closing = market_intent(action="reduce_long", before_quantity=D("0.0003"))
        grown = replace(closing, reference_price=D(80000))
        self.assertEqual(grown.quantity,D("0.0003"))
        self.assertEqual(json.loads(request_plan(grown,"place",context=OWNER).body)["reduceOnly"],"YES")
        with self.assertRaises(DemoRejected): replace(grown,quantity=D("0.0004"))
        with self.assertRaises(DemoRejected): replace(grown,action="open_long",before_quantity=D(0))

    def test_reference_changed_payload_and_order_domain_change_digests(self):
        order = market_intent()
        changed = replace(order, reference_price=D(61000))
        self.assertEqual(order.client_oid, changed.client_oid)
        self.assertNotEqual(order.intent_digest, changed.intent_digest)
        old = DemoIntent(BINDING, order.command_id, GRID, "open_long", D("0.001"), D(19000), D(0))
        self.assertNotEqual(old.client_oid, order.client_oid)
        with self.assertRaises(DemoRejected):
            replace(order, quantity=D("0.0004"))
        with self.assertRaises(DemoRejected):
            replace(order, action="reduce_long")

    def test_market_journal_roundtrip_keeps_unknown_max_and_rejects_rewrite(self):
        order = market_intent(); record = _intent_record(order)
        restored = _intent(json.loads(json.dumps(record)), BINDING)
        self.assertEqual(restored, order)
        self.assertIsNone(restored.grid.max_market_quantity)
        for change in (dict(schema="limit"), dict(reference_price="61000"),
                       dict(observed_ms=True), dict(limit_price="60000")):
            with self.subTest(change=change), self.assertRaises(DemoRejected):
                _intent({**record, **change}, BINDING)

    def test_slippage_above_reference_or_20_notional_is_retained_as_actual_fill(self):
        order = market_intent()
        trace = DemoTrace(order).dispatched(context=OWNER, at_ms=AT)
        filled = observe(trace, response(market_detail(order)), context=OWNER, now_ms=AT+100)
        self.assertEqual(filled.observation.average_price, D(70000))
        self.assertEqual(filled.observation.quantity * filled.observation.average_price, D(21))
        self.assertIsNone(filled.observation.reported_fee)
        self.assertEqual(check_position(filled, response(positions("0.0003")),
                         context=OWNER, now_ms=AT+100), D("0.0003"))

    def test_partial_then_canceled_fill_retained_and_wrong_order_kind_denies(self):
        order = market_intent()
        trace = DemoTrace(order).dispatched(context=OWNER, at_ms=AT)
        partial = observe(trace, response(market_detail(order, state="partially_filled",
            baseVolume="0.0001")), context=OWNER, now_ms=AT+100)
        canceled = observe(partial, response(market_detail(order, state="canceled",
            baseVolume="0.0001", uTime=str(AT+30))), context=OWNER, now_ms=AT+100)
        self.assertEqual(canceled.observation.quantity, D("0.0001"))
        for fields in (dict(orderType="limit"), dict(size="0.0004"), dict(reduceOnly="yes"),
                       dict(baseVolume="0.0004"), dict(priceAvg="0")):
            with self.subTest(fields=fields), self.assertRaises(DemoRejected):
                observe(trace, response(market_detail(order, **fields)), context=OWNER, now_ms=AT+100)
