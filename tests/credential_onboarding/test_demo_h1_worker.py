"""Real strategy/journal/consumer/AEAD/packets; synthetic current native replies."""
from dataclasses import replace, fields
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
import json
import unittest
from uuid import uuid4

import test_demo_basket_orders as fixture
from test_demo_worker_authorization import wire, KEY
from test_demo_worker_bootstrap import account, frames, START
from test_futures_demo import BINDING, OWNER, response
from test_futures_capital_signals import hour
from investalo_bitget import parse
from investalo_bitget.futures_demo_basket import BasketMarketGrid
from investalo_bitget.futures_demo_read import SignedDemoReadRequest
from investalo_bitget.futures_demo_policy import ApprovedDemoStrategyPolicy
from investalo_bitget.futures_demo_margin import margin_snapshot
from investalo_credential_store.demo_basket_orders import SignedBasketRequest, milliseconds
from investalo_credential_store.demo_basket_margin import BasketNativeMarginSource
from investalo_credential_store.demo_basket_funding import BasketNativeFundingSource
from investalo_credential_store.demo_trading_provider import SealedDemoTradingProvider
from investalo_credential_store.demo_worker_authorization import DurableBasketConsumer
from investalo_credential_store.demo_h1_market import NativeMarketView
from investalo_trading.futures_broker_plan import CapitalBrokerPlan, BrokerGridRule
from investalo_trading.futures_broker_journal import BrokerEntryJournal
from investalo_trading.futures_ledger import LedgerMark
from investalo_trading.capital_digest import digest
from investalo_workers.futures_demo_h1_worker import DemoH1Worker

D = Decimal


class H1WorkerTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.BasketNativeTests(); self.f.setUp()
        self.f.journal.close()
        self.f.path = Path(self.f.temp.name)/"operative"
        original = fixture.native_profile()
        self.policy = ApprovedDemoStrategyPolicy(BINDING, 1, 1)
        args = {f.name: getattr(original.plan, f.name) for f in fields(original.plan) if f.init}
        args["grid_rules"] = tuple(BrokerGridRule(r.symbol, r.price_tick, None) for r in original.plan.grid_rules)
        profile = replace(original, plan=CapitalBrokerPlan(**args, budget_indices=(0,)*3,
            approved_policy_digest=self.policy.policy_digest))
        quotes = tuple(LedgerMark(s, D(61000)) for s in profile.plan.symbols)
        self.f.journal = BrokerEntryJournal.create_current(self.f.path, profile, quotes, quotes,
            account(START), START, journal_id=uuid4())
        self.f.now = milliseconds(START)
        self.control = wire(self.f.now, assets=["BTCUSDT"])
        root = Path(self.f.temp.name)/"consumer"; root.mkdir(mode=0o700)
        self.consumer = DurableBasketConsumer(root, binding=BINDING, intent_key=KEY,
            read_control=lambda: self.control, actor_guard=lambda _: self.f.load_snapshot(BINDING, OWNER),
            journal=self.f.journal, milliseconds=lambda: self.f.now)
        self.values = list(frames(self.f.journal))
        self.warmup = SimpleNamespace(
            __call__=None, collect=lambda symbols, end: SimpleNamespace(frames=tuple(self.values[-300:])))
        class Source:
            def __call__(_, **v): return tuple(self.values[v["offset"]:v["offset"]+v["count"]])
            def collect(_, symbols, end): return SimpleNamespace(frames=tuple(self.values[-300:]))
        self.worker = DemoH1Worker(self.f.journal, self.consumer, Source(), self.now)
        self.posts, self.trades = [], []
        self.native_quantity, self.native_average = D(0), D(0)
        self.native_margin, self.native_fees, self.native_pnl = D(0), D(0), D(0)
        self.quote = D(61000)
        self.lost_ack = False
        self.new_ports()

    def now(self):
        return parse.EPOCH+timedelta(milliseconds=self.f.now)

    def new_ports(self):
        self.f.provider = SealedDemoTradingProvider(self.f.spec, expected_storage=1,
            read_snapshot=self.f.load_snapshot, load_keyring=lambda: self.f.ring,
            expires_ms=self.f.now+60000, milliseconds=lambda: self.f.now)
        source = BasketNativeMarginSource(transport=self.native, milliseconds=lambda: self.f.now, policy=self.policy)
        dispatcher = self.f.dispatcher(read_transport=self.native, order_transport=self.send,
            margin_resolver=None, margin_source=source, funding_source=BasketNativeFundingSource(source),
            authorize_once=self.consumer)
        def market():
            self.f.now += 1
            marks = tuple(LedgerMark(s, self.quote) for s in self.f.journal.state.book.signal.profile.plan.symbols)
            return NativeMarketView((), marks, marks, tuple((p.symbol,p.price) for p in marks),
                self.now(), digest(("synthetic-ticker", self.f.now, self.quote)))
        self.ports = SimpleNamespace(owner=OWNER, dispatcher=dispatcher,
            guard=lambda: self.f.load_snapshot(BINDING, OWNER), market=SimpleNamespace(read=market))

    def native(self, packet):
        self.f.now += 1
        if type(packet) is SignedDemoReadRequest:
            return self.f.native(packet)
        self.assertIs(type(packet), SignedBasketRequest)
        packet.consume()
        op, intent = packet.plan.operation, packet.plan.intent
        if op == "wallet":
            upl = D(25) if self.native_quantity else D(0)
            return response([dict(marginCoin="USDT", assetMode="single", locked="0", crossedMargin="0",
                coupon="0", grant=None, accountEquity=str(D(10000)+self.native_pnl-self.native_fees+upl),
                unrealizedPL=str(upl), isolatedMargin=str(self.native_margin))], at=self.f.now)
        if op == "positions":
            rows = [] if not self.native_quantity else [dict(symbol="BTCUSDT", marginCoin="USDT", holdSide="long",
                marginMode="isolated", posMode="one_way_mode", leverage="2", total=str(self.native_quantity),
                available=str(self.native_quantity), locked="0", openPriceAvg=str(self.native_average),
                marginSize=str(self.native_margin), assetMode="single", autoMargin="off", openDelegateSize="0",
                totalFee="", deductedFee=str(self.native_fees), achievedProfits="0")]
            return response(rows, at=self.f.now)
        if op == "bills":
            rows = [] if packet.plan.cursor else [r for r in self.trades
                if packet.plan.start_ms <= int(r["cTime"]) <= packet.plan.end_ms]
            return response(dict(bills=rows, endId=rows[-1]["billId"] if rows else None), at=self.f.now)
        if op == "detail":
            p = self.posts[-1]
            return response(dict(symbol="BTCUSDT", clientOid=intent.client_oid, orderId="123", marginCoin="USDT",
                marginMode="isolated", posMode="one_way_mode", posSide="net", leverage="2", size=str(intent.quantity),
                side=p["side"], reduceOnly=p["reduceOnly"].lower(), orderType="market", state="filled",
                baseVolume=str(intent.quantity), priceAvg=p["fill"], fee=p["fee"],
                cTime=p["at"], uTime=str(self.f.now)), at=self.f.now)
        raise AssertionError("unsupported synthetic native request")

    def send(self, packet):
        self.assertEqual(self.f.journal.state.recovery_mode, "get_only")
        self.assertEqual(json.loads(self.f.path.read_bytes().splitlines()[-1])["command"]["kind"], "attempt_with_margin")
        self.assertTrue(list((Path(self.f.temp.name)/"consumer").glob("consumed-*")))
        packet.consume()
        terms = json.loads(packet.body)
        quantity = D(terms["size"]); price = self.quote
        fee = quantity*price*D(".0006")
        pnl = D(0) if terms["side"] == "buy" else quantity*(price-self.native_average)
        if terms["side"] == "buy":
            self.native_quantity += quantity
            self.native_average = price
            self.native_margin += quantity*price/2
        else:
            self.native_quantity -= quantity
            self.native_margin = D(0)
        self.native_fees += fee; self.native_pnl += pnl
        at = str(milliseconds(self.f.journal.state.current_attempt.attempted_at))
        self.posts.append({**terms, "fill":str(price), "fee":str(-fee), "at":at})
        self.trades.append(dict(billId=str(100+len(self.trades)), symbol="BTCUSDT", coin="USDT",
            businessType=terms["side"], amount=str(pnl), fee=str(-fee), feeByCoupon="", cTime=at))
        if self.lost_ack:
            raise OSError("synthetic ACK lost")
        return response(dict(clientOid=packet.plan.intent.client_oid, orderId="123"), at=self.f.now)

    def warmed(self):
        for _ in range(13):
            self.worker.run_once(self.ports)
        self.assertEqual(self.f.journal.state.warmed_hours, 300)

    def fresh_hour(self):
        end = self.values[-1].close_time+timedelta(hours=1)
        self.values.append(hour(self.f.journal.state.book.signal, D(60000), all_assets=True, close=end))
        self.f.now = milliseconds(end)+2000
        self.new_ports()

    def tearDown(self):
        self.consumer.close(); self.f.tearDown()

    def test_no_historical_buy_then_real_stage_margin_times2_and_native_fill(self):
        self.warmed(); self.assertEqual(self.posts, [])
        self.fresh_hour()
        p = self.worker.run_once(self.ports)
        self.assertEqual(p.detail, "entry_reconciliation")
        self.assertEqual(len(self.posts), 1)
        self.assertGreater(D(self.posts[0]["size"])*61000, 500)
        self.assertEqual(self.f.journal.state.book.signal.economic.stages, ())
        p = self.worker.run_once(self.ports)
        self.assertEqual(p.detail, "order_settled")
        basket = self.f.journal.state.book.signal.economic.ledger.baskets[1]
        self.assertEqual((basket.quantity, basket.margin_committed), (self.native_quantity, self.native_margin))
        self.assertEqual(len(self.f.journal.state.book.signal.economic.stages), 1)

    def test_lost_post_ack_only_recovers_gets_and_never_duplicates_entry(self):
        self.warmed(); self.fresh_hour(); self.lost_ack = True
        self.worker.run_once(self.ports)
        self.worker.run_once(self.ports)
        self.assertEqual(len(self.posts), 1)
        self.assertIsNone(self.f.journal.state.book.pending)

    def test_pause_owns_position_and_reduce_only_exit_still_runs(self):
        self.warmed(); self.fresh_hour()
        self.worker.run_once(self.ports); self.worker.run_once(self.ports)
        self.control = wire(self.f.now, action="pause", revision=2, assets=["BTCUSDT"])
        self.quote = D(65000)
        p = self.worker.run_once(self.ports)
        self.assertEqual(p.state, "paused", repr(self.f.journal.state.book.signal.signals[1]))
        self.quote = D(61000)
        p = self.worker.run_once(self.ports)
        self.assertEqual(p.detail, "exit_reconciliation")
        self.assertEqual(self.posts[-1]["reduceOnly"], "YES")
        self.worker.run_once(self.ports)
        self.assertEqual(self.native_quantity, 0)
        self.assertEqual(self.f.journal.state.book.signal.economic.ledger.baskets[1].quantity, 0)

    def test_closed_hours_after_financial_observation_do_not_backdate_cash_or_buy(self):
        self.warmed()
        before = self.f.journal.state.book.signal.economic
        end = self.values[-1].close_time+timedelta(hours=1)
        frame = hour(self.f.journal.state.book.signal, D(60000), all_assets=True, close=end)
        self.f.now = milliseconds(end)+60000
        self.f.journal.append("native_hour", frame=frame, expected_revision=self.f.journal.state.revision, at=self.now())
        self.assertEqual(self.f.journal.state.book.signal.economic, before)
        self.assertIsNone(self.f.journal.state.book.signal.last_entry_at)

    def test_restore_native_unknown_grid_preserves_original_cash_and_prefix(self):
        self.warmed()
        receipt = self.f.journal.receipt
        j = self.f.journal
        uuid = __import__("uuid").UUID(j._header["journal_id"])
        profile = j.state.book.signal.profile.profile_digest
        j.close()
        self.f.journal = BrokerEntryJournal.restore(self.f.path, journal_id=uuid,
            profile_digest=profile, minimum_receipt=receipt)
        self.assertEqual(self.f.journal.receipt, receipt)
        self.assertIsNone(self.f.journal.state.book.signal.profile.plan.grid_rules[0].maximum_market_quantity)

    def test_unapproved_unknown_grid_still_rejected_known_small_max_does_not_shrink_stage(self):
        with self.assertRaises(ValueError):
            BasketMarketGrid("BTCUSDT", D(".0001"), D(".1"), D(".0001"), D(5), None)
        plan = self.f.journal.state.book.signal.profile.plan
        limited = replace(plan, grid_rules=tuple(replace(r, maximum_market_quantity=D(".0001")) for r in plan.grid_rules))
        with self.assertRaisesRegex(ValueError, "complete native stage"):
            limited.entry_quantity("BTCUSDT", D(293), D(2), D(61000))

    def test_native_ceiling_update_preserves_capital_and_original_budget(self):
        self.warmed()
        ledger = self.f.journal.state.book.signal.economic.ledger
        self.f.journal.append("native_limit", limit=4,
            expected_revision=self.f.journal.state.revision, at=self.now())
        updated = self.f.journal.state.book.signal.economic.ledger
        self.assertEqual(updated.unposted_cash, ledger.unposted_cash)
        self.assertEqual(updated.plan.budgets, ledger.plan.budgets)
        self.assertEqual(updated.plan.configured_limit, 4)

    def test_native_next_day_basis_uses_observed_time_without_historical_midnight_cash(self):
        self.warmed()
        self.f.now = milliseconds(START+timedelta(days=1))
        marks = tuple(LedgerMark(s,D(61000)) for s in self.f.journal.state.book.signal.profile.plan.symbols)
        self.f.journal.append("prices", trade=marks, marks=marks, event_id="actual-new-day",
            expected_revision=self.f.journal.state.revision, at=self.now())
        ledger = self.f.journal.state.book.signal.economic.ledger
        self.assertEqual(ledger.day_started_at, self.now())
        self.assertEqual(ledger.unposted_cash, D(10000))
