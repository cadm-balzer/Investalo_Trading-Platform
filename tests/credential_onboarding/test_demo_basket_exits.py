"""Actual journal/AEAD/HMAC/reducers, synthetic original actor and native replies."""
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
from investalo_bitget.futures_demo_basket import BasketExitIntent, BasketRequestPlan
from investalo_bitget.futures_demo_margin import capture_margin_baseline, reconcile_exit
from investalo_bitget.futures_demo_reconcile import OrderObservation
from investalo_bitget.futures_demo_read import SignedDemoReadRequest
from investalo_credential_store.demo_basket_orders import (
    EXIT_PURPOSE, SignedBasketRequest, milliseconds,
)
from investalo_credential_store.demo_basket_margin import BasketNativeMarginSource
from investalo_trading.futures_broker_entries import BrokerExitOrder, prepare_broker_exit
from investalo_trading.futures_broker_journal import BrokerEntryJournal
from investalo_trading.futures_ledger import LedgerMark
from investalo_bitget.signing import hmac_sha256_base64

D = Decimal


class NativeExitTests(unittest.TestCase):
    def setUp(self):
        self.m = margin_fixture.NativeMarginTests()
        self.m.setUp()
        self.m.dispatch()
        self.m.observe()
        self.f = self.m.f
        self.unprotected = self.f.journal.state.book
        self.quantity = self.f.journal.state.book.signal.economic.ledger.baskets[1].quantity
        self.margin = D("292.8")
        self.open_fee = D(".35136")
        self.fill = self.quantity
        self.fill_price = D(62000)
        self.state = "filled"
        self.fee = D("-.35712")
        self.exit_posted = False
        self.posts = []
        self.detail_changes = {}
        self.after_wallet_changes = {}
        self.after_position_changes = {}
        self.before_position_changes = {}
        self.bill_changes = {}
        self.bill_pages = None
        self.foreign_positions = []
        self.foreign_margin = D(0)
        self.foreign_drift = False
        self.revoked_at = None
        self.lost_ack = False
        self.source = BasketNativeMarginSource(transport=self.native, milliseconds=lambda: self.f.now)
        self.dispatcher = self.f.dispatcher(read_transport=self.native, order_transport=self.send,
            margin_resolver=None, margin_source=self.source)
        # Activate protection above +5%, then cross the established protection.
        self.prices(65000)
        self.prices(61000)
        self.prepare()

    def tearDown(self):
        self.m.tearDown()

    def prices(self, value):
        self.f.now += 1
        marks = tuple(LedgerMark(s, D(value)) for s in self.f.journal.state.book.signal.profile.plan.symbols)
        self.f.journal.append("prices", expected_revision=self.f.journal.state.revision,
            at=parse.EPOCH + timedelta(milliseconds=self.f.now),
            trade=marks, marks=marks, event_id=f"exit-price-{self.f.now}")

    def prepare(self, command="owned-exit"):
        self.f.journal.append("prepare_exit", expected_revision=self.f.journal.state.revision,
            at=parse.EPOCH + timedelta(milliseconds=self.f.now),
            symbol="BTCUSDT", command_id=command)

    def wallet(self):
        cash = D(10000) - self.open_fee
        quantity = self.quantity
        if self.exit_posted:
            cash += self.fill * (self.fill_price - 61000) + self.fee
            quantity -= self.fill
        upl = D(25) if quantity else D(0)
        return {**dict(marginCoin="USDT", assetMode="single", locked="0", crossedMargin="0", coupon="0", grant="0",
            accountEquity=str(cash+upl), unrealizedPL=str(upl),
            isolatedMargin=str(self.margin*quantity/self.quantity + self.foreign_margin)),
            **(self.after_wallet_changes if self.exit_posted else {})}

    def positions(self):
        remaining = self.quantity - (self.fill if self.exit_posted else 0)
        rows = []
        if remaining:
            rows.append({**dict(symbol="BTCUSDT", marginCoin="USDT", holdSide="long", marginMode="isolated",
                posMode="one_way_mode", leverage="2", assetMode="single", autoMargin="off",
                openDelegateSize="0", total=str(remaining), available=str(remaining), locked="0",
                openPriceAvg="61000", marginSize=str(self.margin*remaining/self.quantity), totalFee="",
                deductedFee=str(self.open_fee-(self.fee if self.exit_posted else 0)),
                achievedProfits=str(self.fill*(self.fill_price-61000) if self.exit_posted else 0)),
                **(self.after_position_changes if self.exit_posted else self.before_position_changes)})
        rows.extend(self.foreign_positions)
        if self.foreign_drift and self.exit_posted and rows:
            rows[-1] = {**rows[-1], "marginSize": "201"}
        return rows

    def native(self, packet):
        self.f.now += 1
        if type(packet) is SignedDemoReadRequest:
            return self.f.native(packet)
        self.assertIs(type(packet), SignedBasketRequest)
        packet.consume()
        op = packet.plan.operation
        if op == self.revoked_at:
            self.f.revoked = True
        if op == "wallet":
            return response([self.wallet()], at=self.f.now)
        if op == "positions":
            return response(self.positions(), at=self.f.now)
        if op == "detail":
            intent = packet.plan.intent
            return response({**dict(symbol="BTCUSDT", clientOid=intent.client_oid, orderId="456",
                marginCoin="USDT", marginMode="isolated", posMode="one_way_mode", posSide="net", leverage="2",
                size=str(intent.quantity), side="sell", reduceOnly="YES", orderType="market",
                state=self.state, baseVolume=str(self.fill), priceAvg=str(self.fill_price if self.fill else 0),
                fee=str(self.fee) if self.fee is not None else None,
                cTime=str(milliseconds(self.f.journal.state.current_attempt.attempted_at)), uTime=str(self.f.now)),
                **self.detail_changes}, at=self.f.now)
        self.assertEqual(op, "bills")
        if self.bill_pages is not None:
            data = self.bill_pages.pop(0)
        else:
            rows = [] if packet.plan.cursor is not None or not self.fill else [
                {**dict(billId="200", symbol="BTCUSDT", amount=str(self.fill*(self.fill_price-61000)),
                    fee=str(self.fee), feeByCoupon="", businessType="sell", coin="USDT", balance="10008.89152",
                    cTime=str(milliseconds(self.f.journal.state.current_attempt.attempted_at))),
                    **self.bill_changes}]
            data = dict(bills=rows, endId="200" if rows else None)
        return response(data, at=self.f.now)

    def send(self, packet):
        last = json.loads(self.f.path.read_bytes().splitlines()[-1])
        self.assertEqual(last["command"]["kind"], "attempt_with_margin")
        self.assertIsNotNone(self.f.journal.state.current_attempt.margin_baseline)
        packet.consume()
        self.posts.append(packet)
        self.exit_posted = True
        self.f.now += 1
        if self.lost_ack:
            raise OSError("synthetic POST succeeded, ACK lost")
        # Documented reduce-only ACK may omit orderId.
        return response(dict(clientOid=packet.plan.intent.client_oid), at=self.f.now)

    def dispatch(self):
        return self.dispatcher.dispatch(context=OWNER, expected_revision=self.f.journal.state.revision)

    def observe(self):
        return self.dispatcher.observe(context=OWNER, expected_revision=self.f.journal.state.revision)

    def test_exact_owned_reduce_market_signed_and_distinct_purpose(self):
        self.assertEqual(self.dispatch(), "acknowledged")
        packet = self.posts[0]
        self.assertIs(type(packet.plan.intent), BasketExitIntent)
        self.assertIs(type(self.f.journal.state.book.pending), BrokerExitOrder)
        body = json.loads(packet.body)
        self.assertEqual((body["side"], body["reduceOnly"], body["orderType"]), ("sell", "YES", "market"))
        self.assertEqual(D(body["size"]), self.quantity)
        self.assertTrue(body["clientOid"].startswith("ivx"))
        self.assertNotEqual(body["clientOid"], self.m.posts[0].plan.intent.client_oid)
        self.assertNotIn("price", body); self.assertNotIn("force", body)
        stamp = packet.headers["ACCESS-TIMESTAMP"]
        self.assertEqual(packet.headers["ACCESS-SIGN"], hmac_sha256_base64(b"synthetic-secret",
            stamp.encode()+b"POST"+packet.target.encode()+packet.body))
        approval = self.f.approval(packet.plan.intent, self.f.journal.receipt, OWNER)
        self.assertEqual(approval.purpose, EXIT_PURPOSE)
        with self.assertRaises(DemoRejected):
            approval.check(self.m.posts[0].plan.intent, self.f.journal.receipt, self.f.now)
        self.assertFalse(self.f.journal.state.book.signal.economic.ledger.closed_baskets)

    def test_actual_close_cash_fee_flat_rearms_only_new_cycle(self):
        self.dispatch()
        result = self.observe()
        basket = result.book.signal.economic.ledger.baskets[1]
        self.assertIsNone(result.book.pending)
        self.assertEqual((basket.quantity, basket.isolated_balance, basket.margin_committed), (D(0),)*3)
        self.assertEqual(result.book.signal.economic.ledger.closed_baskets, 1)
        self.assertEqual(result.book.signal.economic.ledger.realized_net_pnl, D("8.89152"))
        settlement = json.loads(self.f.path.read_bytes().splitlines()[-1])["command"]["arguments"]["observation"]
        self.assertEqual((settlement["realized_pnl"], settlement["signed_fee"]), ("9.6000", "-0.35712"))
        self.assertEqual(result.book.signal.economic.ledger.unposted_cash, D("10008.89152"))
        signal = result.book.signal.signals[1]
        self.assertEqual((signal.cycle, signal.below_count, signal.rearmed, signal.exit_reasons), (2, 0, False, ()))
        with self.assertRaises(DemoRejected): self.observe()
        self.assertEqual(len(self.posts), 1)

    def test_lost_ack_restore_get_only_with_missing_ack_orderid(self):
        self.lost_ack = True
        self.assertEqual(self.dispatch(), "outcome_unknown")
        receipt = self.f.journal.receipt
        original = self.f.journal.state
        self.f.journal.close()
        self.f.journal = BrokerEntryJournal.restore(self.f.path, journal_id=order_fixture.JOURNAL_ID,
            profile_digest=order_fixture.native_profile().profile_digest, minimum_receipt=receipt)
        self.assertEqual(self.f.journal.state, original)
        self.dispatcher = self.f.dispatcher(read_transport=self.native, order_transport=self.send,
            margin_resolver=None, margin_source=self.source)
        with self.assertRaises(DemoRejected): self.dispatch()
        self.assertIsNone(self.observe().book.pending)
        self.assertEqual(len(self.posts), 1)

    def test_terminal_partial_only_releases_actual_fraction_and_remaining_can_close(self):
        self.fill /= 2; self.fee /= 2; self.state = "canceled"
        self.dispatch()
        result = self.observe()
        basket = result.book.signal.economic.ledger.baskets[1]
        self.assertEqual((basket.quantity, basket.average_entry, basket.isolated_balance),
                         (self.fill, D(61000), D("146.4")))
        self.assertEqual((basket.exit_fees, basket.realized_price_pnl), (D(".17856"), D("4.8")))
        self.assertFalse(result.book.signal.economic.ledger.closed_baskets)
        self.assertIn("terminal_partial_exit", result.book.notices)
        self.prices(61000)
        self.prepare("remaining-exit")
        self.assertEqual(self.f.journal.state.book.pending.request.quantity, self.fill)

    def test_live_partial_does_not_book_or_resend_then_terminal_settles(self):
        self.fill /= 2; self.fee /= 2; self.state = "partially_filled"
        self.dispatch()
        result = self.observe()
        self.assertEqual(result.book.signal.economic.ledger.baskets[1].quantity, self.quantity)
        with self.assertRaises(DemoRejected): self.dispatch()
        self.state = "canceled"
        self.assertIsNone(self.observe().book.pending)
        self.assertEqual(len(self.posts), 1)

    def test_known_zero_unfilled_cancellation_preserves_original_basket(self):
        self.fill = D(0); self.fee = D(0); self.state = "canceled"
        self.dispatch()
        result = self.observe()
        self.assertIsNone(result.book.pending)
        self.assertEqual(result.book.signal.economic.ledger.baskets[1].quantity, self.quantity)
        self.assertFalse(result.book.signal.economic.ledger.closed_baskets)

    def test_cash_or_bill_disagreement_never_marks_closed(self):
        self.dispatch()
        for changes in ({"amount": "9.61"}, {"fee": "-.35"}, {"businessType": "contract_settle_fee"},
                        {"businessType": "force_sell"}, {"symbol": "ETHUSDT"}, {"feeByCoupon": ".01"}):
            with self.subTest(changes=changes):
                self.bill_changes = changes
                result = self.observe()
                self.assertIsNotNone(result.book.pending)
                self.assertIsNone(result.book.observation.realized_pnl)
                self.assertFalse(result.book.signal.economic.ledger.closed_baskets)
        self.bill_changes = {}
        self.after_wallet_changes["accountEquity"] = "10009.89152"
        self.assertIsNotNone(self.observe().book.pending)
        self.after_wallet_changes.clear()
        self.assertIsNone(self.observe().book.pending)

    def test_partial_changed_margin_funding_fees_or_realized_remains_pending(self):
        self.fill /= 2; self.fee /= 2; self.state = "canceled"
        self.dispatch()
        for field, value in (("marginSize", "147.4"), ("totalFee", "-0.01"),
                             ("deductedFee", "0.52"), ("achievedProfits", "4.81")):
            with self.subTest(field=field):
                self.after_position_changes = {field: value}
                self.assertIsNotNone(self.observe().book.pending)
        self.after_position_changes = {}
        self.assertIsNone(self.observe().book.pending)

    def test_unknown_fee_or_missing_complete_bill_window_keeps_exposure_pending(self):
        self.dispatch()
        self.detail_changes["fee"] = None
        self.assertIsNotNone(self.observe().book.pending)
        self.detail_changes.clear()
        self.bill_pages = [dict(bills=[dict(billId=str(300-i), symbol="BTCUSDT", amount="0", fee="0",
            feeByCoupon="0", businessType="sell", coin="USDT",
            cTime=str(milliseconds(self.f.journal.state.current_attempt.attempted_at)))], endId=str(300-i))
            for i in range(8)]
        self.assertIsNotNone(self.observe().book.pending)

    def test_wrong_side_reduce_only_qty_native_id_or_position_denied(self):
        self.dispatch()
        for field, value in (("side", "buy"), ("reduceOnly", "NO"), ("size", "0.01"), ("leverage", "10")):
            with self.subTest(field=field):
                self.detail_changes = {field: value}
                with self.assertRaises(DemoRejected): self.observe()
        self.detail_changes = {}
        self.fill /= 2; self.fee /= 2; self.state = "partially_filled"
        self.observe()
        self.detail_changes["orderId"] = "999"
        with self.assertRaises(ValueError): self.observe()
        self.assertEqual(len(self.posts), 1)

    def test_exit_before_image_cannot_adopt_unbooked_funding_or_margin(self):
        for field, value in (("totalFee", "-0.01"), ("deductedFee", "0.36"), ("achievedProfits", "1")):
            with self.subTest(field=field):
                self.before_position_changes = {field: value}
                with self.assertRaises(DemoRejected): self.dispatch()
                self.assertEqual(len(self.posts), 0)
        self.before_position_changes = {}

    def test_source_missing_or_actor_revocation_denies_dispatch_and_publication(self):
        no_source = self.f.dispatcher(read_transport=self.native, order_transport=self.send)
        with self.assertRaises(DemoRejected):
            no_source.dispatch(context=OWNER, expected_revision=self.f.journal.state.revision)
        self.dispatch()
        self.revoked_at = "bills"
        with self.assertRaises(ValueError): self.observe()
        self.assertIsNone(self.f.journal.state.book.observation)

    def test_loss_exit_books_actual_negative_pnl_not_assumed_profit(self):
        self.fill_price = D(60000); self.fee = D("-.3456")
        self.dispatch()
        result = self.observe()
        self.assertEqual(result.book.signal.economic.ledger.closed_baskets, 1)
        self.assertEqual(result.book.signal.economic.ledger.realized_net_pnl, D("-10.29696"))

    def test_stale_quote_or_missing_exit_reason_does_not_dispatch(self):
        self.f.now += 6000
        with self.assertRaisesRegex(ValueError, "fresh"):
            self.dispatch()
        self.assertEqual(len(self.posts), 0)

    def test_original_exit_cannot_be_canceled_or_observed_as_entry(self):
        self.dispatch()
        with self.assertRaises(ValueError):
            self.f.journal.append("cancel_preparation", expected_revision=self.f.journal.state.revision,
                at=self.f.journal.state.as_of, order_digest=self.f.journal.state.book.pending.order_digest)
        with self.assertRaises(DemoRejected):
            BasketRequestPlan(replace(self.posts[0].plan.intent, quantity=self.quantity/2), "place")

    def test_without_strategy_stop_or_with_liquidation_no_regular_exit(self):
        book = self.unprotected
        with self.assertRaises(ValueError):
            prepare_broker_exit(book, "BTCUSDT", "no-stop", book.revision, book.as_of)
        book = self.f.journal.state.book
        signal = book.signal.signals[1]
        changed = replace(signal, exit_reasons=("liquidation_settlement_required", *signal.exit_reasons))
        signals = tuple(changed if i == 1 else s for i, s in enumerate(book.signal.signals))
        book = replace(book, pending=None, signal=replace(book.signal, signals=signals))
        with self.assertRaises(ValueError):
            prepare_broker_exit(book, "BTCUSDT", "not-liquidation", book.revision, book.as_of)

    def test_before_cash_drift_rejected_without_post(self):
        original_wallet = self.wallet
        self.wallet = lambda: {**original_wallet(), "accountEquity": "10025.64864"}
        with self.assertRaisesRegex(DemoRejected, "cash"):
            self.dispatch()
        self.assertFalse(self.posts)

    def test_unowned_native_basket_blocks_exit_before_post(self):
        self.foreign_positions = [dict(symbol="BNBUSDT", marginCoin="USDT", holdSide="long",
            marginMode="isolated", posMode="one_way_mode", leverage="2", assetMode="single", autoMargin="off",
            openDelegateSize="0", total="1", available="1", locked="0", openPriceAvg="400",
            marginSize="200", totalFee="", deductedFee="0.24", achievedProfits="0")]
        self.foreign_margin = D(200)
        # Fixture has no matching owned BNB receipt: complete native admission must reject it.
        with self.assertRaises(DemoRejected):
            self.dispatch()
        self.assertFalse(self.posts)

    def test_complete_owned_product_releases_only_target_margin_with_other_upl(self):
        intent = self.dispatcher._intent(self.f.journal.state, OWNER)
        at = self.f.now
        other = dict(symbol="BNBUSDT", marginCoin="USDT", holdSide="long",
            marginMode="isolated", posMode="one_way_mode", leverage="2", assetMode="single", autoMargin="off",
            openDelegateSize="0", total="1", available="1", locked="0", openPriceAvg="400",
            marginSize="200", totalFee="", deductedFee="0.24", achievedProfits="0")
        target = self.positions()[0]
        expected = (("BNBUSDT", D(1), D(400), D(".01")),
                    ("BTCUSDT", self.quantity, D(61000), D(".1")),
                    ("ETHUSDT", D(0), D(0), D(".01")))
        def wallet(cash, upl, margin):
            return [dict(marginCoin="USDT", assetMode="single", locked="0", crossedMargin="0",
                coupon="0", grant="0", accountEquity=str(D(cash)+D(upl)), unrealizedPL=upl, isolatedMargin=margin)]
        baseline = capture_margin_baseline(response(wallet("9999.40864", "30", "492.8"), at=at),
            response([other, target], at=at+1), intent, context=OWNER, now_ms=at+1, expected_positions=expected)
        observation = OrderObservation(intent.intent_digest, "456", "filled", self.quantity, D(62000),
            D("-.35712"), at+2, at+3, at+4)
        final = response([other], at=at+5)
        account = response(wallet("10008.65152", "-50", "200"), at=at+6)
        bill = response(dict(bills=[dict(billId="200", symbol="BTCUSDT", amount="9.6", fee="-0.35712",
            feeByCoupon="", businessType="sell", coin="USDT", cTime=str(at+2))], endId="200"), at=at+7)
        terminal = response(dict(bills=[], endId=None), at=at+8)
        args = dict(context=OWNER, now_ms=at+8, expected_positions=expected, attempted_ms=at+2)
        result = reconcile_exit(baseline, account, final, (bill, terminal), intent, observation, **args)
        self.assertEqual(result[:2], (D("292.8"), D("9.6")))
        changed_other = {**other, "deductedFee": "0.25"}
        self.assertIsNone(reconcile_exit(baseline, account, response([changed_other], at=at+5),
            (bill, terminal), intent, observation, **args))

    def test_partial_exit_restore_retains_cumulative_observation_and_original_quantity(self):
        self.fill /= 2; self.fee /= 2; self.state = "partially_filled"
        self.dispatch()
        current = self.observe()
        receipt = self.f.journal.receipt
        self.f.journal.close()
        self.f.journal = BrokerEntryJournal.restore(self.f.path, journal_id=order_fixture.JOURNAL_ID,
            profile_digest=order_fixture.native_profile().profile_digest, minimum_receipt=receipt)
        self.assertEqual(self.f.journal.state, current)
        self.assertEqual(current.book.pending.request.quantity, self.quantity)
        self.dispatcher = self.f.dispatcher(read_transport=self.native, order_transport=self.send,
            margin_resolver=None, margin_source=self.source)
        self.state = "canceled"
        result = self.observe()
        self.assertEqual(result.book.signal.economic.ledger.baskets[1].quantity, self.quantity/2)


if __name__ == "__main__":
    unittest.main()
