import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import parse_qs, urlsplit

from investalo_trading import Candle, PaperSimulator
from investalo_marketdata import (
    BITGET_URL, DatasetSnapshot, H4, HistoryCoverage, InstrumentMetadata, MAX_BARS,
    SnapshotSource, BitgetHistoryAdapter, dump_snapshot, import_csv, load_snapshot,
    make_snapshot, synthetic_snapshot, to_trading_candles,
)
from investalo_marketdata.__main__ import failure_code, main
from investalo_marketdata.snapshot import decimal_string, parse_time, price

D = Decimal
START = datetime(2020, 1, 1, tzinfo=timezone.utc)
RETRIEVED = datetime(2021, 1, 1, tzinfo=timezone.utc)
SOURCE = SnapshotSource("csv", "csv-v1", None, RETRIEVED)


def bar(index=0, symbol="BTC/USDT", close="100.123456789012345678"):
    return Candle(symbol, START + index * H4, START + (index + 1) * H4,
                  D("100"), D("102"), D("98"), D(close))


def snapshot(rows=None, source=SOURCE, **kwargs):
    return make_snapshot("BTC/USDT", tuple(rows if rows is not None else (bar(0), bar(1))),
                         source, synthetic=False, **kwargs)


def response(rows):
    return {"code": "00000", "data": rows, "msg": "success"}


def venue_row(index, close="100.123456789012345678"):
    stamp = int((START + index * H4).timestamp()) * 1000
    return [str(stamp), "100", "102", "98", close, "0.1", "10"]


class SnapshotTests(unittest.TestCase):
    def test_canonical_roundtrip_preserves_decimal_precision_and_frozen_records(self):
        original = snapshot()
        text = dump_snapshot(original)
        restored = load_snapshot(text)
        self.assertEqual(original, restored)
        self.assertEqual(text, dump_snapshot(restored))
        self.assertIn('"100.123456789012345678"', text)
        self.assertEqual(restored.candles[0].close, D("100.123456789012345678"))
        with self.assertRaises(FrozenInstanceError):
            restored.synthetic = True

    def test_digest_ignores_retrieval_time_and_requested_coverage_but_tracks_provenance(self):
        original = snapshot()
        later = snapshot(source=replace(SOURCE, retrieved_at=RETRIEVED + timedelta(days=1)),
                         requested_start=START - H4, requested_end=START + 3 * H4)
        self.assertEqual(original.data_digest, later.data_digest)
        self.assertNotEqual(dump_snapshot(original), dump_snapshot(later))
        changed = replace(original, synthetic=True)
        self.assertNotEqual(original.data_digest, changed.data_digest)
        changed_price = snapshot((bar(0, close="99"), bar(1)))
        self.assertNotEqual(original.data_digest, changed_price.data_digest)

    def test_digest_tamper_unknown_fields_and_duplicate_members_rejected(self):
        raw = json.loads(dump_snapshot(snapshot()))
        raw["candles"][0]["close"] = "99"
        with self.assertRaisesRegex(ValueError, "digest"):
            load_snapshot(json.dumps(raw))
        raw = json.loads(dump_snapshot(snapshot()))
        raw["secret"] = "ignored-input-must-not-pass"
        with self.assertRaises(ValueError):
            load_snapshot(json.dumps(raw))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            load_snapshot('{"symbol":"BTC/USDT","symbol":"ETH/USDT"}')

    def test_prices_reject_numbers_nonfinite_unbounded_precision_and_positive_failures(self):
        for invalid in (1.1, 1, True, "NaN", "Infinity", "-1", "0", "1e999",
                        "1e-25", "1e25", "1." + "1" * 37, "1" * 100):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                price(invalid)
        self.assertEqual(decimal_string(D("100.12000")), "100.12")
        self.assertEqual(decimal_string(D("1e-8")), "0.00000001")

    def test_future_unclosed_and_non_utc_boundaries_rejected(self):
        source = replace(SOURCE, retrieved_at=START + H4 - timedelta(microseconds=1))
        with self.assertRaisesRegex(ValueError, "unclosed"):
            snapshot((bar(),), source=source)
        with self.assertRaisesRegex(ValueError, "future"):
            snapshot(source=replace(SOURCE, retrieved_at=datetime.now(timezone.utc) + timedelta(days=1)))
        for stamp in ("2020-01-01T00:00:00", "2020-01-01T00:00:00+01:00",
                      "2020-01-01T01:00:00Z", "2020-01-01T00:00:00.000000001Z"):
            with self.assertRaises(ValueError):
                parse_time(stamp, aligned=True)

    def test_no_sorting_duplicate_or_gap_interpolation_in_snapshot_boundary(self):
        for rows in ((bar(1), bar(0)), (bar(0), bar(0)), (bar(0), bar(2))):
            with self.assertRaises(ValueError):
                snapshot(rows)
        with self.assertRaisesRegex(ValueError, "symbol"):
            snapshot((bar(symbol="ETH/USDT"),))

    def test_ohlc_contradictions_and_empty_or_oversized_inputs_rejected(self):
        with self.assertRaises(ValueError):
            Candle("BTC/USDT", START, START + H4, D("100"), D("99"), D("98"), D("100"))
        with self.assertRaises(ValueError):
            snapshot(())
        with self.assertRaises(ValueError):
            replace(snapshot(), candles=(bar(),) * (MAX_BARS + 1))
        with self.assertRaises(ValueError):
            load_snapshot(" " * (16 * 1024 * 1024 + 1))

    def test_history_shortfall_is_explicit_and_not_validation_evidence(self):
        result = snapshot(requested_start=START - 2 * H4, requested_end=START + 3 * H4)
        self.assertFalse(result.coverage.complete)
        self.assertEqual(result.coverage.record()["missing_leading_bars"], 2)
        self.assertEqual(result.coverage.record()["missing_trailing_bars"], 1)
        self.assertIsNone(snapshot().coverage.complete)
        self.assertTrue(snapshot(requested_start=START, requested_end=START + 2 * H4).coverage.complete)
        raw = json.loads(dump_snapshot(result))
        raw["coverage"]["complete"] = True
        with self.assertRaises(ValueError):
            load_snapshot(json.dumps(raw))
        raw["coverage"]["complete"] = 0
        with self.assertRaises(ValueError):
            load_snapshot(json.dumps(raw))

    def test_instrument_metadata_is_provenanced_not_implicitly_used_as_historical_rules(self):
        metadata = InstrumentMetadata("BTCUSDT", D(".01"), D(".001"), D("5"), "current",
                                      "https://api.bitget.com/api/v3/market/instruments", START)
        original = snapshot(instrument_metadata=metadata)
        self.assertEqual(load_snapshot(dump_snapshot(original)), original)
        self.assertNotEqual(original.data_digest, snapshot().data_digest)
        self.assertEqual(PaperSimulator().engine.rules("BTCUSDT").quantity_step, D(".00000001"))
        with self.assertRaises(ValueError):
            replace(metadata, quantity_step=.01)
        with self.assertRaises(ValueError):
            snapshot(instrument_metadata=replace(metadata, venue_symbol="ETHUSDT"))

    def test_source_disallows_credentials_queries_unsupported_and_false_synthetic(self):
        for url in ("http://source.test/a", "https://user:pass@source.test/a",
                    "https://source.test/a?token=secret", "https://source.test/a#fragment"):
            with self.assertRaises(ValueError):
                replace(SOURCE, url=url)
        with self.assertRaises(ValueError):
            SnapshotSource("binance", "3", None, RETRIEVED)
        with self.assertRaises(ValueError):
            replace(snapshot(), source=SnapshotSource("synthetic", "fixture-v1", None, RETRIEVED))

    def test_csv_precision_provenance_and_required_closed_order(self):
        text = "symbol,open_time,close_time,open,high,low,close\n"
        for index in (0, 1):
            item = bar(index)
            text += ",".join((item.symbol, item.open_time.isoformat(), item.close_time.isoformat(),
                              "100", "102", "98", "100.123456789012345678")) + "\n"
        result = import_csv(text, symbol="BTC/USDT", source=SOURCE, synthetic=False)
        self.assertEqual(result, snapshot())
        self.assertEqual(result.source.venue, "csv")
        with self.assertRaises(ValueError):
            import_csv(text.replace("symbol,", "symbol,symbol,", 1), symbol="BTC/USDT",
                       source=SOURCE, synthetic=False)
        with self.assertRaises(ValueError):
            import_csv(text.replace("100.123456789012345678", "NaN"), symbol="BTC/USDT",
                       source=SOURCE, synthetic=False)

    def test_synthetic_runs_real_simulator_but_is_always_labelled_and_causal(self):
        fixture = synthetic_snapshot("BTC/USDT", bars=150, retrieved_at=RETRIEVED)
        self.assertTrue(fixture.synthetic)
        self.assertEqual(fixture.source.venue, "synthetic")
        self.assertIsNone(fixture.source.url)
        core = to_trading_candles(fixture)
        self.assertEqual(core[0].symbol, "BTCUSDT")
        self.assertEqual(core[0].close, fixture.candles[0].close)
        simulator = PaperSimulator()
        short = simulator.run(core[:70])
        full = simulator.run(core)
        # The next open shares the previous close's timestamp but is a later
        # observed event. Prefix comparison preserves that event ordering.
        self.assertEqual(short.equity_curve, full.equity_curve[:len(short.equity_curve)])
        self.assertEqual(short.fills, full.fills[:len(short.fills)])
        self.assertFalse(full.manual_fills_fabricated)
        self.assertEqual(fixture.data_digest,
                         synthetic_snapshot("BTC/USDT", bars=150,
                                            retrieved_at=RETRIEVED + timedelta(days=1)).data_digest)

    def test_cli_create_only_and_explicit_synthetic_label(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / "fixture.json"
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(main(["synthetic", "--symbol", "BTC/USDT", "--bars", "30",
                                       "--output", str(output)]), 0)
                self.assertEqual(main(["validate", str(output)]), 0)
                self.assertEqual(main(["synthetic", "--symbol", "BTC/USDT", "--output", str(output)]), 2)
            self.assertTrue(load_snapshot(output.read_bytes()).synthetic)

    def test_cli_diagnostics_are_static_without_raw_rows_paths_or_transport_urls(self):
        from urllib.error import URLError
        self.assertEqual(failure_code(ValueError("Bitget returned future/nonprogressing candles")),
                         "PROVIDER_FUTURE_OR_NONPROGRESS")
        self.assertEqual(failure_code(ValueError("secret-unknown-exception")), "INVALID_DATA")
        self.assertEqual(failure_code(URLError("https://user:secret@internal/")), "TRANSPORT_NETWORK_OR_TLS")
        self.assertEqual(failure_code(FileExistsError("/private/secret-file")), "OUTPUT_EXISTS")


class BitgetTests(unittest.TestCase):
    def adapter(self, pages):
        calls = []
        def fetch(url):
            calls.append(parse_qs(urlsplit(url).query))
            return response(pages.pop(0))
        return BitgetHistoryAdapter(fetch_json=fetch, sleep=lambda _: None), calls

    def test_closed_utc_h4_pagination_and_full_decimal_strings(self):
        adapter, calls = self.adapter([
            [venue_row(index) for index in range(104, 4, -1)],
            [venue_row(index) for index in range(4, -1, -1)],
        ])
        result = adapter.fetch_history("BTC/USDT", start=START, end=START + 105 * H4,
                                       retrieved_at=RETRIEVED)
        self.assertEqual(len(result.candles), 105)
        self.assertTrue(result.coverage.complete)
        self.assertEqual(result.candles[-1].close, D("100.123456789012345678"))
        self.assertEqual(calls[0]["category"], ["SPOT"])
        self.assertEqual(calls[0]["interval"], ["4H"])
        self.assertEqual(calls[0]["symbol"], ["BTCUSDT"])
        self.assertEqual(calls[0]["limit"], ["100"])
        self.assertEqual(int(calls[1]["endTime"][0]),
                         int((START + 5 * H4).timestamp()) * 1000)
        for request in calls:
            self.assertLess(int(request["endTime"][0]) - int(request["startTime"][0]),
                            90 * 86_400_000)

    def test_verified_v3_flooring_uses_exact_boundaries_to_avoid_page_gaps(self):
        # Public probe 2026-11-07:
        # endTime=1794038399999 -> last bar 00:00 UTC (too early);
        # endTime=1794038400000 -> last bar 04:00 UTC (correct before 08:00).
        # Reproduce that documented interval-flooring shape across two pages.
        epoch_ms = int(START.timestamp()) * 1000
        h4_ms = 4 * 60 * 60 * 1000
        calls = []
        def flooring_provider(url):
            query = parse_qs(urlsplit(url).query)
            end_ms = int(query["endTime"][0])
            first = int(query["startTime"][0])
            calls.append(query)
            end_index = (end_ms - epoch_ms) // h4_ms
            indices = range(max(0, end_index - 100), end_index)
            return response([venue_row(i) for i in indices
                             if int(venue_row(i)[0]) >= first])
        adapter = BitgetHistoryAdapter(fetch_json=flooring_provider, sleep=lambda _: None)
        result = adapter.fetch_history("BTC/USDT", start=START, end=START + 105 * H4,
                                       retrieved_at=RETRIEVED)
        self.assertTrue(result.coverage.complete)
        self.assertEqual(len(result.candles), 105)
        self.assertEqual(len(calls), 2)
        self.assertEqual(int(calls[0]["endTime"][0]) % h4_ms, 0)
        self.assertEqual(int(calls[1]["endTime"][0]) % h4_ms, 0)

    def test_one_extra_old_rounding_interval_is_filtered_only_at_requested_boundary(self):
        adapter, _ = self.adapter([[venue_row(i) for i in range(-1, 3)]])
        result = adapter.fetch_history("BTC/USDT", start=START, end=START + 3 * H4,
                                       retrieved_at=RETRIEVED)
        self.assertEqual(len(result.candles), 3)
        self.assertTrue(result.coverage.complete)

    def test_empty_older_history_records_boundary_shortfall(self):
        adapter, _ = self.adapter([[venue_row(2), venue_row(3)], []])
        result = adapter.fetch_history("BTC/USDT", start=START, end=START + 5 * H4,
                                       retrieved_at=RETRIEVED)
        self.assertFalse(result.coverage.complete)
        self.assertEqual(result.coverage.record()["missing_leading_bars"], 2)
        self.assertEqual(result.coverage.record()["missing_trailing_bars"], 1)
        self.assertFalse(result.synthetic)

    def test_api_failures_no_history_nonprogress_duplicate_and_gap_rejected(self):
        for pages in (
            [[]],
            [[venue_row(3)]],
            [[venue_row(0), venue_row(0)]],
            [[venue_row(0), venue_row(2)]],
        ):
            adapter, _ = self.adapter(pages)
            with self.assertRaises(ValueError):
                adapter.fetch_history("BTC/USDT", start=START, end=START + 3 * H4,
                                      retrieved_at=RETRIEVED)
        adapter = BitgetHistoryAdapter(fetch_json=lambda _: {"code": "40000", "data": []})
        with self.assertRaises(ValueError):
            adapter.fetch_history("BTC/USDT", start=START, end=START + H4, retrieved_at=RETRIEVED)

    def test_future_window_and_number_prices_fail_before_snapshot(self):
        adapter, calls = self.adapter([])
        with self.assertRaises(ValueError):
            adapter.fetch_history("BTC/USDT", start=START, end=RETRIEVED + H4, retrieved_at=RETRIEVED)
        self.assertEqual(calls, [])
        row = venue_row(0)
        row[1] = 100.0
        adapter, _ = self.adapter([[row]])
        with self.assertRaises(ValueError):
            adapter.fetch_history("BTC/USDT", start=START, end=START + H4, retrieved_at=RETRIEVED)


if __name__ == "__main__":
    unittest.main()
