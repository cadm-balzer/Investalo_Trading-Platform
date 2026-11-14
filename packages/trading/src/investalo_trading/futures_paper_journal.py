"""Own Paper journal, independent of frozen market research journal schemas."""
from dataclasses import fields, replace
from datetime import datetime
from decimal import Decimal
import os
from pathlib import Path
from threading import RLock

from .allocation import revision
from .capital_digest import digest
from .capital_identity_history import CapitalIdentityHistory
from .futures_capital_grid import CapitalGridRule
from .futures_capital_journal import CapitalReplayJournal, MAX_FILE_BYTES, MAX_LINE_BYTES
from .futures_capital_research import start_capital_research
from .futures_capital_signals import CapitalH1SignalProfile, CapitalHour, start_capital_signals
from .futures_ledger import LedgerMark, timestamp
from .futures_paper import FuturesPaperConfig, PaperBatch, paper_settings, run_paper_batch, start_paper, warm_paper
from .futures_paper_plan import CapitalPaperPoolPlan
from .futures_paper_settlement import PaperSettlement, settle_paper_funding
from .futures_paper_minute import PaperMinuteSettlement, settle_paper_minute
from .futures_replay_journal import _fields, _json, _open, _sha
from .futures_risk import FuturesPlan
from .snapshot import _decode, primitive

VERSION = "isolated-usdt-futures-paper-journal/1"
MAX_COMMANDS = 50_000
ARGUMENTS = {"warmup": {"hours": tuple[CapitalHour, ...]},
             "batch": {"batch": PaperBatch},
             "settlement": {"settlement": PaperSettlement},
             "minute_settlement": {"settlement": PaperMinuteSettlement},
             "settings": {"limit": int, "settings_revision": int}}


def _config(raw):
    _fields(raw, ("profile", "trading_from", "liquidation_fee_rate", "assume_insurance_credit"))
    p = _fields(raw["profile"], ("plan", "protection_hours", "slippage", "assumptions_digest", "signal_policy"))
    if p["signal_policy"] != CapitalH1SignalProfile.signal_policy:
        raise ValueError("own closed H1 Paper policy required")
    plan_raw = dict(p["plan"])
    if plan_raw.pop("capital_policy", None) != CapitalPaperPoolPlan.capital_policy:
        raise ValueError("own Paper pool policy required")
    extra = {name: _decode(kind, plan_raw.pop(name)) for name, kind in (
        ("grid_rules", tuple[CapitalGridRule, ...]), ("grid_source_digest", str),
        ("initial_slots", int), ("configured_limit", int))}
    base = _decode(FuturesPlan, plan_raw)
    plan = CapitalPaperPoolPlan(**{f.name: getattr(base, f.name) for f in fields(FuturesPlan)}, **extra)
    profile = CapitalH1SignalProfile(plan, _decode(int, p["protection_hours"]),
                                    _decode(Decimal, p["slippage"]), _decode(str, p["assumptions_digest"]))
    return FuturesPaperConfig(profile, _decode(datetime, raw["trading_from"]),
                              _decode(Decimal, raw["liquidation_fee_rate"]),
                              _decode(bool, raw["assume_insurance_credit"]))


def _genesis(header):
    _fields(header, ("schema_version", "config", "initial_trade", "initial_mark", "at",
                     "evidence_digest", "command_capacity", "execution_enabled"))
    if header["schema_version"] != VERSION or header["execution_enabled"] is not False:
        raise ValueError("own non-executable Paper journal required")
    if type(header["command_capacity"]) is not int or not 1 <= header["command_capacity"] <= MAX_COMMANDS:
        raise ValueError("bounded Paper command capacity required")
    config, at = _config(header["config"]), timestamp(_decode(datetime, header["at"]))
    marks = _decode(tuple[LedgerMark, ...], header["initial_mark"])
    trade = _decode(tuple[LedgerMark, ...], header["initial_trade"])
    economic = start_capital_research(config.profile.plan, marks, at, header["evidence_digest"], identity_capacity=1)
    economic = replace(economic, event_ids=CapitalIdentityHistory("event", 1_000_000))
    return start_paper(config, start_capital_signals(config.profile, economic, trade))


def _command(kind, expected_revision, at, arguments):
    if type(kind) is not str or kind not in ARGUMENTS:
        raise ValueError("unsupported Paper command")
    revision(expected_revision)
    _fields(arguments, ARGUMENTS[kind])
    return {"kind": kind, "revision": expected_revision, "at": timestamp(at).isoformat(),
            "arguments": {name: primitive(arguments[name]) for name in ARGUMENTS[kind]}}


def _apply(state, command):
    _fields(command, ("kind", "revision", "at", "arguments"))
    kind = command["kind"]
    if type(kind) is not str or kind not in ARGUMENTS:
        raise ValueError("unsupported Paper command")
    revision(command["revision"])
    raw = _fields(command["arguments"], ARGUMENTS[kind])
    args = {key: _decode(cls, raw[key]) for key, cls in ARGUMENTS[kind].items()}
    function = {"warmup": warm_paper, "batch": run_paper_batch, "settings": paper_settings,
                "settlement": settle_paper_funding, "minute_settlement": settle_paper_minute}[kind]
    return function(state, *args.values(), command["revision"], _decode(datetime, command["at"]))


class FuturesPaperJournal(CapitalReplayJournal):
    """Reuse hardened file IO only; own genesis, commands and replay identity."""
    def __init__(self, *args):
        super().__init__(*args)
        self._lock = RLock()
        self._minimum_receipt = None

    @property
    def state(self):
        with self._lock:
            return super().state

    @property
    def receipt(self):
        with self._lock:
            return super().receipt

    def checkpoint(self):
        """One acknowledged state/receipt pair, including unknown-write checks."""
        with self._lock:
            return super().state, super().receipt

    def acknowledges(self, receipt):
        """Current receipt or the exact ancestor proved by full restore."""
        with self._lock:
            return receipt == super().receipt or (
                self._minimum_receipt is not None and receipt == self._minimum_receipt)

    def close(self):
        with self._lock:
            super().close()

    @classmethod
    def create(cls, path, config, initial_trade, initial_mark, at, evidence_digest,
               *, command_capacity=MAX_COMMANDS):
        header = {"schema_version": VERSION, "config": primitive(config),
                  "initial_trade": primitive(initial_trade), "initial_mark": primitive(initial_mark),
                  "at": timestamp(at).isoformat(), "evidence_digest": evidence_digest,
                  "command_capacity": command_capacity, "execution_enabled": False}
        state = _genesis(header)
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
    def restore(cls, path, *, config_digest, minimum_receipt=None):
        handle = _open(path, create=False)
        try:
            if os.fstat(handle.fileno()).st_size > MAX_FILE_BYTES:
                raise ValueError("Paper journal exceeds file resource bound")
            header = _json(handle.readline(MAX_LINE_BYTES + 1))
            state = _genesis(header)
            if state.config.config_digest != config_digest:
                raise ValueError("foreign own Paper context")
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
                    raise ValueError("foreign acknowledged Paper receipt")

            def anchor():
                if minimum_receipt is not None and sequence == minimum_receipt["sequence"]:
                    if head != minimum_receipt["head"] or state.state_digest != minimum_receipt["state_digest"]:
                        raise ValueError("acknowledged Paper anchor mismatch")

            anchor()
            while line := handle.readline(MAX_LINE_BYTES + 1):
                record = _fields(_json(line), ("sequence", "prior_head", "prior_state_digest",
                                              "command", "state_digest", "head"))
                if (type(record["sequence"]) is not int or record["sequence"] != sequence + 1
                        or record["prior_head"] != head or record["prior_state_digest"] != state.state_digest
                        or sequence >= header["command_capacity"]):
                    raise ValueError("Paper sequence or prior context mismatch")
                candidate = _apply(state, record["command"])
                expected = digest((VERSION, head, record["command"], candidate.state_digest, sequence + 1))
                if record["state_digest"] != candidate.state_digest or record["head"] != expected:
                    raise ValueError("Paper deterministic replay or chain mismatch")
                state, head, sequence = candidate, expected, sequence + 1
                anchor()
            if minimum_receipt is not None and sequence < minimum_receipt["sequence"]:
                raise ValueError("Paper journal truncated before acknowledged receipt")
            journal = cls(handle, header, state, head, sequence)
            journal._minimum_receipt = dict(minimum_receipt) if minimum_receipt is not None else None
            return journal
        except BaseException:
            handle.close()
            raise

    def append(self, kind, *, expected_revision, at, **arguments):
        with self._lock:
            return self._append(kind, expected_revision=expected_revision, at=at, **arguments)

    def _append(self, kind, *, expected_revision, at, **arguments):
        self._usable()
        if self._sequence >= self._header["command_capacity"]:
            raise ValueError("Paper journal capacity exhausted; never evict evidence")
        command = _command(kind, expected_revision, at, arguments)
        candidate = _apply(self._state, command)
        head = digest((VERSION, self._head, command, candidate.state_digest, self._sequence + 1))
        self._write({"sequence": self._sequence + 1, "prior_head": self._head,
                     "prior_state_digest": self._state.state_digest, "command": command,
                     "state_digest": candidate.state_digest, "head": head})
        self._state, self._head, self._sequence = candidate, head, self._sequence + 1
        return candidate
