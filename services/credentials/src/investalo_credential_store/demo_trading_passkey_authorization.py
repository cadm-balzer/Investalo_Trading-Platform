"""Private durable Demo Trading authorization; no broker or credential writer.

The injected factory must supply fresh non-autocommit transaction contexts that
commit on successful exit and roll back on failure. An unknown commit never
returns a handle and is never retried here. The separate onboarding executor
combines this domain's final execution lock,018 writer and019 completion.
"""
from __future__ import annotations

from contextlib import contextmanager
import json
from uuid import UUID

from .client import ConnectFactory, _row
from .models import StoreContext, _PrivateImmutable
from .passkey_request_assertion import PasskeyRequestContext
from .demo_trading_passkey_assertion import DemoTradingPasskeyActionAssertion, DemoTradingPasskeyRequestVerifier
from .request_assertion import OnboardingRejected
from .demo_passkey_authorization import DemoPasskeyAuthorizationClient

CONSUME_SQL = "SELECT platform.demo_trading_credential_consume_passkey_authorization(%s::jsonb)"
LOCK_SQL = "SELECT platform.demo_trading_credential_lock_passkey_authorization(%s::jsonb)"


def _claims_json(assertion: DemoTradingPasskeyActionAssertion) -> str:
    """Explicit private DB boundary; contains hashes and claims, never secrets."""
    if type(assertion) is not DemoTradingPasskeyActionAssertion:
        raise OnboardingRejected("invalid_record") from None
    claims = {}
    for field in DemoTradingPasskeyActionAssertion.__slots__:
        value = getattr(assertion, field)
        claims[field] = (str(value) if type(value) is UUID else
                         dict(value) if field == "target" else value)
    return json.dumps(claims, ensure_ascii=True, separators=(",", ":"), allow_nan=False)


class ConsumedDemoTradingPasskeyAuthorization(_PrivateImmutable):
    """Available only after an acknowledged consume commit; no public projection."""
    __slots__ = ("_owner", "_assertion")

    def __init__(self, owner, assertion):
        object.__setattr__(self, "_owner", owner)
        object.__setattr__(self, "_assertion", assertion)


class DemoTradingPasskeyAuthorizationClient(DemoPasskeyAuthorizationClient):
    """Own domain; inherit only restricted LOGIN/current-actor session checks."""
    __slots__ = ()

    def __init__(self, store_context: StoreContext, request_context: PasskeyRequestContext,
                 *, verifier: DemoTradingPasskeyRequestVerifier, connect: ConnectFactory):
        try:
            if (type(store_context) is not StoreContext
                    or type(request_context) is not PasskeyRequestContext
                    or type(verifier) is not DemoTradingPasskeyRequestVerifier or not callable(connect)
                    or (store_context.tenant_id, store_context.user_id)
                    != (request_context.tenant_id, request_context.user_id)):
                raise ValueError()
        except Exception:
            raise OnboardingRejected("invalid_context") from None
        for field, value in (("_store_context", store_context), ("_request_context", request_context),
                             ("_verifier", verifier), ("_connect", connect)):
            object.__setattr__(self, field, value)

    def consume(self, action: str, *, token: str, body: bytes) -> ConsumedDemoTradingPasskeyAuthorization:
        """Authenticate before DB access; consume once and commit before return."""
        assertion = self._verifier.verify(
            token, action=action, body=body, context=self._request_context,
        )
        claims = _claims_json(assertion)
        with self._session() as connection:
            with connection.cursor() as cursor:
                cursor.execute(CONSUME_SQL, (claims,))
                authorization_id, = _row(cursor, 1)
                if (type(authorization_id) is not UUID
                        or authorization_id != assertion.authorization_id):
                    raise OnboardingRejected("invalid_record") from None
        # The factory's transaction __exit__ has acknowledged the consume commit.
        return ConsumedDemoTradingPasskeyAuthorization(self, assertion)

    @contextmanager
    def lock(self, authorization: ConsumedDemoTradingPasskeyAuthorization):
        """Recheck the same claims in a separate final-write transaction.

        SQL requires the consume to be committed in another transaction and
        rechecks current actor/session/factor/metadata/CAS/time under its locks.
        Current checks require the original metadata to remain unchanged.
        The onboarding executor uses the separate post-write completion contract.
        This helper validates unchanged metadata and does not write credentials.
        Time/authority are checked again before final transaction completion.
        """
        try:
            if (type(authorization) is not ConsumedDemoTradingPasskeyAuthorization
                    or authorization._owner is not self):
                raise ValueError()
            claims = _claims_json(authorization._assertion)
        except Exception:
            raise OnboardingRejected("invalid_context") from None
        with self._session() as connection:
            with connection.cursor() as cursor:
                cursor.execute(LOCK_SQL, (claims,))
                locked, = _row(cursor, 1)
                if locked is not True:
                    raise OnboardingRejected("invalid_record") from None
            yield connection
            with connection.cursor() as cursor:
                cursor.execute(LOCK_SQL, (claims,))
                locked, = _row(cursor, 1)
                if locked is not True:
                    raise OnboardingRejected("invalid_record") from None
