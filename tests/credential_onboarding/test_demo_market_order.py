"""Market-specific consent, actual durable dispatcher and native admission checks."""
from dataclasses import replace
from decimal import Decimal
import json
import unittest
from unittest.mock import patch
from uuid import UUID

from investalo_bitget import parse
from investalo_bitget.models import ProductType
from investalo_bitget.futures_demo import DemoRejected
from investalo_bitget.futures_demo_market import (
    BTCMarketPreview, CONFIRMATION, btc_market_preview)
from investalo_bitget.futures_demo_registry import RegisteredDemoOutbox
from investalo_credential_store.demo_order_consent import DemoBTCMarketConsentVerifier
from investalo_credential_store.demo_order_consumer import DurableDemoOrderConsumer
from investalo_credential_store.demo_market_test_check import check_btc_market_test
from test_futures_demo import OWNER, AT, response
from test_futures_demo_market import market_intent, market_detail
import test_demo_order_consent as consent
import test_demo_account_sync as account_fixture


class MarketConsentTests(unittest.TestCase):
    def setUp(self):
        self.f = consent.OrderConsentTests(); self.f.setUp()
        c = self.f.case
        c.box.close()
        registry, directory = c.root / "market-registry", c.root / "market-outbox"
        registry.mkdir(mode=0o700); directory.mkdir(mode=0o700)
        c.registry, c.directory = registry, directory
        c.box = RegisteredDemoOutbox.create(registry, directory, binding=c.spec.binding,
            outbox_id=UUID(int=93), context=OWNER)
        c.order = market_intent()
        c.box.prepare(c.order, context=OWNER, expected_revision=0)
        self.f.verifier = DemoBTCMarketConsentVerifier(key=consent.KEY,
            oidc_issuer=self.f.verifier.oidc_issuer, origin=self.f.verifier.origin)
        self.f.request.update(intent_sha256=c.order.intent_digest,
                             outbox_receipt=c.box.receipt.record(), confirmation=CONFIRMATION)
        self.f.body = json.dumps(self.f.request, separators=(",", ":")).encode()

    def tearDown(self):
        self.f.tearDown()

    def token(self, **changes):
        return self.f.token(**dict(kind="investalo-demo-btc-market-order-consent/1",
            aud="investalo-demo-btc-market-order", htu="/v1/bitget-demo-trading/market-order-submit", **changes))

    def consumer(self, **changes):
        f = self.f
        f.store = DurableDemoOrderConsumer(f.root, issuer=f.issuer(token=self.token(), **changes),
            guard=lambda: None, milliseconds=lambda: f.case.now)
        return f.store

    def test_signed_market_consumer_dispatches_once_and_reconciles_real_journal(self):
        c = self.f.case
        result = c.dispatch(c.dispatcher(authorize_once=self.consumer()))
        self.assertEqual(result.outcome, "acknowledged")
        body = json.loads(c.sent[0].body)
        self.assertEqual(body["orderType"], "market")
        self.assertNotIn("force", body); self.assertNotIn("price", body)
        self.assertEqual(len(list(self.f.root.glob("consumed-*.json"))), 1)
        receipt = c.box.accept_observation(c.order.command_id, response(market_detail(c.order,
            cTime=str(c.now), uTime=str(c.now))),
            context=OWNER, expected_revision=c.box.receipt.revision, now_ms=c.now)
        c.box.close()
        c.box = RegisteredDemoOutbox.restore(c.registry, c.directory, binding=c.spec.binding,
            outbox_id=UUID(int=93), context=OWNER, minimum_receipt=receipt)
        trace = c.box.traces(context=OWNER)[0]
        self.assertEqual(trace.observation.average_price, Decimal(70000))
        self.assertIsNone(trace.observation.reported_fee)
        with self.assertRaises(DemoRejected): c.dispatch(c.dispatcher(authorize_once=self.f.store))
        self.assertEqual(len(c.sent), 1)

    def test_limit_consent_domain_denied_before_storage_and_secret_access(self):
        f = self.f
        with self.assertRaises(DemoRejected):
            f.issue(f.issuer(token=f.token()))
        self.assertEqual(f.case.reads, 0)
        old = consent.DemoBTCTestConsentVerifier(key=consent.KEY,
            oidc_issuer=f.verifier.oidc_issuer, origin=f.verifier.origin)
        with self.assertRaises(DemoRejected):
            old.verify(f.context, self.token(), f.body, f.case.order, f.case.box.receipt, f.case.now)

    def test_changed_market_plan_or_stale_quote_denied_before_issuer_snapshot(self):
        f = self.f
        for changes in (dict(reference_price=Decimal(61000)), dict(quantity=Decimal("0.0002")),
                        dict(observed_ms=f.case.now-30001), dict(before_quantity=Decimal("0.0001")),
                        dict(action="reduce_long", before_quantity=Decimal("0.0003"))):
            with self.subTest(changes=changes), self.assertRaises(DemoRejected):
                f.issue(f.issuer(token=self.token()), order=replace(f.case.order, **changes))
        self.assertEqual(f.case.reads, 0)

    def test_human_proposal_window_and_expiry_separate_from_fresh_native_source(self):
        f = self.f
        f.case.now += 5001
        approval = f.issue(f.issuer(token=self.token()))
        self.assertEqual(approval.intent.intent_digest, f.case.order.intent_digest)
        self.assertEqual(f.case.reads, 2)
        f.case.reads = 0
        f.case.now += 25000
        with self.assertRaises(DemoRejected):
            f.issue(f.issuer(token=self.token()))
        self.assertEqual(f.case.reads, 0)

    def test_unknown_after_send_survives_restore_without_market_resend(self):
        c = self.f.case
        def fail(request):
            c.sent.append(request)
            raise TimeoutError()
        result = c.dispatch(c.dispatcher(authorize_once=self.consumer(), order_transport=fail))
        self.assertEqual(result.outcome, "outcome_unknown")
        c.box.close()
        c.box = RegisteredDemoOutbox.restore(c.registry, c.directory, binding=c.spec.binding,
            outbox_id=UUID(int=93), context=OWNER, minimum_receipt=result.minimum_receipt)
        with self.assertRaises(DemoRejected): c.dispatch()
        self.assertEqual(len(c.sent), 1)


class MarketAdmissionTests(unittest.TestCase):
    def setUp(self):
        f = self.f = account_fixture.DemoAccountTests(); f.setUp(); f.btc_test()
        del f.wallet[0]["grant"]
        with patch("investalo_credential_store.demo_account_sync.time.sleep"):
            result = f.run_read()
        self.readiness = result["readiness"]
        self.wallet = parse.futures_accounts(response(f.wallet), ProductType.USDT)[0][0]
        self.now = int(__import__("time").time()*1000)
        self.order = market_intent(binding=f.binding, observed_ms=self.now)
        self.market = BTCMarketPreview(self.order.grid, self.order.quantity, self.order.reference_price, self.now)

    def check(self, **changes):
        return check_btc_market_test(**{"intent": self.order, "readiness": self.readiness,
            "wallet": self.wallet, "market": self.market, "now_ms": self.now, **changes})

    def test_only_grant_max_costs_older_scope_unknowns_accepted_for_test(self):
        result = self.check()
        self.assertEqual(result, dict(grant_verified=False, native_market_max_verified=False,
                                     costs_verified=False, pending_scope_verified=False))
        self.assertIsNone(self.wallet.grant)
        self.assertIsNone(self.order.grid.max_market_quantity)

    def test_positive_or_other_unknown_collateral_and_wrong_margin_deny(self):
        for changes in (dict(grant=Decimal(1)), dict(coupon=None), dict(available=None),
                        dict(account_equity=Decimal(9999)), dict(locked=Decimal(1)),
                        dict(asset_mode="union"), dict(unrealized_pnl=Decimal(-1)),
                        dict(margin_coin="SUSDT")):
            with self.subTest(changes=changes), self.assertRaises(DemoRejected):
                self.check(wallet=replace(self.wallet, **changes))

    def test_fresh_quote_raster_and_planning_value_rechecked_without_resizing(self):
        for changes in (dict(observed_ms=self.now-5001), dict(reference_price=Decimal(67000)),
                        dict(reference_price=Decimal(1000)),
                        dict(grid=replace(self.market.grid, quantity_step=Decimal("0.001")))):
            with self.subTest(changes=changes), self.assertRaises(DemoRejected):
                self.check(market=replace(self.market, **changes))

    def test_foreign_account_open_orders_and_nonmatching_configuration_deny(self):
        for field in ("account", "orders", "configurations"):
            data = json.loads(json.dumps(self.readiness))
            if field == "account": data[field]["account_id"] = str(UUID(int=99))
            elif field == "orders": data[field][2]["count"] = 1; data["blockers"].append("orders_present")
            else:
                data[field][0]["matches"] = False; data["blockers"].append("configuration_mismatch")
            data["blockers"].sort()
            with self.subTest(field=field), self.assertRaises(DemoRejected):
                self.check(readiness=data)

    def test_original_native_reader_market_preview_keeps_eleven_fixed_gets_and_unknowns(self):
        f = self.f
        f.sent.clear(); f.market_axes.clear(); f.native.last = None
        f.target["inspection"] = "btc-market"; f.body = json.dumps(f.target).encode()
        with patch("investalo_credential_store.demo_account_sync.time.sleep"):
            report = f.run_read()
        from investalo_credential_store.demo_btc_test_check import validate_btc_market_test
        from investalo_credential_store.private_http import _application_result, DemoTradingAccountHTTPApplication
        from investalo_credential_store.models import StoreContext
        self.assertEqual(validate_btc_market_test(report), report)
        app = DemoTradingAccountHTTPApplication(StoreContext(tenant_id=f.owner.tenant_id,
            user_id=f.owner.user_id, expected_login_role="synthetic"), lambda *args: None, enabled=True)
        self.assertEqual(_application_result(app, report, "account_read"), report)
        self.assertEqual((len(f.sent), len(f.market_axes)), (9, 2))
        self.assertEqual(report["preview"]["order_type"], "market")
        self.assertIsNone(report["preview"]["native_max_market_quantity_btc"])
        self.assertEqual(report["unknown_wallet_fields"], ["grant"])
        self.assertFalse(report["execution_enabled"])
        for changes in (dict(execution_price_guaranteed=True), dict(planning_notional_usdt="20.01"),
                        dict(force="ioc"), dict(estimated_margin_usdt="0")):
            value = {**report, "preview": {**report["preview"], **changes}}
            with self.subTest(changes=changes), self.assertRaises(Exception):
                validate_btc_market_test(value)
