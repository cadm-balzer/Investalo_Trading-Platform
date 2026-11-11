"""Bounded public Bitget funding observations and explicit schedule diagnostics."""
from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import time
from urllib.parse import urlencode
from urllib.request import Request, build_opener

from .bitget import EPOCH, _NoRedirect
from .futures_snapshot import (
    FUNDING_ENDPOINT, MAX_FUNDING_EVENTS, SYMBOLS, FundingEvent, FundingSnapshot, funding_rate,
)
from .snapshot import canonical, decode_json, iso, utc_time

PAGE_SIZE = 100
MAX_PAGES = 100
MAX_RESPONSE_BYTES = 256 * 1024
VERSION = "funding-availability/1"


def _hash(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def funding_url(symbol, page):
    if symbol not in SYMBOLS or type(page) is not int or not 1 <= page <= MAX_PAGES:
        raise ValueError("fixed futures symbol and bounded page required")
    return FUNDING_ENDPOINT + "?" + urlencode({
        "symbol": symbol, "productType": "USDT-FUTURES",
        "pageSize": str(PAGE_SIZE), "pageNo": str(page),
    })


def fetch_funding_json(url):
    # Only the exact URLs this adapter builds; no keys, cookies or redirects.
    if not isinstance(url, str):
        raise ValueError("fixed public funding URL required")
    from urllib.parse import parse_qs, urlsplit
    query = parse_qs(urlsplit(url).query)
    try:
        expected = funding_url(query["symbol"][0], int(query["pageNo"][0]))
    except (KeyError, ValueError, TypeError, IndexError):
        raise ValueError("fixed public funding URL required") from None
    if url != expected:
        raise ValueError("fixed public funding URL required")
    request = Request(url, headers={"Accept": "application/json",
                                   "User-Agent": "Investalo-funding-history/1"})
    with build_opener(_NoRedirect()).open(request, timeout=10) as response:
        body = response.read(MAX_RESPONSE_BYTES + 1)
    return decode_json(body, max_bytes=MAX_RESPONSE_BYTES)


def _rows(payload, symbol, retrieved_at):
    if not isinstance(payload, dict) or payload.get("code") != "00000":
        raise ValueError("provider did not confirm funding success")
    rows = payload.get("data")
    if type(rows) is not list or len(rows) > PAGE_SIZE:
        raise ValueError("bounded funding page required")
    events = []
    for row in rows:
        if (not isinstance(row, dict) or set(row) != {"symbol", "fundingTime", "fundingRate"}
                or row["symbol"] != symbol):
            raise ValueError("own exact funding row required")
        stamp = row["fundingTime"]
        if (not isinstance(stamp, str) or not stamp.isascii() or not stamp.isdigit()
                or not 1 <= len(stamp) <= 15):
            raise ValueError("bounded millisecond timestamp required")
        try:
            at = EPOCH + timedelta(milliseconds=int(stamp))
        except OverflowError:
            raise ValueError("funding timestamp outside supported range") from None
        if at >= retrieved_at:
            raise ValueError("future or not-yet-observed funding settlement")
        event = FundingEvent(at, funding_rate(row["fundingRate"]))
        if events and event.timestamp >= events[-1].timestamp:
            raise ValueError("funding page must be strictly descending")
        events.append(event)
    return tuple(events)


@dataclass(frozen=True)
class FundingPage:
    page: int
    url: str
    response_digest: str
    returned_events: int
    newest: datetime | None
    oldest: datetime | None

    def record(self):
        return {**self.__dict__,
                "newest": iso(self.newest) if self.newest is not None else None,
                "oldest": iso(self.oldest) if self.oldest is not None else None}


@dataclass(frozen=True)
class FundingHistoryResult:
    requested: FundingSnapshot
    observed: FundingSnapshot
    pages: tuple[FundingPage, ...]
    termination: str


@dataclass(frozen=True)
class BitgetFundingHistoryAdapter:
    fetch_json: object = fetch_funding_json
    sleep: object = time.sleep
    page_delay_seconds: float = .1

    def fetch_history(self, symbol, *, start, end, retrieved_at):
        start, end, retrieved_at = map(utc_time, (start, end, retrieved_at))
        # Validate before network access, including empty and future windows.
        FundingSnapshot(symbol, retrieved_at, start, end, ())
        events, pages, previous_oldest = {}, [], None
        for page in range(1, MAX_PAGES + 1):
            if page > 1:
                self.sleep(self.page_delay_seconds)
            url = funding_url(symbol, page)
            payload = self.fetch_json(url)
            rows = _rows(payload, symbol, retrieved_at)
            pages.append(FundingPage(page, url, _hash(payload), len(rows),
                                     rows[0].timestamp if rows else None,
                                     rows[-1].timestamp if rows else None))
            if not rows:
                termination = "empty_page"
                break
            oldest = rows[-1].timestamp
            if previous_oldest is not None and oldest >= previous_oldest:
                raise ValueError("funding pagination did not advance")
            for event in rows:
                existing = events.get(event.timestamp)
                if existing is not None and existing != event:
                    raise ValueError("revised funding overlap")
                events[event.timestamp] = event
            if len(events) > MAX_FUNDING_EVENTS:
                raise ValueError("funding event capacity exhausted")
            previous_oldest = oldest
            if oldest <= start:
                termination = "reached_requested_start"
                break
        else:
            raise ValueError("funding page capacity exhausted; no success receipt")
        observed = tuple(events[at] for at in sorted(events))
        selected = tuple(e for e in observed if start <= e.timestamp < end)
        return FundingHistoryResult(
            FundingSnapshot(symbol, retrieved_at, start, end, selected),
            FundingSnapshot(symbol, retrieved_at,
                            observed[0].timestamp if observed else start, retrieved_at, observed),
            tuple(pages), termination,
        )


@dataclass(frozen=True)
class FundingExpectation:
    """Caller-declared calendar; neither provider attestation nor economic authority."""
    symbol: str
    start: datetime
    end: datetime
    settlements: tuple[datetime, ...]
    assumptions_digest: str

    def __post_init__(self):
        if self.symbol not in SYMBOLS or not isinstance(self.assumptions_digest, str) or not (
                1 <= len(self.assumptions_digest) <= 128):
            raise ValueError("own symbol and explicit calendar assumption required")
        utc_time(self.start)
        utc_time(self.end)
        if (not self.start < self.end or type(self.settlements) is not tuple
                or not 1 <= len(self.settlements) <= MAX_FUNDING_EVENTS):
            raise ValueError("bounded nonempty explicit settlement calendar required")
        previous = None
        for at in self.settlements:
            utc_time(at)
            if not self.start <= at < self.end or previous is not None and at <= previous:
                raise ValueError("canonical settlement times inside exact window required")
            previous = at

    @property
    def expectation_digest(self):
        return _hash((VERSION, self.symbol, iso(self.start), iso(self.end),
                      tuple(iso(at) for at in self.settlements), self.assumptions_digest))


def regular_funding_expectation(symbol, start, end, *, interval_hours, assumptions_digest):
    """Explicit hypothesis only; current cadence is not a historical schedule proof."""
    start, end = utc_time(start), utc_time(end)
    if type(interval_hours) is not int or not 1 <= interval_hours <= 24 or not start < end:
        raise ValueError("bounded explicit interval and positive window required")
    interval = timedelta(hours=interval_hours)
    count = (end - start + interval - timedelta(microseconds=1)) // interval
    if not 1 <= count <= MAX_FUNDING_EVENTS:
        raise ValueError("settlement calendar capacity exhausted")
    return FundingExpectation(symbol, start, end,
                              tuple(start + interval * i for i in range(count)), assumptions_digest)


def audit_funding_coverage(snapshot, expectation):
    if not isinstance(snapshot, FundingSnapshot) or not isinstance(expectation, FundingExpectation):
        raise ValueError("typed snapshot and explicit expectation required")
    if (snapshot.symbol, snapshot.requested_start, snapshot.requested_end) != (
            expectation.symbol, expectation.start, expectation.end):
        raise ValueError("foreign symbol or calendar window")
    actual = {event.timestamp for event in snapshot.events}
    expected = set(expectation.settlements)
    missing, unexpected = tuple(sorted(expected - actual)), tuple(sorted(actual - expected))
    return {
        "schema_version": VERSION, "data_digest": snapshot.data_digest,
        "expectation_digest": expectation.expectation_digest,
        "expected_events": len(expected), "observed_events": len(actual),
        "missing_events": len(missing), "unexpected_events": len(unexpected),
        "first_missing": iso(missing[0]) if missing else None,
        "last_missing": iso(missing[-1]) if missing else None,
        "missing_times_digest": _hash(tuple(iso(at) for at in missing)),
        "unexpected_times_digest": _hash(tuple(iso(at) for at in unexpected)),
        "complete_against_declared_calendar": not missing and not unexpected,
        "calendar_provenance": "declared-research-assumption",
        "historical_schedule_verified": False, "performance_evaluated": False,
        "execution_enabled": False,
    }
