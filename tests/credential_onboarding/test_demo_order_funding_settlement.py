"""Actual journal/AEAD/once packets; synthetic whole-product exchange only."""
from dataclasses import replace
from decimal import Decimal
from datetime import timedelta
import json
import unittest

import test_demo_basket_orders as fixture
from test_futures_demo import OWNER,response
from investalo_bitget import parse
from investalo_bitget.futures_demo import DemoRejected
from investalo_bitget.futures_demo_basket import BasketExitIntent
from investalo_bitget.futures_demo_read import SignedDemoReadRequest
from investalo_credential_store.demo_basket_orders import SignedBasketRequest,milliseconds
from investalo_credential_store.demo_basket_margin import BasketNativeMarginSource
from investalo_trading.futures_broker_journal import BrokerEntryJournal
from investalo_trading.futures_ledger import LedgerMark

D=Decimal


class NativeOrderFundingTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.BasketNativeTests(); self.f.setUp()
        self.cash=D(10000); self.positions={}
        self.rows=[]; self.id=100
        self.post_count=0; self.open_price=D(61000); self.close_price=D(62000)
        self.fee=D("-.35136"); self.actual_quantity=None; self.terminal="filled"
        self.funding=[]; self.lost_ack=False; self.current=None
        self.wallet_changes={}; self.position_changes={}; self.row_changes={}
        self.pages=None; self.revoke_at=None
        self.source=BasketNativeMarginSource(transport=self.native,milliseconds=lambda:self.f.now)
        self.dispatcher=self.f.dispatcher(read_transport=self.native,order_transport=self.send,
            margin_resolver=None,margin_source=self.source)

    def tearDown(self):
        self.f.tearDown()

    def bill(self,symbol,kind,amount,fee,at):
        self.id+=1
        self.rows.append(dict(billId=str(self.id),symbol=symbol,businessType=kind,
            amount=str(amount),fee=str(fee),feeByCoupon="",coin="USDT",cTime=str(at)))

    def send(self,packet):
        self.assertEqual(json.loads(self.f.path.read_bytes().splitlines()[-1])["command"]["kind"],
                         "attempt_with_margin")
        packet.consume(); self.post_count+=1
        intent=packet.plan.intent; symbol=intent.grid.symbol
        created=milliseconds(self.f.journal.state.current_attempt.attempted_at)
        self.f.now+=1
        for asset,amount,isolated in self.funding:
            p=self.positions[asset]
            p["margin"]+=isolated; p["funding"]+=amount; self.cash+=amount
            self.bill(asset,"contract_settle_fee",amount,D(0),self.f.now)
        quantity=intent.quantity if self.actual_quantity is None else self.actual_quantity
        price=self.close_price if type(intent) is BasketExitIntent else self.open_price
        self.f.now+=1
        if quantity:
            if type(intent) is BasketExitIntent:
                p=self.positions[symbol]
                pnl=quantity*(price-p["average"])
                self.cash+=pnl+self.fee
                self.bill(symbol,"sell",pnl,self.fee,self.f.now)
                p["margin"]*=1-quantity/p["quantity"]
                p["quantity"]-=quantity
                p["fees"]-=self.fee; p["realized"]+=pnl
                if not p["quantity"]: del self.positions[symbol]
            else:
                p=self.positions.setdefault(symbol,dict(quantity=D(0),average=D(0),margin=D(0),
                    funding=D(0),fees=D(0),realized=D(0)))
                total=p["quantity"]+quantity
                p["average"]=(p["quantity"]*p["average"]+quantity*price)/total
                p["quantity"]=total; p["margin"]+=quantity*price/2; p["fees"]-=self.fee
                self.cash+=self.fee
                self.bill(symbol,"buy",D(0),self.fee,self.f.now)
        self.current=dict(intent=intent,quantity=quantity,price=price,created=created,
            updated=self.f.now,fee=self.fee if quantity else D(0),state=self.terminal)
        if self.lost_ack: raise OSError("synthetic ACK lost after original POST")
        return response(dict(clientOid=intent.client_oid),at=self.f.now)

    def native(self,packet):
        self.f.now+=1
        if type(packet) is SignedDemoReadRequest: return self.f.native(packet)
        self.assertIs(type(packet),SignedBasketRequest)
        packet.consume(); op=packet.plan.operation
        if op==self.revoke_at: self.f.revoked=True
        if op=="wallet":
            data=[{**dict(marginCoin="USDT",assetMode="single",locked="0",crossedMargin="0",coupon="0",grant="0",
                accountEquity=str(self.cash+17 if self.positions else self.cash),
                unrealizedPL="17" if self.positions else "0",
                isolatedMargin=str(sum((p["margin"] for p in self.positions.values()),D(0)))),**self.wallet_changes}]
        elif op=="positions":
            data=[{**dict(symbol=s,marginCoin="USDT",holdSide="long",marginMode="isolated",posMode="one_way_mode",
                leverage="2",assetMode="single",autoMargin="off",openDelegateSize="0",locked="0",
                total=str(p["quantity"]),available=str(p["quantity"]),openPriceAvg=str(p["average"]),
                marginSize=str(p["margin"]),totalFee=str(p["funding"]),deductedFee=str(p["fees"]),
                achievedProfits=str(p["realized"])),**self.position_changes.get(s,{})} for s,p in self.positions.items()]
        elif op=="detail":
            c=self.current; intent=c["intent"]
            data=dict(symbol=intent.grid.symbol,clientOid=intent.client_oid,orderId=str(1000+self.post_count),
                marginCoin="USDT",marginMode="isolated",posMode="one_way_mode",posSide="net",leverage="2",
                size=str(intent.quantity),side="sell" if type(intent) is BasketExitIntent else "buy",
                reduceOnly="YES" if type(intent) is BasketExitIntent else "NO",orderType="market",
                state=c["state"],baseVolume=str(c["quantity"]),priceAvg=str(c["price"] if c["quantity"] else 0),
                fee=str(c["fee"]),cTime=str(c["created"]),uTime=str(c["updated"]))
        else:
            self.assertEqual(op,"bills")
            if self.pages is not None: data=self.pages.pop(0)
            else:
                rows=[{**r,**self.row_changes.get(r["businessType"],{})} for r in self.rows
                    if packet.plan.start_ms<=int(r["cTime"])<=packet.plan.end_ms
                    and (packet.plan.cursor is None or int(r["billId"])<int(packet.plan.cursor))]
                rows=sorted(rows,key=lambda r:int(r["billId"]),reverse=True)[:100]
                data=dict(bills=rows,endId=rows[-1]["billId"] if rows else None)
        return response(data,at=self.f.now)

    def dispatch(self):
        return self.dispatcher.dispatch(context=OWNER,expected_revision=self.f.journal.state.revision)

    def observe(self):
        return self.dispatcher.observe(context=OWNER,expected_revision=self.f.journal.state.revision)

    def prices(self,value=61000):
        self.f.now+=1
        marks=tuple(LedgerMark(s,D(value)) for s in self.f.journal.state.book.signal.profile.plan.symbols)
        self.f.journal.append("prices",expected_revision=self.f.journal.state.revision,
            at=parse.EPOCH+timedelta(milliseconds=self.f.now),trade=marks,marks=marks,event_id=f"quote-{self.f.now}")

    def open_btc(self):
        self.assertEqual(self.dispatch(),"acknowledged")
        self.assertIsNone(self.observe().book.pending)

    def prepare_bnb(self):
        self.prices()
        self.f.journal.append("prepare",expected_revision=self.f.journal.state.revision,
            at=self.f.journal.state.as_of,symbol="BNBUSDT",planning_price=D(61000),command_id="bnb-entry")

    def prepare_close(self):
        self.prices(65000); self.prices(61000)
        self.f.journal.append("prepare_exit",expected_revision=self.f.journal.state.revision,
            at=self.f.journal.state.as_of,symbol="BTCUSDT",command_id="btc-close")
        self.fee=D("-.35712")

    def restore(self):
        state,receipt=self.f.journal.checkpoint()
        self.f.journal.close()
        self.f.journal=BrokerEntryJournal.restore(self.f.path,journal_id=fixture.JOURNAL_ID,
            profile_digest=fixture.native_profile().profile_digest,minimum_receipt=receipt)
        self.assertEqual(self.f.journal.state,state)
        self.dispatcher=self.f.dispatcher(read_transport=self.native,order_transport=self.send,
            margin_resolver=None,margin_source=self.source)

    def test_full_close_and_wallet_funding_one_atomic_native_cash_result(self):
        self.open_btc(); self.prepare_close()
        self.funding=[("BTCUSDT",D("-.12"),D(0))]
        self.dispatch(); result=self.observe()
        self.assertIsNone(result.book.pending)
        ledger=result.book.signal.economic.ledger
        self.assertEqual((ledger.closed_baskets,ledger.realized_net_pnl,ledger.unposted_cash),
                         (1,D("8.77152"),D("10008.77152")))
        self.assertEqual(ledger.unposted_cash,self.cash)
        self.assertEqual(len(result.funding_ids),1)
        row=json.loads(self.f.path.read_bytes().splitlines()[-1])
        self.assertEqual(row["command"]["kind"],"settle_order_funding")
        self.assertIn("terminal_funding_debit_pool_unallocated",result.book.notices)

    def test_full_close_with_isolated_funding_has_same_confirmed_terminal_cash(self):
        self.open_btc(); self.prepare_close()
        self.funding=[("BTCUSDT",D("-.12"),D("-.12"))]
        self.dispatch(); result=self.observe()
        self.assertEqual(result.book.signal.economic.ledger.unposted_cash,self.cash)
        self.assertEqual(result.book.signal.economic.ledger.realized_net_pnl,D("8.77152"))
        self.assertIsNone(result.book.pending)

    def test_lost_ack_restore_and_atomic_recovery_never_resends(self):
        self.open_btc(); self.prepare_close()
        self.funding=[("BTCUSDT",D("-.12"),D(0))]
        self.lost_ack=True
        self.assertEqual(self.dispatch(),"outcome_unknown")
        self.restore()
        with self.assertRaises(DemoRejected): self.dispatch()
        self.assertIsNone(self.observe().book.pending)
        self.assertEqual(self.post_count,2)
        self.restore()
        with self.assertRaises(DemoRejected): self.observe()

    def test_buy_with_funding_on_other_owned_basket_preserves_native_stage_margin(self):
        self.open_btc(); self.prepare_bnb()
        self.funding=[("BTCUSDT",D("-.12"),D(0))]
        self.dispatch(); result=self.observe()
        self.assertIsNone(result.book.pending)
        bnb,btc=result.book.signal.economic.ledger.baskets[:2]
        self.assertEqual((bnb.margin_committed,btc.margin_committed,btc.funding_net,btc.funding_wallet_cost),
                         (D("292.8"),D("292.8"),D("-.12"),D(".12")))
        self.assertEqual(len(result.book.signal.economic.stages),2)
        ledger=result.book.signal.economic.ledger
        self.assertEqual(ledger.unposted_cash+sum((b.isolated_balance for b in ledger.baskets),D(0)),self.cash)

    def test_buy_with_other_isolated_funding_retains_other_principal_and_actual_cash(self):
        self.open_btc(); self.prepare_bnb()
        self.funding=[("BTCUSDT",D("-.12"),D("-.12"))]
        self.dispatch(); result=self.observe()
        btc=result.book.signal.economic.ledger.baskets[1]
        self.assertEqual((btc.margin_committed,btc.isolated_balance,btc.funding_wallet_cost),
                         (D("292.8"),D("292.68"),D(0)))
        self.assertIsNone(result.book.pending)

    def test_zero_net_funding_receipts_and_gross_cost_survive_full_close_restore(self):
        self.open_btc(); self.prepare_close()
        self.funding=[("BTCUSDT",D("-.12"),D(0)),("BTCUSDT",D(".12"),D(".12"))]
        self.dispatch(); result=self.observe()
        self.assertIsNone(result.book.pending)
        self.assertEqual((len(result.funding_ids),result.book.signal.economic.ledger.realized_net_pnl),
                         (2,D("8.89152")))
        self.restore()

    def test_cash_or_bill_disagreement_does_not_partially_publish_or_move_cursor(self):
        self.open_btc(); self.prepare_close()
        self.funding=[("BTCUSDT",D("-.12"),D(0))]
        self.dispatch()
        before=self.f.journal.state
        self.wallet_changes["accountEquity"]=str(self.cash+D(1))
        result=self.observe()
        self.assertIsNotNone(result.book.pending)
        self.assertEqual(result.funding_checked_ms,before.funding_checked_ms)
        self.assertEqual(result.book.signal,before.book.signal)
        self.wallet_changes={}
        self.row_changes["contract_settle_fee"]={"amount":"-0.13"}
        self.assertIsNotNone(self.observe().book.pending)
        self.row_changes={}
        self.assertIsNone(self.observe().book.pending)

    def test_transfer_or_forced_close_or_bonus_stays_pending(self):
        self.open_btc(); self.prepare_close()
        self.funding=[("BTCUSDT",D("-.12"),D(0))]
        self.dispatch()
        for kind in ("trans_from_exchange","auto_append_margin","force_sell","bonus_issue"):
            self.row_changes={"contract_settle_fee":{"businessType":kind}}
            result=self.observe()
            self.assertIsNotNone(result.book.pending)
            self.assertFalse(result.funding_ids)

    def test_ambiguous_target_buy_funding_does_not_invent_posted_margin(self):
        self.open_btc(); self.prepare_bnb()
        # Fund target only after native opening; caller has no allocation witness.
        self.dispatch()
        p=self.positions["BNBUSDT"]
        p["funding"]-=D(".12"); self.cash-=D(".12")
        self.bill("BNBUSDT","contract_settle_fee",D("-.12"),D(0),self.f.now)
        result=self.observe()
        self.assertIsNotNone(result.book.pending)
        self.assertIsNone(result.book.observation.posted_margin)
        self.assertEqual(len(result.book.signal.economic.stages),1)

    def test_partial_target_close_with_funding_requires_separate_allocation_evidence(self):
        self.open_btc(); self.prepare_close()
        self.actual_quantity=D(".0048"); self.terminal="canceled"; self.fee=D("-.17856")
        self.funding=[("BTCUSDT",D("-.12"),D("-.12"))]
        self.dispatch(); result=self.observe()
        self.assertIsNotNone(result.book.pending)
        self.assertFalse(result.book.signal.economic.ledger.closed_baskets)
        self.assertIsNone(result.book.observation.released_margin)

    def test_other_basket_funding_and_target_close_are_atomic(self):
        self.open_btc(); self.prepare_bnb(); self.dispatch(); self.observe()
        self.prepare_close()
        self.funding=[("BNBUSDT",D(".2"),D(".2")),("BTCUSDT",D("-.12"),D(0))]
        self.dispatch(); result=self.observe()
        self.assertIsNone(result.book.pending)
        bnb=result.book.signal.economic.ledger.baskets[0]
        self.assertEqual((bnb.funding_net,bnb.isolated_balance),(D(".2"),D(293)))
        self.assertEqual(len(result.funding_ids),2)
        ledger=result.book.signal.economic.ledger
        self.assertEqual(ledger.unposted_cash+bnb.isolated_balance,self.cash)

    def test_actor_revocation_during_native_read_denies_atomic_publication(self):
        self.open_btc(); self.prepare_close()
        self.funding=[("BTCUSDT",D("-.12"),D(0))]
        self.dispatch(); before=self.f.journal.receipt
        self.revoke_at="bills"
        with self.assertRaises(ValueError): self.observe()
        self.assertEqual(self.f.journal.receipt,before)

    def test_funding_after_terminal_full_close_is_not_attributed_to_closed_cycle(self):
        self.open_btc(); self.prepare_close()
        self.funding=[("BTCUSDT",D("-.12"),D(0))]
        self.dispatch()
        self.row_changes["contract_settle_fee"]={"cTime":str(self.current["updated"]+1)}
        self.assertIsNotNone(self.observe().book.pending)

    def test_negative_price_result_and_funding_are_both_real_losses(self):
        self.open_btc(); self.prepare_close(); self.close_price=D(60000); self.fee=D("-.3456")
        self.funding=[("BTCUSDT",D("-.12"),D(0))]
        self.dispatch(); result=self.observe()
        self.assertEqual(result.book.signal.economic.ledger.realized_net_pnl,D("-10.41696"))
        self.assertEqual(result.book.signal.economic.ledger.unposted_cash,self.cash)

    def test_unknown_fee_never_completes_combined_settlement(self):
        self.open_btc(); self.prepare_close()
        self.funding=[("BTCUSDT",D("-.12"),D(0))]
        self.dispatch()
        raw_native=self.native
        def unknown(packet):
            reply=raw_native(packet)
            if type(packet) is SignedBasketRequest and packet.plan.operation=="detail":
                data=json.loads(reply.body); data["data"]["fee"]=None
                return type(reply)(reply.status,json.dumps(data).encode())
            return reply
        self.dispatcher=self.f.dispatcher(read_transport=unknown,order_transport=self.send,
            margin_resolver=None,margin_source=self.source)
        self.assertIsNotNone(self.observe().book.pending)

    def test_partial_canceled_buy_and_other_funding_book_only_actual_stage_fraction(self):
        self.open_btc(); self.prepare_bnb()
        self.actual_quantity=D(".0048"); self.terminal="canceled"; self.fee=D("-.17568")
        self.funding=[("BTCUSDT",D("-.12"),D(0))]
        self.dispatch(); result=self.observe()
        self.assertIsNone(result.book.pending)
        bnb=result.book.signal.economic.ledger.baskets[0]
        self.assertEqual((bnb.quantity,bnb.margin_committed,bnb.entry_fees),
                         (D(".0048"),D("146.4"),D(".17568")))
        self.assertIn("terminal_partial_entry",result.book.notices)

    def test_own_profitable_close_covers_concurrent_funding_reserve_overrun(self):
        self.open_btc(); self.prepare_close(); self.close_price=D(70000); self.fee=D("-.4032")
        self.funding=[("BTCUSDT",D(-40),D(0))]
        self.dispatch(); result=self.observe()
        ledger=result.book.signal.economic.ledger
        self.assertEqual((ledger.closed_baskets,ledger.realized_net_pnl),
                         (1,D("45.64544")))
        self.assertNotIn("basket_budget_breach",ledger.halt_reasons)

    def test_duplicate_funding_bill_id_cannot_double_book_or_complete_order(self):
        self.open_btc(); self.prepare_close()
        self.funding=[("BTCUSDT",D("-.12"),D(0))]
        self.dispatch()
        self.rows.append(dict(next(r for r in self.rows if r["businessType"]=="contract_settle_fee")))
        result=self.observe()
        self.assertIsNotNone(result.book.pending)
        self.assertFalse(result.funding_ids)

    def test_eight_nonempty_pages_do_not_prove_terminal_bill_coverage(self):
        self.open_btc(); self.prepare_close()
        self.funding=[("BTCUSDT",D("-.12"),D(0))]
        self.dispatch()
        original=next(r for r in self.rows if r["businessType"]=="contract_settle_fee")
        self.pages=[dict(bills=[{**original,"billId":str(500-i)}],endId=str(500-i)) for i in range(8)]
        result=self.observe()
        self.assertIsNotNone(result.book.pending)
        self.assertFalse(result.funding_ids)

    def test_unknown_funding_pool_cannot_assert_actual_reserve_breach(self):
        self.open_btc(); self.prepare_close()
        self.funding=[("BTCUSDT",D(-40),D(-40))]
        self.dispatch()
        before=self.f.journal.receipt
        with self.assertRaisesRegex(ValueError,"pool needed"):
            self.observe()
        self.assertEqual(self.f.journal.receipt,before)
        self.assertNotIn("basket_budget_breach",self.f.journal.state.book.signal.economic.ledger.halt_reasons)


if __name__=="__main__": unittest.main()
