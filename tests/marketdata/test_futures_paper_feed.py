"""Actual source contract and causal Paper handoff, with synthetic HTTP only."""
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from investalo_marketdata.bitget import milliseconds
from investalo_marketdata.futures_paper_feed import (
    BitgetFuturesMarketSource, MAX_COLLECTION_SECONDS, PATHS, SYMBOLS,
    fetch_paper_source_json, request_url,
)
from investalo_marketdata.snapshot import canonical, decode_json
from investalo_trading.futures_capital_grid import CapitalGridRule
from investalo_trading.futures_capital_research import start_capital_research
from investalo_trading.futures_capital_signals import CapitalH1SignalProfile, start_capital_signals
from investalo_trading.futures_ledger import LedgerMark
from investalo_trading.futures_paper import FuturesPaperConfig, run_paper_batch, start_paper, warm_paper
from investalo_trading.futures_paper_journal import FuturesPaperJournal
from investalo_trading.futures_paper_plan import paper_pool_plan
from investalo_trading.snapshot import _decode
from investalo_marketdata.futures_paper_feed import FuturesMarketObservation
from test_futures_ledger import AT, fixture

D = Decimal
H1 = timedelta(hours=1)
END = AT + 16 * H1
NOW = END + timedelta(seconds=1)


class Provider:
    def __init__(self, now=NOW, next_update=AT + 24 * H1, mutate=None):
        self.now, self.next_update, self.mutate = now, next_update, mutate
        self.urls = []

    def fetch(self, url):
        self.urls.append(url)
        parsed = urlsplit(url)
        query = parse_qs(parsed.query)
        symbol = query["symbol"][0]
        kind = next(k for k, path in PATHS.items() if path == parsed.path)
        if kind in ("trade", "mark"):
            # Include the documented preceding boundary; the selected axis is exact.
            rows = []
            for i in range(-1, 17):
                opened = AT + i * H1
                price = D(130 - 2 * i) + (D(".05") if kind == "mark" else D(0))
                rows.append([str(milliseconds(opened)), str(price), str(price + 1),
                             str(price - 1), str(price), "0", "0"])
        elif kind == "funding":
            rows = [{"symbol": symbol, "fundingTime": str(milliseconds(AT + i * H1)),
                     "fundingRate": "-0.0001" if i == 8 else "0.0001"} for i in (16, 8, 0, -8)]
        elif kind == "forecast":
            rows = [{"symbol": symbol, "fundingRateInterval": "8", "fundingRate": "0.0002",
                     "nextUpdate": str(milliseconds(self.next_update))}]
        else:
            rows = [{"symbol": symbol, "bidPr": "100", "askPr": "100.01", "markPrice": "100.005",
                     "ts": str(milliseconds(self.now - timedelta(milliseconds=SYMBOLS.index(symbol) + 1)))}]
        payload = {"code": "00000", "requestTime": milliseconds(self.now), "data": rows}
        if self.mutate:
            self.mutate(kind, payload)
        return payload

    def collect(self):
        return BitgetFuturesMarketSource(self.fetch, lambda: self.now, lambda _: None).collect(
            start=AT, end=END, funding_start=AT)


def initial():
    contracts = tuple(replace(c, symbol="BITGET:" + s)
                      for c, s in zip(fixture(5).plan.contracts, SYMBOLS, strict=True))
    plan = paper_pool_plan("tenant", "account", "classic-paper", contracts,
                          tuple(CapitalGridRule(c.symbol, D(".01"), D("100000")) for c in contracts),
                          "a" * 64, initial_slots=3, configured_limit=3)
    prices = tuple(LedgerMark(s, D(100)) for s in plan.symbols)
    economic = start_capital_research(plan, prices, AT, "source-fixture-genesis")
    profile = CapitalH1SignalProfile(plan, 1, D(0), "source-fixture-assumptions")
    return start_paper(FuturesPaperConfig(profile, END, D(".001"), True),
                       start_capital_signals(profile, economic, prices))


def opened(observation=None):
    observation = observation or Provider().collect()
    state = initial()
    state = warm_paper(state, observation.hours, state.revision, END)
    batch = observation.paper_batch(state)
    return run_paper_batch(state, batch, state.revision, batch.quoted_at)


class FuturesPaperFeedTests(unittest.TestCase):
    def test_native_trade_mark_clocks_and_funding_are_distinct(self):
        provider = Provider()
        observation = provider.collect()
        self.assertEqual(len(provider.urls), 25)
        self.assertEqual(len(observation.hours), 16)
        self.assertEqual(len(observation.quotes), 5)
        self.assertEqual(len(observation.funding), 15)
        self.assertEqual(len({q.native_at for q in observation.quotes}), 5)
        self.assertEqual(observation.hours[-1].trade[0].close, D(100))
        self.assertEqual(observation.hours[-1].mark[0].close, D("100.05"))
        self.assertEqual(observation.funding[5].rate, D("-.0001"))
        self.assertEqual(observation.forecasts[0].current_rate, D(".0002"))
        self.assertFalse(observation.record()["settlement_mark_available"])
        self.assertFalse(observation.record()["execution_enabled"])
        self.assertTrue(all("kLineType" not in url for url in provider.urls))

    def test_fixed_transport_rejects_foreign_or_private_urls_before_io(self):
        url = request_url(SYMBOLS[0], "quote")
        wrong = (url.replace("api.bitget.com", "other.invalid"),
                 url + "&extra=1", url + "#fragment", url + "&symbol=BTCUSDT",
                 url.replace("/ticker", "/place-order"), url.replace("USDT-FUTURES", "SPOT"))
        with patch("investalo_marketdata.futures_paper_feed.build_opener") as opener:
            for value in wrong:
                with self.subTest(url=value), self.assertRaises(ValueError):
                    fetch_paper_source_json(value)
            opener.assert_not_called()

    def test_http_uses_unsigned_get_no_redirect_bounded_read(self):
        url = request_url(SYMBOLS[0], "quote")
        with patch("investalo_marketdata.futures_paper_feed.build_opener") as opener:
            response = opener.return_value.open.return_value.__enter__.return_value
            response.read.return_value = b'{"code":"00000","data":[]}'
            self.assertEqual(fetch_paper_source_json(url)["data"], [])
            request = opener.return_value.open.call_args.args[0]
            self.assertEqual(request.get_method(), "GET")
            self.assertEqual(set(k.lower() for k in request.headers), {"accept", "user-agent"})
            self.assertEqual(opener.return_value.open.call_args.kwargs["timeout"], 5)
            response.read.assert_called_once_with(256 * 1024 + 1)

    def test_candle_axis_duplicates_and_invalid_ohlc_fail(self):
        def gap(kind, p):
            if kind == "mark":
                p["data"].pop(4)
        def duplicate(kind, p):
            if kind == "trade":
                p["data"].append(deepcopy(p["data"][1]))
        def invalid(kind, p):
            if kind == "trade":
                p["data"][1][2] = "1"
        for mutation in (gap, duplicate, invalid):
            with self.subTest(mutation=mutation.__name__), self.assertRaises(ValueError):
                Provider(mutate=mutation).collect()

    def test_partial_response_and_provider_error_fail(self):
        for mutation in (lambda k, p: p.update(code="40000"),
                         lambda k, p: p.update(data=None)):
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                Provider(mutate=mutation).collect()

    def test_funding_truncation_duplicate_and_future_fail(self):
        def truncated(kind, p):
            if kind == "funding":
                p["data"] = p["data"][:2]
        def duplicate(kind, p):
            if kind == "funding":
                p["data"][1] = deepcopy(p["data"][0])
        def future(kind, p):
            if kind == "funding":
                p["data"][0]["fundingTime"] = str(milliseconds(NOW))
        for mutation in (truncated, duplicate, future):
            with self.subTest(mutation=mutation.__name__), self.assertRaises(ValueError):
                Provider(mutate=mutation).collect()

    def test_quote_currency_price_clock_and_crossed_spread_fail(self):
        for field, value in (("symbol", "BTCUSDC"), ("bidPr", "NaN"), ("bidPr", "101"),
                             ("ts", str(milliseconds(NOW - timedelta(seconds=31)))),
                             ("ts", str(milliseconds(NOW + timedelta(milliseconds=1))))):
            def mutation(kind, p):
                if kind == "quote":
                    p["data"][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                Provider(mutate=mutation).collect()

    def test_native_forecast_is_not_historical_funding(self):
        for update in (NOW, NOW + timedelta(days=2)):
            with self.subTest(update=update), self.assertRaises(ValueError):
                Provider(next_update=update).collect()
        def invalid(kind, p):
            if kind == "forecast":
                p["data"][0]["fundingRateInterval"] = "0"
        with self.assertRaises(ValueError):
            Provider(mutate=invalid).collect()

    def test_clock_regression_deadline_and_hour_roll_fail(self):
        for later in (NOW - timedelta(seconds=1),
                      NOW + timedelta(seconds=MAX_COLLECTION_SECONDS + 1),
                      END + H1):
            times = iter((NOW, NOW, later))
            with self.subTest(later=later), self.assertRaises(ValueError):
                BitgetFuturesMarketSource(Provider().fetch, lambda: next(times),
                                         lambda _: None).collect(start=AT, end=END, funding_start=AT)

    def test_transport_failure_has_no_automatic_retry(self):
        calls = []
        def broken(url):
            calls.append(url)
            raise OSError("synthetic disconnect")
        with self.assertRaises(OSError):
            BitgetFuturesMarketSource(broken, lambda: NOW, lambda _: None).collect(
                start=AT, end=END, funding_start=AT)
        self.assertEqual(len(calls), 1)

    def test_source_handoff_uses_own_cash_ask_and_frozen_leverage(self):
        state = opened()
        self.assertEqual(len(state.signal.economic.stages), 3)
        self.assertTrue(all(s.price == D("100.01") and s.own_capital == D("293.13365892")
                            for s in state.signal.economic.stages))
        self.assertTrue(all(d.leverage == 2 for d in state.signal.economic.decisions))
        self.assertEqual(state.signal.as_of, NOW)

    def test_open_exposure_requires_acknowledged_source_and_complete_window(self):
        old = Provider().collect()
        state = opened(old)
        new = Provider(now=NOW + timedelta(seconds=1)).collect()
        with self.assertRaisesRegex(ValueError, "prior source receipt"):
            new.paper_batch(state)
        with self.assertRaisesRegex(ValueError, "prior source receipt"):
            new.paper_batch(state, previous=replace(old, collected_at=NOW - timedelta(seconds=1)))
        with self.assertRaisesRegex(ValueError, "checkpoint"):
            replace(new, funding_start=NOW + timedelta(microseconds=1)).paper_batch(state, previous=old)
        batch = new.paper_batch(state, previous=old)
        self.assertEqual(len(run_paper_batch(state, batch, state.revision, batch.quoted_at)
                             .signal.economic.stages), 3)

    def test_native_funding_crossing_or_publication_lag_stops_before_commit(self):
        old = Provider(next_update=END + H1).collect()
        state = opened(old)
        new = Provider(now=END + H1 + timedelta(seconds=1), next_update=END + 2 * H1).collect()
        for observation in (new, replace(new, funding=())):
            with self.subTest(funding_present=bool(observation.funding)):
                with self.assertRaisesRegex(ValueError, "settlement valuation"):
                    observation.paper_batch(state, previous=old)
        # A settlement before the forecast due time also cannot be dropped.
        old = Provider().collect()
        state = opened(old)
        new = Provider(now=NOW + timedelta(seconds=2)).collect()
        funding = replace(new.funding[0], settled_at=NOW + timedelta(seconds=1))
        with self.assertRaisesRegex(ValueError, "settlement valuation"):
            replace(new, funding=(funding,)).paper_batch(state, previous=old)

    def test_committed_candle_revision_rejected(self):
        old = Provider().collect()
        state = opened(old)
        new = Provider(now=NOW + timedelta(seconds=1)).collect()
        hour = new.hours[-1]
        revised = replace(hour, trade=(replace(hour.trade[0], close=D("100.5")),) + hour.trade[1:])
        with self.assertRaisesRegex(ValueError, "candle revised"):
            replace(new, hours=new.hours[:-1] + (revised,)).paper_batch(state, previous=old)

    def test_source_artifact_digest_and_paper_journal_restore(self):
        old = Provider().collect()
        new = Provider(now=NOW + timedelta(seconds=1)).collect()
        initial_state = initial()
        with TemporaryDirectory() as folder:
            path = Path(folder) / "paper.jsonl"
            source = Path(folder) / "source.json"
            source.write_text(canonical(old.record()))
            restored_source = _decode(FuturesMarketObservation,
                                      decode_json(source.read_bytes())["observation"])
            self.assertEqual(restored_source.data_digest, old.data_digest)
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), old.data_digest)
            journal = FuturesPaperJournal.create(path, initial_state.config,
                                                initial_state.signal.trade_prices,
                                                initial_state.signal.trade_prices, AT,
                                                "source-fixture-genesis")
            journal.append("warmup", expected_revision=0, at=END, hours=old.hours)
            batch = old.paper_batch(journal.state)
            journal.append("batch", expected_revision=journal.state.revision, at=batch.quoted_at, batch=batch)
            batch = new.paper_batch(journal.state, previous=restored_source)
            journal.append("batch", expected_revision=journal.state.revision, at=batch.quoted_at, batch=batch)
            receipt, expected = journal.receipt, journal.state
            journal.close()
            restored = FuturesPaperJournal.restore(path, config_digest=initial_state.config.config_digest,
                                                  minimum_receipt=receipt)
            self.assertEqual(restored.state, expected)
            self.assertIn("bitget-" + restored_source.data_digest, restored.state.inputs)
            restored.close()
