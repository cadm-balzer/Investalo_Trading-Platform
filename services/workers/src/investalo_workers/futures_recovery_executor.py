"""Exclusive bounded own Paper executor; active feed writer is never interrupted."""
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
import os

from investalo_marketdata.futures_paper_archive import _read, _write
from investalo_marketdata.snapshot import decode_json
from investalo_trading.capital_digest import digest
from investalo_trading.futures_paper_journal import FuturesPaperJournal
from investalo_trading.futures_paper_recovery import PaperRecoveryRequest
from investalo_trading.futures_paper_status import FuturesAssetReader, FuturesAssetPublisher, _directory
from investalo_trading.futures_replay_journal import _fields
from .futures_paper_bootstrap import load_spec
from .futures_account_reader import FuturesPaperAccountReader

VERSION = "own-futures-paper-recovery-location/1"


def location_name(tenant, account):
    from uuid import UUID
    for value in (tenant, account):
        if str(UUID(value)) != value:
            raise ValueError("canonical own recovery location required")
    return digest((VERSION, tenant, account)) + ".json"


def register_recovery(root, spec_path, spec_digest, journal_path):
    spec = load_spec(spec_path, spec_digest)
    plan = spec.config.profile.plan
    value = dict(schema_version=VERSION, spec=str(Path(spec_path).absolute()),
        spec_digest=spec_digest, journal=str(Path(journal_path).absolute()), execution_enabled=False)
    fd = _directory(Path(root).absolute())
    try:
        name = location_name(plan.tenant_id, plan.account_id)
        try:
            old = decode_json(_read(fd, name, 16 * 1024))
        except FileNotFoundError:
            _write(fd, name, value, 16 * 1024)
            os.fsync(fd)
        else:
            if old != value:
                raise ValueError("existing recovery allocation cannot be replaced")
    finally:
        os.close(fd)


@dataclass(frozen=True)
class FuturesPaperRecoveryExecutor:
    root: Path
    status_root: Path
    connection_parameters: dict = field(repr=False)
    clock: object = lambda: datetime.now(timezone.utc)

    def _location(self, tenant, account):
        fd = _directory(Path(self.root).absolute())
        try:
            location = _fields(decode_json(_read(fd, location_name(
                tenant, account), 16 * 1024)),
                ("schema_version", "spec", "spec_digest", "journal", "execution_enabled"))
        finally:
            os.close(fd)
        if location["schema_version"] != VERSION or location["execution_enabled"] is not False:
            raise ValueError("own non-executable recovery location required")
        spec = load_spec(Path(location["spec"]), location["spec_digest"])
        if (spec.binding.tenant_id, spec.binding.account_id) != (tenant, account):
            raise ValueError("foreign recovery allocation")
        return location, spec

    def available(self, tenant, account, actor):
        try:
            _, spec = self._location(tenant, account)
            return spec.binding.user_id == actor
        except Exception:
            return False

    def __call__(self, request):
        if type(request) is not PaperRecoveryRequest:
            raise ValueError("server-created own manual Paper request required")
        location, spec = self._location(request.tenant_id, request.account_id)
        b = spec.binding
        if (b.tenant_id, b.account_id, b.user_id) != (
                request.tenant_id, request.account_id, request.actor_id):
            raise PermissionError("own current delegated actor required")
        reader = FuturesPaperAccountReader(b, self.connection_parameters, self.clock)
        published = FuturesAssetReader(self.status_root, self.clock).publication(b.tenant_id, b.account_id)
        if published is None or published.recovery is None:
            raise ValueError("acknowledged own recovery publication required")
        # Nonblocking exclusive lock: no parallel feed/API writer, reset or forced shutdown.
        with FuturesPaperJournal.restore(Path(location["journal"]), config_digest=spec.config.config_digest,
                                         minimum_receipt=published.journal_receipt) as journal:
            state = journal.state
            current = reader()
            if ((current.settings_revision, current.basket_limit) != (
                    state.settings_revision, state.config.profile.plan.configured_limit)):
                raise ValueError("current own planning not yet acknowledged")
            with FuturesAssetPublisher(self.status_root, journal, clock=self.clock,
                                       recovery_enabled=True) as publisher:
                publisher.check()
                # Full restore already proves model positions/orders/booked liquidation.
                checked = reader()
                if replace(checked, observed_at=current.observed_at) != current:
                    raise ValueError("own permission/settings changed before manual commit")
                after = journal.append("manual_recovery", request=request,
                    expected_revision=request.expected_revision, at=self.clock())
                publisher.publish(expected_revision=after.revision)
                return journal.receipt
