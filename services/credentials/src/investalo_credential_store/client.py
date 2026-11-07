"""Fixed-function credential persistence with database-authenticated ownership."""
from __future__ import annotations

from contextlib import contextmanager
import json
from typing import Callable, ContextManager, Protocol
from uuid import UUID

from investalo_credentials import (
    AADBinding, EnvelopeRejected, KEKRing, SecretPayload, MAX_DOCUMENT_BYTES,
    dump_envelope, load_envelope, open_envelope, rewrap as rewrap_envelope, seal,
)
from .models import ErrorCode, OpenedCredential, StoreContext, StoredSnapshot, StoreRejected


class Cursor(Protocol):
    def execute(self, query: str, params: tuple = ()) -> object: ...
    def fetchone(self) -> tuple | None: ...
    def __enter__(self) -> Cursor: ...
    def __exit__(self, exc_type, exc_value, traceback) -> object: ...


class Connection(Protocol):
    autocommit: bool
    def cursor(self) -> ContextManager[Cursor]: ...


ConnectFactory = Callable[[], ContextManager[Connection]]

# No dynamic identifiers. Only this metadata projection and agreed functions.
ROLE_SQL = """SELECT session_user, current_user, rolsuper, rolcreaterole,
rolcreatedb, rolreplication, rolbypassrls, rolcanlogin
FROM pg_catalog.pg_roles WHERE rolname = session_user"""
CONTEXT_SQL = "SELECT tenant_id, user_id FROM platform.credential_context()"
COLUMNS = ("tenant_id, user_id, platform_account_id, connection_id, broker_uid, parent_uid, "
           "broker, account_family, connection_mode, credential_revision, storage_version, status, envelope")
CREATE_SQL = f"SELECT {COLUMNS} FROM platform.credential_create(%s, %s, %s, %s, %s::jsonb)"
READ_SQL = f"SELECT {COLUMNS} FROM platform.credential_read(%s)"
REPLACE_SQL = f"SELECT {COLUMNS} FROM platform.credential_replace(%s, %s, %s, %s::jsonb)"
REWRAP_SQL = f"SELECT {COLUMNS} FROM platform.credential_rewrap(%s, %s, %s, %s::jsonb)"
REVOKE_SQL = "SELECT platform.credential_revoke(%s, %s, %s)"


def _db_error(error: Exception) -> ErrorCode:
    try:
        state = getattr(error, "sqlstate", None)
        if type(state) is str and len(state) == 5:
            return {"42501": ErrorCode.ACCESS_DENIED, "40001": ErrorCode.CONCURRENT_CHANGE,
                    "23505": ErrorCode.IDENTITY_CONFLICT, "22023": ErrorCode.INVALID_RECORD}.get(
                        state, ErrorCode.UNAVAILABLE)
    except Exception:
        pass
    return ErrorCode.UNAVAILABLE


def _crypto_error(error: EnvelopeRejected) -> ErrorCode:
    return {"authentication_failed": ErrorCode.AUTHENTICATION_FAILED,
            "key_unavailable": ErrorCode.KEY_UNAVAILABLE,
            "crypto_failure": ErrorCode.CRYPTO_FAILURE}.get(error.code.value, ErrorCode.INVALID_RECORD)


def _row(cursor: Cursor, count: int) -> tuple:
    row = cursor.fetchone()
    if not isinstance(row, tuple) or len(row) != count or cursor.fetchone() is not None:
        raise StoreRejected(ErrorCode.INVALID_RECORD) from None
    return row


def _versions(revision: int, storage: int):
    if (type(revision) is not int or type(storage) is not int
            or not 1 <= revision <= 2**63 - 1 or not 1 <= storage < 2**63 - 1):
        raise StoreRejected(ErrorCode.INVALID_RECORD) from None


def _same_binding(left: AADBinding, right: AADBinding) -> bool:
    return all(getattr(left, field) == getattr(right, field) for field in (
        "tenant_id", "user_id", "platform_account_id", "connection_id", "broker_uid",
        "parent_uid", "credential_revision", "broker", "account_family", "connection_mode"))


def _next_binding(old: AADBinding) -> AADBinding:
    if old.credential_revision == 2**63 - 1:
        raise StoreRejected(ErrorCode.INVALID_RECORD) from None
    return AADBinding(
        tenant_id=old.tenant_id, user_id=old.user_id, platform_account_id=old.platform_account_id,
        connection_id=old.connection_id, broker_uid=old.broker_uid, parent_uid=old.parent_uid,
        credential_revision=old.credential_revision + 1,
        broker=old.broker, account_family=old.account_family, connection_mode=old.connection_mode)


def _db_envelope(value: object):
    expected = {"schema_version", "kek_id", "payload_nonce", "wrap_nonce", "wrapped_dek", "ciphertext"}
    if (not isinstance(value, dict) or set(value) != expected
            or any(type(part) is not str or len(part) > MAX_DOCUMENT_BYTES for part in value.values())):
        raise StoreRejected(ErrorCode.INVALID_RECORD) from None
    return load_envelope(json.dumps(value, ensure_ascii=True, separators=(",", ":"), allow_nan=False))


class CredentialStore:
    __slots__ = ("_context", "_keyring", "_connect")

    def __init__(self, context: StoreContext, keyring: KEKRing, *, connect: ConnectFactory):
        if not isinstance(context, StoreContext) or not callable(connect):
            raise StoreRejected(ErrorCode.INVALID_CONTEXT) from None
        if not isinstance(keyring, KEKRing):
            raise StoreRejected(ErrorCode.INVALID_RECORD) from None
        self._context = context
        self._keyring = keyring
        self._connect = connect

    def __repr__(self):
        return "CredentialStore(<redacted>)"

    __str__ = __repr__

    def __reduce_ex__(self, protocol):
        raise TypeError("Private object serialization denied")

    @contextmanager
    def _session(self):
        try:
            # Factory supplies a fresh non-autocommit transactional connection.
            # Its context manager commits on success, rolls back on failure and
            # closes/releases the connection; the client never accepts a DSN.
            with self._connect() as connection:
                if connection.autocommit is not False:
                    raise StoreRejected(ErrorCode.INVALID_CONTEXT) from None
                with connection.cursor() as cursor:
                    cursor.execute(ROLE_SQL)
                    role = _row(cursor, 8)
                    if (role[:2] != (self._context.expected_login_role,) * 2
                            or any(type(flag) is not bool for flag in role[2:])
                            or any(role[2:7]) or role[7] is not True):
                        raise StoreRejected(ErrorCode.ACCESS_DENIED) from None
                    cursor.execute(CONTEXT_SQL)
                    tenant, user = _row(cursor, 2)
                    if (not isinstance(tenant, UUID) or not isinstance(user, UUID)
                            or (tenant, user) != (self._context.tenant_id, self._context.user_id)):
                        raise StoreRejected(ErrorCode.ACCESS_DENIED) from None
                    yield cursor
        except StoreRejected:
            raise
        except EnvelopeRejected as error:
            raise StoreRejected(_crypto_error(error)) from None
        except Exception as error:
            raise StoreRejected(_db_error(error)) from None

    def _snapshot(self, cursor: Cursor, expected_connection: UUID) -> StoredSnapshot:
        row = _row(cursor, 13)
        tenant, user, account, connection, uid, parent, broker, family, mode, revision, storage, status, raw = row
        if (tenant != self._context.tenant_id or user != self._context.user_id
                or connection != expected_connection):
            raise StoreRejected(ErrorCode.ACCESS_DENIED) from None
        if status != "active":
            raise StoreRejected(ErrorCode.ACCESS_DENIED) from None
        binding = AADBinding(tenant_id=tenant, user_id=user, platform_account_id=account,
                             connection_id=connection, broker_uid=uid, parent_uid=parent,
                             broker=broker, account_family=family, connection_mode=mode,
                             credential_revision=revision)
        return StoredSnapshot(binding, storage, _db_envelope(raw))

    @staticmethod
    def _connection_id(value: UUID):
        if not isinstance(value, UUID):
            raise StoreRejected(ErrorCode.INVALID_RECORD) from None

    def _read(self, cursor: Cursor, connection_id: UUID) -> StoredSnapshot:
        cursor.execute(READ_SQL, (connection_id,))
        return self._snapshot(cursor, connection_id)

    @staticmethod
    def _verify_written(actual: StoredSnapshot, expected_binding: AADBinding,
                        expected_storage: int, expected_envelope):
        if (not _same_binding(actual.binding, expected_binding)
                or actual.storage_version != expected_storage
                or dump_envelope(actual.envelope) != dump_envelope(expected_envelope)):
            raise StoreRejected(ErrorCode.INVALID_RECORD) from None

    def register(self, binding: AADBinding, payload: SecretPayload) -> StoredSnapshot:
        if (not isinstance(binding, AADBinding) or not isinstance(payload, SecretPayload)
                or binding.credential_revision != 1):
            raise StoreRejected(ErrorCode.INVALID_RECORD) from None
        if (binding.tenant_id, binding.user_id) != (self._context.tenant_id, self._context.user_id):
            raise StoreRejected(ErrorCode.ACCESS_DENIED) from None
        with self._session() as cursor:
            encrypted = seal(payload, binding, self._keyring)
            cursor.execute(CREATE_SQL, (binding.platform_account_id, binding.connection_id,
                                       binding.broker_uid, binding.parent_uid, dump_envelope(encrypted)))
            actual = self._snapshot(cursor, binding.connection_id)
            self._verify_written(actual, binding, 1, encrypted)
            return actual

    def read(self, connection_id: UUID) -> OpenedCredential:
        self._connection_id(connection_id)
        with self._session() as cursor:
            current = self._read(cursor, connection_id)
            return OpenedCredential(current, open_envelope(current.envelope, current.binding, self._keyring))

    @staticmethod
    def _expected(current: StoredSnapshot, revision: int, storage: int):
        if current.binding.credential_revision != revision or current.storage_version != storage:
            raise StoreRejected(ErrorCode.CONCURRENT_CHANGE) from None

    def replace(self, connection_id: UUID, *, expected_revision: int, expected_storage: int,
                payload: SecretPayload) -> StoredSnapshot:
        self._connection_id(connection_id)
        _versions(expected_revision, expected_storage)
        if not isinstance(payload, SecretPayload):
            raise StoreRejected(ErrorCode.INVALID_RECORD) from None
        with self._session() as cursor:
            current = self._read(cursor, connection_id)
            self._expected(current, expected_revision, expected_storage)
            # Authenticate the complete current record before any new sealing.
            open_envelope(current.envelope, current.binding, self._keyring)
            revised = _next_binding(current.binding)
            encrypted = seal(payload, revised, self._keyring)
            cursor.execute(REPLACE_SQL, (connection_id, expected_revision, expected_storage,
                                        dump_envelope(encrypted)))
            actual = self._snapshot(cursor, connection_id)
            self._verify_written(actual, revised, expected_storage + 1, encrypted)
            return actual

    def rewrap(self, connection_id: UUID, *, expected_revision: int, expected_storage: int) -> StoredSnapshot:
        self._connection_id(connection_id)
        _versions(expected_revision, expected_storage)
        with self._session() as cursor:
            current = self._read(cursor, connection_id)
            self._expected(current, expected_revision, expected_storage)
            encrypted = rewrap_envelope(current.envelope, current.binding, self._keyring)
            cursor.execute(REWRAP_SQL, (connection_id, expected_revision, expected_storage,
                                       dump_envelope(encrypted)))
            actual = self._snapshot(cursor, connection_id)
            self._verify_written(actual, current.binding, expected_storage + 1, encrypted)
            return actual

    def revoke(self, connection_id: UUID, *, expected_revision: int, expected_storage: int) -> int:
        self._connection_id(connection_id)
        _versions(expected_revision, expected_storage)
        with self._session() as cursor:
            # No read/decrypt prerequisite: SQL permits protective revocation
            # even when a paused account prevents credential reads.
            cursor.execute(REVOKE_SQL, (connection_id, expected_revision, expected_storage))
            result, = _row(cursor, 1)
            if type(result) is not int or result != expected_storage + 1:
                raise StoreRejected(ErrorCode.INVALID_RECORD) from None
            return result
