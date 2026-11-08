"""Real synthetic mutual-TLS boundary checks; no broker or database connection."""
import base64
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import socket
import ssl
import tempfile
import threading
import time
import unittest
from uuid import UUID

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from investalo_credential_store.models import StoreContext
from investalo_credential_store.onboarding import OnboardingResult
from investalo_credential_store.passkey_request_assertion import PasskeyRequestVerifier, TARGETS
from investalo_credential_store.private_http import (
    CredentialHTTPApplication, create_private_https_server, parse_request_context,
)
from investalo_credential_store.request_assertion import OnboardingRejected
from test_passkey_assertions import (
    CONNECTION, ISSUER, KEY, NOW, ORIGIN, SUBJECT, TENANT, USER,
    fixture_body, fixture_claims, fixture_context, sign_assertion,
)


def wire_context(**changes):
    context = fixture_context()
    fields = {name: getattr(context, name) for name in context.__slots__}
    fields.update(changes)
    for name in ("tenant_id", "user_id"):
        fields[name] = str(fields[name])
    return fields


def encoded_context(fields=None, *, raw=None):
    raw = json.dumps(wire_context() if fields is None else fields,
                     separators=(",", ":"), ensure_ascii=False).encode() if raw is None else raw
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def authority():
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "synthetic credential authority")])
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(now + timedelta(hours=1))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(key.public_key()), critical=False)
            .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False,
                                        key_encipherment=False, data_encipherment=False,
                                        key_agreement=False, key_cert_sign=True, crl_sign=True,
                                        encipher_only=False, decipher_only=False), critical=True)
            .sign(key, hashes.SHA256()))
    return key, cert


def leaf(ca_key, ca_cert, name, usage):
    key = ec.generate_private_key(ec.SECP256R1())
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder()
            .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)]))
            .issuer_name(ca_cert.subject).public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(now + timedelta(hours=1))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
            .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False,
                                        key_encipherment=False, data_encipherment=False,
                                        key_agreement=False, key_cert_sign=False, crl_sign=False,
                                        encipher_only=False, decipher_only=False), critical=True)
            .add_extension(x509.SubjectAlternativeName([x509.DNSName(name)]), critical=False)
            .add_extension(x509.ExtendedKeyUsage([usage]), critical=False)
            .sign(ca_key, hashes.SHA256()))
    return key, cert


class PrivateContextTests(unittest.TestCase):
    def setUp(self):
        self.context = StoreContext(tenant_id=TENANT, user_id=USER,
                                    expected_login_role="credential_fixture")

    def test_context_is_independent_from_assertion_and_preserves_original_time(self):
        context = parse_request_context(encoded_context(), self.context)
        self.assertEqual(context.oidc_auth_time, NOW - 86400)
        self.assertEqual(context.subject, SUBJECT)
        self.assertEqual(context.tenant_id, TENANT)
        self.assertEqual(context.user_id, USER)

    def test_foreign_actor_role_extras_and_invalid_scalar_context_rejected(self):
        changes = (
            {"tenant_id": UUID(int=201)}, {"user_id": UUID(int=202)},
            {"expected_login_role": "investalo_migration"}, {"subject": "\x00private"},
            {"auth_epoch": True}, {"session_expires_at": 1.0},
            {"session_binding": "ZZ" * 32}, {"user_id": str(USER).upper()},
        )
        for change in changes:
            with self.subTest(change=next(iter(change))):
                with self.assertRaises(OnboardingRejected):
                    parse_request_context(encoded_context(wire_context(**change)), self.context)

    def test_duplicate_invalid_utf8_excess_noncanonical_base64_and_nan_rejected(self):
        normal = json.dumps(wire_context(), separators=(",", ":")).encode()
        cases = (
            b'{"subject":"first","subject":"second"}', b"\xff", b" " * 2049,
            normal.replace(b'"auth_epoch":2', b'"auth_epoch":NaN'),
        )
        for raw in cases:
            with self.subTest(size=len(raw)):
                with self.assertRaises(OnboardingRejected):
                    parse_request_context(encoded_context(raw=raw), self.context)
        for wire in (encoded_context() + "=", "", "aaaa.", None):
            with self.assertRaises(OnboardingRejected):
                parse_request_context(wire, self.context)

    def test_application_is_default_off_immutable_redacted(self):
        application = CredentialHTTPApplication(self.context, lambda *_: None)
        self.assertFalse(application.enabled)
        with self.assertRaises(AttributeError):
            application.enabled = True
        self.assertNotIn(str(TENANT), repr(application))


class PrivateHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix="credential-mtls-synthetic-")
        cls.path = Path(cls.directory.name)
        ca_key, ca_cert = authority()
        other_key, other_cert = authority()
        pairs = {
            "server": leaf(ca_key, ca_cert, "localhost", ExtendedKeyUsageOID.SERVER_AUTH),
            "client": leaf(ca_key, ca_cert, "synthetic-bff", ExtendedKeyUsageOID.CLIENT_AUTH),
            "unpinned": leaf(ca_key, ca_cert, "other-bff", ExtendedKeyUsageOID.CLIENT_AUTH),
            "foreign": leaf(other_key, other_cert, "foreign-bff", ExtendedKeyUsageOID.CLIENT_AUTH),
            "wrong_eku": leaf(ca_key, ca_cert, "wrong-bff", ExtendedKeyUsageOID.SERVER_AUTH),
        }
        cls.ca = cls.path / "ca.pem"
        cls.ca.write_bytes(ca_cert.public_bytes(serialization.Encoding.PEM))
        cls.pin = hashlib.sha256(pairs["client"][1].public_bytes(serialization.Encoding.DER)).hexdigest()
        for name, (key, cert) in pairs.items():
            cert_path, key_path = cls.path / f"{name}.pem", cls.path / f"{name}.key"
            cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
            key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM,
                                                  serialization.PrivateFormat.PKCS8,
                                                  serialization.NoEncryption()))
            key_path.chmod(0o400)
        cls.store = StoreContext(tenant_id=TENANT, user_id=USER,
                                expected_login_role="credential_fixture")

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def setUp(self):
        self.calls = []
        self.verifier = PasskeyRequestVerifier(
            key=KEY, oidc_issuer=ISSUER, origin=ORIGIN, clock=lambda: NOW,
        )

    def execute(self, context, action, token, body):
        self.verifier.verify(token, action=action, body=body, context=context)
        self.calls.append((context, action, token, body))
        return OnboardingResult(UUID(CONNECTION), 1, 1,
                                "revoked" if action == "revoke" else "active")

    def server_context(self):
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.verify_mode = ssl.CERT_REQUIRED
        context.load_verify_locations(cafile=str(self.ca))
        context.load_cert_chain(str(self.path / "server.pem"), str(self.path / "server.key"))
        return context

    def client_context(self, identity="client"):
        context = ssl.create_default_context(cafile=str(self.ca))
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        if identity is not None:
            context.load_cert_chain(str(self.path / f"{identity}.pem"),
                                    str(self.path / f"{identity}.key"))
        return context

    @contextmanager
    def server(self, *, enabled=True, execute=None, timeout=3, max_workers=4):
        application = CredentialHTTPApplication(self.store, execute or self.execute, enabled=enabled)
        service = create_private_https_server(
            ("127.0.0.1", 0), tls_context=self.server_context(),
            client_certificate_sha256=frozenset((self.pin,)), application=application,
            timeout_seconds=timeout, max_workers=max_workers,
        )
        thread = threading.Thread(target=service.serve_forever, kwargs={"poll_interval": 0.02},
                                  daemon=True)
        thread.start()
        try:
            yield service
        finally:
            service.shutdown()
            service.server_close()
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive())

    def request(self, *, action="register", body=None, token=None,
                context=None, method="POST", path=None, headers=None):
        body = fixture_body(action) if body is None else body
        token = sign_assertion(fixture_claims(action, body=body)) if token is None else token
        context = encoded_context() if context is None else context
        values = [
            ("Host", "localhost"), ("Authorization", "Bearer " + token),
            ("X-Investalo-Credential-Context", context),
            ("Content-Type", "application/json"), ("Content-Length", str(len(body))),
            ("Connection", "close"),
        ]
        if headers is not None:
            values = headers(values)
        wire = f"{method} {path or TARGETS[action]} HTTP/1.1\r\n"
        wire += "".join(f"{name}: {value}\r\n" for name, value in values)
        return wire.encode() + b"\r\n" + body

    def exchange(self, service, raw, identity="client", hostname="localhost"):
        with socket.create_connection(service.server_address, timeout=3) as plain:
            with self.client_context(identity).wrap_socket(plain, server_hostname=hostname) as connection:
                connection.sendall(raw)
                received = bytearray()
                while True:
                    block = connection.recv(4096)
                    if not block:
                        break
                    received.extend(block)
                return bytes(received)

    def response(self, raw):
        head, body = raw.split(b"\r\n\r\n", 1)
        status = int(head.split(b" ", 2)[1])
        self.assertIn(b"Cache-Control: no-store", head)
        self.assertIn(b"Connection: close", head)
        self.assertNotIn(b"Server:", head)
        for private in (SUBJECT.encode(), b"synthetic-private-secret", KEY):
            self.assertNotIn(private, raw)
        return status, json.loads(body)

    def test_all_actions_real_mtls_exact_whitespace_utf8_body_and_four_field_result(self):
        with self.server() as service:
            for action in TARGETS:
                body = b" \n" + fixture_body(action) + b"\t "
                status, result = self.response(self.exchange(service, self.request(action=action, body=body)))
                self.assertEqual(status, 200)
                self.assertEqual(set(result), {"connection_id", "credential_revision", "storage_version", "status"})
                self.assertEqual(self.calls[-1][3], body)
                self.assertEqual(self.calls[-1][0].oidc_auth_time, NOW - 86400)
                self.assertEqual(self.calls[-1][1], action)
        self.assertEqual(len(self.calls), 3)

    def test_default_disabled_404_without_reading_private_body_or_executor(self):
        with self.server(enabled=False) as service:
            raw = self.request(headers=lambda items: [
                (name, "4096" if name == "Content-Length" else value) for name, value in items
            ]).split(b"\r\n\r\n")[0] + b"\r\n\r\n"
            status, result = self.response(self.exchange(service, raw))
            self.assertEqual(status, 404)
        self.assertEqual(self.calls, [])

    def test_missing_untrusted_wrong_eku_or_other_ca_client_never_reaches_executor(self):
        with self.server() as service:
            for identity in (None, "unpinned", "foreign", "wrong_eku"):
                with self.subTest(identity=identity):
                    try:
                        response = self.exchange(service, self.request(), identity)
                    except (OSError, ssl.SSLError):
                        response = b""
                    self.assertNotIn(b" 200 ", response)
        self.assertEqual(self.calls, [])

    def test_client_verifies_server_hostname(self):
        with self.server() as service:
            with self.assertRaises(ssl.SSLCertVerificationError):
                self.exchange(service, self.request(), hostname="wrong.fixture.invalid")
        self.assertEqual(self.calls, [])

    def test_duplicate_sensitive_headers_and_obsolete_folding_are_rejected(self):
        with self.server() as service:
            for name in ("Host", "Authorization", "X-Investalo-Credential-Context",
                         "Content-Type", "Content-Length"):
                with self.subTest(header=name):
                    raw = self.request(headers=lambda items: items + [
                        (name.lower(), next(value for key, value in items if key == name)),
                    ])
                    self.assertEqual(self.response(self.exchange(service, raw))[0], 400)
            raw = self.request().replace(b"Host: localhost\r\n", b"Host: localhost\r\n folded\r\n")
            self.assertEqual(self.response(self.exchange(service, raw))[0], 431)
            for invalid in (b"Host : localhost\r\n", b"Ho(st: localhost\r\n",
                            b"Host: local\x00host\r\n"):
                raw = self.request().replace(b"Host: localhost\r\n", invalid)
                self.assertEqual(self.response(self.exchange(service, raw))[0], 431)
        self.assertEqual(self.calls, [])

    def test_transfer_encoding_content_encoding_expect_and_unknown_headers_rejected(self):
        with self.server() as service:
            for name, value in (("Transfer-Encoding", "chunked"), ("Content-Encoding", "gzip"),
                                ("Expect", "100-continue"), ("X-Actor-Role", "investalo_migration")):
                with self.subTest(header=name):
                    status, _ = self.response(self.exchange(
                        service, self.request(headers=lambda items: items + [(name, value)]),
                    ))
                    self.assertEqual(status, 400)
        self.assertEqual(self.calls, [])

    def test_unknown_path_query_wrong_method_and_absolute_target_rejected(self):
        with self.server() as service:
            for path in (TARGETS["register"] + "?x=1", "/private-secret",
                         "https://localhost" + TARGETS["register"]):
                self.assertEqual(self.response(self.exchange(service, self.request(path=path)))[0], 404)
            self.assertEqual(self.response(self.exchange(service, self.request(method="GET")))[0], 405)
            self.assertEqual(self.response(self.exchange(
                service, self.request(path="/" + TARGETS["register"]),
            ))[0], 400)
        self.assertEqual(self.calls, [])

    def test_zero_negative_float_duplicate_missing_and_excess_body_lengths_rejected(self):
        with self.server() as service:
            for length in ("0", "-1", "1.0", "+1", "0002", "4097"):
                with self.subTest(length=length):
                    raw = self.request(headers=lambda items: [
                        (name, length if name == "Content-Length" else value) for name, value in items
                    ])
                    self.assertIn(self.response(self.exchange(service, raw))[0], (400, 413))
            raw = self.request(headers=lambda items: [(name, value) for name, value in items
                                                     if name != "Content-Length"])
            self.assertEqual(self.response(self.exchange(service, raw))[0], 400)
        self.assertEqual(self.calls, [])

    def test_total_header_and_single_line_budget_rejected_without_secret_echo(self):
        with self.server() as service:
            for extras in ([("Accept", "x" * 9217)],
                           [("Accept", "x" * 8000), ("Connection", "x" * 8000)]):
                self.assertEqual(self.response(self.exchange(
                    service, self.request(headers=lambda items: items + extras),
                ))[0], 431)
        self.assertEqual(self.calls, [])

    def test_actor_session_time_and_body_drift_do_not_reach_verified_executor(self):
        with self.server() as service:
            for context in (
                encoded_context(wire_context(user_id=UUID(int=202))),
                encoded_context(wire_context(tenant_id=UUID(int=203))),
                encoded_context(wire_context(subject="foreign-opaque")),
                encoded_context(wire_context(oidc_auth_time=NOW - 10)),
                encoded_context(wire_context(session_binding="01" * 32)),
                encoded_context(wire_context(auth_epoch=3)),
            ):
                with self.subTest(context_length=len(context)):
                    status, _ = self.response(self.exchange(service, self.request(context=context)))
                    self.assertIn(status, (401, 403))
            token = sign_assertion(fixture_claims())
            status, _ = self.response(self.exchange(
                service, self.request(body=fixture_body() + b" ", token=token),
            ))
            self.assertEqual(status, 401)
        self.assertEqual(self.calls, [])

    def test_arbitrary_executor_exceptions_are_static_and_never_retried(self):
        calls = []
        def execute(*args):
            calls.append(1)
            raise RuntimeError("synthetic-private-secret " + KEY.decode())
        with self.server(execute=execute) as service:
            status, value = self.response(self.exchange(service, self.request()))
            self.assertEqual((status, value), (503, {"error": "unavailable"}))
        self.assertEqual(len(calls), 1)
        def mutated(*args):
            error = OnboardingRejected("unavailable")
            error.code = "synthetic-private-secret"
            raise error
        with self.server(execute=mutated) as service:
            status, value = self.response(self.exchange(service, self.request()))
            self.assertEqual((status, value), (503, {"error": "unavailable"}))
        class Subclass(OnboardingRejected):
            CODES = frozenset(("synthetic-private-secret",))
        with self.server(execute=lambda *_: (_ for _ in ()).throw(
                Subclass("synthetic-private-secret"))) as service:
            status, value = self.response(self.exchange(service, self.request()))
            self.assertEqual((status, value), (503, {"error": "unavailable"}))

    def test_public_result_rejects_private_dictionary_malformed_uuid_and_bad_versions(self):
        values = [
            {"secret": "synthetic-private-secret"},
            OnboardingResult("synthetic-private-secret", 1, 1, "active"),
            OnboardingResult(UUID(CONNECTION), True, 1, "active"),
            OnboardingResult(UUID(CONNECTION), 1, 9007199254740992, "active"),
            OnboardingResult(UUID(CONNECTION), 1, 1, "revoked"),
        ]
        for value in values:
            with self.server(execute=lambda *_: value) as service:
                status, result = self.response(self.exchange(service, self.request()))
                self.assertEqual((status, result), (400, {"error": "invalid_record"}))

    def test_one_request_per_socket_drops_pipelined_second_operation(self):
        with self.server() as service:
            raw = self.request() + self.request()
            status, _ = self.response(self.exchange(service, raw))
            self.assertEqual(status, 200)
        self.assertEqual(len(self.calls), 1)

    def test_total_deadline_bounds_header_slow_drip(self):
        with self.server(timeout=1) as service:
            with socket.create_connection(service.server_address, timeout=3) as plain:
                with self.client_context().wrap_socket(plain, server_hostname="localhost") as connection:
                    started = time.monotonic()
                    connection.sendall(b"POST " + TARGETS["register"].encode() + b" HTTP/1.1\r\n")
                    time.sleep(0.6)
                    connection.sendall(b"Host: localhost\r\n")
                    try:
                        response = connection.recv(4096)
                    except OSError:
                        response = b""
                    self.assertLess(time.monotonic() - started, 1.7)
                    self.assertNotIn(b" 200 ", response)
        self.assertEqual(self.calls, [])

    def test_capacity_is_bounded_and_recovers_after_deadline(self):
        with self.server(timeout=1, max_workers=1) as service:
            with socket.create_connection(service.server_address, timeout=3) as plain:
                with self.client_context().wrap_socket(plain, server_hostname="localhost"):
                    try:
                        response = self.exchange(service, self.request())
                    except OSError:
                        response = b""
                    self.assertNotIn(b" 200 ", response)
                    time.sleep(1.15)
            status, _ = self.response(self.exchange(service, self.request()))
            self.assertEqual(status, 200)
        self.assertEqual(len(self.calls), 1)

    def test_invalid_tls_pin_capacity_and_context_configuration_fail_before_listener(self):
        base = {
            "tls_context": self.server_context(), "client_certificate_sha256": frozenset((self.pin,)),
            "application": CredentialHTTPApplication(self.store, self.execute),
        }
        changes = (
            {"client_certificate_sha256": frozenset()}, {"client_certificate_sha256": {self.pin}},
            {"client_certificate_sha256": frozenset(("XX" * 32,))}, {"timeout_seconds": 0.5},
            {"max_workers": 0}, {"max_workers": True}, {"application": None},
        )
        weak = self.server_context()
        weak.verify_mode = ssl.CERT_NONE
        for changed in (*changes, {"tls_context": weak}):
            with self.assertRaises(OnboardingRejected):
                create_private_https_server(("127.0.0.1", 0), **{**base, **changed})


if __name__ == "__main__":
    unittest.main()
