"""Shared Wilder calculation, public-source causality and bounded hour cache."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import threading
import time
import unittest
from unittest.mock import patch

from investalo_bitget.futures_demo_signals import (
    SYMBOLS, WARM_BARS, DemoSignalMonitor, boundary, milliseconds, signal_asset,
    signal_url, unavailable_asset,
)
from investalo_bitget.transport import ReadResponse
from investalo_trading.indicators import advance
from investalo_trading.models import IndicatorState
from investalo_trading.futures_signals import IndicatorParameters
from investalo_trading.timeframe_research import ResearchCandle

END = datetime(2026, 11, 24, 13, tzinfo=timezone.utc)
NOW = END + timedelta(minutes=1)
D = Decimal


def rows(end=END):
    return [[str(milliseconds(end - (WARM_BARS - i) * timedelta(hours=1))),
             str(1000-i), str(1001-i), str(999-i), str(1000-i), "2", "2000"]
            for i in range(WARM_BARS)]


def response(data=None, at=NOW):
    return ReadResponse(200, json.dumps(dict(code="00000", requestTime=milliseconds(at),
        data=rows() if data is None else data)).encode())


class DemoSignalTests(unittest.TestCase):
    def test_shared_wilder_matches_direct_core_zero_and_last_closed_hour(self):
        value = signal_asset(response(), "BTCUSDT", end=END, received_at=NOW)
        state = IndicatorState()
        for row in rows():
            opened = datetime.fromtimestamp(int(row[0])/1000, tz=timezone.utc)
            state = advance(state, ResearchCandle("BITGET:BTCUSDT", opened,
                opened+timedelta(hours=1), *map(D, row[1:5])), IndicatorParameters())
        self.assertEqual(D(value["rsi"]), state.rsi)
        self.assertEqual((value["rsi"], value["below_count"], value["entry_condition"]), ("0", 2, "confirmed"))
        self.assertEqual(value["candle_closed_at"], END.isoformat())

    def test_unfinished_row_ignored_and_response_order_not_indicator_order(self):
        unfinished = [str(milliseconds(END)), "100", "999999", "1", "999999", "1", "1"]
        regular = signal_asset(response(), "BTCUSDT", end=END, received_at=NOW)
        actual = signal_asset(response(list(reversed(rows()+[unfinished]))), "BTCUSDT",
                              end=END, received_at=NOW)
        self.assertEqual(actual, regular)

    def test_duplicate_gap_wrong_axis_invalid_ohlc_and_missing_latest_rejected(self):
        variants = []
        duplicate = rows(); duplicate[-1] = duplicate[-2]; variants.append(duplicate)
        gap = rows(); gap[-10][0] = str(milliseconds(END - timedelta(hours=400))); variants.append(gap)
        misaligned = rows(); misaligned[-1][0] = str(int(misaligned[-1][0])+1); variants.append(misaligned)
        prices = rows(); prices[-1][2] = "1"; variants.append(prices)
        missing = rows(); missing.pop(); variants.append(missing)
        stale = rows(END-timedelta(hours=1)); variants.append(stale)
        future = rows(); future[-1][0] = str(milliseconds(END+timedelta(hours=1))); variants.append(future)
        for data in variants:
            with self.subTest(case=data[-1]), self.assertRaises(ValueError):
                signal_asset(response(data), "BTCUSDT", end=END, received_at=NOW)

    def test_response_clock_and_foreign_symbol_fail(self):
        for at in (NOW-timedelta(seconds=6), NOW+timedelta(milliseconds=1)):
            with self.assertRaises(ValueError):
                signal_asset(response(at=at), "BTCUSDT", end=END, received_at=NOW)
        with self.assertRaises(ValueError):
            signal_asset(response(), "SBTCSUSDT", end=END, received_at=NOW)
        with self.assertRaises(ValueError):
            signal_asset(response(), "BTCUSDT", end=END, received_at=END+timedelta(hours=1))

    def test_flat_history_rsi50_and_exact_threshold_does_not_invent_under30(self):
        flat = rows()
        for row in flat: row[1:5] = ["100", "101", "99", "100"]
        value = signal_asset(response(flat), "BTCUSDT", end=END, received_at=NOW)
        self.assertEqual((value["rsi"], value["below_count"]), ("50", 0))
        # A mock isolates threshold comparison from Wilder's arithmetic.
        with patch("investalo_bitget.futures_demo_signals.advance",
                   return_value=IndicatorState(rsi=D("30"))):
            value = signal_asset(response(flat), "BTCUSDT", end=END, received_at=NOW)
            self.assertEqual((value["below_count"], value["entry_condition"]), (0, "waiting_rsi"))

    def test_one_fetch_per_closed_hour_preserves_source_time_and_renewal_next_hour(self):
        clock, calls = [NOW], []
        def fetch(symbol, end, *, timeout_seconds):
            calls.append((symbol, end))
            return response(rows(end), at=clock[0])
        monitor = DemoSignalMonitor(fetch=fetch, clock=lambda: clock[0])
        first = monitor()
        clock[0] += timedelta(minutes=10)
        cached = monitor()
        self.assertEqual(len(calls), 7)
        self.assertEqual(first["assets"], cached["assets"])
        self.assertNotEqual(first["observed_at"], cached["observed_at"])
        clock[0] += timedelta(hours=1)
        self.assertEqual(monitor()["assets"][0]["candle_closed_at"], boundary(clock[0]).isoformat())
        self.assertEqual(len(calls), 14)

    def test_failure_unknown_does_not_hide_good_assets_retry_only_failed(self):
        calls, failure, clock = [], [True], [NOW]
        def fetch(symbol, end, *, timeout_seconds):
            calls.append(symbol)
            if symbol == "AVAXUSDT" and failure[0]: raise ValueError("private upstream details")
            return response(at=clock[0])
        monitor = DemoSignalMonitor(fetch=fetch, clock=lambda: clock[0])
        first = monitor()
        self.assertEqual(first["assets"][0], unavailable_asset("AVAXUSDT"))
        self.assertTrue(all(a["status"] == "confirmed" for a in first["assets"][1:]))
        self.assertNotIn("private", json.dumps(first))
        failure[0] = False
        monitor()
        self.assertEqual(len(calls), 7)
        clock[0] += timedelta(seconds=31)
        self.assertEqual(monitor()["assets"][0]["status"], "confirmed")
        self.assertEqual(len(calls), 8)

    def test_limited_three_workers_singleflight_and_pid_guard(self):
        count, maximum, lock = [0], [0], threading.Lock()
        def fetch(symbol, end, *, timeout_seconds):
            with lock:
                count[0] += 1
                maximum[0] = max(maximum[0], count[0])
            time.sleep(.25)
            with lock: count[0] -= 1
            return response()
        monitor = DemoSignalMonitor(fetch=fetch, clock=lambda: NOW)
        thread = threading.Thread(target=monitor)
        thread.start()
        while not monitor.lock.locked(): time.sleep(.001)
        with self.assertRaises(ValueError): monitor()
        thread.join()
        self.assertLessEqual(maximum[0], 3)
        self.assertGreater(maximum[0], 1)
        monitor.pid = -1
        with self.assertRaises(ValueError): monitor()

    def test_fixed_public_requests_no_arbitrary_symbol_or_window(self):
        url = signal_url("BTCUSDT", END)
        self.assertIn("productType=USDT-FUTURES", url)
        self.assertIn("granularity=1H", url)
        self.assertIn("limit=301", url)
        self.assertNotIn("secret", url)
        for symbol, end in (("BNB&host=evil", END), ("BTCUSDT", NOW)):
            with self.assertRaises(ValueError): signal_url(symbol, end)
