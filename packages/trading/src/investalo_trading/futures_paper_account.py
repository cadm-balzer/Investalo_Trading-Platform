"""Trusted own Paper allocation and latest committed planning evidence."""
from dataclasses import dataclass, replace
from datetime import datetime
from uuid import UUID

from .allocation import revision
from .capital_digest import digest
from .futures_ledger import timestamp
from .futures_paper import _check, _finish
from .futures_replay_journal import _sha


@dataclass(frozen=True)
class PaperAccountBinding:
    tenant_id: str
    account_id: str
    user_id: str
    oidc_issuer: str
    oidc_subject: str
    auth_epoch: int
    authorized_at: datetime

    def __post_init__(self):
        for value in (self.tenant_id, self.account_id, self.user_id):
            if type(value) is not str or str(UUID(value)) != value:
                raise ValueError("canonical own UUID binding required")
        if (type(self.oidc_issuer) is not str or not self.oidc_issuer.startswith("https://")
                or len(self.oidc_issuer) > 2048 or type(self.oidc_subject) is not str
                or not 1 <= len(self.oidc_subject) <= 255):
            raise ValueError("explicit own administrative identity binding required")
        revision(self.auth_epoch)
        timestamp(self.authorized_at)

    @property
    def binding_digest(self):
        return digest(("futures-paper-account-binding/1", self))


@dataclass(frozen=True)
class PaperSettingsEvidence:
    tenant_id: str
    account_id: str
    binding_digest: str
    settings_revision: int
    basket_limit: int
    observed_at: datetime

    def __post_init__(self):
        for value in (self.tenant_id, self.account_id):
            if type(value) is not str or str(UUID(value)) != value:
                raise ValueError("canonical own settings UUID required")
        _sha(self.binding_digest)
        revision(self.settings_revision)
        if type(self.basket_limit) is not int or not 3 <= self.basket_limit <= 7:
            raise ValueError("own bounded basket ceiling required")
        timestamp(self.observed_at)
        if self.settings_revision == 0 and self.basket_limit != 5:
            raise ValueError("unsaved planning default is five")


def apply_account_settings(state, evidence, expected_revision, at):
    """One actual latest DB revision, never invent skipped intermediate values."""
    _check(state, expected_revision, at)
    at = timestamp(at)
    plan = state.config.profile.plan
    if (type(evidence) is not PaperSettingsEvidence
            or (evidence.tenant_id, evidence.account_id) != (plan.tenant_id, plan.account_id)
            or not 0 <= (at - evidence.observed_at).total_seconds() <= 30
            or evidence.settings_revision <= state.settings_revision or at < state.signal.as_of):
        raise ValueError("fresh strictly newer own committed settings required")
    plan = replace(plan, configured_limit=evidence.basket_limit)
    profile = replace(state.config.profile, plan=plan)
    economic = replace(state.signal.economic, ledger=replace(state.signal.economic.ledger, plan=plan))
    signal = replace(state.signal, profile=profile, economic=economic)
    return _finish(state, ("account_settings", evidence), config=replace(state.config, profile=profile),
                   signal=signal, settings_revision=evidence.settings_revision, observed_at=at)
