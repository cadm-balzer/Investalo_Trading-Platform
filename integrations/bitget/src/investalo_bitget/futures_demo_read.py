"""Explicit Classic Demo GET transport; trusted provisioning is still external."""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import os
import re
import ssl
import threading
import time
from urllib.error import HTTPError
from urllib.request import HTTPSHandler, ProxyHandler, Request, build_opener

from . import parse
from .futures_demo import DemoBinding, DemoRejected, clock, digest
from .futures_demo_account import (
    AXES, CONFIGS, AccountCheck, AccountExpectation, DemoPacket, DemoReadPlan, _frame, _pages,
)
from .futures_demo_reconcile import FRESH_MS
from .futures_demo_registry import RegisteredDemoOutbox
from .models import AccountBinding, BitgetRejected, ClassicIdentity
from .signing import Credentials, INFO_PATH, ORIGIN, RedactedHeaders, hmac_sha256_base64
from .transport import MAX_RESPONSE_BYTES, ReadResponse, _NoRedirect


@dataclass(frozen=True, repr=False)
class DemoReadCredential:
    """Trusted provider declaration, NOT a native proof of Demo key creation."""
    binding: DemoBinding
    credentials: Credentials
    expected_parent: str
    expected_egress_ip: str
    provisioning_digest: str
    revision: int
    expires_ms: int

    def __post_init__(self):
        if (not isinstance(self.binding, DemoBinding) or not isinstance(self.credentials, Credentials)
                or not isinstance(self.expected_parent, str)
                or not isinstance(self.provisioning_digest, str)
                or not re.fullmatch("[0-9a-f]{64}", self.provisioning_digest)
                or type(self.revision) is not int or self.revision < 1
                or self.revision > 10**15):
            raise DemoRejected("invalid_demo_read_credential")
        clock(self.expires_ms)
        binding = AccountBinding(self.binding.owner, self.binding.broker_uid,
                                 self.expected_parent, expected_egress_ip=self.expected_egress_ip)
        if binding.expected_egress_ip is None or binding.expected_egress_ip != self.expected_egress_ip:
            raise DemoRejected("canonical_demo_egress_required")

    def record(self):
        return {"schema": "bitget-demo-read-declaration/1", "binding": self.binding.record(),
                "parent": self.expected_parent, "egress": self.expected_egress_ip,
                "provisioning_digest": self.provisioning_digest, "revision": self.revision,
                "expires_ms": self.expires_ms}

    def fingerprint(self):
        # Private ephemeral equality check, never public or persisted.
        payload = (self.credentials._api_key + "\0" + self.credentials._passphrase).encode("utf-8")
        return hmac_sha256_base64(self.credentials._secret_key, payload)

    def __reduce_ex__(self, protocol):
        raise TypeError("Demo credentials serialization denied")


class SignedDemoReadRequest:
    """Fixed identity/14-axis targets only; no URL/order/body/mode parameters."""
    __slots__ = ("binding", "axis", "cursor", "target", "url", "method", "body", "_headers")

    def __init__(self, credential, *, timestamp_ms, axis="identity", cursor=None):
        if not isinstance(credential, DemoReadCredential):
            raise DemoRejected("invalid_demo_read_credential")
        clock(timestamp_ms)
        if not timestamp_ms < credential.expires_ms:
            raise DemoRejected("expired_demo_read_credential")
        if axis == "identity":
            if cursor is not None:
                raise DemoRejected("unexpected_cursor")
            target = INFO_PATH
        else:
            target = DemoReadPlan(credential.binding, axis, cursor).target
        timestamp = str(timestamp_ms)
        signature = hmac_sha256_base64(credential.credentials._secret_key,
                                      (timestamp + "GET" + target).encode("ascii"))
        for name, value in (("binding", credential.binding), ("axis", axis), ("cursor", cursor),
                            ("target", target), ("url", ORIGIN + target), ("method", "GET"), ("body", b"")):
            object.__setattr__(self, name, value)
        object.__setattr__(self, "_headers", RedactedHeaders({
            "ACCESS-KEY": credential.credentials._api_key, "ACCESS-SIGN": signature,
            "ACCESS-TIMESTAMP": timestamp, "ACCESS-PASSPHRASE": credential.credentials._passphrase,
            "paptrading": "1", "locale": "en-US", "Accept": "application/json",
            "Content-Type": "application/json",
        }))

    @property
    def headers(self):
        return self._headers

    def validate(self):
        if not isinstance(self.binding, DemoBinding):
            raise DemoRejected("invalid_demo_read_request")
        expected = INFO_PATH if self.axis == "identity" and self.cursor is None else (
            DemoReadPlan(self.binding, self.axis, self.cursor).target)
        if (self.target != expected or self.url != ORIGIN + expected or self.method != "GET"
                or self.body != b"" or self.headers.get("paptrading") != "1"):
            raise DemoRejected("invalid_demo_read_request")

    def __setattr__(self, name, value):
        raise AttributeError("Signed Demo requests are immutable")

    def __repr__(self):
        return "SignedDemoReadRequest(<redacted>)"

    def __reduce_ex__(self, protocol):
        raise TypeError("Signed Demo request serialization denied")


@dataclass(frozen=True)
class HTTPSDemoReadTransport:
    timeout_seconds: float = 5
    diagnostic: object = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        if (type(self.timeout_seconds) not in (int, float)
                or not 1 <= self.timeout_seconds <= 5
                or self.diagnostic is not None and not callable(self.diagnostic)):
            raise DemoRejected("invalid_demo_read_timeout")

    def _observe(self, status, body):
        """Opt-in numeric metadata only; never broker messages/identity/keys."""
        if self.diagnostic is None:
            return
        code = None
        try:
            if type(body) is bytes and len(body) <= MAX_RESPONSE_BYTES:
                value = json.loads(body)
                candidate = value.get("code") if type(value) is dict else None
                if type(candidate) is str and re.fullmatch("[0-9]{5}", candidate):
                    code = candidate
        except Exception:
            pass
        try:
            self.diagnostic(status if type(status) is int and 100 <= status <= 599 else None, code)
        except Exception:
            pass  # Diagnostics never change authorization or trigger a retry.

    def __call__(self, request):
        if type(request) is not SignedDemoReadRequest:
            raise DemoRejected("invalid_demo_read_request")
        request.validate()
        try:
            context = ssl.create_default_context()
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            opener = build_opener(ProxyHandler({}), HTTPSHandler(context=context), _NoRedirect())
            outgoing = Request(request.url, headers=dict(request.headers), method="GET")
            with opener.open(outgoing, timeout=self.timeout_seconds) as response:
                body = response.read(MAX_RESPONSE_BYTES + 1)
                if len(body) > MAX_RESPONSE_BYTES:
                    raise DemoRejected("demo_read_response_too_large")
                self._observe(response.status, body)
                if response.status != 200:
                    raise DemoRejected("demo_read_http_failure")
                return ReadResponse(response.status, body)
        except HTTPError as error:
            if self.diagnostic is not None:
                try:
                    self._observe(error.code, error.read(MAX_RESPONSE_BYTES + 1))
                except Exception:
                    self._observe(error.code, b"")
            try:
                error.close()
            except Exception:
                pass
            raise DemoRejected("demo_read_http_failure") from None
        except (DemoRejected, BitgetRejected):
            raise
        except Exception:
            raise DemoRejected("demo_read_transport_failure") from None


@dataclass(frozen=True, repr=False)
class DemoReadResult:
    account: AccountCheck
    identity: ClassicIdentity
    identity_response_sha256: str
    provisioning_declaration_digest: str
    credential_revision: int
    native_acceptance_verified: bool = field(default=False, init=False)


class DemoReadClient:
    """Explicit injected provisioning provider and transport; no service activation."""
    def __init__(self, *, provider, transport, milliseconds=lambda: time.time_ns() // 1_000_000):
        if not callable(provider) or not callable(transport) or not callable(milliseconds):
            raise DemoRejected("invalid_demo_read_client")
        self._provider, self._transport, self._milliseconds = provider, transport, milliseconds
        self._mutex, self._pid, self._last_started = threading.Lock(), os.getpid(), None

    def _credential(self, binding, context, now_ms):
        try:
            value = self._provider(binding, context)
        except Exception:
            raise DemoRejected("demo_read_provider_unavailable") from None
        if (not isinstance(value, DemoReadCredential) or value.binding != binding
                or not now_ms < value.expires_ms <= now_ms + 60_000):
            raise DemoRejected("demo_read_provisioning_mismatch")
        return value

    def capture(self, box, expectation, *, context, expected_revision):
        if (os.getpid() != self._pid or type(box) is not RegisteredDemoOutbox
                or not isinstance(expectation, AccountExpectation)):
            raise DemoRejected("registered_demo_read_required")
        binding = expectation.binding
        binding.check(context)
        with self._mutex:
            original = box.check_binding(binding, context=context, expected_revision=expected_revision)
            start = clock(self._milliseconds())
            if self._last_started is not None and start - self._last_started < 1000:
                raise DemoRejected("demo_read_rate_limited")
            credential = self._credential(binding, context, start)
            declared, key = credential.record(), credential.fingerprint()
            self._last_started = start
            latest = start

            def guard():
                nonlocal latest
                now = clock(self._milliseconds())
                if not latest <= now <= start + FRESH_MS:
                    raise DemoRejected("demo_read_cohort_expired")
                latest = now
                current = self._credential(binding, context, now)
                if current.record() != declared or current.fingerprint() != key:
                    raise DemoRejected("demo_read_credential_changed")
                if box.check_binding(binding, context=context, expected_revision=expected_revision) != original:
                    raise DemoRejected("demo_read_outbox_changed")
                # Provider/catalog IO can consume the remaining cohort deadline.
                after = clock(self._milliseconds())
                if not now <= after <= start + FRESH_MS:
                    raise DemoRejected("demo_read_cohort_expired")
                latest = after
                return after

            def get(axis, cursor=None):
                now = guard()
                request = SignedDemoReadRequest(credential, timestamp_ms=now, axis=axis, cursor=cursor)
                try:
                    response = self._transport(request)
                except (BitgetRejected, DemoRejected):
                    raise
                except Exception:
                    raise DemoRejected("demo_read_transport_failure") from None
                at = guard()
                raw, native_time = parse.envelope(response)
                delta = native_time - parse.EPOCH
                millis = delta.days * 86_400_000 + delta.seconds * 1000 + delta.microseconds // 1000
                if not 0 <= at - millis <= FRESH_MS:
                    raise DemoRejected("stale_demo_read_response")
                return response, raw, at

            response, _, _ = get("identity")
            identity_hash = hashlib.sha256(response.body).hexdigest()
            info = parse.identity(response)  # Existing Classic read-only authority vocabulary.
            AccountBinding(binding.owner, binding.broker_uid, credential.expected_parent,
                           expected_egress_ip=credential.expected_egress_ip).validate(context, info, require_ip=True)
            if (info.ip_whitelist != (credential.expected_egress_ip,)
                    or not {"coor", "cpor"}.issubset(info.authorities)):
                raise DemoRejected("demo_read_identity_gate")
            packets = []
            for axis in (*AXES, *CONFIGS):
                pages, cursor = [], None
                for _ in range(1 if axis in ("wallet", "positions", *CONFIGS) else 10):
                    response, raw, at = get(axis, cursor)
                    packet = DemoPacket(DemoReadPlan(binding, axis, cursor), response)
                    _frame(packet, binding, context, at)
                    pages.append(packet)
                    if axis in ("wallet", "positions", *CONFIGS):
                        break
                    _, complete = _pages(tuple(pages), axis, binding, context, at)
                    if complete or raw["endId"] in (None, ""):
                        break
                    cursor = raw["endId"]
                packets.extend(pages)
            now = guard()
            # Identity must still be fresh when the complete report is published.
            delta = info.server_time - parse.EPOCH
            info_ms = delta.days * 86_400_000 + delta.seconds * 1000 + delta.microseconds // 1000
            if not 0 <= now - info_ms <= FRESH_MS:
                raise DemoRejected("stale_demo_read_identity")
            result = box.check_account(expectation, tuple(packets), context=context,
                                       expected_revision=expected_revision, now_ms=now)
            # No raw reply cache/persistence and no economic or dispatch mutation.
            return DemoReadResult(result, info, identity_hash, digest(declared), credential.revision)

    def __repr__(self):
        return "DemoReadClient(<private>)"
