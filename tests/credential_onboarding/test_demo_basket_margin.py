"""Real journal/AEAD/signatures and native parsers; synthetic broker/actor only."""
from dataclasses import replace
from decimal import Decimal
import json
import unittest

import test_demo_basket_orders as native_fixture
from test_futures_demo import OWNER, response
from investalo_bitget.futures_demo import DemoRejected
from investalo_bitget.futures_demo_basket import BasketRequestPlan
from investalo_bitget.futures_demo_read import SignedDemoReadRequest
from investalo_bitget.futures_demo_margin import capture_margin_baseline, reconcile_margin
from investalo_bitget.futures_demo_reconcile import OrderObservation
from investalo_credential_store.demo_basket_margin import BasketNativeMarginSource
from investalo_credential_store.demo_basket_orders import SignedBasketRequest
from investalo_trading.futures_broker_journal import BrokerEntryJournal, VERSION

D = Decimal


class NativeMarginTests(unittest.TestCase):
    def setUp(self):
        self.f = native_fixture.BasketNativeTests()
        self.f.setUp()
        self.posted = False
        self.posts = []
        self.cash_drift = D(0)
        self.upl = D(25)
        self.margin_changes = {}
        self.wallet_changes = {}
        self.bill_changes = {}
        self.bill_pages = None
        self.wallet_reads = []
        self.position_reads = []
        self.revoke_at = None
        self.source = BasketNativeMarginSource(transport=self.native, milliseconds=lambda: self.f.now)
        self.dispatcher = self.f.dispatcher(read_transport=self.native, order_transport=self.send,
            margin_resolver=None, margin_source=self.source)

    def tearDown(self):
        self.f.tearDown()

    def wallet(self):
        quantity = D(self.f.detail_changes.get("baseVolume", self.f.journal.state.book.pending.request.quantity))
        average = D(self.f.detail_changes.get("priceAvg", "61000"))
        fee = D(self.f.detail_changes.get("fee") or "-0.35136")
        margin = quantity * average / 2 if self.posted else D(0)
        if self.posted:
            margin = D(self.margin_changes.get("marginSize", str(margin)))
        return {**dict(marginCoin="USDT", assetMode="single", locked="0", crossedMargin="0", coupon="0", grant="0",
            accountEquity=str(D(10000)+self.upl+fee+self.cash_drift if self.posted else D(10000)),
            unrealizedPL=str(self.upl if self.posted else D(0)), isolatedMargin=str(margin)),
            **self.wallet_changes}

    def positions(self):
        if not self.posted:
            return []
        quantity = D(self.f.detail_changes.get("baseVolume", self.f.journal.state.book.pending.request.quantity))
        average = D(self.f.detail_changes.get("priceAvg", "61000"))
        if not quantity:
            return []
        return [{**dict(symbol="BTCUSDT", marginCoin="USDT", holdSide="long", marginMode="isolated",
            posMode="one_way_mode", leverage="2", assetMode="single", autoMargin="off", openDelegateSize="0",
            total=str(quantity), available=str(quantity), locked="0", openPriceAvg=str(average),
            marginSize=str(quantity*average/2), totalFee="", deductedFee="0.35136", achievedProfits="0"),
            **self.margin_changes}]

    def native(self, packet):
        self.f.now += 1
        if type(packet) is SignedDemoReadRequest:
            return self.f.native(packet)
        self.assertIs(type(packet), SignedBasketRequest)
        if self.revoke_at == packet.plan.operation:
            self.f.revoked = True
        operation = packet.plan.operation
        if operation == "detail":
            return self.f.native(packet)
        packet.consume()
        if operation == "wallet":
            value = response([self.wallet()], at=self.f.now)
            self.wallet_reads.append(value)
            return value
        if operation == "positions":
            value = response(self.positions(), at=self.f.now)
            self.position_reads.append(value)
            return value
        self.assertEqual(operation, "bills")
        self.assertIn("onlyFunding=no", packet.target)
        self.assertNotIn("businessType=", packet.target)
        self.assertEqual(packet.plan.start_ms, self.f.journal.state.current_attempt.margin_baseline.start_ms)
        self.assertLessEqual(packet.plan.end_ms, self.f.now)
        if self.bill_pages is not None:
            data = self.bill_pages.pop(0)
        elif packet.plan.cursor is not None:
            data = dict(bills=[], endId=None)
        else:
            fee = self.f.detail_changes.get("fee", "-0.35136")
            rows = [] if not D(self.f.detail_changes.get("baseVolume", "1")) else [
                {**dict(billId="100", symbol="BTCUSDT", amount="0", fee=fee, feeByCoupon="",
                     businessType="buy", coin="USDT", balance="9999.64864",
                     cTime=str(native_fixture.milliseconds(self.f.journal.state.current_attempt.attempted_at))),
                     **self.bill_changes}]
            data = dict(bills=rows, endId="100" if rows else None)
        return response(data, at=self.f.now)

    def send(self, packet):
        record = json.loads(self.f.path.read_bytes().splitlines()[-1])
        self.assertEqual(record["command"]["kind"], "attempt_with_margin")
        self.assertIsNotNone(self.f.journal.state.current_attempt.margin_baseline)
        self.assertEqual(self.f.journal.state.recovery_mode, "get_only")
        packet.consume()
        self.posts.append(packet)
        self.posted = True
        self.f.now += 1
        if self.f.fail_post:
            raise OSError("synthetic ACK lost after send")
        return response(dict(clientOid=packet.plan.intent.client_oid, orderId="123"), at=self.f.now)

    def dispatch(self):
        return self.dispatcher.dispatch(context=OWNER, expected_revision=self.f.journal.state.revision)

    def observe(self):
        return self.dispatcher.observe(context=OWNER, expected_revision=self.f.journal.state.revision)

    def test_confirmed_native_margin_delta_cash_fee_and_upl_separation(self):
        self.assertEqual(self.dispatch(), "acknowledged")
        baseline = self.f.journal.state.current_attempt.margin_baseline
        self.assertEqual((baseline.equity, baseline.isolated_margin, baseline.positions), (D(10000), D(0), ()))
        state = self.observe()
        self.assertIsNone(state.book.pending)
        basket = state.book.signal.economic.ledger.baskets[1]
        self.assertEqual((basket.quantity, basket.margin_committed, basket.entry_fees),
                         (D(".0096"), D("292.8"), D(".35136")))
        self.assertEqual(len(self.posts), 1)

    def test_lost_ack_full_restore_keeps_exact_before_image_and_never_resends(self):
        self.f.fail_post = True
        self.assertEqual(self.dispatch(), "outcome_unknown")
        state, receipt = self.f.journal.checkpoint()
        self.f.journal.close()
        self.f.journal = BrokerEntryJournal.restore(self.f.path, journal_id=native_fixture.JOURNAL_ID,
            profile_digest=native_fixture.native_profile().profile_digest, minimum_receipt=receipt)
        self.assertEqual(self.f.journal.state.current_attempt.margin_baseline,
                         state.current_attempt.margin_baseline)
        self.dispatcher = self.f.dispatcher(read_transport=self.native, order_transport=self.send,
            margin_resolver=None, margin_source=self.source)
        with self.assertRaises(DemoRejected): self.dispatch()
        self.assertIsNone(self.observe().book.pending)
        self.assertEqual(len(self.posts), 1)

    def test_partial_terminal_native_fill_consumes_one_stage_and_actual_margin(self):
        self.f.detail_changes = dict(state="canceled", baseVolume="0.0048", fee="-0.17568")
        self.margin_changes["deductedFee"] = "0.17568"
        self.dispatch()
        state = self.observe()
        basket = state.book.signal.economic.ledger.baskets[1]
        self.assertEqual((basket.quantity, basket.margin_committed, basket.entry_fees),
                         (D(".0048"), D("146.4"), D(".17568")))
        self.assertEqual(len(state.book.signal.economic.stages), 1)

    def test_unfilled_cancel_known_fee0_and_margin0_does_not_book_stage(self):
        self.f.detail_changes = dict(state="canceled", baseVolume="0", priceAvg="0", fee="0")
        self.upl = D(0)
        self.dispatch()
        state = self.observe()
        self.assertIsNone(state.book.pending)
        self.assertFalse(state.book.signal.economic.stages)

    def test_cash_drift_undocumented_margin_and_changed_funding_remain_pending(self):
        self.dispatch()
        for name, value in (
            ("cash", D(1)), ("margin", "293.8"), ("funding", "-.01"), ("realized", "1"),
        ):
            with self.subTest(case=name):
                self.cash_drift = D(0)
                self.margin_changes.clear()
                if name == "cash": self.cash_drift = value
                else: self.margin_changes[dict(margin="marginSize", funding="totalFee",
                                                realized="achievedProfits")[name]] = value
                state = self.observe()
                self.assertIsNotNone(state.book.pending)
                self.assertIsNone(state.book.observation.posted_margin)
                self.assertEqual(state.book.observation.quantity, D(".0096"))
                self.assertFalse(state.book.signal.economic.stages)
        self.margin_changes.clear()
        self.assertIsNone(self.observe().book.pending)

    def test_funding_adjustments_transfers_foreign_symbol_and_unknown_bills_not_buy_margin(self):
        self.dispatch()
        for changes in (
            dict(businessType="contract_settle_fee", amount="-0.01"),
            dict(businessType="append_margin", amount="100"),
            dict(businessType="auto_append_margin", amount="100"),
            dict(businessType="trans_from_exchange", amount="100"),
            dict(businessType="unknown"), dict(symbol="ETHUSDT"),
            dict(fee=""), dict(feeByCoupon="0.1"), dict(amount="1"),
        ):
            with self.subTest(changes=changes):
                self.bill_changes = changes
                state = self.observe()
                self.assertIsNotNone(state.book.pending)
                self.assertIsNone(state.book.observation.posted_margin)
        self.bill_changes = {}
        self.assertIsNone(self.observe().book.pending)

    def test_missing_native_fields_are_not_zero_and_no_before_image_means_no_post(self):
        self.wallet_changes["grant"] = ""
        with self.assertRaises(DemoRejected): self.dispatch()
        self.assertEqual(self.posts, [])
        self.assertIsNone(self.f.journal.state.current_attempt)
        self.wallet_changes.clear()
        self.dispatch()
        self.wallet_changes["isolatedMargin"] = ""
        state = self.observe()
        self.assertIsNotNone(state.book.pending)
        self.assertIsNone(state.book.observation.posted_margin)

    def test_revoked_source_cannot_publish_terminal_fill_or_margin(self):
        self.dispatch()
        before = self.f.journal.receipt
        self.revoke_at = "wallet"
        with self.assertRaises(ValueError): self.observe()
        self.assertEqual(self.f.journal.receipt, before)
        self.assertEqual(len(self.posts), 1)

    def test_known_partial_live_is_preserved_without_attempting_margin_bill_resolution(self):
        self.f.detail_changes = dict(state="partially_filled", baseVolume="0.0048", fee="")
        self.dispatch()
        state = self.observe()
        self.assertIsNotNone(state.book.pending)
        self.assertEqual(state.book.observation.quantity, D(".0048"))
        self.assertIsNone(state.book.observation.posted_margin)

    def test_full_bill_page_requires_terminal_empty_page_and_sums_each_bill_once(self):
        self.dispatch()
        created = str(native_fixture.milliseconds(self.f.journal.state.current_attempt.attempted_at))
        bills = [dict(billId=str(i), symbol="BTCUSDT", amount="0", fee="-0.0035136",
                      feeByCoupon="", businessType="buy", coin="USDT", cTime=created)
                 for i in range(100, 0, -1)]
        self.bill_pages = [dict(bills=bills, endId="1"), dict(bills=[], endId=None)]
        self.assertIsNone(self.observe().book.pending)
        self.assertEqual(self.bill_pages, [])

    def test_wrong_bill_cursor_coverage_time_or_identity_never_proves_margin(self):
        self.dispatch()
        for changes in (dict(cTime=str(self.f.now+9999)), dict(billId="0"),
                        dict(coin="BTC"), dict(billId="100&x=evil")):
            self.bill_changes = changes
            state = self.observe()
            self.assertIsNotNone(state.book.pending)
            self.assertIsNone(state.book.observation.posted_margin)

    def test_bounded_get_only_bill_targets_reject_unrelated_query_mutation(self):
        self.dispatch()
        intent = self.f.intent
        basis = self.f.journal.state.current_attempt.margin_baseline
        plan = BasketRequestPlan(intent, "bills", basis.start_ms, self.f.now)
        self.assertEqual((plan.method, plan.body), ("GET", b""))
        for args in (
            (basis.start_ms, basis.start_ms, None),
            (basis.start_ms, basis.start_ms+31*86400000, None),
            (basis.start_ms, self.f.now, "1&symbol=ETHUSDT"),
        ):
            with self.assertRaises(DemoRejected): BasketRequestPlan(intent, "bills", *args)
        with self.assertRaises(DemoRejected): BasketRequestPlan(intent, "place", basis.start_ms, self.f.now)

    def test_durable_baseline_clock_or_order_binding_cannot_be_forged_before_post(self):
        self.dispatch()
        baseline = self.f.journal.state.current_attempt.margin_baseline
        from investalo_trading.futures_broker_journal import BrokerEntryAttempt
        original = self.f.journal.state.current_attempt
        for changed in (replace(baseline, order_digest="a"*64),
                        replace(baseline, wallet_ms=baseline.wallet_ms+10000, positions_ms=baseline.positions_ms+10000)):
            with self.assertRaises(ValueError):
                BrokerEntryAttempt(original.command_id, original.order_digest, original.authorization_digest,
                                   original.request_digest, original.attempted_at, changed)
        self.assertEqual(VERSION, "bitget-demo-h1-basket-entry-journal/6")

    def test_second_purchase_uses_native_delta_not_whole_position_and_retains_other_basket(self):
        self.dispatch()
        intent = replace(self.f.intent, stage=2, quantity=D(".0126"), planning_price=D(57950),
            planned_margin=D("366.41707366"), before_quantity=D(".0096"), before_average=D(61000),
            command_id="native-entry-2", order_digest="f"*64)
        at = self.f.now
        expected = (("BNBUSDT", D(".1"), D(100), D(".1")),
                    ("BTCUSDT", D(".0096"), D(61000), D(".1")),
                    ("ETHUSDT", D(0), D(0), D(".1")))
        def row(symbol, q, average, margin, fees):
            return dict(symbol=symbol, marginCoin="USDT", holdSide="long", marginMode="isolated",
                posMode="one_way_mode", leverage="2", total=q, available=q, locked="0",
                openPriceAvg=average, marginSize=margin, assetMode="single", autoMargin="off",
                openDelegateSize="0", totalFee="", deductedFee=fees, achievedProfits="0")
        other = row("BNBUSDT", "0.1", "100", "5", "0.01")
        original = row("BTCUSDT", "0.0096", "61000", "292.8", "0.35136")
        def wallet(cash, upl, occupied):
            return [dict(marginCoin="USDT", assetMode="single", locked="0", crossedMargin="0",
                coupon="0", grant="0", accountEquity=str(D(cash)+D(upl)),
                unrealizedPL=upl, isolatedMargin=occupied)]
        basis = capture_margin_baseline(response(wallet("9999.64864", "10", "297.8"), at=at),
            response([other, original], at=at+1), intent, context=OWNER, now_ms=at+1,
            expected_positions=expected)
        observation = OrderObservation(intent.intent_digest, "456", "filled",
            D(".0126"), D(57950), D("-.438102"), at+2, at+3, at+4)
        average = format((D(".0096")*61000+D(".0126")*57950)/D(".0222"), ".12f")
        final = row("BTCUSDT", "0.0222", average, "657.885", "0.789462")
        positions = response([other, final], at=at+5)
        after = response(wallet("9999.210538", "-50", "662.885"), at=at+6)
        bill = response(dict(bills=[dict(billId="123", symbol="BTCUSDT", amount="0", fee="-0.438102",
            feeByCoupon="", businessType="buy", coin="USDT", cTime=str(at+2))], endId="123"), at=at+7)
        terminal = response(dict(bills=[], endId=None), at=at+8)
        args = dict(context=OWNER, now_ms=at+8, expected_positions=expected, attempted_ms=at+2)
        result = reconcile_margin(basis, after, positions, (bill, terminal), intent, observation, **args)
        self.assertEqual(result[0], D("365.085"))
        self.assertNotEqual(result[0], D("657.885"))
        changed_other = {**other, "marginSize": "6"}
        changed_wallet = response(wallet("9999.210538", "-50", "663.885"), at=at+6)
        self.assertIsNone(reconcile_margin(basis, changed_wallet, response([changed_other, final], at=at+5),
                                          (bill, terminal), intent, observation, **args))

    def test_bill_end_covers_both_native_wallet_and_position_clocks(self):
        self.dispatch()
        original = self.native
        end = []
        def staggered(packet):
            self.f.now += 10
            result = original(packet)
            if type(packet) is SignedBasketRequest and packet.plan.operation == "wallet":
                raw = json.loads(result.body)
                raw["requestTime"] -= 20
                return type(result)(result.status, json.dumps(raw).encode())
            if type(packet) is SignedBasketRequest and packet.plan.operation == "bills":
                end.append(packet.plan.end_ms)
            return result
        source = BasketNativeMarginSource(transport=staggered, milliseconds=lambda: self.f.now)
        self.dispatcher = self.f.dispatcher(read_transport=staggered, order_transport=self.send,
            margin_resolver=None, margin_source=source)
        state = self.observe()
        self.assertIsNone(state.book.pending)
        native_position_ms = json.loads(self.position_reads[-1].body)["requestTime"]
        self.assertTrue(end and all(at == native_position_ms for at in end))

    def test_short_nonempty_page_cannot_claim_complete_bill_scope(self):
        self.dispatch()
        basis = self.f.journal.state.current_attempt.margin_baseline
        intent = self.f.intent
        from investalo_bitget.futures_demo_margin import parse_bill_page
        page = response(dict(bills=[dict(billId="123", symbol="BTCUSDT", amount="0",
            fee="-0.35136", businessType="buy", coin="USDT", feeByCoupon="",
            cTime=str(self.f.now))], endId="123"), at=self.f.now+1)
        _, cursor, _ = parse_bill_page(page, intent, context=OWNER, now_ms=self.f.now+1,
            start_ms=basis.start_ms, end_ms=self.f.now)
        self.assertEqual(cursor, "123")
