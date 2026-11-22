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
        self.assertEqual([r.axis for r in self.sent], ["identity", "wallet", "positions", *CONFIGS, *AXES[2:]])
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
        self.assertEqual(len([r for r in self.sent if r.axis == "live"]), 2)

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
        self.assertEqual(self.sent[-1].axis, "BTCUSDT")

    def test_changed_balance_is_compared_with_original_user_declared_start(self):
        self.startup()
        self.wallet[0]["available"] = "9999"
        with patch("investalo_credential_store.demo_account_sync.time.sleep"):
            report = self.run_read()
        self.assertIn("initial_balance_changed", report["blockers"])
        self.assertEqual(report["expected_initial_usdt"], "10000")

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
        self.assertEqual(self.sent[-1].axis, "BTCUSDT")

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
