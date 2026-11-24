"""Own Demo basket entry journal: full replay, one attempt, GET-only recovery.

The sender is a trusted injected port, not an installed broker client. External
strategy authorization/account/credential checks remain required; a recorded
authorization digest is not a consent token or a grant issued by this journal.
"""
from dataclasses import dataclass, fields, replace
from datetime import datetime, timedelta
from decimal import Decimal
import os
from pathlib import Path
import stat
from threading import RLock
from typing import get_type_hints
from uuid import UUID

from .allocation import revision
from .capital_digest import CapitalCanonical, digest
from .futures_broker_entries import (
    BrokerEntryBook, BrokerEntryObservation, cancel_broker_preparation,
    observe_broker_entry, observe_broker_prices, prepare_broker_entry,
    replay_broker_hour, start_broker_entries,
)
from .futures_capital_grid import CapitalGridPlan
from .futures_capital_journal import CapitalReplayJournal, MAX_FILE_BYTES, MAX_LINE_BYTES
from .futures_capital_research import (
    CapitalCashPlan, CapitalPlan, CapitalRealizedCashPlan, CapitalReservedCashPlan,
    start_capital_research,
)
from .futures_capital_signals import (
    CapitalH1SignalProfile, CapitalHour, assess_capital_signal, start_capital_signals,
)
from .futures_ledger import LedgerMark, timestamp
from .futures_paper_plan import CapitalPaperPoolPlan
from .futures_paper_profit_plan import CapitalPaperProfitPlan
from .futures_replay_journal import JournalCommitUnknown, _fields, _json, _open, _sha
from .snapshot import _decode, primitive

VERSION = "bitget-demo-h1-basket-entry-journal/1"
MAX_COMMANDS = 50_000
PLANS = {p.capital_policy: p for p in (
    CapitalPlan, CapitalCashPlan, CapitalRealizedCashPlan, CapitalReservedCashPlan,
    CapitalGridPlan, CapitalPaperPoolPlan, CapitalPaperProfitPlan)}
ARGUMENTS = {
    "hour": {"frame": CapitalHour},
    "prices": {"trade": tuple[LedgerMark, ...], "marks": tuple[LedgerMark, ...], "event_id": str},
    "prepare": {"symbol": str, "planning_price": Decimal, "command_id": str},
    "cancel_preparation": {"order_digest": str},
    "attempt": {"order_digest": str, "authorization_digest": str, "request_digest": str},
    "observe": {"observation": BrokerEntryObservation},
}


class BrokerSubmissionUnknown(RuntimeError):
    """The recorded attempt survives. Observe it; never invoke the sender again."""


@dataclass(frozen=True)
class BrokerEntryAttempt(CapitalCanonical):
    command_id: str
    order_digest: str
    authorization_digest: str
    request_digest: str
    attempted_at: datetime

    def __post_init__(self):
        from .allocation import identifier
        identifier(self.command_id)
        for value in (self.order_digest, self.authorization_digest, self.request_digest):
            _sha(value)
        timestamp(self.attempted_at)


@dataclass(frozen=True)
class BrokerJournalState(CapitalCanonical):
    book: BrokerEntryBook
    revision: int
    as_of: datetime
    attempts: tuple[BrokerEntryAttempt, ...]

    def __post_init__(self):
        revision(self.revision)
        timestamp(self.as_of)
        if (type(self.book) is not BrokerEntryBook or self.book.as_of > self.as_of
                or type(self.attempts) is not tuple or len(self.attempts) > MAX_COMMANDS
                or any(type(a) is not BrokerEntryAttempt or a.command_id not in self.book.commands
                       or a.attempted_at > self.as_of for a in self.attempts)
                or len({a.command_id for a in self.attempts}) != len(self.attempts)):
            raise ValueError("own immutable once-only basket journal state required")
        if self.current_attempt is not None and (
                self.current_attempt.order_digest != self.book.pending.order_digest):
            raise ValueError("pending basket order changed after its attempt")

    @property
    def current_attempt(self):
        if self.book.pending is None:
            return None
        return next((a for a in reversed(self.attempts)
                     if a.command_id == self.book.pending.command_id), None)

    @property
    def recovery_mode(self):
        if self.book.pending is None:
            return "none"
        return "get_only" if self.current_attempt is not None else "unsent_preparation"

    @property
    def state_digest(self):
        return digest((VERSION, self))

    @property
    def execution_enabled(self):
        return False


def _profile(raw):
    expected = {f.name for f in fields(CapitalH1SignalProfile)}
    _fields(raw, expected)
    if raw["signal_policy"] != CapitalH1SignalProfile.signal_policy:
        raise ValueError("own H1 profile required")
    plan_raw = dict(raw["plan"])
    policy = plan_raw.pop("capital_policy", None)
    cls = PLANS.get(policy) if type(policy) is str else None
    if cls is None:
        raise ValueError("known capital allocation policy required")
    # init=False discriminators are verified above, never passed as constructor
    # arguments. Each inherited field retains its concrete declared type.
    expected_plan = {f.name for f in fields(cls) if f.init}
    _fields(plan_raw, expected_plan)
    hints = get_type_hints(cls)
    plan = cls(**{key: _decode(hints[key], plan_raw[key]) for key in expected_plan})
    return CapitalH1SignalProfile(
        plan, _decode(int, raw["protection_hours"]), _decode(Decimal, raw["slippage"]),
        _decode(str, raw["assumptions_digest"]))


def _genesis(header):
    _fields(header, ("schema_version", "journal_id", "environment", "profile", "initial_trade",
                     "initial_mark", "at", "evidence_digest", "command_capacity", "execution_enabled"))
    if (header["schema_version"] != VERSION or header["environment"] != "bitget_demo"
            or header["execution_enabled"] is not False):
        raise ValueError("own disabled Demo basket journal required")
    if type(header["journal_id"]) is not str or str(UUID(header["journal_id"])) != header["journal_id"]:
        raise ValueError("canonical journal UUID required")
    if type(header["command_capacity"]) is not int or not 1 <= header["command_capacity"] <= MAX_COMMANDS:
        raise ValueError("bounded basket journal capacity required")
    profile = _profile(header["profile"])
    at = timestamp(_decode(datetime, header["at"]))
    trade = _decode(tuple[LedgerMark, ...], header["initial_trade"])
    marks = _decode(tuple[LedgerMark, ...], header["initial_mark"])
    economic = start_capital_research(profile.plan, marks, at, header["evidence_digest"])
    book = start_broker_entries(start_capital_signals(profile, economic, trade))
    return BrokerJournalState(book, 0, at, ())


def _command(kind, expected_revision, at, arguments):
    if type(kind) is not str or kind not in ARGUMENTS:
        raise ValueError("unsupported basket journal command")
    revision(expected_revision)
    _fields(arguments, ARGUMENTS[kind])
    return dict(kind=kind, revision=expected_revision, at=timestamp(at).isoformat(),
                arguments={key: primitive(arguments[key]) for key in ARGUMENTS[kind]})


def _apply(state, command):
    _fields(command, ("kind", "revision", "at", "arguments"))
    kind, expected = command["kind"], command["revision"]
    if type(kind) is not str or kind not in ARGUMENTS:
        raise ValueError("unsupported basket journal command")
    revision(expected)
    at = timestamp(_decode(datetime, command["at"]))
    if expected != state.revision or at < state.as_of:
        raise ValueError("stale basket journal revision or backdated command")
    raw = _fields(command["arguments"], ARGUMENTS[kind])
    args = {key: _decode(cls, raw[key]) for key, cls in ARGUMENTS[kind].items()}
    book, attempts = state.book, state.attempts
    if kind == "attempt":
        order = book.pending
        if (order is None or order.order_digest != args["order_digest"]
                or state.current_attempt is not None or book.observation is not None
                or not timedelta(0) <= at - order.prepared_at <= timedelta(seconds=30)):
            raise ValueError("original fresh unsent order required; resend forbidden")
        # Recheck the current H1/capital state. A marker cannot extend the
        # original signal window, replace a stage, or bless a now-rejected order.
        fresh = assess_capital_signal(
            book.signal, order.request.symbol, order.request.maximum_fill_price, at).capital
        if (not fresh.allowed or fresh.stage != order.assessment.capital.stage
                or any(getattr(fresh.request, key) != getattr(order.request, key) for key in (
                    "tenant_id", "account_id", "plan_digest", "symbol", "quantity",
                    "maximum_fill_price", "posted_margin", "requested_leverage"))):
            raise ValueError("basket admission changed before attempt")
        attempts += (BrokerEntryAttempt(order.command_id, order.order_digest,
                     args["authorization_digest"], args["request_digest"], at),)
    elif kind == "observe":
        if state.current_attempt is None:
            raise ValueError("broker observation requires its recorded original attempt")
        if args["observation"].observed_at < state.current_attempt.attempted_at:
            raise ValueError("observation predates the recorded attempt")
        book = observe_broker_entry(book, args["observation"], book.revision, at)
    elif kind == "cancel_preparation":
        if state.current_attempt is not None:
            raise ValueError("attempted order is GET-only; cannot discard exposure")
        book = cancel_broker_preparation(book, args["order_digest"], book.revision, at)
    else:
        functions = {"hour": replay_broker_hour, "prices": observe_broker_prices,
                     "prepare": prepare_broker_entry}
        book = functions[kind](book, *args.values(), book.revision, at)
    if kind != "attempt" and book is state.book:
        raise ValueError("duplicate observation or hour needs no journal write")
    return BrokerJournalState(book, state.revision + 1, at, attempts)


class BrokerEntryJournal(CapitalReplayJournal):
    """Reuse owned file IO; own genesis/commands/context and deterministic fold."""

    def __init__(self, *args, path):
        super().__init__(*args)
        self._lock = RLock()
        self._minimum_receipt = None
        self._pid = os.getpid()
        self._path = Path(path).absolute()
        info = os.fstat(self._handle.fileno())
        self._identity = info.st_dev, info.st_ino
        self._generation = info.st_size, info.st_mtime_ns, info.st_ctime_ns

    def _usable(self):
        super()._usable()
        self._own_process()
        try:
            info = os.fstat(self._handle.fileno())
            path_info = os.stat(self._path, follow_symlinks=False)
            if (not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600
                    or info.st_uid != os.getuid() or info.st_nlink != 1
                    or (info.st_dev, info.st_ino) != self._identity
                    or (path_info.st_dev, path_info.st_ino) != self._identity
                    or (info.st_size, info.st_mtime_ns, info.st_ctime_ns) != self._generation
                    or self._handle.tell() != info.st_size):
                raise OSError("basket journal changed outside its writer")
        except OSError:
            self._uncertain = True
            raise JournalCommitUnknown("basket journal identity/content unconfirmed; full restore required") from None

    def _write(self, record):
        self._usable()
        super()._write(record)
        try:
            info = os.fstat(self._handle.fileno())
            self._generation = info.st_size, info.st_mtime_ns, info.st_ctime_ns
        except OSError:
            self._uncertain = True
            raise JournalCommitUnknown("basket journal write acknowledgement unknown; full restore required") from None

    def _own_process(self):
        if os.getpid() != self._pid:
            raise ValueError("fork-inherited basket writer forbidden; close and restore")

    @property
    def state(self):
        self._own_process()
        with self._lock:
            return super().state

    @property
    def receipt(self):
        self._own_process()
        with self._lock:
            return super().receipt

    def checkpoint(self):
        self._own_process()
        with self._lock:
            return super().state, super().receipt

    def acknowledges(self, receipt):
        self._own_process()
        with self._lock:
            self._usable()
            return receipt == super().receipt or (
                self._minimum_receipt is not None and receipt == self._minimum_receipt)

    def close(self):
        if os.getpid() != self._pid:
            super().close()
            return
        with self._lock:
            super().close()

    @classmethod
    def create(cls, path, profile, initial_trade, initial_mark, at, evidence_digest, *,
               journal_id, command_capacity=MAX_COMMANDS):
        header = dict(schema_version=VERSION, journal_id=str(journal_id), environment="bitget_demo",
                      profile=primitive(profile), initial_trade=primitive(initial_trade),
                      initial_mark=primitive(initial_mark), at=timestamp(at).isoformat(),
                      evidence_digest=evidence_digest, command_capacity=command_capacity,
                      execution_enabled=False)
        state = _genesis(header)
        handle = _open(path, create=True)
        journal = cls(handle, header, state, digest((VERSION, header)), 0, path=path)
        try:
            journal._write(header)
            directory = os.open(Path(path).parent, os.O_DIRECTORY | os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
            return journal
        except BaseException:
            journal.close()
            raise

    @classmethod
    def restore(cls, path, *, journal_id, profile_digest, minimum_receipt):
        # A caller restoring an acknowledged journal must retain its external
        # receipt. Explicit None means no prefix has yet been acknowledged.
        handle = _open(path, create=False)
        try:
            before = os.fstat(handle.fileno())
            if before.st_size > MAX_FILE_BYTES:
                raise ValueError("basket journal exceeds file capacity")
            header = _json(handle.readline(MAX_LINE_BYTES + 1))
            state = _genesis(header)
            if header["journal_id"] != str(journal_id) or state.book.signal.profile.profile_digest != profile_digest:
                raise ValueError("foreign basket journal or profile")
            head, sequence = digest((VERSION, header)), 0
            if minimum_receipt is not None:
                _fields(minimum_receipt, ("schema_version", "context_digest", "sequence", "head",
                                         "state_digest", "execution_enabled"))
                revision(minimum_receipt["sequence"])
                for key in ("head", "state_digest"):
                    _sha(minimum_receipt[key])
                if (minimum_receipt["schema_version"] != VERSION
                        or minimum_receipt["context_digest"] != digest(header)
                        or minimum_receipt["execution_enabled"] is not False):
                    raise ValueError("foreign acknowledged basket receipt")

            def anchor():
                if minimum_receipt is not None and sequence == minimum_receipt["sequence"]:
                    if head != minimum_receipt["head"] or state.state_digest != minimum_receipt["state_digest"]:
                        raise ValueError("acknowledged basket prefix mismatch")

            anchor()
            while line := handle.readline(MAX_LINE_BYTES + 1):
                record = _fields(_json(line), ("sequence", "prior_head", "prior_state_digest",
                                              "command", "state_digest", "head"))
                if (type(record["sequence"]) is not int or record["sequence"] != sequence + 1
                        or record["prior_head"] != head or record["prior_state_digest"] != state.state_digest
                        or sequence >= header["command_capacity"]):
                    raise ValueError("basket journal sequence or prior binding mismatch")
                candidate = _apply(state, record["command"])
                expected = digest((VERSION, head, record["command"], candidate.state_digest, sequence + 1))
                if record["state_digest"] != candidate.state_digest or record["head"] != expected:
                    raise ValueError("basket journal replay or chain mismatch")
                state, head, sequence = candidate, expected, sequence + 1
                anchor()
            if minimum_receipt is not None and sequence < minimum_receipt["sequence"]:
                raise ValueError("basket journal truncated before acknowledged prefix")
            after = os.fstat(handle.fileno())
            if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                    after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                raise ValueError("basket journal changed during full restore")
            journal = cls(handle, header, state, head, sequence, path=path)
            journal._minimum_receipt = dict(minimum_receipt) if minimum_receipt is not None else None
            return journal
        except BaseException:
            handle.close()
            raise

    def append(self, kind, *, expected_revision, at, **arguments):
        self._own_process()
        with self._lock:
            self._usable()
            if self._sequence >= self._header["command_capacity"]:
                raise ValueError("basket journal capacity exhausted; never evict evidence")
            command = _command(kind, expected_revision, at, arguments)
            candidate = _apply(self._state, command)
            head = digest((VERSION, self._head, command, candidate.state_digest, self._sequence + 1))
            self._write(dict(sequence=self._sequence + 1, prior_head=self._head,
                             prior_state_digest=self._state.state_digest, command=command,
                             state_digest=candidate.state_digest, head=head))
            self._state, self._head, self._sequence = candidate, head, self._sequence + 1
            return candidate

    def invoke_once(self, sender, *, expected_revision, at, order_digest,
                    authorization_digest, request_digest):
        """Persist/fsync unknown-before-send; ACK alone does not book an entry.

        Trusted production sender must enforce the actual authorization and exact
        request digest. This journal provides no credential or authority adapter.
        """
        self._own_process()
        if not callable(sender):
            raise ValueError("trusted callable sender required")
        with self._lock:
            state = self.append("attempt", expected_revision=expected_revision, at=at,
                                order_digest=order_digest, authorization_digest=authorization_digest,
                                request_digest=request_digest)
            order, attempt = state.book.pending, state.current_attempt
        try:
            return sender(order, attempt)
        except BaseException:
            raise BrokerSubmissionUnknown("basket submission unconfirmed; GET-only recovery, no resend") from None
