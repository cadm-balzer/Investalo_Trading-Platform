"""Unsigned Classic observations and guarded handoff to the own Paper runner."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import time
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, build_opener

from investalo_trading.capital_digest import digest
from investalo_trading.futures_capital_signals import CapitalHour
from investalo_trading.futures_paper import FuturesPaperState, PaperBatch, PaperFunding, PaperQuote
from investalo_trading.snapshot import primitive
from investalo_trading.timeframe_research import ResearchCandle

from .bitget import EPOCH, _NoRedirect, milliseconds
from .futures_broker_calibration import SYMBOLS
from .futures_snapshot import funding_rate
from .snapshot import canonical, decode_json, price, utc_time

VERSION = "bitget-classic-futures-paper-source/1"
ORIGIN = "https://api.bitget.com"
PATHS = {
    "trade": "/api/v2/mix/market/history-candles",
    "mark": "/api/v2/mix/market/history-mark-candles",
    "funding": "/api/v2/mix/market/history-fund-rate",
    "forecast": "/api/v2/mix/market/current-fund-rate",
    "quote": "/api/v2/mix/market/ticker",
}
H1 = timedelta(hours=1)
MAX_BYTES = 256 * 1024
MAX_COLLECTION_SECONDS = 25


def hour_boundary(value):
    return utc_time(value).replace(minute=0, second=0, microsecond=0)


def stamp(value, *, integer=False):
    if integer:
        if type(value) is not int or value < 0:
            raise ValueError("integer provider requestTime required")
        value = str(value)
    if (type(value) is not str or not value.isascii() or not value.isdigit()
            or not 1 <= len(value) <= 15):
        raise ValueError("bounded native millisecond timestamp required")
    try:
        return EPOCH + timedelta(milliseconds=int(value))
    except OverflowError:
        raise ValueError("provider timestamp outside bounds") from None


def request_url(symbol, kind, *, start=None, end=None):
    if symbol not in SYMBOLS or kind not in PATHS:
        raise ValueError("fixed calibrated Classic candidate and public kind required")
    query = {"productType": "USDT-FUTURES", "symbol": symbol}
    if kind in ("trade", "mark"):
        if (start != hour_boundary(start) or end != hour_boundary(end)
                or not 1 <= (end - start) // H1 <= 72):
            raise ValueError("bounded exact closed H1 window required")
        query.update(granularity="1H", limit="100",
                     startTime=str(milliseconds(start - H1)), endTime=str(milliseconds(end)))
    elif start is not None or end is not None:
        raise ValueError("unexpected public query window")
    if kind == "funding":
        query.update(pageSize="100", pageNo="1")
    return ORIGIN + PATHS[kind] + "?" + urlencode(query)


def fetch_paper_source_json(url):
    """Canonical GET URLs only; no redirects, keys, retry or caller-supplied host."""
    if type(url) is not str or len(url) > 512:
        raise ValueError("bounded fixed public URL required")
    parsed = urlsplit(url)
    try:
        query = parse_qs(parsed.query, strict_parsing=True)
        symbol = query["symbol"][0]
        kind = next(k for k in PATHS if parsed.path == PATHS[k])
        kwargs = ({"start": stamp(query["startTime"][0]) + H1,
                   "end": stamp(query["endTime"][0])} if kind in ("trade", "mark") else {})
        expected = request_url(symbol, kind, **kwargs)
    except (KeyError, StopIteration, ValueError, TypeError):
        raise ValueError("fixed public Classic URL required") from None
    if url != expected:
        raise ValueError("canonical public Classic URL required")
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "Investalo-futures-paper-source/1"})
    with build_opener(_NoRedirect()).open(request, timeout=5) as response:
        raw = response.read(MAX_BYTES + 1)
    return decode_json(raw, max_bytes=MAX_BYTES)


@dataclass(frozen=True)
class PublicRead:
    url: str
    requested_at: datetime
    received_at: datetime
    server_at: datetime
    response_digest: str


@dataclass(frozen=True)
class NativeQuote:
    quote: PaperQuote
    native_at: datetime


@dataclass(frozen=True)
class NativeFunding:
    symbol: str
    native_id: str
    settled_at: datetime
    rate: Decimal


@dataclass(frozen=True)
class FundingForecast:
    symbol: str
    observed_at: datetime
    next_update: datetime
    interval_hours: int
    current_rate: Decimal


@dataclass(frozen=True)
class FuturesMarketObservation:
    start: datetime
    end: datetime
    funding_start: datetime
    collected_at: datetime
    hours: tuple[CapitalHour, ...]
    quotes: tuple[NativeQuote, ...]
    funding: tuple[NativeFunding, ...]
    forecasts: tuple[FundingForecast, ...]
    reads: tuple[PublicRead, ...]

    @property
    def data_digest(self):
        return hashlib.sha256(canonical(self.record()).encode()).hexdigest()

    def record(self):
        return {"schema_version": VERSION, "observation": primitive(self),
                "venue": "bitget", "account_family": "classic", "product": "USDT-FUTURES",
                "settlement_mark_available": False, "execution_enabled": False}

    def paper_batch(self, state, *, previous=None, settlement=None):
        """Receipt-time valuation; each native quote clock stays in source evidence.

        Crossing funding needs the acknowledged explicit settlement command.
        Neither a forecast rate nor a later mark substitutes for it.
        Preserve this source record before acknowledging its digest in a journal.
        """
        if type(state) is not FuturesPaperState or not state.warmed:
            raise ValueError("own warmed Paper state required")
        symbols = tuple("BITGET:" + s for s in SYMBOLS)
        if state.signal.profile.plan.symbols != symbols:
            raise ValueError("own Classic Paper universe required; no Binance/Spot mixing")
        if self.funding_start > state.signal.as_of or self.collected_at < state.observed_at:
            raise ValueError("source window misses own Paper checkpoint")
        if (any(not timedelta(0) <= self.collected_at - q.native_at <= timedelta(seconds=30)
                for q in self.quotes)
                or tuple(q.quote.symbol for q in self.quotes) != symbols
                or tuple(f.symbol for f in self.forecasts) != symbols):
            raise ValueError("complete fresh native source evidence required")
        active = {b.symbol for b in state.signal.economic.ledger.baskets if b.quantity}
        if any(f.next_update <= self.collected_at for f in self.forecasts):
            raise ValueError("funding forecast rolled during collection; refresh source")
        if active:
            from investalo_trading.futures_paper_settlement import PaperSettlement
            from investalo_trading.futures_paper_minute import PaperMinuteSettlement
            accounted = (type(settlement) in (PaperSettlement, PaperMinuteSettlement)
                         and settlement.receipt_id in state.inputs
                         and settlement.settled_at == state.signal.as_of)
            if (type(previous) is not FuturesMarketObservation
                    or (previous.collected_at != state.signal.as_of and not (
                        accounted and previous.collected_at == state.signal.trade_at))
                    or "bitget-" + previous.data_digest not in state.inputs):
                raise ValueError("acknowledged prior source receipt required for open Paper exposure")
            paid = ({(f.symbol, f.settled_at) for f in settlement.funding} if accounted else set())
            if accounted:
                native = tuple(PaperFunding(f.symbol, f.native_id, f.settled_at, f.rate)
                               for f in self.funding if f.settled_at == settlement.settled_at)
                if native != settlement.funding:
                    raise ValueError("committed native funding revised or missing from source")
                if any(f.symbol in active and previous.collected_at < f.settled_at <= state.signal.as_of
                       and (f.symbol, f.settled_at) not in paid for f in self.funding):
                    raise ValueError("unaccounted earlier native funding requires reconciliation")
            if (any(f.symbol in active and f.next_update <= self.collected_at
                    and (f.symbol, f.next_update) not in paid for f in previous.forecasts)
                    or any(f.symbol in active and state.signal.as_of < f.settled_at <= self.collected_at
                           for f in self.funding)):
                raise ValueError("funding settlement valuation required; do not omit or shift native funding")
        overlap = tuple(h for h in self.hours if h.close_time == state.signal.last_hour.close_time)
        if overlap and overlap[0] != state.signal.last_hour:
            raise ValueError("committed native H1 candle revised")
        hours = tuple(h for h in self.hours if h.close_time > state.signal.last_hour.close_time)
        return PaperBatch("bitget-" + self.data_digest, self.collected_at,
                          tuple(q.quote for q in self.quotes), hours, ())

    def paper_settlement(self, state, *, previous, settled_at, marks, valuation_digest):
        """Join published native rates to separately archived exact-time marks.

        This source has no settlement mark. The caller must supply that evidence;
        current ticker marks and H1 approximations are never selected automatically.
        """
        from investalo_trading.futures_paper_settlement import PaperSettlement
        settled_at = utc_time(settled_at)
        symbols = tuple("BITGET:" + s for s in SYMBOLS)
        if (type(state) is not FuturesPaperState or not state.warmed
                or state.config.profile.plan.symbols != symbols
                or type(previous) is not FuturesMarketObservation
                or previous.collected_at != state.signal.as_of
                or "bitget-" + previous.data_digest not in state.inputs
                or self.funding_start > previous.collected_at
                or not state.signal.as_of < settled_at <= self.collected_at
                or self.collected_at - settled_at > timedelta(hours=1)
                or self.collected_at < state.observed_at):
            raise ValueError("bounded current source and acknowledged own settlement predecessor required")
        active = {b.symbol for b in state.signal.economic.ledger.baskets if b.quantity}
        if any(f.symbol in active and state.signal.as_of < f.settled_at < settled_at
               for f in self.funding) or any(
                f.symbol in active and f.next_update < settled_at for f in previous.forecasts):
            raise ValueError("earlier native or expected funding cannot be omitted")
        rows = tuple(PaperFunding(f.symbol, f.native_id, f.settled_at, f.rate)
                     for f in self.funding if f.settled_at == settled_at)
        paid = {f.symbol for f in rows}
        if any(f.symbol in active and f.next_update == settled_at and f.symbol not in paid
               for f in previous.forecasts):
            raise ValueError("expected native funding not yet published")
        overlap = tuple(h for h in self.hours if h.close_time == state.signal.last_hour.close_time)
        if overlap and overlap[0] != state.signal.last_hour:
            raise ValueError("committed native H1 candle revised")
        hours = tuple(h for h in self.hours if state.signal.last_hour.close_time < h.close_time <= settled_at)
        key = digest((self.data_digest, previous.data_digest, settled_at, marks, valuation_digest))
        return PaperSettlement("bitget-settlement-" + key, settled_at, marks, valuation_digest, rows, hours)


@dataclass(frozen=True)
class BitgetFuturesMarketSource:
    fetch_json: object = fetch_paper_source_json
    clock: object = lambda: datetime.now(timezone.utc)
    sleep: object = time.sleep
    pace_seconds: float = .1

    def __post_init__(self):
        if (not all(callable(c) for c in (self.fetch_json, self.clock, self.sleep))
                or type(self.pace_seconds) not in (int, float)
                or not .05 <= self.pace_seconds <= 1):
            raise ValueError("bounded paced public transport/clock required")

    def collect(self, *, start, end, funding_start):
        start, end, funding_start = map(utc_time, (start, end, funding_start))
        request_url(SYMBOLS[0], "trade", start=start, end=end)
        began = utc_time(self.clock())
        if end > hour_boundary(began) or not began - timedelta(hours=72) <= funding_start <= began:
            raise ValueError("closed current source and bounded funding lookback required")
        reads = []

        def read(symbol, kind, **kwargs):
            if reads:
                self.sleep(self.pace_seconds)
            before = utc_time(self.clock())
            if before < began or (reads and before < reads[-1].received_at):
                raise ValueError("source clock regressed")
            url = request_url(symbol, kind, **kwargs)
            payload = self.fetch_json(url)
            after = utc_time(self.clock())
            if not before <= after <= began + timedelta(seconds=MAX_COLLECTION_SECONDS):
                raise ValueError("source clock/deadline changed during collection")
            encoded = canonical(payload).encode()
            if (len(encoded) > MAX_BYTES or type(payload) is not dict or payload.get("code") != "00000"
                    or type(payload.get("data")) is not list):
                raise ValueError("successful bounded public Classic response required")
            server = stamp(payload.get("requestTime"), integer=True)
            if not timedelta(0) <= after - server <= timedelta(seconds=30):
                raise ValueError("stale/future provider response clock")
            reads.append(PublicRead(url, before, after, server, hashlib.sha256(encoded).hexdigest()))
            return payload["data"], after, server

        candles, funding, forecasts = {}, [], []
        for symbol in SYMBOLS:
            for kind in ("trade", "mark"):
                rows, after, _ = read(symbol, kind, start=start, end=end)
                if not len(rows) <= 100:
                    raise ValueError("bounded current H1 response required")
                selected, seen = {}, set()
                for row in rows:
                    if type(row) is not list or len(row) != 7:
                        raise ValueError("native seven-field H1 row required")
                    opened = stamp(row[0])
                    if (opened != hour_boundary(opened) or opened in seen
                            or not start - H1 <= opened <= end):
                        raise ValueError("duplicate, unaligned or out-of-window H1 row")
                    seen.add(opened)
                    price(row[5], zero=True)
                    price(row[6], zero=True)
                    candle = ResearchCandle(f"BITGET:{symbol}:USDT-M:{kind}", opened, opened + H1,
                                            *(price(row[i]) for i in (1, 2, 3, 4)))
                    if start <= opened < end:
                        if candle.close_time > after:
                            raise ValueError("unfinished native H1")
                        selected[opened] = candle
                axis = tuple(start + H1 * i for i in range(int((end - start) // H1)))
                if set(selected) != set(axis):
                    raise ValueError("native H1 coverage incomplete")
                candles[symbol, kind] = tuple(selected[t] for t in axis)
            rows, _, server = read(symbol, "funding")
            if not 1 <= len(rows) <= 100:
                raise ValueError("nonempty bounded native funding history required")
            last = None
            for row in rows:
                if type(row) is not dict or set(row) != {"symbol", "fundingTime", "fundingRate"} or row["symbol"] != symbol:
                    raise ValueError("own native funding fields required")
                settled = stamp(row["fundingTime"])
                if settled >= server or last is not None and settled >= last:
                    raise ValueError("native funding duplicate, unsorted or future")
                last = settled
                rate = funding_rate(row["fundingRate"])
                if funding_start <= settled:
                    funding.append(NativeFunding("BITGET:" + symbol, f"BITGET:{symbol}:{row['fundingTime']}",
                                                 settled, rate))
            if last > funding_start:
                raise ValueError("native funding history does not cover checkpoint")
            rows, _, server = read(symbol, "forecast")
            if len(rows) != 1 or type(rows[0]) is not dict or rows[0].get("symbol") != symbol:
                raise ValueError("one own current funding forecast required")
            row = rows[0]
            interval, update = row.get("fundingRateInterval"), stamp(row.get("nextUpdate"))
            if interval not in ("1", "2", "4", "8") or not server < update <= server + timedelta(hours=24):
                raise ValueError("bounded native next funding forecast required")
            forecasts.append(FundingForecast("BITGET:" + symbol, server, update, int(interval),
                                             funding_rate(row.get("fundingRate"))))
        # Quotes are last, keeping native bid/ask/mark clocks fresh as a cohort.
        quotes = []
        for symbol in SYMBOLS:
            rows, after, server = read(symbol, "quote")
            if len(rows) != 1 or type(rows[0]) is not dict or rows[0].get("symbol") != symbol:
                raise ValueError("one own Classic quote required")
            row = rows[0]
            native = stamp(row.get("ts"))
            if (not timedelta(0) <= after - native <= timedelta(seconds=30)
                    or abs(native - server) > timedelta(seconds=1)):
                raise ValueError("stale, future or mismatched native quote clock")
            quotes.append(NativeQuote(PaperQuote("BITGET:" + symbol, price(row.get("bidPr")),
                                                 price(row.get("askPr")), price(row.get("markPrice"))), native))
        collected = utc_time(self.clock())
        if (not reads[-1].received_at <= collected <= began + timedelta(seconds=MAX_COLLECTION_SECONDS)
                or any(not timedelta(0) <= collected - q.native_at <= timedelta(seconds=30) for q in quotes)
                or hour_boundary(collected) != hour_boundary(began)):
            raise ValueError("source cohort stale or hour boundary changed during collection")
        if any(f.next_update <= collected for f in forecasts):
            raise ValueError("funding forecast rolled during collection; refresh source")
        hours = tuple(CapitalHour(
            tuple(candles[s, "trade"][i] for s in SYMBOLS),
            tuple(candles[s, "mark"][i] for s in SYMBOLS))
            for i in range(len(candles[SYMBOLS[0], "trade"])))
        return FuturesMarketObservation(start, end, funding_start, collected, hours, tuple(quotes),
                                        tuple(sorted(funding, key=lambda f: (f.settled_at, f.symbol))),
                                        tuple(forecasts), tuple(reads))
