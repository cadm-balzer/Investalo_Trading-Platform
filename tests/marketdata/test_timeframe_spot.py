from datetime import datetime, timedelta, timezone
import json
from urllib.parse import parse_qs, urlsplit
import unittest

from investalo_marketdata.bitget import milliseconds
from investalo_marketdata.timeframe_spot import (
    KNOWN_MISSING, URL, fetch_history, fetch_json, load_history, request_url, sha,
)

AT = datetime(2022, 8, 1, tzinfo=timezone.utc)


def fixture(url):
    query = parse_qs(urlsplit(url).query)
    start, end = int(query["startTime"][0]), int(query["endTime"][0])
    return [[stamp, "100", "102", "99", "101", "5", stamp + 3599999,
             "500", 8, "2", "200", "0"]
            for stamp in range(start, end + 1, 3600000)]


class HourlySourceTests(unittest.TestCase):
    def test_native_hourly_roundtrip_and_exact_two_page_coverage(self):
        calls, delays = [], []
        def fetch(url):
            calls.append(url)
            return fixture(url)
        snapshot, pages = fetch_history("BTCUSDT", AT, AT + timedelta(hours=1004), fetch, delays.append)
        restored, bars = load_history(json.dumps(snapshot))
        self.assertEqual(restored, snapshot)
        self.assertEqual(len(bars), 1004)
        self.assertEqual([p["rows"] for p in pages], [1000, 4])
        self.assertEqual(len(calls), 2)
        self.assertEqual(delays, [0.1])
        self.assertEqual(bars[-1].close_time, AT + timedelta(hours=1004))

    def test_page_gap_duplicate_extra_and_bad_close_are_rejected(self):
        for mode in ("gap", "duplicate", "extra", "close", "price"):
            def fetch(url):
                payload = fixture(url)
                if mode == "gap":
                    payload.pop()
                elif mode == "duplicate":
                    payload[1] = payload[0]
                elif mode == "extra":
                    payload.append(payload[-1])
                elif mode == "close":
                    payload[0][6] += 1
                else:
                    payload[0][1] = "NaN"
                return payload
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                fetch_history("BTCUSDT", AT, AT + timedelta(hours=4), fetch)

    def test_identity_tamper_and_unknown_fields_rejected_even_with_new_digest(self):
        snapshot, _ = fetch_history("BTCUSDT", AT, AT + timedelta(hours=4), fixture)
        for key, value in (("venue", "bitget"), ("market", "futures"), ("timeframe", "4h"),
                           ("symbol", "ETHUSDT"), ("url", "https://example.com")):
            altered = {**snapshot, key: value}
            altered["data_digest"] = sha({k: v for k, v in altered.items()
                                          if k not in ("retrieved_at", "data_digest")})
            with self.subTest(key=key), self.assertRaises(ValueError):
                load_history(json.dumps(altered))
        with self.assertRaises(ValueError):
            load_history(json.dumps({**snapshot, "extra": True}))

    def test_bounded_canonical_url_rejects_credentials_redirect_hosts_and_extra_query(self):
        good = request_url("BTCUSDT", AT, AT + timedelta(hours=4))
        self.assertTrue(good.startswith(URL))
        for bad in (good + "&apiKey=secret", good + "#fragment",
                    good.replace("data-api.binance.vision", "example.com"),
                    good.replace("interval=1h", "interval=4h"),
                    good.replace("https://", "https://user:password@")):
            with self.subTest(url=bad), self.assertRaises(ValueError):
                fetch_json(bad)
        for symbol, start, end in (
            ("XMRUSDT", AT, AT + timedelta(hours=1)),
            ("BTCUSDT", AT, AT + timedelta(hours=1001)),
            ("BTCUSDT", AT + timedelta(minutes=1), AT + timedelta(hours=1)),
        ):
            with self.assertRaises(ValueError):
                request_url(symbol, start, end)

    def test_retrieved_before_window_and_modified_price_rejected(self):
        snapshot, _ = fetch_history("BTCUSDT", AT, AT + timedelta(hours=4), fixture)
        with self.assertRaises(ValueError):
            load_history(json.dumps({**snapshot, "retrieved_at": "2022-08-01T00:00:00Z"}))
        snapshot["candles"][0]["close"] = "100"
        with self.assertRaises(ValueError):
            load_history(json.dumps(snapshot))

    def test_only_prespecified_missing_hour_is_disclosed_without_price_repair(self):
        start = KNOWN_MISSING - timedelta(hours=1)
        end = KNOWN_MISSING + timedelta(hours=2)
        def actual_gap(url):
            rows = [row for row in fixture(url) if row[0] != milliseconds(KNOWN_MISSING)]
            rows[0][6] = milliseconds(KNOWN_MISSING - timedelta(hours=1)) + 2381451
            return rows
        snapshot, _ = fetch_history("BTCUSDT", start, end, actual_gap)
        _, restored = load_history(json.dumps(snapshot))
        self.assertEqual(len(restored), 2)
        self.assertNotIn(KNOWN_MISSING, [b.open_time for b in restored])
        self.assertEqual(snapshot["missing_intervals"], ["2023-03-24T13:00:00Z"])
        self.assertEqual(snapshot["irregular_native_closes"][0]["native_close_ms"], 1679661581451)
        with self.assertRaises(ValueError):
            fetch_history("BTCUSDT", start, end, fixture)


if __name__ == "__main__":
    unittest.main()
