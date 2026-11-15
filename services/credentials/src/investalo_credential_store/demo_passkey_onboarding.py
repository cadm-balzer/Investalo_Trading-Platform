"""Private Demo executor; provisioning/keys are trusted injected server inputs."""
from contextlib import contextmanager

from investalo_bitget import OwnerContext, BitgetRejected
from investalo_bitget.models import address
from investalo_credentials import KEKRing

from .client import _db_error, _row
from .demo_passkey_assertion import DemoPasskeyRequestVerifier
from .demo_passkey_authorization import (
    DemoPasskeyAuthorizationClient, ConsumedDemoPasskeyAuthorization, _claims_json,
)
from .demo_secret_provider import DemoSecretSpec
from .demo_store import DemoCredentialStore, DemoStoreAuthority
from .models import ErrorCode, StoreRejected, _PrivateImmutable
from .onboarding import OnboardingResult, _request
from .request_assertion import OnboardingRejected

LOCK_SQL = "SELECT platform.demo_credential_lock_passkey_execution(%s::jsonb)"
FINISH_SQL = "SELECT platform.demo_credential_finish_passkey_authorization(%s::jsonb,%s)"


class DemoPasskeyOnboarding(_PrivateImmutable):
    """Commit consume, obtain own provisioning, then atomically seal/write/finish.

    Provisioning must independently verify the supplied Demo triple and return
    the full original DemoSecretSpec. It is not native proof implemented here.
    It receives only the verified own target and short assertion deadline;
    request fields cannot select UID/parent/IP/provenance. No implicit HTTP.
    """
    __slots__ = ("_context", "_authorization", "_provision", "_keyring", "_ip")

    def __init__(self, context, *, connect, verifier, request_context,
                 provision, load_keyring, expected_egress_ip):
        try:
            if (type(verifier) is not DemoPasskeyRequestVerifier
                    or not callable(provision) or not callable(load_keyring)):
                raise ValueError()
            authorization = DemoPasskeyAuthorizationClient(
                context, request_context, verifier=verifier, connect=connect)
            ip = address(expected_egress_ip)
            if ip != expected_egress_ip:
                raise ValueError()
        except Exception:
            raise OnboardingRejected("invalid_context") from None
        for field, value in (("_context", context), ("_authorization", authorization),
                             ("_provision", provision), ("_keyring", load_keyring), ("_ip", ip)):
            object.__setattr__(self, field, value)

    @contextmanager
    def _final_connection(self, authorization):
        """Own016 post-write check replaces the immutable015 pre-write recheck."""
        try:
            if (type(authorization) is not ConsumedDemoPasskeyAuthorization
                    or authorization._owner is not self._authorization):
                raise OnboardingRejected("invalid_context")
            claims = _claims_json(authorization._assertion)
            with self._authorization._session() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(LOCK_SQL, (claims,))
                    if _row(cursor, 1)[0] is not True:
                        raise OnboardingRejected("invalid_record")
                yield connection
                with connection.cursor() as cursor:
                    cursor.execute(FINISH_SQL, (claims, "completed"))
                    if _row(cursor, 1)[0] is not True:
                        raise OnboardingRejected("invalid_record")
        except OnboardingRejected as error:
            try:
                code = ErrorCode(error.code)
            except ValueError:
                code = ErrorCode.UNAVAILABLE
            raise StoreRejected(code) from None

    def _failed(self, authorization):
        try:
            with self._authorization._session() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(FINISH_SQL, (_claims_json(authorization._assertion), "failed"))
                    if _row(cursor, 1)[0] is not True:
                        raise OnboardingRejected("invalid_record")
        except Exception:
            # No command retry. Missing failure audit never rearms the consume,
            # and acknowledged/unknown successful completion cannot be overwritten.
            pass

    def apply(self, action, *, token, body):
        authorization = None
        try:
            authorization = self._authorization.consume(action, token=token, body=body)
            account, connection, revision, storage, credentials, _ = _request(action, body)
            assertion = authorization._assertion
            authority = DemoStoreAuthority(self._context, auth_epoch=assertion.auth_epoch,
                auth_time_ms=assertion.oidc_auth_time*1000, expires_ms=assertion.exp*1000)
            if action == "register":
                owner = OwnerContext(self._context.tenant_id, self._context.user_id)
                spec = self._provision(credentials, owner=owner, account_id=account,
                    connection_id=connection, expires_ms=authority.expires_ms)
                if (type(spec) is not DemoSecretSpec or spec.binding.owner != owner
                        or spec.binding.account_id != account
                        or spec.binding.credential_ref != connection
                        or spec.credential_revision != 1 or spec.egress_ip != self._ip):
                    raise OnboardingRejected("broker_rejected")
                keyring = self._keyring()
                if type(keyring) is not KEKRing:
                    raise OnboardingRejected("key_unavailable")
            guarded = DemoCredentialStore(authority,
                connect=lambda: self._final_connection(authorization))
            if action == "register":
                written = guarded.register(spec, credentials, keyring)
                return OnboardingResult(connection, 1, written.storage_version, "active")
            version = guarded.revoke(connection, expected_revision=revision, expected_storage=storage)
            return OnboardingResult(connection, revision, version, "revoked")
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
