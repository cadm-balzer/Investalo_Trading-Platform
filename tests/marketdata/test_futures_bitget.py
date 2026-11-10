import unittest
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from investalo_marketdata.futures_bitget import (
    BitgetFuturesHistoryAdapter, MAX_PAGES, PAGE_LIMIT, fetch_futures_json,
)
from investalo_marketdata.futures_snapshot import ENDPOINTS, candle_symbol
from investalo_marketdata.snapshot import H4

START = datetime(2022, 8, 1, tzinfo=timezone.utc)
RETRIEVED = datetime(2025, 9, 1, tzinfo=timezone.utc)


def row(index):
    return [str(int((START + index * H4).timestamp()) * 1000),
            "100", "102", "98", "101", "0", "0"]


def response(rows):
    return {"code": "00000", "data": rows}


class FuturesHistoryTests(unittest.TestCase):
    def adapter(self, fetch):
        return BitgetFuturesHistoryAdapter(fetch, 0.1, lambda _: None)

    def test_exact_boundary_pagination_preserves_all_bars_and_price_kind(self):
        calls = []

        def fetch(url):
            calls.append(url)
            query = parse_qs(urlsplit(url).query)
            self.assertEqual(query["productType"], ["USDT-FUTURES"])
            self.assertEqual(query["granularity"], ["4H"])
            self.assertEqual(query["limit"], [str(PAGE_LIMIT)])
            lower = int(query["startTime"][0])
            upper = int(query["endTime"][0])
            self.assertLessEqual(upper - lower, 90 * 86400 * 1000)
            return response(list(reversed([row(i) for i in range(401)
                                          if lower <= int(row(i)[0]) < upper])))

        for kind in ENDPOINTS:
            with self.subTest(kind=kind):
                result = self.adapter(fetch).fetch_history(
                    "BTCUSDT", kind, start=START, end=START + 401 * H4,
                    retrieved_at=RETRIEVED,
                )
                self.assertEqual(len(result.candles), 401)
                self.assertTrue(result.coverage.complete)
                self.assertTrue(all(bar.symbol == candle_symbol("BTCUSDT", kind)
                                    for bar in result.candles))
                self.assertEqual(urlsplit(calls[-1]).path, urlsplit(ENDPOINTS[kind]).path)
        self.assertEqual(len(calls), 9)
        self.assertEqual(MAX_PAGES, 52)

    def test_short_listing_history_remains_explicitly_incomplete(self):
        pages = iter((response([row(1), row(2)]), response([])))
        result = self.adapter(lambda _: next(pages)).fetch_history(
            "AVAXUSDT", "mark", start=START, end=START + 3 * H4, retrieved_at=RETRIEVED)
        self.assertFalse(result.coverage.complete)
        self.assertEqual(result.coverage.record()["missing_leading_bars"], 1)

    def test_interior_gaps_duplicates_outside_pages_and_unclosed_bars_rejected(self):
        for rows in ([row(0), row(2)], [row(0), row(0)], [row(3)],
                     [row(-2), row(0)], [row(0)[:5]],
                     [[True, *row(0)[1:]]], [[row(0)[0], "NaN", *row(0)[2:]]]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                self.adapter(lambda _: response(rows)).fetch_history(
                    "BTCUSDT", "trade", start=START, end=START + 3 * H4,
                    retrieved_at=RETRIEVED)

    def test_nonprogressing_second_page_never_retried(self):
        calls = []

        def fetch(url):
            calls.append(url)
            return response([row(200)])

        with self.assertRaises(ValueError):
            self.adapter(fetch).fetch_history("BTCUSDT", "trade", start=START,
                                              end=START + 201 * H4, retrieved_at=RETRIEVED)
        self.assertEqual(len(calls), 2)

    def test_empty_error_oversized_pages_and_transport_failure_fail_without_retry(self):
        for payload in (response([]), {"code": "40000", "data": []},
                        response([row(0)] * 202), response("not-rows")):
            calls = []

            def fetch(url):
                calls.append(url)
                return payload

            with self.subTest(payload=payload), self.assertRaises(ValueError):
                self.adapter(fetch).fetch_history("ETHUSDT", "index", start=START,
                                                  end=START + H4, retrieved_at=RETRIEVED)
            self.assertEqual(len(calls), 1)
        calls = []

        def fail(url):
            calls.append(url)
            raise TimeoutError("synthetic transport timeout")

        with self.assertRaises(TimeoutError):
            self.adapter(fail).fetch_history("BTCUSDT", "mark", start=START,
                                             end=START + H4, retrieved_at=RETRIEVED)
        self.assertEqual(len(calls), 1)

    def test_unsupported_window_market_and_pacing_rejected_before_transport(self):
        def fail(_):
            self.fail("invalid input reached transport")

        for symbol, kind, start, end in (
            ("BTC/USDT", "trade", START, START + H4),
            ("BTCUSDT", "spot", START, START + H4),
            ("BTCUSDT", "trade", START, START),
            ("BTCUSDT", "trade", START, START + 10001 * H4),
            ("BTCUSDT", "trade", START + timedelta(seconds=1), START + H4),
            ("BTCUSDT", "trade", START, RETRIEVED + H4),
        ):
            with self.subTest(symbol=symbol, kind=kind, end=end), self.assertRaises(ValueError):
                self.adapter(fail).fetch_history(symbol, kind, start=start, end=end,
                                                 retrieved_at=RETRIEVED)
        for delay in (True, 0, 0.049, float("nan"), 11):
            with self.subTest(delay=delay), self.assertRaises(ValueError):
                BitgetFuturesHistoryAdapter(fail, delay)

    def test_transport_rejects_nonpublic_origin_and_redirects(self):
        with patch("investalo_marketdata.futures_bitget.build_opener") as opener:
            for url in ("https://attacker.test/?key=secret",
                        ENDPOINTS["trade"] + "/extra?x=1",
                        "https://api.bitget.com/api/v2/mix/order/place-order?x=1"):
                with self.subTest(url=url), self.assertRaises(ValueError):
                    fetch_futures_json(url)
            opener.assert_not_called()
        from investalo_marketdata.bitget import _NoRedirect
        with self.assertRaises(ValueError):
            _NoRedirect().redirect_request(None, None, 302, "", {}, "https://attacker.test/")
