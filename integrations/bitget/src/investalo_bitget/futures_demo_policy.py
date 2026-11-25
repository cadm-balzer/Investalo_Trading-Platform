"""Account/key-bound Demo exception approved on 2026-11-25.

Trusted installation policy, never a browser claim, broker maximum,
measured zero, or authority to send an order.
"""
from dataclasses import dataclass, field
from .futures_demo import DemoBinding, DemoRejected, digest


@dataclass(frozen=True, repr=False)
class ApprovedDemoStrategyPolicy:
    binding: DemoBinding
    credential_revision: int
    storage_version: int
    schema: str = field(default="bitget-demo-strategy-unconfirmed-native/1", init=False)
    accepted_unknowns: tuple[str, ...] = field(default=(
        "grant", "market_maximum", "actual_costs_before_fill", "orders_before_api_window"), init=False)

    def __post_init__(self):
        if (type(self.binding) is not DemoBinding or self.binding.environment != "demo"
                or self.binding.leverage != 2 or type(self.credential_revision) is not int
                or self.credential_revision != 1 or type(self.storage_version) is not int
                or not 1 <= self.storage_version <= 9007199254740991):
            raise DemoRejected("own_approved_demo_strategy_policy_required")

    @property
    def policy_digest(self):
        return digest((self.schema, self.binding.record(), self.credential_revision,
                       self.storage_version, self.accepted_unknowns, "approved-2026-11-25"))

    def check(self, binding, credential_revision=None, storage_version=None):
        if (binding != self.binding
                or credential_revision is not None and credential_revision != self.credential_revision
                or storage_version is not None and storage_version != self.storage_version):
            raise DemoRejected("approved_demo_policy_account_or_key_changed")
