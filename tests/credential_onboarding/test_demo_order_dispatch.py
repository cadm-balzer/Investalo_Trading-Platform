"""Actual private registry/outbox + AEAD; authority and broker replies synthetic."""
from dataclasses import replace
from decimal import Decimal
import json
from pathlib import Path
import pickle
import tempfile
import threading
import unittest
from unittest.mock import patch
from uuid import UUID

from investalo_bitget import Credentials
from investalo_bitget.futures_demo import DemoRejected
from investalo_bitget.futures_demo_read import HTTPSDemoReadTransport
from investalo_bitget.futures_demo_registry import RegisteredDemoOutbox
from investalo_bitget.signing import hmac_sha256_base64
from investalo_credentials import KEKRing
from investalo_credential_store.demo_trading_provider import DemoTradingSecretSnapshot, SealedDemoTradingProvider
from investalo_credential_store.demo_trading_secret import DemoTradingSecretSpec, seal_demo_trading_secret
from investalo_credential_store.demo_order_dispatch import (
    DemoOrderApproval, DemoOrderDispatcher, SignedDemoOrderRequest, HTTPSDemoOrderTransport)
from test_futures_demo import AT, BINDING, OWNER, OTHER, intent, response, detail, positions


class DemoDispatchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.registry, self.directory = self.root / "registry", self.root / "outbox"
        self.registry.mkdir(mode=0o700); self.directory.mkdir(mode=0o700)
        self.box = RegisteredDemoOutbox.create(self.registry, self.directory,
            binding=BINDING, outbox_id=UUID(int=90), context=OWNER)
        self.order = intent()
        self.box.prepare(self.order, context=OWNER, expected_revision=0)
        self.spec = DemoTradingSecretSpec(binding=BINDING, parent_uid="0", egress_ip="192.0.2.8",
            authorities=("coow", "cpow", "stow"), provisioning_digest="d"*64, credential_revision=1)
        self.ring = KEKRing((("synthetic", b"K"*32),), active_version="synthetic")
        self.key = Credentials("synthetic-api", "synthetic-secret", "synthetic-pass")
        self.snapshot = DemoTradingSecretSnapshot(self.spec, seal_demo_trading_secret(
            self.key, self.spec, self.ring), storage_version=1)
        self.now, self.reads, self.revoked = AT + 100, 0, False
        self.sent, self.identities, self.grants = [], [], 0
        self.guard_error, self.approval_change = False, None
        self.mutex = threading.Lock()
        def read(binding, context):
            self.reads += 1
            if self.revoked: raise ValueError("synthetic revoked")
            return self.snapshot
        self.provider = SealedDemoTradingProvider(self.spec, expected_storage=1,
            read_snapshot=read, load_keyring=lambda: self.ring, expires_ms=AT+30000, milliseconds=lambda: self.now)

    def tearDown(self):
        self.box.close(); self.tmp.cleanup()

    def authorize(self, order, receipt, context):
        self.grants += 1
        return DemoOrderApproval(UUID(int=91), self.approval_change or order, receipt,
            credential_revision=1, storage_version=1, granted_ms=self.now, expires_ms=self.now+15000)

    def account_guard(self, *args):
        if self.guard_error: raise ValueError("synthetic foreign account order")

    def identity(self, request):
        self.identities.append(request)
        return response(dict(userId="123456", parentId=0, ips="", authorities=["coow","cpow","stow"]), at=self.now)

    def send(self, request):
        # Observe the actual on-disk prefix before mocked native send.
        raw = (self.directory / "commands.jsonl").read_text()
        self.assertIn('"kind":"dispatch"', raw)
        self.assertEqual(self.box.traces(context=OWNER)[0].state, "submission_unknown")
        self.sent.append(request)
        return response(dict(clientOid=self.order.client_oid, orderId="123"), at=self.now)

    def dispatcher(self, **changes):
        return DemoOrderDispatcher(self.box, self.provider, **{
            "read_transport": self.identity, "order_transport": self.send, "native_guard": lambda: None,
            "account_guard": self.account_guard, "shared_lock": self.mutex, "ip_binding": "unavailable_in_demo",
            "authorize_once": self.authorize, "enabled": True, "milliseconds": lambda: self.now, **changes})

    def dispatch(self, dispatcher=None):
        return (dispatcher or self.dispatcher()).dispatch(self.order.command_id,
            context=OWNER, expected_revision=self.box.receipt.revision)

    def test_actual_unknown_prefix_precedes_exact_signed_post_and_ack_is_not_fill(self):
        result = self.dispatch()
        self.assertEqual(result.outcome, "acknowledged")
        self.assertEqual(result.minimum_receipt.revision, 3)
        trace = self.box.traces(context=OWNER)[0]
        self.assertEqual(trace.state, "acknowledged")
        self.assertIsNone(trace.observation)
        request = self.sent[0]
        body = json.loads(request.body)
        self.assertEqual((request.method, request.target, body["force"], body["marginMode"]),
            ("POST", "/api/v2/mix/order/place-order", "ioc", "isolated"))
        self.assertEqual(body["clientOid"], self.order.client_oid)
        self.assertEqual(request.headers["paptrading"], "1")
        self.assertEqual(request.headers["ACCESS-SIGN"], hmac_sha256_base64(b"synthetic-secret",
            str(self.now).encode() + b"POST" + request.target.encode() + request.body))
        self.assertGreaterEqual(self.reads, 8)  # Real fresh AEAD before and after broker boundaries.
        with self.assertRaises(DemoRejected): self.dispatch()
        self.assertEqual((len(self.sent), self.grants), (1, 1))

    def test_disabled_or_missing_grant_stops_before_secret_and_io(self):
        for changes in (dict(enabled=False), dict(authorize_once=None)):
            with self.subTest(changes=changes), self.assertRaises(DemoRejected):
                self.dispatch(self.dispatcher(**changes))
        self.assertEqual((self.reads, self.grants, len(self.sent)), (0, 0, 0))

    def test_account_guard_and_foreign_scope_stop_before_authorization_or_decrypt(self):
        self.guard_error = True
        with self.assertRaises(ValueError): self.dispatch()
        with self.assertRaises(DemoRejected):
            self.dispatcher().dispatch(self.order.command_id, context=OTHER, expected_revision=1)
        self.assertEqual((self.grants, self.reads, len(self.sent)), (0, 0, 0))

    def test_exact_price_change_invalidates_approval_before_decrypt(self):
        self.approval_change = replace(self.order, limit_price=self.order.limit_price + 1)
        with self.assertRaises(DemoRejected): self.dispatch()
        self.assertEqual((self.reads, len(self.sent)), (0, 0))

    def test_foreign_or_stale_native_identity_stops_before_durable_attempt(self):
        for uid, at in (("999999", self.now), ("123456", self.now-5001)):
            d = self.dispatcher(read_transport=lambda r: response(
                dict(userId=uid, parentId=0, ips="", authorities=["coow","cpow","stow"]), at=at))
            with self.subTest(uid=uid, at=at), self.assertRaises(Exception): self.dispatch(d)
            self.assertEqual(self.box.receipt.revision, 1)
        self.assertEqual(len(self.sent), 0)

    def test_network_failure_survives_restore_and_never_resends(self):
        def fail(request):
            self.sent.append(request)
            raise TimeoutError("synthetic native ACK missing")
        result = self.dispatch(self.dispatcher(order_transport=fail))
        self.assertEqual(result.outcome, "outcome_unknown")
        self.box.close()
        self.box = RegisteredDemoOutbox.restore(self.registry, self.directory,
            binding=BINDING, outbox_id=UUID(int=90), context=OWNER, minimum_receipt=result.minimum_receipt)
        self.assertEqual(self.box.traces(context=OWNER)[0].state, "submission_unknown")
        with self.assertRaises(DemoRejected): self.dispatch()
        self.assertEqual((len(self.sent), self.grants), (1, 1))

    def test_actor_revocation_after_native_send_keeps_unknown_not_failed(self):
        def revoke(request):
            value = self.send(request)
            self.revoked = True
            return value
        result = self.dispatch(self.dispatcher(order_transport=revoke))
        self.assertEqual(result.outcome, "outcome_unknown")
        self.assertEqual(self.box.traces(context=OWNER)[0].state, "submission_unknown")
        with self.assertRaises(DemoRejected): self.dispatch()
        self.assertEqual(len(self.sent), 1)

    def test_unknown_begin_commit_sends_nothing_and_restores_existing_prefix(self):
        prior = self.box.receipt
        publish = self.box._box._publish
        def lost_ack(receipt):
            publish(receipt)
            raise OSError("synthetic lost local publish ACK")
        with patch.object(self.box._box, "_publish", lost_ack), self.assertRaises(DemoRejected):
            self.dispatch()
        self.assertEqual(len(self.sent), 0)
        self.box.close()
        self.box = RegisteredDemoOutbox.restore(self.registry, self.directory,
            binding=BINDING, outbox_id=UUID(int=90), context=OWNER, minimum_receipt=prior)
        self.assertEqual(self.box.traces(context=OWNER)[0].state, "submission_unknown")
        with self.assertRaises(DemoRejected): self.dispatch()

    def test_busy_shared_uid_does_not_consume_approval(self):
        self.mutex.acquire()
        try:
            with self.assertRaises(DemoRejected): self.dispatch()
        finally: self.mutex.release()
        self.assertEqual(self.grants, 0)

    def test_private_packets_and_grants_redact_and_deny_serialization(self):
        lease = self.provider(BINDING, OWNER)
        packet = SignedDemoOrderRequest(lease, self.order, "place", timestamp_ms=self.now)
        for value in (packet, self.authorize(self.order, self.box.receipt, OWNER)):
            self.assertNotIn("synthetic", repr(value))
            with self.assertRaises(TypeError): pickle.dumps(value)
        with self.assertRaises(AttributeError): packet.body = b"changed"
        with self.assertRaises(DemoRejected): HTTPSDemoReadTransport()(packet)
        packet.consume()
        with self.assertRaises(DemoRejected): packet.consume()

    def test_post_transport_has_exact_tls_no_proxy_no_redirect_and_no_retry(self):
        lease = self.provider(BINDING, OWNER)
        packet = SignedDemoOrderRequest(lease, self.order, "place", timestamp_ms=self.now)
        class Reply:
            status = 200
            def read(self, maximum): return b'{"code":"00000","data":{}}'
            def __enter__(self): return self
            def __exit__(self, *args): pass
        class Opener:
            def open(_self, request, timeout):
                self.assertEqual(request.method, "POST"); self.assertEqual(request.data, packet.body)
                self.assertEqual(timeout, 3); return Reply()
        with patch("investalo_credential_store.demo_order_dispatch.build_opener", return_value=Opener()) as opener:
            self.assertEqual(HTTPSDemoOrderTransport()(packet).status, 200)
            handlers = opener.call_args.args
            self.assertEqual(handlers[0].proxies, {})
            self.assertTrue(handlers[1]._context.check_hostname)
            self.assertEqual(type(handlers[2]).__name__, "_NoRedirect")
            with self.assertRaises(DemoRejected): HTTPSDemoOrderTransport()(packet)
            self.assertEqual(opener.call_count, 1)

    def test_unknown_attempt_recovers_only_with_get_and_retains_partial_fill_unknown_fee(self):
        def timeout(request):
            self.sent.append(request); raise TimeoutError()
        self.dispatch(self.dispatcher(order_transport=timeout))
        queried = []
        def read(request):
            if request.axis == "identity": return self.identity(request)
            self.assertEqual(request.axis, "positions")
            return response(positions(), at=self.now)
        def get_detail(request):
            queried.append(request)
            self.assertEqual(request.method, "GET"); self.assertEqual(request.body, b"")
            self.assertIn("clientOid="+self.order.client_oid, request.target)
            return response(detail(self.order, state="canceled", cTime=str(self.now), uTime=str(self.now)), at=self.now)
        d = self.dispatcher(read_transport=read, order_transport=get_detail)
        result = d.observe(self.order.command_id, context=OWNER, expected_revision=2)
        self.assertTrue(result.position_matched)
        self.assertFalse(result.costs_verified)
        trace = self.box.traces(context=OWNER)[0]
        self.assertEqual((trace.state, trace.observation.quantity), ("canceled", Decimal("0.004")))
        self.assertIsNone(trace.observation.reported_fee)
        self.assertEqual((len(self.sent), len(queried), self.grants), (1, 1, 1))
        with self.assertRaises(DemoRejected): self.dispatch()

    def test_position_mismatch_retains_confirmed_order_detail_and_does_not_book_pnl(self):
        self.dispatch()
        d = self.dispatcher(order_transport=lambda r: response(
            detail(self.order, cTime=str(self.now), uTime=str(self.now)), at=self.now),
            read_transport=lambda r: self.identity(r) if r.axis == "identity" else response(positions("0.03"), at=self.now))
        result = d.observe(self.order.command_id, context=OWNER, expected_revision=3)
        self.assertFalse(result.position_matched)
        self.assertEqual(self.box.traces(context=OWNER)[0].observation.quantity, Decimal("0.004"))
        self.assertEqual(len(self.sent), 1)
