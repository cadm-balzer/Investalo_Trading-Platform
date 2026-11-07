"""Private immutable store models, static errors, no browser-facing serializer."""
from enum import StrEnum
import re
from uuid import UUID

from investalo_credentials import AADBinding, Envelope, SecretPayload


class ErrorCode(StrEnum):
    INVALID_CONTEXT = "invalid_context"
    ACCESS_DENIED = "access_denied"
    INVALID_RECORD = "invalid_record"
    CONCURRENT_CHANGE = "concurrent_change"
    IDENTITY_CONFLICT = "identity_conflict"
    UNAVAILABLE = "unavailable"
    AUTHENTICATION_FAILED = "authentication_failed"
    KEY_UNAVAILABLE = "key_unavailable"
    CRYPTO_FAILURE = "crypto_failure"


class StoreRejected(ValueError):
    def __init__(self, code: ErrorCode):
        if not isinstance(code, ErrorCode):
            code = ErrorCode.UNAVAILABLE
        self.code = code
        super().__init__(code.value)


class _PrivateImmutable:
    __slots__ = ()

    def __setattr__(self, name, value):
        raise AttributeError("Immutable private object")

    def __repr__(self):
        return type(self).__name__ + "(<redacted>)"

    __str__ = __repr__

    def __reduce_ex__(self, protocol):
        raise TypeError("Private object serialization denied")


class StoreContext(_PrivateImmutable):
    __slots__ = ("tenant_id", "user_id", "expected_login_role")

    def __init__(self, *, tenant_id: UUID, user_id: UUID, expected_login_role: str):
        if (not isinstance(tenant_id, UUID) or not isinstance(user_id, UUID)
                or not isinstance(expected_login_role, str) or len(expected_login_role) > 63
                or not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", expected_login_role)):
            raise StoreRejected(ErrorCode.INVALID_CONTEXT) from None
        object.__setattr__(self, "tenant_id", tenant_id)
        object.__setattr__(self, "user_id", user_id)
        object.__setattr__(self, "expected_login_role", expected_login_role)


class StoredSnapshot(_PrivateImmutable):
    __slots__ = ("binding", "storage_version", "envelope", "status")

    def __init__(self, binding: AADBinding, storage_version: int, envelope: Envelope, *, status: str = "active"):
        if (not isinstance(binding, AADBinding) or not isinstance(envelope, Envelope)
                or type(storage_version) is not int or not 1 <= storage_version <= 2**63 - 1
                or status != "active"):
            raise StoreRejected(ErrorCode.INVALID_RECORD) from None
        object.__setattr__(self, "binding", binding)
        object.__setattr__(self, "storage_version", storage_version)
        object.__setattr__(self, "envelope", envelope)
        object.__setattr__(self, "status", status)


class OpenedCredential(_PrivateImmutable):
    __slots__ = ("snapshot", "payload")

    def __init__(self, snapshot: StoredSnapshot, payload: SecretPayload):
        if not isinstance(snapshot, StoredSnapshot) or not isinstance(payload, SecretPayload):
            raise StoreRejected(ErrorCode.INVALID_RECORD) from None
        object.__setattr__(self, "snapshot", snapshot)
        object.__setattr__(self, "payload", payload)
