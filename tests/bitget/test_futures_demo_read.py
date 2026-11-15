"""Synthetic replies and mocked HTTPS only; actual registered private outbox."""
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import pickle
import ssl
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import HTTPSHandler, ProxyHandler
from uuid import UUID

from investalo_bitget import BitgetRejected, HTTPSReadTransport
from investalo_bitget.futures_demo import DemoRejected
from investalo_bitget.futures_demo_account import AXES, CONFIGS
from investalo_bitget.futures_demo_read import (
    DemoReadClient, DemoReadCredential, HTTPSDemoReadTransport, SignedDemoReadRequest,
)
from investalo_bitget.futures_demo_registry import RegisteredDemoOutbox
from investalo_bitget.signing import Credentials, INFO_PATH, SignedReadRequest, hmac_sha256_base64
from investalo_bitget.transport import MAX_RESPONSE_BYTES, _NoRedirect
from test_futures_demo import AT, BINDING, OWNER, OTHER, intent, response
from test_futures_demo_account import cohort, expectation, pending

IP = "192.0.2.10"
SECRETS = Credentials("synthetic-demo-key", "synthetic-demo-secret", "synthetic-demo-pass")


def credential(**changes):
    return DemoReadCredential(**{"binding": BINDING, "credentials": SECRETS,
        "expected_parent": "0", "expected_egress_ip": IP, "provisioning_digest": "a" * 64,
        "revision": 1, "expires_ms": AT + 30_000, **changes})


def identity(**changes):
    return {"userId": BINDING.broker_uid, "parentId": 0, "authorities": ["coor", "cpor"],
            "ips": IP, **changes}


class DemoReadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.registry, self.directory = root / "registry", root / "original"
        for path in (self.registry, self.directory):
            path.mkdir(mode=0o700)
        self.box = RegisteredDemoOutbox.create(self.registry, self.directory,
            binding=BINDING, outbox_id=UUID(int=123), context=OWNER)
        self.now = AT + 100
        self.key = credential()
        self.info = identity()
        self.requests = []
        self.replies = {p.plan.axis: p.response for p in cohort()}
        self.client = DemoReadClient(provider=lambda binding, context: self.key,
                                     transport=self.transport, milliseconds=lambda: self.now)

    def tearDown(self):
        self.box.close()
        self.tmp.cleanup()

    def transport(self, request):
        request.validate()
        self.requests.append(request)
        return response(self.info) if request.axis == "identity" else self.replies[request.axis]

    def capture(self, client=None, **changes):
        return (client or self.client).capture(self.box, expectation(), **{
            "context": OWNER, "expected_revision": 0, **changes})

    def test_fifteen_fixed_demo_gets_bound_to_actual_receipt_without_mutation(self):
        before = self.box.receipt
        journal = (self.directory / "commands.jsonl").read_bytes()
        result = self.capture()
        self.assertEqual([r.axis for r in self.requests], ["identity", *AXES, *CONFIGS])
        self.assertTrue(result.account.matched)
        self.assertFalse(result.account.execution_ready)
        self.assertFalse(result.native_acceptance_verified)
        self.assertEqual(result.account.receipt, before)
        self.assertEqual(self.box.receipt, before)
        self.assertEqual(result.identity_response_sha256, hashlib.sha256(response(self.info).body).hexdigest())
        self.assertEqual(result.credential_revision, 1)
        self.assertEqual((self.directory / "commands.jsonl").read_bytes(), journal)
        for request in self.requests:
            self.assertEqual(request.method, "GET")
            self.assertEqual(request.body, b"")
            self.assertEqual(request.headers["paptrading"], "1")
            self.assertTrue(request.url.startswith("https://api.bitget.com/api/v2/"))

    def test_exact_signature_bytes_with_native_cursor_query(self):
        request = SignedDemoReadRequest(credential(), timestamp_ms=AT + 100, axis="live", cursor="123")
        expected = "/api/v2/mix/order/orders-pending?productType=USDT-FUTURES&status=live&limit=100&idLessThan=123"
        self.assertEqual(request.target, expected)
        self.assertEqual(request.headers["ACCESS-SIGN"],
            hmac_sha256_base64(b"synthetic-demo-secret", (str(AT + 100) + "GET" + expected).encode("ascii")))

    def test_signed_objects_redact_immutable_and_deny_serialization(self):
        request = SignedDemoReadRequest(credential(), timestamp_ms=AT)
        for value in (request, request.headers, credential(), SECRETS, self.client):
            for secret in ("synthetic-demo-key", "synthetic-demo-pass", "synthetic-demo-secret", BINDING.broker_uid):
                self.assertNotIn(secret, repr(value))
        for value in (request, request.headers, credential()):
            with self.assertRaises(TypeError):
                pickle.dumps(value)
        with self.assertRaises(AttributeError):
            request.url = "https://example.invalid"

    def test_old_three_path_transport_cannot_accept_demo_requests(self):
        request = SignedDemoReadRequest(credential(), timestamp_ms=AT)
        with self.assertRaises(BitgetRejected):
            HTTPSReadTransport()(request)
        old = SignedReadRequest(SECRETS, INFO_PATH, (), AT)
        with self.assertRaisesRegex(DemoRejected, "invalid_demo_read_request"):
            HTTPSDemoReadTransport()(old)

    def test_arbitrary_spot_order_funding_paths_and_cursors_reject_before_network(self):
        for axis in ("https://example.invalid", "/api/v2/mix/order/place-order", "spot", "funding"):
            with self.subTest(axis=axis), self.assertRaises(DemoRejected):
                SignedDemoReadRequest(credential(), timestamp_ms=AT, axis=axis)
        for axis in ("identity", "wallet", "positions", "BTCUSDT"):
            with self.subTest(axis=axis), self.assertRaises(DemoRejected):
                SignedDemoReadRequest(credential(), timestamp_ms=AT, axis=axis, cursor="123")

    def test_stale_owner_revision_and_foreign_registered_binding_send_nothing(self):
        for changes in ({"context": OTHER}, {"expected_revision": 1}, {"expected_revision": True}):
            with self.subTest(changes=changes), self.assertRaises(DemoRejected):
                self.capture(**changes)
        foreign = expectation(binding=replace(BINDING, credential_ref=UUID(int=99)))
        with self.assertRaisesRegex(DemoRejected, "registered_read_binding_mismatch"):
            self.client.capture(self.box, foreign, context=OWNER, expected_revision=0)
        self.assertEqual(self.requests, [])

    def test_invalid_missing_expired_or_foreign_provisioning_sends_nothing(self):
        for key in (None, credential(expires_ms=AT + 100), credential(expires_ms=AT + 61_000),
                    credential(binding=replace(BINDING, account_id=UUID(int=99)))):
            self.key = key
            client = DemoReadClient(provider=lambda *args: self.key, transport=self.transport,
                                    milliseconds=lambda: self.now)
            with self.subTest(key=key), self.assertRaises(DemoRejected):
                self.capture(client)
        self.assertEqual(self.requests, [])

    def test_credential_declaration_requires_known_parent_ip_receipt_and_revision(self):
        for changes in ({"expected_parent": None}, {"expected_egress_ip": None},
                        {"expected_egress_ip": "192.0.2.010"}, {"provisioning_digest": ""},
                        {"revision": True}, {"revision": 0}, {"expires_ms": True}):
            with self.subTest(changes=changes), self.assertRaises((DemoRejected, BitgetRejected)):
                credential(**changes)

    def test_wrong_uid_parent_ip_or_rights_stop_after_identity(self):
        for info in (identity(userId="987"), identity(parentId=1), identity(parentId=None),
                     identity(ips=None), identity(ips=""), identity(ips="192.0.2.11"),
                     identity(ips=IP + ",192.0.2.11"), identity(authorities=["coor"]),
                     identity(authorities=["coor", "cpor", "unknown_trade_right"]),
                     {"uid": BINDING.broker_uid, "permissions": ["read"]}):
            self.info, self.requests = info, []
            client = DemoReadClient(provider=lambda *args: self.key, transport=self.transport,
                                    milliseconds=lambda: self.now)
            with self.subTest(info=info), self.assertRaises((DemoRejected, BitgetRejected)):
                self.capture(client)
            self.assertEqual([r.axis for r in self.requests], ["identity"])

    def test_replaced_key_or_revision_during_capture_stops_before_next_request(self):
        original = self.transport
        for changed in (credential(revision=2), credential(provisioning_digest="b" * 64),
                        credential(expected_parent="1"),
                        credential(credentials=Credentials("new-key", "new-secret", "new-pass"))):
            self.requests, self.key = [], credential()

            def transport(request):
                reply = original(request)
                self.key = changed
                return reply
            client = DemoReadClient(provider=lambda *args: self.key, transport=transport,
                                    milliseconds=lambda: self.now)
            with self.subTest(changed=changed), self.assertRaisesRegex(DemoRejected, "credential_changed"):
                self.capture(client)
            self.assertEqual(len(self.requests), 1)

    def test_outbox_change_during_capture_discards_report_without_retry(self):
        def transport(request):
            reply = self.transport(request)
            self.box.prepare(intent(), context=OWNER, expected_revision=0)
            return reply
        client = DemoReadClient(provider=lambda *args: self.key, transport=transport,
                                milliseconds=lambda: self.now)
        with self.assertRaisesRegex(DemoRejected, "revision_conflict"):
            self.capture(client)
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(self.box.receipt.revision, 1)
        self.assertTrue(self.box.traces(context=OWNER)[0].can_submit)

    def test_registry_change_during_capture_stops_before_another_get(self):
        def transport(request):
            reply = self.transport(request)
            (self.registry / ("account-" + "a" * 64 + ".json")).touch(mode=0o600)
            return reply
        client = DemoReadClient(provider=lambda *args: self.key, transport=transport,
                                milliseconds=lambda: self.now)
        with self.assertRaises(DemoRejected):
            self.capture(client)
        self.assertEqual(len(self.requests), 1)

    def test_expired_cohort_and_backward_clock_discard_without_retry(self):
        for next_time in (AT + 5101, AT + 99):
            self.now, self.requests = AT + 100, []

            def transport(request):
                reply = self.transport(request)
                self.now = next_time
                return reply
            client = DemoReadClient(provider=lambda *args: self.key, transport=transport,
                                    milliseconds=lambda: self.now)
            with self.subTest(next_time=next_time), self.assertRaisesRegex(DemoRejected, "cohort_expired"):
                self.capture(client)
            self.assertEqual(len(self.requests), 1)

    def test_stale_future_identity_or_packet_never_returns_report(self):
        for at in (AT - 5000, AT + 101):
            def transport(request):
                self.requests.append(request)
                return response(identity(), at=at)
            client = DemoReadClient(provider=lambda *args: self.key, transport=transport,
                                    milliseconds=lambda: self.now)
            with self.subTest(at=at), self.assertRaisesRegex(DemoRejected, "stale_demo_read_response"):
                self.capture(client)

    def test_native_cursor_pages_are_signed_and_other_axes_stay_present(self):
        original = self.transport

        def transport(request):
            if request.axis != "live":
                return original(request)
            self.requests.append(request)
            if request.cursor is None:
                return response({"entrustedList": [pending()], "endId": "123"})
            self.assertEqual(request.cursor, "123")
            return response({"entrustedList": [], "endId": ""})
        client = DemoReadClient(provider=lambda *args: self.key, transport=transport,
                                milliseconds=lambda: self.now)
        result = self.capture(client)
        self.assertEqual(len(self.requests), 16)
        self.assertIn("foreign_orders_present", result.account.blockers)
        self.assertEqual(result.account.foreign_pending, ("123",))

    def test_incomplete_nonempty_page_is_reported_not_assumed_empty(self):
        self.replies["live"] = response({"entrustedList": [pending()], "endId": ""})
        result = self.capture()
        self.assertIn("pending_coverage_incomplete", result.account.blockers)
        self.assertEqual(len(self.requests), 15)

    def test_bad_or_repeating_cursor_fails_before_more_network_calls(self):
        original = self.transport

        def transport(request):
            if request.axis != "live":
                return original(request)
            self.requests.append(request)
            return response({"entrustedList": [pending()], "endId": "123"})
        client = DemoReadClient(provider=lambda *args: self.key, transport=transport,
                                milliseconds=lambda: self.now)
        with self.assertRaisesRegex(DemoRejected, "duplicate_or_regressed"):
            self.capture(client)
        self.assertEqual(len([r for r in self.requests if r.axis == "live"]), 2)

    def test_local_identity_pacing_has_no_sleep_or_automatic_retry(self):
        self.capture()
        count = len(self.requests)
        with self.assertRaisesRegex(DemoRejected, "rate_limited"):
            self.capture()
        self.assertEqual(len(self.requests), count)
        self.now += 1000
        self.assertTrue(self.capture().account.matched)

    def test_provider_and_transport_exception_text_is_suppressed(self):
        def fail(*args):
            raise RuntimeError("synthetic-demo-secret")
        for provider, transport in ((fail, self.transport), (lambda *args: self.key, fail)):
            client = DemoReadClient(provider=provider, transport=transport, milliseconds=lambda: self.now)
            with self.subTest(provider=provider), self.assertRaises(DemoRejected) as raised:
                self.capture(client)
            self.assertNotIn("synthetic-demo-secret", str(raised.exception))
            self.assertTrue(raised.exception.__suppress_context__)

    def test_provider_delay_exhausts_deadline_before_sending_identity(self):
        calls = 0

        def provider(*args):
            nonlocal calls
            calls += 1
            if calls == 2:
                self.now = AT + 5101
            return self.key
        client = DemoReadClient(provider=provider, transport=self.transport,
                                milliseconds=lambda: self.now)
        with self.assertRaisesRegex(DemoRejected, "cohort_expired"):
            self.capture(client)
        self.assertEqual(self.requests, [])

    def test_https_ca_hostname_proxy_redirect_and_timeout_without_network(self):
        class Reply:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, count): return response(identity()).body

        class Opener:
            def open(inner, request, timeout):
                self.assertEqual(request.get_method(), "GET")
                self.assertEqual(request.get_header("Paptrading"), "1")
                self.assertEqual(timeout, 5)
                return Reply()
        with patch("investalo_bitget.futures_demo_read.build_opener", return_value=Opener()) as builder:
            HTTPSDemoReadTransport()(SignedDemoReadRequest(credential(), timestamp_ms=AT))
        handlers = builder.call_args.args
        self.assertEqual(next(h for h in handlers if isinstance(h, ProxyHandler)).proxies, {})
        context = next(h for h in handlers if isinstance(h, HTTPSHandler))._context
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertGreaterEqual(context.minimum_version, ssl.TLSVersion.TLSv1_2)
        redirect = next(h for h in handlers if isinstance(h, _NoRedirect))
        with self.assertRaises(BitgetRejected):
            redirect.redirect_request(None, None, 302, "secret", {}, "https://example.invalid")
        for timeout in (True, 0, 6, float("nan")):
            with self.subTest(timeout=timeout), self.assertRaises(DemoRejected):
                HTTPSDemoReadTransport(timeout)

    def test_https_errors_and_oversized_reply_are_static_without_retry(self):
        request = SignedDemoReadRequest(credential(), timestamp_ms=AT)
        for failure in (HTTPError("secret-url", 429, "secret-message", {}, None), OSError("secret-key")):
            opener = unittest.mock.Mock()
            opener.open.side_effect = failure
            with patch("investalo_bitget.futures_demo_read.build_opener", return_value=opener):
                with self.assertRaises(DemoRejected) as raised:
                    HTTPSDemoReadTransport()(request)
            self.assertNotIn("secret", str(raised.exception))
            self.assertEqual(opener.open.call_count, 1)
        reply = unittest.mock.MagicMock()
        reply.__enter__.return_value = reply
        reply.read.return_value = b"x" * (MAX_RESPONSE_BYTES + 1)
        opener = unittest.mock.Mock()
        opener.open.return_value = reply
        with patch("investalo_bitget.futures_demo_read.build_opener", return_value=opener):
            with self.assertRaisesRegex(DemoRejected, "too_large"):
                HTTPSDemoReadTransport()(request)


if __name__ == "__main__":
    unittest.main()
