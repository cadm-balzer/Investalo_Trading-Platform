from datetime import datetime, timedelta, timezone
from decimal import Decimal
from urllib.parse import parse_qs, urlsplit
import pytest

from investalo_marketdata.paper_feed import BitgetPaperFeed, boundary, fetch_feed_json

NOW = datetime(2026, 1, 5, 12, 0, 10, tzinfo=timezone.utc)
END = boundary(NOW)


def ticker(**changes):
    return {"code": "00000", "data": [{
        "category": "SPOT", "symbol": "BTCUSDT", "bid1Price": "99.10",
        "ask1Price": "99.11", "ts": str(int(NOW.timestamp()*1000)), **changes,
    }]}


def row(opened):
    return [str(int(opened.timestamp()*1000)), "100", "101", "99", "100", "1", "100"]


def test_quote_uses_real_bid_ask_and_fixed_unsigned_spot_request():
    urls = []
    def fetch(url):
        urls.append(url)
        return ticker()
    q = BitgetPaperFeed(fetch).quote("BTCUSDT", now=NOW)
    assert q.bid == Decimal("99.10") and q.ask == Decimal("99.11")
    assert urls == ["https://api.bitget.com/api/v3/market/tickers?category=SPOT&symbol=BTCUSDT"]


@pytest.mark.parametrize("changes", [
    {"category": "USDT-FUTURES"}, {"symbol": "ETHUSDT"}, {"bid1Price": "101"},
    {"ask1Price": "0"}, {"bid1Price": 99}, {"ts": int(NOW.timestamp()*1000)},
    {"ts": str(int((NOW-timedelta(seconds=31)).timestamp()*1000))},
    {"ts": str(int((NOW+timedelta(milliseconds=1)).timestamp()*1000))},
])
def test_bad_wrong_stale_or_future_quote_rejected(changes):
    with pytest.raises(ValueError):
        BitgetPaperFeed(lambda _: ticker(**changes)).quote("BTCUSDT", now=NOW)


def test_closed_window_filters_current_bar_and_preserves_decimal_ohlc():
    start = END-timedelta(hours=8)
    def fetch(url):
        query = parse_qs(urlsplit(url).query)
        assert query["category"] == ["SPOT"] and query["interval"] == ["4H"]
        assert query["limit"] == ["100"]
        assert query["startTime"] == [str(int((start-timedelta(hours=4)).timestamp()*1000))]
        return {"code": "00000", "data": [row(END), row(start), row(start+timedelta(hours=4))]}
    bars = BitgetPaperFeed(fetch).closed_bars("BTCUSDT", start=start, end=END, now=NOW)
    assert len(bars) == 2 and bars[-1].close_time == END
    assert bars[0].symbol == "BTCUSDT"


@pytest.mark.parametrize("rows", [
    [], [row(END-timedelta(hours=8))],
    [row(END-timedelta(hours=8)), row(END-timedelta(hours=8))],
    [row(END-timedelta(hours=8)), row(END+timedelta(hours=4))],
])
def test_gaps_duplicates_and_out_of_window_bars_rejected(rows):
    with pytest.raises(ValueError):
        BitgetPaperFeed(lambda _: {"code": "00000", "data": rows}).closed_bars(
            "BTCUSDT", start=END-timedelta(hours=8), end=END, now=NOW)


@pytest.mark.parametrize("url", [
    "http://api.bitget.com/api/v3/market/tickers",
    "https://api.bitget.com.evil.test/api/v3/market/tickers",
    "https://api.bitget.com/api/v3/trade/place-order",
    "https://user@api.bitget.com/api/v3/market/candles",
    "https://api.bitget.com/api/v3/market/tickers#x",
])
def test_other_origins_private_paths_and_redirect_targets_rejected_before_io(url):
    with pytest.raises(ValueError):
        fetch_feed_json(url)
