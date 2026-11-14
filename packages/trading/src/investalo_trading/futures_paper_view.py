"""Read-only selected-asset view of an acknowledged own Paper state."""
from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta
from decimal import Decimal
import re

from .allocation import identifier, revision
from .futures_ledger import number, timestamp
from .futures_paper import FuturesPaperState
from .models import floor_step, precise


@dataclass(frozen=True)
class FuturesAssetValues:
    symbol: str
    rsi: Decimal | None
    confirmations: int
    rearmed: bool
    bid: Decimal
    quantity: Decimal
    average_entry: Decimal
    leverage: Decimal
    regular_entries: int
    last_entry_price: Decimal | None
    maximum_fill_price: Decimal | None
    stopped: bool
    protected: bool

    @precise
    def __post_init__(self):
        if (not isinstance(self.symbol, str) or not re.fullmatch(r"BITGET:[A-Z0-9]{2,16}USDT", self.symbol)
                or type(self.confirmations) is not int or not 0 <= self.confirmations <= 2
                or type(self.regular_entries) is not int or not 0 <= self.regular_entries <= 5
                or any(type(v) is not bool for v in (self.rearmed, self.stopped, self.protected))):
            raise ValueError("bounded own asset values required")
        for v in (self.bid, self.quantity, self.average_entry, self.leverage):
            number(v, nonnegative=True)
        number(self.bid, positive=True)
        if self.rsi is not None:
            number(self.rsi, nonnegative=True)
            if self.rsi > 100:
                raise ValueError("bounded RSI required")
        if self.leverage != 2:
            raise ValueError("fixed 2x own Paper view required")
        if self.quantity:
            if not self.regular_entries or self.average_entry <= 0:
                raise ValueError("actual open stage and average entry required")
            number(self.last_entry_price, positive=True)
            number(self.maximum_fill_price, nonnegative=True)
            if self.maximum_fill_price > self.last_entry_price * Decimal(".95"):
                raise ValueError("own last-fill ceiling required")
        elif self.regular_entries or self.last_entry_price is not None or self.maximum_fill_price is not None:
            raise ValueError("flat asset cannot advertise actual entries")


@dataclass(frozen=True)
class FuturesAssetState:
    """Compact read model; cannot restore or execute a trading state."""
    tenant_id: str
    account_id: str
    revision: int
    known_at: datetime
    trade_at: datetime
    indicator_at: datetime | None
    entry_at: datetime | None
    warmed: bool
    simultaneous_limit: int
    halted: bool
    assets: tuple[FuturesAssetValues, ...]

    def __post_init__(self):
        identifier(self.tenant_id)
        identifier(self.account_id)
        revision(self.revision)
        timestamp(self.known_at)
        timestamp(self.trade_at)
        for at in (self.indicator_at, self.entry_at):
            if at is not None and (timestamp(at) > self.known_at or at.minute or at.second or at.microsecond):
                raise ValueError("closed H1 view clock required")
        if (self.trade_at > self.known_at
                or any(type(v) is not bool for v in (self.warmed, self.halted))
                or type(self.simultaneous_limit) is not int or not 3 <= self.simultaneous_limit <= 7
                or type(self.assets) is not tuple or not 3 <= len(self.assets) <= 7
                or any(type(v) is not FuturesAssetValues for v in self.assets)):
            raise ValueError("own bounded Paper read model required")
        symbols = tuple(v.symbol for v in self.assets)
        if symbols != tuple(sorted(set(symbols))):
            raise ValueError("canonical own asset pool required")


@precise
def asset_state(state):
    if type(state) is not FuturesPaperState:
        raise ValueError("own acknowledged Paper state required")
    plan = state.config.profile.plan
    signal, ledger = state.signal, state.signal.economic.ledger
    stopped = {b.symbol for b in signal.economic.stopped}
    assets = []
    for i, (s, basket) in enumerate(zip(signal.signals, ledger.baskets, strict=True)):
        stages = tuple(r for r in signal.economic.stages
                       if (r.symbol, r.cycle) == (s.symbol, s.cycle)) if basket.quantity else ()
        if basket.quantity and (basket.cycle != s.cycle or not stages
                                or tuple(r.stage for r in stages) != tuple(range(1, len(stages) + 1))):
            raise ValueError("open own basket lacks regular fill evidence")
        ceiling = (floor_step(stages[-1].price * Decimal(".95"), plan.grid_rules[i].price_tick)
                   if stages else None)
        assets.append(FuturesAssetValues(
            s.symbol, s.entry_indicator.rsi, min(s.below_count, 2), s.rearmed,
            signal.trade_prices[i].price, basket.quantity, basket.average_entry, basket.broker_leverage,
            len(stages), stages[-1].price if stages else None, ceiling,
            s.symbol in stopped, bool(s.protected or s.exit_reasons)))
    return FuturesAssetState(
        plan.tenant_id, plan.account_id, state.revision, state.observed_at, signal.trade_at,
        signal.last_hour.close_time if signal.last_hour else None, signal.last_entry_at,
        state.warmed, plan.simultaneous_limit, bool(ledger.halted or signal.economic.liquidation_required),
        tuple(assets))


@precise
def asset_snapshot(state, *, tenant_id, account_id, now, account_ready=True):
    state = asset_state(state) if type(state) is FuturesPaperState else state
    if type(state) is not FuturesAssetState or type(account_ready) is not bool:
        raise ValueError("own acknowledged Paper read model required")
    now = timestamp(now)
    if state.tenant_id != tenant_id or state.account_id != account_id or state.known_at > now:
        raise ValueError("own current Paper context required")
    hour = now.replace(minute=0, second=0, microsecond=0)
    fresh = (state.warmed and state.indicator_at == hour
             and timedelta(0) <= now - state.trade_at <= timedelta(seconds=30))
    occupied = sum(bool(a.quantity) or a.stopped for a in state.assets)
    assets = []
    for a in state.assets:
        reasons = []
        if not account_ready:
            reasons.append("account_unavailable")
        if a.stopped:
            reasons.append("liquidation_stop")
        if state.halted:
            reasons.append("account_halt")
        if a.protected:
            reasons.append("exit_protection")
        if not fresh:
            reasons.append("data_stale")
        if not a.quantity and occupied >= state.simultaneous_limit:
            reasons.append("capacity_full")
        if reasons:
            status = "blocked"
        elif a.regular_entries >= 5:
            status = "manual_only"
        elif a.rsi is None:
            status = "warming"
        elif (state.entry_at is None
              or not timedelta(0) <= now - state.entry_at <= timedelta(seconds=30)):
            status = "waiting_signal_check"
        elif a.regular_entries and not a.rearmed:
            status = "waiting_rearm"
        elif a.rsi >= 30:
            status = "waiting_rsi"
        elif not a.regular_entries and a.confirmations < 2:
            status = "waiting_confirmation"
        elif a.maximum_fill_price is not None and a.bid > a.maximum_fill_price:
            # Bid above the ceiling proves Ask cannot fit. Bid below it does
            # not prove the executable Ask/slippage/margin checks will pass.
            status = "waiting_price"
        else:
            status = "signal_confirmed"
        assets.append({
            "symbol": a.symbol.removeprefix("BITGET:"), "rsi": str(a.rsi) if a.rsi is not None else None,
            "rsi_confirmations": a.confirmations, "rearmed": a.rearmed,
            "reference_bid": str(a.bid),
            "position": {
                "quantity": str(a.quantity), "average_entry": str(a.average_entry),
                "leverage": str(a.leverage), "regular_entries": a.regular_entries,
                "last_entry_price": str(a.last_entry_price),
            } if a.quantity else None,
            "next_buy": {
                "stage": a.regular_entries + 1,
                "maximum_fill_price": str(a.maximum_fill_price) if a.maximum_fill_price is not None else None,
                "status": status, "reasons": reasons,
            },
        })
    return {
        "revision": state.revision, "observed_at": state.trade_at.isoformat(),
        "indicator_at": state.indicator_at.isoformat() if state.indicator_at else None,
        "next_signal_check": (hour + timedelta(hours=1)).isoformat(),
        "data_fresh": fresh, "rsi_period": 14, "timeframe": "H1", "assets": assets,
    }
