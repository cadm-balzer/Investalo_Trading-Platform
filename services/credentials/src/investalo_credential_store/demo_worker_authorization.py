"""Consume original signed Dashboard intent, independently of browser sessions.

The trusted installation supplies only the derived intent key and the isolated
control reader. No OIDC claim is synthesized and no technical BTC grant reused.
The mandatory actor guard must validate current membership/epoch/account/key.
"""
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import fcntl
import hashlib
import hmac
import json
import os
import re
import threading
import time
from uuid import UUID, uuid5

from investalo_bitget.futures_demo import DemoBinding, DemoRejected, SYMBOLS, clock
from investalo_bitget.futures_demo_basket import BasketMarketIntent, BasketExitIntent
from investalo_bitget.futures_demo_registry import _directory, _file, _identity, _named
from investalo_trading.futures_broker_journal import BrokerEntryJournal
from .demo_basket_orders import BasketOrderApproval, basket_journal_intent

INTENT_SCHEMA = "investalo-demo-h1-intent/1"
STATE_SCHEMA = "investalo-demo-h1-consumer/1"
MAX_CONSUMED = 50_000
NAMESPACE = UUID("9b3d369e-eded-42b9-bef5-33e7ba06cd72")


def _object(pairs):
    result = {}
    for k, v in pairs:
        if k in result:
            raise DemoRejected("duplicate_worker_control_field")
        result[k] = v
    return result


def _json(raw):
    return json.loads(raw, object_pairs_hook=_object,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))


def _exact(value, fields):
    if type(value) is not dict or set(value) != set(fields):
        raise DemoRejected("invalid_worker_control_shape")
    return value


def _integer(value, minimum, maximum=9007199254740991):
    if type(value) is not int or not minimum <= value <= maximum:
        raise DemoRejected("invalid_worker_control_integer")
    return value


def _uuid(value):
    if type(value) is not str or str(UUID(value)) != value:
        raise DemoRejected("invalid_worker_control_uuid")
    return UUID(value)


@dataclass(frozen=True, repr=False)
class WorkerIntent:
    tenant_id: UUID
    account_id: UUID
    user_id: UUID
    subject: str
    auth_epoch: int
    connection_id: UUID
    credential_revision: int
    storage_version: int
    revision: int
    action: str
    basket_limit: int
    assets: tuple[str, ...]
    requested_ms: int
    payload_digest: str

    def matches(self, binding):
        return (type(binding) is DemoBinding and
                (self.tenant_id, self.user_id, self.account_id, self.connection_id) ==
                (binding.owner.tenant_id, binding.owner.user_id, binding.account_id, binding.credential_ref))


def verify_worker_intent(raw, key, *, binding, now_ms):
    """Verify exact bytes written by DemoControlStore; never renew their time."""
    try:
        if (type(raw) is not bytes or not 1 <= len(raw) <= 8192
                or type(key) is not bytes or len(key) != 32 or type(binding) is not DemoBinding):
            raise ValueError()
        wire = _exact(_json(raw.decode("utf-8")), ("payload", "mac"))
        payload, mac = wire["payload"], wire["mac"]
        if (type(payload) is not str or type(mac) is not str or not re.fullmatch("[a-f0-9]{64}", mac)
                or not hmac.compare_digest(mac, hmac.new(key, payload.encode(), hashlib.sha256).hexdigest())):
            raise ValueError()
        v = _exact(_json(payload), ("schema", "binding", "revision", "action", "basket_limit", "assets", "requested_at"))
        b = _exact(v["binding"], ("tenant_id", "account_id", "user_id", "subject", "auth_epoch",
                                  "connection_id", "credential_revision", "storage_version"))
        if (v["schema"] != INTENT_SCHEMA or v["action"] not in ("start", "pause")
                or type(b["subject"]) is not str or not 1 <= len(b["subject"]) <= 255
                or type(v["assets"]) is not list or not 1 <= len(v["assets"]) <= len(SYMBOLS)
                or any(type(s) is not str or s not in SYMBOLS for s in v["assets"])
                or v["assets"] != [s for s in sorted(SYMBOLS) if s in v["assets"]]
                or type(v["requested_at"]) is not str):
            raise ValueError()
        at = datetime.fromisoformat(v["requested_at"].replace("Z", "+00:00"))
        if (at.tzinfo != timezone.utc or at.isoformat(timespec="milliseconds").replace("+00:00", "Z") != v["requested_at"]):
            raise ValueError()
        delta = at - datetime(1970, 1, 1, tzinfo=timezone.utc)
        requested = delta.days * 86400000 + delta.seconds * 1000 + delta.microseconds // 1000
        if not 0 < requested <= clock(now_ms) + 5000:
            raise ValueError()
        result = WorkerIntent(
            *(_uuid(b[k]) for k in ("tenant_id", "account_id", "user_id")), b["subject"],
            _integer(b["auth_epoch"], 0, 10**15), _uuid(b["connection_id"]),
            _integer(b["credential_revision"], 1, 1), _integer(b["storage_version"], 1),
            _integer(v["revision"], 1), v["action"], _integer(v["basket_limit"], 3, 7),
            tuple(v["assets"]), requested, hashlib.sha256(payload.encode()).hexdigest())
        if not result.matches(binding):
            raise ValueError()
        return result
    except Exception:
        raise DemoRejected("worker_intent_not_confirmed") from None


class DurableBasketConsumer:
    """Single account, original signed start/pause, durable per-command spend."""

    def __init__(self, root, *, binding, intent_key, read_control, actor_guard, journal,
                 milliseconds=lambda: time.time_ns() // 1_000_000):
        if (type(binding) is not DemoBinding or type(intent_key) is not bytes or len(intent_key) != 32
                or type(journal) is not BrokerEntryJournal
                or not all(callable(p) for p in (read_control, actor_guard, milliseconds))):
            raise DemoRejected("invalid_basket_consumer_installation")
        self.root, self.fd = root, _directory(root)
        self.binding, self.key, self.read, self.guard = binding, intent_key, read_control, actor_guard
        self.journal, self.now, self.pid, self.lock = journal, milliseconds, os.getpid(), threading.RLock()
        self.poisoned = False
        self.lock_fd = _file(self.fd, "lock", os.O_RDWR | os.O_CREAT)

    def close(self):
        with self.lock:
            if self.fd is not None:
                os.close(self.lock_fd)
                os.close(self.fd)
                self.fd = None

    def _root(self):
        if self.fd is None or self.pid != os.getpid() or self.poisoned:
            raise DemoRejected("basket_consumer_closed_forked_or_uncertain")
        current = _directory(self.root)
        try:
            if _identity(current) != _identity(self.fd):
                raise DemoRejected("basket_consumer_root_replaced")
            _named(self.fd, "lock", self.lock_fd)
        finally:
            os.close(current)
        names = os.listdir(self.fd)
        if len(names) > MAX_CONSUMED * 2 + 2 or any(
                n not in ("lock", "state") and not re.fullmatch(r"consumed-[a-f0-9]{64}|accepted-[0-9]{16}-[a-f0-9]{64}", n)
                for n in names):
            raise DemoRejected("basket_consumer_foreign_file_or_capacity")

    @contextmanager
    def _locked(self):
        with self.lock:
            self._root()
            # Do not block behind another account worker; its next poll owns it.
            try:
                fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise DemoRejected("basket_consumer_busy") from None
            try:
                self._root()
                yield
            finally:
                fcntl.flock(self.lock_fd, fcntl.LOCK_UN)

    def _bytes(self, name):
        fd = _file(self.fd, name, os.O_RDONLY)
        try:
            before = os.fstat(fd)
            if not 1 <= before.st_size <= 16384:
                raise DemoRejected("basket_consumer_invalid_file")
            raw = os.read(fd, 16385)
            after = os.fstat(fd)
            _named(self.fd, name, fd)
            if (len(raw) != before.st_size or before.st_size != after.st_size
                    or before.st_mtime_ns != after.st_mtime_ns or before.st_ctime_ns != after.st_ctime_ns):
                raise DemoRejected("basket_consumer_file_changed")
            return raw
        finally:
            os.close(fd)

    def _seal(self, payload):
        text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        mac = hmac.new(self.key, (STATE_SCHEMA + "\0" + text).encode(), hashlib.sha256).hexdigest()
        return json.dumps(dict(payload=text, mac=mac), separators=(",", ":")).encode()

    def _state(self):
        accepted = sorted(n for n in os.listdir(self.fd) if n.startswith("accepted-"))
        try:
            raw = self._bytes("state")
        except FileNotFoundError:
            # A missing checkpoint must not undo a pause even before any order.
            if accepted or any(n.startswith("consumed-") for n in os.listdir(self.fd)):
                raise DemoRejected("basket_consumer_checkpoint_missing")
            return None
        try:
            wire = _exact(_json(raw), ("payload", "mac"))
            value = _exact(_json(wire["payload"]), ("schema", "revision", "digest", "ever_started", "journal_id"))
            if (not hmac.compare_digest(raw, self._seal(value)) or value["schema"] != STATE_SCHEMA
                    or value["journal_id"] != self.journal._header["journal_id"]
                    or type(value["ever_started"]) is not bool
                    or not re.fullmatch("[a-f0-9]{64}", value["digest"])):
                raise ValueError()
            _integer(value["revision"], 1)
            marker = f'accepted-{value["revision"]:016d}-{value["digest"]}'
            if not accepted or accepted[-1] != marker or self._bytes(marker) != raw:
                raise ValueError()
            return value
        except Exception:
            raise DemoRejected("basket_consumer_checkpoint_not_confirmed") from None

    def _write(self, name, raw, *, replace=False):
        # Uncertain writes stay spent. A surviving temporary file blocks restart.
        target = ".state-pending" if replace else name
        fd = _file(self.fd, target, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        try:
            offset = 0
            while offset < len(raw):
                count = os.write(fd, raw[offset:])
                if count <= 0:
                    raise OSError()
                offset += count
            os.fsync(fd)
            _named(self.fd, target, fd)
            if replace:
                os.rename(target, name, src_dir_fd=self.fd, dst_dir_fd=self.fd)
            os.fsync(self.fd)
            if not hmac.compare_digest(self._bytes(name), raw):
                raise OSError()
        except Exception:
            self.poisoned = True
            raise DemoRejected("basket_consumer_write_unconfirmed") from None
        finally:
            os.close(fd)

    def _sync(self):
        intent = verify_worker_intent(self.read(), self.key, binding=self.binding, now_ms=self.now())
        self.guard(intent)
        previous = self._state()
        if previous and (intent.revision < previous["revision"] or
                         intent.revision == previous["revision"] and intent.payload_digest != previous["digest"]):
            raise DemoRejected("basket_control_rollback_or_revision_reuse")
        if not previous or intent.revision > previous["revision"]:
            next_state = dict(schema=STATE_SCHEMA, revision=intent.revision, digest=intent.payload_digest,
                              ever_started=intent.action == "start" or bool(previous and previous["ever_started"]),
                              journal_id=self.journal._header["journal_id"])
            self._write(f"accepted-{intent.revision:016d}-{intent.payload_digest}", self._seal(next_state))
            self._write("state", self._seal(next_state), replace=True)
            previous = next_state
        self.guard(intent)
        return intent, previous

    def sync(self):
        with self._locked():
            return self._sync()[0]

    def __call__(self, intent, receipt, context):
        if (type(intent) not in (BasketMarketIntent, BasketExitIntent) or intent.binding != self.binding
                or context != self.binding.owner):
            raise DemoRejected("foreign_basket_consume_scope")
        with self._locked():
            control, accepted = self._sync()
            state, current_receipt = self.journal.checkpoint()
            pending = state.book.pending
            plan = state.book.signal.profile.plan
            if (receipt != current_receipt or pending is None or state.current_attempt is not None
                    or str(intent.journal_id) != self.journal._header["journal_id"]
                    or pending.command_id != intent.command_id or pending.order_digest != intent.order_digest
                    or plan.tenant_id != str(control.tenant_id) or plan.account_id != str(control.account_id)
                    or not accepted["ever_started"]):
                raise DemoRejected("original_owned_pending_basket_required")
            if intent != basket_journal_intent(self.journal, self.binding, state, context):
                raise DemoRejected("basket_intent_differs_from_original_journal")
            if type(intent) is BasketMarketIntent and (
                    control.action != "start" or intent.grid.symbol not in control.assets
                    or control.basket_limit != plan.configured_limit):
                raise DemoRejected("basket_buys_paused_or_settings_changed")
            now = clock(self.now())
            approval = BasketOrderApproval(uuid5(NAMESPACE, str(intent.journal_id) + "\0" + intent.command_id),
                intent, receipt, credential_revision=control.credential_revision,
                storage_version=control.storage_version, granted_ms=now, expires_ms=now + 15000)
            name = "consumed-" + hashlib.sha256((str(intent.journal_id) + "\0" + intent.command_id).encode()).hexdigest()
            record = dict(schema="investalo-demo-h1-basket-consumed/1", control_digest=control.payload_digest,
                          control_revision=control.revision, purpose=approval.purpose,
                          authorization_digest=approval.authorization_digest, intent_digest=intent.intent_digest,
                          receipt_digest=approval.receipt_digest, request_digest=approval.request_digest)
            try:
                self._write(name, self._seal(record))
            except FileExistsError:
                raise DemoRejected("basket_command_already_consumed") from None
            # A pause, settings change or revocation while fsync ran blocks POST.
            latest, _ = self._sync()
            if latest != control:
                raise DemoRejected("basket_control_changed_during_consumption")
            approval.check(intent, receipt, clock(self.now()))
            self._root()
            return approval
