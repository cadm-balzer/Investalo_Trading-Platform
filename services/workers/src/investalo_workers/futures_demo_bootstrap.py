"""Bounded, restartable indicator initialization for an owned native Demo journal.

The injected source supplies original native frames; the current actor/credential
guard is mandatory. This helper neither installs an account source nor sends orders.
"""
from dataclasses import dataclass

from investalo_trading.futures_broker_bootstrap import (
    BrokerCurrentLedgerState, WARMUP_HOURS, WARMUP_BATCH,
)
from investalo_trading.futures_broker_journal import BrokerEntryJournal


@dataclass(frozen=True)
class DemoBootstrapProgress:
    warmed_hours: int
    required_hours: int
    ready: bool
    revision: int
    state_digest: str
    execution_enabled: bool = False


class DemoBootstrapWorker:
    def __init__(self, journal, source, guard, clock):
        if (type(journal) is not BrokerEntryJournal or not callable(source)
                or not callable(guard) or not callable(clock)):
            raise ValueError("owned native journal and independent source/actor guard required")
        self.journal, self.source, self.guard, self.clock = journal, source, guard, clock

    def warm_once(self):
        self.guard()
        state = self.journal.state
        ledger = state.book.signal.economic.ledger
        if type(ledger) is not BrokerCurrentLedgerState:
            raise ValueError("current native genesis required; no Paper journal adoption")
        if state.warmed_hours < WARMUP_HOURS:
            end = ledger.financial_started_at.replace(minute=0, second=0, microsecond=0)
            count = min(WARMUP_BATCH, WARMUP_HOURS-state.warmed_hours)
            frames = self.source(
                symbols=state.book.signal.profile.plan.symbols, end=end,
                offset=state.warmed_hours, count=count,
            )
            self.guard()
            if type(frames) is not tuple or len(frames) != count:
                raise ValueError("complete original bounded native warmup batch required")
            state = self.journal.append("warmup", frames=frames, expected_revision=state.revision,
                                        at=self.clock())
        self.guard()
        return DemoBootstrapProgress(state.warmed_hours, WARMUP_HOURS,
            state.warmed_hours == WARMUP_HOURS, state.revision, state.state_digest)
