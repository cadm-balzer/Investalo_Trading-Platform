"""Pure paper-domain transitions. No network, broker credentials or authentication."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from decimal import Decimal, localcontext

from .indicators import advance
from .models import (
    AccountState, BasketState, Candle, ClosedBasket, DomainEvent, EngineState,
    EntryStage, Fill, InstrumentRules, ManualPreview, OrderIntent, OrderRecord,
    OrderStatus, Quote, Side, StrategyConfig, TradingRejected, Transition,
    floor_step, positive, precise, utc,
)
from .snapshot import digest

D = Decimal


def _basket(state: EngineState, value: BasketState) -> EngineState:
    return replace(state, baskets=tuple(value if b.symbol == value.symbol else b for b in state.baskets))


def _order(state: EngineState, value: OrderRecord) -> EngineState:
    return replace(state, orders=tuple(value if o.intent.intent_id == value.intent.intent_id else o
                                      for o in state.orders))


@dataclass(frozen=True)
class CryptoEngine:
    config: StrategyConfig = StrategyConfig()
    instrument_rules: tuple[InstrumentRules, ...] = ()

    def __post_init__(self) -> None:
        names = tuple(r.symbol for r in self.instrument_rules)
        if len(names) != len(set(names)) or any(s not in self.config.symbols for s in names):
            raise ValueError("invalid instrument rules")

    @precise
    def start(self, tenant_id: str, account_id: str, at: datetime) -> EngineState:
        if not tenant_id or not account_id:
            raise ValueError("tenant and account IDs are required")
        at = utc(at)
        return EngineState(
            self.config.version,
            AccountState(tenant_id, account_id, self.config.initial_equity,
                         self.config.initial_equity, at.date(), self.config.initial_equity),
            tuple(BasketState(symbol) for symbol in self.config.symbols),
            configuration_digest=digest((self.config, self.instrument_rules)),
        )

    def _validate(self, state: EngineState, symbol: str | None = None) -> None:
        if state.version != self.config.version or state.account.initial_equity != self.config.initial_equity:
            raise ValueError("state and strategy configuration differ")
        if state.configuration_digest != digest((self.config, self.instrument_rules)):
            raise ValueError("state belongs to a different immutable configuration")
        if tuple(b.symbol for b in state.baskets) != self.config.symbols:
            raise ValueError("state symbols differ from strategy configuration")
        if symbol is not None and symbol not in self.config.symbols:
            raise TradingRejected("unsupported_symbol")

    def rules(self, symbol: str) -> InstrumentRules:
        return next((r for r in self.instrument_rules if r.symbol == symbol), InstrumentRules(symbol))

    def _active(self, state: EngineState, basket: BasketState) -> tuple[OrderRecord, ...]:
        return tuple(o for o in state.orders if o.intent.basket_id == basket.basket_id and o.unresolved)

    @precise
    def risk_reasons(self, state: EngineState, now: datetime) -> tuple[str, ...]:
        self._validate(state)
        now = utc(now)
        reasons: list[str] = []
        if state.account.trading_day != now.date():
            reasons.append("daily_baseline_required")
        elif state.equity <= state.account.day_start_equity * (1 - self.config.daily_loss_fraction):
            reasons.append("daily_loss_limit")
        if state.equity <= state.account.initial_equity * (1 - self.config.initial_loss_fraction):
            reasons.append("initial_loss_limit")
        if state.account.cash < 0:
            reasons.append("negative_cash")
        return tuple(reasons)

    @precise
    def reset_day(self, state: EngineState, midnight: datetime) -> EngineState:
        """Caller first supplies midnight quotes; missing baselines block new buys.

        The historical simulator uses its known candle-boundary quote.
        This function does not clear a latched risk halt.
        """
        self._validate(state)
        midnight = utc(midnight)
        if midnight.time().replace(tzinfo=None) != datetime.min.time():
            raise ValueError("daily baseline timestamp must be midnight UTC")
        if midnight.date() < state.account.trading_day:
            raise ValueError("cannot reset backwards")
        if midnight.date() == state.account.trading_day:
            return state
        if any(b.quantity and (state.quote(b.symbol) is None
                               or state.quote(b.symbol).observed_at != midnight) for b in state.baskets):
            raise TradingRejected("midnight_valuation_required")
        return replace(state, account=replace(state.account, trading_day=midnight.date(),
                                               day_start_equity=state.equity))

    def resume(self, state: EngineState, now: datetime) -> EngineState:
        """Explicit operator action; caller must enforce tenant authorization/MFA."""
        if self.risk_reasons(state, now):
            raise TradingRejected("risk_limits_still_breached")
        if any(o.unresolved for o in state.orders):
            raise TradingRejected("unresolved_order")
        return replace(state, account=replace(state.account, halted=False, halt_reasons=()))

    @precise
    def resume_basket(self, state: EngineState, symbol: str, now: datetime) -> EngineState:
        """Conscious restart after a basket risk-stop; application enforces MFA.

        Flatness and authoritative order reconciliation are mandatory. Signals
        collected during the stop cannot immediately create a replacement entry.
        """
        self._validate(state, symbol)
        if state.account.halted or self.risk_reasons(state, now):
            raise TradingRejected("account_risk_still_breached")
        basket = state.basket(symbol)
        if basket.quantity or self._active(state, basket):
            raise TradingRejected("basket_not_flat_or_unreconciled")
        if not basket.risk_stopped:
            return state
        return _basket(state, replace(basket, risk_stopped=False, risk_stop_reason=None,
                                       sub30_count=0, rearmed=False))

    def _new_id(self, state: EngineState, basket: BasketState, reason: str, event: str) -> str:
        return digest((state.account.tenant_id, state.account.account_id, self.config.version,
                       basket.basket_id, reason, event))[:40]

    def _exit(self, state: EngineState, basket: BasketState, now: datetime,
              reason: str) -> Transition:
        intents: list[OrderIntent] = []
        events: list[DomainEvent] = []
        basket = replace(basket, exiting=True,
                         risk_stopped=basket.risk_stopped or reason == "first_fill_55pct_exit",
                         risk_stop_reason=("first_fill_55pct_exit" if reason == "first_fill_55pct_exit"
                                           else basket.risk_stop_reason))
        state = _basket(state, basket)
        active = self._active(state, basket)
        for record in active:
            if record.intent.side == Side.BUY and record.status != OrderStatus.CANCEL_REQUESTED:
                state = _order(state, replace(record, status=OrderStatus.CANCEL_REQUESTED))
                events.append(DomainEvent("cancel_order", basket.symbol, record.intent.intent_id, reason))
        if basket.quantity > 0 and not any(o.intent.side == Side.SELL for o in active):
            identifier = self._new_id(state, basket, "exit", str(sum(
                o.intent.side == Side.SELL and o.intent.basket_id == basket.basket_id for o in state.orders)))
            intent = OrderIntent(identifier, basket.basket_id, basket.symbol, Side.SELL, now,
                                 self.config.version, reason, quantity=basket.quantity)
            state = replace(state, orders=state.orders + (OrderRecord(intent),))
            intents.append(intent)
        return Transition(state, tuple(intents), tuple(events))

    def _risk_exit(self, state: EngineState, now: datetime) -> Transition:
        reasons = tuple(r for r in self.risk_reasons(state, now) if r != "daily_baseline_required")
        if reasons:
            state = replace(state, account=replace(
                state.account, halted=True,
                halt_reasons=tuple(dict.fromkeys(state.account.halt_reasons + reasons)),
            ))
        if not state.account.halted:
            return Transition(state)
        intents: list[OrderIntent] = []
        events: list[DomainEvent] = []
        for basket in state.baskets:
            if basket.quantity or self._active(state, basket):
                result = self._exit(state, basket, now, "account_risk")
                state = result.state
                intents.extend(result.intents)
                events.extend(result.events)
        return Transition(state, tuple(intents), tuple(events))

    def _protect(self, state: EngineState, symbol: str, now: datetime) -> Transition:
        basket, quote = state.basket(symbol), state.quote(symbol)
        if not basket.quantity or quote is None:
            return Transition(state)
        if basket.first_fill_price is not None and quote.bid <= basket.first_fill_price * self.config.emergency_exit_fraction:
            return self._exit(state, basket, now, "first_fill_55pct_exit")
        if basket.exiting:
            return self._exit(state, basket, now, "exit_in_progress")
        if basket.stop_price is not None and quote.bid <= basket.stop_price:
            return self._exit(state, basket, now, "trailing_stop")
        if not basket.protected and quote.bid < basket.average_price * (1 + self.config.profit_activation):
            return Transition(state)
        with localcontext() as ctx:
            ctx.prec = 36
            net_floor = (basket.principal_spent + basket.costs_spent) / (
                basket.quantity * (1 - self.config.estimated_exit_fee_rate)
                * (1 - self.config.estimated_exit_slippage_fraction))
        candidates = [net_floor]
        if basket.stop_price is not None:
            candidates.append(basket.stop_price)
        line = basket.indicators.supertrend
        if basket.indicators.bullish and line is not None and D("0") < line < quote.bid:
            candidates.append(line)
        stop = max(candidates)
        state = _basket(state, replace(basket, protected=True, stop_price=stop, rearmed=False))
        events = [DomainEvent("protection_updated", symbol, basket.basket_id, str(stop))]
        # Stop intent may become unplaceable on a rapid move: do not claim protection.
        if stop >= quote.bid:
            result = self._exit(state, state.basket(symbol), now, "protective_floor_crossed")
            return Transition(result.state, result.intents, tuple(events) + result.events)
        return Transition(state, events=tuple(events))

    @precise
    def on_quote(self, state: EngineState, quote: Quote, *, now: datetime | None = None) -> Transition:
        self._validate(state, quote.symbol)
        now = utc(now or quote.observed_at)
        age = (now - quote.observed_at).total_seconds()
        if age < 0:
            raise TradingRejected("future_quote")
        if age > self.config.quote_max_age_seconds:
            return Transition(state, events=(DomainEvent("data_rejected", quote.symbol, "", "stale_quote"),))
        old = state.quote(quote.symbol)
        if old is not None and quote.observed_at < old.observed_at:
            raise TradingRejected("out_of_order_quote")
        if old == quote:
            return Transition(state)
        state = replace(state, quotes=tuple(q for q in state.quotes if q.symbol != quote.symbol) + (quote,))
        first = self._risk_exit(state, now)
        second = self._protect(first.state, quote.symbol, now)
        return Transition(second.state, first.intents + second.intents, first.events + second.events)

    def _buy_rejection(self, state: EngineState, symbol: str, now: datetime) -> str | None:
        basket = state.basket(symbol)
        if state.account.halted:
            return "account_halted"
        if basket.risk_stopped:
            return "basket_risk_stopped"
        reasons = self.risk_reasons(state, now)
        if reasons:
            return reasons[0]
        if basket.protected:
            return "profit_protection_active"
        if basket.exiting:
            return "exit_in_progress"
        if self._active(state, basket):
            return "unresolved_order"
        for holding in state.baskets:
            if holding.quantity or holding.symbol == symbol:
                quote = state.quote(holding.symbol)
                if quote is None:
                    return "quote_required"
                age = (now - quote.observed_at).total_seconds()
                if age < 0 or age > self.config.quote_max_age_seconds:
                    return "stale_quote"
        quote = state.quote(symbol)
        if basket.first_fill_price is not None and quote.bid <= basket.first_fill_price * self.config.emergency_exit_fraction:
            return "first_fill_55pct_exit"
        if basket.costs_spent >= self.config.basket_cost_reserve:
            return "cost_reserve_exhausted"
        return None

    def _buy_rejection_for_dispatch(self, state: EngineState, record: OrderRecord,
                                    now: datetime) -> str | None:
        if record.status != OrderStatus.OPEN:
            return "order_uncertain_requires_reconciliation"
        if record.filled_quantity:
            return "partial_order_requires_reconciliation"
        without_own_reservation = replace(state, orders=tuple(
            o for o in state.orders if o.intent.intent_id != record.intent.intent_id))
        reason = self._buy_rejection(without_own_reservation, record.intent.symbol, now)
        if reason:
            return reason
        basket = state.basket(record.intent.symbol)
        if basket.principal_spent + record.intent.maximum_quote > self.config.basket_principal:
            return "basket_principal_limit"
        quote = state.quote(record.intent.symbol)
        if record.intent.maximum_price is not None and quote.ask > record.intent.maximum_price:
            return "price_above_limit"
        reserved_others = sum((max(D("0"), o.intent.maximum_quote - o.filled_principal)
                               for o in without_own_reservation.orders
                               if o.unresolved and o.intent.side == Side.BUY), D("0"))
        if state.account.cash - reserved_others < record.intent.maximum_quote + (
                self.config.basket_cost_reserve - basket.costs_spent):
            return "insufficient_cash"
        return None

    @precise
    def validate_dispatch(self, state: EngineState, intent_id: str, now: datetime) -> None:
        """Recheck immediately before execution. Does not execute or authenticate."""
        self._validate(state)
        now = utc(now)
        record = next((o for o in state.orders if o.intent.intent_id == intent_id), None)
        if record is None or not record.unresolved:
            raise TradingRejected("order_not_open")
        if record.intent.created_at > now:
            raise TradingRejected("dispatch_before_intent")
        if record.intent.side == Side.BUY:
            reason = self._buy_rejection_for_dispatch(state, record, now)
            if reason:
                raise TradingRejected(reason)
        elif record.status != OrderStatus.OPEN:
            raise TradingRejected("order_uncertain_requires_reconciliation")

    def _buy(self, state: EngineState, symbol: str, stage: int, now: datetime,
             event: str, authorization: str | None = None) -> Transition:
        reason = self._buy_rejection(state, symbol, now)
        if reason:
            return Transition(state, events=(DomainEvent("entry_blocked", symbol, "", reason),))
        basket, rules = state.basket(symbol), self.rules(symbol)
        amount = floor_step(self.config.allocations[stage - 1], rules.quote_step)
        amount = min(amount, self.config.basket_principal - basket.principal_spent)
        limit = None if stage == 1 else basket.last_regular_price * (1 - self.config.entry_drop)
        quote = state.quote(symbol)
        if limit is not None and quote.ask > limit:
            return Transition(state, events=(DomainEvent("entry_blocked", symbol, "", "price_above_limit"),))
        if amount < rules.minimum_quote or amount <= 0:
            return Transition(state, events=(DomainEvent("entry_blocked", symbol, "", "below_minimum_quote"),))
        reserved = sum((max(D("0"), o.intent.maximum_quote - o.filled_principal)
                        for o in state.orders if o.unresolved and o.intent.side == Side.BUY), D("0"))
        if state.account.cash - reserved < amount + self.config.basket_cost_reserve - basket.costs_spent:
            return Transition(state, events=(DomainEvent("entry_blocked", symbol, "", "insufficient_cash"),))
        kind = "manual_reserve" if stage == 6 else "rsi_entry"
        identifier = self._new_id(state, basket, kind, event)
        if any(o.intent.intent_id == identifier for o in state.orders):
            return Transition(state)
        intent = OrderIntent(identifier, basket.basket_id, symbol, Side.BUY, now,
                             self.config.version, kind, stage=stage, maximum_quote=amount,
                             maximum_price=limit, manual_authorization=authorization)
        return Transition(replace(state, orders=state.orders + (OrderRecord(intent),)), (intent,))

    @precise
    def on_bar(self, state: EngineState, bar: Candle, *, observed_at: datetime | None = None) -> Transition:
        self._validate(state, bar.symbol)
        now = utc(observed_at or bar.close_time)
        if now < bar.close_time:
            raise TradingRejected("unfinished_candle")
        basket = state.basket(bar.symbol)
        bar_digest = digest(bar)
        bar_id = f"{bar.symbol}:{bar.open_time.isoformat()}"
        previous_digest = next((d for key, d in state.processed_bars if key == bar_id), None)
        if previous_digest is not None:
            if previous_digest == bar_digest:
                return Transition(state)
            raise TradingRejected("out_of_order_or_revised_candle")
        if basket.last_bar_open is not None and bar.open_time <= basket.last_bar_open:
            if bar.open_time == basket.last_bar_open and bar_digest == basket.last_bar_digest:
                return Transition(state)
            raise TradingRejected("out_of_order_or_revised_candle")
        if basket.last_bar_open is not None and bar.open_time != basket.last_bar_open + timedelta(hours=4):
            return Transition(state, events=(DomainEvent("data_rejected", bar.symbol, "", "candle_gap"),))
        indicator = advance(basket.indicators, bar, self.config)
        below = indicator.rsi is not None and indicator.rsi < D("30")
        rearmed = basket.rearmed
        if basket.entries and indicator.rsi is not None and indicator.rsi > D("30"):
            rearmed = True
        basket = replace(basket, indicators=indicator,
                         sub30_count=basket.sub30_count + 1 if below else 0,
                         rearmed=rearmed, last_bar_open=bar.open_time, last_bar_digest=bar_digest)
        state = _basket(state, basket)
        state = replace(state, processed_bars=state.processed_bars + ((bar_id, bar_digest),))
        risk = self._risk_exit(state, now)
        protected = self._protect(risk.state, bar.symbol, now)
        state, basket = protected.state, protected.state.basket(bar.symbol)
        ready = False
        number = basket.completed_regular_stages + 1
        if number == 1:
            ready = basket.sub30_count >= 2
        elif number <= 5:
            ready = (below and basket.rearmed and basket.last_regular_price is not None
                     and bar.close <= basket.last_regular_price * (1 - self.config.entry_drop))
        if ready and (now - bar.close_time).total_seconds() > self.config.quote_max_age_seconds:
            purchase = Transition(state, events=(DomainEvent("entry_blocked", bar.symbol, "", "stale_signal"),))
        else:
            purchase = self._buy(state, bar.symbol, number, now, bar.close_time.isoformat()) if ready else Transition(state)
        return Transition(purchase.state, risk.intents + protected.intents + purchase.intents,
                          risk.events + protected.events + purchase.events)

    @precise
    def preview_manual(self, state: EngineState, symbol: str, now: datetime) -> ManualPreview:
        self._validate(state, symbol)
        now = utc(now)
        reason = self._buy_rejection(state, symbol, now)
        if reason:
            raise TradingRejected(reason)
        basket = state.basket(symbol)
        if basket.completed_regular_stages != 5:
            raise TradingRejected("five_completed_stages_required")
        if basket.manual_used or any(o.intent.basket_id == basket.basket_id and o.intent.stage == 6
                                     for o in state.orders):
            raise TradingRejected("manual_stage_already_used")
        limit = basket.last_regular_price * (1 - self.config.entry_drop)
        quote = state.quote(symbol)
        if quote.ask > limit:
            raise TradingRejected("price_above_limit")
        amount = floor_step(self.config.allocations[5], self.rules(symbol).quote_step)
        maximum = min(amount, self.config.basket_principal - basket.principal_spent)
        state_digest = digest(state)
        identifier = digest((state_digest, symbol, now.isoformat(), str(maximum), str(limit)))
        return ManualPreview(identifier, state_digest, basket.basket_id, symbol, maximum,
                             limit, quote.ask, now, now + timedelta(seconds=self.config.preview_lifetime_seconds),
                             self.config.version)

    @precise
    def confirm_manual(self, state: EngineState, preview: ManualPreview, now: datetime,
                       *, authorization_reference: str) -> Transition:
        """API MUST verify owner/trader, tenant binding, fresh MFA and one-use approval.

        The nonempty reference is an audit handle, not an authentication mechanism.
        """
        now = utc(now)
        if not authorization_reference or not authorization_reference.strip():
            raise TradingRejected("manual_authorization_required")
        if preview.expires_at != preview.created_at + timedelta(seconds=self.config.preview_lifetime_seconds):
            raise TradingRejected("invalid_preview")
        if now < preview.created_at or now >= preview.expires_at:
            raise TradingRejected("preview_expired")
        current = self.preview_manual(state, preview.symbol, now)
        if (preview.strategy_version != self.config.version or digest(state) != preview.state_digest
                or current.basket_id != preview.basket_id
                or current.maximum_quote != preview.maximum_quote
                or current.maximum_price != preview.maximum_price
                or current.quoted_ask != preview.quoted_ask):
            raise TradingRejected("preview_changed")
        if preview.preview_id != digest((preview.state_digest, preview.symbol, preview.created_at.isoformat(),
                                        str(preview.maximum_quote), str(preview.maximum_price))):
            raise TradingRejected("invalid_preview")
        return self._buy(state, preview.symbol, 6, now, preview.preview_id, authorization_reference)

    def mark_order_unknown(self, state: EngineState, intent_id: str) -> EngineState:
        self._validate(state)
        record = next(o for o in state.orders if o.intent.intent_id == intent_id)
        if not record.unresolved:
            raise TradingRejected("order_already_resolved")
        return _order(state, replace(record, status=OrderStatus.UNKNOWN))

    def reconcile_cancelled(self, state: EngineState, intent_id: str) -> Transition:
        """Only call after authoritative cancellation/fill-history reconciliation."""
        self._validate(state)
        record = next(o for o in state.orders if o.intent.intent_id == intent_id)
        if not record.unresolved:
            return Transition(state)
        state = _order(state, replace(record, status=OrderStatus.CANCELLED))
        basket = state.basket(record.intent.symbol)
        if record.intent.side == Side.BUY and record.filled_quantity > 0:
            basket = replace(basket, entries=tuple(
                replace(e, complete=True) if e.number == record.intent.stage else e for e in basket.entries))
            state = _basket(state, basket)
        state = self._finalize_closed(state, basket.symbol)
        return self._notice(state, basket.symbol)

    def _finalize_closed(self, state: EngineState, symbol: str) -> EngineState:
        basket = state.basket(symbol)
        if basket.quantity != 0 or not basket.exiting or self._active(state, basket):
            return state
        if basket.started_at is not None:
            timestamps = tuple(o.last_fill_at for o in state.orders
                               if o.intent.basket_id == basket.basket_id and o.last_fill_at is not None)
            closed = ClosedBasket(basket.basket_id, basket.symbol, basket.started_at, max(timestamps),
                                  basket.exit_proceeds - basket.principal_spent - basket.costs_spent,
                                  basket.manual_used)
            state = replace(state, closed_baskets=state.closed_baskets + (closed,))
        return _basket(state, BasketState(
            symbol=basket.symbol, cycle=basket.cycle + 1,
            risk_stopped=basket.risk_stopped, risk_stop_reason=basket.risk_stop_reason,
            last_bar_open=basket.last_bar_open, last_bar_digest=basket.last_bar_digest,
            indicators=basket.indicators,
        ))

    def _notice(self, state: EngineState, symbol: str) -> Transition:
        basket = state.basket(symbol)
        if basket.completed_regular_stages == 5 and not basket.reserve_notified:
            state = _basket(state, replace(basket, reserve_notified=True))
            return Transition(state, events=(DomainEvent("manual_reserve_available", symbol, basket.basket_id),))
        return Transition(state)

    @precise
    def apply_fill(self, state: EngineState, fill: Fill) -> Transition:
        self._validate(state)
        fingerprint = digest(fill)
        previous = next((d for identifier, d in state.processed_fills if identifier == fill.fill_id), None)
        if previous is not None:
            if previous != fingerprint:
                raise TradingRejected("conflicting_duplicate_fill")
            return Transition(state)
        record = next((o for o in state.orders if o.intent.intent_id == fill.intent_id), None)
        if record is None:
            raise TradingRejected("unknown_fill_intent_requires_reconciliation")
        intent, basket = record.intent, state.basket(record.intent.symbol)
        if fill.occurred_at < intent.created_at:
            raise TradingRejected("fill_before_intent")
        if record.last_fill_at is not None and fill.occurred_at < record.last_fill_at:
            raise TradingRejected("out_of_order_fill_requires_reconciliation")
        if basket.basket_id != intent.basket_id:
            raise TradingRejected("late_fill_for_closed_basket_requires_reconciliation")
        if fill.final and record.status == OrderStatus.COMPLETE:
            raise TradingRejected("additional_fill_after_final")
        principal = fill.quantity * fill.price
        cumulative = record.filled_principal + principal
        violations: list[str] = []
        if intent.side == Side.BUY:
            if cumulative > intent.maximum_quote:
                violations.append("fill_exceeds_quote_budget")
            if intent.maximum_price is not None and fill.price > intent.maximum_price:
                violations.append("fill_exceeds_price_limit")
            if record.status == OrderStatus.CANCELLED or basket.exiting or basket.protected:
                violations.append("late_buy_after_cancel_or_protection")
            entry = next((e for e in basket.entries if e.number == intent.stage), EntryStage(intent.stage))
            entry = replace(entry, principal=entry.principal + principal,
                            quantity=entry.quantity + fill.quantity, fees=entry.fees + fill.fee,
                            complete=fill.final)
            entries = tuple(e for e in basket.entries if e.number != entry.number) + (entry,)
            entries = tuple(sorted(entries, key=lambda e: e.number))
            basket = replace(
                basket, entries=entries, quantity=basket.quantity + fill.quantity,
                principal_spent=basket.principal_spent + principal,
                costs_spent=basket.costs_spent + fill.fee, rearmed=False, sub30_count=0,
                manual_used=basket.manual_used or intent.stage == 6,
                started_at=basket.started_at or fill.occurred_at,
            )
            cash = state.account.cash - principal - fill.fee
        else:
            if fill.quantity > basket.quantity or record.filled_quantity + fill.quantity > intent.quantity:
                raise TradingRejected("sell_overfill_requires_reconciliation")
            basket = replace(basket, quantity=basket.quantity - fill.quantity,
                             costs_spent=basket.costs_spent + fill.fee,
                             exit_proceeds=basket.exit_proceeds + principal)
            cash = state.account.cash + principal - fill.fee
        if basket.costs_spent > self.config.basket_cost_reserve:
            violations.append("fill_exceeds_cost_reserve")
        if basket.principal_spent > self.config.basket_principal:
            violations.append("fill_exceeds_basket_principal")
        state = _basket(state, basket)
        state = replace(state, account=replace(state.account, cash=cash),
                        processed_fills=state.processed_fills + ((fill.fill_id, fingerprint),))
        status = OrderStatus.COMPLETE if fill.final else record.status
        state = _order(state, replace(record, status=status,
                                     filled_quantity=record.filled_quantity + fill.quantity,
                                     filled_principal=cumulative, last_fill_at=fill.occurred_at))
        state = self._finalize_closed(state, intent.symbol)
        if violations:
            state = replace(state, account=replace(
                state.account, halted=True,
                halt_reasons=tuple(dict.fromkeys(state.account.halt_reasons + tuple(violations)))))
        notice = self._notice(state, intent.symbol)
        risk = self._risk_exit(notice.state, fill.occurred_at)
        protection = self._protect(risk.state, intent.symbol, fill.occurred_at)
        return Transition(protection.state, risk.intents + protection.intents,
                          notice.events + risk.events + protection.events)
