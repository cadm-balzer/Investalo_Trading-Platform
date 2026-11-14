"""Read-only selected-asset view of an acknowledged own Paper state."""
from datetime import timedelta
from decimal import Decimal
import re

from .futures_ledger import timestamp
from .futures_paper import FuturesPaperState
from .models import floor_step, precise


@precise
def asset_snapshot(state, *, tenant_id, account_id, now, account_ready=True):
    if type(state) is not FuturesPaperState or type(account_ready) is not bool:
        raise ValueError("own acknowledged Paper state required")
    now = timestamp(now)
    plan = state.config.profile.plan
    signal, ledger = state.signal, state.signal.economic.ledger
    if (plan.tenant_id != tenant_id or plan.account_id != account_id
            or state.observed_at > now or signal.as_of > now):
        raise ValueError("own current Paper context required")
    hour = now.replace(minute=0, second=0, microsecond=0)
    indicator_at = signal.last_hour.close_time if signal.last_hour else None
    fresh = (state.warmed and indicator_at == hour
             and timedelta(0) <= now - signal.trade_at <= timedelta(seconds=30))
    stopped = {b.symbol for b in signal.economic.stopped}
    occupied = sum(bool(b.quantity) or b.symbol in stopped for b in ledger.baskets)
    assets = []
    for i, (s, basket) in enumerate(zip(signal.signals, ledger.baskets, strict=True)):
        if not re.fullmatch(r"BITGET:[A-Z0-9]{2,16}USDT", s.symbol):
            raise ValueError("own Classic Futures asset identity required")
        stages = tuple(r for r in signal.economic.stages
                       if (r.symbol, r.cycle) == (s.symbol, s.cycle)) if basket.quantity else ()
        if basket.quantity and (basket.cycle != s.cycle or not stages
                                or tuple(r.stage for r in stages) != tuple(range(1, len(stages) + 1))):
            raise ValueError("open own basket lacks regular fill evidence")
        ceiling = (floor_step(stages[-1].price * Decimal(".95"), plan.grid_rules[i].price_tick)
                   if stages else None)
        rsi = s.entry_indicator.rsi
        if rsi is not None and not Decimal(0) <= rsi <= Decimal(100):
            raise ValueError("bounded RSI required")
        reasons = []
        if not account_ready:
            reasons.append("account_unavailable")
        if s.symbol in stopped:
            reasons.append("liquidation_stop")
        if ledger.halted or signal.economic.liquidation_required:
            reasons.append("account_halt")
        if s.protected or s.exit_reasons:
            reasons.append("exit_protection")
        if not fresh:
            reasons.append("data_stale")
        if not basket.quantity and occupied >= plan.simultaneous_limit:
            reasons.append("capacity_full")
        if reasons:
            status = "blocked"
        elif len(stages) >= 5:
            status = "manual_only"
        elif rsi is None:
            status = "warming"
        elif (signal.last_entry_at is None
              or not timedelta(0) <= now - signal.last_entry_at <= timedelta(seconds=30)):
            status = "waiting_signal_check"
        elif stages and not s.rearmed:
            status = "waiting_rearm"
        elif rsi >= 30:
            status = "waiting_rsi"
        elif not stages and s.below_count < 2:
            status = "waiting_confirmation"
        elif ceiling is not None and signal.trade_prices[i].price > ceiling:
            # Bid above the ceiling proves Ask cannot fit. Bid below it does
            # not prove the executable Ask/slippage/margin checks will pass.
            status = "waiting_price"
        else:
            status = "signal_confirmed"
        assets.append({
            "symbol": s.symbol.removeprefix("BITGET:"), "rsi": str(rsi) if rsi is not None else None,
            "rsi_confirmations": min(s.below_count, 2), "rearmed": s.rearmed,
            "reference_bid": str(signal.trade_prices[i].price),
            "position": {
                "quantity": str(basket.quantity), "average_entry": str(basket.average_entry),
                "leverage": str(basket.broker_leverage), "regular_entries": len(stages),
                "last_entry_price": str(stages[-1].price) if stages else None,
            } if basket.quantity else None,
            "next_buy": {
                "stage": len(stages) + 1 if stages else 1,
                "maximum_fill_price": str(ceiling) if ceiling is not None else None,
                "status": status, "reasons": reasons,
            },
        })
    return {
        "revision": state.revision, "observed_at": signal.trade_at.isoformat(),
        "indicator_at": indicator_at.isoformat() if indicator_at else None,
        "next_signal_check": (hour + timedelta(hours=1)).isoformat(),
        "data_fresh": fresh, "rsi_period": 14, "timeframe": "H1", "assets": assets,
    }
