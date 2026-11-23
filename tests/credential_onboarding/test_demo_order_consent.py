"""Own signed order domain + actual consumer/outbox/AEAD; synthetic browser consent."""
import base64
from dataclasses import replace
from decimal import Decimal
import hashlib
import hmac
import json
import pickle
import unittest
from unittest.mock import patch
from uuid import UUID

from investalo_bitget.futures_demo import DemoRejected
from investalo_bitget.futures_demo_registry import RegisteredDemoOutbox
from investalo_credential_store.demo_order_consent import (
    AUDIENCE, BODY, CONFIRMATION, CONTEXT, KIND, PATH,
    DemoBTCTestConsentIssuer, DemoBTCTestConsentVerifier)
from investalo_credential_store.demo_order_consumer import DurableDemoOrderConsumer
from investalo_credential_store.passkey_request_assertion import PasskeyRequestContext
from investalo_credential_store.demo_trading_provider import DemoTradingSecretSnapshot
from investalo_credential_store.demo_trading_secret import DemoTradingSecretSpec, seal_demo_trading_secret
import investalo_credential_store.demo_trading_provider as crypto
import test_demo_order_dispatch as fixture
from test_futures_demo import OWNER, OTHER

KEY = b"S"*32


class OrderConsentTests(unittest.TestCase):
    def setUp(self):
        c = self.case = fixture.DemoDispatchTests()
        c.setUp()
        c.box.close()
        self.registry, self.box_root = c.root / "test-registry", c.root / "test-outbox"
        self.registry.mkdir(mode=0o700); self.box_root.mkdir(mode=0o700)
        c.box = RegisteredDemoOutbox.create(self.registry, self.box_root,
            binding=c.spec.binding, outbox_id=UUID(int=92), context=OWNER)
        c.registry, c.directory = self.registry, self.box_root
        c.order = replace(c.order, quantity=Decimal("0.001"), before_quantity=Decimal(0))
        c.box.prepare(c.order, context=OWNER, expected_revision=0)
        self.root = c.root / "consents"
        self.root.mkdir(mode=0o700)
        at = c.now//1000
        self.context = PasskeyRequestContext(tenant_id=OWNER.tenant_id, user_id=OWNER.user_id,
            subject="synthetic-order-owner", auth_epoch=3, oidc_auth_time=at-30,
            session_binding="a"*64, session_expires_at=at+3600)
        self.verifier = DemoBTCTestConsentVerifier(key=KEY,
            oidc_issuer="https://auth.cockpit.investalo.de", origin="https://cockpit.investalo.de")
        self.request = dict(platform_account_id=str(c.order.binding.account_id),
            connection_id=str(c.order.binding.credential_ref), credential_revision=1,
            storage_version=1, command_id=str(c.order.command_id), intent_sha256=c.order.intent_digest,
            outbox_receipt=c.box.receipt.record(), confirmation=CONFIRMATION)
        self.body = json.dumps(self.request, separators=(",", ":")).encode()
        self.store = None

    def tearDown(self):
        if self.store: self.store.close()
        self.case.tearDown()

    def token(self, *, header=None, key=KEY, **changes):
        claims = {name: str(getattr(self.context, name)) if type(getattr(self.context, name)) is UUID
            else getattr(self.context, name) for name in CONTEXT}
        claims.update(kind=KIND, aud=AUDIENCE, oidc_issuer=self.verifier.oidc_issuer,
            origin=self.verifier.origin, iat=self.case.now//1000, exp=self.case.now//1000+15,
            jti=str(UUID(int=500)), htm="POST", htu=PATH, body_sha256=hashlib.sha256(self.body).hexdigest())
        claims.update(changes)
        encode = lambda value: base64.urlsafe_b64encode(value).rstrip(b"=").decode()
        a = encode(json.dumps(header or dict(alg="HS256", typ="JWT")).encode())
        b = encode(json.dumps(claims).encode())
        return a+"."+b+"."+encode(hmac.digest(key, (a+"."+b).encode("ascii"), "sha256"))

    def issuer(self, **changes):
        return DemoBTCTestConsentIssuer(self.verifier, self.context,
            changes.pop("token", self.token()), changes.pop("body", self.body), **{
                "read_snapshot": self.case.provider._read, "guard": lambda: None,
                "milliseconds": lambda: self.case.now, **changes})

    def issue(self, issuer=None, order=None, receipt=None, owner=OWNER):
        return (issuer or self.issuer())(order or self.case.order, receipt or self.case.box.receipt, owner)

    def test_signed_exact_btc_consent_consumed_before_real_aead_and_post(self):
        c = self.case
        self.store = DurableDemoOrderConsumer(self.root, issuer=self.issuer(),
            guard=lambda: None, milliseconds=lambda: c.now)
        original = crypto.open_demo_trading_secret
        def checked(*args, **kwargs):
            self.assertEqual(len(list(self.root.iterdir())), 1)
            return original(*args, **kwargs)
        with patch.object(crypto, "open_demo_trading_secret", side_effect=checked):
            result = c.dispatch(c.dispatcher(authorize_once=self.store))
        self.assertEqual(result.outcome, "acknowledged")
        self.assertEqual(len(c.sent), 1)
        self.assertEqual(json.loads(c.sent[0].body)["size"], "0.001")
        self.assertEqual(set(self.request), BODY)
        self.assertEqual(c.box.traces(context=OWNER)[0].state, "acknowledged")

    def test_read_and_key_write_domains_deny_before_snapshot(self):
        for changes in (dict(kind="investalo-demo-account-read/1", aud="investalo-demo-account-read",
                            htu="/v1/bitget-demo-trading/account-read"),
                dict(kind="passkey-demo-trading-credential-write/1", aud="investalo-demo-trading"),
                dict(kind="passkey-demo-credential-write/1"),
                dict(aud="investalo-demo-account-read")):
            with self.subTest(changes=changes), self.assertRaises(DemoRejected):
                self.issue(self.issuer(token=self.token(**changes)))
        self.assertEqual(self.case.reads, 0)

    def test_old_account_read_rejects_fresh_order_token_before_native_io(self):
        from test_demo_account_sync import DemoAccountTests
        from investalo_credential_store.request_assertion import OnboardingRejected
        read = DemoAccountTests(); read.setUp()
        try:
            claims = {name: str(getattr(read.context, name)) if type(getattr(read.context, name)) is UUID
                else getattr(read.context, name) for name in CONTEXT}
            claims.update(kind=KIND, aud=AUDIENCE, oidc_issuer=read.config["oidc_issuer"],
                origin=read.config["origin"], iat=read.now, exp=read.now+15,
                jti=str(UUID(int=500)), htm="POST", htu=PATH,
                body_sha256=hashlib.sha256(read.body).hexdigest())
            encode = lambda value: base64.urlsafe_b64encode(value).rstrip(b"=").decode()
            a = encode(b'{"alg":"HS256","typ":"JWT"}'); b = encode(json.dumps(claims).encode())
            token = a+"."+b+"."+encode(hmac.digest(KEY, (a+"."+b).encode("ascii"), "sha256"))
            with self.assertRaises(OnboardingRejected):
                read.reader(read.context, token, read.body)
            self.assertEqual(read.sent, [])
        finally:
            read.tearDown()

    def test_original_actor_session_epoch_and_clock_cannot_be_changed(self):
        at = self.case.now//1000
        for changes in (dict(tenant_id=str(UUID(int=9))), dict(user_id=str(OTHER.user_id)),
                dict(subject="foreign"), dict(auth_epoch=4), dict(auth_epoch=True),
                dict(oidc_auth_time=at), dict(session_binding="b"*64), dict(session_expires_at=at+60),
                dict(exp=at), dict(exp=at+16), dict(iat=at+1), dict(exp=True),
                dict(jti=str(UUID(int=500)).upper() + "x")):
            with self.subTest(changes=changes), self.assertRaises(DemoRejected):
                self.issue(self.issuer(token=self.token(**changes)))
        self.assertEqual(self.case.reads, 0)

    def test_foreign_origin_method_path_key_and_header_deny(self):
        for changes in (dict(origin="https://foreign.invalid"), dict(oidc_issuer="https://foreign.invalid"),
                dict(htm="GET"), dict(htu="/v1/bitget-demo-trading/credential-write"),
                dict(key=b"F"*32), dict(header=dict(alg="none", typ="JWT"))):
            with self.subTest(changes=changes), self.assertRaises(DemoRejected):
                self.issue(self.issuer(token=self.token(**changes)))
        self.assertEqual(self.case.reads, 0)

    def test_body_digest_exact_fields_receipt_types_and_confirmation_deny(self):
        for changes in (dict(confirmation="yes"), dict(private_key="synthetic"),
                dict(command_id=str(UUID(int=9))), dict(intent_sha256="0"*64),
                dict(connection_id=str(UUID(int=9))), dict(platform_account_id=str(UUID(int=9))),
                dict(credential_revision=True), dict(storage_version=True),
                dict(outbox_receipt={**self.request["outbox_receipt"], "revision": True})):
            body = json.dumps({**self.request, **changes}).encode()
            token = self.token(body_sha256=hashlib.sha256(body).hexdigest())
            with self.subTest(changes=changes), self.assertRaises(DemoRejected):
                self.issue(self.issuer(token=token, body=body))
        with self.assertRaises(DemoRejected):
            self.issue(self.issuer(body=self.body+b" "))
        self.assertEqual(self.case.reads, 0)

    def test_changed_price_position_action_budget_or_asset_deny(self):
        c = self.case
        for order in (replace(c.order, limit_price=c.order.limit_price+Decimal("0.1")),
                replace(c.order, quantity=Decimal("0.002")),
                replace(c.order, before_quantity=Decimal("0.001")),
                replace(c.order, action="reduce_long", before_quantity=Decimal("0.001")),
                replace(c.order, grid=replace(c.order.grid, symbol="ETHUSDT"))):
            with self.subTest(order=repr(order)), self.assertRaises(DemoRejected):
                self.issue(order=order)
        self.assertEqual(c.reads, 0)

    def test_role_revocation_foreign_owner_or_fork_stops_before_store(self):
        with self.assertRaises(DemoRejected):
            self.issue(owner=OTHER)
        def denied(): raise ValueError("synthetic actor revoked")
        with self.assertRaises(ValueError):
            self.issue(self.issuer(guard=denied))
        issuer = self.issuer()
        with patch("investalo_credential_store.demo_order_consent.os.getpid", return_value=-1), self.assertRaises(DemoRejected):
            self.issue(issuer)
        self.assertEqual(self.case.reads, 0)

    def test_current_credential_storage_and_ciphertext_drift_deny(self):
        c = self.case
        foreign = DemoTradingSecretSpec(binding=replace(c.spec.binding, credential_ref=UUID(int=9)),
            parent_uid=c.spec.parent_uid, egress_ip=c.spec.egress_ip, authorities=c.spec.authorities,
            provisioning_digest=c.spec.provisioning_digest, credential_revision=1)
        advanced = DemoTradingSecretSnapshot(c.spec, c.snapshot.envelope, storage_version=2)
        for snapshot in (None, advanced,
                DemoTradingSecretSnapshot(foreign, c.snapshot.envelope, storage_version=1)):
            with self.subTest(snapshot=repr(snapshot)), self.assertRaises(DemoRejected):
                self.issue(self.issuer(read_snapshot=lambda *args: snapshot))
        counter = []
        def drift(*args):
            counter.append(True)
            return c.snapshot if len(counter) == 1 else DemoTradingSecretSnapshot(c.spec,
                seal_demo_trading_secret(c.key, c.spec, c.ring), storage_version=1)
        with self.assertRaises(DemoRejected):
            self.issue(self.issuer(read_snapshot=drift))

    def test_expiry_during_independent_snapshot_read_denies(self):
        def read(*args):
            self.case.now += 15000
            return self.case.snapshot
        with self.assertRaises(DemoRejected):
            self.issue(self.issuer(read_snapshot=read))
        self.assertEqual(list(self.root.iterdir()), [])

    def test_same_consent_jti_cannot_be_consumed_after_new_issuer(self):
        self.store = DurableDemoOrderConsumer(self.root, issuer=self.issuer(),
            guard=lambda: None, milliseconds=lambda: self.case.now)
        self.store(self.case.order, self.case.box.receipt, OWNER)
        self.store.close()
        self.store = DurableDemoOrderConsumer(self.root, issuer=self.issuer(),
            guard=lambda: None, milliseconds=lambda: self.case.now)
        with self.assertRaises(DemoRejected):
            self.store(self.case.order, self.case.box.receipt, OWNER)
        self.assertEqual(self.case.sent, [])

    def test_failed_issuer_is_not_reusable_and_private_objects_do_not_serialize(self):
        issuer = self.issuer(token="invalid")
        for _ in range(2):
            with self.assertRaises(DemoRejected):
                self.issue(issuer)
        for value in (issuer, self.verifier):
            self.assertNotIn("synthetic", repr(value))
            with self.assertRaises(TypeError):
                pickle.dumps(value)
