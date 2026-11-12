"""Hourly native identities, transport bounds, offset-preserving funding."""
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from investalo_marketdata.binance_futures import load_binance_snapshot
from investalo_marketdata.binance_futures_hourly import (
    H1, MAX_HOURS, HourlyHistoryAdapter, HourlySnapshot, fetch_hourly_json,
    funding_diagnostics, load_hourly_snapshot, parse_rows, request_url,
)
from investalo_marketdata.bitget import EPOCH, milliseconds
from investalo_marketdata.snapshot import canonical
from investalo_trading.timeframe_research import aggregate_h4
from test_binance_futures import START, NOW


def kline(at=START):
    return [milliseconds(at), "100", "110", "90", "105", "0",
            milliseconds(at + H1) - 1, "0", 1, "0", "0", "0"]


def funding(at=START, rate="0.0001", mark=""):
    return {"symbol": "SOLUSDT", "fundingTime": milliseconds(at),
            "fundingRate": rate, "markPrice": mark}


def adapter(fetch):
    return HourlyHistoryAdapter(fetch, sleep=lambda _: None)


class BinanceHourlyTests(unittest.TestCase):
    def test_all_five_symbols_and_price_kinds_roundtrip_under_own_identity(self):
        for symbol in ("BNBUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"):
            for kind in ("trade", "mark"):
                with self.subTest(symbol=symbol, kind=kind):
                    snapshot, _ = adapter(lambda _: [kline()]).fetch_history(
                        symbol, kind, start=START, end=START + H1, retrieved_at=NOW)
                    text = canonical(snapshot.record())
                    self.assertEqual(load_hourly_snapshot(text), snapshot)
                    self.assertEqual(snapshot.rows[0].symbol, f"BINANCE:{symbol}:USDT-M:{kind}")
                    with self.assertRaises(ValueError):
                        load_binance_snapshot(text)

    def test_legacy_h4_loader_does_not_accept_hourly_even_on_h4_aligned_window(self):
        snapshot, _ = adapter(lambda _: [kline(START + H1 * i) for i in range(4)]).fetch_history(
            "BTCUSDT", "trade", start=START, end=START + H1 * 4, retrieved_at=NOW)
        self.assertEqual(len(aggregate_h4(snapshot.rows)), 1)
        with self.assertRaises(ValueError):
            load_binance_snapshot(canonical(snapshot.record()))

    def test_h1_inclusive_close_and_exact_hour_alignment_are_enforced(self):
        for row in (kline(START + timedelta(minutes=1)), kline()):
            if row[0] == milliseconds(START):
                row[6] += 1
            with self.subTest(row=row[0]), self.assertRaises(ValueError):
                parse_rows([row], "SOLUSDT", "mark")
        self.assertEqual(parse_rows([kline()], "SOLUSDT", "mark")[0].close_time, START + H1)

    def test_exact_requested_coverage_and_gaps_are_enforced(self):
        for payload in ([], [kline()], [kline(), kline(START + H1 * 2)]):
            with self.subTest(rows=len(payload)), self.assertRaises(ValueError):
                adapter(lambda _: payload).fetch_history(
                    "BTCUSDT", "trade", start=START, end=START + H1 * 2, retrieved_at=NOW)

    def test_duplicate_and_unsorted_hourly_pages_fail_without_reordering(self):
        for payload in ([kline(), kline()], [kline(START + H1), kline()]):
            with self.assertRaises(ValueError):
                parse_rows(payload, "BTCUSDT", "trade")

    def test_1000_boundary_and_hourly_not_h4_queries(self):
        calls = []
        def fetch(url):
            calls.append(url)
            params = parse_qs(urlsplit(url).query)
            at = EPOCH + timedelta(milliseconds=int(params["startTime"][0]))
            count = (int(params["endTime"][0]) + 1 - int(params["startTime"][0])) // 3600000
            return [kline(at + H1 * i) for i in range(count)]
        snapshot, pages = adapter(fetch).fetch_history(
            "SOLUSDT", "mark", start=START, end=START + H1 * 1001, retrieved_at=NOW)
        self.assertEqual(len(snapshot.rows), 1001)
        self.assertEqual(len(pages), 2)
        self.assertIn("interval=1h", calls[0])
        self.assertIn(f"startTime={milliseconds(START + H1 * 1000)}", calls[1])

    def test_three_year_capacity_exceeds_old_h4_bounds_without_eviction(self):
        def fetch(url):
            query = parse_qs(urlsplit(url).query)
            at = EPOCH + timedelta(milliseconds=int(query["startTime"][0]))
            count = (int(query["endTime"][0]) + 1 - int(query["startTime"][0])) // 3600000
            return [kline(at + H1 * i) for i in range(count)]
        snapshot, pages = adapter(fetch).fetch_history(
            "BTCUSDT", "trade", start=START, end=START + H1 * 26304, retrieved_at=NOW)
        self.assertEqual(len(snapshot.rows), 26304)
        self.assertEqual(len(pages), 27)
        self.assertEqual(snapshot.rows[0].open_time, START)
        self.assertEqual(snapshot.rows[-1].close_time, START + H1 * 26304)

    def test_pagination_exhaustion_cannot_return_a_truncated_success(self):
        with patch("investalo_marketdata.binance_futures_hourly.MAX_PAGES", 1), \
                self.assertRaisesRegex(ValueError, "pagination"):
            adapter(lambda _: [funding()]).fetch_history(
                "SOLUSDT", "funding", start=START, end=START + H1 * 8, retrieved_at=NOW)

    def test_signed_funding_millisecond_offsets_and_missing_marks_are_preserved(self):
        replies = iter([[funding(START + timedelta(milliseconds=29), "-0.001")], []])
        snapshot, pages = adapter(lambda _: next(replies)).fetch_history(
            "SOLUSDT", "funding", start=START, end=START + H1 * 8, retrieved_at=NOW)
        self.assertEqual(snapshot.rows[0].timestamp.microsecond, 29000)
        self.assertEqual(snapshot.rows[0].rate, Decimal("-.001"))
        self.assertIsNone(snapshot.rows[0].mark_price)
        self.assertIn(f"startTime={milliseconds(START) + 30}", pages[1]["url"])
        self.assertEqual(funding_diagnostics(snapshot)["missing_native_mark_prices"], 1)
        self.assertEqual(load_hourly_snapshot(canonical(snapshot.record())), snapshot)

    def test_empty_funding_is_missing_and_explicit_zero_is_present(self):
        empty, _ = adapter(lambda _: []).fetch_history(
            "SOLUSDT", "funding", start=START, end=START + H1 * 8, retrieved_at=NOW)
        self.assertEqual(funding_diagnostics(empty)["missing_buckets"], 1)
        replies = iter([[funding(rate="0", mark="100")], []])
        zero, _ = adapter(lambda _: next(replies)).fetch_history(
            "SOLUSDT", "funding", start=START, end=START + H1 * 8, retrieved_at=NOW)
        self.assertEqual(funding_diagnostics(zero)["missing_buckets"], 0)
        self.assertEqual(funding_diagnostics(zero)["missing_native_mark_prices"], 0)
        self.assertEqual(zero.rows[0].rate, Decimal(0))

    def test_shorter_native_intervals_are_retained_even_when_8h_diagnostic_has_extra_events(self):
        replies = iter([[funding(), funding(START + H1 * 4)], []])
        snapshot, _ = adapter(lambda _: next(replies)).fetch_history(
            "SOLUSDT", "funding", start=START, end=START + H1 * 8, retrieved_at=NOW)
        diagnostic = funding_diagnostics(snapshot)
        self.assertEqual(len(snapshot.rows), 2)
        self.assertEqual(diagnostic["missing_buckets"], 0)
        self.assertEqual(diagnostic["duplicate_buckets"], 1)
        self.assertEqual(snapshot.rows[1].timestamp, START + H1 * 4)
        self.assertEqual(load_hourly_snapshot(canonical(snapshot.record())).rows, snapshot.rows)

    def test_funding_duplicates_revised_overlap_and_foreign_rows_are_rejected(self):
        for payload in ([funding(), funding()], [{**funding(), "symbol": "BTCUSDT"}]):
            with self.assertRaises(ValueError):
                parse_rows(payload, "SOLUSDT", "funding")
        replies = iter([[funding()], [funding()]])
        with self.assertRaises(ValueError):
            adapter(lambda _: next(replies)).fetch_history(
                "SOLUSDT", "funding", start=START, end=START + H1 * 8, retrieved_at=NOW)

    def test_windows_and_native_resource_bounds_fail_before_network(self):
        def fail(_):
            self.fail("must not fetch")
        for symbol, kind, end in (
            ("HYPEUSDT", "trade", START + H1), ("BTCUSDT", "index", START + H1),
            ("BTCUSDT", "trade", START + H1 * (MAX_HOURS + 1)),
        ):
            with self.subTest(symbol=symbol, kind=kind), self.assertRaises(ValueError):
                adapter(fail).fetch_history(symbol, kind, start=START, end=end, retrieved_at=NOW)

    def test_digests_bind_identity_but_exclude_retrieval_time(self):
        snapshot, _ = adapter(lambda _: [kline()]).fetch_history(
            "BTCUSDT", "trade", start=START, end=START + H1, retrieved_at=NOW)
        self.assertEqual(snapshot.data_digest, replace(snapshot, retrieved_at=NOW - H1).data_digest)
        for key, value in (("venue", "bitget"), ("market", "spot"), ("interval", "4h"),
                           ("kind", "mark"), ("data_digest", "0" * 64)):
            raw = snapshot.record()
            raw[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                load_hourly_snapshot(canonical(raw))

    def test_fixed_canonical_public_urls_reject_auth_redirect_hosts_and_extra_queries(self):
        url = request_url("BTCUSDT", "trade", milliseconds(START), milliseconds(START + H1) - 1)
        invalid = (url + "&signature=x", url.replace("interval=1h", "interval=4h"),
                   url.replace("https://fapi.binance.com", "https://other.example"),
                   url.replace("https://", "https://user@"), url + "#fragment",
                   url + "&symbol=BTCUSDT", url.replace("limit=1000", "limit=1001"))
        with patch("investalo_marketdata.binance_futures_hourly.build_opener") as opener:
            for value in invalid:
                with self.subTest(url=value), self.assertRaises(ValueError):
                    fetch_hourly_json(value)
            opener.assert_not_called()

    def test_timeout_and_response_bounds_never_retry(self):
        url = request_url("BTCUSDT", "trade", milliseconds(START), milliseconds(START + H1) - 1)
        with patch("investalo_marketdata.binance_futures_hourly.build_opener") as opener:
            opener.return_value.open.side_effect = TimeoutError
            with self.assertRaises(TimeoutError):
                fetch_hourly_json(url)
            self.assertEqual(opener.return_value.open.call_count, 1)
        with patch("investalo_marketdata.binance_futures_hourly.build_opener") as opener:
            response = opener.return_value.open.return_value.__enter__.return_value
            response.read.return_value = b" " * (512 * 1024 + 1)
            with self.assertRaises(ValueError):
                fetch_hourly_json(url)

    def test_invalid_ohlc_non_decimal_funding_and_shortened_native_close_fail(self):
        rows = []
        for index, value in ((1, "NaN"), (2, "1"), (4, 105), (6, True)):
            row = kline()
            row[index] = value
            rows.append(row)
        for row in rows:
            with self.subTest(row=row), self.assertRaises(ValueError):
                parse_rows([row], "BTCUSDT", "trade")
        for value in (True, "NaN", "2"):
            with self.assertRaises(ValueError):
                parse_rows([funding(rate=value)], "SOLUSDT", "funding")


if __name__ == "__main__":
    unittest.main()
