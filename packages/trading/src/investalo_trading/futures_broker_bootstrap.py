"""Current financial genesis and historical indicators, without historical trades."""
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from decimal import Decimal

from .capital_digest import CapitalCanonical, digest
from .futures_broker_entries import BrokerEntryBook
from .futures_capital_research import CapitalResearchState
from .futures_capital_signals import (
    CapitalH1SignalProfile, CapitalHour, start_capital_signals,
)
from .futures_ledger import (
    FuturesLedgerState, LedgerBasket, MarkBatch, number, timestamp, _halt_reasons,
)
from .futures_signals import IndicatorParameters
from .identity_history import IdentityHistory
from .indicators import advance
from .models import precise
from .futures_replay_journal import _sha

VERSION = "bitget-demo-current-bootstrap/1"
WARMUP_HOURS = 300
WARMUP_BATCH = 24
ZERO = Decimal(0)


@dataclass(frozen=True)
class _NativeProfileProjection:
    profile: CapitalH1SignalProfile


@dataclass(frozen=True)
class BrokerFlatAccount(CapitalCanonical):
    """An independent native producer must confirm all these current amounts."""
    equity: Decimal
    available: Decimal
    locked: Decimal
    unrealized_pnl: Decimal
    isolated_margin: Decimal
    position_count: int
    wallet_at: datetime
    positions_at: datetime
    source_digest: str

    def __post_init__(self):
        number(self.equity, positive=True)
        number(self.available, positive=True)
        for amount in (self.locked, self.unrealized_pnl, self.isolated_margin):
            number(amount)
        timestamp(self.wallet_at)
        timestamp(self.positions_at)
        _sha(self.source_digest)
        if (self.equity != self.available or any((self.locked, self.unrealized_pnl, self.isolated_margin))
                or type(self.position_count) is not int or self.position_count != 0
                or abs(self.wallet_at - self.positions_at) > timedelta(seconds=5)):
            raise ValueError("confirmed flat own-capital account required; no position adoption")


@dataclass(frozen=True)
class BrokerCurrentLedgerState(FuturesLedgerState):
    """First partial day starts at the actual snapshot; future days at native midnight."""
    financial_started_at: datetime

    def _validate_day_basis(self, day):
        started = timestamp(self.financial_started_at)
        from .futures_broker_plan import CapitalBrokerPlan
        if type(self.plan) is CapitalBrokerPlan:
            if started > self.as_of or day < started or day > self.as_of:
                raise ValueError("actual native observation day basis required")
            return
        if (started > self.as_of or day < started
                or day != started and day != day.replace(hour=0, minute=0, second=0, microsecond=0)):
            raise ValueError("native first-day basis or subsequent exact midnight required")


@precise
def start_current_broker_signals(profile, trade, marks, account, at):
    at = timestamp(at)
    if (type(profile) is not CapitalH1SignalProfile or type(account) is not BrokerFlatAccount
            or profile.plan.initial_equity != account.equity or getattr(profile.plan, "epochs", ())
            or any(not timedelta(0) <= at - source <= timedelta(seconds=5)
                   for source in (account.wallet_at, account.positions_at))):
        raise ValueError("fresh current account and own unchanged initial capital required")
    for values in (trade, marks):
        batch = MarkBatch(values)
        if tuple(m.symbol for m in batch.marks) != profile.plan.symbols:
            raise ValueError("complete original current trade/mark quotes required")
    source = digest((VERSION, profile.profile_digest, account, trade, marks, at))
    ledger = BrokerCurrentLedgerState(
        profile.plan, 0, at, 0, at, account.equity, source, account.available,
        tuple(LedgerBasket(m.symbol, m.price, at) for m in marks), (), 0, ZERO,
        digest((VERSION, source, "current-financial-genesis")), at,
    )
    ledger = replace(ledger, halt_reasons=_halt_reasons(ledger))
    economic = CapitalResearchState(
        ledger, 0, at, (), (), (), IdentityHistory("event"),
        digest((VERSION, ledger.state_digest)),
    )
    return start_capital_signals(profile, economic, trade)


@precise
def warm_broker_hours(book, frames, already_warmed, at):
    """Only native historical indicators advance. Current money/quotes stay intact."""
    at = timestamp(at)
    signal = book.signal
    ledger = signal.economic.ledger
    if (type(book) is not BrokerEntryBook or type(ledger) is not BrokerCurrentLedgerState
            or type(frames) is not tuple or not 1 <= len(frames) <= WARMUP_BATCH
            or type(already_warmed) is not int or not 0 <= already_warmed < WARMUP_HOURS
            or already_warmed + len(frames) > WARMUP_HOURS or signal.economic.revision
            or book.pending is not None or len(book.commands) or at < book.as_of
            or signal.last_entry_at is not None):
        raise ValueError("bounded untouched current genesis warmup required")
    end = ledger.financial_started_at.replace(minute=0, second=0, microsecond=0)
    opened = end - timedelta(hours=WARMUP_HOURS-already_warmed)
    symbols = signal.profile.plan.symbols
    updated, group = signal.signals, signal.h4_buffer
    for frame in frames:
        if (type(frame) is not CapitalHour or frame.trade[0].open_time != opened
                or frame.close_time > end
                or tuple(b.symbol for b in frame.trade) != tuple(f"{s}:USDT-M:trade" for s in symbols)
                or tuple(b.symbol for b in frame.mark) != tuple(f"{s}:USDT-M:mark" for s in symbols)):
            raise ValueError("complete original 300 contiguous closed native H1 frames required")
        warmed = []
        for previous, candle in zip(updated, frame.trade, strict=True):
            indicator = advance(previous.entry_indicator, candle, IndicatorParameters())
            protection = advance(previous.protection_indicator, candle, IndicatorParameters())
            below = indicator.rsi is not None and indicator.rsi < 30
            warmed.append(replace(previous, entry_indicator=indicator, protection_indicator=protection,
                below_count=min(2, previous.below_count+1) if below else 0))
        updated = tuple(warmed)
        # Keep calendar-aligned H4 scratch data expected by the shared H1 reducer.
        group = () if frame.close_time.hour % 4 == 0 else (*group, frame)
        opened = frame.close_time
    next_signal = replace(signal, revision=signal.revision+1, as_of=at,
        signals=updated, last_hour=frames[-1], h4_buffer=group,
        audit_head=digest((VERSION, signal.audit_head, frames, already_warmed, at)))
    return replace(book, signal=next_signal, revision=book.revision+1, as_of=at,
        audit_head=digest((VERSION, book.audit_head, next_signal.state_digest)))


@precise
def advance_native_hour(book, frame, at):
    """Advance closed native indicators without backdating current money/fills."""
    from .futures_broker_plan import CapitalBrokerPlan
    at = timestamp(at)
    s = book.signal
    if (type(s.profile.plan) is not CapitalBrokerPlan or type(frame) is not CapitalHour
            or s.last_hour is None or frame.trade[0].open_time != s.last_hour.close_time
            or frame.close_time > at or at < book.as_of
            or tuple(b.symbol for b in frame.trade) != tuple(f"{n}:USDT-M:trade" for n in s.profile.plan.symbols)
            or tuple(b.symbol for b in frame.mark) != tuple(f"{n}:USDT-M:mark" for n in s.profile.plan.symbols)):
        raise ValueError("original contiguous completed native hour required")
    updated = []
    for old, bar, basket in zip(s.signals, frame.trade, s.economic.ledger.baskets, strict=True):
        indicator = advance(old.entry_indicator, bar, IndicatorParameters())
        below = indicator.rsi is not None and indicator.rsi < 30
        updated.append(replace(old, entry_indicator=indicator,
            protection_indicator=advance(old.protection_indicator, bar, IndicatorParameters()),
            below_count=min(2, old.below_count+1) if below else 0,
            rearmed=old.rearmed or bool(basket.quantity and indicator.rsi is not None and indicator.rsi > 30)))
    fresh = timedelta(0) <= at-frame.close_time <= timedelta(seconds=30)
    next_signal = replace(s, revision=s.revision+1, as_of=at, signals=tuple(updated), last_hour=frame,
        h4_buffer=(), last_entry_at=frame.close_time if fresh else None,
        audit_head=digest(("native-hour/1", s.audit_head, frame, at)))
    return replace(book, signal=next_signal, revision=book.revision+1, as_of=at,
        audit_head=digest(("native-hour/1", book.audit_head, next_signal.state_digest)))


def native_plan_update(book, at, *, limit=None, profit=False):
    from .futures_broker_plan import CapitalBrokerPlan
    from .futures_paper_profit import assess_profit_epoch, refresh_profit_budgets
    from types import SimpleNamespace
    if type(book.signal.profile.plan) is not CapitalBrokerPlan or book.pending is not None:
        raise ValueError("idle own native plan required")
    plan = book.signal.profile.plan
    if limit is not None:
        if type(limit) is not int or not 3 <= limit <= 7:
            raise ValueError("native basket ceiling required")
        plan = replace(plan, configured_limit=limit)
    if profit:
        state = SimpleNamespace(config=SimpleNamespace(profile=book.signal.profile), signal=book.signal,
            warmed=True, observed_at=book.as_of)
        assessment = assess_profit_epoch(state, now=at)
        if assessment.reasons:
            raise ValueError("native profit allocation not eligible")
        plan = replace(plan, epochs=(*plan.epochs, assessment.epoch))
    profile = replace(book.signal.profile, plan=plan)
    economic = replace(book.signal.economic, ledger=replace(book.signal.economic.ledger, plan=plan))
    signal = replace(book.signal, profile=profile, economic=economic)
    _, signal = refresh_profit_budgets(_NativeProfileProjection(profile), signal)
    signal = replace(signal, revision=signal.revision+1, as_of=at,
        audit_head=digest(("native-plan/1", signal.audit_head, plan, at)))
    return replace(book, signal=signal, revision=book.revision+1, as_of=at,
        audit_head=digest(("native-plan/1", book.audit_head, signal.state_digest)))
