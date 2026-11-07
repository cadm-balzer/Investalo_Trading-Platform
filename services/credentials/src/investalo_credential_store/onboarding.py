"""Trusted-service Bitget onboarding, one-use authorization and atomic final writes."""
from __future__ import annotations

from contextlib import contextmanager
import json

from investalo_bitget import ClassicReadClient, Credentials, OwnerContext, AccountBinding, BitgetRejected
from investalo_bitget.models import address
from investalo_credentials import AADBinding, KEKRing

from .bitget_payload import encode_credentials
from .client import CredentialStore, ConnectFactory, _db_error, _row
from .models import StoreContext, StoreRejected, _PrivateImmutable
from .request_assertion import RequestVerifier, OnboardingRejected, _object, _uuid

BEGIN_SQL = "SELECT platform.credential_begin_request(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
LOCK_SQL = "SELECT platform.credential_lock_request(%s,%s,%s,%s,%s,%s)"
FINISH_SQL = "SELECT platform.credential_finish_request(%s,%s)"


class OnboardingResult(_PrivateImmutable):
    """Explicit public projection contains no credentials, UID, KEK or ciphertext."""
    __slots__ = ("connection_id", "credential_revision", "storage_version", "status")

    def __init__(self, connection_id, credential_revision, storage_version, status):
        for name, value in locals().copy().items():
            if name != "self":
                object.__setattr__(self, name, value)

    def public(self) -> dict:
        return {
            "connection_id": str(self.connection_id), "credential_revision": self.credential_revision,
            "storage_version": self.storage_version, "status": self.status,
        }


def _request(action, raw):
    try:
        body = json.loads(raw.decode("utf-8"), object_pairs_hook=_object,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        fields = {"platform_account_id", "connection_id"}
        if action in ("replace", "revoke"):
            fields |= {"expected_revision", "expected_storage"}
        if action != "revoke":
            fields.add("credentials")
        if type(body) is not dict or set(body) != fields:
            raise ValueError()
        account, connection = _uuid(body["platform_account_id"]), _uuid(body["connection_id"])
        revision, storage = body.get("expected_revision"), body.get("expected_storage")
        if action != "register" and (
            type(revision) is not int or type(storage) is not int
            or not 1 <= revision < 2**63 or not 1 <= storage < 2**63 - 1
        ):
            raise ValueError()
        credentials = payload = None
        if action != "revoke":
            triple = body["credentials"]
            if type(triple) is not dict or set(triple) != {"api_key", "secret", "passphrase"}:
                raise ValueError()
            credentials = Credentials(triple["api_key"], triple["secret"], triple["passphrase"])
            payload = encode_credentials(credentials)
        return account, connection, revision, storage, credentials, payload
    except Exception:
        raise OnboardingRejected("invalid_request") from None


class BitgetOnboarding(_PrivateImmutable):
    __slots__ = ("_context", "_keyring", "_connect", "_verifier", "_transport", "_ip", "_store")

    def __init__(self, context: StoreContext, keyring: KEKRing, *, connect: ConnectFactory,
                 verifier: RequestVerifier, transport, expected_egress_ip: str):
        try:
            if not isinstance(verifier, RequestVerifier) or not callable(transport):
                raise ValueError()
            store = CredentialStore(context, keyring, connect=connect)
            ip = address(expected_egress_ip)
        except Exception:
            raise OnboardingRejected("invalid_context") from None
        for name, value in (("_context", context), ("_keyring", keyring), ("_connect", connect),
                            ("_verifier", verifier), ("_transport", transport),
                            ("_ip", ip), ("_store", store)):
            object.__setattr__(self, name, value)

    def _begin(self, assertion, action, account, connection, revision, storage):
        with self._store._session() as cursor:
            cursor.execute(BEGIN_SQL, (
                assertion.nonce, assertion.issuer, assertion.subject, assertion.auth_epoch,
                assertion.auth_time, assertion.started_at, assertion.expires_at,
                action, account, connection, revision, storage,
            ))
            if _row(cursor, 1) != (assertion.nonce,):
                raise OnboardingRejected("invalid_record") from None

    @contextmanager
    def _final_connection(self, assertion, action, account, connection_id, revision, storage):
        with self._connect() as connection:
            if connection.autocommit is not False:
                raise OnboardingRejected("invalid_context") from None
            with connection.cursor() as cursor:
                cursor.execute(LOCK_SQL, (assertion.nonce, action, account, connection_id, revision, storage))
                if _row(cursor, 1)[0] is not True:
                    raise OnboardingRejected("invalid_record") from None
            yield connection
            with connection.cursor() as cursor:
                cursor.execute(FINISH_SQL, (assertion.nonce, "completed"))
                if _row(cursor, 1)[0] is not True:
                    raise OnboardingRejected("invalid_record") from None

    def _failed(self, nonce):
        try:
            with self._store._session() as cursor:
                cursor.execute(FINISH_SQL, (nonce, "failed"))
                _row(cursor, 1)
        except Exception:
            # A committed begin remains consumed even if failure finalization is
            # unavailable or a completed-but-unacknowledged commit already exists.
            # Do not overwrite the original static error or retry the mutation.
            pass

    def apply(self, action: str, *, token: str, body: bytes) -> OnboardingResult:
        assertion = self._verifier.verify(token, action=action, body=body)
        account, connection, revision, storage, credentials, payload = _request(action, body)
        if assertion.tenant_id != self._context.tenant_id:
            raise OnboardingRejected("access_denied") from None
        begun = False
        try:
            self._begin(assertion, action, account, connection, revision, storage)
            begun = True
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
                # Onboarding is stricter than the general adapter: no additional
                # unapproved whitelist addresses, no client-supplied egress IP.
                if probe.ip_whitelist != (self._ip,):
                    raise OnboardingRejected("broker_rejected") from None
                if old is not None:
                    AccountBinding(owner, old.binding.broker_uid, old.binding.parent_uid,
                                   expected_egress_ip=self._ip).validate(owner, probe, require_ip=True)
            factory = lambda: self._final_connection(assertion, action, account, connection, revision, storage)
            guarded = CredentialStore(self._context, self._keyring, connect=factory)
            if action == "register":
                binding = AADBinding(
                    tenant_id=self._context.tenant_id, user_id=self._context.user_id,
                    platform_account_id=account, connection_id=connection,
                    broker_uid=probe.user_id, parent_uid=probe.parent_id, credential_revision=1,
                )
                written = guarded.register(binding, payload)
            elif action == "replace":
                written = guarded.replace(connection, expected_revision=revision, expected_storage=storage, payload=payload)
            else:
                version = guarded.revoke(connection, expected_revision=revision, expected_storage=storage)
                return OnboardingResult(connection, revision, version, "revoked")
            return OnboardingResult(connection, written.binding.credential_revision, written.storage_version, "active")
        except Exception as error:
            if begun:
                self._failed(assertion.nonce)
            if isinstance(error, OnboardingRejected):
                raise error from None
            if isinstance(error, BitgetRejected):
                raise OnboardingRejected("broker_rejected") from None
            if isinstance(error, StoreRejected):
                raise OnboardingRejected(error.code.value) from None
            raise OnboardingRejected(_db_error(error).value) from None
