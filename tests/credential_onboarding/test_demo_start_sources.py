"""Real AEAD/HMAC/journal/worker; actor and native account/candle replies synthetic."""
from datetime import timedelta
from decimal import Decimal
import unittest

import test_demo_basket_orders as fixture
from test_futures_demo import OWNER, OTHER, response
from test_futures_demo_signals import END, NOW, rows, response as candles_response
from investalo_bitget.futures_demo import DemoRejected
from investalo_bitget.models import BitgetRejected
from investalo_bitget.futures_demo_bootstrap import native_start_account
from investalo_bitget.futures_demo_signals import signal_url
from investalo_bitget.futures_demo_warmup import DemoWarmupSource
from investalo_bitget.futures_demo_read import SignedDemoReadRequest
from investalo_bitget.signing import hmac_sha256_base64
from investalo_credential_store.demo_start_account import NativeStartAccountSource
from investalo_credential_store.demo_trading_secret import DemoTradingSecretRejected
from investalo_trading.futures_broker_journal import BrokerEntryJournal
from investalo_trading.futures_ledger import LedgerMark
from investalo_trading.futures_broker_bootstrap import BrokerFlatAccount
from investalo_workers.futures_demo_bootstrap import DemoBootstrapWorker

D = Decimal


def wallet(**changes):
    return dict(marginCoin="USDT", accountEquity="10000", available="10000",
        locked="0", unrealizedPL="0", isolatedMargin="0", crossedMargin="0",
        coupon="0", grant="0", assetMode="single", **changes)


class NativeStartSourceTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.BasketNativeTests(); self.f.setUp()
        self.wallet_changes, self.identity_changes, self.positions = {}, {}, []
        self.calls, self.mutate = [], lambda _: None
        def native(packet):
            self.assertIs(type(packet), SignedDemoReadRequest); packet.validate()
            self.assertEqual(packet.method, "GET")
            self.assertEqual(packet.headers["paptrading"], "1")
            self.assertEqual(packet.headers["ACCESS-SIGN"], hmac_sha256_base64(self.f.credentials._secret_key,
                (str(self.f.now)+"GET"+packet.target).encode()))
            self.calls.append(packet.axis)
            if packet.axis == "identity":
                data = dict(userId="123456", parentId=0, ips="", authorities=["coow", "cpow", "stow"])
                data.update(self.identity_changes)
            elif packet.axis == "wallet":
                data = [wallet() | self.wallet_changes]
            elif packet.axis == "positions":
                data = self.positions
            else:
                raise AssertionError("unexpected native operation")
            result = response(data, at=self.f.now)
            self.mutate(packet.axis)
            return result
        self.transport = native
        self.source = NativeStartAccountSource(self.f.provider, guard=lambda: None,
            shared_lock=self.f.mutex, ip_binding="unavailable_in_demo",
            transport=native, milliseconds=lambda: self.f.now)

    def tearDown(self):
        self.f.tearDown()

    def test_three_fixed_gets_yield_original_current_flat_account_without_order_or_grant(self):
        original = self.f.journal.receipt
        result = self.source.read(context=OWNER)
        self.assertEqual(self.calls, ["identity", "wallet", "positions"])
        self.assertIs(type(result.account), BrokerFlatAccount)
        self.assertEqual(result.account.equity, D(10000))
        self.assertEqual(result.blockers, ())
        self.assertFalse(result.execution_enabled)
        self.assertEqual(self.f.sent, [])
        self.assertNotIn("consume-basket", self.f.events)
        self.assertEqual(self.f.journal.receipt, original)

    def test_missing_collateral_amounts_and_positive_extra_capital_stay_blocked(self):
        for values, reason in [
            ({"grant": None}, "collateral_unconfirmed"), ({"coupon": ""}, "collateral_unconfirmed"),
            ({"grant": "1"}, "foreign_collateral"), ({"accountEquity": None}, "account_amounts_unconfirmed"),
            ({"available": "9000"}, "account_not_flat"), ({"assetMode": "union"}, "wallet_profile_unconfirmed"),
        ]:
            self.wallet_changes = values
            self.f.now += 1000
            result = self.source.read(context=OWNER)
            self.assertIsNone(result.account); self.assertIn(reason, result.blockers)

    def test_existing_native_position_is_not_adopted_even_when_wallet_claims_flat(self):
        self.positions = [dict(symbol="BTCUSDT", marginCoin="USDT", holdSide="long",
            marginMode="isolated", posMode="one_way_mode", leverage="2",
            total="0.01", available="0.01", locked="0", marginSize="300")]
        result = self.source.read(context=OWNER)
        self.assertIsNone(result.account); self.assertIn("positions_not_flat", result.blockers)

    def test_uid_parent_rights_and_unexpected_whitelist_reject_before_wallet(self):
        for values in [{"userId": "987654"}, {"parentId": 99}, {"authorities": ["coow", "stow"]},
                       {"ips": "192.0.2.99"}]:
            self.identity_changes = values; self.calls.clear(); self.f.now += 1000
            with self.assertRaises((DemoRejected, BitgetRejected)):
                self.source.read(context=OWNER)
            self.assertEqual(self.calls, ["identity"])

    def test_foreign_actor_busy_source_fork_and_revocation_never_publish(self):
        with self.assertRaises(DemoRejected): self.source.read(context=OTHER)
        self.assertEqual(self.calls, [])
        self.f.mutex.acquire()
        try:
            with self.assertRaises(DemoRejected): self.source.read(context=OWNER)
        finally: self.f.mutex.release()
        self.source.pid -= 1
        with self.assertRaises(DemoRejected): self.source.read(context=OWNER)
        self.source.pid += 1
        self.mutate = lambda axis: setattr(self.f, "revoked", True) if axis == "wallet" else None
        with self.assertRaises(DemoTradingSecretRejected): self.source.read(context=OWNER)
        self.assertEqual(self.calls, ["identity", "wallet"])

    def test_cohort_clock_cannot_be_renewed_by_a_late_reply_and_failed_reads_consume_quota(self):
        self.mutate = lambda axis: setattr(self.f, "now", self.f.now+5001) if axis == "wallet" else None
        with self.assertRaises(DemoRejected): self.source.read(context=OWNER)
        self.assertNotIn("positions", self.calls)
        self.mutate = lambda _: None
        self.source.last = self.f.now
        with self.assertRaises(DemoRejected): self.source.read(context=OWNER)
        self.assertEqual(self.calls, ["identity", "wallet"])

    def test_independent_current_actor_guard_revocation_blocks_publication(self):
        checks = []
        def guard():
            checks.append(True)
            if len(checks) == 3:
                raise DemoRejected("synthetic actor revoked")
        self.source.guard = guard
        with self.assertRaisesRegex(DemoRejected, "actor revoked"):
            self.source.read(context=OWNER)
        self.assertEqual(self.calls, ["identity"])

    def test_whole_product_parser_rejects_duplicate_wallet_and_stale_clocks(self):
        binding = self.f.spec.binding
        with self.assertRaises((DemoRejected, BitgetRejected)):
            native_start_account(response([wallet(), wallet()], at=self.f.now),
                response([], at=self.f.now), binding, context=OWNER, now_ms=self.f.now)
        with self.assertRaises(DemoRejected):
            native_start_account(response([wallet()], at=self.f.now-5001),
                response([], at=self.f.now), binding, context=OWNER, now_ms=self.f.now)


class NativeWarmupSourceTests(unittest.TestCase):
    def source(self, **changes):
        calls = []
        def fetch(symbol, end, *, kind, timeout_seconds):
            calls.append((symbol, kind, end))
            self.assertLessEqual(timeout_seconds, 3)
            values = rows(end)
            if kind == "mark":
                values = [[r[0], *(str(D(v)+D(".5")) for v in r[1:5]), *r[5:]] for r in values]
            return candles_response(values)
        return DemoWarmupSource(fetch=changes.get("fetch", fetch), clock=lambda: NOW), calls

    def test_dual_native_axes_all_original_frames_and_cache_preserve_source_time(self):
        source, calls = self.source()
        window = source.collect(("BNBUSDT", "BTCUSDT", "ETHUSDT"), END)
        self.assertEqual(len(calls), 6); self.assertEqual(len(window.frames), 300)
        self.assertEqual(window.frames[-1].close_time, END)
        self.assertEqual(window.frames[0].trade[1].symbol, "BTCUSDT:USDT-M:trade")
        self.assertEqual(window.frames[0].mark[1].close-window.frames[0].trade[1].close, D(".5"))
        self.assertIs(source.collect(window.symbols, END), window)
        self.assertEqual(len(calls), 6); self.assertEqual(window.fetched_at, NOW)
        self.assertFalse(window.execution_enabled)

    def test_restart_slice_keeps_original_closed_window_after_new_hour_without_current_substitution(self):
        source, calls = self.source()
        source.clock = lambda: NOW+timedelta(hours=2)
        source.fetch = lambda symbol, end, **_: candles_response(rows(end), at=NOW+timedelta(hours=2))
        first = source(symbols=("BNBUSDT", "BTCUSDT", "ETHUSDT"), end=END, offset=24, count=24)
        self.assertEqual(first[0].close_time, END-timedelta(hours=275))
        self.assertEqual(first[-1].close_time, END-timedelta(hours=252))
        self.assertEqual(source.window.end, END)
        for offset, count in [(-1, 24), (0, 25), (299, 2)]:
            with self.assertRaises(ValueError):
                source(symbols=source.window.symbols, end=END, offset=offset, count=count)

    def test_mark_failure_duplicate_and_missing_bar_publish_no_partial_window(self):
        for variant in ("failure", "duplicate", "missing"):
            def fetch(symbol, end, *, kind, **_):
                values = rows(end)
                if kind == "mark" and symbol == "BTCUSDT":
                    if variant == "failure": raise OSError("synthetic native failure")
                    if variant == "duplicate": values[-1] = values[-2]
                    if variant == "missing": values.pop()
                return candles_response(values)
            source, _ = self.source(fetch=fetch)
            with self.assertRaises((ValueError, OSError)):
                source.collect(("BNBUSDT", "BTCUSDT", "ETHUSDT"), END)
            self.assertIsNone(source.window)

    def test_scope_urls_future_windows_and_fork_are_rejected(self):
        self.assertIn("kLineType=market", signal_url("BTCUSDT", END))
        self.assertIn("kLineType=mark", signal_url("BTCUSDT", END, "mark"))
        with self.assertRaises(ValueError): signal_url("BTCUSDT", END, "index")
        source, calls = self.source()
        for symbols in [("BTCUSDT",)*3, ("BTCUSDT", "ETHUSDT", "SBTCSUSDT")]:
            with self.assertRaises(ValueError): source.collect(symbols, END)
        with self.assertRaises(ValueError): source.collect(("BNBUSDT", "BTCUSDT", "ETHUSDT"), END+timedelta(hours=1))
        source.pid -= 1
        with self.assertRaises(ValueError): source.collect(("BNBUSDT", "BTCUSDT", "ETHUSDT"), END)
        self.assertEqual(calls, [])

    def test_complete_source_drives_real_worker_journal_without_historical_financial_events(self):
        f = fixture.BasketNativeTests(); f.setUp()
        try:
            path = f.path.parent/"current-native"
            profile = fixture.native_profile()
            quotes = tuple(LedgerMark(s, D(1000)) for s in profile.plan.symbols)
            account = BrokerFlatAccount(D(10000), D(10000), D(0), D(0), D(0), 0, NOW, NOW, "a"*64)
            source, calls = self.source()
            with BrokerEntryJournal.create_current(path, profile, quotes, quotes, account, NOW,
                                                   journal_id=fixture.JOURNAL_ID) as journal:
                initial = journal.state.book.signal.economic
                worker = DemoBootstrapWorker(journal, source, lambda: None, lambda: NOW)
                while not worker.warm_once().ready: pass
                self.assertEqual(len(calls), 6)
                self.assertEqual(journal.state.book.signal.economic, initial)
                self.assertEqual(journal.state.warmed_hours, 300)
                self.assertEqual(journal.state.book.signal.signals[1].entry_indicator.rsi, 0)
        finally:
            f.tearDown()
