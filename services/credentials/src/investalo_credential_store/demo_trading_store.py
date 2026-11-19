"""Own trading-purpose SQL adapter; no HTTP intake or passkey authority."""
from contextlib import contextmanager
import json
from uuid import UUID

from investalo_bitget.futures_demo import DemoBinding
from investalo_bitget.models import OwnerContext
from investalo_credentials import KEKRing, dump_envelope

from .client import _db_envelope, _row, _versions
from .demo_store import COLUMNS as READ_COLUMNS, DemoCredentialStore
from .demo_trading_provider import DemoTradingSecretSnapshot, SealedDemoTradingProvider
from .demo_trading_secret import (
    PROFILE, PURPOSE, DemoTradingSecretSpec, DemoTradingSecretRejected,
    seal_demo_trading_secret, rewrap_demo_trading_secret,
)
from .models import StoreRejected, ErrorCode

COLUMNS = READ_COLUMNS + ",authorities"
CREATE_SQL = f"SELECT {COLUMNS} FROM platform.demo_trading_credential_create(%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s)"
READ_SQL = f"SELECT {COLUMNS} FROM platform.demo_trading_credential_read(%s,%s,%s,%s)"
REWRAP_SQL = f"SELECT {COLUMNS} FROM platform.demo_trading_credential_rewrap(%s,%s,%s,%s::jsonb,%s,%s,%s)"
REVOKE_SQL = "SELECT platform.demo_trading_credential_revoke(%s,%s,%s,%s,%s,%s)"


class DemoTradingCredentialStore(DemoCredentialStore):
    """Share actual restricted LOGIN/current-context checks, never read-purpose CRUD."""
    __slots__ = ()

    @contextmanager
    def _session(self):
        with super()._session() as cursor:
            try:
                yield cursor
            except DemoTradingSecretRejected:
                raise StoreRejected(ErrorCode.AUTHENTICATION_FAILED) from None

    def _snapshot(self, cursor, binding):
        row = _row(cursor, 19)
        tenant, user, account, connection, uid, parent, env, family, mode, lev, profile, purpose, ip, prov, rev, storage, status, raw, rights = row
        self._binding(binding)
        if (any(type(value) is not UUID for value in (tenant, user, account, connection))
                or type(lev) is not int or type(rev) is not int or rev != 1
                or status != "active" or profile != PROFILE or purpose != PURPOSE):
            raise StoreRejected(ErrorCode.INVALID_RECORD)
        actual = DemoBinding(OwnerContext(tenant, user), account, connection, uid,
                             environment=env, api_family=family, position_mode=mode, leverage=lev)
        if actual != binding:
            raise StoreRejected(ErrorCode.ACCESS_DENIED)
        spec = DemoTradingSecretSpec(binding=actual, parent_uid=parent, egress_ip=ip,
            authorities=rights, provisioning_digest=prov, credential_revision=rev)
        return DemoTradingSecretSnapshot(spec, _db_envelope(raw), storage_version=storage)

    def register(self, spec, credentials, keyring):
        if type(spec) is not DemoTradingSecretSpec or spec.credential_revision != 1:
            raise StoreRejected(ErrorCode.INVALID_RECORD)
        self._binding(spec.binding)
        with self._session() as cursor:
            encrypted = seal_demo_trading_secret(credentials, spec, keyring)
            b = spec.binding
            cursor.execute(CREATE_SQL, (b.account_id, b.credential_ref, b.broker_uid, spec.parent_uid,
                spec.egress_ip, spec.provisioning_digest, json.dumps(list(spec.authorities)),
                dump_envelope(encrypted), *self._authority.arguments()))
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

    def provider(self, expected_spec, *, expected_storage, load_keyring, milliseconds=None):
        if type(expected_spec) is not DemoTradingSecretSpec:
            raise StoreRejected(ErrorCode.INVALID_RECORD)
        self._binding(expected_spec.binding)
        kwargs = {} if milliseconds is None else {"milliseconds": milliseconds}
        return SealedDemoTradingProvider(expected_spec, expected_storage=expected_storage,
            read_snapshot=self.read_snapshot, load_keyring=load_keyring,
            expires_ms=self._authority.expires_ms, **kwargs)

    def rewrap(self, expected_spec, *, expected_storage, keyring):
        if type(expected_spec) is not DemoTradingSecretSpec or type(keyring) is not KEKRing:
            raise StoreRejected(ErrorCode.INVALID_RECORD)
        self._binding(expected_spec.binding)
        _versions(expected_spec.credential_revision, expected_storage)
        with self._session() as cursor:
            binding = expected_spec.binding
            cursor.execute(READ_SQL, (binding.credential_ref, *self._authority.arguments()))
            current = self._snapshot(cursor, binding)
            if current.spec.record() != expected_spec.record() or current.storage_version != expected_storage:
                raise StoreRejected(ErrorCode.CONCURRENT_CHANGE)
            encrypted = rewrap_demo_trading_secret(current.envelope, expected_spec, keyring)
            cursor.execute(REWRAP_SQL, (binding.credential_ref, expected_spec.credential_revision,
                expected_storage, dump_envelope(encrypted), *self._authority.arguments()))
            actual = self._snapshot(cursor, binding)
            self._written(actual, expected_spec, expected_storage + 1, encrypted)
            return actual

    def revoke(self, connection_id, *, expected_revision, expected_storage):
        if type(connection_id) is not UUID:
            raise StoreRejected(ErrorCode.INVALID_RECORD)
        _versions(expected_revision, expected_storage)
        with self._session() as cursor:
            cursor.execute(REVOKE_SQL, (connection_id, expected_revision, expected_storage,
                                       *self._authority.arguments()))
            version, = _row(cursor, 1)
            if type(version) is not int or version != expected_storage + 1:
                raise StoreRejected(ErrorCode.INVALID_RECORD)
            return version
