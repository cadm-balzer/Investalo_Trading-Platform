"""Durable exact-order consumption; requires a separately installed consent issuer.

No HTTP route, token issuer or account-read conversion is provided here.
The private original directory is selected by trusted installation, never by
a request. An uncertain consume remains spent and is never removed/retried.
"""
import os
import re
import threading
import time
from uuid import UUID

from investalo_bitget import OwnerContext
from investalo_bitget.futures_demo import DemoIntent, DemoRejected, clock, digest
from investalo_bitget.futures_demo_market import BTCMarketIntent
from investalo_bitget.futures_demo_outbox import OutboxReceipt, encode
from investalo_bitget.futures_demo_registry import _directory, _file, _identity, _named

from .demo_order_dispatch import DemoOrderApproval
from .models import _PrivateImmutable

MAX_CONSUMED = 1024


class DurableDemoOrderConsumer(_PrivateImmutable):
    """Consume a real issuer's exact approval before dispatcher secret access."""
    __slots__ = ("root", "fd", "issuer", "guard", "now", "pid", "lock")

    def __init__(self, root, *, issuer, guard, milliseconds=lambda: time.time_ns() // 1_000_000):
        if not all(callable(value) for value in (issuer, guard, milliseconds)):
            raise DemoRejected("invalid_order_consumer_installation")
        fd = _directory(root)
        for name, value in (("root", root), ("fd", fd), ("issuer", issuer), ("guard", guard),
                ("now", milliseconds), ("pid", os.getpid()), ("lock", threading.Lock())):
            object.__setattr__(self, name, value)

    def close(self):
        with self.lock:
            if self.fd is not None:
                os.close(self.fd)
                object.__setattr__(self, "fd", None)

    def _root(self):
        if self.fd is None or self.pid != os.getpid():
            raise DemoRejected("order_consumer_closed_or_forked")
        current = _directory(self.root)
        try:
            if _identity(current) != _identity(self.fd):
                raise DemoRejected("original_order_consumer_root_replaced")
        finally:
            os.close(current)
        names = os.listdir(self.fd)
        if len(names) > MAX_CONSUMED or any(
                re.fullmatch(r"consumed-[0-9a-f-]{36}\.json", name) is None
                or str(UUID(name[9:-5])) != name[9:-5] for name in names):
            raise DemoRejected("order_consumer_capacity_or_foreign_file")
        return len(names)

    def __call__(self, intent, receipt, context):
        if (type(intent) not in (DemoIntent, BTCMarketIntent) or type(receipt) is not OutboxReceipt
                or type(context) is not OwnerContext):
            raise DemoRejected("invalid_order_consume_scope")
        intent.binding.check(context)
        if receipt.binding_digest != digest(intent.binding.record()):
            raise DemoRejected("foreign_order_consume_receipt")
        with self.lock:
            if self._root() >= MAX_CONSUMED:
                raise DemoRejected("order_consumer_capacity_exhausted")
            self.guard()
            approval = self.issuer(intent, receipt, context)
            if type(approval) is not DemoOrderApproval:
                raise DemoRejected("order_consent_not_confirmed")
            approval.check(intent, receipt, clock(self.now()))
            self.guard()
            self._root()
            name = "consumed-" + str(approval.authorization_id) + ".json"
            # UUID name is global within the original installation root.
            # O_EXCL also rejects corrupt/empty prior markers after a crash.
            try:
                fd = _file(self.fd, name, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
            except FileExistsError:
                raise DemoRejected("order_consent_already_consumed") from None
            try:
                record = encode(dict(schema="investalo-demo-order-consumed/1",
                    authorization_id=str(approval.authorization_id),
                    command_id=str(intent.command_id), intent_digest=intent.intent_digest,
                    binding_digest=receipt.binding_digest, receipt=receipt.record(),
                    credential_revision=approval.credential_revision,
                    storage_version=approval.storage_version,
                    granted_ms=approval.granted_ms, expires_ms=approval.expires_ms))
                offset = 0
                while offset < len(record):
                    written = os.write(fd, record[offset:])
                    if written <= 0:
                        raise DemoRejected("order_consent_write_unconfirmed")
                    offset += written
                os.fsync(fd)
                os.fsync(self.fd)
                self._root()
                _named(self.fd, name, fd)
                # Actual bytes read back from a distinct descriptor.
                read = _file(self.fd, name, os.O_RDONLY)
                try:
                    if (_identity(read) != _identity(fd) or os.fstat(read).st_size != len(record)
                            or os.read(read, len(record) + 1) != record):
                        raise DemoRejected("order_consent_readback_unconfirmed")
                finally:
                    os.close(read)
                self.guard()
                approval.check(intent, receipt, clock(self.now()))
                return approval
            finally:
                os.close(fd)
