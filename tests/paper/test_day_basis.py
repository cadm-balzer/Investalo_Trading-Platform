from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json

import pytest

from investalo_trading import Candle, IndicatorState, PaperRunner, Quote, TradingRejected

D = Decimal
MIDNIGHT = datetime(2026, 1, 2, tzinfo=timezone.utc)


def bars(at=MIDNIGHT):
    return tuple(Candle(symbol, at-timedelta(hours=4), at, D(p), D(p), D(p), D(p))
                 for symbol, p in (("BTCUSDT", "100"), ("ETHUSDT", "200")))


def state():
    runner = PaperRunner("tenant", "account")
    cp = runner.start(MIDNIGHT-timedelta(seconds=1))
    baskets = tuple(replace(b, quantity=D(q)) for b, q in zip(cp.state.baskets, ("1", "2")))
    return runner, replace(cp, state=replace(cp.state, baskets=baskets,
                         account=replace(cp.state.account, cash=D("9500"))))


def test_midnight_basis_uses_prior_cash_inventory_and_only_closes():
    runner, old = state()
    result = runner.day(old, bars(), now=MIDNIGHT+timedelta(seconds=7))
    current = result.checkpoint.state
    assert current.account.day_start_equity == D("10000")
    assert current.account.trading_day == MIDNIGHT.date()
    assert replace(current.account, trading_day=old.state.account.trading_day,
                   day_start_equity=old.state.account.day_start_equity) == old.state.account
    assert current.baskets == old.state.baskets  # includes RSI/rearm/protection
    assert current.quotes == old.state.quotes == ()
    assert current.orders == old.state.orders == ()
    assert result.entry.input_kind == "day" and not result.entry.fills
    evidence = json.loads(result.entry.events[0].reason)
    assert evidence["policy"] == "paper-h4-close/1"
    assert evidence["cash"] == "9500" and evidence["quantities"] == ["1", "2"]
    assert [b["close"] for b in evidence["bars"]] == ["100", "200"]


def test_restart_same_day_never_revalues_or_emits_another_entry():
    runner, old = state()
    updated = runner.day(old, bars(), now=MIDNIGHT+timedelta(seconds=7)).checkpoint
    restored = runner.restore(runner.dump(updated))
    revised = tuple(replace(b, close=D("150"), high=D("200"), low=D("100")) for b in bars())
    duplicate = runner.day(restored, revised, now=MIDNIGHT+timedelta(hours=1))
    assert duplicate.checkpoint == updated and duplicate.entry is None


@pytest.mark.parametrize("values", [bars()[:1], bars()[::-1], bars(MIDNIGHT+timedelta(hours=4))])
def test_missing_wrong_asset_or_non_midnight_bars_reject(values):
    runner, old = state()
    with pytest.raises(TradingRejected, match="midnight_bars"):
        runner.day(old, values, now=MIDNIGHT+timedelta(seconds=7))


def test_post_midnight_inventory_cannot_be_retroactively_used():
    runner, old = state()
    # Includes exact midnight, where prior execution ordering is unproven.
    for at in (MIDNIGHT, MIDNIGHT+timedelta(seconds=1)):
        with pytest.raises(TradingRejected, match="inventory_unavailable"):
            runner.day(replace(old, observed_at=at), bars(), now=MIDNIGHT+timedelta(seconds=7))


def test_latched_risk_halt_and_all_protection_flags_survive_day_roll():
    runner, old = state()
    old = replace(old, state=replace(old.state,
        account=replace(old.state.account, halted=True, halt_reasons=("daily_loss_limit",)),
        baskets=tuple(replace(b, protected=True, risk_stopped=True) for b in old.state.baskets)))
    current = runner.day(old, bars(), now=MIDNIGHT+timedelta(seconds=7)).checkpoint.state
    assert current.account.halted and current.account.halt_reasons == ("daily_loss_limit",)
    assert current.baskets == old.state.baskets
    assert runner.simulator.engine._buy_rejection(current, "BTCUSDT", MIDNIGHT) == "account_halted"


def test_offline_days_use_current_midnight_with_unchanged_persisted_inventory():
    runner, old = state()
    at = MIDNIGHT+timedelta(days=3)
    current = runner.day(old, bars(at), now=at+timedelta(seconds=7)).checkpoint.state
    assert current.account.trading_day == at.date() and current.account.day_start_equity == D("10000")


def test_model_basis_does_not_fake_quotes_or_remove_closed_h4_rsi_entry_requirement():
    runner = PaperRunner("tenant", "account")
    old = runner.start(MIDNIGHT-timedelta(seconds=1))
    cp = runner.day(old, bars(), now=MIDNIGHT+timedelta(seconds=1)).checkpoint
    for symbol in ("BTCUSDT", "ETHUSDT"):
        cp = runner.quote(cp, Quote(symbol, MIDNIGHT+timedelta(seconds=2), D(100), D(101)),
                          now=MIDNIGHT+timedelta(seconds=2)).checkpoint
    for bar in bars():
        cp = runner.bar(cp, bar, now=MIDNIGHT+timedelta(seconds=3)).checkpoint
    assert not cp.state.orders and not cp.state.processed_fills
    assert all(b.indicators.rsi is None for b in cp.state.baskets)
    assert runner.simulator.engine.config.rsi_period == 14


def test_second_closed_h4_rsi_below_30_still_creates_intent_then_real_later_fill():
    runner = PaperRunner("tenant", "account")
    old = runner.start(MIDNIGHT-timedelta(seconds=1))
    btc = replace(old.state.baskets[0], sub30_count=1,
                  indicators=IndicatorState(previous_close=D(100), changes=14,
                      average_gain=D(0), average_loss=D(1), rsi=D(0)))
    old = replace(old, state=replace(old.state, baskets=(btc, old.state.baskets[1])))
    cp = runner.day(old, bars(), now=MIDNIGHT+timedelta(seconds=1)).checkpoint
    assert cp.state.basket("BTCUSDT").indicators == btc.indicators
    for symbol in ("BTCUSDT", "ETHUSDT"):
        cp = runner.quote(cp, Quote(symbol, MIDNIGHT+timedelta(seconds=2), D(100), D(101)),
                          now=MIDNIGHT+timedelta(seconds=2)).checkpoint
    cp = runner.bar(cp, bars()[0], now=MIDNIGHT+timedelta(seconds=3)).checkpoint
    assert cp.state.basket("BTCUSDT").sub30_count == 2
    assert len(cp.state.orders) == 1 and not cp.state.processed_fills
    cp = runner.quote(cp, Quote("BTCUSDT", MIDNIGHT+timedelta(seconds=4), D(100), D(101)),
                      now=MIDNIGHT+timedelta(seconds=4)).checkpoint
    assert len(cp.state.processed_fills) == 1
    assert cp.last_entry.fills[0].price == D("101.101")
