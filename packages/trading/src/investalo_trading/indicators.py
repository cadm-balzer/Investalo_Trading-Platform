"""Incremental Wilder indicators; input is one completed candle at a time."""

from dataclasses import replace
from decimal import Decimal, localcontext

from .models import Candle, IndicatorState, StrategyConfig, precise

D = Decimal


@precise
def advance(state: IndicatorState, bar: Candle, config: StrategyConfig) -> IndicatorState:
    with localcontext() as ctx:
        ctx.prec = 36
        gain_sum, loss_sum = state.gain_sum, state.loss_sum
        gain, loss = state.average_gain, state.average_loss
        changes = state.changes
        if state.previous_close is not None:
            change = bar.close - state.previous_close
            up, down = max(change, D("0")), max(-change, D("0"))
            changes += 1
            if gain is None:
                gain_sum += up
                loss_sum += down
                if changes == config.rsi_period:
                    gain = gain_sum / config.rsi_period
                    loss = loss_sum / config.rsi_period
            else:
                gain = (gain * (config.rsi_period - 1) + up) / config.rsi_period
                loss = (loss * (config.rsi_period - 1) + down) / config.rsi_period
        rsi = None
        if gain is not None and loss is not None:
            # Equivalent form avoids subtractive rounding turning exact RSI30
            # into 29.999..., which would invent a confirmed strategy trigger.
            rsi = D("50") if gain == loss == 0 else D("100") * gain / (gain + loss)
        tr = bar.high - bar.low
        if state.previous_close is not None:
            tr = max(tr, abs(bar.high - state.previous_close), abs(bar.low - state.previous_close))
        count = state.true_ranges + 1
        tr_sum, atr = state.true_range_sum, state.atr
        if atr is None:
            tr_sum += tr
            if count == config.atr_period:
                atr = tr_sum / config.atr_period
        else:
            atr = (atr * (config.atr_period - 1) + tr) / config.atr_period
        upper, lower, bullish, line = state.upper_band, state.lower_band, state.bullish, None
        if atr is not None:
            midpoint = (bar.high + bar.low) / 2
            raw_upper = midpoint + config.supertrend_factor * atr
            raw_lower = midpoint - config.supertrend_factor * atr
            if upper is None:
                upper, lower, bullish = raw_upper, raw_lower, False
            else:
                upper = raw_upper if raw_upper < upper or state.previous_close > upper else upper
                lower = raw_lower if raw_lower > lower or state.previous_close < lower else lower
                bullish = not (bar.close < lower) if state.bullish else bar.close > upper
            line = lower if bullish else upper
        return replace(
            state, previous_close=bar.close, changes=changes,
            gain_sum=gain_sum, loss_sum=loss_sum, average_gain=gain, average_loss=loss,
            true_ranges=count, true_range_sum=tr_sum, atr=atr,
            upper_band=upper, lower_band=lower, bullish=bullish, rsi=rsi, supertrend=line,
        )
