"""Private passkey-authorized Bitget onboarding; no HTTP or implicit transport."""
from __future__ import annotations

from contextlib import contextmanager

from investalo_bitget import (
    AccountBinding, BitgetRejected, ClassicReadClient, OwnerContext,
)
from investalo_bitget.models import address
from investalo_credentials import AADBinding, KEKRing

from .client import CredentialStore, ConnectFactory, _db_error, _row
from .models import ErrorCode, StoreContext, StoreRejected, _PrivateImmutable
from .onboarding import OnboardingResult, _request
from .passkey_authorization import PasskeyAuthorizationClient, _claims_json
from .passkey_request_assertion import PasskeyRequestContext, PasskeyRequestVerifier
from .request_assertion import OnboardingRejected

FINISH_SQL = "SELECT platform.credential_finish_passkey_authorization(%s::jsonb,%s)"


class PasskeyBitgetOnboarding(_PrivateImmutable):
    """Connect durable purpose consent to existing private probe/store primitives.

    The factory must commit on successful exit and roll back on failure. Neither
    unknown consume commits nor unknown final commits are retried. Transport,
    trusted original session, signing identity and keyring are server inputs.
    """
    __slots__ = ("_context", "_keyring", "_connect", "_authorization",
                 "_transport", "_ip", "_store")

    def __init__(self, context: StoreContext, keyring: KEKRing, *,
                 connect: ConnectFactory, verifier: PasskeyRequestVerifier,
                 request_context: PasskeyRequestContext, transport,
                 expected_egress_ip: str):
        try:
            if not callable(transport):
                raise ValueError()
            authorization = PasskeyAuthorizationClient(
                context, request_context, verifier=verifier, connect=connect,
            )
            store = CredentialStore(context, keyring, connect=connect)
            ip = address(expected_egress_ip)
        except Exception:
            raise OnboardingRejected("invalid_context") from None
        for field, value in (
            ("_context", context), ("_keyring", keyring), ("_connect", connect),
            ("_authorization", authorization), ("_transport", transport),
            ("_ip", ip), ("_store", store),
        ):
            object.__setattr__(self, field, value)

    @contextmanager
    def _final_connection(self, authorization):
        """Write and terminal completion share the checked008 lock transaction."""
        try:
            with self._authorization.lock(authorization) as connection:
                yield connection
                with connection.cursor() as cursor:
                    cursor.execute(FINISH_SQL, (
                        _claims_json(authorization._assertion), "completed",
                    ))
                    if _row(cursor, 1)[0] is not True:
                        raise OnboardingRejected("invalid_record") from None
        except OnboardingRejected as error:
            # CredentialStore deliberately recognizes StoreRejected rather than
            # arbitrary exceptions. Keep static authority/crypto/CAS codes
            # through this nested transaction factory without exposing drivers.
            try:
                code = ErrorCode(error.code)
            except ValueError:
                code = ErrorCode.UNAVAILABLE
            raise StoreRejected(code) from None

    def _failed(self, authorization):
        try:
            with self._authorization._session() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(FINISH_SQL, (
                        _claims_json(authorization._assertion), "failed",
                    ))
                    if _row(cursor, 1)[0] is not True:
                        raise OnboardingRejected("invalid_record") from None
        except Exception:
            # Committed consume stays terminal if best-effort audit is absent.
            # A successful-but-unacknowledged completion must not be overwritten.
            pass

    def apply(self, action: str, *, token: str, body: bytes) -> OnboardingResult:
        authorization = None
        try:
            # Verification includes the exact body/target schema. No old key
            # read or broker dispatch may happen before the consume is committed.
            authorization = self._authorization.consume(action, token=token, body=body)
            account, connection, revision, storage, credentials, payload = _request(action, body)
            old = None
            if action == "replace":
                old = self._store.read(connection).snapshot
                if old.binding.platform_account_id != account:
                    raise OnboardingRejected("access_denied") from None
                if (old.binding.credential_revision, old.storage_version) != (revision, storage):
                    raise OnboardingRejected("concurrent_change") from None
            if action != "revoke":
                owner = OwnerContext(self._context.tenant_id, self._context.user_id)
                probe = ClassicReadClient(credentials, owner, transport=self._transport).probe_identity(
                    owner, expected_egress_ip=self._ip,
                )
                if probe.ip_whitelist != (self._ip,):
                    raise OnboardingRejected("broker_rejected") from None
                if old is not None:
                    AccountBinding(
                        owner, old.binding.broker_uid, old.binding.parent_uid,
                        expected_egress_ip=self._ip,
                    ).validate(owner, probe, require_ip=True)
            guarded = CredentialStore(
                self._context, self._keyring,
                connect=lambda: self._final_connection(authorization),
            )
            if action == "register":
                binding = AADBinding(
                    tenant_id=self._context.tenant_id, user_id=self._context.user_id,
                    platform_account_id=account, connection_id=connection,
                    broker_uid=probe.user_id, parent_uid=probe.parent_id,
                    credential_revision=1,
                )
                written = guarded.register(binding, payload)
            elif action == "replace":
                written = guarded.replace(
                    connection, expected_revision=revision,
                    expected_storage=storage, payload=payload,
                )
            else:
                version = guarded.revoke(
                    connection, expected_revision=revision, expected_storage=storage,
                )
                return OnboardingResult(connection, revision, version, "revoked")
            return OnboardingResult(
                connection, written.binding.credential_revision,
                written.storage_version, "active",
            )
        except Exception as error:
            if authorization is not None:
                self._failed(authorization)
            if isinstance(error, OnboardingRejected):
                raise OnboardingRejected(error.code) from None
            if isinstance(error, BitgetRejected):
                raise OnboardingRejected("broker_rejected") from None
            if isinstance(error, StoreRejected):
                raise OnboardingRejected(error.code.value) from None
            raise OnboardingRejected(_db_error(error).value) from None
