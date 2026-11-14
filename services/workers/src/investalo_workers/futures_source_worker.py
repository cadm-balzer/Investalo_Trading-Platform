"""Archived unsigned Classic feed coordinator; existing own Paper genesis only."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from investalo_marketdata.futures_paper_feed import hour_boundary
from investalo_trading.futures_ledger import timestamp
from investalo_trading.futures_paper import PaperFunding
from investalo_trading.futures_paper_minute import PaperMarkMinute

H1 = timedelta(hours=1)


@dataclass(frozen=True)
class FuturesSourceCycle:
    outcome: str
    revision: int
    entries: int = 0
    closures: int = 0
    execution_enabled: bool = False


@dataclass(frozen=True)
class FuturesSourceWorker:
    journal: object
    archive: object
    publisher: object
    clock: object = lambda: datetime.now(timezone.utc)
    commit_guard: object = lambda: None

    def _guard(self, guard):
        guard()
        self.publisher.check()
        self.journal.source_checkpoint()

    def _commit(self, kind, before, guard, **arguments):
        self._guard(guard)
        self.commit_guard()
        after = self.journal.append(kind, expected_revision=before.revision,
                                    at=timestamp(self.clock()), **arguments)
        self._guard(guard)
        self.publisher.publish(expected_revision=after.revision)
        return after

    def _market(self, state, guard, *, warmup=False):
        end = state.config.trading_from if warmup else hour_boundary(self.clock())
        start = state.signal.as_of if warmup else state.signal.last_hour.close_time - H1
        if start != hour_boundary(start) or end != hour_boundary(end) or not 1 <= (end - start) // H1 <= 72:
            raise ValueError("bounded own closed native history window required")
        if warmup and (end - start) // H1 < 16:
            raise ValueError("own genesis must declare at least16 closed warmup hours")
        if not warmup and any(b.quantity for b in state.signal.economic.ledger.baskets):
            if end - state.signal.last_hour.close_time > H1:
                raise ValueError("open Paper source gap requires reconciliation")
        self._guard(guard)
        return self.archive.market(start=start, end=end, funding_start=state.signal.as_of,
                                   guard=lambda: self._guard(guard))

    def _pending(self, cursor):
        prior = self.archive.load(cursor.market) if cursor.market is not None else None
        if cursor.pending is None:
            return prior, None
        pending = cursor.pending
        market, minute = self.archive.load(pending.market), self.archive.load(pending.minute)
        native = tuple(PaperFunding(f.symbol, f.native_id, f.settled_at, f.rate) for f in minute.funding)
        minutes = tuple(PaperMarkMinute(
            f.symbol, m.open_time, m.close_time, m.open, m.high, m.low, m.close)
            for f, m in zip(minute.funding, minute.minutes, strict=True))
        current_native = tuple(PaperFunding(f.symbol, f.native_id, f.settled_at, f.rate)
                               for f in market.funding if f.settled_at == minute.settled_at)
        value = pending.settlement
        if (native != current_native or native != value.funding or minutes != value.minutes
                or value.valuation_digest != minute.data_digest
                or value.source_collected_at != minute.collected_at
                or pending.prior != cursor.market):
            raise ValueError("pending journal funding differs from archived native evidence")
        return prior, value

    def run_once(self, *, guard=lambda: None):
        self._guard(guard)
        before, _, cursor = self.journal.source_checkpoint()
        if cursor.warmup is None and before.revision:
            raise ValueError("existing unbound Paper history needs separate source migration")
        if (before.signal.economic.liquidation_required or any(
                "liquidation_settlement_required" in s.exit_reasons for s in before.signal.signals)):
            raise ValueError("liquidation requires manual reconciliation before source continuation")
        if not before.warmed:
            ref, market = self._market(before, guard, warmup=True)
            after = self._commit("source_warmup", before, guard, hours=market.hours, source=ref)
            return FuturesSourceCycle("warmed", after.revision)
        self.archive.load(cursor.warmup)
        prior, settlement = self._pending(cursor)
        active = {b.symbol for b in before.signal.economic.ledger.baskets if b.quantity}
        now = timestamp(self.clock())
        due = (min((f.next_update for f in prior.forecasts
                    if f.symbol in active and f.next_update <= now), default=None)
               if prior is not None and settlement is None else None)
        minute_ref = minute = None
        if due is not None:
            if now - due > H1:
                raise ValueError("funding publication gap requires reconciliation")
            if now < due + timedelta(minutes=1):
                return FuturesSourceCycle("waiting_funding_minute", before.revision)
            minute_ref, minute = self.archive.minute(due, guard=lambda: self._guard(guard))
        market_ref, market = self._market(before, guard)
        if settlement is None and prior is not None and active:
            native_due = min((f.settled_at for f in market.funding
                              if f.symbol in active and before.signal.as_of < f.settled_at <= market.collected_at),
                             default=None)
            target = min(t for t in (due, native_due) if t is not None) if due or native_due else None
            if target is not None:
                now = timestamp(self.clock())
                if now - target > H1:
                    raise ValueError("native funding gap requires reconciliation")
                if now < target + timedelta(minutes=1):
                    return FuturesSourceCycle("waiting_funding_minute", before.revision)
                if minute is None or minute.settled_at != target:
                    minute_ref, minute = self.archive.minute(target, guard=lambda: self._guard(guard))
                settlement = minute.paper_minute_settlement(before, observation=market, previous=prior)
                before = self._commit(
                    "source_minute_settlement", before, guard, settlement=settlement,
                    market=market_ref, minute=minute_ref, prior=cursor.market)
                if before.signal.economic.liquidation_required:
                    return FuturesSourceCycle("liquidation_reconciliation_required", before.revision)
        batch = market.paper_batch(before, previous=prior, settlement=settlement)
        after = self._commit("source_batch", before, guard, batch=batch,
                             source=market_ref, prior=cursor.market)
        return FuturesSourceCycle(
            "funding_and_quotes" if settlement is not None else "quotes", after.revision,
            len(after.signal.economic.stages) - len(before.signal.economic.stages),
            after.signal.economic.ledger.closed_baskets - before.signal.economic.ledger.closed_baskets)
