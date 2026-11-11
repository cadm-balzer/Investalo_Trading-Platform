"""Frozen protocol, create-only artifacts and failure semantics of the actual CLI."""
import hashlib
import importlib.util
import io
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import parse_qs, urlsplit
import unittest
from unittest.mock import patch

from investalo_marketdata.binance_futures import load_binance_snapshot
from investalo_marketdata.bitget import EPOCH, milliseconds
from investalo_marketdata.snapshot import canonical, decode_json, iso

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("binance_import", ROOT / "infra/scripts/import-binance-futures-history.py")
SCRIPT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SCRIPT)


class BinanceImportTests(unittest.TestCase):
    def test_frozen_protocol_hash_matches(self):
        raw = (ROOT / "docs/research-protocols/binance-futures-history-20261111.json").read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), SCRIPT.PROTOCOL_SHA256)
        self.assertEqual(decode_json(raw)["expected_h4_bars_per_stream"], 6576)

    def test_changed_protocol_fails_before_output_or_network(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / "new"
            with patch.object(SCRIPT.sys, "argv", ["import", str(output)]), \
                    patch.object(Path, "read_bytes", return_value=b"{}"), \
                    patch.object(SCRIPT, "fetch_binance_json") as fetch, \
                    self.assertRaisesRegex(ValueError, "protocol changed"):
                SCRIPT.main()
            fetch.assert_not_called()
            self.assertFalse(output.exists())

    def test_existing_output_is_not_changed(self):
        with TemporaryDirectory() as directory:
            marker = Path(directory) / "marker"
            marker.write_text("keep")
            with patch.object(SCRIPT.sys, "argv", ["import", directory]), \
                    patch.object(SCRIPT, "fetch_binance_json") as fetch, \
                    self.assertRaises(FileExistsError):
                SCRIPT.main()
            fetch.assert_not_called()
            self.assertEqual(marker.read_text(), "keep")

    def test_failed_fetch_leaves_no_success_receipt_and_never_retries(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / "new"
            with patch.object(SCRIPT.sys, "argv", ["import", str(output)]), \
                    patch.object(SCRIPT, "fetch_binance_json", side_effect=TimeoutError) as fetch, \
                    self.assertRaises(TimeoutError):
                SCRIPT.main()
            self.assertEqual(fetch.call_count, 1)
            self.assertFalse((output / "receipt.json").exists())

    def test_complete_artifacts_have_exact_venue_and_honest_readiness(self):
        start = datetime(2022, 8, 1, tzinfo=timezone.utc)
        end = start + timedelta(hours=8)
        raw = canonical({"symbols": ["BTCUSDT", "ETHUSDT"], "price_kinds": ["trade", "mark", "index"],
                         "start": iso(start), "end_exclusive": iso(end),
                         "expected_h4_bars_per_stream": 2}).encode()
        funding_calls = set()
        def fetch(url):
            query = parse_qs(urlsplit(url).query)
            if "/fundingRate?" in url:
                symbol = query["symbol"][0]
                if symbol in funding_calls:
                    return []
                funding_calls.add(symbol)
                return [{"symbol": symbol, "fundingTime": milliseconds(start) + 10,
                         "fundingRate": "-0.0001", "markPrice": ""}]
            at = EPOCH + timedelta(milliseconds=int(query["startTime"][0]))
            return [[milliseconds(at + timedelta(hours=4 * i)), "100", "110", "90", "100", "0",
                     milliseconds(at + timedelta(hours=4 * (i + 1))) - 1, "0", 1, "0", "0", "0"]
                    for i in range(2)]
        with TemporaryDirectory() as directory:
            output = Path(directory) / "new"
            with patch.object(SCRIPT.sys, "argv", ["import", str(output)]), \
                    patch.object(Path, "read_bytes", return_value=raw), \
                    patch.object(SCRIPT, "PROTOCOL_SHA256", hashlib.sha256(raw).hexdigest()), \
                    patch.object(SCRIPT, "fetch_binance_json", side_effect=fetch), redirect_stdout(io.StringIO()):
                SCRIPT.main()
            receipt = decode_json((output / "receipt.json").read_text())
            self.assertEqual(len(receipt["streams"]), 8)
            self.assertTrue(receipt["all_price_windows_complete"])
            self.assertTrue(receipt["all_funding_windows_match_declared_buckets"])
            for key in ("net_backtest_ready", "historical_schedule_verified", "performance_evaluated",
                        "holdout_requested", "execution_enabled", "historical_fee_and_maintenance_rules_verified"):
                self.assertFalse(receipt[key])
            for stream in receipt["streams"]:
                text = (output / stream["file"]).read_text()
                self.assertEqual(hashlib.sha256(text.encode()).hexdigest(), stream["file_sha256"])
                self.assertEqual(load_binance_snapshot(text).data_digest, stream["data_digest"])


if __name__ == "__main__":
    unittest.main()
