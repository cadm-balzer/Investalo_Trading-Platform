"""Native identity, exact windows, causal timestamps and transport failure bounds."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest
from unittest.mock import Mock, patch

from investalo_marketdata.binance_futures import (
    BinanceHistoryAdapter, BinanceSnapshot, FundingObservation, fetch_binance_json,
    funding_diagnostics, load_binance_snapshot, parse_rows, request_url,
)
from investalo_marketdata.bitget import milliseconds
from investalo_marketdata.futures_snapshot import load_futures_snapshot
from investalo_marketdata.snapshot import H4, canonical

START = datetime(2022, 8, 1, tzinfo=timezone.utc)
NOW = datetime(2026, 11, 1, tzinfo=timezone.utc)


def kline(at=START):
    return [milliseconds(at), "100", "110", "90", "105", "0",
            milliseconds(at + H4) - 1, "0", 1, "0", "0", "0"]


def funding(at=START, rate="0.0001", mark=""):
    return {"symbol": "BTCUSDT", "fundingTime": milliseconds(at), "fundingRate": rate,
            "markPrice": mark, "rateType": "Regular"}


def adapter(fetch):
    return BinanceHistoryAdapter(fetch, sleep=lambda _: None)


class BinanceFuturesTests(unittest.TestCase):
    def test_each_native_price_kind_roundtrips_with_own_identity(self):
        for kind in ("trade", "mark", "index"):
            with self.subTest(kind=kind):
                snapshot, pages = adapter(lambda _: [kline()]).fetch_history(
                    "BTCUSDT", kind, start=START, end=START + H4, retrieved_at=NOW)
                text = canonical(snapshot.record())
                self.assertEqual(load_binance_snapshot(text), snapshot)
                self.assertTrue(snapshot.rows[0].symbol.startswith("BINANCE:"))
                self.assertEqual(len(pages), 1)
                with self.assertRaises(ValueError):
                    load_futures_snapshot(text)

    def test_source_digest_tampering_is_rejected(self):
        snapshot, _ = adapter(lambda _: [kline()]).fetch_history(
            "BTCUSDT", "trade", start=START, end=START + H4, retrieved_at=NOW)
        for key, value in (("venue", "bitget"), ("url", "https://api.bitget.com"),
                           ("data_digest", "0" * 64), ("market", "spot")):
            with self.subTest(key=key):
                raw = snapshot.record()
                raw[key] = value
                with self.assertRaises(ValueError):
                    load_binance_snapshot(canonical(raw))

    def test_retrieval_time_is_not_part_of_economic_data_digest(self):
        snapshot, _ = adapter(lambda _: [kline()]).fetch_history(
            "BTCUSDT", "trade", start=START, end=START + H4, retrieved_at=NOW)
        self.assertEqual(replace(snapshot, retrieved_at=NOW - H4).data_digest, snapshot.data_digest)

    def test_millisecond_offsets_signed_rates_and_absent_mark_are_preserved(self):
        native = funding(START + timedelta(milliseconds=19), "-0.000125")
        replies = iter([[native], []])
        snapshot, pages = adapter(lambda _: next(replies)).fetch_history(
            "BTCUSDT", "funding", start=START, end=START + H4 * 2, retrieved_at=NOW)
        self.assertEqual(snapshot.rows[0].timestamp.microsecond, 19000)
        self.assertEqual(snapshot.rows[0].rate, Decimal("-0.000125"))
        self.assertIsNone(snapshot.rows[0].mark_price)
        self.assertIn("startTime=1659312000020", pages[1]["url"])
        self.assertEqual(load_binance_snapshot(canonical(snapshot.record())), snapshot)
        diagnostic = funding_diagnostics(snapshot)
        self.assertEqual(diagnostic["max_native_offset_ms"], 19)
        self.assertEqual(diagnostic["missing_buckets"], 0)
        self.assertFalse(diagnostic["historical_schedule_verified"])

    def test_empty_funding_is_missing_not_zero(self):
        snapshot, _ = adapter(lambda _: []).fetch_history(
            "BTCUSDT", "funding", start=START, end=START + H4 * 4, retrieved_at=NOW)
        self.assertEqual(snapshot.rows, ())
        self.assertEqual(funding_diagnostics(snapshot)["missing_buckets"], 2)

    def test_explicit_zero_and_native_mark_are_not_missing(self):
        replies = iter([[funding(rate="0", mark="123")], []])
        snapshot, _ = adapter(lambda _: next(replies)).fetch_history(
            "BTCUSDT", "funding", start=START, end=START + H4 * 2, retrieved_at=NOW)
        self.assertEqual(snapshot.rows[0].rate, Decimal(0))
        self.assertEqual(snapshot.rows[0].mark_price, Decimal(123))
        self.assertEqual(funding_diagnostics(snapshot)["missing_native_mark_prices"], 0)

    def test_calendar_diagnostic_reports_inner_holes_and_duplicate_buckets(self):
        rows = tuple(FundingObservation(at, Decimal(0), None, None) for at in (
            START, START + timedelta(milliseconds=1), START + H4 * 4))
        snapshot = BinanceSnapshot("BTCUSDT", "funding", START, START + H4 * 6, NOW, rows)
        result = funding_diagnostics(snapshot)
        self.assertEqual(result["missing_buckets"], 1)
        self.assertEqual(result["duplicate_buckets"], 1)

    def test_exact_inclusive_close_becomes_exclusive_h4_close(self):
        self.assertEqual(parse_rows([kline()], "BTCUSDT", "mark")[0].close_time, START + H4)
        row = kline()
        row[6] += 1
        with self.assertRaises(ValueError):
            parse_rows([row], "BTCUSDT", "mark")

    def test_incomplete_or_gapped_price_history_fails(self):
        for rows in ([], [kline()], [kline(), kline(START + H4 * 2)]):
            with self.subTest(rows=len(rows)), self.assertRaises(ValueError):
                adapter(lambda _: rows).fetch_history(
                    "BTCUSDT", "trade", start=START, end=START + H4 * 2, retrieved_at=NOW)

    def test_price_chunks_cover_exact_1000_row_boundary(self):
        calls = []
        def fetch(url):
            calls.append(url)
            if len(calls) == 1:
                return [kline(START + H4 * i) for i in range(1000)]
            return [kline(START + H4 * 1000)]
        snapshot, _ = adapter(fetch).fetch_history(
            "BTCUSDT", "trade", start=START, end=START + H4 * 1001, retrieved_at=NOW)
        self.assertEqual(len(snapshot.rows), 1001)
        self.assertEqual(len(calls), 2)
        self.assertIn(f"startTime={milliseconds(START + H4 * 1000)}", calls[1])

    def test_revised_overlap_and_recent_substitution_are_rejected(self):
        for second in (funding(), funding(NOW - H4)):
            with self.subTest(second=second["fundingTime"]):
                replies = iter([[funding()], [second]])
                with self.assertRaises(ValueError):
                    adapter(lambda _: next(replies)).fetch_history(
                        "BTCUSDT", "funding", start=START, end=START + H4 * 2, retrieved_at=NOW)

    def test_bounded_native_row_validation(self):
        invalid = [
            {**funding(), "symbol": "ETHUSDT"}, {**funding(), "fundingTime": True},
            {**funding(), "fundingRate": 0.1}, {**funding(), "fundingRate": "NaN"},
            {**funding(), "fundingRate": "2"}, {**funding(), "markPrice": "0"},
            {**funding(), "rateType": "Unexpected"}, {**funding(), "secret": "x"},
        ]
        for row in invalid:
            with self.subTest(row=row), self.assertRaises(ValueError):
                parse_rows([row], "BTCUSDT", "funding")

    def test_no_reordering_or_duplicate_candles_and_settlements(self):
        for rows, kind in (
            ([kline(), kline()], "trade"), ([kline(START + H4), kline()], "mark"),
            ([funding(), funding()], "funding"), ([funding(START + H4), funding()], "funding"),
        ):
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                parse_rows(rows, "BTCUSDT", kind)

    def test_inconsistent_or_non_decimal_ohlc_rejected(self):
        for value in ("80", 110, "Infinity"):
            row = kline()
            row[2] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                adapter(lambda _: [row]).fetch_history(
                    "BTCUSDT", "trade", start=START, end=START + H4, retrieved_at=NOW)

    def test_invalid_window_fails_before_fetch(self):
        for symbol, kind, start, end in (
            ("XMRUSDT", "funding", START, START + H4),
            ("BTCUSDT", "spot", START, START + H4),
            ("BTCUSDT", "trade", START, START),
            ("BTCUSDT", "trade", START + timedelta(seconds=1), START + H4),
            ("BTCUSDT", "trade", START, NOW + H4),
            ("BTCUSDT", "funding", START, START + H4 * 10001),
        ):
            calls = []
            with self.subTest(kind=kind, end=end), self.assertRaises(ValueError):
                adapter(lambda url: calls.append(url)).fetch_history(
                    symbol, kind, start=start, end=end, retrieved_at=NOW)
            self.assertFalse(calls)

    def test_timeout_is_not_retried(self):
        fetch = Mock(side_effect=TimeoutError)
        with self.assertRaises(TimeoutError):
            adapter(fetch).fetch_history(
                "BTCUSDT", "funding", start=START, end=START + H4, retrieved_at=NOW)
        self.assertEqual(fetch.call_count, 1)

    def test_pagination_exhaustion_is_not_success(self):
        index = 0
        def fetch(_):
            nonlocal index
            index += 1
            return [funding(START + timedelta(milliseconds=index))]
        with self.assertRaisesRegex(ValueError, "pagination bound"):
            adapter(fetch).fetch_history(
                "BTCUSDT", "funding", start=START, end=START + H4, retrieved_at=NOW)

    def test_no_private_redirect_extra_duplicate_or_foreign_url(self):
        good = request_url("BTCUSDT", "funding", milliseconds(START), milliseconds(START + H4) - 1)
        urls = [good + "&signature=x", good + "&symbol=BTCUSDT", good + "#fragment",
                good.replace("fapi.binance.com", "fapi.binance.com.evil.test"),
                good.replace("/fundingRate", "/order"), good.replace("https:", "http:"),
                good.replace("limit=1000", "limit=1001")]
        with patch("investalo_marketdata.binance_futures.build_opener") as opener:
            for url in urls:
                with self.subTest(url=url), self.assertRaises(ValueError):
                    fetch_binance_json(url)
            opener.assert_not_called()

    def test_index_uses_native_pair_parameter(self):
        url = request_url("ETHUSDT", "index", milliseconds(START), milliseconds(START + H4) - 1)
        self.assertIn("pair=ETHUSDT&interval=4h", url)
        self.assertNotIn("symbol=", url)

    def test_public_query_window_is_bounded_before_transport(self):
        for kind, bars in (("trade", 1001), ("funding", 10001)):
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                request_url("BTCUSDT", kind, milliseconds(START), milliseconds(START + H4 * bars) - 1)

    def test_declared_calendar_rejects_unaligned_diagnostic_window(self):
        snapshot = BinanceSnapshot("BTCUSDT", "funding", START + H4, START + H4 * 3, NOW, ())
        with self.assertRaises(ValueError):
            funding_diagnostics(snapshot)

    def test_transport_bounds_payload_and_uses_unsigned_get(self):
        good = request_url("BTCUSDT", "funding", milliseconds(START), milliseconds(START + H4) - 1)
        response = Mock()
        response.read.return_value = b"[]"
        opener = Mock()
        opener.open.return_value.__enter__ = Mock(return_value=response)
        opener.open.return_value.__exit__ = Mock(return_value=False)
        with patch("investalo_marketdata.binance_futures.build_opener", return_value=opener):
            self.assertEqual(fetch_binance_json(good), [])
            request = opener.open.call_args.args[0]
            self.assertEqual(request.get_method(), "GET")
            self.assertFalse(any("key" in key.lower() or "cookie" in key.lower() for key in request.headers))
            response.read.return_value = b" " * (512 * 1024 + 1)
            with self.assertRaises(ValueError):
                fetch_binance_json(good)

    def test_oversized_or_error_public_page_is_rejected(self):
        for payload in ({"code": -1003}, [funding()] * 1001):
            with self.subTest(type=type(payload)), self.assertRaises(ValueError):
                parse_rows(payload, "BTCUSDT", "funding")


if __name__ == "__main__":
    unittest.main()
