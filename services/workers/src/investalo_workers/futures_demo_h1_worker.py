"""Actual H1 orchestration. Native fills only, retained GET-only recovery."""
from dataclasses import dataclass, replace
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from investalo_trading.futures_broker_journal import BrokerEntryJournal
from investalo_trading.futures_broker_entries import observe_broker_prices, prepare_broker_entry
from investalo_trading.futures_capital_signals import assess_capital_signal
from investalo_trading.futures_broker_bootstrap import WARMUP_HOURS
from investalo_trading.futures_broker_plan import CapitalBrokerPlan
from .futures_demo_bootstrap import DemoBootstrapWorker

D = Decimal


@dataclass(frozen=True)
class DemoH1Progress:
    state: str
    detail: str
    revision: int
    execution_enabled: bool


class DemoH1Worker:
    def __init__(self, journal, consumer, warmup, clock):
        if type(journal) is not BrokerEntryJournal or type(journal.state.book.signal.profile.plan) is not CapitalBrokerPlan:
            raise ValueError("own operative native journal required")
        self.journal, self.consumer, self.warmup, self.clock = journal, consumer, warmup, clock

    def _append(self, kind, **terms):
        return self.journal.append(kind, expected_revision=self.journal.state.revision, at=self.clock(), **terms)

    def run_once(self, ports):
        control = self.consumer.sync()
        ports.guard()
        if self.journal.state.warmed_hours < WARMUP_HOURS:
            p = DemoBootstrapWorker(self.journal, self.warmup, ports.guard, self.clock).warm_once()
            return DemoH1Progress("waiting", f"warmup:{p.warmed_hours}/300", p.revision, False)
        if self.journal.state.book.pending is not None:
            if self.journal.state.current_attempt is None:
                # Every actual POST is preceded by its durable attempt. No attempt
                # means no native POST, even if a consent marker already survived.
                self._append("cancel_preparation", order_digest=self.journal.state.book.pending.order_digest)
            else:
                ports.dispatcher.observe(context=ports.owner, expected_revision=self.journal.state.revision)
                pending = self.journal.state.book.pending is not None
                return DemoH1Progress("blocked" if pending else "waiting",
                    "order_reconciliation" if pending else "order_settled", self.journal.state.revision, not pending)
        at = self.clock()
        if control.basket_limit != self.journal.state.book.signal.profile.plan.configured_limit:
            self._append("native_limit", limit=control.basket_limit)
        end = at.replace(minute=0, second=0, microsecond=0)
        last = self.journal.state.book.signal.last_hour.close_time
        new_hour = last < end
        if new_hour:
            window = self.warmup.collect(self.journal.state.book.signal.profile.plan.symbols, end)
            frames = tuple(f for f in window.frames if f.close_time > last)
            if not frames or frames[0].trade[0].open_time != last:
                raise ValueError("native_history_gap")
            for frame in frames:
                self._append("native_hour", frame=frame)
        # Update actual funding before financial actions. Empty complete native
        # windows are checked every pulse but committed only once per hour.
        if ports.dispatcher.funding(context=ports.owner, expected_revision=self.journal.state.revision,
                                    commit_empty=new_hour) is None:
            return DemoH1Progress("blocked", "funding_reconciliation", self.journal.state.revision, False)
        market = ports.market.read()
        at = self.clock()
        if not timedelta(0) <= at-market.observed_at <= timedelta(seconds=5):
            raise ValueError("native_quote_stale")
        old = self.journal.state.book
        projected = observe_broker_prices(old, market.trade, market.marks, "quote-"+market.source_digest, old.revision, at)
        changed_protection = projected.signal.signals != old.signal.signals
        fresh_entry = projected.signal.last_entry_at is not None and timedelta(0) <= (
            at-projected.signal.last_entry_at) <= timedelta(seconds=30)
        if new_hour or changed_protection or fresh_entry:
            self._append("prices", trade=market.trade, marks=market.marks, event_id="quote-"+market.source_digest)
        if new_hour:
            from investalo_trading.futures_paper_profit import assess_profit_epoch
            from types import SimpleNamespace
            s = self.journal.state.book.signal
            assessment = assess_profit_epoch(SimpleNamespace(config=SimpleNamespace(profile=s.profile),
                signal=s, warmed=True, observed_at=self.journal.state.book.as_of), now=self.clock())
            if not assessment.reasons:
                self._append("native_profit")
        book = self.journal.state.book
        for signal, basket in zip(book.signal.signals, book.signal.economic.ledger.baskets, strict=True):
            if basket.quantity and signal.exit_reasons:
                if "liquidation_settlement_required" in signal.exit_reasons:
                    return DemoH1Progress("blocked", "native_position_reconciliation", self.journal.state.revision, False)
                self._append("prepare_exit", symbol=basket.symbol, command_id="exit-"+uuid4().hex)
                ports.dispatcher.dispatch(context=ports.owner, expected_revision=self.journal.state.revision)
                return DemoH1Progress("waiting", "exit_reconciliation", self.journal.state.revision, True)
        if control.action == "pause":
            return DemoH1Progress("paused", "buys_paused_positions_managed", self.journal.state.revision, False)
        if control.basket_limit != book.signal.profile.plan.configured_limit:
            return DemoH1Progress("blocked", "basket_setting_changed", self.journal.state.revision, False)
        if fresh_entry:
            plan = book.signal.profile.plan
            for symbol in control.assets:
                ask = dict(market.asks)[symbol]
                price = plan.adverse_price(symbol, ask*(1+book.signal.profile.slippage), buy=True)
                command_id = "entry-"+uuid4().hex
                try:
                    prepare_broker_entry(book, symbol, price, command_id, book.revision, self.clock())
                except ValueError:
                    continue
                self._append("prepare", symbol=symbol, planning_price=price, command_id=command_id)
                ports.dispatcher.dispatch(context=ports.owner, expected_revision=self.journal.state.revision)
                return DemoH1Progress("waiting", "entry_reconciliation", self.journal.state.revision, True)
        ports.guard()
        return DemoH1Progress("running", "waiting_for_h1_signal", self.journal.state.revision, True)
