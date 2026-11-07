"""Immutable domain records. Prices, quantities and money are Decimal, times UTC."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_EVEN, localcontext
from functools import wraps
from enum import StrEnum
from typing import Callable, ParamSpec, TypeVar

D = Decimal
VERSION = "crypto-basket/1.0.0"
P = ParamSpec("P")
R = TypeVar("R")


def precise(function: Callable[P, R]) -> Callable[P, R]:
    """Isolate arithmetic from a caller's mutable global Decimal context."""
    @wraps(function)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
        with localcontext() as ctx:
            ctx.prec = 36
            ctx.rounding = ROUND_HALF_EVEN
            return function(*args, **kwargs)
    return wrapped


def utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("a timezone-aware timestamp is required")
    return value.astimezone(timezone.utc)


def positive(value: Decimal, name: str, *, zero: bool = False) -> None:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise ValueError(f"{name} must be a finite Decimal")
    if value < 0 or (not zero and value == 0):
        raise ValueError(f"{name} must be {'nonnegative' if zero else 'positive'}")


def floor_step(value: Decimal, step: Decimal) -> Decimal:
    with localcontext() as ctx:
        ctx.prec = 36
        ctx.rounding = ROUND_HALF_EVEN
        return (value / step).to_integral_value(rounding=ROUND_DOWN) * step


@dataclass(frozen=True)
class StrategyConfig:
    version: str = VERSION
    symbols: tuple[str, ...] = ("BTCUSDT", "ETHUSDT")
    initial_equity: Decimal = D("10000")
    basket_principal: Decimal = D("500")
    basket_cost_reserve: Decimal = D("5")
    daily_loss_fraction: Decimal = D("0.06")
    initial_loss_fraction: Decimal = D("0.08")
    entry_drop: Decimal = D("0.05")
    profit_activation: Decimal = D("0.05")
    emergency_exit_fraction: Decimal = D("0.45")
    rsi_period: int = 14
    atr_period: int = 10
    supertrend_factor: Decimal = D("3")
    estimated_exit_fee_rate: Decimal = D("0.001")
    estimated_exit_slippage_fraction: Decimal = D("0.001")
    quote_max_age_seconds: int = 30
    preview_lifetime_seconds: int = 30

    def __post_init__(self) -> None:
        if self.version != VERSION:
            raise ValueError("unsupported strategy version")
        if not self.symbols or len(set(self.symbols)) != len(self.symbols):
            raise ValueError("symbols must be unique")
        if any(s not in ("BTCUSDT", "ETHUSDT") for s in self.symbols):
            raise ValueError("this version supports BTC/ETH USDT spot only")
        for name in ("initial_equity", "basket_principal", "basket_cost_reserve",
                     "daily_loss_fraction", "initial_loss_fraction", "entry_drop",
                     "profit_activation", "emergency_exit_fraction", "supertrend_factor"):
            positive(getattr(self, name), name)
        for name in ("daily_loss_fraction", "initial_loss_fraction", "entry_drop",
                     "profit_activation", "emergency_exit_fraction"):
            if getattr(self, name) >= 1:
                raise ValueError(f"{name} must be below one")
        if self.rsi_period < 2 or self.atr_period < 2:
            raise ValueError("indicator periods must be at least two")
        for name in ("estimated_exit_fee_rate", "estimated_exit_slippage_fraction"):
            positive(getattr(self, name), name, zero=True)
            if getattr(self, name) >= 1:
                raise ValueError("exit cost fractions must be below one")
        if self.quote_max_age_seconds <= 0 or self.preview_lifetime_seconds <= 0:
            raise ValueError("age limits must be positive")
        if len(self.symbols) * (self.basket_principal + self.basket_cost_reserve) > self.initial_equity:
            raise ValueError("basket budgets exceed initial capital")

    @property
    def allocations(self) -> tuple[Decimal, ...]:
        with localcontext() as ctx:
            ctx.prec = 36
            ctx.rounding = ROUND_HALF_EVEN
            weights = tuple(D("1.25") ** i for i in range(6))
            return tuple(self.basket_principal * w / sum(weights) for w in weights)


@dataclass(frozen=True)
class InstrumentRules:
    """Simulator precision, not a claim about a venue's live instrument rules."""

    symbol: str
    quantity_step: Decimal = D("0.00000001")
    quote_step: Decimal = D("0.00000001")
    minimum_quote: Decimal = D("0")

    def __post_init__(self) -> None:
        positive(self.quantity_step, "quantity_step")
        positive(self.quote_step, "quote_step")
        positive(self.minimum_quote, "minimum_quote", zero=True)


@dataclass(frozen=True)
class Candle:
    symbol: str
    open_time: datetime
    close_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal

    def __post_init__(self) -> None:
        opened, closed = utc(self.open_time), utc(self.close_time)
        if closed - opened != timedelta(hours=4):
            raise ValueError("only H4 candles are supported")
        if opened.hour % 4 or opened.minute or opened.second or opened.microsecond:
            raise ValueError("H4 candles must align to UTC boundaries")
        object.__setattr__(self, "open_time", opened)
        object.__setattr__(self, "close_time", closed)
        for name in ("open", "high", "low", "close"):
            positive(getattr(self, name), name)
        if self.high < max(self.open, self.close, self.low) or self.low > min(self.open, self.close):
            raise ValueError("inconsistent OHLC")


@dataclass(frozen=True)
class Quote:
    symbol: str
    observed_at: datetime
    bid: Decimal
    ask: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(self, "observed_at", utc(self.observed_at))
        positive(self.bid, "bid")
        positive(self.ask, "ask")
        if self.ask < self.bid:
            raise ValueError("crossed quote")


@dataclass(frozen=True)
class IndicatorState:
    previous_close: Decimal | None = None
    changes: int = 0
    gain_sum: Decimal = D("0")
    loss_sum: Decimal = D("0")
    average_gain: Decimal | None = None
    average_loss: Decimal | None = None
    true_ranges: int = 0
    true_range_sum: Decimal = D("0")
    atr: Decimal | None = None
    upper_band: Decimal | None = None
    lower_band: Decimal | None = None
    bullish: bool = False
    rsi: Decimal | None = None
    supertrend: Decimal | None = None


@dataclass(frozen=True)
class EntryStage:
    number: int
    principal: Decimal = D("0")
    quantity: Decimal = D("0")
    fees: Decimal = D("0")
    complete: bool = False

    @property
    def vwap(self) -> Decimal:
        if self.quantity <= 0:
            raise ValueError("a stage without fills has no VWAP")
        with localcontext() as ctx:
            ctx.prec = 36
            ctx.rounding = ROUND_HALF_EVEN
            return self.principal / self.quantity


class Side(StrEnum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(StrEnum):
    OPEN = "open"
    UNKNOWN = "unknown"
    CANCEL_REQUESTED = "cancel_requested"
    COMPLETE = "complete"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class OrderIntent:
    intent_id: str
    basket_id: str
    symbol: str
    side: Side
    created_at: datetime
    strategy_version: str
    reason: str
    stage: int | None = None
    maximum_quote: Decimal = D("0")
    maximum_price: Decimal | None = None
    quantity: Decimal = D("0")
    manual_authorization: str | None = None


@dataclass(frozen=True)
class OrderRecord:
    intent: OrderIntent
    status: OrderStatus = OrderStatus.OPEN
    filled_quantity: Decimal = D("0")
    filled_principal: Decimal = D("0")
    last_fill_at: datetime | None = None

    @property
    def unresolved(self) -> bool:
        return self.status in (OrderStatus.OPEN, OrderStatus.UNKNOWN, OrderStatus.CANCEL_REQUESTED)


@dataclass(frozen=True)
class Fill:
    """Confirmed execution. fee is denominated in quote currency (USDT)."""

    fill_id: str
    intent_id: str
    occurred_at: datetime
    quantity: Decimal
    price: Decimal
    fee: Decimal = D("0")
    final: bool = True

    def __post_init__(self) -> None:
        if not self.fill_id or not self.intent_id:
            raise ValueError("fill and intent IDs are required")
        object.__setattr__(self, "occurred_at", utc(self.occurred_at))
        positive(self.quantity, "quantity")
        positive(self.price, "price")
        positive(self.fee, "fee", zero=True)


@dataclass(frozen=True)
class BasketState:
    symbol: str
    cycle: int = 0
    entries: tuple[EntryStage, ...] = ()
    quantity: Decimal = D("0")
    principal_spent: Decimal = D("0")
    costs_spent: Decimal = D("0")
    exit_proceeds: Decimal = D("0")
    rearmed: bool = False
    sub30_count: int = 0
    protected: bool = False
    stop_price: Decimal | None = None
    exiting: bool = False
    risk_stopped: bool = False
    risk_stop_reason: str | None = None
    manual_used: bool = False
    reserve_notified: bool = False
    started_at: datetime | None = None
    last_bar_open: datetime | None = None
    last_bar_digest: str | None = None
    indicators: IndicatorState = field(default_factory=IndicatorState)

    @property
    def basket_id(self) -> str:
        return f"{self.symbol}:{self.cycle}"

    @property
    def completed_regular_stages(self) -> int:
        return sum(e.complete and e.number <= 5 for e in self.entries)

    @property
    def average_price(self) -> Decimal | None:
        quantity = sum((e.quantity for e in self.entries), D("0"))
        if quantity == 0:
            return None
        with localcontext() as ctx:
            ctx.prec = 36
            ctx.rounding = ROUND_HALF_EVEN
            return sum((e.principal for e in self.entries), D("0")) / quantity

    @property
    def first_fill_price(self) -> Decimal | None:
        return self.entries[0].vwap if self.entries else None

    @property
    def last_regular_price(self) -> Decimal | None:
        entries = tuple(e for e in self.entries if e.number <= 5 and e.quantity > 0)
        return entries[-1].vwap if entries else None


@dataclass(frozen=True)
class AccountState:
    tenant_id: str
    account_id: str
    initial_equity: Decimal
    cash: Decimal
    trading_day: date
    day_start_equity: Decimal
    halted: bool = False
    halt_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class ClosedBasket:
    basket_id: str
    symbol: str
    started_at: datetime
    closed_at: datetime
    net_pnl: Decimal
    manual: bool


@dataclass(frozen=True)
class EngineState:
    version: str
    account: AccountState
    baskets: tuple[BasketState, ...]
    configuration_digest: str = ""
    quotes: tuple[Quote, ...] = ()
    orders: tuple[OrderRecord, ...] = ()
    processed_fills: tuple[tuple[str, str], ...] = ()
    processed_bars: tuple[tuple[str, str], ...] = ()
    closed_baskets: tuple[ClosedBasket, ...] = ()

    def basket(self, symbol: str) -> BasketState:
        return next(b for b in self.baskets if b.symbol == symbol)

    def quote(self, symbol: str) -> Quote | None:
        return next((q for q in self.quotes if q.symbol == symbol), None)

    @property
    @precise
    def equity(self) -> Decimal:
        total = self.account.cash
        for basket in self.baskets:
            if basket.quantity:
                quote = self.quote(basket.symbol)
                if quote is None:
                    raise ValueError("position valuation requires a quote")
                total += basket.quantity * quote.bid
        return total


@dataclass(frozen=True)
class DomainEvent:
    kind: str
    symbol: str
    reference: str
    reason: str = ""


@dataclass(frozen=True)
class Transition:
    state: EngineState
    intents: tuple[OrderIntent, ...] = ()
    events: tuple[DomainEvent, ...] = ()


@dataclass(frozen=True)
class ManualPreview:
    preview_id: str
    state_digest: str
    basket_id: str
    symbol: str
    maximum_quote: Decimal
    maximum_price: Decimal
    quoted_ask: Decimal
    created_at: datetime
    expires_at: datetime
    strategy_version: str


class TradingRejected(ValueError):
    """A fail-closed domain rejection, suitable for a structured API response."""
