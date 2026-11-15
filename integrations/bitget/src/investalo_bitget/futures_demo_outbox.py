"""Bounded private offline Demo outbox: exclusive writer, CAS, fsync, full replay."""
from __future__ import annotations

from dataclasses import dataclass, fields, replace
from decimal import Decimal
import fcntl
import json
import os
from pathlib import Path
import stat
from threading import RLock
from uuid import UUID, uuid4

from .futures_demo import DemoBinding, DemoGrid, DemoIntent, DemoRejected, clock, digest, text
from .futures_demo_reconcile import (
    DemoTrace, OrderObservation, FRESH_MS, acknowledge, apply_observation, frame, native_id, observe,
)
from .parse import amount

VERSION = "bitget-classic-demo-outbox/1"
MAX_BYTES = 16 * 1024 * 1024
MAX_LINE = 16 * 1024


def encode(raw):
    return json.dumps(raw, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def exact(raw, keys):
    if not isinstance(raw, dict) or set(raw) != set(keys):
        raise DemoRejected("journal_schema_mismatch")
    return raw


def _pairs(pairs):
    raw = {}
    for key, value in pairs:
        if key in raw:
            raise DemoRejected("duplicate_journal_field")
        raw[key] = value
    return raw


def decode(raw):
    if not isinstance(raw, bytes) or len(raw) > MAX_LINE:
        raise DemoRejected("journal_record_too_large")
    try:
        result = json.loads(raw.decode("ascii"), object_pairs_hook=_pairs,
                            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, UnicodeError, RecursionError):
        raise DemoRejected("invalid_journal_json") from None
    if encode(result) != raw:
        raise DemoRejected("noncanonical_journal")
    return result


def _observation_record(observation):
    if observation is None:
        return None
    result = {}
    for f in fields(OrderObservation):
        value = getattr(observation, f.name)
        if isinstance(value, Decimal):
            value = ("-" if value < 0 else "") + text(value.copy_abs())
        result[f.name] = value
    return result


def _observation(raw):
    exact(raw, (f.name for f in fields(OrderObservation)))
    values = dict(raw)
    for key in ("quantity", "average_price", "reported_fee"):
        values[key] = amount(raw[key], signed=key == "reported_fee")
    return OrderObservation(**values)


def _intent_record(intent):
    return {"command_id": str(intent.command_id), "grid": intent.grid.record(),
            "action": intent.action, "quantity": text(intent.quantity),
            "limit_price": text(intent.limit_price), "before_quantity": text(intent.before_quantity),
            "intent_digest": intent.intent_digest}


def _intent(raw, binding):
    exact(raw, ("command_id", "grid", "action", "quantity", "limit_price",
                "before_quantity", "intent_digest"))
    grid = exact(raw["grid"], ("symbol", "quantity_step", "price_tick",
                              "min_quantity", "min_notional", "max_limit_quantity"))
    try:
        identifier = UUID(raw["command_id"])
    except (ValueError, TypeError, AttributeError):
        raise DemoRejected("invalid_command_id") from None
    intent = DemoIntent(binding, identifier, DemoGrid(**{
        k: v if k == "symbol" else amount(v) for k, v in grid.items()}),
        raw["action"], amount(raw["quantity"]), amount(raw["limit_price"]),
        amount(raw["before_quantity"]))
    if _intent_record(intent) != raw:
        raise DemoRejected("intent_digest_mismatch")
    return intent


def _trace_record(trace):
    return {"intent": _intent_record(trace.intent), "state": trace.state,
            "dispatch_ms": trace.dispatch_ms, "order_id": trace.order_id,
            "observation": _observation_record(trace.observation)}


@dataclass(frozen=True, repr=False)
class OutboxReceipt:
    outbox_id: str
    binding_digest: str
    revision: int
    head: str
    state_digest: str

    def record(self):
        return {"schema": VERSION, **vars(self)}


class DemoOutbox:
    """Filesystem owner is trusted. One fixed registry path/account is required."""

    def __init__(self):
        raise DemoRejected("use_create_or_restore")

    @classmethod
    def _open(cls, directory, binding, outbox_id, context):
        if not isinstance(binding, DemoBinding) or not isinstance(outbox_id, UUID):
            raise DemoRejected("invalid_outbox_binding")
        binding.check(context)
        path = Path(directory)
        if not path.is_absolute() or ".." in path.parts:
            raise DemoRejected("private_absolute_directory_required")
        obj = object.__new__(cls)
        obj._mutex = RLock()
        obj._root_fd = obj._lock_fd = obj._journal_fd = None
        obj._closed, obj._poisoned = False, False
        try:
            # Walk through directory descriptors so ancestor symlinks cannot race
            # a prior path inspection. Subsequent operations stay in this directory.
            obj._root_fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
            for part in path.parts[1:]:
                next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                  dir_fd=obj._root_fd)
                os.close(obj._root_fd)
                obj._root_fd = next_fd
            mode = os.fstat(obj._root_fd)
            if mode.st_uid != os.geteuid() or stat.S_IMODE(mode.st_mode) != 0o700:
                raise DemoRejected("private_directory_required")
            try:
                obj._lock_fd = obj._file("writer.lock", os.O_RDWR | os.O_CREAT | os.O_EXCL)
                os.fsync(obj._lock_fd)
                os.fsync(obj._root_fd)
            except FileExistsError:
                obj._lock_fd = obj._file("writer.lock", os.O_RDWR)
            try:
                fcntl.flock(obj._lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise DemoRejected("outbox_writer_busy") from None
            obj._binding, obj._outbox_id = binding, str(outbox_id)
            obj._traces = {}
            return obj
        except BaseException:
            obj.close()
            raise

    def _file(self, name, flags):
        fd = os.open(name, flags | os.O_NOFOLLOW, 0o600, dir_fd=self._root_fd)
        try:
            mode = os.fstat(fd)
            if (not stat.S_ISREG(mode.st_mode) or stat.S_IMODE(mode.st_mode) != 0o600
                    or mode.st_uid != os.geteuid() or mode.st_nlink != 1):
                raise DemoRejected("private_regular_file_required")
            return fd
        except BaseException:
            os.close(fd)
            raise

    def _state_digest(self):
        return digest({"binding": self._binding.record(),
                       "traces": [_trace_record(self._traces[key]) for key in sorted(self._traces)]})

    def _new_receipt(self, revision, head):
        return OutboxReceipt(self._outbox_id, digest(self._binding.record()),
                             revision, head, self._state_digest())

    @classmethod
    def create(cls, directory, *, binding, outbox_id, context, capacity=1000):
        if type(capacity) is not int or not 1 <= capacity <= 10_000:
            raise DemoRejected("invalid_outbox_capacity")
        obj = cls._open(directory, binding, outbox_id, context)
        try:
            # A failed/partial original initialization is never silently reset.
            if os.path.lexists(Path(directory) / "receipt.json"):
                raise DemoRejected("outbox_already_exists")
            obj._journal_fd = obj._file("commands.jsonl", os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_EXCL)
            obj._capacity = capacity
            header = {"schema": VERSION, "execution_enabled": False,
                      "outbox_id": obj._outbox_id, "binding": binding.record(), "capacity": capacity}
            obj._bytes = encode(header) + b"\n"
            obj._append_bytes(obj._bytes)
            os.fsync(obj._root_fd)
            obj._receipt = obj._new_receipt(0, digest(header))
            obj._publish(obj._receipt)
            return obj
        except BaseException:
            obj.close()
            raise

    @classmethod
    def restore(cls, directory, *, binding, outbox_id, context, minimum_receipt=None):
        obj = cls._open(directory, binding, outbox_id, context)
        try:
            obj._journal_fd = obj._file("commands.jsonl", os.O_RDWR | os.O_APPEND)
            checkpoint = obj._read_checkpoint()
            raw = obj._read_journal()
            if not raw.endswith(b"\n"):
                raise DemoRejected("incomplete_journal_tail")
            lines = raw.splitlines()
            if not lines:
                raise DemoRejected("missing_journal_genesis")
            header = exact(decode(lines[0]), ("schema", "execution_enabled", "outbox_id", "binding", "capacity"))
            if (header["schema"] != VERSION or header["execution_enabled"] is not False
                    or header["binding"] != binding.record() or header["outbox_id"] != obj._outbox_id
                    or type(header["capacity"]) is not int or not 1 <= header["capacity"] <= 10_000):
                raise DemoRejected("foreign_outbox_genesis")
            obj._capacity = header["capacity"]
            obj._receipt = obj._new_receipt(0, digest(header))
            anchors = [checkpoint]
            if minimum_receipt is not None:
                if not isinstance(minimum_receipt, OutboxReceipt):
                    raise DemoRejected("invalid_minimum_receipt")
                anchors.append(minimum_receipt.record())
            matched = [False] * len(anchors)
            for anchor in anchors:
                exact(anchor, ("schema", *vars(obj._receipt)))
                if (anchor["schema"] != VERSION or anchor["outbox_id"] != obj._outbox_id
                        or anchor["binding_digest"] != digest(binding.record())
                        or type(anchor["revision"]) is not int or anchor["revision"] < 0):
                    raise DemoRejected("foreign_minimum_receipt")

            def match():
                for index, anchor in enumerate(anchors):
                    if anchor["revision"] == obj._receipt.revision:
                        if anchor != obj._receipt.record():
                            raise DemoRejected("receipt_fork")
                        matched[index] = True

            match()
            for line in lines[1:]:
                record = exact(decode(line), ("revision", "previous", "command", "state_digest", "head"))
                if (type(record["revision"]) is not int
                        or record["revision"] != obj._receipt.revision + 1
                        or record["revision"] > obj._capacity
                        or record["previous"] != obj._receipt.head):
                    raise DemoRejected("journal_sequence_mismatch")
                obj._apply(record["command"])
                unsigned = {k: v for k, v in record.items() if k != "head"}
                if record["state_digest"] != obj._state_digest() or record["head"] != digest(unsigned):
                    raise DemoRejected("journal_digest_mismatch")
                obj._receipt = obj._new_receipt(record["revision"], record["head"])
                match()
            if not all(matched):
                raise DemoRejected("journal_below_minimum_receipt")
            obj._bytes = raw
            # Fully verified suffix from an unknown write is retained, never resent.
            os.fsync(obj._journal_fd)
            os.fsync(obj._root_fd)
            obj._publish(obj._receipt)
            return obj
        except BaseException:
            obj.close()
            raise

    def _read_journal(self):
        lock = os.fstat(self._lock_fd)
        named_lock = os.stat("writer.lock", dir_fd=self._root_fd, follow_symlinks=False)
        if (not stat.S_ISREG(named_lock.st_mode) or lock.st_nlink != 1
                or stat.S_IMODE(lock.st_mode) != 0o600 or lock.st_uid != os.geteuid()
                or (lock.st_dev, lock.st_ino) != (named_lock.st_dev, named_lock.st_ino)):
            raise DemoRejected("outbox_lock_file_mismatch")
        mode = os.fstat(self._journal_fd)
        named = os.stat("commands.jsonl", dir_fd=self._root_fd, follow_symlinks=False)
        if (not stat.S_ISREG(named.st_mode) or mode.st_nlink != 1
                or stat.S_IMODE(mode.st_mode) != 0o600 or mode.st_uid != os.geteuid()
                or (mode.st_dev, mode.st_ino) != (named.st_dev, named.st_ino)
                or mode.st_size > MAX_BYTES):
            raise DemoRejected("journal_file_mismatch")
        data = bytearray()
        while len(data) < mode.st_size:
            chunk = os.pread(self._journal_fd, min(64 * 1024, mode.st_size - len(data)), len(data))
            if not chunk:
                raise DemoRejected("short_journal_read")
            data.extend(chunk)
        return bytes(data)

    def _read_checkpoint(self):
        fd = self._file("receipt.json", os.O_RDONLY)
        try:
            if os.fstat(fd).st_size > MAX_LINE:
                raise DemoRejected("checkpoint_too_large")
            return decode(os.read(fd, MAX_LINE + 1))
        finally:
            os.close(fd)

    def _append_bytes(self, data):
        view = memoryview(data)
        while view:
            count = os.write(self._journal_fd, view)
            if count <= 0:
                raise DemoRejected("short_journal_write")
            view = view[count:]
        os.fsync(self._journal_fd)

    def _publish(self, receipt):
        data = encode(receipt.record())
        name = "receipt-" + uuid4().hex + ".tmp"
        fd = self._file(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        try:
            view = memoryview(data)
            while view:
                count = os.write(fd, view)
                if count <= 0:
                    raise DemoRejected("short_checkpoint_write")
                view = view[count:]
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(name, "receipt.json", src_dir_fd=self._root_fd, dst_dir_fd=self._root_fd)
        os.fsync(self._root_fd)
        if self._read_checkpoint() != receipt.record():
            raise DemoRejected("checkpoint_readback_mismatch")

    def _check(self, context, expected_revision):
        self._binding.check(context)
        if self._closed or self._poisoned:
            raise DemoRejected("outbox_stopped")
        if type(expected_revision) is not int or expected_revision != self._receipt.revision:
            raise DemoRejected("outbox_revision_conflict")

    def _apply(self, command):
        exact(command, ("kind", "command_id", "payload"))
        key, kind, payload = command["command_id"], command["kind"], command["payload"]
        if kind == "prepare":
            candidate = _intent(payload, self._binding)
            if key != str(candidate.command_id) or key in self._traces:
                raise DemoRejected("duplicate_journal_command")
            if any(candidate.client_oid == item.intent.client_oid for item in self._traces.values()):
                raise DemoRejected("client_oid_collision")
            self._traces[key] = DemoTrace(candidate)
            return
        if not isinstance(key, str) or key not in self._traces:
            raise DemoRejected("unknown_order_command")
        trace = self._traces[key]
        if kind == "dispatch":
            exact(payload, ("at_ms",))
            candidate = trace.dispatched(context=self._binding.owner, at_ms=payload["at_ms"])
        elif kind == "ack":
            exact(payload, ("order_id", "response_ms", "known_at_ms"))
            clock(payload["response_ms"])
            clock(payload["known_at_ms"])
            if (trace.state != "submission_unknown" or payload["response_ms"] < trace.dispatch_ms
                    or not 0 <= payload["known_at_ms"] - payload["response_ms"] <= FRESH_MS):
                raise DemoRejected("invalid_ack_evidence")
            candidate = replace(trace, state="acknowledged",
                                order_id=native_id(payload["order_id"], optional=True))
        elif kind == "observation":
            exact(payload, ("observation", "known_at_ms"))
            current = _observation(payload["observation"])
            clock(payload["known_at_ms"])
            if not 0 <= payload["known_at_ms"] - current.response_ms <= FRESH_MS:
                raise DemoRejected("invalid_observation_evidence")
            candidate = apply_observation(trace, current)
        else:
            raise DemoRejected("unsupported_journal_command")
        self._traces[key] = candidate

    def _commit(self, command):
        if self._receipt.revision >= self._capacity:
            raise DemoRejected("outbox_capacity_exhausted")
        # Validate/reduce before touching disk; known rejected input stays usable.
        original = dict(self._traces)
        try:
            self._apply(command)
            unsigned = {"revision": self._receipt.revision + 1, "previous": self._receipt.head,
                        "command": command, "state_digest": self._state_digest()}
            record = {**unsigned, "head": digest(unsigned)}
            line = encode(record) + b"\n"
            next_receipt = self._new_receipt(unsigned["revision"], record["head"])
        finally:
            self._traces = original
        if len(line) > MAX_LINE or len(self._bytes) + len(line) > MAX_BYTES:
            raise DemoRejected("outbox_size_exhausted")
        try:
            if (self._read_journal() != self._bytes
                    or self._read_checkpoint() != self._receipt.record()):
                raise DemoRejected("outbox_disk_drift")
            self._append_bytes(line)
            if self._read_journal() != self._bytes + line:
                raise DemoRejected("journal_readback_mismatch")
            self._publish(next_receipt)
            self._apply(command)
            self._bytes += line
            self._receipt = next_receipt
            return self._receipt
        except BaseException:
            self._poisoned = True
            raise DemoRejected("outbox_write_unknown_restore_required") from None

    def prepare(self, intent, *, context, expected_revision):
        with self._mutex:
            self._check(context, expected_revision)
            if not isinstance(intent, DemoIntent) or intent.binding != self._binding:
                raise DemoRejected("foreign_order_intent")
            key = str(intent.command_id)
            old = self._traces.get(key)
            if old is not None:
                if old.intent.intent_digest != intent.intent_digest:
                    raise DemoRejected("order_payload_conflict")
                return self._receipt
            return self._commit({"kind": "prepare", "command_id": key, "payload": _intent_record(intent)})

    def begin_attempt(self, command_id, *, context, expected_revision, at_ms):
        with self._mutex:
            self._check(context, expected_revision)
            return self._commit({"kind": "dispatch", "command_id": str(command_id),
                                 "payload": {"at_ms": at_ms}})

    def accept_ack(self, command_id, response, *, context, expected_revision, now_ms):
        with self._mutex:
            self._check(context, expected_revision)
            key = str(command_id)
            if key not in self._traces:
                raise DemoRejected("unknown_order_command")
            candidate = acknowledge(self._traces[key], response, context=context, now_ms=now_ms)
            _, at_ms = frame(response, candidate.intent, context, now_ms)
            return self._commit({"kind": "ack", "command_id": key, "payload": {
                "order_id": candidate.order_id, "response_ms": at_ms, "known_at_ms": now_ms}})

    def accept_observation(self, command_id, response, *, context, expected_revision, now_ms):
        with self._mutex:
            self._check(context, expected_revision)
            key = str(command_id)
            if key not in self._traces:
                raise DemoRejected("unknown_order_command")
            candidate = observe(self._traces[key], response, context=context, now_ms=now_ms)
            return self._commit({"kind": "observation", "command_id": key, "payload": {
                "observation": _observation_record(candidate.observation), "known_at_ms": now_ms}})

    @property
    def receipt(self):
        with self._mutex:
            if self._closed or self._poisoned:
                raise DemoRejected("outbox_stopped")
            return self._receipt

    def traces(self, *, context):
        with self._mutex:
            self._check(context, self._receipt.revision)
            return tuple(self._traces[key] for key in sorted(self._traces))

    def check_account(self, expectation, packets, *, context, expected_revision, now_ms):
        """One locked readonly snapshot; result is not persisted or a send permit."""
        from .futures_demo_account import check_account
        with self._mutex:
            self._check(context, expected_revision)
            return check_account(expectation, self._receipt, self.traces(context=context),
                                 packets, context=context, now_ms=now_ms)

    def close(self):
        with self._mutex:
            self._closed = True
            for name in ("_journal_fd", "_lock_fd", "_root_fd"):
                fd = getattr(self, name)
                if fd is not None:
                    os.close(fd)
                    setattr(self, name, None)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def __repr__(self):
        return "DemoOutbox(<private offline>)"
