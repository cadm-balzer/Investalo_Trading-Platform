import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from investalo_marketdata import (
    H4, InstrumentMetadata, SnapshotSource, dump_snapshot, load_snapshot,
    make_snapshot, synthetic_snapshot, window_snapshot,
)
from investalo_marketdata.__main__ import main
from investalo_trading import Candle


START = datetime(2020, 2, 28, tzinfo=timezone.utc)
RETRIEVED = datetime(2021, 1, 1, tzinfo=timezone.utc)
SOURCE = SnapshotSource("csv", "csv-v1", "https://example.test/history", RETRIEVED)
D = Decimal


def snapshot(*, bars=18, requested_start=None, requested_end=None, metadata=None):
    candles = tuple(
        Candle("BTC/USDT", START + index * H4, START + (index + 1) * H4,
               D("100"), D("102"), D("98"), D("100.123456789012345678"))
        for index in range(bars)
    )
    return make_snapshot(
        "BTC/USDT", candles, SOURCE, synthetic=False,
        requested_start=requested_start, requested_end=requested_end,
        instrument_metadata=metadata,
    )


class WindowTests(unittest.TestCase):
    def test_exact_values_source_retrieval_metadata_and_original_are_preserved(self):
        metadata = InstrumentMetadata(
            "BTCUSDT", D(".00000001"), D(".01"), D("5"), "historical",
            "https://example.test/instruments", START,
        )
        original = snapshot(metadata=metadata)
        original_bytes = dump_snapshot(original)
        result = window_snapshot(original, start=START + 3 * H4, end=START + 9 * H4)
        self.assertEqual(result.candles, original.candles[3:9])
        self.assertTrue(all(a is b for a, b in zip(result.candles, original.candles[3:9])))
        self.assertIs(result.source, original.source)
        self.assertIs(result.instrument_metadata, metadata)
        self.assertEqual(result.source.retrieved_at, RETRIEVED)
        self.assertEqual(result.candles[0].close, D("100.123456789012345678"))
        self.assertFalse(result.synthetic)
        self.assertEqual(dump_snapshot(original), original_bytes)
        self.assertNotEqual(result.data_digest, original.data_digest)

    def test_single_candle_window_uses_exclusive_end(self):
        original = snapshot()
        result = window_snapshot(original, start=START + H4, end=START + 2 * H4)
        self.assertEqual(result.candles, (original.candles[1],))
        self.assertEqual(result.coverage.requested_start, original.candles[1].open_time)
        self.assertEqual(result.coverage.requested_end, original.candles[1].close_time)
        self.assertTrue(result.coverage.complete)

    def test_whole_window_keeps_data_identity_and_adds_exact_coverage(self):
        original = snapshot()
        self.assertIsNone(original.coverage.complete)
        result = window_snapshot(original, start=START, end=START + 18 * H4)
        self.assertEqual(original.data_digest, result.data_digest)
        self.assertNotEqual(dump_snapshot(original), dump_snapshot(result))
        self.assertTrue(result.coverage.complete)
        self.assertEqual(result.coverage.record()["missing_leading_bars"], 0)
        self.assertEqual(result.coverage.record()["missing_trailing_bars"], 0)

    def test_adjacent_leap_day_windows_have_no_overlap_or_lost_bars(self):
        original = snapshot()
        leap_day = datetime(2020, 2, 29, tzinfo=timezone.utc)
        march = datetime(2020, 3, 1, tzinfo=timezone.utc)
        end = datetime(2020, 3, 2, tzinfo=timezone.utc)
        pieces = [
            window_snapshot(original, start=START, end=leap_day),
            window_snapshot(original, start=leap_day, end=march),
            window_snapshot(original, start=march, end=end),
        ]
        self.assertEqual([len(piece.candles) for piece in pieces], [6, 6, 6])
        self.assertEqual(tuple(bar for piece in pieces for bar in piece.candles), original.candles)
        self.assertEqual(len({bar.open_time for piece in pieces for bar in piece.candles}), 18)

    def test_four_year_h4_input_partitions_into_three_years_and_one_year(self):
        start = datetime(2022, 8, 1, tzinfo=timezone.utc)
        boundary = datetime(2025, 8, 1, tzinfo=timezone.utc)
        end = datetime(2026, 8, 1, tzinfo=timezone.utc)
        source = SnapshotSource("csv", "csv-v1", None,
                                datetime(2026, 9, 1, tzinfo=timezone.utc))
        bars = (end - start) // H4
        self.assertEqual(bars, 8766)
        original = make_snapshot(
            "ETH/USDT",
            tuple(Candle("ETH/USDT", start + index * H4, start + (index + 1) * H4,
                         D("100"), D("102"), D("98"), D("101"))
                  for index in range(bars)),
            source, synthetic=False, requested_start=start, requested_end=end,
        )
        research = window_snapshot(original, start=start, end=boundary)
        reserved = window_snapshot(original, start=boundary, end=end)
        self.assertEqual(len(research.candles), 6576)
        self.assertEqual(len(reserved.candles), 2190)
        self.assertEqual(research.candles + reserved.candles, original.candles)
        self.assertEqual(research.candles[-1].close_time, reserved.candles[0].open_time)
        self.assertEqual(research.symbol, "ETH/USDT")

    def test_window_outside_available_history_is_rejected_instead_of_clipped(self):
        original = snapshot()
        for start, end in (
            (START - H4, START + H4),
            (START + 17 * H4, START + 19 * H4),
            (START - H4, START + 19 * H4),
            (START + 20 * H4, START + 21 * H4),
        ):
            with self.subTest(start=start, end=end), self.assertRaisesRegex(ValueError, "not fully covered"):
                window_snapshot(original, start=start, end=end)

    def test_incomplete_parent_only_permits_a_fully_available_child_window(self):
        original = snapshot(requested_start=START - H4, requested_end=START + 20 * H4)
        self.assertFalse(original.coverage.complete)
        with self.assertRaisesRegex(ValueError, "not fully covered"):
            window_snapshot(original, start=START - H4, end=START + 20 * H4)
        result = window_snapshot(original, start=START, end=START + 18 * H4)
        self.assertTrue(result.coverage.complete)
        self.assertEqual(result.coverage.requested_start, START)
        self.assertFalse(original.coverage.complete)

    def test_empty_and_reversed_windows_rejected(self):
        for start, end in ((START, START), (START + H4, START)):
            with self.subTest(start=start, end=end), self.assertRaisesRegex(ValueError, "at least one"):
                window_snapshot(snapshot(), start=start, end=end)

    def test_off_grid_start_or_end_rejected_without_rounding(self):
        for start, end in (
            (START + timedelta(hours=1), START + H4),
            (START, START + H4 + timedelta(microseconds=1)),
            (START + timedelta(minutes=1), START + 2 * H4),
        ):
            with self.subTest(start=start, end=end), self.assertRaisesRegex(ValueError, "UTC H4"):
                window_snapshot(snapshot(), start=start, end=end)

    def test_naive_non_utc_and_wrong_boundary_types_rejected(self):
        values = [
            START.replace(tzinfo=None),
            START.astimezone(timezone(timedelta(hours=1))),
            "2020-02-28T00:00:00Z",
            None,
        ]
        for value in values:
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "explicit UTC"):
                window_snapshot(snapshot(), start=value, end=START + H4)
            with self.subTest(end=value), self.assertRaisesRegex(ValueError, "explicit UTC"):
                window_snapshot(snapshot(), start=START, end=value)

    def test_window_remains_roundtrip_canonical_and_digest_bound(self):
        result = window_snapshot(snapshot(), start=START + H4, end=START + 10 * H4)
        encoded = dump_snapshot(result)
        self.assertEqual(load_snapshot(encoded), result)
        self.assertEqual(dump_snapshot(load_snapshot(encoded)), encoded)
        changed = json.loads(encoded)
        changed["candles"][0]["close"] = "99"
        with self.assertRaisesRegex(ValueError, "digest"):
            load_snapshot(json.dumps(changed))

    def test_synthetic_source_and_truthful_label_are_never_promoted(self):
        original = synthetic_snapshot("BTC/USDT", bars=24, start=START, retrieved_at=RETRIEVED)
        result = window_snapshot(original, start=START + H4, end=START + 10 * H4)
        self.assertTrue(result.synthetic)
        self.assertEqual(result.source.venue, "synthetic")
        self.assertEqual(result.source.api_version, "fixture-v1")
        self.assertIsNone(result.source.url)

    def test_non_snapshot_input_rejected(self):
        for value in (None, {}, (), "snapshot"):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "immutable snapshot"):
                window_snapshot(value, start=START, end=START + H4)

    def test_cli_creates_valid_window_once_without_overwriting_source_or_output(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "original.json"
            output = Path(directory) / "window.json"
            original_bytes = dump_snapshot(snapshot()) + "\n"
            source.write_text(original_bytes)
            arguments = ["window", str(source), "--start", "2020-02-28T04:00:00Z",
                         "--end", "2020-02-29T00:00:00Z", "--output", str(output)]
            out = io.StringIO()
            with redirect_stdout(out), redirect_stderr(io.StringIO()):
                self.assertEqual(main(arguments), 0)
            self.assertEqual(json.loads(out.getvalue())["bar_count"], 5)
            emitted_bytes = output.read_bytes()
            self.assertEqual(len(load_snapshot(emitted_bytes).candles), 5)
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(main(arguments), 2)
            self.assertEqual(output.read_bytes(), emitted_bytes)
            self.assertEqual(source.read_text(), original_bytes)

    def test_cli_rejects_shortfall_without_creating_output_or_echoing_paths(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "private-source-canary.json"
            output = Path(directory) / "private-output-canary.json"
            source.write_text(dump_snapshot(snapshot()))
            stderr = io.StringIO()
            with redirect_stdout(io.StringIO()), redirect_stderr(stderr):
                code = main(["window", str(source), "--start", "2020-02-27T20:00:00Z",
                             "--end", "2020-02-29T00:00:00Z", "--output", str(output)])
            self.assertEqual(code, 2)
            self.assertFalse(output.exists())
            self.assertEqual(json.loads(stderr.getvalue()), {
                "error": "snapshot_rejected", "stage": "window",
                "code": "WINDOW_NOT_COVERED", "validation_claim": False,
            })
            self.assertNotIn("private-source-canary", stderr.getvalue())
            self.assertNotIn("private-output-canary", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
