"""Injected development-only credential HTTPS adapter, with no runtime launcher.

This small stdlib server is an isolated integration boundary, not a production
HTTP stack. No provider, key paths, database identity or broker transport can be
selected by a request. The configured callback must use PasskeyBitgetOnboarding:
TLS authenticates the BFF transport; that executor separately verifies the
passkey assertion and consumes the durable authorization before any probe.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import http.client
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import re
import socket
from socketserver import ThreadingMixIn
import ssl
import threading
from uuid import UUID

from .models import StoreContext, _PrivateImmutable
from .onboarding import OnboardingResult
from .passkey_request_assertion import (
    MAX_BODY_BYTES, MAX_SAFE_INTEGER, PasskeyRequestContext, TARGETS,
)
from .request_assertion import OnboardingRejected

CONTEXT_HEADER = "X-Investalo-Credential-Context"
MAX_CONTEXT_BYTES = 2048
MAX_HEADER_BYTES = 16384
MAX_HEADER_LINE = 9216
MAX_RESPONSE_BYTES = 4096
_CONTEXT_FIELDS = frozenset(PasskeyRequestContext.__slots__)
_ALLOWED_HEADERS = frozenset((
    "host", "authorization", "x-investalo-credential-context", "content-type",
    "content-length", "connection", "accept",
))
_ERROR_STATUS = {
    "authentication_required": 401, "authentication_failed": 401,
    "access_denied": 403, "concurrent_change": 409, "identity_conflict": 409,
    "unavailable": 503, "key_unavailable": 503, "crypto_failure": 503,
}


def _object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError()
        value[key] = item
    return value


def _invalid_constant(_):
    raise ValueError()


def parse_request_context(value: str, configured: StoreContext) -> PasskeyRequestContext:
    """Decode the separately TLS-authenticated BFF context, never token claims."""
    try:
        if (type(configured) is not StoreContext or type(value) is not str
                or not 1 <= len(value) <= (MAX_CONTEXT_BYTES * 4 + 2) // 3
                or re.fullmatch(r"[A-Za-z0-9_-]+", value) is None):
            raise ValueError()
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        if (len(raw) > MAX_CONTEXT_BYTES
                or base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii") != value):
            raise ValueError()
        fields = json.loads(raw.decode("utf-8", errors="strict"),
                           object_pairs_hook=_object, parse_constant=_invalid_constant)
        if type(fields) is not dict or set(fields) != _CONTEXT_FIELDS:
            raise ValueError()
        for field in ("tenant_id", "user_id"):
            if type(fields[field]) is not str:
                raise ValueError()
            parsed = UUID(fields[field])
            if str(parsed) != fields[field]:
                raise ValueError()
            fields[field] = parsed
        context = PasskeyRequestContext(**fields)
        if (context.tenant_id != configured.tenant_id
                or context.user_id != configured.user_id):
            raise ValueError()
        return context
    except Exception:
        raise OnboardingRejected("access_denied") from None


class CredentialHTTPApplication(_PrivateImmutable):
    """Fixed-actor trusted callback. Requests cannot choose the credential LOGIN."""
    __slots__ = ("context", "execute", "enabled")

    def __init__(self, context: StoreContext, execute, *, enabled: bool = False):
        if (type(context) is not StoreContext or not callable(execute)
                or type(enabled) is not bool):
            raise OnboardingRejected("invalid_context") from None
        object.__setattr__(self, "context", context)
        object.__setattr__(self, "execute", execute)
        object.__setattr__(self, "enabled", enabled)


def _public_result(result, action):
    if type(result) is not OnboardingResult:
        raise OnboardingRejected("invalid_record") from None
    value = result.public()
    try:
        if type(value) is not dict or set(value) != {
            "connection_id", "credential_revision", "storage_version", "status",
        }:
            raise ValueError()
        connection = value["connection_id"]
        if type(connection) is not str or str(UUID(connection)) != connection:
            raise ValueError()
        for field in ("credential_revision", "storage_version"):
            if type(value[field]) is not int or not 1 <= value[field] <= MAX_SAFE_INTEGER:
                raise ValueError()
        if value["status"] != ("revoked" if action == "revoke" else "active"):
            raise ValueError()
        return value
    except Exception:
        raise OnboardingRejected("invalid_record") from None


class _HeaderBudget:
    def __init__(self, reader):
        self.reader, self.remaining = reader, MAX_HEADER_BYTES

    def readline(self, _limit=-1):
        limit = min(self.remaining + 1, MAX_HEADER_LINE + 1)
        value = self.reader.readline(limit)
        self.remaining -= len(value)
        if (self.remaining < 0 or len(value) > MAX_HEADER_LINE
                or value and not value.endswith(b"\r\n")
                or value not in (b"", b"\r\n") and (
                    re.match(rb"[!#$%&'*+\-.^_`|~0-9A-Za-z]+:", value) is None
                    or any(byte < 32 and byte != 9 or byte >= 127 for byte in value[:-2])
                )):
            raise http.client.LineTooLong("private header")
        return value


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_):
        pass

    def send_error(self, code, message=None, explain=None):
        # BaseHTTPServer's default HTML errors can echo request lines/paths.
        self._reply(code if code in (400, 404, 405, 413, 431) else 400,
                    {"error": "invalid_request"})

    def handle_expect_100(self):
        self._reply(400, {"error": "invalid_request"})
        return False

    def _reply(self, status, value):
        self.close_connection = True
        try:
            body = json.dumps(value, separators=(",", ":"), ensure_ascii=True).encode("ascii")
            if len(body) > MAX_RESPONSE_BYTES:
                raise ValueError()
            self.send_response_only(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(body)
        except Exception:
            # A lost response never causes a retry of the executed operation.
            pass

    def handle_one_request(self):
        self.close_connection = True
        try:
            self.raw_requestline = self.rfile.readline(4097)
            if not self.raw_requestline:
                return
            request = re.fullmatch(
                rb"([A-Z]{1,16}) ([!-~]{1,2048}) HTTP/1\.1\r\n", self.raw_requestline,
            )
            if len(self.raw_requestline) > 4096 or request is None:
                self.request_version = "HTTP/1.1"
                self._reply(400, {"error": "invalid_request"})
                return
            original = self.rfile
            self.rfile = _HeaderBudget(original)
            try:
                parsed = self.parse_request()
            finally:
                self.rfile = original
            if not parsed:
                return
            if self.path != request.group(2).decode("ascii"):
                self._reply(400, {"error": "invalid_request"})
                return
            # One request per authenticated connection; no pipelining/upgrade.
            self.close_connection = True
            self._dispatch()
        except Exception:
            self._reply(400, {"error": "invalid_request"})

    def _dispatch(self):
        app = self.server.application
        if not app.enabled:
            self._reply(404, {"error": "invalid_request"})
            return
        if self.request_version != "HTTP/1.1":
            self._reply(400, {"error": "invalid_request"})
            return
        action = next((key for key, path in TARGETS.items() if path == self.path), None)
        if action is None:
            self._reply(404, {"error": "invalid_request"})
            return
        if self.command != "POST":
            self._reply(405, {"error": "invalid_request"})
            return
        try:
            names = [name.lower() for name in self.headers.keys()]
            if (len(names) != len(set(names)) or len(names) > 16
                    or not set(names) <= _ALLOWED_HEADERS
                    or any("\r" in value or "\n" in value
                           for value in self.headers.values())):
                raise OnboardingRejected("invalid_request")
            host = self.headers.get("Host")
            if (type(host) is not str or not 1 <= len(host) <= 255
                    or re.fullmatch(r"[a-zA-Z0-9.-]+(?::[0-9]{1,5})?", host) is None):
                raise OnboardingRejected("invalid_request")
            if (self.headers.get("Content-Type") != "application/json"
                    or self.headers.get("Connection", "close").lower() != "close"
                    or self.headers.get("Accept", "application/json") != "application/json"):
                raise OnboardingRejected("invalid_request")
            length = self.headers.get("Content-Length")
            if type(length) is not str or re.fullmatch(r"[1-9][0-9]{0,3}", length) is None:
                raise OnboardingRejected("invalid_request")
            size = int(length)
            if size > MAX_BODY_BYTES:
                self._reply(413, {"error": "invalid_request"})
                return
            authorization = self.headers.get("Authorization")
            if (type(authorization) is not str
                    or re.fullmatch(r"Bearer [A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+",
                                    authorization) is None
                    or len(authorization) > 8199):
                raise OnboardingRejected("authentication_required")
            context = parse_request_context(self.headers.get(CONTEXT_HEADER), app.context)
            body = self.rfile.read(size)
            if len(body) != size:
                raise OnboardingRejected("invalid_request")
            result = app.execute(context, action, authorization[7:], body)
            self._reply(200, _public_result(result, action))
        except OnboardingRejected as error:
            code = (error.code if type(error.code) is str and error.code in OnboardingRejected.CODES
                    else "unavailable")
            self._reply(_ERROR_STATUS.get(code, 400), {"error": code})
        except Exception:
            self._reply(503, {"error": "unavailable"})


def _abort_socket(connection):
    try:
        connection.shutdown(socket.SHUT_RDWR)
    except Exception:
        pass
    try:
        connection.close()
    except Exception:
        pass


class _PrivateHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    block_on_close = False
    request_queue_size = 8

    def get_request(self):
        raw, address = super().get_request()
        if not self._slots.acquire(blocking=False):
            raw.close()
            raise OSError("private service capacity")
        connection = raw
        timer = None
        try:
            raw.settimeout(self.timeout_seconds)
            connection = self.tls_context.wrap_socket(
                raw, server_side=True, do_handshake_on_connect=False,
            )
            # Total connection deadline bounds handshake/header/body slow drips.
            timer = threading.Timer(self.timeout_seconds, _abort_socket, args=(connection,))
            timer.daemon = True
            timer.start()
            connection.do_handshake()
            peer = connection.getpeercert(binary_form=True)
            digest = hashlib.sha256(peer).hexdigest()
            if not any(hmac.compare_digest(digest, allowed) for allowed in self.peer_fingerprints):
                raise ssl.SSLError("private peer rejected")
            with self._timer_lock:
                self._timers[id(connection)] = timer
            return connection, address
        except Exception:
            if timer is not None:
                timer.cancel()
            _abort_socket(connection)
            self._slots.release()
            raise OSError("private peer rejected") from None

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._release(request)

    def process_request(self, request, client_address):
        try:
            super().process_request(request, client_address)
        except Exception:
            self._release(request)
            _abort_socket(request)
            raise

    def _release(self, request):
        with self._timer_lock:
            timer = self._timers.pop(id(request), None)
        if timer is not None:
            timer.cancel()
            self._slots.release()

    def handle_error(self, request, client_address):
        # SocketServer's default traceback can retain the private callback body.
        pass


def create_private_https_server(address, *, tls_context: ssl.SSLContext,
                                client_certificate_sha256: frozenset[str],
                                application: CredentialHTTPApplication,
                                timeout_seconds: float = 20,
                                max_workers: int = 4):
    """Create an explicitly injected, default-off development mTLS server.

    The caller owns certificate loading, trusted peer fingerprints and lifecycle.
    No environment/file provisioning, listening default or automatic activation
    is provided. A deadline can close a response while its final DB transaction
    completes; callers must reconcile such uncertainty and never retry blindly.
    """
    try:
        if (type(application) is not CredentialHTTPApplication
                or not isinstance(tls_context, ssl.SSLContext)
                or tls_context.protocol != ssl.PROTOCOL_TLS_SERVER
                or tls_context.verify_mode != ssl.CERT_REQUIRED
                or tls_context.minimum_version < ssl.TLSVersion.TLSv1_2
                or tls_context.cert_store_stats()["x509_ca"] < 1
                or type(client_certificate_sha256) is not frozenset
                or not 1 <= len(client_certificate_sha256) <= 4
                or any(type(item) is not str or re.fullmatch(r"[a-f0-9]{64}", item) is None
                       for item in client_certificate_sha256)
                or type(timeout_seconds) not in (int, float)
                or not 1 <= timeout_seconds <= 30
                or type(max_workers) is not int or not 1 <= max_workers <= 8):
            raise ValueError()
        server = _PrivateHTTPServer(address, _Handler)
        server.application = application
        server.tls_context = tls_context
        server.peer_fingerprints = client_certificate_sha256
        server.timeout_seconds = timeout_seconds
        server._slots = threading.BoundedSemaphore(max_workers)
        server._timers, server._timer_lock = {}, threading.Lock()
        return server
    except Exception:
        raise OnboardingRejected("invalid_context") from None
