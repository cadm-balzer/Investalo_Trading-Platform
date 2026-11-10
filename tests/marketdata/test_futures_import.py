"""Operational acceptance: failed fetches never publish a successful receipt."""
import importlib.util
import io
from contextlib import redirect_stdout
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from investalo_trading import Candle
from investalo_marketdata.futures_snapshot import (
    FuturesSource, candle_symbol, load_futures_snapshot, make_futures_snapshot,
)
from investalo_marketdata.snapshot import H4, decode_json

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "futures_import", ROOT / "infra/scripts/import-futures-history.py")
SCRIPT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SCRIPT)


class FuturesImportTests(unittest.TestCase):
    def test_existing_directory_is_never_overwritten_or_fetched(self):
        with TemporaryDirectory() as directory:
            marker = Path(directory) / "existing.json"
            marker.write_text("preserved", encoding="utf-8")
            with patch.object(SCRIPT.sys, "argv", ["import", directory]), \
                    patch.object(SCRIPT, "fetch_futures_json") as fetch, \
                    self.assertRaises(FileExistsError):
                SCRIPT.main()
            fetch.assert_not_called()
            self.assertEqual(marker.read_text(), "preserved")

    def test_failed_transport_has_no_retry_or_success_receipt(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / "new"
            with patch.object(SCRIPT.sys, "argv", ["import", str(output)]), \
                    patch.object(SCRIPT, "fetch_futures_json", side_effect=TimeoutError) as fetch, \
                    self.assertRaises(TimeoutError):
                SCRIPT.main()
            self.assertEqual(fetch.call_count, 1)
            self.assertFalse((output / "receipt.json").exists())

    def test_partial_availability_records_six_distinct_price_streams_without_complete_claim(self):
        started = datetime(2022, 8, 1, tzinfo=timezone.utc)

        class ShortHistory:
            def __init__(self, fetch):
                pass

            def fetch_history(self, symbol, kind, *, start, end, retrieved_at):
                bar = Candle(candle_symbol(symbol, kind), started, started + H4,
                             *(Decimal(v) for v in ("100", "102", "98", "101")))
                return make_futures_snapshot(
                    symbol, kind, (bar,), FuturesSource(kind, retrieved_at),
                    requested_start=start, requested_end=end,
                )

        with TemporaryDirectory() as directory:
            output = Path(directory) / "new"
            with patch.object(SCRIPT.sys, "argv", ["import", str(output)]), \
                    patch.object(SCRIPT, "BitgetFuturesHistoryAdapter", ShortHistory), \
                    redirect_stdout(io.StringIO()):
                SCRIPT.main()
            receipt = decode_json((output / "receipt.json").read_bytes())
            self.assertFalse(receipt["all_requested_streams_complete"])
            self.assertFalse(receipt["funding_imported"])
            self.assertFalse(receipt["performance_evaluated"])
            self.assertFalse(receipt["holdout_requested"])
            self.assertEqual(len(receipt["streams"]), 6)
            digests = set()
            for stream in receipt["streams"]:
                restored = load_futures_snapshot((output / stream["file"]).read_bytes())
                digests.add(restored.data_digest)
                self.assertEqual(restored.data_digest, stream["data_digest"])
                self.assertFalse(restored.coverage.complete)
            self.assertEqual(len(digests), 6)
