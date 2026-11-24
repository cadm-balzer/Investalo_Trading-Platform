"""Real durable close/AEAD/mTLS paths, synthetic native account and actor ports."""
import json
import time
import unittest
from decimal import Decimal
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from investalo_credential_store.demo_market_runtime import DemoMarketTestRuntime, validate_market_result
from investalo_credential_store.request_assertion import OnboardingRejected
import test_demo_market_runtime as base


class CloseRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.case = c = base.MarketRuntimeTests(); c.setUp()
        self.closed, self.fail_ack, self.foreign = False, False, False
        self.close_fill,self.close_state="0.0003","filled"
        self.orders = {}
        original = c.f.native.transport
        def native(packet):
            if packet.axis == "positions" and c.posts:
                quantity=str(Decimal("0.0003")-Decimal(self.close_fill)) if len(c.posts)>1 else "0.0003"
                rows = [] if self.closed else [dict(symbol="BTCUSDT",marginCoin="USDT",holdSide="long",
                    marginMode="isolated",posMode="one_way_mode",leverage="2",
                    total="0.0004" if self.foreign else quantity,available=quantity,locked="0",
                    openPriceAvg="70000",markPrice="71000",unrealizedPL="0.3")]
                return c.reply(rows)
            if packet.axis == "wallet" and c.posts:
                row=dict(c.f.wallet[0],accountEquity="10000.27",available="10000.27" if self.closed else "9990",
                    isolatedMargin="0" if self.closed else "10.5",unrealizedPL="0" if self.closed else "0.3")
                return c.reply([row])
            return original(packet)
        c.f.native.transport=native
        c.runtime.order_transport=self.order

    def tearDown(self):
        self.case.tearDown()

    def order(self, packet):
        packet.consume(); c=self.case
        if packet.method=="POST":
            raw=json.loads(packet.body); closing=raw["side"]=="sell"
            self.assertEqual(raw["reduceOnly"],"YES" if closing else "NO")
            self.assertEqual(raw["size"],"0.0003")
            self.assertNotIn("price",raw);self.assertNotIn("force",raw)
            self.assertNotIn(raw["clientOid"],self.orders)
            c.posts.append(raw)
            self.orders[raw["clientOid"]]=(closing,int(packet.headers["ACCESS-TIMESTAMP"]))
            if closing:
                self.closed=self.close_fill=="0.0003"
                self.assertEqual(len(list((c.root/"consents").glob("consumed-*.json"))),2)
                if self.fail_ack:raise TimeoutError()
            # Official one-way reduceOnly may omit orderId. Original clientOid
            # must remain sufficient for once-only GET recovery.
            return c.reply(dict(clientOid=raw["clientOid"],**({} if closing else {"orderId":"123"})))
        oid=parse_qs(urlsplit(packet.target).query)["clientOid"][0]
        closing,started=self.orders[oid]
        return c.reply(dict(symbol="BTCUSDT",clientOid=oid,orderId="124" if closing else "123",
            marginCoin="USDT",marginMode="isolated",posMode="one_way_mode",posSide="net",leverage="2",
            size="0.0003",orderType="market",side="sell" if closing else "buy",reduceOnly="YES" if closing else "NO",
            state=self.close_state if closing else "filled",baseVolume=self.close_fill if closing else "0.0003",
            priceAvg="71000" if closing else "70000",
            fee="-0.02" if closing else "-0.01",cTime=str(started),uTime=str(time.time_ns()//1_000_000)))

    def opened(self):
        c=self.case
        p=c.prepare();c.call("market_submit",p["consent_request"])
        result=c.call("market_observe",{**c.target,"command_id":"latest"})
        self.assertTrue(result["position_matched"])
        return p

    def test_owned_open_close_restore_latest_fees_and_flat_wallet(self):
        self.opened();c=self.case
        p=c.call("market_close_prepare",c.target)
        self.assertEqual(validate_market_result("market_close_prepare",p),p)
        result=c.call("market_close_submit",p["consent_request"])
        self.assertEqual(result["order"]["state"],"acknowledged")
        self.assertIsNone(result["settlement"])
        c.runtime.state.close()
        c.runtime=DemoMarketTestRuntime(c.f.reader,root=c.root,order_transport=self.order)
        result=c.call("market_observe",{**c.target,"command_id":"latest"})
        self.assertEqual(validate_market_result("market_observe",result),result)
        self.assertEqual(result["order"]["state"],"filled")
        self.assertTrue(result["order"]["position_matched"])
        s=result["settlement"];self.assertTrue(s["position_closed"])
        self.assertEqual((s["wallet"]["equity"],s["open_position_count"],s["opening_reported_fee_usdt"]),
                         ("10000.27",0,"-0.01"))
        self.assertEqual(result["order"]["reported_fee_usdt"],"-0.02")
        for action,body in (("market_close_submit",p["consent_request"]),("market_close_prepare",c.target),
                            ("market_prepare",c.target)):
            with self.assertRaises(OnboardingRejected):c.call(action,body)
        self.assertEqual(len(c.posts),2)

    def test_unknown_close_ack_never_resends_and_recovers_by_original_client_oid(self):
        self.opened();c=self.case;p=c.call("market_close_prepare",c.target);self.fail_ack=True
        result=c.call("market_close_submit",p["consent_request"])
        self.assertEqual(result["order"]["state"],"submission_unknown")
        result=c.call("market_observe",{**c.target,"command_id":"latest"})
        self.assertTrue(result["settlement"]["position_closed"])
        self.assertEqual(len(c.posts),2)

    def test_partial_close_retains_residual_position_and_never_claims_flat_or_resends(self):
        self.opened();c=self.case;p=c.call("market_close_prepare",c.target)
        self.close_fill,self.close_state="0.0002","partially_filled"
        c.call("market_close_submit",p["consent_request"])
        result=c.call("market_observe",{**c.target,"command_id":"latest"})
        self.assertEqual(validate_market_result("market_observe",result),result)
        self.assertEqual(result["order"]["filled_quantity_btc"],"0.0002")
        self.assertTrue(result["order"]["position_matched"])
        self.assertFalse(result["settlement"]["position_closed"])
        self.assertEqual(result["settlement"]["open_position_count"],1)
        with self.assertRaises(OnboardingRejected):c.call("market_close_prepare",c.target)
        self.assertEqual(len(c.posts),2)

    def test_no_original_opening_and_changed_position_deny_without_close_post(self):
        c=self.case
        with self.assertRaises(OnboardingRejected):c.call("market_close_prepare",c.target)
        self.opened();p=c.call("market_close_prepare",c.target);self.foreign=True
        with self.assertRaises(OnboardingRejected):c.call("market_close_submit",p["consent_request"])
        with self.assertRaises(OnboardingRejected):c.call("market_close_prepare",c.target)
        self.assertEqual(len(c.posts),1)

    def test_open_close_purposes_and_confirmation_cannot_be_interchanged(self):
        self.opened();c=self.case;p=c.call("market_close_prepare",c.target)
        for action,body,claims in [
            ("market_submit",p["consent_request"],{}),
            ("market_close_submit",p["consent_request"],{"aud":"investalo-demo-btc-market-order"}),
            ("market_close_submit",{**p["consent_request"],"confirmation":"btc-demo-market-long-isolated-2x-estimate-20-usdt"},{}),
            ("market_close_submit",p["consent_request"],{"auth_epoch":4})]:
            with self.assertRaises(OnboardingRejected):c.call(action,body,**claims)
        self.assertEqual(len(c.posts),1)

    def test_close_above_opening_notional_budget_keeps_exact_quantity(self):
        self.opened();c=self.case;original=c.f.reader.market_read
        def quotes(axis):
            response=original(axis)
            if axis=="ticker":
                frame=json.loads(response.body)
                frame["data"][0]["askPr"]="71000"
                frame["data"][0]["bidPr"]="70999"
                return c.reply(frame["data"])
            return response
        c.f.reader.market_read=quotes
        p=c.call("market_close_prepare",c.target)
        self.assertEqual((p["quantity_btc"],p["estimated_notional_usdt"]),("0.0003","21.3"))
        c.call("market_close_submit",p["consent_request"])
        self.assertEqual(len(c.posts),2)

    def test_launcher_market_dispatch_requires_installed_service_and_exact_known_action(self):
        from investalo_credential_store.demo_trading_runtime import _application_executor
        c=self.case
        for service,action in ((None,"market_close_prepare"),(c.runtime,"market_unknown")):
            execute=_application_executor(c.f.config,c.f.reader.context,connect=None,verifier=None,
                provision=c.f.native,keyring=c.f.reader.keyring,guard=c.runtime._guard,
                account_read=c.f.reader,market_test=service)
            with self.assertRaises(OnboardingRejected):execute(c.f.context,action,"",b"")
        self.assertFalse(c.posts)


class CloseASGITests(base.MarketASGITests):
    test_actual_asgi_mtls_prepare_submit_observe_retains_original_actor_context = None
    def setUp(self):
        super().setUp()
        self.sleep_patch.stop();self.case.tearDown()
        self.close_case=CloseRuntimeTests();self.close_case.setUp();self.case=self.close_case.case
        self.sleep_patch=patch("investalo_credential_store.demo_market_runtime.time.sleep",base.REAL_SLEEP)
        self.sleep_patch.start();self.store=self.case.f.reader.context

    def tearDown(self):
        self.sleep_patch.stop();self.close_case.tearDown()

    def test_actual_asgi_mtls_owned_close_and_original_account_settlement(self):
        from investalo_credential_store.private_http import DemoMarketTestHTTPApplication
        from investalo_credential_store.demo_trading_runtime import _application_executor
        # Exercise the actual launcher dispatch closure, rather than wiring
        # the Market service straight into the TLS adapter.
        execute=_application_executor(self.case.f.config,self.store,connect=None,verifier=None,
            provision=self.case.f.native,keyring=self.case.f.reader.keyring,guard=self.case.runtime._guard,
            account_read=self.case.f.reader,market_test=self.case.runtime)
        with self.server(execute=execute,application_type=DemoMarketTestHTTPApplication) as service:
            def call(action,body):
                code,data=self.response(self.exchange(service,self.wire(action,body)))
                self.assertEqual(code,200);return data
            p=call("market_prepare",self.case.target)
            call("market_submit",p["consent_request"])
            call("market_observe",{**self.case.target,"command_id":"latest"})
            p=call("market_close_prepare",self.case.target)
            call("market_close_submit",p["consent_request"])
            result=call("market_observe",{**self.case.target,"command_id":"latest"})
            self.assertTrue(result["settlement"]["position_closed"])
            self.assertEqual(len(self.case.posts),2)
