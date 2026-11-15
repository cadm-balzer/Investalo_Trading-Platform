"""Declared synthetic prices/contracts for isolated Recovery acceptance only."""
from datetime import timedelta
from decimal import Decimal as D

from investalo_marketdata.futures_broker_calibration import ContractRules
from investalo_marketdata.futures_paper_universe import SEVEN_SYMBOLS
from investalo_trading.capital_digest import digest
from investalo_trading.futures_capital_signals import CapitalHour
from investalo_trading.futures_ledger import LedgerMark
from investalo_trading.futures_paper import PaperBatch, PaperQuote
from investalo_trading.futures_paper_journal import FuturesPaperJournal
from investalo_trading.timeframe_research import ResearchCandle
from investalo_workers.futures_local_profile import local_seven_profit_config


def hour(symbols, price, close):
    p = D(price)
    def candles(kind):
        return tuple(ResearchCandle(f"{s}:USDT-M:{kind}", close - timedelta(hours=1),
            close, p, p + 1, p - 1, p) for s in symbols)
    return CapitalHour(candles("trade"), candles("mark"))


def feed(journal, at, prices, hours=()):
    state = journal.state
    quotes = tuple(PaperQuote(s, D(p), D(p), D(p))
                   for s, p in zip(state.config.profile.plan.symbols, prices, strict=True))
    batch = PaperBatch("declared-recovery-fixture-" + str(state.revision), at, quotes, hours)
    return journal.append("batch", batch=batch, expected_revision=state.revision, at=at)


def create(path, tenant, account, now):
    """Actual reducers/journal, simulated observations; never a market-profit claim."""
    boundary = now.replace(minute=0, second=0, microsecond=0)
    origin = (boundary - timedelta(days=4)).replace(hour=0)
    rules = tuple(ContractRules(s, "normal", D(".01"), D(".0001"), D(".001"), D(5),
        D(100000), D(100000), D(".0006"), D(".0006"), D(".01"), D(".01"), D(1), D(20))
        for s in SEVEN_SYMBOLS)
    config = local_seven_profit_config(tenant, account, rules,
        digest(("declared-recovery-fixture-contracts", rules)), origin + timedelta(hours=16))
    symbols = config.profile.plan.symbols
    marks = tuple(LedgerMark(s, D(100)) for s in symbols)
    journal = FuturesPaperJournal.create(path, config, marks, marks, origin,
                                        "declared-synthetic-recovery-fixture")
    try:
        warm = tuple(hour(symbols, 130 - 2 * i, origin + timedelta(hours=i+1)) for i in range(16))
        journal.append("warmup", hours=warm, expected_revision=0, at=config.trading_from)
        feed(journal, config.trading_from + timedelta(seconds=1), (100,) * 7)
        close = config.trading_from + timedelta(hours=1)
        feed(journal, close, (2000,) * 7, (hour(symbols, 2000, close),))
        feed(journal, close + timedelta(seconds=1), (1000,) * 7)
        if journal.state.signal.economic.ledger.closed_baskets != 3:
            raise ValueError("synthetic profitable full closing fixture failed")
        # Stay flat with high RSI, then evaluate the final closed descending series.
        prefix = int((boundary - close).total_seconds() // 3600) - 59
        for offset in range(0, prefix, 72):
            count = min(72, prefix - offset)
            bars = tuple(hour(symbols, 2000, close + timedelta(hours=i+1))
                         for i in range(count))
            close = bars[-1].close_time
            feed(journal, close + timedelta(seconds=1), (1000,) * 7, bars)
        bars = tuple(hour(symbols, 2000 - 30 * i, close + timedelta(hours=i)) for i in range(1, 60))
        state = feed(journal, boundary + timedelta(seconds=1), (100,) * 7, bars)
        target = next(i for i, b in enumerate(state.signal.economic.ledger.baskets) if b.quantity)
        prices = tuple(40 if i == target else 100 for i in range(7))
        state = feed(journal, boundary + timedelta(seconds=2), prices)
        state = feed(journal, now - timedelta(seconds=2), prices)
        if len(state.signal.economic.stopped) != 1:
            raise ValueError("actual synthetic liquidation fixture failed")
        return journal, config
    except BaseException:
        journal.close()
        raise
