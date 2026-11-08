"""Actual synthetic TLS checks of the pinned ASGI and capacity boundaries."""
import asyncio
from contextlib import contextmanager
import io
import logging
import os
import socket
import ssl
import threading
import time
import unittest
from unittest.mock import patch
from uuid import UUID

from investalo_credential_store.onboarding import OnboardingResult
from investalo_credential_store.passkey_request_assertion import TARGETS
from investalo_credential_store.private_asgi import (
    _Application, create_private_asgi_server,
)
from investalo_credential_store.private_http import CredentialHTTPApplication
from investalo_credential_store.request_assertion import OnboardingRejected
import test_private_http as fixture
from test_passkey_assertions import CONNECTION, KEY, NOW, fixture_body


class PrivateASGITests(unittest.TestCase):
    # Certificate and wire fixture helpers only; the old TestCase is not
    # subclassed, imported as a class, or collected a second time.
    setUpClass = classmethod(fixture.PrivateHTTPTests.setUpClass.__func__)
    tearDownClass = classmethod(fixture.PrivateHTTPTests.tearDownClass.__func__)
    setUp = fixture.PrivateHTTPTests.setUp
    execute = fixture.PrivateHTTPTests.execute
    server_context = fixture.PrivateHTTPTests.server_context
    client_context = fixture.PrivateHTTPTests.client_context
    request = fixture.PrivateHTTPTests.request
    exchange = fixture.PrivateHTTPTests.exchange
    response = fixture.PrivateHTTPTests.response

    @contextmanager
    def server(self, *, enabled=True, execute=None, timeout=3, max_workers=4):
        service = create_private_asgi_server(
            ("127.0.0.1", 0), tls_context=self.server_context(),
            client_certificate_sha256=frozenset((self.pin,)),
            application=CredentialHTTPApplication(self.store, execute or self.execute, enabled=enabled),
            timeout_seconds=timeout, max_workers=max_workers,
        )
        thread = threading.Thread(target=service.serve_forever, daemon=True)
        thread.start()
        try:
            yield service
        finally:
            service.shutdown()
            service.server_close()
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive())

    def connected(self, service):
        plain = socket.create_connection(service.server_address, timeout=3)
        try:
            return self.client_context().wrap_socket(plain, server_hostname="localhost")
        except Exception:
            plain.close()
            raise

    def eventually(self, predicate):
        deadline = time.monotonic() + 2
        while not predicate() and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(predicate())

    def test_asgi_all_actions_preserve_original_context_and_exact_private_bytes(self):
        with self.server() as service:
            for action in TARGETS:
                body = b" \n" + fixture_body(action) + b"\t "
                status, value = self.response(self.exchange(service, self.request(action=action, body=body)))
                self.assertEqual(status, 200)
                self.assertEqual(set(value), {"connection_id", "credential_revision", "storage_version", "status"})
                self.assertEqual(self.calls[-1][3], body)
                self.assertEqual(self.calls[-1][0].oidc_auth_time, NOW - 86400)
            self.assertEqual(service.config.workers, 1)
            self.assertFalse(service.config.proxy_headers)
            self.assertFalse(service.loop.get_debug())
        self.assertEqual(len(self.calls), 3)

    def test_mtls_missing_other_ca_wrong_eku_and_unpinned_leaf_never_parse_or_execute(self):
        with self.server() as service:
            for identity in (None, "foreign", "wrong_eku", "unpinned"):
                try:
                    response = self.exchange(service, self.request(), identity)
                except (OSError, ssl.SSLError):
                    response = b""
                self.assertNotIn(b" 200 ", response)
            self.assertEqual(self.response(self.exchange(service, self.request()))[0], 200)
        self.assertEqual(len(self.calls), 1)

    def test_duplicate_content_length_and_obsfold_are_rejected_before_h11_normalizes(self):
        with self.server() as service:
            duplicate = self.request(headers=lambda values: values + [
                ("content-length", next(value for name, value in values if name == "Content-Length")),
            ])
            folded = self.request().replace(b"Host: localhost\r\n", b"Host: localhost\r\n folded\r\n")
            self.assertEqual(self.response(self.exchange(service, duplicate))[0], 400)
            self.assertEqual(self.response(self.exchange(service, folded))[0], 431)
        self.assertEqual(self.calls, [])

    def test_preparser_rejects_raw_path_normalization_and_forbidden_framing(self):
        with self.server() as service:
            cases = (
                (self.request(path="/" + TARGETS["register"]), 400),
                (self.request(path=TARGETS["register"] + "?private=1"), 404),
                (self.request(path="/v1/credentials/bitget/%72egister"), 404),
                (self.request().replace(b"Host: localhost\r\n", b"Host : localhost\r\n"), 431),
            )
            for raw, status in cases:
                self.assertEqual(self.response(self.exchange(service, raw))[0], status)
            for name, value in (("Transfer-Encoding", "chunked"), ("Expect", "100-continue"),
                                ("Content-Encoding", "gzip"), ("X-Forwarded-For", "127.0.0.1")):
                raw = self.request(headers=lambda values: values + [(name, value)])
                self.assertEqual(self.response(self.exchange(service, raw))[0], 400)
        self.assertEqual(self.calls, [])

    def test_exact_headers_do_not_gain_trailing_whitespace_acceptance(self):
        with self.server() as service:
            for target in ("Content-Type", "Authorization", "X-Investalo-Credential-Context",
                           "Content-Length", "Connection"):
                raw = self.request(headers=lambda values: [
                    (name, value + " " if name == target else value) for name, value in values
                ])
                self.assertIn(self.response(self.exchange(service, raw))[0], (400, 401, 403))
        self.assertEqual(self.calls, [])

    def test_bounded_headers_and_declared_body_reject_before_work_submission(self):
        with self.server() as service:
            line = self.request(headers=lambda values: values + [("Accept", "x" * 9217)])
            total = self.request(headers=lambda values: values + [
                ("Accept", "x" * 8000), ("Connection", "x" * 8000),
            ])
            self.assertEqual(self.response(self.exchange(service, line))[0], 431)
            self.assertEqual(self.response(self.exchange(service, total))[0], 431)
            oversized = self.request(headers=lambda values: [
                (name, "4097" if name == "Content-Length" else value) for name, value in values
            ])
            self.assertEqual(self.response(self.exchange(service, oversized))[0], 413)
        self.assertEqual(self.calls, [])

    def test_disabled_and_readiness_routes_do_not_wait_for_private_body(self):
        incomplete = self.request().split(b"\r\n\r\n", 1)[0] + b"\r\n\r\n"
        with self.server(enabled=False) as service:
            self.assertEqual(self.response(self.exchange(service, incomplete))[0], 404)
        with self.server() as service:
            self.assertEqual(self.response(self.exchange(service, self.request(method="GET")))[0], 405)
            self.assertEqual(self.response(self.exchange(service, self.request(path="/not-a-route")))[0], 404)
        self.assertEqual(self.calls, [])

    def test_fragmented_header_and_utf8_body_keep_exact_single_body(self):
        raw = self.request(body=b" \n" + fixture_body() + b"\t")
        with self.server() as service:
            with self.connected(service) as peer:
                for start in range(0, len(raw), 17):
                    peer.sendall(raw[start:start + 17])
                response = bytearray()
                while block := peer.recv(4096):
                    response.extend(block)
            self.assertEqual(self.response(bytes(response))[0], 200)
        self.assertEqual(self.calls[0][3], raw.split(b"\r\n\r\n", 1)[1])

    def test_extra_pipeline_bytes_are_never_another_asgi_operation(self):
        with self.server() as service:
            raw = self.request() + self.request() + b"x" * 65536
            status, _ = self.response(self.exchange(service, raw))
            self.assertEqual(status, 200)
        self.assertEqual(len(self.calls), 1)

    def test_total_deadline_does_not_reset_after_tls_handshake(self):
        with self.server(timeout=1, max_workers=1) as service:
            plain = socket.create_connection(service.server_address, timeout=3)
            try:
                self.eventually(lambda: service._connection_count == 1)
                started = time.monotonic()
                time.sleep(0.55)
                with self.client_context().wrap_socket(plain, server_hostname="localhost") as peer:
                    peer.sendall(b"POST " + TARGETS["register"].encode() + b" HTTP/1.1\r\n")
                    try:
                        response = peer.recv(4096)
                    except OSError:
                        response = b""
                    self.assertNotIn(b" 200 ", response)
                self.assertLess(time.monotonic() - started, 1.35)
            finally:
                plain.close()
        self.assertEqual(self.calls, [])

    def test_tls_handshake_capacity_is_bounded_and_recovers_once_after_timeout(self):
        with self.server(timeout=1, max_workers=1) as service:
            plain = socket.create_connection(service.server_address, timeout=3)
            try:
                self.eventually(lambda: service._connection_count == 1)
                try:
                    response = self.exchange(service, self.request())
                except OSError:
                    response = b""
                self.assertNotIn(b" 200 ", response)
                self.eventually(lambda: service._connection_count == 0)
                self.assertEqual(self.response(self.exchange(service, self.request()))[0], 200)
            finally:
                plain.close()
            self.eventually(lambda: service._connection_count == 0)
        self.assertEqual(len(self.calls), 1)

    def blocking_executor(self):
        entered, release, finished = threading.Event(), threading.Event(), threading.Event()
        calls = []
        def execute(*_):
            calls.append(1)
            entered.set()
            release.wait(timeout=5)
            finished.set()
            return OnboardingResult(UUID(CONNECTION), 1, 1, "active")
        self.addCleanup(release.set)
        return execute, entered, release, finished, calls

    def test_disconnected_callback_holds_work_capacity_until_actual_completion(self):
        execute, entered, release, finished, calls = self.blocking_executor()
        with self.server(execute=execute, max_workers=1) as service:
            peer = self.connected(service)
            peer.sendall(self.request())
            self.assertTrue(entered.wait(timeout=2))
            peer.close()
            self.eventually(lambda: service._connection_count == 0)
            self.assertEqual(service.work.active, 1)
            self.assertEqual(self.response(self.exchange(service, self.request()))[0], 503)
            self.assertEqual(len(calls), 1)
            release.set()
            self.assertTrue(finished.wait(timeout=2))
            self.eventually(lambda: service.work.active == 0)
            self.assertEqual(self.response(self.exchange(service, self.request()))[0], 200)
        self.assertEqual(len(calls), 2)

    def test_deadline_keeps_uncertain_work_permit_and_never_retries(self):
        execute, entered, release, finished, calls = self.blocking_executor()
        with self.server(execute=execute, timeout=1, max_workers=1) as service:
            peer = self.connected(service)
            peer.sendall(self.request())
            self.assertTrue(entered.wait(timeout=2))
            started = time.monotonic()
            try:
                response = peer.recv(4096)
            except OSError:
                response = b""
            finally:
                peer.close()
            self.assertLess(time.monotonic() - started, 1.5)
            self.assertNotIn(b" 200 ", response)
            self.eventually(lambda: service._connection_count == 0)
            self.assertEqual(service.work.active, 1)
            self.assertEqual(self.response(self.exchange(service, self.request()))[0], 503)
            self.assertEqual(len(calls), 1)
            release.set()
            self.assertTrue(finished.wait(timeout=2))
            self.eventually(lambda: service.work.active == 0)
        self.assertEqual(len(calls), 1)

    def test_shutdown_does_not_cancel_or_retry_already_running_work(self):
        execute, entered, release, finished, calls = self.blocking_executor()
        with self.server(execute=execute, max_workers=1) as service:
            peer = self.connected(service)
            try:
                peer.sendall(self.request())
                self.assertTrue(entered.wait(timeout=2))
                service.server_close()
                self.assertEqual(service.work.active, 1)
                self.assertFalse(finished.is_set())
                release.set()
                self.assertTrue(finished.wait(timeout=2))
            finally:
                peer.close()
        self.assertEqual(len(calls), 1)

    def test_scope_strings_and_copied_marker_cannot_establish_transport_authority(self):
        class Protocol:
            authenticated = False
            scope = {"type": "http", "scheme": "https"}
            service = None
        protocol = Protocol()
        sent = []
        async def receive():
            self.fail("Untrusted scope read private body")
        async def send(value):
            sent.append(value)
        asyncio.run(_Application(protocol)(protocol.scope, receive, send))
        self.assertEqual(sent[0]["status"], 403)
        protocol.authenticated = True
        sent.clear()
        asyncio.run(_Application(protocol)(dict(protocol.scope), receive, send))
        self.assertEqual(sent[0]["status"], 403)

    def test_private_errors_remain_static_without_uvicorn_or_asyncio_logs(self):
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        logger = logging.getLogger()
        logger.addHandler(handler)
        self.addCleanup(logger.removeHandler, handler)
        calls = []
        def execute(*_):
            calls.append(1)
            raise RuntimeError("synthetic-private-secret " + KEY.decode())
        with self.server(execute=execute) as service:
            self.assertEqual(self.response(self.exchange(service, self.request())),
                             (503, {"error": "unavailable"}))
        self.assertEqual(calls, [1])
        self.assertEqual(stream.getvalue(), "")

    def test_ambient_debug_and_web_concurrency_do_not_change_fixed_runtime(self):
        with patch.dict(os.environ, {"PYTHONASYNCIODEBUG": "1", "WEB_CONCURRENCY": "not-a-number"}):
            with self.server() as service:
                self.assertEqual(self.response(self.exchange(service, self.request()))[0], 200)
                self.assertFalse(service.loop.get_debug())
                self.assertEqual(service.config.workers, 1)

    def test_invalid_tls_capacity_and_nonfinite_deadline_reject_before_socket(self):
        base = dict(tls_context=self.server_context(), client_certificate_sha256=frozenset((self.pin,)),
                    application=CredentialHTTPApplication(self.store, self.execute))
        weak = self.server_context()
        weak.verify_mode = ssl.CERT_NONE
        changes = (
            {"tls_context": weak}, {"client_certificate_sha256": frozenset()},
            {"client_certificate_sha256": {self.pin}}, {"application": None},
            {"timeout_seconds": float("nan")}, {"timeout_seconds": float("inf")},
            {"timeout_seconds": True}, {"max_workers": 0}, {"max_workers": True},
        )
        for change in changes:
            with patch("investalo_credential_store.private_asgi.socket.socket") as listen:
                with self.assertRaises(OnboardingRejected):
                    create_private_asgi_server(("127.0.0.1", 0), **{**base, **change})
                listen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
