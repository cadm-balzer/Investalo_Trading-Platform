"""Read-only durable delegation adapter; does not impersonate an OIDC session."""
from contextlib import contextmanager
import time

from investalo_bitget import OwnerContext
from investalo_bitget.futures_demo import DemoBinding, clock
from .client import ROLE_SQL, CONTEXT_SQL, _row, _db_error
from .demo_trading_provider import SealedDemoTradingProvider
from .demo_trading_secret import DemoTradingSecretSpec, DemoTradingSecretRejected
from .demo_trading_store import COLUMNS, DemoTradingCredentialStore
from .demo_worker_authorization import WorkerIntent
from .models import StoreContext, StoreRejected, ErrorCode, _PrivateImmutable

READ_SQL = f"SELECT {COLUMNS} FROM platform.demo_worker_credential_read(%s,%s,%s,%s,%s,%s,%s,%s)"


class DemoWorkerCredentialStore(_PrivateImmutable):
    """Only a verified original worker intent reaches this trusted SQL port."""
    __slots__ = ("_context", "_intent", "_issuer", "_connect", "_guard", "_expires", "_now")

    def __init__(self, context, intent, *, oidc_issuer, connect, control_guard, expires_ms,
                 milliseconds=lambda: time.time_ns() // 1_000_000):
        if (type(context) is not StoreContext or type(intent) is not WorkerIntent
                or (context.tenant_id, context.user_id) != (intent.tenant_id, intent.user_id)
                or type(oidc_issuer) is not str or not oidc_issuer.startswith("https://")
                or not all(callable(p) for p in (connect, control_guard, milliseconds))):
            raise StoreRejected(ErrorCode.INVALID_CONTEXT)
        clock(expires_ms)
        for k, v in dict(_context=context, _intent=intent, _issuer=oidc_issuer,
                         _connect=connect, _guard=control_guard, _expires=expires_ms, _now=milliseconds).items():
            object.__setattr__(self, k, v)

    def _check(self):
        now = clock(self._now())
        if not now < self._expires <= now + 60000:
            raise StoreRejected(ErrorCode.ACCESS_DENIED)
        self._guard(self._intent)

    def _binding(self, binding):
        if type(binding) is not DemoBinding or not self._intent.matches(binding):
            raise StoreRejected(ErrorCode.ACCESS_DENIED)

    # Reuse the exact immutable Trading AEAD/binding/rights row decoder.
    _snapshot = DemoTradingCredentialStore._snapshot

    @contextmanager
    def _session(self):
        try:
            self._check()
            with self._connect() as db:
                if db.autocommit is not False:
                    raise StoreRejected(ErrorCode.INVALID_CONTEXT)
                with db.cursor() as cur:
                    cur.execute(ROLE_SQL)
                    role = _row(cur, 8)
                    if (role[:2] != (self._context.expected_login_role,) * 2
                            or any(type(flag) is not bool for flag in role[2:])
                            or any(role[2:7]) or role[7] is not True):
                        raise StoreRejected(ErrorCode.ACCESS_DENIED)
                    cur.execute(CONTEXT_SQL)
                    if _row(cur, 2) != (self._context.tenant_id, self._context.user_id):
                        raise StoreRejected(ErrorCode.ACCESS_DENIED)
                    yield cur
                    self._check()
        except StoreRejected:
            raise
        except DemoTradingSecretRejected:
            raise StoreRejected(ErrorCode.AUTHENTICATION_FAILED) from None
        except Exception as e:
            raise StoreRejected(_db_error(e)) from None

    def read_snapshot(self, binding, context):
        self._binding(binding)
        if type(context) is not OwnerContext or context != binding.owner:
            raise StoreRejected(ErrorCode.ACCESS_DENIED)
        i = self._intent
        with self._session() as cur:
            args = (binding.credential_ref, i.auth_epoch, i.subject, self._issuer, i.requested_ms,
                    i.credential_revision, i.storage_version, self._expires)
            cur.execute(READ_SQL, args)
            snapshot = self._snapshot(cur, binding)
            # Re-evaluate real actor/key/reauth under the same transaction locks.
            cur.execute(READ_SQL, args)
            latest = self._snapshot(cur, binding)
            if latest.spec.record() != snapshot.spec.record() or latest.storage_version != snapshot.storage_version:
                raise StoreRejected(ErrorCode.CONCURRENT_CHANGE)
            return latest

    def provider(self, expected_spec, *, load_keyring):
        if type(expected_spec) is not DemoTradingSecretSpec:
            raise StoreRejected(ErrorCode.INVALID_RECORD)
        self._binding(expected_spec.binding)
        return SealedDemoTradingProvider(expected_spec, expected_storage=self._intent.storage_version,
            read_snapshot=self.read_snapshot, load_keyring=load_keyring, expires_ms=self._expires,
            milliseconds=self._now)
