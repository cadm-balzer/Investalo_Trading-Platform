"""Actual synthetic mTLS and own signed-verifier boundaries, no DB/broker calls."""
from contextlib import contextmanager
import hashlib
import json
import ssl
import threading
import unittest
from uuid import UUID

from investalo_credential_store.demo_trading_passkey_assertion import DemoTradingPasskeyRequestVerifier, TARGETS
from investalo_credential_store.onboarding import OnboardingResult
from investalo_credential_store.private_asgi import create_private_asgi_server
from investalo_credential_store.private_http import (
    CredentialHTTPApplication, DemoCredentialHTTPApplication, DemoTradingCredentialHTTPApplication, create_private_https_server,
)
from investalo_credential_store.request_assertion import OnboardingRejected
import test_private_http as tls
from test_passkey_assertions import (
    ACCOUNT, CONNECTION, ISSUER, KEY, NOW, ORIGIN, fixture_body, fixture_claims, sign_assertion,
)


class DemoPrivateTransportTests(unittest.TestCase):
    setUpClass = classmethod(tls.PrivateHTTPTests.setUpClass.__func__)
    tearDownClass = classmethod(tls.PrivateHTTPTests.tearDownClass.__func__)
    server_context = tls.PrivateHTTPTests.server_context
    client_context = tls.PrivateHTTPTests.client_context
    exchange = tls.PrivateHTTPTests.exchange
    response = tls.PrivateHTTPTests.response

    def setUp(self):
        self.calls = []
        self.verifier = DemoTradingPasskeyRequestVerifier(key=KEY, oidc_issuer=ISSUER, origin=ORIGIN, clock=lambda: NOW)

    def execute(self, context, action, token, body):
        result = self.verifier.verify(token, action=action, body=body, context=context)
        self.calls.append((context, action, body))
        return OnboardingResult(UUID(result.target["connection_id"]), 1,
                                1 if action == "register" else result.target["expected_storage"] + 1,
                                "revoked" if action == "revoke" else "active")

    def request(self, action="register", *, path=None, normal=False, read=False, context=None, body=None):
        if body is None:
            payload = json.loads(fixture_body(action))
            if action == "revoke":
                payload["expected_revision"] = 1
            body = b" \n" + json.dumps(payload, ensure_ascii=False).encode() + b"\t "
        target = {"action": action, **json.loads(body)}
        target.pop("credentials", None)
        claims = fixture_claims(action, body=body, target=target)
        if not normal:
            claims.update(aud="investalo-credentials-demo-trading-passkey",
                          authorization_kind="passkey-demo-trading-credential-authorization/1", htu=TARGETS[action])
        if read:
            claims.update(aud="investalo-credentials-demo-passkey",
                          authorization_kind="passkey-demo-credential-authorization/1")
        return tls.PrivateHTTPTests.request(self, action=action, body=body,
            token=sign_assertion(claims), context=context, path=path or TARGETS[action])

    @contextmanager
    def server(self, factory, *, demo=True, read=False, enabled=True, execute=None):
        application = (DemoCredentialHTTPApplication if read else
                       DemoTradingCredentialHTTPApplication if demo else CredentialHTTPApplication)(
            self.store, execute or self.execute, enabled=enabled)
        service = factory(("127.0.0.1", 0), tls_context=self.server_context(),
            client_certificate_sha256=frozenset((self.pin,)), application=application, timeout_seconds=3)
        thread = threading.Thread(target=service.serve_forever, daemon=True)
        thread.start()
        try:
            yield service
        finally:
            service.shutdown()
            service.server_close()
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive())

    def test_both_listeners_dispatch_only_own_register_revoke_with_exact_signed_bytes(self):
        for factory in (create_private_https_server, create_private_asgi_server):
            with self.subTest(listener=factory.__name__), self.server(factory) as service:
                for action in ("register", "revoke"):
                    wire = self.request(action)
                    status, result = self.response(self.exchange(service, wire))
                    self.assertEqual(status, 200)
                    self.assertEqual(result["credential_revision"], 1)
                    self.assertEqual(self.calls[-1][2], wire.split(b"\r\n\r\n", 1)[1])
                    self.assertEqual(self.calls[-1][0].oidc_auth_time, NOW - 86400)
                    self.assertEqual(result["status"], "revoked" if action == "revoke" else "active")
        self.assertEqual(len(self.calls), 4)

    def test_normal_and_demo_paths_never_cross_or_dispatch_replace(self):
        for factory in (create_private_https_server, create_private_asgi_server):
            for demo in (True, False):
                with self.subTest(listener=factory.__name__, demo=demo), self.server(factory, demo=demo) as service:
                    path = "/v1/credentials/bitget/register" if demo else TARGETS["register"]
                    for target in (path, "/v1/credentials/bitget-demo-trading/replace", TARGETS["register"] + "?x=1"):
                        status, _ = self.response(self.exchange(service, self.request(path=target)))
                        self.assertEqual(status, 404)
        self.assertEqual(self.calls, [])

    def test_disabled_before_token_parsing_and_own_domain_rejects_normal_assertion(self):
        for factory in (create_private_https_server, create_private_asgi_server):
            with self.subTest(listener=factory.__name__), self.server(factory, enabled=False) as service:
                status, _ = self.response(self.exchange(service, self.request(normal=True)))
                self.assertEqual(status, 404)
            with self.server(factory) as service:
                status, _ = self.response(self.exchange(service, self.request(normal=True)))
                self.assertEqual(status, 401)
        self.assertEqual(self.calls, [])

    def test_actual_mtls_rejects_missing_foreign_and_unpinned_client(self):
        for factory in (create_private_https_server, create_private_asgi_server):
            with self.subTest(listener=factory.__name__), self.server(factory) as service:
                for identity in (None, "foreign", "unpinned"):
                    try:
                        received = self.exchange(service, self.request(), identity=identity)
                    except (OSError, ssl.SSLError):
                        continue
                    self.assertNotIn(b" 200 ", received)
        self.assertEqual(self.calls, [])

    def test_independent_tls_context_cannot_be_reconstructed_from_valid_assertion(self):
        for factory in (create_private_https_server, create_private_asgi_server):
            with self.subTest(listener=factory.__name__), self.server(factory) as service:
                context = tls.encoded_context({**tls.wire_context(), "oidc_auth_time": NOW - 1})
                status, _ = self.response(self.exchange(service, self.request(context=context)))
                self.assertEqual(status, 401)
        self.assertEqual(self.calls, [])

    def test_uncertain_execution_runs_once_and_returns_only_static_error(self):
        calls = []
        def fail(*args):
            calls.append(args)
            raise RuntimeError("synthetic-private-key-or-commit-sentinel")
        for factory in (create_private_https_server, create_private_asgi_server):
            with self.subTest(listener=factory.__name__), self.server(factory, execute=fail) as service:
                status, result = self.response(self.exchange(service, self.request()))
                self.assertEqual((status, result), (503, {"error": "unavailable"}))
        self.assertEqual(len(calls), 2)

    def test_own_application_rejects_changed_revision_or_private_result(self):
        for factory in (create_private_https_server, create_private_asgi_server):
            for value in (OnboardingResult(UUID(CONNECTION), 2, 1, "active"),
                          {"connection_id": CONNECTION, "secret": "synthetic-private-sentinel"}):
                with self.subTest(listener=factory.__name__), self.server(
                        factory, execute=lambda *_, value=value: value) as service:
                    status, result = self.response(self.exchange(service, self.request()))
                    self.assertEqual((status, result), (400, {"error": "invalid_record"}))

    def test_unknown_application_subclass_is_not_a_transport_domain(self):
        class Forged(DemoTradingCredentialHTTPApplication):
            __slots__ = ()
        for factory in (create_private_https_server, create_private_asgi_server):
            with self.subTest(listener=factory.__name__), self.assertRaises(OnboardingRejected):
                factory(("127.0.0.1", 0), tls_context=self.server_context(),
                    client_certificate_sha256=frozenset((self.pin,)), application=Forged(self.store, self.execute))

    def test_read_and_trading_paths_and_assertions_never_cross(self):
        for factory in (create_private_https_server, create_private_asgi_server):
            with self.subTest(listener=factory.__name__):
                with self.server(factory) as service:
                    for action in ("register", "revoke"):
                        status, _ = self.response(self.exchange(service,
                            self.request(action, path="/v1/credentials/bitget-demo/"+action)))
                        self.assertEqual(status, 404)
                    status, _ = self.response(self.exchange(service, self.request(read=True)))
                    self.assertEqual(status, 401)
                with self.server(factory, read=True) as service:
                    status, _ = self.response(self.exchange(service, self.request()))
                    self.assertEqual(status, 404)
        self.assertEqual(self.calls, [])
