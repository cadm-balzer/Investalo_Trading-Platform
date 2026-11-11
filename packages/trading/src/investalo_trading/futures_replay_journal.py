"""Local research-only durable input journal; restore by full deterministic replay."""
from __future__ import annotations

import fcntl
from datetime import datetime
import json
import os
from pathlib import Path
import re
import stat

from .allocation import revision
from .futures_ledger import (
    EntryFill, ExitFill, FundingSettlement, FuturesLedgerState, MarginPosting, timestamp,
)
from .futures_pending import OrderResolution, start_long_pending_research
from .futures_signals import (
    H4Frame, ReplayProfile, replay_attempt, replay_cancel_unattempted, replay_economic_event,
    replay_fill, replay_frame, replay_terminal, reserve_signal, start_signal_replay,
)
from .snapshot import _decode, digest, primitive

VERSION = "isolated-usdt-long-replay-journal/1"
MAX_LINE_BYTES = 256 * 1024
MAX_FILE_BYTES = 128 * 1024 * 1024
MAX_COMMANDS = 100_000
ARGUMENTS = {
    "frame": {"frame": H4Frame},
    "reserve": {"symbol": str, "intent_id": str},
    "attempt": {"intent_id": str, "order_id": str},
    "cancel": {"intent_id": str},
    "fill": {"payload": None, "order_id": str, "fill_id": str},
    "terminal": {"resolution": OrderResolution},
    "economic": {"payload": None, "event_id": str},
}
PAYLOADS = {"EntryFill": EntryFill, "ExitFill": ExitFill,
            "FundingSettlement": FundingSettlement, "MarginPosting": MarginPosting}


class JournalCommitUnknown(RuntimeError):
    """No retry. Close and fully read back before continuing research."""


def _fields(value, expected):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError("journal record fields mismatch")
    return value


def _sha(value):
    if not isinstance(value, str) or re.fullmatch("[0-9a-f]{64}", value) is None:
        raise ValueError("explicit SHA256 binding required")
    return value


def _duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate journal JSON key")
        result[key] = value
    return result


def _json(line):
    if not line.endswith(b"\n") or len(line) > MAX_LINE_BYTES:
        raise ValueError("incomplete or oversized journal record")
    try:
        return json.loads(line, object_pairs_hook=_duplicates,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))
    except (RecursionError, UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("invalid bounded journal JSON") from None


def _apply(state, command):
    _fields(command, ("kind", "revision", "at", "arguments"))
    kind = command["kind"]
    if not isinstance(kind, str) or kind not in ARGUMENTS:
        raise ValueError("unsupported research input kind")
    revision(command["revision"])
    at = timestamp(_decode(datetime, command["at"]))
    expected = command["revision"]
    raw = _fields(command["arguments"], ARGUMENTS[kind])
    args = {}
    for key, value in raw.items():
        cls = ARGUMENTS[kind][key]
        if cls is None:
            wrapped = _fields(value, ("kind", "value"))
            cls = PAYLOADS.get(wrapped["kind"]) if isinstance(wrapped["kind"], str) else None
            permitted = (EntryFill, ExitFill) if kind == "fill" else (FundingSettlement, MarginPosting)
            if cls not in permitted:
                raise ValueError("foreign payload type in research input")
            value = wrapped["value"]
        args[key] = _decode(cls, value)
    if kind == "frame":
        result = replay_frame(state, args["frame"], expected, at)
    elif kind == "reserve":
        result = reserve_signal(state, args["symbol"], args["intent_id"], expected, at)
    elif kind == "attempt":
        result = replay_attempt(state, args["intent_id"], args["order_id"], expected, at)
    elif kind == "cancel":
        result = replay_cancel_unattempted(state, args["intent_id"], expected, at)
    elif kind == "fill":
        result = replay_fill(state, args["payload"], args["order_id"], args["fill_id"], expected, at)
    elif kind == "terminal":
        result = replay_terminal(state, args["resolution"], expected, at)
    else:
        result = replay_economic_event(state, args["payload"], args["event_id"], expected, at)
    if result.revision != state.revision + 1:
        raise ValueError("journal requires a new transition, not a duplicate frame")
    return result


def _command(kind, expected_revision, at, arguments):
    if not isinstance(kind, str) or kind not in ARGUMENTS:
        raise ValueError("unsupported research input kind")
    _fields(arguments, ARGUMENTS[kind])
    raw = {}
    for key, value in arguments.items():
        cls = ARGUMENTS[kind][key]
        if cls is None:
            permitted = (EntryFill, ExitFill) if kind == "fill" else (FundingSettlement, MarginPosting)
            if type(value) not in permitted:
                raise ValueError("typed research payload required")
            raw[key] = {"kind": type(value).__name__, "value": primitive(value)}
        else:
            if type(value) is not cls:
                raise ValueError("typed research input required")
            raw[key] = primitive(value)
    return {"kind": kind, "revision": expected_revision, "at": timestamp(at).isoformat(), "arguments": raw}


def _genesis(header):
    _fields(header, ("schema_version", "profile", "ledger", "protocol_digest", "dataset_digests",
                     "identity_capacity", "command_capacity", "execution_enabled"))
    if header["schema_version"] != VERSION or header["execution_enabled"] is not False:
        raise ValueError("unsupported or executable journal")
    _sha(header["protocol_digest"])
    datasets = header["dataset_digests"]
    if (type(datasets) is not list or not 1 <= len(datasets) <= 64
            or not all(isinstance(value, str) for value in datasets)
            or datasets != sorted(set(datasets))):
        raise ValueError("canonical unique dataset bindings required")
    for value in datasets:
        _sha(value)
    if type(header["command_capacity"]) is not int or not 1 <= header["command_capacity"] <= MAX_COMMANDS:
        raise ValueError("bounded command capacity required")
    ledger = _decode(FuturesLedgerState, header["ledger"])
    profile = _decode(ReplayProfile, header["profile"])
    return start_signal_replay(profile, start_long_pending_research(
        ledger, identity_capacity=header["identity_capacity"]))


def _open(path, *, create):
    flags = os.O_RDWR | os.O_NOFOLLOW | (os.O_CREAT | os.O_EXCL if create else 0)
    fd = os.open(Path(path), flags, 0o600)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1):
            raise ValueError("owned private regular research journal required")
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return os.fdopen(fd, "r+b", buffering=0)
    except BaseException:
        os.close(fd)
        raise


class FuturesReplayJournal:
    """Exclusive local writer. No broker, dispatch, SQL service or snapshot shortcut."""
    def __init__(self, handle, header, state, head, sequence):
        self._handle, self._header, self._state = handle, header, state
        self._head, self._sequence, self._uncertain = head, sequence, False

    @classmethod
    def create(cls, path, profile, ledger, *, protocol_digest, dataset_digests,
               identity_capacity=50_000, command_capacity=MAX_COMMANDS):
        header = {"schema_version": VERSION, "profile": primitive(profile), "ledger": primitive(ledger),
                  "protocol_digest": protocol_digest, "dataset_digests": list(dataset_digests),
                  "identity_capacity": identity_capacity, "command_capacity": command_capacity,
                  "execution_enabled": False}
        state = _genesis(header)  # validate before filesystem mutation
        handle = _open(path, create=True)
        journal = cls(handle, header, state, digest((VERSION, header)), 0)
        try:
            journal._write(header)
            directory = os.open(Path(path).parent, os.O_DIRECTORY | os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        except BaseException:
            journal.close()
            raise
        return journal

    @classmethod
    def restore(cls, path, *, profile_digest, protocol_digest, dataset_digests, minimum_receipt=None):
        handle = _open(path, create=False)
        try:
            if os.fstat(handle.fileno()).st_size > MAX_FILE_BYTES:
                raise ValueError("journal exceeds file resource bound")
            header = _json(handle.readline(MAX_LINE_BYTES + 1))
            state = _genesis(header)
            if (state.profile.profile_digest != profile_digest
                    or header["protocol_digest"] != protocol_digest
                    or header["dataset_digests"] != list(dataset_digests)):
                raise ValueError("foreign profile/protocol/dataset journal")
            head, sequence = digest((VERSION, header)), 0
            if minimum_receipt is not None:
                _fields(minimum_receipt, ("schema_version", "context_digest", "sequence", "head",
                                         "state_digest", "execution_enabled"))
                revision(minimum_receipt["sequence"])
                if (minimum_receipt["schema_version"] != VERSION
                        or minimum_receipt["context_digest"] != digest(header)
                        or minimum_receipt["execution_enabled"] is not False):
                    raise ValueError("foreign acknowledged journal receipt")
            def check_anchor():
                if minimum_receipt is not None and sequence == minimum_receipt["sequence"]:
                    if head != minimum_receipt["head"] or state.state_digest != minimum_receipt["state_digest"]:
                        raise ValueError("acknowledged journal anchor mismatch")
            check_anchor()
            while line := handle.readline(MAX_LINE_BYTES + 1):
                record = _fields(_json(line), ("sequence", "prior_head", "prior_state_digest",
                                              "command", "state_digest", "head"))
                if (type(record["sequence"]) is not int or record["sequence"] != sequence + 1
                        or record["prior_head"] != head or record["prior_state_digest"] != state.state_digest
                        or sequence >= header["command_capacity"]):
                    raise ValueError("journal sequence or prior binding mismatch")
                candidate = _apply(state, record["command"])
                expected = digest((VERSION, head, record["command"], candidate.state_digest, sequence + 1))
                if record["state_digest"] != candidate.state_digest or record["head"] != expected:
                    raise ValueError("journal replay or chain digest mismatch")
                state, head, sequence = candidate, expected, sequence + 1
                check_anchor()
            if minimum_receipt is not None and sequence < minimum_receipt["sequence"]:
                raise ValueError("journal truncated before acknowledged receipt")
            return cls(handle, header, state, head, sequence)
        except BaseException:
            handle.close()
            raise

    @property
    def state(self):
        self._usable()
        return self._state

    @property
    def receipt(self):
        self._usable()
        return {"schema_version": VERSION, "context_digest": digest(self._header), "sequence": self._sequence,
                "head": self._head, "state_digest": self._state.state_digest, "execution_enabled": False}

    def _usable(self):
        if self._uncertain:
            raise JournalCommitUnknown("journal acknowledgement unknown; close and fully read back")
        if self._handle.closed:
            raise ValueError("journal is closed")

    def _write(self, record):
        line = (json.dumps(record, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
        if len(line) > MAX_LINE_BYTES or self._handle.tell() + len(line) > MAX_FILE_BYTES:
            raise ValueError("journal resource capacity exhausted; never evict evidence")
        try:
            if self._handle.write(line) != len(line):
                raise OSError("short journal write")
            os.fsync(self._handle.fileno())
        except BaseException:
            self._uncertain = True
            raise JournalCommitUnknown("journal acknowledgement unknown; no retry") from None

    def append(self, kind, *, expected_revision, at, **arguments):
        self._usable()
        if self._sequence >= self._header["command_capacity"]:
            raise ValueError("journal command capacity exhausted; never evict evidence")
        command = _command(kind, expected_revision, at, arguments)
        candidate = _apply(self._state, command)
        head = digest((VERSION, self._head, command, candidate.state_digest, self._sequence + 1))
        record = {"sequence": self._sequence + 1, "prior_head": self._head,
                  "prior_state_digest": self._state.state_digest, "command": command,
                  "state_digest": candidate.state_digest, "head": head}
        self._write(record)
        self._state, self._head, self._sequence = candidate, head, self._sequence + 1
        return candidate

    def close(self):
        self._handle.close()

    def __enter__(self):
        return self

    def __exit__(self, *ignored):
        self.close()
