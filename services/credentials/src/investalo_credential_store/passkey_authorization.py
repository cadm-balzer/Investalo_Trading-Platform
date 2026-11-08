"""Private durable passkey authorization intake; no broker or credential writer.

The injected factory must supply fresh non-autocommit transaction contexts that
commit on successful exit and roll back on failure. An unknown commit never
returns a handle and is never retried here. The lock transaction belongs to a
future explicit writer; this module does not call any 003/004 mutation.
"""
from __future__ import annotations

from contextlib import contextmanager
import json
from uuid import UUID

from .client import ConnectFactory, CONTEXT_SQL, ROLE_SQL, _db_error, _row
from .models import StoreContext, StoreRejected, _PrivateImmutable
from .passkey_request_assertion import (
    PasskeyActionAssertion, PasskeyRequestContext, PasskeyRequestVerifier,
)
from .request_assertion import OnboardingRejected

CONSUME_SQL = "SELECT platform.credential_consume_passkey_authorization(%s::jsonb)"
LOCK_SQL = "SELECT platform.credential_lock_passkey_authorization(%s::jsonb)"


def _claims_json(assertion: PasskeyActionAssertion) -> str:
    """Explicit private DB boundary; contains hashes and claims, never secrets."""
    if type(assertion) is not PasskeyActionAssertion:
        raise OnboardingRejected("invalid_record") from None
    claims = {}
    for field in PasskeyActionAssertion.__slots__:
        value = getattr(assertion, field)
        claims[field] = (str(value) if type(value) is UUID else
                         dict(value) if field == "target" else value)
    return json.dumps(claims, ensure_ascii=True, separators=(",", ":"), allow_nan=False)


class ConsumedPasskeyAuthorization(_PrivateImmutable):
    """Available only after an acknowledged consume commit; no public projection."""
    __slots__ = ("_owner", "_assertion")

    def __init__(self, owner, assertion):
        object.__setattr__(self, "_owner", owner)
        object.__setattr__(self, "_assertion", assertion)


class PasskeyAuthorizationClient(_PrivateImmutable):
    """Bind a dedicated LOGIN, frozen trusted session, and passkey verifier."""
    __slots__ = ("_store_context", "_request_context", "_verifier", "_connect")

    def __init__(self, store_context: StoreContext, request_context: PasskeyRequestContext,
                 *, verifier: PasskeyRequestVerifier, connect: ConnectFactory):
        try:
            if (type(store_context) is not StoreContext
                    or type(request_context) is not PasskeyRequestContext
                    or type(verifier) is not PasskeyRequestVerifier or not callable(connect)
                    or (store_context.tenant_id, store_context.user_id)
                    != (request_context.tenant_id, request_context.user_id)):
                raise ValueError()
        except Exception:
            raise OnboardingRejected("invalid_context") from None
        for field, value in (("_store_context", store_context), ("_request_context", request_context),
                             ("_verifier", verifier), ("_connect", connect)):
            object.__setattr__(self, field, value)

    @contextmanager
    def _session(self):
        try:
            with self._connect() as connection:
                if connection.autocommit is not False:
                    raise OnboardingRejected("invalid_context") from None
                with connection.cursor() as cursor:
                    cursor.execute(ROLE_SQL)
                    role = _row(cursor, 8)
                    if (role[:2] != (self._store_context.expected_login_role,) * 2
                            or any(type(flag) is not bool for flag in role[2:])
                            or any(role[2:7]) or role[7] is not True):
                        raise OnboardingRejected("access_denied") from None
                    cursor.execute(CONTEXT_SQL)
                    tenant, user = _row(cursor, 2)
                    if (type(tenant) is not UUID or type(user) is not UUID
                            or (tenant, user)
                            != (self._store_context.tenant_id, self._store_context.user_id)):
                        raise OnboardingRejected("access_denied") from None
                yield connection
        except OnboardingRejected as error:
            raise OnboardingRejected(error.code) from None
        except StoreRejected as error:
            raise OnboardingRejected(error.code.value) from None
        except Exception as error:
            raise OnboardingRejected(_db_error(error).value) from None

    def consume(self, action: str, *, token: str, body: bytes) -> ConsumedPasskeyAuthorization:
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
        return ConsumedPasskeyAuthorization(self, assertion)

    @contextmanager
    def lock(self, authorization: ConsumedPasskeyAuthorization):
        """Recheck the same claims in a separate final-write transaction.

        SQL requires the consume to be committed in another transaction and
        rechecks current actor/session/factor/metadata/CAS/time under its locks.
        The caller may use this connection only for its separately reviewed
        final write/completion; this module supplies neither operation.
        """
        try:
            if (type(authorization) is not ConsumedPasskeyAuthorization
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
