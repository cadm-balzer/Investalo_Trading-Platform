"""Disabled own Basket Journal → Trading AEAD → native Market/GET bridge.

Trusted installer must provide independent native account/admission guards,
durable own Basket authorization consumption and reconciled margin evidence.
No strategy issuer, launcher, Dashboard route or automatic activation here.
"""
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
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
from investalo_bitget.futures_demo import DemoRejected, clock
from investalo_bitget.futures_demo_basket import (
    BasketMarketGrid, BasketMarketIntent, BasketRequestPlan, basket_ack,
    basket_order_detail, basket_position_match,
)
from investalo_bitget.futures_demo_read import DemoReadCredential, SignedDemoReadRequest, HTTPSDemoReadTransport
from investalo_bitget.models import AccountBinding
from investalo_bitget.signing import ORIGIN, RedactedHeaders, hmac_sha256_base64
from investalo_bitget.transport import MAX_RESPONSE_BYTES, ReadResponse, _NoRedirect
from investalo_trading.capital_digest import digest
from investalo_trading.futures_broker_entries import BrokerEntryObservation
from investalo_trading.futures_broker_journal import (
    BrokerEntryJournal, BrokerSubmissionUnknown, VERSION as JOURNAL_VERSION,
)
from investalo_trading.futures_replay_journal import _fields, _sha

from .demo_trading_provider import DemoTradingCredentialLease, SealedDemoTradingProvider
from .models import _PrivateImmutable

PURPOSE = "bitget-demo-h1-basket-entry/1"


def milliseconds(at):
    delta = at - parse.EPOCH
    return delta.days * 86400000 + delta.seconds * 1000 + delta.microseconds // 1000


class BasketOrderApproval(_PrivateImmutable):
    """Only the installed durable own-purpose consumer supplies this result."""
    __slots__ = ("authorization_id", "intent_digest", "receipt_digest", "request_digest",
                 "credential_revision", "storage_version", "granted_ms", "expires_ms")

    def __init__(self, authorization_id, intent, receipt, *, credential_revision,
                 storage_version, granted_ms, expires_ms):
        _fields(receipt, ("schema_version", "context_digest", "sequence", "head",
                          "state_digest", "execution_enabled"))
        for key in ("context_digest", "head", "state_digest"):
            _sha(receipt[key])
        if (type(authorization_id) is not UUID or type(intent) is not BasketMarketIntent
                or receipt["schema_version"] != JOURNAL_VERSION or receipt["execution_enabled"] is not False
                or type(credential_revision) is not int or credential_revision != 1
                or type(storage_version) is not int or not 1 <= storage_version < 2**63
                or not clock(granted_ms) < clock(expires_ms) <= granted_ms + 15000):
            raise DemoRejected("invalid_basket_order_approval")
        values = dict(authorization_id=authorization_id, intent_digest=intent.intent_digest,
                      receipt_digest=digest(receipt), request_digest=BasketRequestPlan(intent, "place").request_digest,
                      credential_revision=credential_revision, storage_version=storage_version,
                      granted_ms=granted_ms, expires_ms=expires_ms)
        for name, value in values.items():
            object.__setattr__(self, name, value)

    @property
    def authorization_digest(self):
        return digest((PURPOSE, tuple(getattr(self, name) for name in self.__slots__
                      if name != "authorization_id"), str(self.authorization_id)))

    def check(self, intent, receipt, now_ms):
        if (intent.intent_digest != self.intent_digest or digest(receipt) != self.receipt_digest
                or BasketRequestPlan(intent, "place").request_digest != self.request_digest
                or not self.granted_ms <= clock(now_ms) < self.expires_ms):
            raise DemoRejected("basket_order_approval_changed_or_expired")


class SignedBasketRequest(_PrivateImmutable):
    __slots__ = ("plan", "url", "method", "target", "body", "headers", "_lock", "_used", "_pid")

    def __init__(self, lease, intent, operation, *, timestamp_ms, **window):
        if (type(lease) is not DemoTradingCredentialLease or type(intent) is not BasketMarketIntent
                or lease.spec.binding != intent.binding or not clock(timestamp_ms) < lease.expires_ms):
            raise DemoRejected("own_basket_lease_and_intent_required")
        plan = BasketRequestPlan(intent, operation, **window)
        signature = hmac_sha256_base64(lease.credentials._secret_key,
            str(timestamp_ms).encode() + plan.method.encode() + plan.target.encode() + plan.body)
        values = dict(plan=plan, url=ORIGIN + plan.target, method=plan.method, target=plan.target, body=plan.body,
            headers=RedactedHeaders({"ACCESS-KEY": lease.credentials._api_key, "ACCESS-SIGN": signature,
                "ACCESS-TIMESTAMP": str(timestamp_ms), "ACCESS-PASSPHRASE": lease.credentials._passphrase,
                "paptrading": "1", "Content-Type": "application/json", "Accept": "application/json"}),
            _lock=threading.Lock(), _used=False, _pid=os.getpid())
        for name, value in values.items():
            object.__setattr__(self, name, value)

    def consume(self):
        if self._pid != os.getpid():
            raise DemoRejected("fork_inherited_basket_packet")
        with self._lock:
            expected = BasketRequestPlan(self.plan.intent, self.plan.operation, self.plan.start_ms,
                                         self.plan.end_ms, self.plan.cursor)
            if (self._used or self.url != ORIGIN + expected.target or self.method != expected.method
                    or self.target != expected.target or self.body != expected.body
                    or self.headers["paptrading"] != "1"):
                raise DemoRejected("basket_packet_already_used_or_changed")
            object.__setattr__(self, "_used", True)


@dataclass(frozen=True)
class HTTPSBasketTransport:
    timeout_seconds: float = 3

    def __post_init__(self):
        if type(self.timeout_seconds) not in (float, int) or not 1 <= self.timeout_seconds <= 5:
            raise DemoRejected("invalid_basket_timeout")

    def __call__(self, request):
        if type(request) is not SignedBasketRequest:
            raise DemoRejected("own_signed_basket_packet_required")
        request.consume()
        try:
            tls = ssl.create_default_context()
            tls.minimum_version = ssl.TLSVersion.TLSv1_2
            opener = build_opener(ProxyHandler({}), HTTPSHandler(context=tls), _NoRedirect())
            packet = Request(request.url, data=request.body if request.method == "POST" else None,
                             headers=dict(request.headers), method=request.method)
            with opener.open(packet, timeout=self.timeout_seconds) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
                if response.status != 200 or len(raw) > MAX_RESPONSE_BYTES:
                    raise ValueError()
                return ReadResponse(response.status, raw)
        except HTTPError as error:
            error.close()
            raise DemoRejected("basket_transport_unconfirmed") from None
        except Exception:
            raise DemoRejected("basket_transport_unconfirmed") from None


@dataclass(frozen=True)
class HTTPSBasketReadTransport:
    """Fixed GET multiplexer: old identity GET or own order/positions GET."""
    timeout_seconds: float = 3

    def __call__(self, request):
        if type(request) is SignedDemoReadRequest:
            return HTTPSDemoReadTransport(timeout_seconds=self.timeout_seconds)(request)
        if type(request) is SignedBasketRequest and request.plan.operation in ("detail", "positions", "wallet", "bills"):
            return HTTPSBasketTransport(self.timeout_seconds)(request)
        raise DemoRejected("basket_read_transport_get_only")


@dataclass(frozen=True, repr=False)
class BasketMarginEvidence:
    """Trusted native reconciliation result; no qty×price or marginSize inference."""
    order_digest: str
    source_digest: str
    filled_quantity: Decimal
    posted_margin: Decimal
    observed_ms: int

    def __post_init__(self):
        from investalo_bitget.futures_demo import number
        _sha(self.order_digest); _sha(self.source_digest)
        number(self.filled_quantity, zero=True)
        number(self.posted_margin, zero=True)
        clock(self.observed_ms)


class BasketOrderDispatcher(_PrivateImmutable):
    __slots__ = ("journal", "provider", "read_transport", "order_transport", "native_guard",
                 "account_guard", "authorize_once", "margin_resolver", "margin_source",
                 "enabled", "lock", "ip_binding", "now", "pid")

    def __init__(self, journal, provider, *, read_transport, order_transport, native_guard,
                 account_guard, shared_lock, ip_binding, authorize_once=None, margin_resolver=None,
                 margin_source=None, enabled=False, milliseconds=lambda: time.time_ns() // 1_000_000):
        from .demo_basket_margin import BasketNativeMarginSource
        if (type(journal) is not BrokerEntryJournal or type(provider) is not SealedDemoTradingProvider
                or type(enabled) is not bool or type(shared_lock) is not type(threading.Lock())
                or ip_binding not in ("single_ip", "unavailable_in_demo")
                or not all(callable(p) for p in (read_transport, order_transport, native_guard, account_guard, milliseconds))
                or authorize_once is not None and not callable(authorize_once)
                or margin_resolver is not None and not callable(margin_resolver)
                or margin_source is not None and type(margin_source) is not BasketNativeMarginSource
                or margin_source is not None and margin_resolver is not None):
            raise DemoRejected("invalid_basket_dispatch_installation")
        for name, value in dict(journal=journal, provider=provider, read_transport=read_transport,
                order_transport=order_transport, native_guard=native_guard, account_guard=account_guard,
                lock=shared_lock, ip_binding=ip_binding, authorize_once=authorize_once,
                margin_resolver=margin_resolver, margin_source=margin_source,
                enabled=enabled, now=milliseconds, pid=os.getpid()).items():
            object.__setattr__(self, name, value)

    def _intent(self, state, context):
        binding = self.provider._spec.binding
        binding.check(context)
        order = state.book.pending
        if (type(context) is not OwnerContext or order is None
                or (order.request.tenant_id, order.request.account_id) != (
                    str(binding.owner.tenant_id), str(binding.account_id))):
            raise DemoRejected("foreign_basket_journal")
        plan = state.book.signal.profile.plan
        index = plan.symbols.index(order.request.symbol)
        rules = getattr(plan, "grid_rules", ())
        if len(rules) != len(plan.symbols):
            raise DemoRejected("basket_requires_confirmed_native_market_grid")
        contract, rule = plan.contracts[index], rules[index]
        grid = BasketMarketGrid(contract.symbol, contract.quantity_step, rule.price_tick, contract.minimum_quantity,
                                contract.minimum_notional, rule.maximum_market_quantity)
        return BasketMarketIntent(binding, UUID(self.journal._header["journal_id"]), order.command_id,
            order.order_digest, grid, order.assessment.capital.stage, order.cycle, order.request.quantity,
            order.request.maximum_fill_price, order.request.posted_margin, order.before_quantity,
            order.before_average, milliseconds(order.prepared_at))

    def _lease(self, intent, context, original=None):
        self.native_guard()
        lease = self.provider(intent.binding, context)
        if original is not None and (lease.spec.record() != original.spec.record()
                or not hmac.compare_digest(hmac_sha256_base64(lease.credentials._secret_key,
                    (lease.credentials._api_key + "\0" + lease.credentials._passphrase).encode()),
                hmac_sha256_base64(original.credentials._secret_key,
                    (original.credentials._api_key + "\0" + original.credentials._passphrase).encode()))):
            raise DemoRejected("basket_credential_changed")
        return lease

    def _identity(self, lease, intent, context):
        spec = lease.spec
        declaration = DemoReadCredential(intent.binding, lease.credentials, spec.parent_uid,
            spec.egress_ip, spec.provisioning_digest, spec.credential_revision, lease.expires_ms)
        response = self.read_transport(SignedDemoReadRequest(
            declaration, timestamp_ms=self.now(), axis="identity"))
        _, at = parse.envelope(response)
        if not 0 <= self.now() - milliseconds(at) <= 5000:
            raise DemoRejected("stale_basket_identity")
        identity = trading_identity(response)
        bound = self.ip_binding == "single_ip"
        AccountBinding(context, intent.binding.broker_uid, spec.parent_uid,
            expected_egress_ip=spec.egress_ip if bound else None).validate(context, identity, require_ip=bound)
        if (identity.authorities != spec.authorities or bound and identity.ip_whitelist != (spec.egress_ip,)
                or not bound and identity.ip_whitelist not in (None, ())):
            raise DemoRejected("basket_native_identity_changed")

    def _scope(self, context, revision):
        if not self.enabled or self.pid != os.getpid():
            raise DemoRejected("basket_dispatch_disabled")
        state, receipt = self.journal.checkpoint()
        if state.revision != revision:
            raise DemoRejected("stale_basket_dispatch_revision")
        return state, receipt, self._intent(state, context)

    def dispatch(self, *, context, expected_revision):
        if self.authorize_once is None:
            raise DemoRejected("basket_order_consumer_missing")
        if not self.lock.acquire(blocking=False):
            raise DemoRejected("demo_uid_busy")
        try:
            state, receipt, intent = self._scope(context, expected_revision)
            if state.current_attempt is not None:
                raise DemoRejected("basket_resend_denied")
            self.native_guard()
            self.account_guard(intent, receipt, context)  # Complete native admission, including unresolved max/costs.
            approval = self.authorize_once(intent, receipt, context)
            if type(approval) is not BasketOrderApproval:
                raise DemoRejected("own_basket_order_approval_required")
            approval.check(intent, receipt, self.now())
            lease = self._lease(intent, context)
            if (lease.spec.credential_revision != approval.credential_revision
                    or self.provider._storage != approval.storage_version):
                raise DemoRejected("approved_basket_credential_changed")
            started = self.now()
            self._identity(lease, intent, context)
            self._lease(intent, context, lease)
            self.account_guard(intent, receipt, context)
            baseline = None
            if self.margin_source is not None:
                expected = tuple((b.symbol, b.quantity, b.average_entry, rule.price_tick)
                    for b, rule in zip(state.book.signal.economic.ledger.baskets,
                                       state.book.signal.profile.plan.grid_rules, strict=True))
                baseline = self.margin_source.capture(lease, intent, context=context,
                    expected_positions=expected, guard=lambda: self._lease(intent, context, lease))
                self._lease(intent, context, lease)
            approval.check(intent, receipt, self.now())

            def send(order, marker):
                self._lease(intent, context, lease)
                approval.check(intent, receipt, self.now())
                packet = SignedBasketRequest(lease, intent, "place", timestamp_ms=self.now())
                if marker.request_digest != packet.plan.request_digest or not 0 <= self.now() - started <= 5000:
                    raise DemoRejected("basket_source_or_request_changed")
                response = self.order_transport(packet)
                self._lease(intent, context, lease)
                approval.check(intent, receipt, self.now())
                if not 0 <= self.now() - started <= 5000:
                    raise DemoRejected("basket_dispatch_cohort_expired")
                basket_ack(response, intent, context=context, now_ms=self.now())
                return "acknowledged"
            try:
                return self.journal.invoke_once(send, expected_revision=expected_revision,
                    at=parse.EPOCH + timedelta(milliseconds=self.now()), order_digest=intent.order_digest,
                    authorization_digest=approval.authorization_digest, request_digest=approval.request_digest,
                    margin_baseline=baseline)
            except BrokerSubmissionUnknown:
                return "outcome_unknown"
        finally:
            self.lock.release()

    def observe(self, *, context, expected_revision):
        if not self.lock.acquire(blocking=False):
            raise DemoRejected("demo_uid_busy")
        try:
            state, receipt, intent = self._scope(context, expected_revision)
            if state.current_attempt is None:
                raise DemoRejected("basket_original_attempt_required")
            if state.current_attempt.request_digest != BasketRequestPlan(intent, "place").request_digest:
                raise DemoRejected("basket_original_request_changed")
            started = self.now()
            lease = self._lease(intent, context)
            self._identity(lease, intent, context)
            self._lease(intent, context, lease)
            response = self.read_transport(SignedBasketRequest(lease, intent, "detail", timestamp_ms=self.now()))
            self._lease(intent, context, lease)
            observation = basket_order_detail(response, intent, context=context, now_ms=self.now(),
                attempted_ms=milliseconds(state.current_attempt.attempted_at))
            positions = self.read_transport(SignedBasketRequest(lease, intent, "positions", timestamp_ms=self.now()))
            self._lease(intent, context, lease)
            expected = tuple((b.symbol, b.quantity, b.average_entry, rule.price_tick)
                for b, rule in zip(state.book.signal.economic.ledger.baskets,
                                   state.book.signal.profile.plan.grid_rules, strict=True))
            matched = False
            try:
                matched = basket_position_match(positions, intent, observation, context=context,
                                                now_ms=self.now(), expected_positions=expected)
            except DemoRejected:
                pass
            margin = None
            evidence = None
            if matched and (self.margin_resolver is not None or self.margin_source is not None):
                if self.margin_source is not None:
                    evidence = self.margin_source.resolve(lease, intent, observation, positions,
                        baseline=state.current_attempt.margin_baseline, context=context,
                        expected_positions=expected, attempted_ms=milliseconds(state.current_attempt.attempted_at),
                        guard=lambda: self._lease(intent, context, lease))
                else:
                    evidence = self.margin_resolver(intent, observation, positions, context)
                if evidence is not None:
                    if (type(evidence) is not BasketMarginEvidence or evidence.order_digest != intent.order_digest
                            or evidence.filled_quantity != observation.quantity
                            or not 0 <= self.now() - evidence.observed_ms <= 5000
                            or not milliseconds(state.current_attempt.attempted_at) <= evidence.observed_ms):
                        raise DemoRejected("invalid_basket_margin_evidence")
                    margin = evidence.posted_margin
            self._lease(intent, context, lease)
            if not 0 <= self.now() - started <= 5000:
                raise DemoRejected("basket_observation_cohort_expired")
            proof = BrokerEntryObservation(intent.order_digest, observation.state, observation.quantity,
                observation.average_price, observation.reported_fee, margin, matched,
                parse.EPOCH + timedelta(milliseconds=observation.response_ms),
                digest((PURPOSE, intent.intent_digest, observation, evidence)),
                digest((PURPOSE, observation.order_id, observation.created_ms)), observation.updated_ms)
            if proof == state.book.observation:
                return state  # Identical poll does not rewrite evidence or renew a source clock.
            return self.journal.append("observe", expected_revision=expected_revision,
                at=parse.EPOCH + timedelta(milliseconds=self.now()), observation=proof)
        finally:
            self.lock.release()
