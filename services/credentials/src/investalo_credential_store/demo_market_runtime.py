"""Explicit single BTC Demo Market test over original BFF context and durable state."""
import hashlib
import hmac
import os
import threading
import time
from pathlib import Path
from uuid import UUID, uuid4

from investalo_bitget import OwnerContext
from investalo_bitget.futures_demo import DemoBinding, DemoRejected, text
from investalo_bitget.futures_demo_market import CONFIRMATION, BTCMarketIntent
from investalo_bitget.futures_demo_outbox import OutboxReceipt, decode, encode, exact
from investalo_bitget.futures_demo_registry import RegisteredDemoOutbox, _directory, _file, _identity, _named
from investalo_credentials import dump_envelope
from .demo_account_sync import CONTEXT, FIELDS, TARGET_FIELDS
from .demo_store import DemoStoreAuthority
from .demo_trading_store import DemoTradingCredentialStore
from .demo_order_consent import BODY, DemoBTCMarketConsentVerifier, DemoBTCTestConsentIssuer
from .demo_order_consumer import DurableDemoOrderConsumer
from .demo_order_dispatch import DemoOrderDispatcher, HTTPSDemoOrderTransport
from .demo_market_test_check import check_btc_market_test
from .passkey_request_assertion import PasskeyRequestContext, _decode, _json
from .request_assertion import OnboardingRejected

ROOT = "/var/lib/investalo-demo-market-test"
TARGETS = {
    "market_prepare": "/v1/bitget-demo-trading/market-order-prepare",
    "market_submit": "/v1/bitget-demo-trading/market-order-submit",
    "market_observe": "/v1/bitget-demo-trading/market-order-observe",
}
DOMAINS = {
    "market_prepare": ("investalo-demo-btc-market-prepare/1", "investalo-demo-btc-market-prepare"),
    "market_submit": ("investalo-demo-btc-market-order-consent/1", "investalo-demo-btc-market-order"),
    "market_observe": ("investalo-demo-btc-market-observe/1", "investalo-demo-btc-market-observe"),
}


class MarketTestState:
    """One original private root. Partial bootstrap is retained and fails closed."""
    def __init__(self, root):
        self.root = Path(root)
        self.fd = _directory(self.root)
        self.pin, self.pid = _identity(self.fd), os.getpid()
        self.children = {}
        for name in ("registry", "outbox", "consents"):
            fd = _directory(self.root / name)
            self.children[name] = _identity(fd)
            os.close(fd)

    def guard(self):
        if self.pid != os.getpid():
            raise DemoRejected("market_state_forked")
        fd = _directory(self.root)
        try:
            if _identity(fd) != self.pin or set(os.listdir(fd)) - {
                    "registry", "outbox", "consents", "installation.json"}:
                raise DemoRejected("original_market_state_changed")
        finally:
            os.close(fd)
        for name, pin in self.children.items():
            fd = _directory(self.root / name)
            try:
                if _identity(fd) != pin:
                    raise DemoRejected("original_market_state_changed")
            finally:
                os.close(fd)

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def open_box(self, binding, owner, *, create=False):
        self.guard()
        try:
            fd = _file(self.fd, "installation.json", os.O_RDONLY)
        except FileNotFoundError:
            if not create:
                raise DemoRejected("market_test_not_prepared") from None
            # A missing manifest never permits reusing an existing journal or
            # registry reservation, including incomplete earlier bootstraps.
            if any(os.listdir(self.root / name) for name in self.children):
                raise DemoRejected("market_bootstrap_unknown")
            box = RegisteredDemoOutbox.create(self.root / "registry", self.root / "outbox",
                binding=binding, outbox_id=uuid4(), context=owner, capacity=16)
            try:
                raw = encode(dict(schema="investalo-demo-market-installation/1",
                    binding=binding.record(), minimum_receipt=box.receipt.record()))
                fd = _file(self.fd, "installation.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL)
                try:
                    offset = 0
                    while offset < len(raw):
                        written = os.write(fd, raw[offset:])
                        if written <= 0:
                            raise DemoRejected("market_bootstrap_unknown")
                        offset += written
                    os.fsync(fd); os.fsync(self.fd); _named(self.fd, "installation.json", fd)
                finally:
                    os.close(fd)
                check = _file(self.fd, "installation.json", os.O_RDONLY)
                try:
                    if os.read(check, len(raw)+1) != raw:
                        raise DemoRejected("market_bootstrap_unknown")
                finally:
                    os.close(check)
                self.guard()
                return box
            except BaseException:
                box.close()
                raise
        try:
            if os.fstat(fd).st_size > 16384:
                raise DemoRejected("invalid_market_installation")
            record = decode(os.read(fd, 16385))
            _named(self.fd, "installation.json", fd)
        finally:
            os.close(fd)
        exact(record, ("schema", "binding", "minimum_receipt"))
        if record["schema"] != "investalo-demo-market-installation/1" or record["binding"] != binding.record():
            raise DemoRejected("foreign_market_installation")
        receipt = dict(record["minimum_receipt"])
        if receipt.pop("schema", None) != "bitget-classic-demo-outbox/1":
            raise DemoRejected("invalid_market_installation")
        minimum = OutboxReceipt(**receipt)
        return RegisteredDemoOutbox.restore(self.root / "registry", self.root / "outbox",
            binding=binding, outbox_id=UUID(minimum.outbox_id), context=owner, minimum_receipt=minimum)


class DemoMarketTestRuntime:
    def __init__(self, reader, *, root=ROOT, order_transport=None):
        self.reader, self.config, self.native = reader, reader.config, reader.native
        self.state = MarketTestState(root)
        self.order_transport = order_transport or HTTPSDemoOrderTransport()
        self.operation = threading.Lock()
        self.seen, self.pid, self.last_http = {}, os.getpid(), None
        self.verifier = DemoBTCMarketConsentVerifier(key=reader.signing_key,
            oidc_issuer=self.config["oidc_issuer"], origin=self.config["origin"])

    def _authorize(self, context, action, token, body):
        try:
            if (action not in TARGETS or type(context) is not PasskeyRequestContext
                    or context.tenant_id != self.reader.context.tenant_id
                    or context.user_id != self.reader.context.user_id
                    or type(body) is not bytes or not 0 < len(body) <= 16384
                    or type(token) is not str or len(token) > 8192 or self.pid != os.getpid()):
                raise ValueError()
            a, b, c = token.split(".")
            if (_json(_decode(a)) != {"alg": "HS256", "typ": "JWT"}
                    or not hmac.compare_digest(hmac.digest(self.reader.signing_key,
                        (a+"."+b).encode("ascii"), "sha256"), _decode(c))):
                raise ValueError()
            claims, request, now = _json(_decode(b)), _json(body), int(time.time())
            kind, audience = DOMAINS[action]
            if (set(claims) != FIELDS or claims["kind"] != kind or claims["aud"] != audience
                    or claims["htu"] != TARGETS[action] or claims["htm"] != "POST"
                    or claims["oidc_issuer"] != self.config["oidc_issuer"]
                    or claims["origin"] != self.config["origin"]
                    or claims["body_sha256"] != hashlib.sha256(body).hexdigest()):
                raise ValueError()
            for field in CONTEXT:
                actual = getattr(context, field)
                if type(actual) is UUID: actual = str(actual)
                if type(actual) is not type(claims[field]) or actual != claims[field]:
                    raise ValueError()
            if (type(claims["iat"]) is not int or type(claims["exp"]) is not int
                    or not claims["iat"] <= now < claims["exp"] <= min(claims["iat"]+15, context.session_expires_at)
                    or context.oidc_auth_time > claims["iat"]
                    or str(UUID(claims["jti"])) != claims["jti"]):
                raise ValueError()
            expected = BODY if action == "market_submit" else (
                TARGET_FIELDS | {"command_id"} if action == "market_observe" else TARGET_FIELDS)
            exact(request, expected)
            if (request["platform_account_id"] != str(self.config["account_id"])
                    or str(UUID(request["connection_id"])) != request["connection_id"]
                    or type(request["credential_revision"]) is not int or request["credential_revision"] != 1
                    or type(request["storage_version"]) is not int or not 1 <= request["storage_version"] < 2**53):
                raise ValueError()
            if (action != "market_prepare"
                    and not (action == "market_observe" and request["command_id"] == "latest")
                    and str(UUID(request["command_id"])) != request["command_id"]):
                raise ValueError()
            self.seen = {key: expiry for key, expiry in self.seen.items() if expiry > now}
            if claims["jti"] in self.seen or len(self.seen) >= 256:
                raise ValueError()
            self.seen[claims["jti"]] = claims["exp"]
            return request, claims["exp"] * 1000
        except Exception:
            raise OnboardingRejected("access_denied") from None

    def _guard(self):
        self.state.guard()
        self.native.guard()

    def _basis(self, context, request, expires, *, lock_held=False):
        # Shared original UID quota; wait only before the new five-second cohort.
        if self.native.last is not None:
            time.sleep(max(0, (1000 - (time.time_ns()//1_000_000 - self.native.last))/1000))
        self._guard()
        target = {key: request[key] for key in TARGET_FIELDS}
        target["inspection"] = "btc-market"
        basis = self.reader._read_current(context, target, expires, market_basis=True, lock_held=lock_held)
        self.last_http = time.monotonic()  # conservative after all joined source workers
        self._guard()
        return basis

    def _store(self, context, request, expires):
        owner = OwnerContext(context.tenant_id, context.user_id)
        binding = DemoBinding(owner, self.config["account_id"], UUID(request["connection_id"]), self.config["broker_uid"])
        authority = DemoStoreAuthority(self.reader.context, auth_epoch=context.auth_epoch,
            auth_time_ms=context.oidc_auth_time*1000, expires_ms=expires)
        store = DemoTradingCredentialStore(authority, connect=self.reader.connect)
        snapshot = store.read_snapshot(binding, owner)
        if (snapshot.storage_version != request["storage_version"]
                or snapshot.spec.parent_uid != self.config["parent_uid"]
                or snapshot.spec.egress_ip != self.config["egress_ip"]):
            raise OnboardingRejected("access_denied")
        return owner, binding, store, snapshot

    def __call__(self, context, action, token, body):
        if not self.operation.acquire(blocking=False):
            raise OnboardingRejected("unavailable")
        box, consumer = None, None
        stage, started, native_result = "authorization", time.time_ns()//1_000_000, {}
        def diagnostic(error=None):
            try:
                from .demo_trading_runtime import _write_private_record
                _write_private_record(dict(schema="investalo-demo-market-diagnostic/1",
                    operation=action if action in TARGETS else "invalid", stage=stage,
                    elapsed_ms=time.time_ns()//1_000_000-started,
                    error_type=None if error is None else type(error).__name__, **native_result),
                    "/tmp/demo-market-test-diagnostic.json")
            except Exception:
                pass
        try:
            request, expires = self._authorize(context, action, token, body)
            self._guard()
            stage = "current_store"
            owner, binding, store, snapshot = self._store(context, request, expires)
            stage = "original_state"
            box = self.state.open_box(binding, owner, create=action == "market_prepare")
            traces = box.traces(context=owner)
            if action == "market_prepare":
                if any(not trace.can_submit for trace in traces) or len(traces) >= 16:
                    raise DemoRejected("single_market_test_already_attempted")
                stage = "preparation_source"
                current, _, _, report, (readiness, wallet, market) = self._basis(context, request, expires)
                if (current.spec.record() != snapshot.spec.record() or current.storage_version != snapshot.storage_version
                        or dump_envelope(current.envelope) != dump_envelope(snapshot.envelope)):
                    raise DemoRejected("market_preparation_changed")
                intent = market.intent(binding, uuid4())
                check_btc_market_test(intent, readiness, wallet, market, now_ms=time.time_ns()//1_000_000)
                self._guard()
                latest = store.read_snapshot(binding, owner)
                if (latest.spec.record() != snapshot.spec.record() or latest.storage_version != snapshot.storage_version
                        or dump_envelope(latest.envelope) != dump_envelope(snapshot.envelope)):
                    raise DemoRejected("market_preparation_changed")
                stage = "preparation_journal"
                receipt = box.prepare(intent, context=owner, expected_revision=box.receipt.revision)
                consent = dict(platform_account_id=str(binding.account_id), connection_id=str(binding.credential_ref),
                    credential_revision=1, storage_version=snapshot.storage_version,
                    command_id=str(intent.command_id), intent_sha256=intent.intent_digest,
                    outbox_receipt=receipt.record(), confirmation=CONFIRMATION)
                stage = "completed"; diagnostic()
                return dict(schema="investalo-demo-market-prepared/1", report=report, consent_request=consent,
                            expires_ms=intent.observed_ms+30000)
            found = [trace for trace in traces if (
                not trace.can_submit if action == "market_observe" and request["command_id"] == "latest"
                else str(trace.intent.command_id) == request["command_id"])]
            if len(found) != 1:
                raise DemoRejected("unknown_market_test")
            trace = found[0]
            if type(trace.intent) is not BTCMarketIntent:
                raise DemoRejected("foreign_market_test_intent")
            if action == "market_observe" and trace.can_submit:
                # Positive original journal evidence of no attempted dispatch.
                # Do not query an unsubmitted clientOid or rearm the old consent.
                self._guard(); store.read_snapshot(binding, owner)
                stage = "completed"; diagnostic()
                return market_status(trace)
            def guard():
                self._guard()
                latest = store.read_snapshot(binding, owner)
                if (latest.spec.record() != snapshot.spec.record()
                        or latest.storage_version != snapshot.storage_version
                        or dump_envelope(latest.envelope) != dump_envelope(snapshot.envelope)):
                    raise DemoRejected("market_credential_changed")
            def paced(transport):
                def send(packet):
                    if self.last_http is not None:
                        time.sleep(max(0, .11-(time.monotonic()-self.last_http)))
                    guard()
                    if packet.method == "POST":
                        if len(native_basis) != 1:
                            raise DemoRejected("missing_original_market_basis")
                        _, _, _, _, (readiness, wallet, market) = native_basis[0]
                        check_btc_market_test(trace.intent, readiness, wallet, market,
                                              now_ms=time.time_ns()//1_000_000)
                    self.last_http = time.monotonic()
                    response = transport(packet)
                    if packet.method == "POST" or "/order/detail?" in packet.target:
                        native_result["http_status"] = response.status
                        try:
                            frame = _json(response.body)
                            code = frame.get("code")
                            if type(code) is str and len(code) == 5 and code.isascii() and code.isdecimal():
                                native_result["provider_code"] = code
                        except Exception:
                            pass
                    return response
                return send
            native_basis = []
            def account_guard(intent, receipt, actor):
                if not native_basis:
                    native_basis.append(self._basis(context, request, expires, lock_held=True))
                # Recheck the original native timestamps and current actor/key
                # before POST. Never replace them with the validation time.
                # An expired basis denies before the attempt; no second cohort
                # or synthetic freshness can extend the dispatch's5s budget.
                current, _, _, _, (readiness, wallet, market) = native_basis[0]
                if (current.spec.record() != snapshot.spec.record()
                        or current.storage_version != snapshot.storage_version
                        or dump_envelope(current.envelope) != dump_envelope(snapshot.envelope)):
                    raise DemoRejected("market_credential_changed")
                check_btc_market_test(intent, readiness, wallet, market, now_ms=time.time_ns()//1_000_000)
                guard()
            authorize = None
            if action == "market_submit":
                stage = "consent_verifier"
                self.verifier.verify(context, token, body, trace.intent, box.receipt, time.time_ns()//1_000_000)
                if not trace.can_submit or any(not t.can_submit for t in traces):
                    raise DemoRejected("single_market_test_already_attempted")
                issuer = DemoBTCTestConsentIssuer(self.verifier, context, token, body,
                    read_snapshot=store.read_snapshot, guard=guard)
                consumer = DurableDemoOrderConsumer(self.state.root / "consents", issuer=issuer, guard=guard)
                authorize = consumer
            provider = store.provider(snapshot.spec, expected_storage=snapshot.storage_version,
                                      load_keyring=self.reader.keyring)
            dispatcher = DemoOrderDispatcher(box, provider, read_transport=paced(self.native.transport),
                order_transport=paced(self.order_transport), native_guard=guard, account_guard=account_guard,
                shared_lock=self.native.lock, ip_binding=self.config["ip_binding"],
                authorize_once=authorize, enabled=True)
            matched = False
            if action == "market_submit":
                stage = "dispatch"
                dispatch = dispatcher.dispatch(trace.intent.command_id, context=owner, expected_revision=box.receipt.revision)
                native_result["dispatch_outcome"] = dispatch.outcome
            else:
                stage = "observe"
                result = dispatcher.observe(trace.intent.command_id, context=owner, expected_revision=box.receipt.revision)
                matched = result.position_matched
            guard()
            stage = "completed"; diagnostic()
            return market_status(next(t for t in box.traces(context=owner)
                if t.intent.command_id == trace.intent.command_id), matched)
        except OnboardingRejected as error:
            diagnostic(error)
            raise
        except Exception as error:
            diagnostic(error)
            raise OnboardingRejected("unavailable") from None
        finally:
            if consumer: consumer.close()
            if box: box.close()
            self.operation.release()


def market_status(trace, matched=False):
    observation = trace.observation
    def fee(value):
        return None if value is None else ("-" if value < 0 else "") + text(value.copy_abs())
    return dict(schema="investalo-demo-market-status/1", command_id=str(trace.intent.command_id),
        state=trace.state, requested_quantity_btc=text(trace.intent.quantity),
        filled_quantity_btc=None if observation is None else text(observation.quantity),
        average_price_usdt=None if observation is None or observation.average_price is None else text(observation.average_price),
        reported_fee_usdt=None if observation is None else fee(observation.reported_fee),
        observed_ms=None if observation is None else observation.response_ms,
        position_matched=matched, order_resubmit_allowed=False)


def validate_market_result(action, result):
    from decimal import Decimal
    from .demo_btc_test_check import validate_btc_market_test
    from .demo_account_sync import public_amount
    if action == "market_prepare":
        exact(result, ("schema", "report", "consent_request", "expires_ms"))
        if result["schema"] != "investalo-demo-market-prepared/1":
            raise ValueError()
        report = validate_btc_market_test(result["report"])
        body = exact(result["consent_request"], BODY)
        if (body["confirmation"] != CONFIRMATION or type(body["credential_revision"]) is not int
                or body["credential_revision"] != 1 or type(body["storage_version"]) is not int
                or not 1 <= body["storage_version"] < 2**53
                or body["platform_account_id"] != report["readiness"]["account"]["account_id"]):
            raise ValueError()
        for name in ("platform_account_id", "connection_id", "command_id"):
            if str(UUID(body[name])) != body[name]: raise ValueError()
        receipt = exact(body["outbox_receipt"], ("schema", "outbox_id", "binding_digest", "revision", "head", "state_digest"))
        if (receipt["schema"] != "bitget-classic-demo-outbox/1" or str(UUID(receipt["outbox_id"])) != receipt["outbox_id"]
                or type(receipt["revision"]) is not int or not 1 <= receipt["revision"] <= 10000
                or type(result["expires_ms"]) is not int
                or result["expires_ms"] != report["preview"]["observed_ms"]+30000):
            raise ValueError()
        import re
        if any(type(v) is not str or re.fullmatch("[a-f0-9]{64}", v) is None for v in
               (body["intent_sha256"], receipt["binding_digest"], receipt["head"], receipt["state_digest"])):
            raise ValueError()
    elif action in ("market_submit", "market_observe"):
        exact(result, ("schema", "command_id", "state", "requested_quantity_btc", "filled_quantity_btc",
                       "average_price_usdt", "reported_fee_usdt", "observed_ms", "position_matched", "order_resubmit_allowed"))
        if (result["schema"] != "investalo-demo-market-status/1"
                or str(UUID(result["command_id"])) != result["command_id"]
                or result["state"] not in ("prepared", "submission_unknown", "acknowledged", "live", "partially_filled", "filled", "canceled")
                or result["order_resubmit_allowed"] is not False or type(result["position_matched"]) is not bool):
            raise ValueError()
        quantity = public_amount(result["requested_quantity_btc"])
        filled = None if result["filled_quantity_btc"] is None else public_amount(result["filled_quantity_btc"])
        price = None if result["average_price_usdt"] is None else public_amount(result["average_price_usdt"])
        if (quantity is None or quantity <= 0 or filled is not None and not Decimal(0) <= filled <= quantity
                or price is not None and price <= 0 or filled is None and price is not None
                or filled == 0 and price is not None or filled is not None and filled > 0 and price is None
                or result["state"] == "filled" and filled != quantity
                or result["state"] == "partially_filled" and (filled is None or not 0 < filled < quantity)
                or result["state"] in ("prepared", "submission_unknown", "acknowledged") and filled is not None):
            raise ValueError()
        if result["reported_fee_usdt"] is not None: public_amount(result["reported_fee_usdt"], signed=True)
        if result["observed_ms"] is not None and (type(result["observed_ms"]) is not int or not 0 <= result["observed_ms"] < 10**15):
            raise ValueError()
    else:
        raise ValueError()
    return result
