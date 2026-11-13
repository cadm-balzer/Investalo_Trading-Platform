"""Full durable replay of the new Q41–Q43 capital/RSI profile; research only."""
from dataclasses import replace
from datetime import datetime
from decimal import Decimal
import json
import os
from pathlib import Path

from .allocation import revision
from .capital_identity_history import CapitalIdentityHistory
from .futures_capital_research import (
    CapitalPlan, CapitalCashPlan, CapitalRealizedCashPlan, start_capital_research,
)
from .futures_capital_signals import (
    CapitalFundingBatch, CapitalHour, CapitalSignalAssessment, CapitalSignalProfile,
    CapitalH1SignalProfile, declare_signal_leverage,
    observe_capital_prices, record_signal_economic_event, replay_capital_hour,
    record_signal_funding_batch, replay_valued_capital_hour, simulate_signal_entry, start_capital_signals,
)
from .futures_ledger import (
    ExitFill, FundingSettlement, LedgerMark, LiquidationSettlement, MarginPosting, MarkBatch,
    timestamp,
)
from .futures_replay_journal import JournalCommitUnknown, _fields, _json, _open, _sha
from .futures_risk import FuturesPlan
from .snapshot import _decode, primitive
from .capital_digest import digest

VERSION = "isolated-usdt-capital-replay-journal/1"
H1_VERSION = "isolated-usdt-capital-replay-journal-h1/2"
MAX_FILE_BYTES = 512 * 1024 * 1024
MAX_COMMANDS = 250_000
MAX_LINE_BYTES = 256 * 1024
ARGUMENTS = {
    "hour": {"frame": CapitalHour},
    "valued_hour": {"frame": CapitalHour, "marks": tuple[LedgerMark, ...], "evidence_digest": str},
    "funding_batch": {"batch": CapitalFundingBatch, "event_id": str},
    "prices": {"trade": tuple[LedgerMark, ...], "mark": tuple[LedgerMark, ...], "event_id": str},
    "leverage": {"symbol": str, "leverage": Decimal, "evidence_digest": str, "event_id": str},
    "entry": {"assessment": CapitalSignalAssessment, "price": Decimal, "event_id": str},
    "economic": {"payload": None, "event_id": str},
}
PAYLOADS = {c.__name__: c for c in (
    MarkBatch, FundingSettlement, MarginPosting, ExitFill, LiquidationSettlement,
)}


def _arguments(kind, raw):
    _fields(raw, ARGUMENTS[kind])
    result = {}
    for key, cls in ARGUMENTS[kind].items():
        value = raw[key]
        if cls is None:
            wrapped = _fields(value, ("kind", "value"))
            cls = PAYLOADS.get(wrapped["kind"]) if type(wrapped["kind"]) is str else None
            if cls is None:
                raise ValueError("foreign capital journal payload type")
            value = wrapped["value"]
        result[key] = _decode(cls, value)
    return result


def _apply(state, command):
    _fields(command, ("kind", "revision", "at", "arguments"))
    kind = command["kind"]
    if type(kind) is not str or kind not in ARGUMENTS:
        raise ValueError("unsupported capital journal input kind")
    revision(command["revision"])
    at = timestamp(_decode(datetime, command["at"]))
    args = _arguments(kind, command["arguments"])
    functions = {
        "hour": replay_capital_hour, "valued_hour": replay_valued_capital_hour,
        "funding_batch": record_signal_funding_batch,
        "prices": observe_capital_prices,
        "leverage": declare_signal_leverage, "entry": simulate_signal_entry,
        "economic": record_signal_economic_event,
    }
    # The reducers retain all original causal/revision/admission checks.
    result = functions[kind](state, *args.values(), command["revision"], at)
    if result.revision != state.revision + 1:
        raise ValueError("capital journal requires a new transition, not a duplicate hour")
    return result


def _command(kind, expected_revision, at, arguments):
    if type(kind) is not str or kind not in ARGUMENTS:
        raise ValueError("unsupported capital journal input kind")
    _fields(arguments, ARGUMENTS[kind])
    raw = {}
    # Freeze schema order; JSON field order must never influence reducer arguments.
    for key, cls in ARGUMENTS[kind].items():
        value = arguments[key]
        if cls is None:
            if type(value).__name__ not in PAYLOADS or PAYLOADS[type(value).__name__] is not type(value):
                raise ValueError("typed capital economic input required")
            raw[key] = {"kind": type(value).__name__, "value": primitive(value)}
        else:
            expected = tuple if key in ("trade", "mark", "marks") else cls
            if type(value) is not expected:
                raise ValueError("typed capital journal input required")
            raw[key] = primitive(value)
    return {"kind": kind, "revision": expected_revision, "at": timestamp(at).isoformat(), "arguments": raw}


def _genesis(header):
    _fields(header, ("schema_version", "profile", "initial_trade", "initial_mark", "at",
                     "evidence_digest", "protocol_digest", "dataset_digests", "identity_capacity",
                     "command_capacity", "execution_enabled"))
    if header["schema_version"] not in (VERSION, H1_VERSION) or header["execution_enabled"] is not False:
        raise ValueError("unsupported or executable capital journal")
    _sha(header["protocol_digest"])
    datasets = header["dataset_digests"]
    if (type(datasets) is not list or not 1 <= len(datasets) <= 64
            or any(type(d) is not str for d in datasets) or datasets != sorted(set(datasets))):
        raise ValueError("canonical unique capital dataset bindings required")
    for value in datasets:
        _sha(value)
    if type(header["command_capacity"]) is not int or not 1 <= header["command_capacity"] <= MAX_COMMANDS:
        raise ValueError("bounded capital command capacity required")
    h1 = header["schema_version"] == H1_VERSION
    profile_raw = _fields(header["profile"], (
        "plan", "protection_hours", "slippage", "assumptions_digest",
        *(("signal_policy",) if h1 else ())))
    if h1 and profile_raw["signal_policy"] != CapitalH1SignalProfile.signal_policy:
        raise ValueError("own frozen H1 signal policy required")
    # CapitalPlan has a frozen init=False policy discriminator: decode explicitly.
    plan_raw = dict(profile_raw["plan"])
    policy = plan_raw.pop("capital_policy", None)
    plan_type = {p.capital_policy: p for p in (
        CapitalPlan, CapitalCashPlan, CapitalRealizedCashPlan)}.get(policy)
    if plan_type is None:
        raise ValueError("own frozen capital policy required")
    plan = _decode(FuturesPlan, plan_raw)
    plan = plan_type(**{key: getattr(plan, key) for key in plan_raw})
    profile = (CapitalH1SignalProfile if h1 else CapitalSignalProfile)(
        plan, _decode(int, profile_raw["protection_hours"]),
        _decode(Decimal, profile_raw["slippage"]), _decode(str, profile_raw["assumptions_digest"]),
    )
    trade = _decode(tuple[LedgerMark, ...], header["initial_trade"])
    marks = _decode(tuple[LedgerMark, ...], header["initial_mark"])
    at = timestamp(_decode(datetime, header["at"]))
    history = CapitalIdentityHistory("event", header["identity_capacity"])
    economic = start_capital_research(plan, marks, at, header["evidence_digest"], identity_capacity=1)
    # This is flat genesis only; no advanced history is ever converted or cleared.
    economic = replace(economic, event_ids=history)
    return start_capital_signals(profile, economic, trade)


class CapitalReplayJournal:
    """Owned create-only file, exclusive writer and full input fold from genesis."""
    def __init__(self, handle, header, state, head, sequence):
        self._handle, self._header, self._state = handle, header, state
        self._head, self._sequence, self._uncertain = head, sequence, False

    @classmethod
    def create(cls, path, profile, initial_trade, initial_mark, at, evidence_digest, *,
               protocol_digest, dataset_digests, identity_capacity=250_000,
               command_capacity=MAX_COMMANDS):
        header = {
            "schema_version": H1_VERSION if type(profile) is CapitalH1SignalProfile else VERSION,
            "profile": primitive(profile),
            "initial_trade": primitive(initial_trade), "initial_mark": primitive(initial_mark),
            "at": timestamp(at).isoformat(), "evidence_digest": evidence_digest,
            "protocol_digest": protocol_digest, "dataset_digests": list(dataset_digests),
            "identity_capacity": identity_capacity, "command_capacity": command_capacity,
            "execution_enabled": False,
        }
        state = _genesis(header)
        handle = _open(path, create=True)
        journal = cls(handle, header, state, digest((header["schema_version"], header)), 0)
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
                raise ValueError("capital journal exceeds file resource bound")
            header = _json(handle.readline(MAX_LINE_BYTES + 1))
            state = _genesis(header)
            if (state.profile.profile_digest != profile_digest
                    or header["protocol_digest"] != protocol_digest
                    or header["dataset_digests"] != list(dataset_digests)):
                raise ValueError("foreign capital profile/protocol/dataset journal")
            version = header["schema_version"]
            head, sequence = digest((version, header)), 0
            if minimum_receipt is not None:
                _fields(minimum_receipt, ("schema_version", "context_digest", "sequence", "head",
                                         "state_digest", "execution_enabled"))
                revision(minimum_receipt["sequence"])
                _sha(minimum_receipt["head"])
                _sha(minimum_receipt["state_digest"])
                if (minimum_receipt["schema_version"] != version
                        or minimum_receipt["context_digest"] != digest(header)
                        or minimum_receipt["execution_enabled"] is not False):
                    raise ValueError("foreign acknowledged capital receipt")

            def check_anchor():
                if minimum_receipt is not None and sequence == minimum_receipt["sequence"]:
                    if head != minimum_receipt["head"] or state.state_digest != minimum_receipt["state_digest"]:
                        raise ValueError("acknowledged capital journal anchor mismatch")

            check_anchor()
            while line := handle.readline(MAX_LINE_BYTES + 1):
                record = _fields(_json(line), ("sequence", "prior_head", "prior_state_digest",
                                              "command", "state_digest", "head"))
                if (type(record["sequence"]) is not int or record["sequence"] != sequence + 1
                        or record["prior_head"] != head or record["prior_state_digest"] != state.state_digest
                        or sequence >= header["command_capacity"]):
                    raise ValueError("capital journal sequence or prior binding mismatch")
                candidate = _apply(state, record["command"])
                expected = digest((version, head, record["command"], candidate.state_digest, sequence + 1))
                if record["state_digest"] != candidate.state_digest or record["head"] != expected:
                    raise ValueError("capital journal replay or chain digest mismatch")
                state, head, sequence = candidate, expected, sequence + 1
                check_anchor()
            if minimum_receipt is not None and sequence < minimum_receipt["sequence"]:
                raise ValueError("capital journal truncated before acknowledged receipt")
            return cls(handle, header, state, head, sequence)
        except BaseException:
            handle.close()
            raise

    def _usable(self):
        if self._uncertain:
            raise JournalCommitUnknown("capital journal acknowledgement unknown; close and fully read back")
        if self._handle.closed:
            raise ValueError("capital journal is closed")

    @property
    def state(self):
        self._usable()
        return self._state

    @property
    def receipt(self):
        self._usable()
        return {"schema_version": self._header["schema_version"], "context_digest": digest(self._header),
                "sequence": self._sequence, "head": self._head,
                "state_digest": self._state.state_digest, "execution_enabled": False}

    def _write(self, record):
        line = (json.dumps(record, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
        if len(line) > MAX_LINE_BYTES or self._handle.tell() + len(line) > MAX_FILE_BYTES:
            raise ValueError("capital journal resource capacity exhausted; never evict evidence")
        try:
            if self._handle.write(line) != len(line):
                raise OSError("short capital journal write")
            os.fsync(self._handle.fileno())
        except BaseException:
            self._uncertain = True
            raise JournalCommitUnknown("capital journal acknowledgement unknown; no retry") from None

    def append(self, kind, *, expected_revision, at, **arguments):
        self._usable()
        if self._sequence >= self._header["command_capacity"]:
            raise ValueError("capital journal command capacity exhausted; never evict evidence")
        command = _command(kind, expected_revision, at, arguments)
        candidate = _apply(self._state, command)
        head = digest((self._header["schema_version"], self._head, command,
                       candidate.state_digest, self._sequence + 1))
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
