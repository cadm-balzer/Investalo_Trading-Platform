"""Account projection and real signed readonly authority; synthetic native replies."""
import base64
import hashlib
import hmac
import json
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID, uuid4

from investalo_bitget import Credentials, OwnerContext
from investalo_bitget.futures_demo import DemoBinding
from investalo_bitget.transport import ReadResponse
from investalo_credentials import KEKRing
from investalo_credential_store.demo_account_sync import DemoAccountReader, KIND, PATH, positions, validate_view
from investalo_credential_store.demo_trading_provider import DemoTradingSecretSnapshot, SealedDemoTradingProvider
from investalo_credential_store.demo_trading_secret import DemoTradingSecretSpec, seal_demo_trading_secret
from investalo_credential_store.models import StoreContext
from investalo_credential_store.passkey_request_assertion import PasskeyRequestContext
from investalo_credential_store.private_http import (
    DemoTradingAccountHTTPApplication, DemoTradingCredentialHTTPApplication, _application_targets,
)
from investalo_credential_store.request_assertion import OnboardingRejected
import threading
from investalo_bitget.futures_demo_account import CONFIGS, AXES
from investalo_credential_store.demo_startup_check import validate_startup

KEY = b"S" * 32


class DemoAccountTests(unittest.TestCase):
    def setUp(self):
        self.now = int(time.time())
        self.context = PasskeyRequestContext(tenant_id=UUID(int=1), user_id=UUID(int=2),
            subject="synthetic-account-owner", auth_epoch=3, oidc_auth_time=self.now-3600,
            session_binding="a"*64, session_expires_at=self.now+3600)
        self.config = dict(account_id=UUID(int=3), broker_uid="123456", parent_uid="0",
            egress_ip="192.0.2.8", ip_binding="unavailable_in_demo",
            origin="https://cockpit.investalo.de", oidc_issuer="https://auth.cockpit.investalo.de")
        self.target = dict(platform_account_id=str(UUID(int=3)), connection_id=str(UUID(int=4)),
            credential_revision=1, storage_version=1)
        self.body = json.dumps(self.target).encode()
        self.owner = OwnerContext(UUID(int=1), UUID(int=2))
        self.binding = DemoBinding(self.owner, UUID(int=3), UUID(int=4), "123456")
        spec = DemoTradingSecretSpec(binding=self.binding, parent_uid="0", egress_ip="192.0.2.8",
            authorities=("coow", "cpow", "stow"), provisioning_digest="d"*64, credential_revision=1)
        self.ring = KEKRing((("synthetic", b"K"*32),), active_version="synthetic")
        self.snapshot = DemoTradingSecretSnapshot(spec, seal_demo_trading_secret(
            Credentials("synthetic-api", "synthetic-secret", "synthetic-pass"), spec, self.ring), storage_version=1)
        self.sent, self.revoked = [], False
        self.identity = dict(userId="123456", parentId=0, authorities=["coow", "cpow", "stow"], ips="")
        self.wallet = [dict(marginCoin="USDT", accountEquity="50000", available="49000", locked="0",
            unrealizedPL="-12.25", isolatedMargin="1000", crossedMargin="0")]
        self.rows = [dict(symbol="BTCUSDT", marginCoin="USDT", holdSide="long", marginMode="isolated",
            total="0.1", openPriceAvg="60000", markPrice="59000", unrealizedPL="-100",
            leverage="2", liquidationPrice="-1")]
        def transport(request):
            self.sent.append(request)
            data = dict(identity=self.identity, wallet=self.wallet, positions=self.rows)[request.axis]
            return ReadResponse(200, json.dumps(dict(code="00000", requestTime=int(time.time()*1000), data=data)).encode())
        self.native = SimpleNamespace(lock=threading.Lock(), last=None, guard=lambda: None, transport=transport)
        self.reader = DemoAccountReader(self.config, StoreContext(tenant_id=UUID(int=1), user_id=UUID(int=2),
            expected_login_role="synthetic"), connect=lambda: None, keyring=lambda: self.ring,
            signing_key=KEY, native=self.native)

    def token(self, **changes):
        claims = {k: (str(getattr(self.context, k)) if isinstance(getattr(self.context, k), UUID)
            else getattr(self.context, k)) for k in self.context.__slots__}
        claims.update(kind=KIND, aud="investalo-demo-account-read", oidc_issuer=self.config["oidc_issuer"],
            origin=self.config["origin"], iat=self.now, exp=self.now+15, jti=str(uuid4()),
            htm="POST", htu=PATH, body_sha256=hashlib.sha256(self.body).hexdigest())
        claims.update(changes)
        enc = lambda v: base64.urlsafe_b64encode(v).rstrip(b"=").decode()
        a, b = enc(b'{"alg":"HS256","typ":"JWT"}'), enc(json.dumps(claims).encode())
        return a+"."+b+"."+enc(hmac.digest(KEY, (a+"."+b).encode(), "sha256"))

    def run_read(self, **changes):
        def read(binding, owner):
            if self.revoked:
                raise OnboardingRejected("access_denied")
            self.assertEqual((binding, owner), (self.binding, self.owner))
            return self.snapshot
        def provider(spec, *, expected_storage, load_keyring):
            return SealedDemoTradingProvider(spec, expected_storage=expected_storage,
                read_snapshot=read, load_keyring=load_keyring, expires_ms=(self.now+15)*1000)
        store = SimpleNamespace(read_snapshot=read, provider=provider)
        with patch("investalo_credential_store.demo_account_sync.DemoTradingCredentialStore", return_value=store):
            return self.reader(self.context, self.token(**changes), self.body)

    def test_three_signed_demo_gets_real_aead_and_safe_projection(self):
        view = self.run_read()
        self.assertEqual([r.axis for r in self.sent], ["identity", "wallet", "positions"])
        for r in self.sent:
            self.assertEqual((r.method, r.headers["paptrading"], r.body), ("GET", "1", b""))
        self.assertEqual(view["wallet"]["equity"], "50000")
        self.assertEqual(view["positions"][0]["liquidation_price"], None)
        self.assertNotIn("synthetic", json.dumps(view))
        self.assertEqual(set(view), {"schema", "tenant_id", "account_id", "observed_at", "currency", "wallet", "positions"})

    def test_read_purpose_context_time_and_body_tampering_deny_before_io(self):
        for change in (dict(kind="demo-trading-credential-write"), dict(aud="investalo-demo-trading"),
            dict(auth_epoch=4), dict(subject="foreign"), dict(exp=self.now+16),
            dict(iat=self.now+1), dict(exp=self.now), dict(body_sha256="b"*64)):
            with self.subTest(change=change), self.assertRaises(OnboardingRejected):
                self.run_read(**change)
        self.assertEqual(self.sent, [])

    def test_read_token_replay_denied(self):
        token = self.token()
        self.reader._authorize(self.context, token, self.body)
        with self.assertRaises(OnboardingRejected):
            self.reader._authorize(self.context, token, self.body)

    def test_identity_drift_stops_before_wallet_no_retry(self):
        self.identity["userId"] = "999999"
        with self.assertRaises(OnboardingRejected):
            self.run_read()
        self.assertEqual([r.axis for r in self.sent], ["identity"])

    def test_revocation_between_native_calls_stops_publication(self):
        original = self.native.transport
        def revoke(request):
            result = original(request)
            if request.axis == "wallet":
                self.revoked = True
            return result
        self.native.transport = revoke
        with self.assertRaises(OnboardingRejected):
            self.run_read()
        self.assertEqual([r.axis for r in self.sent], ["identity", "wallet"])

    def test_empty_positions_and_unknown_wallet_are_not_invented(self):
        self.rows, self.wallet[0]["locked"] = [], ""
        view = self.run_read()
        self.assertEqual(view["positions"], [])
        self.assertIsNone(view["wallet"]["locked"])

    def test_duplicate_invalid_oversized_position_records_deny(self):
        for rows in ([self.rows[0]]*2, [dict(self.rows[0], total="NaN")], [self.rows[0]]*101):
            response = ReadResponse(200, json.dumps(dict(code="00000", requestTime=self.now*1000, data=rows)).encode())
            with self.subTest(rows=len(rows)), self.assertRaises(Exception):
                positions(response)

    def test_private_fields_rejected_from_projection(self):
        view = self.run_read()
        view["broker_uid"] = "123456"
        with self.assertRaises(ValueError):
            validate_view(view)

    def test_read_path_requires_explicit_trusted_application(self):
        for cls in (DemoTradingCredentialHTTPApplication, DemoTradingAccountHTTPApplication):
            app = cls(self.reader.context, lambda *args: None, enabled=True)
            self.assertEqual(PATH in _application_targets(app).values(), cls is DemoTradingAccountHTTPApplication)

    def startup(self, handler=None):
        self.target["inspection"] = "startup"
        self.body = json.dumps(self.target).encode()
        self.rows = []
        self.wallet = [dict(marginCoin="USDT", accountEquity="10000", available="10000", locked="0",
            unrealizedPL="0", isolatedMargin="0", crossedMargin="0", assetMode="single", coupon="0", grant="0")]
        original = self.native.transport
        def transport(request):
            if request.axis in ("identity", "wallet", "positions"):
                return original(request)
            self.sent.append(request)
            data = dict(marginCoin="USDT", marginMode="isolated", posMode="one_way_mode",
                        isolatedLongLever=2, assetMode="single") if request.axis in CONFIGS else dict(
                            entrustedList=[], endId="")
            if handler is not None:
                data = handler(request, data)
            return ReadResponse(200, json.dumps(dict(code="00000", requestTime=int(time.time()*1000), data=data)).encode())
        self.native.transport = transport

    def test_startup_collects_every_fixed_axis_without_granting_execution(self):
        self.startup()
        with patch("investalo_credential_store.demo_account_sync.time.sleep"):
            report = self.run_read()
        self.assertEqual([r.axis for r in self.sent[:3]], ["identity", "wallet", "positions"])
        self.assertCountEqual([r.axis for r in self.sent[3:]], [*CONFIGS, *AXES[2:]])
        self.assertEqual(report["blockers"], [])
        self.assertTrue(all(c["matches"] for c in report["configurations"]))
        self.assertTrue(all(o["complete"] and o["count"] == 0 for o in report["orders"]))
        for key in ("pending_scope_verified", "costs_verified", "execution_enabled"):
            self.assertIs(report[key], False)
        self.assertNotIn("synthetic", json.dumps(report))
        self.assertTrue(all(r.method == "GET" and r.headers["paptrading"] == "1" for r in self.sent))

    def test_configuration_drift_and_unknown_are_visible_not_auto_modified(self):
        def drift(request, data):
            if request.axis == "BTCUSDT":
                return dict(data, isolatedLongLever="10", marginMode="crossed", posMode="hedge_mode")
            if request.axis == "ETHUSDT":
                return dict(data, isolatedLongLever=None, assetMode="new_unknown_mode")
            return data
        self.startup(drift)
        with patch("investalo_credential_store.demo_account_sync.time.sleep"):
            report = self.run_read()
        self.assertEqual(report["blockers"], ["configuration_mismatch"])
        btc = next(c for c in report["configurations"] if c["symbol"] == "BTCUSDT")
        self.assertEqual((btc["long_leverage"], btc["matches"]), ("10", False))
        eth = next(c for c in report["configurations"] if c["symbol"] == "ETHUSDT")
        self.assertIsNone(eth["long_leverage"])
        self.assertIsNone(eth["asset_mode"])

    def test_pending_orders_page_to_empty_and_keep_foreign_ids_private(self):
        def orders(request, data):
            if request.axis == "partially_filled" and request.cursor is None:
                return dict(entrustedList=[dict(orderId="999", status="partially_filled")], endId="999")
            if request.axis == "profit_loss" and request.cursor is None:
                return dict(entrustedList=[dict(orderId="888")], endId="888")
            return data
        self.startup(orders)
        with patch("investalo_credential_store.demo_account_sync.time.sleep"):
            report = self.run_read()
        self.assertEqual(report["blockers"], ["orders_present"])
        self.assertEqual(report["orders"][1], dict(category="partially_filled", count=1, pages=2, complete=True))
        self.assertEqual(report["orders"][4]["count"], 1)
        self.assertNotIn("999", json.dumps(report))
        self.assertNotIn("888", json.dumps(report))
        self.assertEqual([r.cursor for r in self.sent if r.axis == "partially_filled"], [None, "999"])

    def test_nonempty_page_without_cursor_remains_incomplete(self):
        self.startup(lambda r, d: dict(entrustedList=[dict(orderId="111", status="live")], endId="")
                     if r.axis == "live" else d)
        with patch("investalo_credential_store.demo_account_sync.time.sleep"):
            report = self.run_read()
        self.assertEqual(report["blockers"], ["order_pages_incomplete", "orders_present"])
        self.assertFalse(report["orders"][0]["complete"])
        self.assertEqual(report["orders"][0]["count"], 1)

    def test_regressed_cursor_and_duplicate_cross_axis_ids_discard_startup(self):
        def bad(request, data):
            if request.axis in ("live", "partially_filled"):
                return dict(entrustedList=[dict(orderId="99", status=request.axis)], endId="99")
            return data
        self.startup(bad)
        with patch("investalo_credential_store.demo_account_sync.time.sleep"), self.assertRaises(OnboardingRejected):
            self.run_read()
        counts = [len([r for r in self.sent if r.axis == axis]) for axis in ("live", "partially_filled")]
        self.assertIn(2, counts)
        self.assertTrue(all(n <= 2 for n in counts))

    def test_startup_revocation_and_native_failure_never_publish_partial_success(self):
        self.startup()
        original = self.native.transport
        def revoke(request):
            result = original(request)
            if request.axis == "BTCUSDT":
                self.revoked = True
            return result
        self.native.transport = revoke
        with patch("investalo_credential_store.demo_account_sync.time.sleep"), self.assertRaises(OnboardingRejected):
            self.run_read()
        self.assertIn("BTCUSDT", [r.axis for r in self.sent])
        self.assertTrue(all(r.axis in ("identity","wallet","positions",*CONFIGS) for r in self.sent))

    def test_changed_balance_is_compared_with_original_user_declared_start(self):
        self.startup()
        self.wallet[0]["available"] = "9999"
        with patch("investalo_credential_store.demo_account_sync.time.sleep"):
            report = self.run_read()
        self.assertIn("initial_balance_changed", report["blockers"])
        self.assertEqual(report["expected_initial_usdt"], "10000")

    def test_unknown_collateral_fields_are_reported_as_unknown_not_funded_margin(self):
        for field in ("coupon", "grant", "assetMode", "locked", "isolatedMargin",
                      "crossedMargin", "unrealizedPL"):
            with self.subTest(field=field):
                self.setUp()
                self.startup()
                del self.wallet[0][field]
                with patch("investalo_credential_store.demo_account_sync.time.sleep"):
                    report = self.run_read()
                self.assertEqual(report["blockers"], ["wallet_unknown"])
                self.assertFalse(report["execution_enabled"])

    def test_known_nonzero_collateral_or_union_mode_remain_visible(self):
        for field, value in (("coupon", "1"), ("grant", "1"), ("locked", "1"),
                ("isolatedMargin", "1"), ("crossedMargin", "1"), ("unrealizedPL", "-1"),
                ("assetMode", "union")):
            with self.subTest(field=field):
                self.setUp()
                self.startup()
                self.wallet[0][field] = value
                with patch("investalo_credential_store.demo_account_sync.time.sleep"):
                    report = self.run_read()
                self.assertEqual(report["blockers"], ["wallet_collateral"])

    def test_startup_cannot_carry_private_fields_or_execution_grant(self):
        self.startup()
        with patch("investalo_credential_store.demo_account_sync.time.sleep"):
            report = self.run_read()
        for change in (dict(execution_enabled=True), dict(costs_verified=True),
                       dict(envelope="private"), dict(pending_scope_verified=True)):
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_startup({**report, **change})

    def test_unknown_inspection_denied_before_secret_and_native_io(self):
        self.target["inspection"] = "trade"
        self.body = json.dumps(self.target).encode()
        with self.assertRaises(OnboardingRejected):
            self.run_read()
        self.assertEqual(self.sent, [])

    def test_late_native_startup_response_discards_whole_cohort_without_retry(self):
        self.startup()
        original = self.native.transport
        def stale(request):
            result = original(request)
            if request.axis == "BTCUSDT":
                raw = json.loads(result.body)
                raw["requestTime"] -= 6000
                return ReadResponse(200, json.dumps(raw).encode())
            return result
        self.native.transport = stale
        with patch("investalo_credential_store.demo_account_sync.time.sleep"), self.assertRaises(OnboardingRejected):
            self.run_read()
        self.assertIn("BTCUSDT", [r.axis for r in self.sent])
        self.assertTrue(all(r.axis in ("identity","wallet","positions",*CONFIGS) for r in self.sent))

    def test_page_cap_is_explicit_incomplete_and_no_eleventh_request(self):
        def many(request, data):
            if request.axis == "live":
                oid = "1000" if request.cursor is None else str(int(request.cursor) - 1)
                return dict(entrustedList=[dict(orderId=oid, status="live")], endId=oid)
            return data
        self.startup(many)
        with patch("investalo_credential_store.demo_account_sync.time.sleep"):
            report = self.run_read()
        self.assertEqual(report["orders"][0], dict(category="live", count=10, pages=10, complete=False))
        self.assertEqual(len([r for r in self.sent if r.axis == "live"]), 10)
        self.assertIn("order_pages_incomplete", report["blockers"])

    def test_startup_failure_diagnostic_never_contains_session_keys_or_native_body(self):
        reports = []
        self.native.diagnostic = reports.append
        self.startup(lambda r, d: {} if r.axis == "live" else d)
        with patch("investalo_credential_store.demo_account_sync.time.sleep"), self.assertRaises(OnboardingRejected):
            self.run_read()
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]["stage"], "live:parse")
        self.assertEqual(set(reports[0]), {"schema","stage","sent","elapsed_ms","error_type",
            "http_status","provider_code","pending_failure"})
        self.assertEqual(reports[0]["pending_failure"], dict(reason="invalid_pending_page",
            shape=dict(data="object", rows="missing", cursor="missing")))
        text = json.dumps(reports)
        for private in ("synthetic", "api", "passphrase", "session_binding", "broker_uid", "entrustedList"):
            self.assertNotIn(private, text)

    def test_pending_diagnostic_classifies_without_copying_ids_or_error_messages(self):
        from investalo_credential_store.demo_startup_check import pending_failure
        from investalo_bitget.futures_demo import DemoRejected
        for cursor, expected in ((None, "null"), ("", "empty_string"), ("0", "zero_string"),
                                 (0, "zero_integer"), ("private-id", "other")):
            response = ReadResponse(200, json.dumps(dict(code="00000", requestTime=int(time.time()*1000),
                data=dict(entrustedList=[], endId=cursor, private="private-data"))).encode())
            result = pending_failure(DemoRejected("invalid_order_id"), response)
            self.assertEqual(result, dict(reason="invalid_order_id",
                shape=dict(data="object", rows="array", row_count=0, cursor=expected)))
            result = pending_failure(ValueError("private-error"), response)
            self.assertEqual(result["reason"], "unclassified")
            self.assertNotIn("private", json.dumps(result))

    def test_native_demo_null_null_empty_page_is_terminal_in_each_family(self):
        self.startup(lambda r, d: dict(entrustedList=None, endId=None) if r.axis in AXES[2:] else d)
        with patch("investalo_credential_store.demo_account_sync.time.sleep"):
            report = self.run_read()
        self.assertEqual(report["blockers"], [])
        self.assertTrue(all(o["count"] == 0 and o["pages"] == 1 and o["complete"]
                            for o in report["orders"]))
        self.assertFalse(report["pending_scope_verified"])
        self.assertFalse(report["execution_enabled"])

    def test_null_rows_with_missing_real_or_unexpected_cursor_fields_still_reject(self):
        variants = ({}, dict(entrustedList=None), dict(endId=None),
            dict(entrustedList=None, endId="123"), dict(entrustedList=None, endId=""),
            dict(entrustedList=None, endId=None, otherOrders=[]))
        for variant in variants:
            with self.subTest(variant=variant):
                self.setUp()
                self.startup(lambda r, d: variant if r.axis == "live" else d)
                with patch("investalo_credential_store.demo_account_sync.time.sleep"), self.assertRaises(OnboardingRejected):
                    self.run_read()

    def test_null_null_terminal_page_retains_preceding_pending_orders(self):
        def pending(request, data):
            if request.axis == "live":
                return (dict(entrustedList=[dict(orderId="123", status="live")], endId="123")
                        if request.cursor is None else dict(entrustedList=None, endId=None))
            return data
        self.startup(pending)
        with patch("investalo_credential_store.demo_account_sync.time.sleep"):
            report = self.run_read()
        self.assertEqual(report["orders"][0], dict(category="live", count=1, pages=2, complete=True))
        self.assertIn("orders_present", report["blockers"])

    def test_empty_page_adapter_preserves_source_clock_and_old_page_contract(self):
        from investalo_credential_store.demo_startup_check import startup_pending_response
        from investalo_bitget.futures_demo_account import _pages, DemoPacket, DemoReadPlan
        from investalo_bitget import parse
        from investalo_bitget.futures_demo import DemoRejected
        now = int(time.time()*1000)
        response = ReadResponse(200, json.dumps(dict(code="00000", requestTime=now-1000,
            data=dict(entrustedList=None, endId=None))).encode())
        adapted = startup_pending_response(response)
        self.assertEqual(parse.envelope(response)[1], parse.envelope(adapted)[1])
        plan = DemoReadPlan(self.binding, "live")
        with self.assertRaises(DemoRejected):
            _pages([DemoPacket(plan, response)], "live", self.binding, self.owner, now)
        self.assertEqual(_pages([DemoPacket(plan, adapted)], "live", self.binding, self.owner, now), ([], True))
        with self.assertRaises(DemoRejected):
            _pages([DemoPacket(plan, adapted)], "live", self.binding, self.owner, now+5000)

    def test_native_latency_overlaps_with_three_workers_but_paces_every_get(self):
        self.startup()
        original = self.native.transport
        lock = threading.Lock()
        starts, active, maximum = [], 0, 0
        def delayed(request):
            nonlocal active, maximum
            with lock:
                starts.append(time.monotonic())
                active += 1; maximum = max(maximum, active)
            try:
                # Fifteen serial calls at this latency exceed the 5s cohort.
                time.sleep(.36)
                return original(request)
            finally:
                with lock: active -= 1
        self.native.transport = delayed
        started = time.monotonic()
        report = self.run_read()
        self.assertLess(time.monotonic()-started, 5)
        self.assertGreaterEqual(maximum, 2)
        self.assertLessEqual(maximum, 3)
        self.assertEqual(len(starts), 15)
        self.assertTrue(all(b-a >= .10 for a,b in zip(starts, starts[1:])))
        self.assertEqual(report["blockers"], [])

    def test_pending_family_uses_free_worker_while_final_config_is_in_flight(self):
        self.startup()
        original = self.native.transport
        final_config, pending_started = threading.Event(), threading.Event()
        def delayed(request):
            if request.axis == CONFIGS[-1]:
                final_config.set()
                self.assertTrue(pending_started.wait(1), "whole-config barrier delayed pending read")
            elif request.axis == "live":
                self.assertTrue(final_config.wait(1))
                pending_started.set()
            return original(request)
        self.native.transport = delayed
        with patch("investalo_credential_store.demo_account_sync.time.sleep"):
            report = self.run_read()
        self.assertTrue(pending_started.is_set())
        self.assertEqual(report["blockers"], [])
        self.assertEqual([c["symbol"] for c in report["configurations"]], list(CONFIGS))
        self.assertEqual([o["category"] for o in report["orders"]], list(AXES[2:]))

    def test_parallel_failure_waits_for_workers_and_never_returns_partial_report(self):
        self.startup()
        original = self.native.transport
        active, lock = 0, threading.Lock()
        def delayed(request):
            nonlocal active
            if request.axis in CONFIGS:
                with lock: active += 1
                try:
                    time.sleep(.02)
                    if request.axis == "BTCUSDT":
                        raise TimeoutError()
                    return original(request)
                finally:
                    with lock: active -= 1
            return original(request)
        self.native.transport = delayed
        with patch("investalo_credential_store.demo_account_sync.time.sleep"), self.assertRaises(OnboardingRejected):
            self.run_read()
        self.assertEqual(active, 0)
        self.assertFalse(self.native.lock.locked())
        self.assertFalse(any(r.axis in AXES[2:] for r in self.sent))

    def test_parallel_cross_family_duplicate_ids_reject_whole_report(self):
        def duplicate(request, data):
            if request.axis in ("live", "partially_filled") and request.cursor is None:
                return dict(entrustedList=[dict(orderId="99", status=request.axis)], endId="99")
            return data
        self.startup(duplicate)
        with patch("investalo_credential_store.demo_account_sync.time.sleep"), self.assertRaises(OnboardingRejected):
            self.run_read()

    def test_success_diagnostic_is_only_completed_timing_and_count(self):
        reports = []
        self.native.diagnostic = reports.append
        self.startup()
        with patch("investalo_credential_store.demo_account_sync.time.sleep"):
            self.run_read()
        self.assertEqual(len(reports), 1)
        self.assertEqual((reports[0]["stage"], reports[0]["sent"], reports[0]["error_type"]), ("completed",15,None))
