"""Real own journal/Trading AEAD/HMAC, with synthetic actor/native/consent ports."""
from dataclasses import replace
from decimal import Decimal
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import unittest
from uuid import UUID

from investalo_bitget import Credentials
from investalo_bitget.futures_demo import DemoRejected, request_plan
from investalo_bitget.futures_demo_basket import (
    BasketMarketGrid, BasketMarketIntent, BasketRequestPlan, basket_order_detail,
    basket_position_match,
)
from investalo_bitget.futures_demo_market import BTCMarketGrid, BTCMarketIntent
from investalo_bitget.futures_demo_read import SignedDemoReadRequest, HTTPSDemoReadTransport
from investalo_bitget.signing import hmac_sha256_base64
from investalo_credentials import KEKRing
from investalo_credential_store.demo_basket_orders import (
    BasketMarginEvidence, BasketOrderApproval, BasketOrderDispatcher, HTTPSBasketTransport, HTTPSBasketReadTransport,
    SignedBasketRequest, milliseconds,
)
from investalo_credential_store.demo_order_dispatch import DemoOrderApproval, SignedDemoOrderRequest
from investalo_credential_store.demo_trading_provider import DemoTradingSecretSnapshot, SealedDemoTradingProvider
from investalo_credential_store.demo_trading_secret import DemoTradingSecretSpec, seal_demo_trading_secret
from investalo_trading.futures_broker_journal import BrokerEntryJournal
from investalo_trading.futures_capital_grid import CapitalGridRule
from investalo_trading.futures_capital_research import start_capital_research
from investalo_trading.futures_capital_signals import CapitalH1SignalProfile, start_capital_signals
from investalo_trading.futures_ledger import LedgerMark
from investalo_trading.futures_paper_plan import paper_pool_plan
from test_futures_capital_signals import hour
from test_futures_ledger import AT, fixture
from test_futures_demo import OWNER, OTHER, BINDING, response

D = Decimal
JOURNAL_ID = UUID(int=400)


def native_profile():
    names = ("BNBUSDT", "BTCUSDT", "ETHUSDT")
    contracts = tuple(replace(c, symbol=s, quantity_step=D(".0001"), minimum_quantity=D(".0001"),
                              minimum_notional=D(5)) for c, s in zip(fixture().plan.contracts, names, strict=True))
    plan = paper_pool_plan(str(OWNER.tenant_id), str(BINDING.account_id), "synthetic-native-grid", contracts,
        tuple(CapitalGridRule(s, D(".1"), D(10)) for s in names), "d" * 64, initial_slots=3, configured_limit=3)
    return CapitalH1SignalProfile(plan, 1, D(0), "synthetic-native-assumptions")


def opened_journal(path):
    profile = native_profile()
    marks = tuple(LedgerMark(s, D(61000)) for s in profile.plan.symbols)
    journal = BrokerEntryJournal.create(path, profile, marks, marks, AT, "synthetic-native-initial",
                                       journal_id=JOURNAL_ID)
    for i in range(16):
        frame = hour(journal.state.book.signal, D(64000) - i * 200, all_assets=True)
        journal.append("hour", expected_revision=journal.state.revision, at=frame.close_time, frame=frame)
    journal.append("prepare", expected_revision=journal.state.revision, at=journal.state.as_of,
                   symbol="BTCUSDT", planning_price=D(61000), command_id="native-entry-1")
    return journal


class BasketNativeTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.path = Path(self.temp.name) / "basket"
        self.journal = opened_journal(self.path)
        self.now = milliseconds(self.journal.state.as_of)
        self.spec = DemoTradingSecretSpec(binding=BINDING, parent_uid="0", egress_ip="192.0.2.8",
            authorities=("coow", "cpow", "stow"), provisioning_digest="d"*64, credential_revision=1)
        self.ring = KEKRing((("synthetic", b"K"*32),), active_version="synthetic")
        self.credentials = Credentials("synthetic-api", "synthetic-secret", "synthetic-pass")
        self.snapshot = DemoTradingSecretSnapshot(
            self.spec, seal_demo_trading_secret(self.credentials, self.spec, self.ring), storage_version=1)
        self.events, self.sent, self.reads = [], [], []
        self.revoked = False
        def load(binding, context):
            self.events.append("snapshot")
            if self.revoked:
                raise ValueError("synthetic revoked")
            return self.snapshot
        self.provider = SealedDemoTradingProvider(self.spec, expected_storage=1,
            read_snapshot=load, load_keyring=lambda: self.ring, expires_ms=self.now+30000,
            milliseconds=lambda: self.now)
        self.mutex = threading.Lock()
        self.detail_changes = {}
        self.position_changes = {}
        self.margin_known = True
        self.margin_amount = D("292.8")
        self.load_snapshot = load
        self.intent = None
        self.fail_post = False

    def tearDown(self):
        self.journal.close()
        self.temp.cleanup()

    def approval(self, intent, receipt, context):
        self.events.append("consume-basket")
        self.intent = intent
        return BasketOrderApproval(UUID(int=401+self.journal.state.revision), intent, receipt, credential_revision=1,
                                   storage_version=1, granted_ms=self.now, expires_ms=self.now+15000)

    def send(self, packet):
        self.assertEqual(json.loads(self.path.read_bytes().splitlines()[-1])["command"]["kind"], "attempt")
        self.assertEqual(self.journal.state.recovery_mode, "get_only")
        packet.consume()
        self.sent.append(packet)
        if self.fail_post:
            raise OSError("synthetic lost ACK")
        return response(dict(clientOid=packet.plan.intent.client_oid, orderId="123"), at=self.now)

    def native(self, packet):
        self.reads.append(packet)
        if type(packet) is SignedDemoReadRequest:
            return response(dict(userId="123456", parentId=0, ips="", authorities=["coow", "cpow", "stow"]),
                            at=self.now)
        packet.consume()
        order = packet.plan.intent
        if packet.plan.operation == "detail":
            return response({"symbol": "btcusdt", "clientOid": order.client_oid, "orderId": "123",
                "marginCoin": "usdt", "marginMode": "isolated", "posMode": "one_way_mode", "posSide": "net",
                "leverage": "2", "size": str(order.quantity), "side": "buy", "reduceOnly": "no", "orderType": "market",
                "state": "filled", "baseVolume": str(order.quantity), "priceAvg": "61000",
                "fee": "-0.35136", "cTime": str(milliseconds(self.journal.state.current_attempt.attempted_at)),
                "uTime": str(self.now), **self.detail_changes}, at=self.now)
        return response([{"symbol": "BTCUSDT", "marginCoin": "USDT", "holdSide": "long",
            "marginMode": "isolated", "posMode": "one_way_mode", "leverage": "2", "total": str(order.quantity),
            "available": self.position_changes.get("total", str(order.quantity)), "locked": "0",
            "openPriceAvg": "61000", "marginSize": "999999", **self.position_changes}], at=self.now)

    def margin(self, intent, observation, positions, context):
        if not self.margin_known:
            return None
        # Explicit synthetic source witness, deliberately unrelated to marginSize.
        return BasketMarginEvidence(intent.order_digest, "e" * 64, observation.quantity, self.margin_amount, self.now)

    def dispatcher(self, **changes):
        return BasketOrderDispatcher(self.journal, self.provider, **{
            "read_transport": self.native, "order_transport": self.send, "native_guard": lambda: None,
            "account_guard": lambda *_: self.events.append("native-admission"), "authorize_once": self.approval,
            "margin_resolver": self.margin, "shared_lock": self.mutex, "ip_binding": "unavailable_in_demo",
            "enabled": True, "milliseconds": lambda: self.now, **changes})

    def dispatch(self, **changes):
        return self.dispatcher(**changes).dispatch(context=OWNER, expected_revision=self.journal.state.revision)

    def observe(self, dispatcher=None):
        return (dispatcher or self.dispatcher()).observe(context=OWNER, expected_revision=self.journal.state.revision)

    def test_margin_times2_native_market_body_own_namespace_and_actual_hmac(self):
        self.assertEqual(self.dispatch(), "acknowledged")
        packet = self.sent[0]
        terms = json.loads(packet.body)
        self.assertEqual((terms["orderType"], terms["side"], terms["reduceOnly"]), ("market", "buy", "NO"))
        self.assertEqual((terms["marginMode"], terms["marginCoin"]), ("isolated", "USDT"))
        self.assertNotIn("force", terms)
        self.assertNotIn("price", terms)
        self.assertEqual(terms["size"], "0.0096")
        self.assertGreater(D(terms["size"]) * 61000, 20)
        self.assertTrue(terms["clientOid"].startswith("ivb"))
        self.assertEqual(packet.headers["paptrading"], "1")
        self.assertEqual(packet.headers["ACCESS-SIGN"], hmac_sha256_base64(b"synthetic-secret",
            str(self.now).encode() + b"POST" + packet.target.encode() + packet.body))
        self.assertLess(self.events.index("consume-basket"), self.events.index("snapshot"))
        self.assertEqual(self.journal.state.book.signal.economic.stages, ())
        self.assertEqual(self.journal.state.current_attempt.request_digest, packet.plan.request_digest)

    def test_actual_raw_fill_fee_and_confirmed_margin_reach_the_shared_ledger_once(self):
        self.dispatch()
        self.observe()
        basket = self.journal.state.book.signal.economic.ledger.baskets[1]
        self.assertEqual((basket.quantity, basket.average_entry, basket.margin_committed, basket.entry_fees),
                         (D(".0096"), D(61000), D("292.8"), D(".35136")))
        self.assertEqual(len(self.journal.state.book.signal.economic.stages), 1)
        self.assertIsNone(self.journal.state.book.pending)
        with self.assertRaises(DemoRejected):
            self.observe()

    def test_lost_ack_restart_get_only_native_original_clientoid_recovery(self):
        self.fail_post = True
        self.assertEqual(self.dispatch(), "outcome_unknown")
        anchor = self.journal.receipt
        self.journal.close()
        self.journal = BrokerEntryJournal.restore(self.path, journal_id=JOURNAL_ID,
            profile_digest=native_profile().profile_digest, minimum_receipt=anchor)
        with self.assertRaisesRegex(DemoRejected, "resend"):
            self.dispatch()
        self.observe()
        self.assertEqual(len(self.sent), 1)
        details = [p for p in self.reads if type(p) is SignedBasketRequest and p.plan.operation == "detail"]
        self.assertEqual(len(details), 1)
        self.assertIn(self.intent.client_oid, details[0].target)
        self.assertEqual(len(self.journal.state.book.signal.economic.stages), 1)

    def test_native_marginSize_is_never_taken_as_new_stage_capital(self):
        self.dispatch()
        self.margin_known = False
        self.observe()
        self.assertIsNotNone(self.journal.state.book.pending)
        self.assertIsNone(self.journal.state.book.observation.posted_margin)
        self.assertTrue(self.journal.state.book.observation.position_matches)
        self.assertEqual(self.journal.state.book.signal.economic.stages, ())

    def test_unknown_fee_can_be_completed_after_restart_without_resend(self):
        self.dispatch()
        self.detail_changes = {"fee": ""}
        self.observe()
        anchor = self.journal.receipt
        self.assertIsNone(self.journal.state.book.observation.signed_fee)
        self.journal.close()
        self.journal = BrokerEntryJournal.restore(self.path, journal_id=JOURNAL_ID,
            profile_digest=native_profile().profile_digest, minimum_receipt=anchor)
        self.detail_changes = {}
        self.observe()
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(len(self.journal.state.book.signal.economic.stages), 1)

    def test_changed_native_order_identity_is_pinned_across_restart(self):
        self.dispatch()
        self.margin_known = False
        self.observe()
        anchor = self.journal.receipt
        self.journal.close()
        self.journal = BrokerEntryJournal.restore(self.path, journal_id=JOURNAL_ID,
            profile_digest=native_profile().profile_digest, minimum_receipt=anchor)
        self.margin_known = True
        self.detail_changes = {"orderId": "456"}
        with self.assertRaisesRegex(ValueError, "native order"):
            self.observe()
        self.assertEqual(self.journal.receipt, anchor)
        self.assertEqual(self.journal.state.book.signal.economic.stages, ())

    def test_partial_native_observations_book_one_stage_only_on_terminal_cancellation(self):
        self.dispatch()
        self.detail_changes = {"state": "partially_filled", "baseVolume": "0.0048"}
        self.position_changes = {"total": "0.0048"}
        self.observe()
        self.assertEqual(self.journal.state.book.signal.economic.stages, ())
        self.now += 1
        self.detail_changes["state"] = "canceled"
        self.observe()
        self.assertEqual(len(self.journal.state.book.signal.economic.stages), 1)
        self.assertEqual(self.journal.state.book.signal.economic.stages[0].quantity, D(".0048"))
        self.assertEqual(len(self.sent), 1)

    def test_position_average_or_product_profile_mismatch_stays_unconfirmed(self):
        self.dispatch()
        for changes in ({"openPriceAvg": "60000"}, {"marginMode": "crossed"},
                        {"posMode": "hedge_mode"}, {"leverage": "10"}, {"total": "0.0095"}):
            self.position_changes = changes
            self.observe()
            self.assertFalse(self.journal.state.book.observation.position_matches)
            self.assertEqual(self.journal.state.book.signal.economic.stages, ())
        self.position_changes = {}
        self.observe()
        self.assertIsNone(self.journal.state.book.pending)

    def test_before_admission_denial_has_no_consumption_decryption_marker_or_post(self):
        def denied(*_):
            raise ValueError("synthetic native max/costs unknown")
        before = self.journal.receipt
        with self.assertRaises(ValueError):
            self.dispatch(account_guard=denied)
        self.assertNotIn("consume-basket", self.events)
        self.assertNotIn("snapshot", self.events)
        self.assertEqual(self.journal.receipt, before)
        self.assertEqual(self.sent, [])

    def test_revocation_and_expired_source_cannot_turn_ack_into_a_fill(self):
        def revoke_after_post(packet):
            result = self.send(packet)
            self.revoked = True
            return result
        self.assertEqual(self.dispatch(order_transport=revoke_after_post), "outcome_unknown")
        self.assertEqual(len(self.sent), 1)
        self.assertEqual(self.journal.state.book.signal.economic.stages, ())
        with self.assertRaises(Exception):
            self.observe()

    def test_default_off_foreign_context_busy_and_wrong_approval_do_not_send(self):
        with self.assertRaises(DemoRejected):
            self.dispatch(enabled=False)
        with self.assertRaises(DemoRejected):
            self.dispatcher().dispatch(context=OTHER, expected_revision=self.journal.state.revision)
        with self.assertRaises(DemoRejected):
            self.dispatch(authorize_once=lambda *_: object())
        self.mutex.acquire()
        try:
            with self.assertRaisesRegex(DemoRejected, "busy"):
                self.dispatch()
        finally:
            self.mutex.release()
        self.assertEqual(self.sent, [])
        self.assertEqual(self.journal.state.attempts, ())

    def test_legacy_read_limit_and_small_test_domains_reject_basket_packets(self):
        self.dispatch()
        packet, intent = self.sent[0], self.sent[0].plan.intent
        with self.assertRaises(DemoRejected):
            request_plan(intent, "place", context=OWNER)
        with self.assertRaises(DemoRejected):
            HTTPSDemoReadTransport()(packet)
        lease = self.provider(BINDING, OWNER)
        with self.assertRaises(DemoRejected):
            SignedDemoOrderRequest(lease, intent, "place", timestamp_ms=self.now)
        with self.assertRaises(DemoRejected):
            DemoOrderApproval(UUID(int=405), intent, object(), credential_revision=1, storage_version=1,
                              granted_ms=self.now, expires_ms=self.now+15000)
        tiny = BTCMarketIntent(BINDING, UUID(int=406),
            BTCMarketGrid("BTCUSDT", D(".0001"), D(".0001"), D(5), None),
            "open_long", D(".0003"), D(61000), D(0), self.now)
        with self.assertRaises(DemoRejected):
            BasketRequestPlan(tiny, "place")
        with self.assertRaises(DemoRejected):
            SignedBasketRequest(lease, tiny, "place", timestamp_ms=self.now)
        with self.assertRaises(DemoRejected):
            HTTPSBasketTransport()(object())

    def test_mutated_and_reused_signed_packets_cannot_send_twice(self):
        self.dispatch()
        packet = self.sent[0]
        with self.assertRaises(DemoRejected):
            packet.consume()
        lease = self.provider(BINDING, OWNER)
        forged = SignedBasketRequest(lease, packet.plan.intent, "place", timestamp_ms=self.now)
        object.__setattr__(forged, "body", b'{"side":"sell"}')
        with self.assertRaises(DemoRejected):
            forged.consume()

    def test_all_seven_native_symbols_and_no_silent_cap_or_wrong_margin_sizing(self):
        self.dispatch()
        intent = self.intent
        for symbol in ("AVAXUSDT", "BNBUSDT", "BTCUSDT", "ETHUSDT", "LINKUSDT", "SOLUSDT", "XRPUSDT"):
            valid = replace(intent, grid=replace(intent.grid, symbol=symbol))
            self.assertEqual(json.loads(BasketRequestPlan(valid, "place").body)["symbol"], symbol)
        for changes in ({"quantity": D(".0003")}, {"stage": 6}, {"before_quantity": D(1)},
                        {"grid": replace(intent.grid, max_market_quantity=D(".0001"))}):
            with self.subTest(changes=changes), self.assertRaises(DemoRejected):
                replace(intent, **changes)
        with self.assertRaises(DemoRejected):
            BasketMarketGrid("BTCUSDT", D(".0001"), D(".1"), D(".0001"), D(5), None)

    def test_next_native_buy_uses_real_rsi_rearm_and_reconciles_averaged_position(self):
        self.dispatch()
        self.observe()
        for price in [D(61000)] * 20 + [D(63440), D(57950)]:
            frame = hour(self.journal.state.book.signal, price, all_assets=True)
            self.journal.append("hour", expected_revision=self.journal.state.revision,
                                at=frame.close_time, frame=frame)
        self.now = milliseconds(self.journal.state.as_of)
        self.provider = SealedDemoTradingProvider(self.spec, expected_storage=1,
            read_snapshot=self.load_snapshot, load_keyring=lambda: self.ring, expires_ms=self.now+30000,
            milliseconds=lambda: self.now)
        self.journal.append("prepare", expected_revision=self.journal.state.revision, at=self.journal.state.as_of,
                            symbol="BTCUSDT", planning_price=D(57950), command_id="native-entry-2")
        self.assertEqual(self.journal.state.book.pending.request.posted_margin, D("366.41707366"))
        self.detail_changes = {"orderId": "456", "priceAvg": "57950", "fee": "-0.4"}
        average = (D(".0096") * 61000 + D(".0126") * 57950) / D(".0222")
        self.position_changes = {"total": "0.0222", "openPriceAvg": str(average)}
        self.margin_amount = D("365.085")
        self.dispatch()
        self.observe()
        self.assertEqual(json.loads(self.sent[-1].body)["size"], "0.0126")
        self.assertEqual(len(self.journal.state.book.signal.economic.stages), 2)
        basket = self.journal.state.book.signal.economic.ledger.baskets[1]
        self.assertEqual(basket.quantity, D(".0222"))
        self.assertEqual(basket.entry_fees, D(".75136"))
        self.assertEqual(basket.average_entry.quantize(D(".00000001")), average.quantize(D(".00000001")))

    def test_margin_evidence_requires_original_order_quantity_and_fresh_source(self):
        self.dispatch()
        for bad in (
            BasketMarginEvidence("f"*64, "e"*64, D(".0096"), D("292.8"), self.now),
            BasketMarginEvidence(self.intent.order_digest, "e"*64, D(".0048"), D("146.4"), self.now),
            BasketMarginEvidence(self.intent.order_digest, "e"*64, D(".0096"), D("292.8"), self.now+1),
        ):
            with self.subTest(bad=bad), self.assertRaisesRegex(DemoRejected, "margin"):
                self.observe(self.dispatcher(margin_resolver=lambda *_: bad))
        self.assertEqual(self.journal.state.book.signal.economic.stages, ())
        self.observe()
        self.assertIsNone(self.journal.state.book.pending)

    def test_native_update_clock_and_fee_cannot_be_rewritten_at_same_version(self):
        self.dispatch()
        self.margin_known = False
        self.observe()
        before = self.journal.receipt
        self.detail_changes = {"fee": "-0.8"}
        with self.assertRaisesRegex(ValueError, "native order"):
            self.observe()
        self.assertEqual(self.journal.receipt, before)
        self.detail_changes = {"cTime": str(self.now-1)}
        with self.assertRaises(DemoRejected):
            self.observe()
        self.assertEqual(self.journal.receipt, before)

    def test_own_read_transport_rejects_market_post_and_foreign_packets_before_network(self):
        self.dispatch()
        with self.assertRaisesRegex(DemoRejected, "get_only"):
            HTTPSBasketReadTransport()(self.sent[0])
        with self.assertRaises(DemoRejected):
            HTTPSBasketReadTransport()(object())


if __name__ == "__main__":
    unittest.main()
