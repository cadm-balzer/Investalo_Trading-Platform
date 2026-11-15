"""Dedicated Demo SQL store primitives; no passkey executor or HTTP activation."""
from contextlib import contextmanager
import time
from uuid import UUID

from investalo_bitget.futures_demo import DemoBinding, clock
from investalo_bitget.models import OwnerContext
from investalo_credentials import KEKRing, dump_envelope

from .client import ROLE_SQL, _row, _db_error, _db_envelope, _versions
from .demo_secret_provider import (
    PROFILE, DemoSecretRejected, DemoSecretSpec, DemoSecretSnapshot,
    seal_demo_secret, rewrap_demo_secret, SealedDemoReadProvider,
)
from .models import _PrivateImmutable, StoreContext, StoreRejected, ErrorCode

CONTEXT_SQL = "SELECT tenant_id,user_id FROM platform.demo_credential_context(%s,%s,%s)"
COLUMNS = ("tenant_id,user_id,platform_account_id,connection_id,broker_uid,parent_uid,"
           "environment,api_family,position_mode,leverage,profile,connection_mode,egress_ip,"
           "provisioning_digest,credential_revision,storage_version,status,envelope")
CREATE_SQL = f"SELECT {COLUMNS} FROM platform.demo_credential_create(%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s)"
READ_SQL = f"SELECT {COLUMNS} FROM platform.demo_credential_read(%s,%s,%s,%s)"
REWRAP_SQL = f"SELECT {COLUMNS} FROM platform.demo_credential_rewrap(%s,%s,%s,%s::jsonb,%s,%s,%s)"
REVOKE_SQL = "SELECT platform.demo_credential_revoke(%s,%s,%s,%s,%s,%s)"


class DemoStoreAuthority(_PrivateImmutable):
    """Trusted original session claims, independently authenticated by service."""
    __slots__ = ("context", "auth_epoch", "auth_time_ms", "expires_ms")

    def __init__(self, context, *, auth_epoch, auth_time_ms, expires_ms):
        try:
            if (type(context) is not StoreContext or type(auth_epoch) is not int
                    or not 0 <= auth_epoch <= 10**15):
                raise ValueError()
            clock(auth_time_ms)
            clock(expires_ms)
            if expires_ms <= auth_time_ms:
                raise ValueError()
            for field, value in (("context", context), ("auth_epoch", auth_epoch),
                                 ("auth_time_ms", auth_time_ms), ("expires_ms", expires_ms)):
                object.__setattr__(self, field, value)
        except Exception:
            raise StoreRejected(ErrorCode.INVALID_CONTEXT) from None

    def arguments(self):
        return (self.auth_epoch, self.auth_time_ms, self.expires_ms)


class DemoCredentialStore(_PrivateImmutable):
    __slots__ = ("_authority", "_connect")

    def __init__(self, authority, *, connect):
        if type(authority) is not DemoStoreAuthority or not callable(connect):
            raise StoreRejected(ErrorCode.INVALID_CONTEXT) from None
        object.__setattr__(self, "_authority", authority)
        object.__setattr__(self, "_connect", connect)

    @contextmanager
    def _session(self):
        try:
            context = self._authority.context
            with self._connect() as connection:
                if connection.autocommit is not False:
                    raise StoreRejected(ErrorCode.INVALID_CONTEXT)
                with connection.cursor() as cursor:
                    cursor.execute(ROLE_SQL)
                    role = _row(cursor, 8)
                    if (role[:2] != (context.expected_login_role,) * 2
                            or any(type(flag) is not bool for flag in role[2:])
                            or any(role[2:7]) or role[7] is not True):
                        raise StoreRejected(ErrorCode.ACCESS_DENIED)
                    cursor.execute(CONTEXT_SQL, self._authority.arguments())
                    if _row(cursor, 2) != (context.tenant_id, context.user_id):
                        raise StoreRejected(ErrorCode.ACCESS_DENIED)
                    yield cursor
                    # Recheck real epoch/reauth/time before final transaction completion.
                    cursor.execute(CONTEXT_SQL, self._authority.arguments())
                    if _row(cursor, 2) != (context.tenant_id, context.user_id):
                        raise StoreRejected(ErrorCode.ACCESS_DENIED)
        except StoreRejected:
            raise
        except DemoSecretRejected:
            raise StoreRejected(ErrorCode.AUTHENTICATION_FAILED) from None
        except Exception as error:
            raise StoreRejected(_db_error(error)) from None

    def _binding(self, binding):
        context = self._authority.context
        if type(binding) is not DemoBinding:
            raise StoreRejected(ErrorCode.INVALID_RECORD)
        if (binding.owner.tenant_id, binding.owner.user_id) != (context.tenant_id, context.user_id):
            raise StoreRejected(ErrorCode.ACCESS_DENIED)

    def _snapshot(self, cursor, binding):
        row = _row(cursor, 18)
        tenant, user, account, connection, uid, parent, env, family, mode, lev, profile, purpose, ip, prov, rev, storage, status, raw = row
        self._binding(binding)
        if (type(tenant) is not UUID or type(user) is not UUID
                or type(account) is not UUID or type(connection) is not UUID
                or type(lev) is not int or type(rev) is not int or rev != 1
                or status != "active" or profile != PROFILE or purpose != "demo_read_only"):
            raise StoreRejected(ErrorCode.INVALID_RECORD)
        actual = DemoBinding(OwnerContext(tenant, user), account, connection, uid,
                             environment=env, api_family=family, position_mode=mode, leverage=lev)
        if actual != binding:
            raise StoreRejected(ErrorCode.ACCESS_DENIED)
        spec = DemoSecretSpec(binding=actual, parent_uid=parent, egress_ip=ip,
                              provisioning_digest=prov, credential_revision=rev)
        return DemoSecretSnapshot(spec, _db_envelope(raw), storage_version=storage)

    @staticmethod
    def _written(actual, spec, storage, envelope):
        if (actual.spec.record() != spec.record() or actual.storage_version != storage
                or dump_envelope(actual.envelope) != dump_envelope(envelope)):
            raise StoreRejected(ErrorCode.INVALID_RECORD)

    def register(self, spec, credentials, keyring):
        """Private trusted provisioning only; does not prove consent/key provenance."""
        if type(spec) is not DemoSecretSpec or spec.credential_revision != 1:
            raise StoreRejected(ErrorCode.INVALID_RECORD)
        self._binding(spec.binding)
        with self._session() as cursor:
            encrypted = seal_demo_secret(credentials, spec, keyring)
            b = spec.binding
            cursor.execute(CREATE_SQL, (b.account_id, b.credential_ref, b.broker_uid, spec.parent_uid,
                spec.egress_ip, spec.provisioning_digest, dump_envelope(encrypted), *self._authority.arguments()))
            actual = self._snapshot(cursor, b)
            self._written(actual, spec, 1, encrypted)
            return actual

    def read_snapshot(self, binding, context):
        self._binding(binding)
        if type(context) is not OwnerContext or context != binding.owner:
            raise StoreRejected(ErrorCode.ACCESS_DENIED)
        with self._session() as cursor:
            cursor.execute(READ_SQL, (binding.credential_ref, *self._authority.arguments()))
            return self._snapshot(cursor, binding)

    def provider(self, expected_spec, *, expected_storage, load_keyring,
                 milliseconds=lambda: time.time_ns() // 1_000_000):
        if type(expected_spec) is not DemoSecretSpec:
            raise StoreRejected(ErrorCode.INVALID_RECORD)
        self._binding(expected_spec.binding)
        return SealedDemoReadProvider(expected_spec, expected_storage=expected_storage,
            read_snapshot=self.read_snapshot, load_keyring=load_keyring,
            expires_ms=self._authority.expires_ms, milliseconds=milliseconds)

    def rewrap(self, expected_spec, *, expected_storage, keyring):
        if type(expected_spec) is not DemoSecretSpec or type(keyring) is not KEKRing:
            raise StoreRejected(ErrorCode.INVALID_RECORD)
        self._binding(expected_spec.binding)
        _versions(expected_spec.credential_revision, expected_storage)
        with self._session() as cursor:
            binding = expected_spec.binding
            cursor.execute(READ_SQL, (binding.credential_ref, *self._authority.arguments()))
            current = self._snapshot(cursor, binding)
            if (current.spec.record() != expected_spec.record() or current.storage_version != expected_storage):
                raise StoreRejected(ErrorCode.CONCURRENT_CHANGE)
            encrypted = rewrap_demo_secret(current.envelope, expected_spec, keyring)
            cursor.execute(REWRAP_SQL, (binding.credential_ref, expected_spec.credential_revision,
                expected_storage, dump_envelope(encrypted), *self._authority.arguments()))
            actual = self._snapshot(cursor, binding)
            self._written(actual, expected_spec, expected_storage + 1, encrypted)
            return actual

    def revoke(self, connection_id, *, expected_revision, expected_storage):
        """Protect an owned connection by its exact ID, without reading secrets."""
        if type(connection_id) is not UUID:
            raise StoreRejected(ErrorCode.INVALID_RECORD)
        _versions(expected_revision, expected_storage)
        with self._session() as cursor:
            cursor.execute(REVOKE_SQL, (connection_id, expected_revision, expected_storage,
                                       *self._authority.arguments()))
            result, = _row(cursor, 1)
            if type(result) is not int or result != expected_storage + 1:
                raise StoreRejected(ErrorCode.INVALID_RECORD)
            return result
