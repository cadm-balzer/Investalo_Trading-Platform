"""Private pinned ASGI transport with independently bounded TLS and work.

This listener supplies accepted sockets to Uvicorn's pinned HTTP/1.1 engine.
Its own admission boundary includes handshakes; a separate work boundary
survives disconnected clients and uncertain commits. No request selects keys,
database roles or transport identity, and no operation is retried.
"""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import hashlib
import hmac
from http import HTTPStatus
import json
import logging
import math
import re
import socket
import ssl
import threading
import time

from uvicorn import Config
from uvicorn.protocols.http.h11_impl import H11Protocol
from uvicorn.server import ServerState

from .passkey_request_assertion import MAX_BODY_BYTES, TARGETS
from .private_http import (
    CONTEXT_HEADER, MAX_HEADER_BYTES, MAX_HEADER_LINE, MAX_RESPONSE_BYTES,
    CredentialHTTPApplication, _ALLOWED_HEADERS, _ERROR_STATUS, _public_result,
    parse_request_context,
)
from .request_assertion import OnboardingRejected

_REQUEST_LIMIT = 4096
_HEAD_LIMIT = _REQUEST_LIMIT + MAX_HEADER_BYTES
_QUIET = logging.Logger("investalo.private.credential.protocol", level=100)
_QUIET.disabled = True
_QUIET.propagate = False
_QUIET.addHandler(logging.NullHandler())


def _json(value):
    body = json.dumps(value, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    if len(body) > MAX_RESPONSE_BYTES:
        raise OnboardingRejected("invalid_record")
    return body


def _wire(status, value):
    body = _json(value)
    return (
        f"HTTP/1.1 {status} {HTTPStatus(status).phrase}\r\n".encode("ascii")
        + b"Content-Type: application/json\r\n"
        + f"Content-Length: {len(body)}\r\n".encode("ascii")
        + b"Cache-Control: no-store\r\nConnection: close\r\n\r\n" + body
    )


class _RejectedHead(Exception):
    def __init__(self, status):
        self.status = status


def _head(raw):
    """Validate original grammar before h11 unfolds or coalesces headers."""
    request, separator, headers = raw.partition(b"\r\n")
    match = re.fullmatch(rb"([A-Z]{1,16}) ([!-~]{1,2048}) HTTP/1\.1", request)
    if not separator or len(request) + 2 > _REQUEST_LIMIT or match is None:
        raise _RejectedHead(400)
    if match.group(2).startswith(b"//"):
        raise _RejectedHead(400)
    if len(headers) > MAX_HEADER_BYTES or not headers.endswith(b"\r\n\r\n"):
        raise _RejectedHead(431)
    values = {}
    for line in headers[:-4].split(b"\r\n") if headers[:-4] else ():
        if (len(line) + 2 > MAX_HEADER_LINE
                or re.match(rb"[!#$%&'*+\-.^_`|~0-9A-Za-z]+:", line) is None
                or any(byte < 32 and byte != 9 or byte >= 127 for byte in line)):
            raise _RejectedHead(431)
        name, _, value = line.partition(b":")
        name = name.lower().decode("ascii")
        if name in values or name not in _ALLOWED_HEADERS or len(values) >= 16:
            raise _RejectedHead(400)
        values[name] = value.lstrip(b" \t").decode("ascii")
    return match.group(1), match.group(2), values


class _Lease:
    """One release shared by failed TLS startup and connection_lost."""
    def __init__(self, service):
        self.service, self.released = service, False

    def release(self):
        if not self.released:
            self.released = True
            self.service._connection_count -= 1


class _Work:
    def __init__(self, limit):
        self.limit, self.active = limit, 0
        self.lock = threading.Lock()
        self.pool = ThreadPoolExecutor(max_workers=limit, thread_name_prefix="credential-private")

    def submit(self, execute, *args):
        # ThreadPoolExecutor itself has an unbounded queue. This limit includes
        # every submitted future until the underlying work actually finishes.
        with self.lock:
            if self.active >= self.limit:
                raise OnboardingRejected("unavailable")
            self.active += 1
        try:
            future = self.pool.submit(execute, *args)
        except Exception:
            self._release(None)
            raise OnboardingRejected("unavailable") from None
        future.add_done_callback(self._release)
        return future

    def _release(self, _):
        with self.lock:
            self.active -= 1

    def close(self):
        # Running database work may already have committed. Do not cancel,
        # retry or manufacture a failed audit because its client disappeared.
        self.pool.shutdown(wait=False, cancel_futures=False)


def _consume_future(future):
    try:
        future.exception()
    except BaseException:
        pass


class _Application:
    def __init__(self, protocol):
        self.protocol = protocol

    async def __call__(self, scope, receive, send):
        protocol, service = self.protocol, self.protocol.service
        # The authoritative scope is made by this authenticated protocol.
        # HTTPS strings or caller-supplied scope markers cannot establish mTLS.
        if (not protocol.authenticated or scope is not protocol.scope
                or scope.get("type") != "http" or scope.get("scheme") != "https"):
            await self._reply(send, 403, {"error": "access_denied"})
            return
        if protocol.dispatched:
            protocol.transport.abort()
            return
        protocol.dispatched = True
        app = service.application
        if not app.enabled:
            await self._reply(send, 404, {"error": "invalid_request"})
            return
        target = protocol.raw_target
        action = next((name for name, path in TARGETS.items() if path.encode("ascii") == target), None)
        if action is None:
            await self._reply(send, 404, {"error": "invalid_request"})
            return
        if protocol.raw_method != b"POST":
            await self._reply(send, 405, {"error": "invalid_request"})
            return
        try:
            if (scope.get("http_version") != "1.1"
                    or scope.get("raw_path") != target or scope.get("query_string") != b""
                    or scope.get("method") != "POST"):
                raise OnboardingRejected("invalid_request")
            headers = protocol.raw_headers
            host = headers.get("host")
            if (type(host) is not str or not 1 <= len(host) <= 255
                    or re.fullmatch(r"[a-zA-Z0-9.-]+(?::[0-9]{1,5})?", host) is None
                    or headers.get("content-type") != "application/json"
                    or headers.get("connection", "close").lower() != "close"
                    or headers.get("accept", "application/json") != "application/json"):
                raise OnboardingRejected("invalid_request")
            length = headers.get("content-length")
            if type(length) is not str or re.fullmatch(r"[1-9][0-9]{0,3}", length) is None:
                raise OnboardingRejected("invalid_request")
            size = int(length)
            if size > MAX_BODY_BYTES:
                await self._reply(send, 413, {"error": "invalid_request"})
                return
            token = headers.get("authorization")
            if (type(token) is not str or len(token) > 8199
                    or re.fullmatch(r"Bearer [A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", token) is None):
                raise OnboardingRejected("authentication_required")
            context = parse_request_context(headers.get(CONTEXT_HEADER.lower()), app.context)
            body = bytearray()
            while True:
                event = await receive()
                if event.get("type") == "http.disconnect":
                    return
                if (event.get("type") != "http.request" or type(event.get("body")) is not bytes
                        or type(event.get("more_body")) is not bool):
                    raise OnboardingRejected("invalid_request")
                body.extend(event["body"])
                if len(body) > size:
                    raise OnboardingRejected("invalid_request")
                if not event["more_body"]:
                    break
            if len(body) != size:
                raise OnboardingRejected("invalid_request")
            if protocol.closed or protocol.transport.is_closing():
                return
            future = service.work.submit(app.execute, context, action, token[7:], bytes(body))
            awaited = asyncio.wrap_future(future)
            awaited.add_done_callback(_consume_future)
            result = await asyncio.shield(awaited)
            await self._reply(send, 200, _public_result(result, action))
        except asyncio.CancelledError:
            raise
        except OnboardingRejected as error:
            code = error.code if type(error.code) is str and error.code in OnboardingRejected.CODES else "unavailable"
            await self._reply(send, _ERROR_STATUS.get(code, 400), {"error": code})
        except Exception:
            await self._reply(send, 503, {"error": "unavailable"})

    @staticmethod
    async def _reply(send, status, value):
        try:
            body = _json(value)
            await send({
                "type": "http.response.start", "status": status,
                "headers": [
                    (b"Content-Type", b"application/json"),
                    (b"Content-Length", str(len(body)).encode("ascii")),
                    (b"Cache-Control", b"no-store"), (b"Connection", b"close"),
                ],
            })
            await send({"type": "http.response.body", "body": body, "more_body": False})
        except Exception:
            pass


class _Protocol(H11Protocol):
    def __init__(self, service, lease, deadline):
        super().__init__(service.config, service.state, {}, _loop=service.loop)
        self.service, self.lease, self.deadline = service, lease, deadline
        self.logger = self.access_logger = _QUIET
        self.access_log = False
        self.app = _Application(self)
        self.authenticated = self.dispatched = self.closed = False
        self.header = bytearray()
        self.raw_method = self.raw_target = None
        self.raw_headers = None
        self.remaining = 0
        self.timer = None

    def connection_made(self, transport):
        self.transport = transport
        try:
            peer = transport.get_extra_info("ssl_object")
            certificate = peer.getpeercert(binary_form=True) if peer is not None else None
            if not certificate:
                raise ValueError()
            digest = hashlib.sha256(certificate).hexdigest()
            if not any(hmac.compare_digest(digest, pin) for pin in self.service.pins):
                raise ValueError()
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise ValueError()
            self.authenticated = True
            super().connection_made(transport)
            self.timer = self.loop.call_later(remaining, transport.abort)
        except Exception:
            self.closed = True
            transport.abort()

    def data_received(self, data):
        if self.closed or not self.authenticated:
            return
        try:
            if self.raw_headers is None:
                # Never buffer an unbounded TLS read merely to locate headers.
                take = min(len(data), _HEAD_LIMIT + 1 - len(self.header))
                self.header.extend(data[:take])
                end = self.header.find(b"\r\n\r\n")
                line_end = self.header.find(b"\r\n")
                if end < 0:
                    if line_end < 0 and len(self.header) > _REQUEST_LIMIT:
                        raise _RejectedHead(400)
                    if (len(self.header) > _HEAD_LIMIT
                            or line_end >= 0 and len(self.header) - line_end - 2 > MAX_HEADER_BYTES):
                        raise _RejectedHead(431)
                    return
                end += 4
                raw_head = bytes(self.header[:end])
                self.raw_method, self.raw_target, self.raw_headers = _head(raw_head)
                length = self.raw_headers.get("content-length", "")
                self.remaining = (int(length) if re.fullmatch(r"[1-9][0-9]{0,3}", length)
                                  and int(length) <= MAX_BODY_BYTES else 0)
                tail = bytes(self.header[end:]) + data[take:take + self.remaining]
                tail = tail[:self.remaining]
                self.remaining -= len(tail)
                self.header.clear()
                super().data_received(raw_head + tail)
            elif self.remaining:
                fragment = data[:self.remaining]
                self.remaining -= len(fragment)
                super().data_received(fragment)
            # Bytes after the single Content-Length body are never fed back
            # to h11, which otherwise supports a pipelined second request.
        except _RejectedHead as error:
            self._reject(error.status)
        except Exception:
            self._reject(400)

    def _reject(self, status):
        if not self.closed:
            self.closed = True
            try:
                self.transport.write(_wire(status, {"error": "invalid_request"}))
                self.transport.close()
            except Exception:
                self.transport.abort()

    def send_400_response(self, _):
        # Uvicorn's parser error text never reaches this private wire.
        self._reject(400)

    def on_response_complete(self):
        self.server_state.total_requests += 1
        self.transport.close()

    def connection_lost(self, exc):
        self.closed = True
        if self.timer is not None:
            self.timer.cancel()
        try:
            super().connection_lost(exc)
        finally:
            self.lease.release()


class _PrivateASGIServer:
    def __init__(self, address, context, pins, application, timeout, limit):
        self.tls_context, self.pins, self.application = context, pins, application
        self.timeout, self.limit = timeout, limit
        self.work = _Work(limit)
        self.state = ServerState()
        self.loop = self.config = self.stop = None
        self._connection_count = 0
        self._closed = threading.Event()
        self._running = threading.Lock()
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind(address)
            self.socket.listen(8)
            self.socket.setblocking(False)
            self.server_address = self.socket.getsockname()
        except Exception:
            self.socket.close()
            self.work.close()
            raise

    def serve_forever(self, poll_interval=None):
        if not self._running.acquire(blocking=False):
            raise OnboardingRejected("invalid_context")
        try:
            if not self._closed.is_set():
                # Debug-mode Handle reprs can contain private data_received
                # arguments. Ambient PYTHONASYNCIODEBUG is never accepted.
                asyncio.run(self._serve(), debug=False)
        finally:
            self.server_close()
            self._running.release()

    async def _serve(self):
        self.loop = asyncio.get_running_loop()
        self.loop.set_exception_handler(lambda *_: None)
        self.stop = asyncio.Event()
        # The protocol has its own authority-bound ASGI app. This default is
        # intentionally inert and cannot act as a directly exposed endpoint.
        async def inert(scope, receive, send):
            await _Application._reply(send, 403, {"error": "access_denied"})
        self.config = Config(
            inert, interface="asgi3", http="h11", ws="none", lifespan="off", workers=1,
            log_config=None, log_level="critical", access_log=False,
            proxy_headers=False, server_header=False, date_header=False,
            timeout_keep_alive=0, h11_max_incomplete_event_size=_HEAD_LIMIT,
            ssl_context_factory=lambda *_: self.tls_context,
        )
        self.config.load()
        pending = set()
        async def establish(raw, lease, deadline):
            try:
                await self.loop.connect_accepted_socket(
                    lambda: _Protocol(self, lease, deadline), raw,
                    ssl=self.tls_context,
                    ssl_handshake_timeout=max(0.001, deadline - time.monotonic()),
                    ssl_shutdown_timeout=1,
                )
            except BaseException:
                raw.close()
                lease.release()

        async def accept():
            while True:
                # Always-ready accepts, including rejected clients, must not
                # starve connection timers, shutdown or actual-work completion.
                await asyncio.sleep(0)
                raw, _ = await self.loop.sock_accept(self.socket)
                if self._connection_count >= self.limit or self._closed.is_set():
                    raw.close()
                    continue
                self._connection_count += 1
                lease = _Lease(self)
                task = self.loop.create_task(establish(raw, lease, time.monotonic() + self.timeout))
                pending.add(task)
                task.add_done_callback(pending.discard)

        if self._closed.is_set():
            self.stop.set()
        accepter = self.loop.create_task(accept())
        try:
            await self.stop.wait()
        finally:
            accepter.cancel()
            await asyncio.gather(accepter, return_exceptions=True)
            for task in tuple(pending):
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            for connection in tuple(self.state.connections):
                connection.transport.abort()
            for task in tuple(self.state.tasks):
                task.cancel()
            await asyncio.gather(*self.state.tasks, return_exceptions=True)
            await asyncio.sleep(0)

    def shutdown(self):
        self.server_close()

    def server_close(self):
        self._closed.set()
        if self.loop is not None and self.stop is not None and not self.loop.is_closed():
            try:
                self.loop.call_soon_threadsafe(self.stop.set)
            except RuntimeError:
                pass
        self.socket.close()
        self.work.close()


def create_private_asgi_server(address, *, tls_context: ssl.SSLContext,
                               client_certificate_sha256: frozenset[str],
                               application: CredentialHTTPApplication,
                               timeout_seconds: float = 20, max_workers: int = 4):
    """Create a fixed-actor, explicit opt-in authenticated private listener."""
    try:
        if (type(application) is not CredentialHTTPApplication
                or not isinstance(tls_context, ssl.SSLContext)
                or tls_context.protocol != ssl.PROTOCOL_TLS_SERVER
                or tls_context.verify_mode != ssl.CERT_REQUIRED
                or tls_context.minimum_version < ssl.TLSVersion.TLSv1_2
                or tls_context.cert_store_stats()["x509_ca"] < 1
                or type(client_certificate_sha256) is not frozenset
                or not 1 <= len(client_certificate_sha256) <= 4
                or any(type(pin) is not str or re.fullmatch(r"[a-f0-9]{64}", pin) is None
                       for pin in client_certificate_sha256)
                or type(timeout_seconds) not in (int, float)
                or not math.isfinite(timeout_seconds) or not 1 <= timeout_seconds <= 30
                or type(max_workers) is not int or not 1 <= max_workers <= 8):
            raise ValueError()
        return _PrivateASGIServer(address, tls_context, client_certificate_sha256,
                                  application, timeout_seconds, max_workers)
    except Exception:
        raise OnboardingRejected("invalid_context") from None
