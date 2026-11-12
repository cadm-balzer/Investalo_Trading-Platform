"""Frozen source CLI, saved readback, create-only and no-success-on-error."""
import hashlib
import importlib.util
import io
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import parse_qs, urlsplit
import unittest
from unittest.mock import patch

from investalo_marketdata.binance_futures_hourly import H1, load_hourly_snapshot
from investalo_marketdata.bitget import EPOCH, milliseconds
from investalo_marketdata.snapshot import canonical, decode_json, iso
from test_binance_futures import START
from test_binance_futures_hourly import kline

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("hourly_import", ROOT / "infra/scripts/import-futures-h1-history.py")
SCRIPT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SCRIPT)


class HourlyImportTests(unittest.TestCase):
    def test_frozen_protocol_hash_symbols_research_window_and_count_match(self):
        raw = (ROOT / "docs/research-protocols/futures-h1-history-20261112.json").read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), SCRIPT.PROTOCOL_SHA256)
        protocol = decode_json(raw)
        self.assertEqual(protocol["expected_h1_bars_per_stream"], 26304)
        self.assertEqual(len(protocol["symbols"]), 5)
        self.assertEqual(protocol["end_exclusive"], "2025-08-01T00:00:00Z")
        self.assertFalse(protocol["holdout_requested"])

    def test_protocol_tampering_fails_before_output_or_network(self):
        with TemporaryDirectory() as directory, \
                patch.object(SCRIPT.sys, "argv", ["import", str(Path(directory) / "new")]), \
                patch.object(Path, "read_bytes", return_value=b"{}"), \
                patch.object(SCRIPT, "fetch_hourly_json") as fetch, \
                self.assertRaisesRegex(ValueError, "protocol changed"):
            SCRIPT.main()
        fetch.assert_not_called()

    def test_existing_output_is_preserved_before_network(self):
        with TemporaryDirectory() as directory:
            marker = Path(directory) / "keep"
            marker.write_text("keep")
            with patch.object(SCRIPT.sys, "argv", ["import", directory]), \
                    patch.object(SCRIPT, "fetch_hourly_json") as fetch, \
                    self.assertRaises(FileExistsError):
                SCRIPT.main()
            fetch.assert_not_called()
            self.assertEqual(marker.read_text(), "keep")

    def test_timeout_never_retries_or_leaves_success_receipt(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / "new"
            with patch.object(SCRIPT.sys, "argv", ["import", str(output)]), \
                    patch.object(SCRIPT, "fetch_hourly_json", side_effect=TimeoutError) as fetch, \
                    self.assertRaises(TimeoutError):
                SCRIPT.main()
            self.assertEqual(fetch.call_count, 1)
            self.assertFalse((output / "receipt.json").exists())

    def test_complete_native_cohort_readbacks_and_honest_readiness(self):
        protocol = canonical({
            "symbols": ["BTCUSDT", "ETHUSDT", "SOLUSDT"], "price_kinds": ["trade", "mark"],
            "start": iso(START), "end_exclusive": iso(START + H1 * 8),
            "expected_h1_bars_per_stream": 8,
        }).encode()
        seen = set()
        def fetch(url):
            query = parse_qs(urlsplit(url).query)
            symbol = query["symbol"][0]
            if "/fundingRate?" in url:
                if symbol in seen:
                    return []
                seen.add(symbol)
                return [{"symbol": symbol, "fundingTime": milliseconds(START) + 19,
                         "fundingRate": "-0.0001", "markPrice": ""}]
            at = EPOCH + H1 * (int(query["startTime"][0]) // 3600000)
            return [kline(at + H1 * i) for i in range(8)]
        with TemporaryDirectory() as directory:
            output = Path(directory) / "new"
            with patch.object(SCRIPT.sys, "argv", ["import", str(output)]), \
                    patch.object(Path, "read_bytes", return_value=protocol), \
                    patch.object(SCRIPT, "PROTOCOL_SHA256", hashlib.sha256(protocol).hexdigest()), \
                    patch.object(SCRIPT, "fetch_hourly_json", side_effect=fetch), \
                    redirect_stdout(io.StringIO()):
                SCRIPT.main()
            receipt = decode_json((output / "receipt.json").read_text())
            self.assertEqual(len(receipt["streams"]), 9)
            self.assertTrue(receipt["shared_hourly_axis_verified"])
            self.assertTrue(receipt["all_funding_windows_match_declared_buckets"])
            for key in ("net_backtest_ready", "performance_evaluated", "execution_enabled",
                        "historical_fee_and_maintenance_rules_verified", "holdout_requested"):
                self.assertFalse(receipt[key])
            for stream in receipt["streams"]:
                text = (output / stream["file"]).read_text()
                self.assertEqual(hashlib.sha256(text.encode()).hexdigest(), stream["file_sha256"])
                self.assertEqual(load_hourly_snapshot(text).data_digest, stream["data_digest"])


if __name__ == "__main__":
    unittest.main()
