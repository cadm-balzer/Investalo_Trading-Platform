"""Local injected-feed Paper worker. No launcher, secrets or broker order client."""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from investalo_trading.futures_capital_signals import CapitalHour
from investalo_trading.futures_paper import FuturesPaperState, PaperBatch
from investalo_trading.futures_paper_journal import FuturesPaperJournal
from investalo_trading.futures_paper_settlement import PaperSettlement
from investalo_trading.futures_paper_minute import PaperMinuteSettlement


class FuturesPaperFeed(Protocol):
    def warmup(self, state: FuturesPaperState) -> tuple[CapitalHour, ...]: ...
    def batch(self, state: FuturesPaperState) -> PaperBatch: ...


class FuturesPaperSettlementFeed(FuturesPaperFeed, Protocol):
    def settlement(self, state: FuturesPaperState) -> PaperSettlement | PaperMinuteSettlement: ...


@dataclass(frozen=True)
class FuturesPaperCycle:
    revision: int
    entries: int
    closures: int
    state_digest: str
    execution_enabled: bool = False


@dataclass(frozen=True)
class FuturesPaperWorker:
    journal: FuturesPaperJournal
    feed: FuturesPaperFeed
    clock: object = lambda: datetime.now(timezone.utc)

    def warmup(self, *, guard=lambda: None):
        guard()
        state = self.journal.state
        hours = self.feed.warmup(state)
        guard()
        return self.journal.append("warmup", hours=hours, expected_revision=state.revision, at=self.clock())

    def run_once(self, *, guard=lambda: None):
        guard()
        before = self.journal.state
        batch = self.feed.batch(before)
        guard()
        after = self.journal.append("batch", batch=batch, expected_revision=before.revision, at=self.clock())
        return FuturesPaperCycle(
            after.revision, len(after.signal.economic.stages) - len(before.signal.economic.stages),
            after.signal.economic.ledger.closed_baskets - before.signal.economic.ledger.closed_baskets,
            after.state_digest,
        )

    def settle_once(self, *, guard=lambda: None):
        """Explicit funding-only step with archived exact or declared model evidence."""
        guard()
        before = self.journal.state
        settlement = self.feed.settlement(before)
        guard()
        kind = "minute_settlement" if type(settlement) is PaperMinuteSettlement else "settlement"
        after = self.journal.append(
            kind, settlement=settlement, expected_revision=before.revision, at=self.clock())
        return FuturesPaperCycle(after.revision, 0, 0, after.state_digest)
