"""Original private Demo account/path registry; no native identity or send proof."""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import stat
from threading import RLock
from uuid import UUID

from .futures_demo import DemoBinding, DemoRejected, digest
from .futures_demo_outbox import DemoOutbox, MAX_LINE, decode, encode, exact
from .models import OwnerContext

VERSION = "bitget-demo-account-registry/1"
MAX_ACCOUNTS = 256


def _directory(path):
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts:
        raise DemoRejected("private_absolute_directory_required")
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        mode = os.fstat(fd)
        if mode.st_uid != os.geteuid() or stat.S_IMODE(mode.st_mode) != 0o700:
            raise DemoRejected("private_directory_required")
        return fd
    except BaseException:
        os.close(fd)
        raise


def _file(root, name, flags):
    fd = os.open(name, flags | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=root)
    try:
        mode = os.fstat(fd)
        if (not stat.S_ISREG(mode.st_mode) or mode.st_uid != os.geteuid()
                or stat.S_IMODE(mode.st_mode) != 0o600 or mode.st_nlink != 1):
            raise DemoRejected("private_regular_file_required")
        return fd
    except BaseException:
        os.close(fd)
        raise


def _identity(fd):
    mode = os.fstat(fd)
    return mode.st_dev, mode.st_ino


def _named(root, name, fd):
    mode = os.fstat(fd)
    named = os.stat(name, dir_fd=root, follow_symlinks=False)
    if (not stat.S_ISREG(named.st_mode) or mode.st_nlink != 1
            or mode.st_uid != os.geteuid() or stat.S_IMODE(mode.st_mode) != 0o600
            or (named.st_dev, named.st_ino) != _identity(fd)):
        raise DemoRejected("registry_file_replaced")


def _binding(raw):
    exact(raw, ("tenant", "user", "account", "credential_ref", "broker_uid",
                "environment", "api_family", "position_mode", "leverage"))
    try:
        binding = DemoBinding(OwnerContext(UUID(raw["tenant"]), UUID(raw["user"])),
            UUID(raw["account"]), UUID(raw["credential_ref"]), raw["broker_uid"],
            raw["environment"], raw["api_family"], raw["position_mode"], raw["leverage"])
    except (ValueError, TypeError, AttributeError):
        raise DemoRejected("invalid_registered_binding") from None
    if binding.record() != raw:
        raise DemoRejected("noncanonical_registered_binding")
    return binding


def _key(binding):
    # Global within the original trusted root; credentials/tenant are NOT the key.
    return digest({"exchange": "bitget", "environment": binding.environment,
                   "api_family": binding.api_family, "broker_uid": binding.broker_uid})


class _Registry:
    def __init__(self, root):
        self.root = Path(root)
        self.fd = self.lock = None
        try:
            self.fd = _directory(root)
            names = os.listdir(self.fd)
            if names and "registry.lock" not in names:
                raise DemoRejected("original_registry_lock_missing")
            try:
                self.lock = _file(self.fd, "registry.lock", os.O_RDWR | os.O_CREAT | os.O_EXCL)
                os.fsync(self.lock)
                os.fsync(self.fd)
            except FileExistsError:
                self.lock = _file(self.fd, "registry.lock", os.O_RDWR)
        except BaseException:
            self.close()
            raise

    def check_root(self):
        fd = _directory(self.root)
        try:
            if _identity(fd) != _identity(self.fd):
                raise DemoRejected("registry_root_replaced")
        finally:
            os.close(fd)
        _named(self.fd, "registry.lock", self.lock)

    @contextmanager
    def exclusive(self):
        self.check_root()
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise DemoRejected("registry_busy") from None
        try:
            self.check_root()
            yield
        finally:
            fcntl.flock(self.lock, fcntl.LOCK_UN)

    def entries(self):
        names = sorted(os.listdir(self.fd))
        if len(names) > 1 + MAX_ACCOUNTS * 2:
            raise DemoRejected("registry_capacity_exhausted")
        entries = {}
        accounts, paths, inodes, boxes = set(), set(), set(), set()
        for name in names:
            if name == "registry.lock":
                continue
            if (not name.startswith("account-") or len(name) != 77
                    or name[8:72].strip("0123456789abcdef")
                    or name[72:] not in (".json", ".lock")):
                raise DemoRejected("unknown_registry_file")
            fd = _file(self.fd, name, os.O_RDONLY)
            try:
                if name.endswith(".lock"):
                    if os.fstat(fd).st_size:
                        raise DemoRejected("invalid_account_lock")
                    continue
                if os.fstat(fd).st_size > MAX_LINE:
                    raise DemoRejected("registry_record_too_large")
                raw = decode(os.read(fd, MAX_LINE + 1))
            finally:
                os.close(fd)
            exact(raw, ("schema", "binding", "outbox_id", "path", "device", "inode", "head"))
            binding = _binding(raw["binding"])
            try:
                box = UUID(raw["outbox_id"])
                path = Path(raw["path"])
            except (ValueError, TypeError, AttributeError):
                raise DemoRejected("invalid_registry_record") from None
            if (raw["schema"] != VERSION or str(box) != raw["outbox_id"]
                    or not path.is_absolute() or ".." in path.parts or str(path) != raw["path"]
                    or type(raw["device"]) is not int or raw["device"] < 0
                    or type(raw["inode"]) is not int or raw["inode"] <= 0
                    or raw["head"] != digest({k: v for k, v in raw.items() if k != "head"})
                    or name != "account-" + _key(binding) + ".json"):
                raise DemoRejected("invalid_registry_record")
            key = _key(binding)
            account, inode = raw["binding"]["account"], (raw["device"], raw["inode"])
            if (account in accounts or raw["path"] in paths or inode in inodes
                    or raw["outbox_id"] in boxes):
                raise DemoRejected("duplicate_registered_resource")
            accounts.add(account)
            paths.add(raw["path"])
            inodes.add(inode)
            boxes.add(raw["outbox_id"])
            entries[key] = raw
        if len(entries) > MAX_ACCOUNTS:
            raise DemoRejected("registry_capacity_exhausted")
        return entries

    def claim(self, record):
        """Create before genesis; an unknown write never deletes or reclaims it."""
        name = "account-" + _key(_binding(record["binding"])) + ".json"
        fd = _file(self.fd, name, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        try:
            view = memoryview(encode(record))
            while view:
                count = os.write(fd, view)
                if count <= 0:
                    raise DemoRejected("short_registry_write")
                view = view[count:]
            os.fsync(fd)
            os.fsync(self.fd)
            if self.entries().get(name[8:72]) != record:
                raise DemoRejected("registry_readback_mismatch")
        except BaseException:
            raise DemoRejected("registry_write_unknown") from None
        finally:
            os.close(fd)

    def close(self):
        for name in ("lock", "fd"):
            fd = getattr(self, name, None)
            if fd is not None:
                os.close(fd)
                setattr(self, name, None)


class RegisteredDemoOutbox:
    """One original trusted registry root is required by every future executor."""
    def __init__(self):
        raise DemoRejected("use_create_or_restore")

    @classmethod
    def _open(cls, registry_root, directory, *, binding, outbox_id, context,
              create, capacity=1000, minimum_receipt=None):
        if not isinstance(binding, DemoBinding) or not isinstance(outbox_id, UUID):
            raise DemoRejected("invalid_outbox_binding")
        binding.check(context)
        if create and (type(capacity) is not int or not 1 <= capacity <= 10_000):
            raise DemoRejected("invalid_outbox_capacity")
        obj = object.__new__(cls)
        obj._mutex = RLock()
        obj._registry = obj._box = obj._lease = None
        obj._closed = obj._poisoned = False
        obj._pid = os.getpid()
        try:
            obj._registry = _Registry(registry_root)
            path = Path(directory)
            fd = _directory(path)
            try:
                device, inode = _identity(fd)
                unsigned = {"schema": VERSION, "binding": binding.record(),
                            "outbox_id": str(outbox_id), "path": str(path),
                            "device": device, "inode": inode}
                obj._record = {**unsigned, "head": digest(unsigned)}
                obj._name = "account-" + _key(binding)
                with obj._registry.exclusive():
                    entries = obj._registry.entries()
                    old = entries.get(_key(binding))
                    if old is not None:
                        if old != obj._record:
                            raise DemoRejected("original_account_binding_conflict")
                        if create:
                            raise DemoRejected("account_already_registered")
                    elif not create:
                        raise DemoRejected("account_not_registered")
                    else:
                        if len(entries) >= MAX_ACCOUNTS:
                            raise DemoRejected("registry_capacity_exhausted")
                        for entry in entries.values():
                            if (entry["binding"]["account"] == str(binding.account_id)
                                    or entry["outbox_id"] == str(outbox_id)
                                    or entry["path"] == str(path)
                                    or (entry["device"], entry["inode"]) == (device, inode)):
                                raise DemoRejected("registered_resource_conflict")
                        if os.listdir(fd):
                            raise DemoRejected("empty_original_outbox_directory_required")
                    if not create:
                        obj._lease = _file(obj._registry.fd, obj._name + ".lock", os.O_RDWR)
                    else:
                        # Lock the broker identity before reserving its new path.
                        # Existing orphan lock files are retained, not replaced.
                        try:
                            obj._lease = _file(obj._registry.fd, obj._name + ".lock",
                                              os.O_RDWR | os.O_CREAT | os.O_EXCL)
                            os.fsync(obj._lease)
                            os.fsync(obj._registry.fd)
                        except FileExistsError:
                            obj._lease = _file(obj._registry.fd, obj._name + ".lock", os.O_RDWR)
                    try:
                        fcntl.flock(obj._lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        raise DemoRejected("account_writer_busy") from None
                    if create:
                        obj._registry.claim(obj._record)
                        obj._box = DemoOutbox.create(path, binding=binding, outbox_id=outbox_id,
                                                    context=context, capacity=capacity)
                    else:
                        obj._box = DemoOutbox.restore(path, binding=binding, outbox_id=outbox_id,
                            context=context, minimum_receipt=minimum_receipt)
                    if _identity(obj._box._root_fd) != (device, inode):
                        raise DemoRejected("registered_outbox_directory_replaced")
                return obj
            finally:
                os.close(fd)
        except BaseException:
            obj.close()
            raise

    @classmethod
    def create(cls, registry_root, directory, *, binding, outbox_id, context, capacity=1000):
        return cls._open(registry_root, directory, binding=binding, outbox_id=outbox_id,
                         context=context, create=True, capacity=capacity)

    @classmethod
    def restore(cls, registry_root, directory, *, binding, outbox_id, context, minimum_receipt=None):
        return cls._open(registry_root, directory, binding=binding, outbox_id=outbox_id,
                         context=context, create=False, minimum_receipt=minimum_receipt)

    def _check(self):
        if self._closed or self._poisoned or os.getpid() != self._pid:
            raise DemoRejected("registered_outbox_stopped")
        self._registry.check_root()
        _named(self._registry.fd, self._name + ".lock", self._lease)
        if self._registry.entries().get(self._name[8:]) != self._record:
            raise DemoRejected("original_account_registration_changed")
        fd = _directory(self._record["path"])
        try:
            if (_identity(fd) != (self._record["device"], self._record["inode"])
                    or _identity(self._box._root_fd) != _identity(fd)):
                raise DemoRejected("registered_outbox_directory_replaced")
        finally:
            os.close(fd)

    @contextmanager
    def _validated(self):
        # A parent thread may have held the inherited mutex at fork.
        if os.getpid() != self._pid:
            raise DemoRejected("registered_outbox_stopped")
        with self._mutex:
            if self._closed or self._poisoned or os.getpid() != self._pid:
                raise DemoRejected("registered_outbox_stopped")
            checked = False
            try:
                # Serialize catalog inspection with other account registrations.
                with self._registry.exclusive():
                    self._check()
                    checked = True
                    yield
            except BaseException as error:
                if not checked and not (isinstance(error, DemoRejected) and str(error) == "registry_busy"):
                    self._poisoned = True
                raise

    def _invoke(self, method, *args, **kwargs):
        with self._validated():
            return getattr(self._box, method)(*args, **kwargs)

    @property
    def receipt(self):
        with self._validated():
            return self._box.receipt

    def prepare(self, *args, **kwargs):
        return self._invoke("prepare", *args, **kwargs)

    def begin_attempt(self, *args, **kwargs):
        return self._invoke("begin_attempt", *args, **kwargs)

    def accept_ack(self, *args, **kwargs):
        return self._invoke("accept_ack", *args, **kwargs)

    def accept_observation(self, *args, **kwargs):
        return self._invoke("accept_observation", *args, **kwargs)

    def traces(self, *args, **kwargs):
        return self._invoke("traces", *args, **kwargs)

    def check_account(self, *args, **kwargs):
        return self._invoke("check_account", *args, **kwargs)

    def check_binding(self, binding, *, context, expected_revision):
        """Validate the original scope before a future private read is dispatched."""
        with self._validated():
            self._box._check(context, expected_revision)
            if not isinstance(binding, DemoBinding) or binding != self._box._binding:
                raise DemoRejected("registered_read_binding_mismatch")
            return self._box.receipt

    def close(self):
        if os.getpid() != self._pid:
            raise DemoRejected("registered_outbox_stopped")
        with self._mutex:
            self._closed = True
            if self._box is not None:
                self._box.close()
                self._box = None
            if self._lease is not None:
                os.close(self._lease)
                self._lease = None
            if self._registry is not None:
                self._registry.close()
                self._registry = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def __repr__(self):
        return "RegisteredDemoOutbox(<private offline>)"
