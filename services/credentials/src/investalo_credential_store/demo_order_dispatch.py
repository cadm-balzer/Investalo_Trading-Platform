"""Private Demo order core. No runtime route, launcher or automatic activation.

The trusted installer must supply durable once-only exact-order authorization
and a native account/budget guard. A credential or account report is not a grant.
"""
from dataclasses import dataclass
import hmac
import os
import ssl
import threading
import time
from urllib.error import HTTPError
from urllib.request import HTTPSHandler, ProxyHandler, Request, build_opener
from uuid import UUID

from investalo_bitget import OwnerContext, parse
from investalo_bitget.demo_trading_identity import trading_identity
from investalo_bitget.futures_demo import DemoBinding, DemoIntent, DemoRejected, DemoRequestPlan, clock
from investalo_bitget.futures_demo_market import BTCMarketIntent
from investalo_bitget.futures_demo_outbox import OutboxReceipt
from investalo_bitget.futures_demo_read import DemoReadCredential, SignedDemoReadRequest
from investalo_bitget.futures_demo_registry import RegisteredDemoOutbox
from investalo_bitget.futures_demo_reconcile import check_position
from investalo_bitget.models import AccountBinding
from investalo_bitget.signing import ORIGIN, RedactedHeaders, hmac_sha256_base64
from investalo_bitget.transport import MAX_RESPONSE_BYTES, ReadResponse, _NoRedirect

from .demo_trading_provider import DemoTradingCredentialLease, SealedDemoTradingProvider
from .models import _PrivateImmutable


class DemoOrderApproval(_PrivateImmutable):
    """Result of the injected trusted durable consumer, never browser input."""
    __slots__ = ("authorization_id", "intent", "receipt", "credential_revision",
                 "storage_version", "granted_ms", "expires_ms")

    def __init__(self, authorization_id, intent, receipt, *, credential_revision,
                 storage_version, granted_ms, expires_ms):
        if (type(authorization_id) is not UUID or type(intent) not in (DemoIntent, BTCMarketIntent)
                or type(receipt) is not OutboxReceipt or type(credential_revision) is not int
                or credential_revision != 1 or type(storage_version) is not int
                or not 1 <= storage_version < 2**63
                or not clock(granted_ms) < clock(expires_ms) <= granted_ms + 15000):
            raise DemoRejected("invalid_order_approval")
        from investalo_bitget.futures_demo import digest
        if receipt.binding_digest != digest(intent.binding.record()):
            raise DemoRejected("foreign_order_approval")
        for name, value in (("authorization_id", authorization_id), ("intent", intent),
                ("receipt", receipt), ("credential_revision", credential_revision),
                ("storage_version", storage_version), ("granted_ms", granted_ms), ("expires_ms", expires_ms)):
            object.__setattr__(self, name, value)

    def check(self, intent, receipt, now):
        if (intent != self.intent or receipt != self.receipt
                or not self.granted_ms <= clock(now) < self.expires_ms):
            raise DemoRejected("order_approval_mismatch_or_expired")


class SignedDemoOrderRequest(_PrivateImmutable):
    """Own exact order bytes; the existing read transports reject this type."""
    __slots__ = ("plan", "url", "method", "target", "body", "headers", "_lock", "_used", "_pid")

    def __init__(self, lease, intent, operation, *, timestamp_ms):
        if (type(lease) is not DemoTradingCredentialLease or type(intent) not in (DemoIntent, BTCMarketIntent)
                or lease.spec.binding != intent.binding
                or not clock(timestamp_ms) < lease.expires_ms or operation not in ("place", "detail")):
            raise DemoRejected("invalid_order_request")
        plan = DemoRequestPlan(intent, operation)
        signature = hmac_sha256_base64(lease.credentials._secret_key,
            str(timestamp_ms).encode("ascii") + plan.method.encode("ascii") + plan.target.encode("ascii") + plan.body)
        values = dict(plan=plan, url=ORIGIN + plan.target, method=plan.method, target=plan.target, body=plan.body,
            headers=RedactedHeaders({"ACCESS-KEY": lease.credentials._api_key, "ACCESS-SIGN": signature,
                "ACCESS-TIMESTAMP": str(timestamp_ms), "ACCESS-PASSPHRASE": lease.credentials._passphrase,
                "paptrading": "1", "Content-Type": "application/json", "Accept": "application/json", "locale": "en-US"}),
            _lock=threading.Lock(), _used=False, _pid=os.getpid())
        for name, value in values.items():
            object.__setattr__(self, name, value)

    def consume(self):
        with self._lock:
            expected = DemoRequestPlan(self.plan.intent, self.plan.operation)
            if (self._used or self._pid != os.getpid() or self.url != ORIGIN + expected.target
                    or self.method != expected.method or self.target != expected.target
                    or self.body != expected.body or self.headers["paptrading"] != "1"):
                raise DemoRejected("order_request_already_used_or_changed")
            object.__setattr__(self, "_used", True)  # Failed sends consume this packet too.


@dataclass(frozen=True)
class HTTPSDemoOrderTransport:
    timeout_seconds: float = 3

    def __post_init__(self):
        if type(self.timeout_seconds) not in (int, float) or not 1 <= self.timeout_seconds <= 5:
            raise DemoRejected("invalid_order_timeout")

    def __call__(self, request):
        if type(request) is not SignedDemoOrderRequest:
            raise DemoRejected("invalid_order_request")
        request.consume()
        try:
            tls = ssl.create_default_context()
            tls.minimum_version = ssl.TLSVersion.TLSv1_2
            opener = build_opener(ProxyHandler({}), HTTPSHandler(context=tls), _NoRedirect())
            outgoing = Request(request.url, data=request.body if request.method == "POST" else None,
                               headers=dict(request.headers), method=request.method)
            with opener.open(outgoing, timeout=self.timeout_seconds) as response:
                body = response.read(MAX_RESPONSE_BYTES + 1)
                if response.status != 200 or len(body) > MAX_RESPONSE_BYTES:
                    raise ValueError()
                return ReadResponse(response.status, body)
        except HTTPError as error:
            error.close()
            raise DemoRejected("demo_order_transport_unconfirmed") from None
        except Exception:
            raise DemoRejected("demo_order_transport_unconfirmed") from None


@dataclass(frozen=True, repr=False)
class DemoDispatchResult:
    command_id: UUID
    minimum_receipt: OutboxReceipt
    outcome: str  # acknowledged or outcome_unknown; never a fill or net-PnL claim.

@dataclass(frozen=True, repr=False)
class DemoObservationResult:
    command_id: UUID
    minimum_receipt: OutboxReceipt
    position_matched: bool
    costs_verified: bool = False


class DemoOrderDispatcher(_PrivateImmutable):
    """One registered writer + genuine Trading provider; off unless explicitly installed."""
    __slots__ = ("box", "provider", "read_transport", "order_transport", "native_guard",
                 "account_guard", "lock", "ip_binding", "authorize_once", "enabled", "now", "pid",
                 "_used_authorizations")
    def __init__(self, box, provider, *, read_transport, order_transport, native_guard,
                 account_guard, shared_lock, ip_binding, authorize_once=None, enabled=False,
                 milliseconds=lambda: time.time_ns() // 1_000_000):
        if (type(box) is not RegisteredDemoOutbox or type(provider) is not SealedDemoTradingProvider
                or type(enabled) is not bool or type(shared_lock) is not type(threading.Lock())
                or ip_binding not in ("single_ip", "unavailable_in_demo")
                or not all(callable(v) for v in (read_transport, order_transport, native_guard,
                    account_guard, milliseconds)) or authorize_once is not None and not callable(authorize_once)):
            raise DemoRejected("invalid_dispatch_installation")
        for name, value in (("box", box), ("provider", provider), ("read_transport", read_transport),
                ("order_transport", order_transport), ("native_guard", native_guard), ("account_guard", account_guard),
                ("lock", shared_lock), ("ip_binding", ip_binding), ("authorize_once", authorize_once),
                ("enabled", enabled), ("now", milliseconds), ("pid", os.getpid()),
                ("_used_authorizations", set())):
            object.__setattr__(self, name, value)

    def _trace(self, command_id, context, revision):
        if type(context) is not OwnerContext or type(command_id) is not UUID:
            raise DemoRejected("invalid_dispatch_scope")
        self.box.check_binding(self.provider._spec.binding, context=context, expected_revision=revision)
        traces = self.box.traces(context=context)
        found = [t for t in traces if t.intent.command_id == command_id]
        if len(found) != 1:
            raise DemoRejected("unknown_order_command")
        return found[0]

    def _lease(self, intent, context, original=None):
        self.native_guard()
        lease = self.provider(intent.binding, context)
        if original is not None and (lease.spec.record() != original.spec.record()
                or not hmac.compare_digest(hmac_sha256_base64(lease.credentials._secret_key,
                    (lease.credentials._api_key + "\0" + lease.credentials._passphrase).encode()),
                hmac_sha256_base64(original.credentials._secret_key,
                    (original.credentials._api_key + "\0" + original.credentials._passphrase).encode()))):
            raise DemoRejected("dispatch_credential_changed")
        return lease

    def _identity(self, lease, intent, context):
        spec = lease.spec
        declaration = DemoReadCredential(intent.binding, lease.credentials, spec.parent_uid,
            spec.egress_ip, spec.provisioning_digest, spec.credential_revision, lease.expires_ms)
        response = self.read_transport(SignedDemoReadRequest(
            declaration, timestamp_ms=self.now(), axis="identity"))
        _, at = parse.envelope(response)
        if not 0 <= self.now() - int(at.timestamp() * 1000) <= 5000:
            raise DemoRejected("stale_dispatch_identity")
        identity = trading_identity(response)
        bound = self.ip_binding == "single_ip"
        AccountBinding(context, intent.binding.broker_uid, spec.parent_uid,
            expected_egress_ip=spec.egress_ip if bound else None).validate(context, identity, require_ip=bound)
        if (identity.authorities != spec.authorities
                or bound and identity.ip_whitelist != (spec.egress_ip,)
                or not bound and identity.ip_whitelist not in (None, ())):
            raise DemoRejected("dispatch_native_identity_changed")

    def dispatch(self, command_id, *, context, expected_revision):
        if not self.enabled or self.authorize_once is None or os.getpid() != self.pid:
            raise DemoRejected("demo_order_dispatch_disabled")
        if not self.lock.acquire(blocking=False):
            raise DemoRejected("demo_uid_busy")
        try:
            trace = self._trace(command_id, context, expected_revision)
            if not trace.can_submit:
                raise DemoRejected("order_already_attempted")
            receipt = self.box.receipt
            self.account_guard(trace.intent, receipt, context)
            approval = self.authorize_once(trace.intent, receipt, context)
            if type(approval) is not DemoOrderApproval:
                raise DemoRejected("order_not_authorized")
            approval.check(trace.intent, receipt, self.now())
            if approval.authorization_id in self._used_authorizations or len(self._used_authorizations) >= 1024:
                raise DemoRejected("order_approval_already_consumed")
            self._used_authorizations.add(approval.authorization_id)
            lease = self._lease(trace.intent, context)
            if (lease.spec.credential_revision != approval.credential_revision
                    or self.provider._storage != approval.storage_version):
                raise DemoRejected("approved_credential_changed")
            started = self.now()
            self._identity(lease, trace.intent, context)
            self._lease(trace.intent, context, lease)
            self.account_guard(trace.intent, receipt, context)
            approval.check(trace.intent, receipt, self.now())
            attempt = self.box.begin_attempt(command_id, context=context,
                expected_revision=expected_revision, at_ms=self.now())
            try:
                self._lease(trace.intent, context, lease)
                approval.check(trace.intent, receipt, self.now())
                if not 0 <= self.now() - started <= 5000:
                    raise ValueError()
                self.box.check_binding(trace.intent.binding, context=context, expected_revision=attempt.revision)
                response = self.order_transport(SignedDemoOrderRequest(lease, trace.intent, "place", timestamp_ms=self.now()))
                self._lease(trace.intent, context, lease)
                approval.check(trace.intent, receipt, self.now())
                if not 0 <= self.now() - started <= 5000:
                    raise ValueError()
                committed = self.box.accept_ack(command_id, response, context=context,
                    expected_revision=attempt.revision, now_ms=self.now())
                return DemoDispatchResult(command_id, committed, "acknowledged")
            except Exception:
                # Keep the durable unknown prefix. An ACK may have committed
                # despite a lost fsync/readback; no failed rewrite or resend.
                return DemoDispatchResult(command_id, attempt, "outcome_unknown")
        finally:
            self.lock.release()

    def observe(self, command_id, *, context, expected_revision):
        """Read the original clientOid and positions; never rearm or send POST."""
        if not self.enabled or os.getpid() != self.pid:
            raise DemoRejected("demo_order_dispatch_disabled")
        if not self.lock.acquire(blocking=False):
            raise DemoRejected("demo_uid_busy")
        try:
            trace = self._trace(command_id, context, expected_revision)
            if trace.can_submit:
                raise DemoRejected("order_not_attempted")
            lease = self._lease(trace.intent, context)
            started = self.now()
            self._identity(lease, trace.intent, context)
            self._lease(trace.intent, context, lease)
            self.box.check_binding(trace.intent.binding, context=context, expected_revision=expected_revision)
            response = self.order_transport(SignedDemoOrderRequest(lease, trace.intent, "detail", timestamp_ms=self.now()))
            self._lease(trace.intent, context, lease)
            if not 0 <= self.now() - started <= 5000:
                raise DemoRejected("stale_order_observation")
            committed = self.box.accept_observation(command_id, response, context=context,
                expected_revision=expected_revision, now_ms=self.now())
            # A failed position check must not erase a committed native detail.
            matched = False
            try:
                current = self._trace(command_id, context, committed.revision)
                spec = lease.spec
                declaration = DemoReadCredential(trace.intent.binding, lease.credentials, spec.parent_uid,
                    spec.egress_ip, spec.provisioning_digest, spec.credential_revision, lease.expires_ms)
                self._lease(trace.intent, context, lease)
                positions = self.read_transport(SignedDemoReadRequest(
                    declaration, timestamp_ms=self.now(), axis="positions"))
                self._lease(trace.intent, context, lease)
                if not 0 <= self.now() - started <= 5000:
                    raise ValueError()
                check_position(current, positions, context=context, now_ms=self.now())
                self.box.check_binding(trace.intent.binding, context=context, expected_revision=committed.revision)
                matched = True
            except Exception:
                pass
            return DemoObservationResult(command_id, committed, matched)
        finally:
            self.lock.release()
