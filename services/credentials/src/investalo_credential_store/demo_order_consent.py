"""Own exact BTC-test consent domain; not installed in the operative runtime.

The trusted BFF must obtain explicit original-session order consent before
signing. This verifier neither establishes browser consent nor issues tokens.
Read/key-management tokens are rejected. A fresh independent actor/store
adapter remains mandatory; no native account or quantity waiver is implied.
"""
import hashlib
import hmac
import os
import threading
import time
from decimal import Decimal, localcontext
from uuid import UUID

from investalo_bitget import OwnerContext
from investalo_bitget.futures_demo import DemoIntent, DemoRejected, clock
from investalo_bitget.futures_demo_market import BTCMarketIntent, CONFIRMATION as MARKET_CONFIRMATION, CLOSE_CONFIRMATION
from investalo_bitget.futures_demo_outbox import OutboxReceipt
from investalo_credentials import dump_envelope

from .demo_order_dispatch import DemoOrderApproval
from .demo_trading_provider import DemoTradingSecretSnapshot
from .models import _PrivateImmutable
from .passkey_request_assertion import PasskeyRequestContext, _decode, _json

PATH = "/v1/bitget-demo-trading/order-submit"
KIND = "investalo-demo-btc-test-order-consent/1"
AUDIENCE = "investalo-demo-btc-test-order"
CONFIRMATION = "btc-demo-long-isolated-2x-notional-at-most-20-usdt"
CONTEXT = ("tenant_id", "user_id", "subject", "auth_epoch", "oidc_auth_time",
           "session_binding", "session_expires_at")
CLAIMS = frozenset((*CONTEXT, "kind", "aud", "oidc_issuer", "origin",
    "iat", "exp", "jti", "htm", "htu", "body_sha256"))
BODY = frozenset(("platform_account_id", "connection_id", "credential_revision",
    "storage_version", "command_id", "intent_sha256", "outbox_receipt", "confirmation"))


class DemoBTCTestConsentVerifier(_PrivateImmutable):
    __slots__ = ("key", "oidc_issuer", "origin")

    def __init__(self, *, key, oidc_issuer, origin):
        if (type(key) is not bytes or len(key) != 32
                or oidc_issuer != "https://auth.cockpit.investalo.de"
                or origin != "https://cockpit.investalo.de"):
            raise DemoRejected("invalid_btc_consent_installation")
        for name, value in (("key", key), ("oidc_issuer", oidc_issuer), ("origin", origin)):
            object.__setattr__(self, name, value)

    def verify(self, context, token, body, intent, receipt, now_ms):
        try:
            now_ms = clock(now_ms)
            closing = type(self) is DemoBTCMarketCloseConsentVerifier
            market = closing or type(self) is DemoBTCMarketConsentVerifier
            kind = "investalo-demo-btc-market-close-consent/1" if closing else "investalo-demo-btc-market-order-consent/1" if market else KIND
            audience = "investalo-demo-btc-market-close" if closing else "investalo-demo-btc-market-order" if market else AUDIENCE
            path = "/v1/bitget-demo-trading/market-close-submit" if closing else "/v1/bitget-demo-trading/market-order-submit" if market else PATH
            confirmation = CLOSE_CONFIRMATION if closing else MARKET_CONFIRMATION if market else CONFIRMATION
            if (type(context) is not PasskeyRequestContext or type(token) is not str
                    or len(token) > 8192 or type(body) is not bytes or not 0 < len(body) <= 16384
                    or type(self) not in (DemoBTCTestConsentVerifier, DemoBTCMarketConsentVerifier, DemoBTCMarketCloseConsentVerifier)
                    or type(intent) is not (BTCMarketIntent if market else DemoIntent)
                    or type(receipt) is not OutboxReceipt):
                raise ValueError()
            intent.binding.check(OwnerContext(context.tenant_id, context.user_id))
            with localcontext() as precision:
                precision.prec = 160
                if (intent.grid.symbol != "BTCUSDT" or intent.action != ("reduce_long" if closing else "open_long")
                        or not closing and intent.before_quantity != Decimal(0)
                        or closing and (intent.before_quantity <= 0 or intent.quantity != intent.before_quantity)
                        or not market and intent.quantity * intent.limit_price > Decimal(20)
                        # A human can confirm a displayed proposal for30s.
                        # It remains a reference, not current native evidence:
                        # account_guard must separately recheck a <=5s source
                        # and the exact quantity at its fresh ask before POST.
                        or market and not 0 <= now_ms - intent.observed_ms <= 30000):
                    raise ValueError()
            header, payload, signature = token.split(".")
            if _json(_decode(header)) != {"alg": "HS256", "typ": "JWT"}:
                raise ValueError()
            expected = hmac.digest(self.key, (header + "." + payload).encode("ascii"), "sha256")
            if not hmac.compare_digest(expected, _decode(signature)):
                raise ValueError()
            claims, request = _json(_decode(payload)), _json(body)
            if set(claims) != CLAIMS or set(request) != BODY:
                raise ValueError()
            for name in CONTEXT:
                actual = getattr(context, name)
                if type(actual) is UUID:
                    actual = str(actual)
                if type(claims[name]) is not type(actual) or claims[name] != actual:
                    raise ValueError()
            if (claims["kind"] != kind or claims["aud"] != audience
                    or claims["oidc_issuer"] != self.oidc_issuer or claims["origin"] != self.origin
                    or claims["htm"] != "POST" or claims["htu"] != path
                    or claims["body_sha256"] != hashlib.sha256(body).hexdigest()
                    or type(claims["iat"]) is not int or type(claims["exp"]) is not int
                    or not claims["iat"] * 1000 <= now_ms < claims["exp"] * 1000
                    or not claims["iat"] < claims["exp"] <= claims["iat"] + 15
                    or claims["exp"] > context.session_expires_at
                    or context.oidc_auth_time > claims["iat"]
                    or type(claims["jti"]) is not str or str(UUID(claims["jti"])) != claims["jti"]):
                raise ValueError()
            if (request["platform_account_id"] != str(intent.binding.account_id)
                    or request["connection_id"] != str(intent.binding.credential_ref)
                    or request["command_id"] != str(intent.command_id)
                    or request["intent_sha256"] != intent.intent_digest
                    or type(request["credential_revision"]) is not int or request["credential_revision"] != 1
                    or type(request["storage_version"]) is not int or not 1 <= request["storage_version"] < 2**53
                    or request["confirmation"] != confirmation
                    or request["outbox_receipt"] != receipt.record()
                    or any(type(request["outbox_receipt"].get(key)) is not type(value)
                           for key, value in receipt.record().items())):
                raise ValueError()
            return UUID(claims["jti"]), request["storage_version"], claims["iat"] * 1000, claims["exp"] * 1000
        except Exception:
            raise DemoRejected("btc_order_consent_not_confirmed") from None


class DemoBTCMarketConsentVerifier(DemoBTCTestConsentVerifier):
    """Own explicit Market test domain; old Limit/read tokens grant no authority."""
    __slots__ = ()

class DemoBTCMarketCloseConsentVerifier(DemoBTCTestConsentVerifier):
    """Separate exact owned-position closing purpose; opening tokens cannot close."""
    __slots__ = ()


class DemoBTCTestConsentIssuer(_PrivateImmutable):
    """Verify own signed consent plus actual current actor and encrypted state.

    Intended as the mandatory issuer of DurableDemoOrderConsumer. The final
    consumer remains responsible for persistent replay rejection before AEAD.
    """
    __slots__ = ("verifier", "context", "token", "body", "read_snapshot", "guard",
                 "now", "pid", "lock", "used")

    def __init__(self, verifier, context, token, body, *, read_snapshot, guard,
                 milliseconds=lambda: time.time_ns() // 1_000_000):
        if (type(verifier) not in (DemoBTCTestConsentVerifier, DemoBTCMarketConsentVerifier, DemoBTCMarketCloseConsentVerifier)
                or type(context) is not PasskeyRequestContext
                or not all(callable(value) for value in (read_snapshot, guard, milliseconds))):
            raise DemoRejected("invalid_btc_order_issuer_installation")
        for name, value in (("verifier", verifier), ("context", context), ("token", token), ("body", body),
                ("read_snapshot", read_snapshot), ("guard", guard), ("now", milliseconds),
                ("pid", os.getpid()), ("lock", threading.Lock()), ("used", False)):
            object.__setattr__(self, name, value)

    def __call__(self, intent, receipt, owner):
        with self.lock:
            if self.used or self.pid != os.getpid():
                raise DemoRejected("btc_order_issuer_already_used")
            object.__setattr__(self, "used", True)
            if type(owner) is not OwnerContext or owner != OwnerContext(self.context.tenant_id, self.context.user_id):
                raise DemoRejected("foreign_btc_order_actor")
            self.guard()
            approved = self.verifier.verify(self.context, self.token, self.body, intent, receipt, self.now())
            first = self.read_snapshot(intent.binding, owner)
            self.guard()
            latest = self.read_snapshot(intent.binding, owner)
            self.verifier.verify(self.context, self.token, self.body, intent, receipt, self.now())
            if (type(first) is not DemoTradingSecretSnapshot or type(latest) is not DemoTradingSecretSnapshot
                    or first.spec.binding != intent.binding or first.spec.credential_revision != 1
                    or first.storage_version != approved[1]
                    or latest.spec.record() != first.spec.record() or latest.storage_version != first.storage_version
                    or dump_envelope(first.envelope) != dump_envelope(latest.envelope)):
                raise DemoRejected("btc_order_credential_not_confirmed")
            self.guard()
            self.verifier.verify(self.context, self.token, self.body, intent, receipt, self.now())
            return DemoOrderApproval(approved[0], intent, receipt, credential_revision=1,
                storage_version=approved[1], granted_ms=approved[2], expires_ms=approved[3])
