"""Synthetic offline native responses; no keys, broker or Paper state mutation."""
from dataclasses import replace
from decimal import Decimal, localcontext
import json
import unittest
from uuid import UUID

from investalo_bitget import OwnerContext, ReadResponse, BitgetRejected, HTTPSReadTransport
from investalo_bitget.futures_demo import DemoBinding, DemoGrid, DemoIntent, DemoRejected, request_plan
from investalo_bitget.futures_demo_reconcile import (
    DemoTrace, acknowledge, observe, check_position,
)

D = Decimal
AT = 1_700_000_000_000
OWNER = OwnerContext(UUID(int=1), UUID(int=2))
OTHER = OwnerContext(UUID(int=1), UUID(int=3))
BINDING = DemoBinding(OWNER, UUID(int=4), UUID(int=5), "123456")
GRID = DemoGrid("BTCUSDT", D("0.001"), D("0.1"), D("0.001"), D("5"), D("10"))


def intent(**changes):
    return DemoIntent(**{"binding": BINDING, "command_id": UUID(int=6), "grid": GRID,
                         "action": "open_long", "quantity": D("0.010"),
                         "limit_price": D("20000"), "before_quantity": D("0.020"), **changes})


def response(data, at=AT + 100, **fields):
    return ReadResponse(200, json.dumps({"code": "00000", "data": data,
                                        "requestTime": at, **fields}).encode())


def detail(order, **changes):
    return {"symbol": order.grid.symbol.lower(), "clientOid": order.client_oid,
            "orderId": "123", "marginCoin": "usdt", "marginMode": "isolated",
            "posMode": "one_way_mode", "posSide": "net", "leverage": "2",
            "size": str(order.quantity), "price": str(order.limit_price),
            "side": "buy" if order.action == "open_long" else "sell",
            "reduceOnly": "no" if order.action == "open_long" else "yes",
            "orderType": "limit", "force": "ioc", "state": "partially_filled",
            "baseVolume": "0.004", "priceAvg": "20000", "fee": "",
            "cTime": str(AT + 10), "uTime": str(AT + 20), **changes}


def positions(quantity="0.024", **changes):
    return [{"symbol": "BTCUSDT", "marginCoin": "USDT", "holdSide": "long",
             "marginMode": "isolated", "posMode": "one_way_mode", "leverage": "2",
             "total": quantity, "available": quantity, "locked": "0", **changes}]


def dispatched(order=None):
    return DemoTrace(order or intent()).dispatched(context=OWNER, at_ms=AT)


def observed(order=None, **fields):
    trace = dispatched(order)
    return observe(trace, response(detail(trace.intent, **fields)), context=OWNER, now_ms=AT + 100)


class DemoContractTests(unittest.TestCase):
    def test_profile_and_owner_reject_before_request(self):
        for changes in ({"environment": "live"}, {"api_family": "uta"},
                        {"position_mode": "hedge_mode"}, {"leverage": 3},
                        {"leverage": True}, {"account_id": "4"}, {"credential_ref": "5"}):
            with self.subTest(changes=changes), self.assertRaises(DemoRejected):
                replace(BINDING, **changes)
        with self.assertRaises(DemoRejected):
            request_plan(intent(), "place", context=OTHER)

    def test_key_reference_and_redacted_model_have_no_credentials(self):
        for model in (BINDING, intent(), request_plan(intent(), "place", context=OWNER)):
            self.assertNotIn("123456", repr(model))
            self.assertNotIn(str(UUID(int=5)), repr(model))
        plan = request_plan(intent(), "place", context=OWNER)
        self.assertFalse(hasattr(plan, "url"))
        self.assertFalse(hasattr(plan, "credentials"))
        with self.assertRaises(BitgetRejected):
            HTTPSReadTransport()(plan)  # existing read transport rejects before any network IO

    def test_exact_ioc_buy_and_reduce_only_close_contract(self):
        for action, side, reduce in (("open_long", "buy", "NO"), ("reduce_long", "sell", "YES")):
            order = intent(action=action)
            plan = request_plan(order, "place", context=OWNER)
            body = json.loads(plan.body)
            self.assertEqual((plan.method, plan.target), ("POST", "/api/v2/mix/order/place-order"))
            self.assertEqual(body, {
                "symbol": "BTCUSDT", "productType": "USDT-FUTURES",
                "marginMode": "isolated", "marginCoin": "USDT", "size": "0.01",
                "price": "20000", "side": side, "reduceOnly": reduce,
                "clientOid": order.client_oid, "force": "ioc", "orderType": "limit"})
            self.assertEqual(dict(plan.headers)["paptrading"], "1")

    def test_lookup_uses_stable_client_oid_and_product_wide_positions(self):
        order = intent()
        self.assertEqual(request_plan(order, "detail", context=OWNER).target,
                         "/api/v2/mix/order/detail?symbol=BTCUSDT&productType=USDT-FUTURES"
                         "&clientOid=" + order.client_oid)
        self.assertEqual(request_plan(order, "positions", context=OWNER).target,
                         "/api/v2/mix/position/all-position?productType=USDT-FUTURES&marginCoin=USDT")
        for operation in ("cancel", "market", "transfer", "set-leverage", "fill-history", "retry"):
            with self.subTest(operation=operation), self.assertRaises(DemoRejected):
                request_plan(order, operation, context=OWNER)

    def test_grid_checks_exactly_without_rounding_or_context_dependence(self):
        with localcontext() as ctx:
            ctx.prec = 2
            self.assertEqual(intent().quantity, D("0.010"))
            for changes in ({"quantity": D("0.0101")}, {"limit_price": D("20000.01")},
                            {"quantity": D("11")}, {"quantity": D("0")},
                            {"limit_price": D("100")}, {"quantity": D("NaN")},
                            {"quantity": 1.0}):
                with self.subTest(changes=changes), self.assertRaises(DemoRejected):
                    intent(**changes)

    def test_close_cannot_reverse_or_exceed_position(self):
        with self.assertRaises(DemoRejected):
            intent(action="reduce_long", before_quantity=D("0.009"))
        for action in ("short", "hedge", "market", ["open_long"]):
            with self.subTest(action=action), self.assertRaises(DemoRejected):
                intent(action=action)

    def test_stable_command_and_changed_payload_conflict_identity(self):
        first, same, changed = intent(), intent(), intent(quantity=D("0.011"))
        self.assertEqual(first.client_oid, same.client_oid)
        self.assertEqual(first.intent_digest, same.intent_digest)
        self.assertEqual(first.client_oid, changed.client_oid)
        self.assertNotEqual(first.intent_digest, changed.intent_digest)
        self.assertNotEqual(first.client_oid, intent(command_id=UUID(int=7)).client_oid)
        self.assertNotEqual(first.client_oid,
                            intent(binding=replace(BINDING, account_id=UUID(int=7))).client_oid)
        self.assertEqual(len(first.client_oid), 32)


class DemoReconciliationTests(unittest.TestCase):
    def test_dispatch_candidate_stops_all_repeat_submission(self):
        trace = dispatched()
        self.assertFalse(trace.can_submit)
        self.assertEqual(trace.state, "submission_unknown")
        with self.assertRaisesRegex(DemoRejected, "resend_denied"):
            trace.dispatched(context=OWNER, at_ms=AT + 1)
        with self.assertRaises(DemoRejected):
            DemoTrace(intent(), state="filled", dispatch_ms=AT)

    def test_success_acknowledgement_never_counts_as_fill(self):
        trace = dispatched()
        for native in (None, "123"):
            result = acknowledge(trace, response({"clientOid": trace.intent.client_oid, "orderId": native}),
                                 context=OWNER, now_ms=AT + 100)
            self.assertEqual(result.state, "acknowledged")
            self.assertEqual(result.order_id, native)
            self.assertIsNone(result.observation)
            self.assertFalse(result.can_submit)
            with self.assertRaises(DemoRejected):
                check_position(result, response([]), context=OWNER, now_ms=AT + 100)

    def test_failure_and_not_found_leave_unknown_without_retry(self):
        trace = dispatched()
        for packet in (ReadResponse(503, b"provider secret"),
                       response(None, code="43025", msg="provider secret"),
                       response({"clientOid": "foreign", "orderId": "123"})):
            with self.subTest(packet=packet), self.assertRaises((DemoRejected, BitgetRejected)):
                acknowledge(trace, packet, context=OWNER, now_ms=AT + 100)
            self.assertEqual(trace.state, "submission_unknown")
            self.assertFalse(trace.can_submit)

    def test_lookup_resolves_missing_acknowledgement_and_keeps_unknown_fee(self):
        result = observed()
        self.assertEqual((result.state, result.order_id), ("partially_filled", "123"))
        self.assertEqual(result.observation.quantity, D("0.004"))
        self.assertIsNone(result.observation.reported_fee)
        self.assertFalse(result.can_submit)
        ack = acknowledge(dispatched(), response({"clientOid": result.intent.client_oid, "orderId": "124"}),
                          context=OWNER, now_ms=AT + 100)
        with self.assertRaises(DemoRejected):
            observe(ack, response(detail(result.intent)), context=OWNER, now_ms=AT + 100)

    def test_partial_cancel_keeps_exposure_and_never_becomes_full_stage(self):
        partial = observed()
        canceled = observe(partial, response(detail(partial.intent, state="canceled",
                           uTime=str(AT + 30), fee="-0.08")), context=OWNER, now_ms=AT + 100)
        self.assertEqual(canceled.observation.quantity, D("0.004"))
        self.assertEqual(canceled.observation.reported_fee, D("-0.08"))
        self.assertEqual(check_position(canceled, response(positions()), context=OWNER, now_ms=AT + 100),
                         D("0.024"))

    def test_full_fill_and_full_reduce_match_actual_base_position(self):
        for action, remaining in (("open_long", "0.030"), ("reduce_long", "0.010")):
            result = observed(intent(action=action), state="filled", baseVolume="0.010", fee="-0.2")
            self.assertEqual(check_position(result, response(positions(remaining)),
                                           context=OWNER, now_ms=AT + 100), D(remaining))
        close = observed(intent(action="reduce_long", before_quantity=D("0.010")),
                         state="filled", baseVolume="0.010")
        self.assertEqual(check_position(close, response([]), context=OWNER, now_ms=AT + 100), D(0))

    def test_zero_fill_cancel_has_no_average_and_does_not_change_position(self):
        result = observed(state="canceled", baseVolume="0", priceAvg="")
        self.assertIsNone(result.observation.average_price)
        self.assertEqual(check_position(result, response(positions("0.020")),
                                       context=OWNER, now_ms=AT + 100), D("0.020"))

    def test_mismatched_native_scope_terms_or_quantity_fail_closed(self):
        cases = ({"clientOid": "foreign"}, {"symbol": "ETHUSDT"}, {"size": "0.02"},
                 {"price": "21000"}, {"side": "sell"}, {"reduceOnly": "YES"},
                 {"marginMode": "crossed"}, {"posMode": "hedge_mode"}, {"leverage": "3"},
                 {"orderType": "market"}, {"force": "gtc"}, {"posSide": "short"},
                 {"symbol": "BTCUſDT"}, {"baseVolume": "NaN"}, {"baseVolume": 0.004},
                 {"state": "filled"}, {"state": "live"}, {"baseVolume": "0.011"},
                 {"priceAvg": "20000.1"}, {"priceAvg": ""},
                 {"uTime": str(AT + 200)}, {"cTime": str(AT - 1)})
        for fields in cases:
            with self.subTest(fields=fields), self.assertRaises((DemoRejected, BitgetRejected)):
                observed(**fields)

    def test_sell_fill_cannot_breach_protective_limit(self):
        with self.assertRaises(DemoRejected):
            observed(intent(action="reduce_long"), priceAvg="19999.9")

    def test_old_future_and_cross_owner_responses_reject(self):
        trace = dispatched()
        for now in (AT + 5101, AT + 99):
            with self.subTest(now=now), self.assertRaises(DemoRejected):
                observe(trace, response(detail(trace.intent)), context=OWNER, now_ms=now)
        with self.assertRaises(DemoRejected):
            observe(trace, response(detail(trace.intent)), context=OTHER, now_ms=AT + 100)

    def test_immutable_order_id_and_monotone_fill_clock(self):
        old = observed()
        for fields in ({"orderId": "124"}, {"baseVolume": "0.003"},
                       {"uTime": str(AT + 19)}, {"cTime": str(AT + 9)},
                       {"state": "live", "baseVolume": "0", "priceAvg": "0"},
                       {"priceAvg": "19999"}, {"priceAvg": "19999", "uTime": str(AT + 30)}):
            with self.subTest(fields=fields), self.assertRaises(DemoRejected):
                observe(old, response(detail(old.intent, **fields)), context=OWNER, now_ms=AT + 100)
        self.assertEqual(observe(old, response(detail(old.intent)), context=OWNER,
                                 now_ms=AT + 100), old)

    def test_terminal_fill_cannot_reopen_or_change_cumulative_quantity(self):
        old = observed(state="filled", baseVolume="0.010")
        for fields in ({"state": "partially_filled", "baseVolume": "0.004"},
                       {"state": "canceled", "baseVolume": "0.004"},
                       {"priceAvg": "19999", "state": "filled", "baseVolume": "0.010"}):
            with self.subTest(fields=fields), self.assertRaises(DemoRejected):
                observe(old, response(detail(old.intent, uTime=str(AT + 30), **fields)),
                        context=OWNER, now_ms=AT + 100)

    def test_unknown_fee_can_become_known_without_inventing_fill_ids(self):
        old = observed()
        known = observe(old, response(detail(old.intent, fee="-0.08")),
                        context=OWNER, now_ms=AT + 100)
        self.assertEqual(known.observation.reported_fee, D("-0.08"))
        self.assertFalse(hasattr(known.observation, "fill_id"))
        with self.assertRaises(DemoRejected):
            observe(known, response(detail(old.intent, fee="-0.09")),
                    context=OWNER, now_ms=AT + 100)

    def test_partial_fill_progress_and_fee_rebate_remain_native_values(self):
        old = observed()
        full = observe(old, response(detail(old.intent, state="filled", baseVolume="0.010",
                       uTime=str(AT + 30), priceAvg="19999", fee="0.1")),
                       context=OWNER, now_ms=AT + 100)
        self.assertEqual(full.observation.quantity, D("0.010"))
        self.assertEqual(full.observation.average_price, D("19999"))
        self.assertEqual(full.observation.reported_fee, D("0.1"))

    def test_position_difference_lock_short_foreign_and_missing_fields_stop(self):
        result = observed()
        for data in (positions("0.025"), positions(locked="0.001"), positions(holdSide="short"),
                     positions(symbol="DOGEUSDT"), positions(posMode="hedge_mode"),
                     positions(leverage="3"), positions(total=""), positions(marginCoin=1),
                     positions() * 2):
            with self.subTest(data=data), self.assertRaises((DemoRejected, BitgetRejected)):
                check_position(result, response(data), context=OWNER, now_ms=AT + 100)

    def test_peer_candidate_position_is_retained_and_snapshot_must_follow_order(self):
        result = observed()
        peer = positions("1", symbol="SOLUSDT")[0]
        self.assertEqual(check_position(result, response(positions() + [peer]),
                                       context=OWNER, now_ms=AT + 100), D("0.024"))
        with self.assertRaises(DemoRejected):
            check_position(result, response(positions(), at=AT + 99),
                           context=OWNER, now_ms=AT + 100)

    def test_duplicate_native_json_fields_and_uta_envelope_reject(self):
        trace = dispatched()
        for packet in (ReadResponse(200, b'{"code":"00000","code":"00000","requestTime":1,"data":{}}'),
                       response({"list": [detail(trace.intent)]})):
            with self.assertRaises((DemoRejected, BitgetRejected)):
                observe(trace, packet, context=OWNER, now_ms=AT + 100)


if __name__ == "__main__":
    unittest.main()
