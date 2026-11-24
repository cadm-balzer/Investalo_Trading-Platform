"""Actual original journal/AEAD/GET packets; synthetic native cash and bill replies."""
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
import json
import unittest

import test_demo_basket_margin as margin_fixture
import test_demo_basket_orders as order_fixture
from test_futures_demo import OWNER, response
from investalo_bitget import parse
from investalo_bitget.futures_demo import DemoRejected
from investalo_bitget.futures_demo_basket import BasketFundingIntent, BasketRequestPlan
from investalo_bitget.futures_demo_funding import funding_batch
from investalo_bitget.futures_demo_read import SignedDemoReadRequest
from investalo_credential_store.demo_basket_funding import BasketNativeFundingSource
from investalo_credential_store.demo_basket_margin import BasketNativeMarginSource
from investalo_credential_store.demo_basket_orders import SignedBasketRequest, BasketOrderApproval, milliseconds
from investalo_trading.futures_broker_journal import BrokerEntryJournal
from investalo_trading.futures_broker_funding import BrokerFundingBatch, record_broker_funding
from investalo_trading.futures_broker_entries import (
    observe_broker_prices, prepare_broker_entry, observe_broker_entry, BrokerEntryObservation,
)
from investalo_trading.futures_ledger import BrokerFundingBasket, LedgerBasket, LedgerMark
from investalo_trading.snapshot import primitive

D = Decimal


class NativeFundingTests(unittest.TestCase):
    def setUp(self):
        self.m = margin_fixture.NativeMarginTests()
        self.m.setUp()
        self.m.dispatch(); self.m.observe()
        self.f = self.m.f
        self.before = self.f.journal.state
        self.payment = D("-.12")
        self.isolated = D(0)
        self.wallet_changes = {}
        self.position_changes = {}
        self.bill_changes = {}
        self.rows = None
        self.pages = None
        self.packets = []
        self.revoke_at = None
        self.fixed_order_time = self.f.now + 10
        self.f.now += 20
        self.reader = BasketNativeMarginSource(transport=self.native, milliseconds=lambda: self.f.now)
        self.source = BasketNativeFundingSource(self.reader)
        self.dispatcher = self.f.dispatcher(read_transport=self.native, order_transport=self.no_post,
            funding_source=self.source)

    def tearDown(self):
        self.m.tearDown()

    def no_post(self, packet):
        self.fail("funding read must never POST")

    def wallet(self):
        return {**dict(marginCoin="USDT", assetMode="single", locked="0", crossedMargin="0", coupon="0", grant="0",
            accountEquity=str(D("9999.64864")+self.payment+17), unrealizedPL="17",
            isolatedMargin=str(D("292.8")+self.isolated)), **self.wallet_changes}

    def position(self):
        return {**dict(symbol="BTCUSDT", marginCoin="USDT", holdSide="long", marginMode="isolated",
            posMode="one_way_mode", leverage="2", assetMode="single", autoMargin="off", openDelegateSize="0",
            total="0.0096", available="0.0096", locked="0", openPriceAvg="61000",
            marginSize=str(D("292.8")+self.isolated), totalFee=str(self.payment),
            deductedFee="0.35136", achievedProfits="0"), **self.position_changes}

    def bill(self, key="300", amount=None, **changes):
        return {**dict(billId=key, symbol="BTCUSDT", amount=str(self.payment if amount is None else amount),
            fee="0", feeByCoupon="", businessType="contract_settle_fee", coin="USDT", balance="9999.52864",
            cTime=str(self.fixed_order_time)), **changes}

    def native(self, packet):
        self.f.now += 1
        if type(packet) is SignedDemoReadRequest:
            return self.f.native(packet)
        self.assertIs(type(packet), SignedBasketRequest)
        self.assertEqual(packet.method, "GET")
        self.assertIs(type(packet.plan.intent), BasketFundingIntent)
        self.packets.append(packet)
        packet.consume()
        op = packet.plan.operation
        if op == self.revoke_at:
            self.f.revoked = True
        if op == "wallet":
            return response([self.wallet()], at=self.f.now)
        if op == "positions":
            return response([self.position()], at=self.f.now)
        self.assertEqual(op, "bills")
        self.assertIn("onlyFunding=no", packet.target)
        self.assertEqual(packet.plan.start_ms, self.f.journal.state.funding_checked_ms)
        if self.pages is not None:
            data = self.pages.pop(0)
        else:
            rows = [] if packet.plan.cursor is not None else (
                self.rows if self.rows is not None else [{**self.bill(), **self.bill_changes}])
            data = dict(bills=rows, endId=min((row["billId"] for row in rows), key=int) if rows else None)
        return response(data, at=self.f.now)

    def read(self):
        return self.dispatcher.funding(context=OWNER, expected_revision=self.f.journal.state.revision)

    def test_actual_wallet_payment_preserves_margin_and_tracks_own_cash_cost(self):
        result = self.read()
        old = self.before.book.signal.economic.ledger.baskets[1]
        ledger = result.book.signal.economic.ledger
        b = ledger.baskets[1]
        self.assertIs(type(b), BrokerFundingBasket)
        self.assertEqual((b.quantity, b.margin_committed, b.isolated_balance),
                         (old.quantity, old.margin_committed, old.isolated_balance))
        self.assertEqual((b.funding_net, b.funding_wallet_cost), (D("-.12"), D(".12")))
        self.assertEqual(ledger.unposted_cash, self.before.book.signal.economic.ledger.unposted_cash-D(".12"))
        self.assertEqual(b.last_funding_at, parse.EPOCH+timedelta(milliseconds=self.fixed_order_time))
        self.assertEqual(len(result.funding_ids), 1)
        self.assertGreater(result.funding_checked_ms, self.before.funding_checked_ms)
        self.assertEqual(result.book.signal.signals, self.before.book.signal.signals)
        self.assertEqual(ledger.plan.basket_cost_usage(b), D(".47136"))
        self.assertEqual(ledger.reserve_shortfall, self.before.book.signal.economic.ledger.reserve_shortfall)
        self.assertTrue(all(p.plan.operation in ("wallet", "positions", "bills") for p in self.packets))

    def test_isolated_payment_never_becomes_stage_principal_or_wallet_debit(self):
        self.isolated = self.payment
        result = self.read()
        b = result.book.signal.economic.ledger.baskets[1]
        self.assertEqual((b.isolated_balance, b.margin_committed, b.funding_wallet_cost),
                         (D("292.68"), D("292.8"), D(0)))
        self.assertEqual(result.book.signal.economic.ledger.unposted_cash,
                         self.before.book.signal.economic.ledger.unposted_cash)
        self.assertEqual(result.book.signal.economic.stages, self.before.book.signal.economic.stages)

    def test_partial_margin_and_wallet_payment_reconciles_both_sources(self):
        self.isolated = D("-.05")
        result = self.read()
        b = result.book.signal.economic.ledger.baskets[1]
        self.assertEqual((b.funding_wallet_cost, b.isolated_balance), (D(".07"), D("292.75")))
        self.assertEqual(result.book.signal.economic.ledger.unposted_cash,
                         self.before.book.signal.economic.ledger.unposted_cash-D(".07"))

    def test_received_funding_in_wallet_or_isolated_is_actual_credit(self):
        self.payment = D(".2")
        result = self.read()
        b = result.book.signal.economic.ledger.baskets[1]
        self.assertEqual((b.funding_net, b.funding_wallet_cost, b.isolated_balance), (D(".2"), D(0), D("292.8")))
        self.assertEqual(result.book.signal.economic.ledger.unposted_cash,
                         self.before.book.signal.economic.ledger.unposted_cash+D(".2"))

    def test_complete_empty_window_advances_cursor_without_financial_or_indicator_event(self):
        self.payment = D(0); self.rows = []
        result = self.read()
        self.assertEqual(result.book.signal, self.before.book.signal)
        self.assertFalse(result.funding_ids)
        self.assertGreater(result.funding_checked_ms, self.before.funding_checked_ms)

    def test_unknown_or_non_funding_bill_never_advances_original_cursor(self):
        for changes in ({"businessType":"buy"}, {"businessType":"auto_append_margin"},
                        {"businessType":"trans_from_exchange"}, {"symbol":"ETHUSDT"}, {"fee":"-0.01"},
                        {"feeByCoupon":"0.01"}, {"amount":None}):
            with self.subTest(changes=changes):
                self.bill_changes = changes
                self.assertIsNone(self.read())
                self.assertEqual(self.f.journal.state, self.before)

    def test_unconfirmed_wallet_or_profile_does_not_book(self):
        for changes in ({"grant":None}, {"coupon":"1"}, {"assetMode":"union"}, {"isolatedMargin":None}):
            with self.subTest(changes=changes):
                self.wallet_changes = changes
                self.assertIsNone(self.read())
                self.assertEqual(self.f.journal.state, self.before)
        self.wallet_changes = {}
        self.position_changes["autoMargin"] = "on"
        self.assertIsNone(self.read())

    def test_native_cash_or_position_counter_mismatch_keeps_file_and_cursor_unchanged(self):
        raw = self.f.path.read_bytes()
        for field, value in (("totalFee","-0.13"), ("deductedFee","0.36"), ("achievedProfits","1"),
                             ("marginSize","293.8")):
            with self.subTest(field=field):
                self.position_changes = {field:value}
                self.wallet_changes = {"isolatedMargin":"293.8"} if field == "marginSize" else {}
                with self.assertRaises(ValueError): self.read()
                self.assertEqual(self.f.path.read_bytes(), raw)
        self.position_changes = {}
        self.wallet_changes = {}
        self.position_changes["total"] = "0.0097"
        self.assertIsNone(self.read())
        self.assertEqual(self.f.path.read_bytes(), raw)
        self.position_changes = {}
        self.wallet_changes["accountEquity"] = "10017.52864"
        with self.assertRaises(ValueError): self.read()
        self.assertEqual(self.f.path.read_bytes(), raw)

    def test_multiple_same_time_bills_are_canonical_and_booked_atomically_once(self):
        self.rows = [self.bill("302", D("-.07")), self.bill("301", D("-.05"))]
        result = self.read()
        self.assertEqual(len(result.funding_ids), 2)
        self.assertEqual(result.book.signal.economic.ledger.baskets[1].funding_net, D("-.12"))
        last = json.loads(self.f.path.read_bytes().splitlines()[-1])
        self.assertEqual(last["command"]["kind"], "funding")
        self.assertEqual(len(last["command"]["arguments"]["batch"]["bills"]), 2)
        # Native API cannot reintroduce an old bill outside the next original window.
        self.assertIsNone(self.read())
        self.assertEqual(self.f.journal.state, result)

    def test_duplicate_native_ids_and_unfinished_pagination_never_publish(self):
        self.rows = [self.bill("300", D("-.06")), self.bill("300", D("-.06"))]
        self.assertIsNone(self.read())
        self.rows = None
        self.pages = [dict(bills=[self.bill(str(400-i), D(0))], endId=str(400-i)) for i in range(8)]
        self.assertIsNone(self.read())
        self.assertEqual(self.f.journal.state, self.before)

    def test_bill_native_time_before_original_covered_window_cannot_be_adopted(self):
        self.bill_changes["cTime"] = str(self.before.funding_checked_ms-1)
        self.assertIsNone(self.read())
        self.assertEqual(self.f.journal.state, self.before)

    def test_restore_exact_cash_cost_bill_ids_cursor_then_repeat_rejected(self):
        result = self.read()
        original_receipt = self.f.journal.receipt
        self.f.journal.close()
        self.f.journal = BrokerEntryJournal.restore(self.f.path, journal_id=order_fixture.JOURNAL_ID,
            profile_digest=order_fixture.native_profile().profile_digest, minimum_receipt=original_receipt)
        self.assertEqual(self.f.journal.state, result)
        self.dispatcher = self.f.dispatcher(read_transport=self.native, order_transport=self.no_post,
            funding_source=self.source)
        self.assertIsNone(self.read())
        self.assertEqual(self.f.journal.receipt, original_receipt)

    def test_read_only_funding_scope_cannot_send_or_receive_order_approval(self):
        self.read()
        intent = self.packets[0].plan.intent
        for operation in ("place", "detail"):
            with self.assertRaises(DemoRejected): BasketRequestPlan(intent, operation)
        with self.assertRaises(DemoRejected):
            BasketOrderApproval(order_fixture.UUID(int=7), intent, self.f.journal.receipt,
                credential_revision=1, storage_version=1, granted_ms=self.f.now, expires_ms=self.f.now+1000)
        with self.assertRaises(DemoRejected):
            BasketRequestPlan(intent, "bills", start_ms=intent.from_ms-1, end_ms=self.f.now)

    def test_actor_revocation_during_bill_read_cannot_publish(self):
        self.revoke_at = "bills"
        with self.assertRaises(ValueError): self.read()
        self.assertEqual(self.f.journal.state, self.before)

    def test_pending_order_shared_mutex_and_default_off_deny_funding(self):
        self.f.mutex.acquire()
        try:
            with self.assertRaises(DemoRejected): self.read()
        finally:
            self.f.mutex.release()
        inactive = self.f.dispatcher(read_transport=self.native, enabled=False, funding_source=self.source)
        with self.assertRaises(DemoRejected):
            inactive.funding(context=OWNER, expected_revision=self.f.journal.state.revision)
        self.f.now += 1
        marks = tuple(LedgerMark(s, D(61000)) for s in self.f.journal.state.book.signal.profile.plan.symbols)
        self.f.journal.append("prices", expected_revision=self.f.journal.state.revision,
            at=parse.EPOCH+timedelta(milliseconds=self.f.now), trade=marks, marks=marks, event_id="fresh-before-pending")
        self.f.journal.append("prepare", expected_revision=self.f.journal.state.revision,
            at=self.f.journal.state.as_of, symbol="BNBUSDT", planning_price=D(61000), command_id="another-entry")
        with self.assertRaises(DemoRejected): self.read()

    def test_legacy_basket_schema_has_no_native_cash_extension(self):
        old = self.before.book.signal.economic.ledger.baskets[1]
        self.assertIs(type(old), LedgerBasket)
        self.assertNotIn("funding_wallet_cost", primitive(old))

    def test_later_native_credit_covers_actual_wallet_cost_without_new_stage_budget(self):
        first = self.read()
        self.fixed_order_time = self.f.now+10
        self.f.now += 20
        self.payment = D(".08")  # Native cumulative total: -.12 + .20.
        self.rows = [self.bill("301", D(".2"))]
        result = self.read()
        b = result.book.signal.economic.ledger.baskets[1]
        self.assertEqual((b.funding_net, b.funding_wallet_cost, b.margin_committed),
                         (D(".08"), D(0), D("292.8")))
        self.assertEqual(result.book.signal.economic.stages, first.book.signal.economic.stages)
        self.assertEqual(len(result.funding_ids), 2)

    def test_isolated_credit_changes_margin_without_spending_unposted_wallet_cash(self):
        self.payment = self.isolated = D(".2")
        result = self.read()
        b = result.book.signal.economic.ledger.baskets[1]
        self.assertEqual((b.funding_net, b.isolated_balance, b.margin_committed),
                         (D(".2"), D("293"), D("292.8")))
        self.assertEqual(result.book.signal.economic.ledger.unposted_cash,
                         self.before.book.signal.economic.ledger.unposted_cash)

    def test_funding_bill_dated_after_native_snapshot_before_ledger_recognition_is_not_lost(self):
        # Original complete financial window ends before its final pagination
        # response. A new funding bill in that small gap must remain readable.
        self.assertLess(self.before.funding_checked_ms, milliseconds(self.before.as_of))
        self.fixed_order_time = self.before.funding_checked_ms+1
        result = self.read()
        self.assertEqual(result.book.signal.economic.ledger.baskets[1].funding_net, D("-.12"))
        self.assertLess(result.book.signal.economic.ledger.baskets[1].last_funding_at,
                        self.before.book.signal.economic.ledger.baskets[1].opened_at)

    def test_real_funding_then_native_reduce_exit_counts_actual_net_once(self):
        funded = self.read()
        posted = False
        def prices(value):
            self.f.now += 1
            marks = tuple(LedgerMark(s,D(value)) for s in funded.book.signal.profile.plan.symbols)
            self.f.journal.append("prices", expected_revision=self.f.journal.state.revision,
                at=parse.EPOCH+timedelta(milliseconds=self.f.now), trade=marks, marks=marks,
                event_id=f"funded-close-{value}")
        prices(65000); prices(61000)
        self.f.journal.append("prepare_exit", expected_revision=self.f.journal.state.revision,
            at=self.f.journal.state.as_of, symbol="BTCUSDT", command_id="funded-close")
        def native(packet):
            self.f.now += 1
            if type(packet) is SignedDemoReadRequest:
                return self.f.native(packet)
            packet.consume()
            op, intent = packet.plan.operation, packet.plan.intent
            if op == "wallet":
                data = [self.wallet()] if not posted else [dict(marginCoin="USDT", assetMode="single",
                    locked="0", crossedMargin="0", coupon="0", grant="0", accountEquity="10008.77152",
                    unrealizedPL="0", isolatedMargin="0")]
            elif op == "positions":
                data = [] if posted else [self.position()]
            elif op == "detail":
                data = dict(symbol="BTCUSDT", clientOid=intent.client_oid, orderId="456",
                    marginCoin="USDT", marginMode="isolated", posMode="one_way_mode", posSide="net", leverage="2",
                    size="0.0096", side="sell", reduceOnly="YES", orderType="market", state="filled",
                    baseVolume="0.0096", priceAvg="62000", fee="-0.35712",
                    cTime=str(milliseconds(self.f.journal.state.current_attempt.attempted_at)), uTime=str(self.f.now))
            else:
                rows = [] if packet.plan.cursor is not None else [dict(billId="400", symbol="BTCUSDT",
                    amount="9.6", fee="-0.35712", feeByCoupon="", businessType="sell", coin="USDT",
                    cTime=str(milliseconds(self.f.journal.state.current_attempt.attempted_at)))]
                data = dict(bills=rows, endId="400" if rows else None)
            return response(data, at=self.f.now)
        def send(packet):
            nonlocal posted
            packet.consume(); posted = True; self.f.now += 1
            return response(dict(clientOid=packet.plan.intent.client_oid), at=self.f.now)
        source = BasketNativeMarginSource(transport=native, milliseconds=lambda:self.f.now)
        dispatcher = self.f.dispatcher(read_transport=native, order_transport=send,
            margin_resolver=None, margin_source=source)
        self.assertEqual(dispatcher.dispatch(context=OWNER, expected_revision=self.f.journal.state.revision),
                         "acknowledged")
        result = dispatcher.observe(context=OWNER, expected_revision=self.f.journal.state.revision)
        self.assertIsNone(result.book.pending)
        ledger = result.book.signal.economic.ledger
        self.assertEqual((ledger.closed_baskets, ledger.realized_net_pnl, ledger.unposted_cash),
                         (1, D("8.77152"), D("10008.77152")))

    def test_two_owned_baskets_native_payment_and_credit_are_atomic(self):
        book = self.before.book
        at = parse.EPOCH+timedelta(milliseconds=self.f.now)
        marks = tuple(LedgerMark(s,D(61000)) for s in book.signal.profile.plan.symbols)
        book = observe_broker_prices(book, marks, marks, "two-funding-marks", book.revision, at)
        pending = prepare_broker_entry(book, "BNBUSDT", D(61000), "synthetic-bnb", book.revision, at)
        quantity = pending.pending.request.quantity
        # Pure original-fill port; native replies are explicitly synthetic.
        book = observe_broker_entry(pending, BrokerEntryObservation(pending.pending.order_digest,
            "filled", quantity, D(61000), D("-.35136"), quantity*61000/2, True, at, "synthetic-bnb-fill"),
            pending.revision, at)
        raw = book.state_digest
        intent = BasketFundingIntent(self.f.spec.binding, order_fixture.JOURNAL_ID, book.state_digest,
            self.before.funding_checked_ms, self.f.now)
        other = {**self.position(), "symbol":"BNBUSDT", "total":str(quantity), "available":str(quantity),
                 "marginSize":str(quantity*61000/2), "totalFee":"0.05"}
        wallet = {**self.wallet(), "accountEquity":"10016.22728", "isolatedMargin":"585.6"}
        page = dict(bills=[self.bill("302"), self.bill("301", D(".05"), symbol="BNBUSDT")], endId="301")
        batch = funding_batch(response([wallet],at=self.f.now+1), response([other,self.position()],at=self.f.now+2),
            (response(page,at=self.f.now+3),response(dict(bills=[],endId=None),at=self.f.now+4)),
            intent,book,context=OWNER,now_ms=self.f.now+4)
        occurred = parse.EPOCH+timedelta(milliseconds=self.f.now+4)
        result = record_broker_funding(book,batch,book.revision,occurred)
        bnb,btc = result.signal.economic.ledger.baskets[:2]
        self.assertEqual((bnb.funding_net,btc.funding_net), (D(".05"),D("-.12")))
        bad = replace(batch.snapshot.positions[1],funding_total=D("-.13"))
        invalid = replace(batch,snapshot=replace(batch.snapshot,positions=(batch.snapshot.positions[0],bad)))
        with self.assertRaises(ValueError): record_broker_funding(book,invalid,book.revision,occurred)
        self.assertEqual(book.state_digest,raw)  # A second-symbol failure publishes no first-symbol mutation.

    def test_mixed_native_pay_and_credit_keep_gross_cost_and_net_amount_distinct(self):
        self.payment = D(".08")
        self.rows = [self.bill("302",D(".2")),self.bill("301",D("-.12"))]
        result = self.read()
        b = result.book.signal.economic.ledger.baskets[1]
        self.assertEqual((b.funding_net,b.funding_wallet_cost,b.charges_in_budget_epoch),
                         (D(".08"),D(0),D(".47136")))


if __name__ == "__main__":
    unittest.main()
