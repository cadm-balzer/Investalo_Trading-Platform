"""Private explicit own Paper allocation; no account creation or broker balance."""
from dataclasses import dataclass, replace
from datetime import timedelta
import hashlib
import os
from pathlib import Path

from investalo_marketdata.futures_paper_archive import _read, _write
from investalo_marketdata.snapshot import canonical, decode_json
from investalo_trading.futures_capital_research import start_capital_research
from investalo_trading.futures_capital_signals import start_capital_signals
from investalo_trading.futures_ledger import LedgerMark, timestamp
from investalo_trading.futures_paper import FuturesPaperConfig, start_paper, warm_paper
from investalo_trading.futures_paper_account import PaperAccountBinding, PaperSettingsEvidence
from investalo_trading.futures_paper_journal import FuturesPaperJournal, _config
from investalo_trading.futures_paper_status import FuturesAssetPublisher, FuturesAssetReader, _directory
from investalo_trading.futures_replay_journal import _fields, _sha
from investalo_trading.snapshot import _decode, primitive
from investalo_trading.models import floor_step

VERSION = "futures-paper-bootstrap/1"
MAX_SPEC = 128 * 1024


@dataclass(frozen=True)
class PaperBootstrapSpec:
    binding: PaperAccountBinding
    config: FuturesPaperConfig

    def __post_init__(self):
        if type(self.binding) is not PaperAccountBinding or type(self.config) is not FuturesPaperConfig:
            raise ValueError("explicit own Paper allocation required")
        plan = self.config.profile.plan
        if (plan.tenant_id, plan.account_id) != (self.binding.tenant_id, self.binding.account_id):
            raise ValueError("allocation belongs to another account")
        if getattr(plan, "epochs", ()):
            raise ValueError("new allocation cannot import acknowledged profit epochs")
        if plan.initial_equity != floor_step(plan.initial_equity, plan.quantum):
            raise ValueError("allocated own Paper capital must use money precision")

    def record(self):
        return {"schema_version": VERSION, "binding": primitive(self.binding),
                "config": primitive(self.config), "execution_enabled": False}

    @property
    def spec_digest(self):
        return hashlib.sha256(canonical(self.record()).encode()).hexdigest()


def save_spec(path, spec):
    """Administrative create-only allocation; caller retains its separate hash."""
    if type(spec) is not PaperBootstrapSpec:
        raise ValueError("own typed allocation required")
    path = Path(path)
    fd = _directory(path.parent)
    try:
        sha = _write(fd, path.name, spec.record(), MAX_SPEC)
        os.fsync(fd)
        if sha != spec.spec_digest:
            raise ValueError("own allocation identity differs")
    finally:
        os.close(fd)
    return sha


def load_spec(path, expected_digest):
    _sha(expected_digest)
    path = Path(path)
    fd = _directory(path.parent)
    try:
        raw = _read(fd, path.name, MAX_SPEC)
    finally:
        os.close(fd)
    if hashlib.sha256(raw).hexdigest() != expected_digest:
        raise ValueError("trusted own allocation hash mismatch")
    value = _fields(decode_json(raw, max_bytes=MAX_SPEC),
                    ("schema_version", "binding", "config", "execution_enabled"))
    if value["schema_version"] != VERSION or value["execution_enabled"] is not False:
        raise ValueError("own non-executing Paper allocation required")
    spec = PaperBootstrapSpec(_decode(PaperAccountBinding, value["binding"]), _config(value["config"]))
    if spec.record() != value or spec.spec_digest != expected_digest:
        raise ValueError("canonical own allocation required")
    return spec


def initialize_paper(path, spec, archive, status_root, read_account, clock, *, guard=lambda: None):
    """Create one explicit allocation and bound native warmup; never reset/retry."""
    path = Path(path)
    if path.exists() or path.is_symlink():
        raise ValueError("existing Paper journal requires restore, never reinitialization")
    fd = _directory(path.parent)
    os.close(fd)
    if FuturesAssetReader(status_root).publication(spec.binding.tenant_id, spec.binding.account_id) is not None:
        raise ValueError("existing own publication requires anchored restore, never a second allocation")
    guard()
    evidence = read_account()
    plan = spec.config.profile.plan
    if (type(evidence) is not PaperSettingsEvidence
            or evidence.binding_digest != spec.binding.binding_digest
            or (evidence.tenant_id, evidence.account_id) != (plan.tenant_id, plan.account_id)
            or evidence.basket_limit != plan.configured_limit
            or plan.initial_slots > evidence.basket_limit
            or not 0 <= (timestamp(clock()) - evidence.observed_at).total_seconds() <= 30):
        raise ValueError("committed own planning must match explicit initial allocation")
    end = spec.config.trading_from
    # Existing flat ledger genesis remains UTC-midnight; select16..39 warmup hours.
    start = (end - timedelta(hours=16)).replace(hour=0, minute=0, second=0, microsecond=0)
    source, observation = archive.market(start=start, end=end, funding_start=start, guard=guard)
    trade = tuple(LedgerMark(s, c.open) for s, c in zip(plan.symbols, observation.hours[0].trade, strict=True))
    mark = tuple(LedgerMark(s, c.open) for s, c in zip(plan.symbols, observation.hours[0].mark, strict=True))
    economic = start_capital_research(plan, mark, start, spec.spec_digest)
    state = start_paper(spec.config, start_capital_signals(spec.config.profile, economic, trade))
    # All native axis/config/warmup checks before creating financial evidence.
    warm_paper(state, observation.hours, 0, timestamp(clock()))
    guard()
    current = read_account()
    if (type(current) is not PaperSettingsEvidence
            or current.observed_at > timestamp(clock())
            or (timestamp(clock()) - current.observed_at).total_seconds() > 30
            or replace(current, observed_at=evidence.observed_at) != evidence):
        raise ValueError("own account changed during initialization")
    with FuturesPaperJournal.create(path, spec.config, trade, mark, start, spec.spec_digest) as journal:
        with FuturesAssetPublisher(status_root, journal, clock=clock) as publisher:
            publisher.check()
            guard()
            after = journal.append("source_warmup", hours=observation.hours, source=source,
                                   expected_revision=0, at=timestamp(clock()))
            guard()
            publisher.publish(expected_revision=after.revision)
            return journal.receipt
