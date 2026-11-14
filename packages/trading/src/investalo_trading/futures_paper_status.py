"""Private atomic read publication; the journal remains the trading authority."""
from dataclasses import dataclass
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import stat
from uuid import uuid4

from .allocation import identifier, revision
from .capital_digest import digest
from .futures_ledger import timestamp
from .futures_paper_journal import FuturesPaperJournal, VERSION as JOURNAL_VERSION
from .futures_paper_view import FuturesAssetState, asset_state
from .futures_replay_journal import _fields, _json, _sha
from .snapshot import _decode, primitive

VERSION = "isolated-usdt-futures-paper-status/1"
MAX_BYTES = 64 * 1024


class PaperStatusCommitUnknown(RuntimeError):
    """Stop worker; restore journal using last published receipt before repair."""


def _directory(root):
    root = Path(root)
    if not root.is_absolute() or ".." in root.parts:
        raise ValueError("explicit private absolute status root required")
    for path in (root, *root.parents):
        if path.is_symlink():
            raise ValueError("status root symlinks rejected")
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        st = os.fstat(fd)
        if st.st_uid != os.getuid() or stat.S_IMODE(st.st_mode) != 0o700:
            raise ValueError("owned0700 status root required")
        return fd
    except BaseException:
        os.close(fd)
        raise


def _name(tenant_id, account_id):
    identifier(tenant_id)
    identifier(account_id)
    return digest((VERSION, tenant_id, account_id)) + ".json"


def _owned_file(fd):
    st = os.fstat(fd)
    if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid()
            or stat.S_IMODE(st.st_mode) != 0o600 or st.st_nlink != 1):
        raise ValueError("owned single-link0600 status file required")
    return st


def _receipt(value):
    _fields(value, ("schema_version", "context_digest", "sequence", "head",
                    "state_digest", "execution_enabled"))
    revision(value["sequence"])
    for key in ("context_digest", "head", "state_digest"):
        _sha(value[key])
    if value["schema_version"] != JOURNAL_VERSION or value["execution_enabled"] is not False:
        raise ValueError("own non-executable Paper receipt required")


@dataclass(frozen=True)
class PublishedAssets:
    state: FuturesAssetState
    journal_receipt: dict
    published_at: datetime

    def __post_init__(self):
        if type(self.state) is not FuturesAssetState:
            raise ValueError("compact own Paper view required")
        _receipt(self.journal_receipt)
        if (self.journal_receipt["sequence"] != self.state.revision
                or timestamp(self.published_at) < self.state.known_at):
            raise ValueError("acknowledged revision and publication knowledge required")

    def record(self):
        body = {"schema_version": VERSION, "state": primitive(self.state),
                "journal_receipt": self.journal_receipt,
                "published_at": self.published_at.isoformat(), "execution_enabled": False}
        return {**body, "content_digest": digest(body)}


def _read(fd, name, tenant_id, account_id):
    try:
        handle = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
    except FileNotFoundError:
        return None
    with os.fdopen(handle, "rb") as source:
        if _owned_file(source.fileno()).st_size > MAX_BYTES:
            raise ValueError("status publication exceeds bound")
        raw = source.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("status publication exceeds bound")
    record = _fields(_json(raw), ("schema_version", "state", "journal_receipt",
                                 "published_at", "execution_enabled", "content_digest"))
    body = {k: v for k, v in record.items() if k != "content_digest"}
    if (record["schema_version"] != VERSION or record["execution_enabled"] is not False
            or _sha(record["content_digest"]) != digest(body)):
        raise ValueError("status schema or content mismatch")
    view = _decode(FuturesAssetState, record["state"])
    if (view.tenant_id, view.account_id) != (tenant_id, account_id):
        raise ValueError("foreign Paper status publication")
    return PublishedAssets(view, record["journal_receipt"], _decode(datetime, record["published_at"]))


@dataclass(frozen=True)
class FuturesAssetReader:
    root: Path
    clock: object = lambda: datetime.now(timezone.utc)

    def publication(self, tenant_id, account_id):
        fd = _directory(self.root)
        try:
            return _read(fd, _name(tenant_id, account_id), tenant_id, account_id)
        finally:
            os.close(fd)

    def __call__(self, tenant_id, account_id):
        value = self.publication(tenant_id, account_id)
        if value is not None and value.published_at > timestamp(self.clock()):
            raise ValueError("future Paper status publication")
        return value.state if value is not None else None


class FuturesAssetPublisher:
    """Own lifetime writer lock. Publish only acknowledged journal checkpoints."""
    def __init__(self, root, journal, *, clock=lambda: datetime.now(timezone.utc)):
        if type(journal) is not FuturesPaperJournal or not callable(clock):
            raise ValueError("own Paper journal and clock required")
        self._journal, self._clock = journal, clock
        self._directory = _directory(root)
        self._lock = None
        self._uncertain = False
        try:
            state, _ = journal.checkpoint()
            plan = state.config.profile.plan
            self._tenant, self._account = plan.tenant_id, plan.account_id
            self._name = _name(self._tenant, self._account)
            self._lock = os.open(self._name + ".lock",
                                 os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK,
                                 0o600, dir_fd=self._directory)
            _owned_file(self._lock)
            fcntl.flock(self._lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            old = _read(self._directory, self._name, self._tenant, self._account)
            if old is not None and not journal.acknowledges(old.journal_receipt):
                raise ValueError("restore with published minimum_receipt before status continuation")
            self._previous = old
        except BaseException:
            self.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        for key in ("_lock", "_directory"):
            fd = getattr(self, key, None)
            if fd is not None:
                os.close(fd)
                setattr(self, key, None)

    def check(self):
        if self._uncertain:
            raise PaperStatusCommitUnknown("status write unknown; stop and read back, never retry")
        if self._directory is None:
            raise ValueError("Paper status publisher closed")
        directory = os.fstat(self._directory)
        if directory.st_uid != os.getuid() or stat.S_IMODE(directory.st_mode) != 0o700:
            raise ValueError("private status root permissions changed")
        if _read(self._directory, self._name, self._tenant, self._account) != self._previous:
            raise ValueError("status publication changed outside own writer")
        self._journal.checkpoint()  # Also refuses a poisoned/closed journal.

    def publish(self, *, expected_revision):
        self.check()
        state, receipt = self._journal.checkpoint()
        revision(expected_revision)
        if state.revision != expected_revision:
            raise ValueError("status checkpoint changed before publication")
        value = PublishedAssets(asset_state(state), receipt, timestamp(self._clock()))
        if (value.state.tenant_id, value.state.account_id) != (self._tenant, self._account):
            raise ValueError("foreign status writer context")
        old = _read(self._directory, self._name, self._tenant, self._account)
        if old != self._previous:
            raise ValueError("status publication changed outside own writer")
        if old is not None:
            if (old.journal_receipt["context_digest"] != receipt["context_digest"]
                    or old.state.revision > state.revision
                    or old.published_at > value.published_at):
                raise ValueError("status context or publication clock regressed")
            if old.state.revision == state.revision:
                if old.state != value.state or old.journal_receipt != receipt:
                    raise ValueError("same revision status evidence changed")
                return old  # Republish cannot refresh clocks.
        raw = (json.dumps(value.record(), sort_keys=True, separators=(",", ":"), allow_nan=False)
               + "\n").encode()
        if len(raw) > MAX_BYTES:
            raise ValueError("status publication exceeds bound")
        temporary = "." + self._name + "." + uuid4().hex
        try:
            handle = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600, dir_fd=self._directory)
            with os.fdopen(handle, "wb") as output:
                _owned_file(output.fileno())
                if output.write(raw) != len(raw):
                    raise OSError("short status write")
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, self._name, src_dir_fd=self._directory, dst_dir_fd=self._directory)
            os.fsync(self._directory)
            actual = _read(self._directory, self._name, self._tenant, self._account)
            if actual != value:
                raise OSError("status acknowledgement readback mismatch")
        except BaseException:
            self._uncertain = True
            raise PaperStatusCommitUnknown("status acknowledgement unknown; stop and read back") from None
        self._previous = actual
        return actual
