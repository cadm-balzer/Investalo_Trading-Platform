"""Apply committed own planning before the bounded archived source worker."""
from dataclasses import dataclass, replace

from investalo_trading.futures_ledger import timestamp
from investalo_trading.futures_paper_account import PaperSettingsEvidence
from investalo_trading.futures_paper_profit import assess_profit_epoch
from investalo_trading.futures_paper_profit_plan import CapitalPaperProfitPlan


@dataclass(frozen=True)
class FuturesAccountWorker:
    source: object
    read_account: object

    def _read(self):
        value = self.read_account()
        state = self.source.journal.state
        plan = state.config.profile.plan
        if (type(value) is not PaperSettingsEvidence
                or (value.tenant_id, value.account_id) != (plan.tenant_id, plan.account_id)
                or not 0 <= (timestamp(self.source.clock()) - value.observed_at).total_seconds() <= 30
                or value.settings_revision < state.settings_revision
                or value.settings_revision == state.settings_revision
                and value.basket_limit != plan.configured_limit):
            raise ValueError("fresh coherent own account/settings evidence required")
        return value

    def _verify(self, expected):
        current = self._read()
        if replace(current, observed_at=expected.observed_at) != expected:
            raise ValueError("account settings changed during source capture; reconcile before commit")

    def _before_commit(self, evidence):
        self.source.commit_guard()
        self._verify(evidence)

    def run_once(self, *, guard=lambda: None):
        self.source._guard(guard)
        before, _, cursor = self.source.journal.source_checkpoint()
        if before.revision and cursor.warmup is None:
            raise ValueError("unbound history needs separate source migration")
        evidence = self._read()
        # Warmup is the first source command; settings do not create a trading history.
        if before.warmed and evidence.settings_revision > before.settings_revision:
            self._before_commit(evidence)
            self.source._guard(guard)
            after = self.source.journal.append(
                "account_settings", evidence=evidence, expected_revision=before.revision,
                at=timestamp(self.source.clock()))
            self.source._guard(guard)
            self.source.publisher.publish(expected_revision=after.revision)
        elif not before.warmed and evidence.basket_limit != before.config.profile.plan.configured_limit:
            raise ValueError("cold allocated profile differs from committed planning")
        source = replace(self.source, commit_guard=lambda: self._before_commit(evidence))
        result = source.run_once(guard=guard)
        state, _, cursor = self.source.journal.source_checkpoint()
        # Fresh source-managed quotes only; funding-only/pending observations never grant.
        if (type(state.config.profile.plan) is CapitalPaperProfitPlan
                and result.outcome in ("quotes", "funding_and_quotes") and cursor.pending is None
                and not assess_profit_epoch(state, now=timestamp(self.source.clock())).reasons):
            source._guard(guard)
            source.commit_guard()
            # Eligibility is recomputed in the journal reducer under its CAS lock.
            after = self.source.journal.append("profit_epoch", expected_revision=state.revision,
                                               at=timestamp(self.source.clock()))
            source._guard(guard)
            source.publisher.publish(expected_revision=after.revision)
            result = replace(result, revision=after.revision)
        return result
