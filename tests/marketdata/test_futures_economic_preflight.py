"""Synthetic native-file preflight/readback failures, not a performance test."""
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import importlib.util
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from investalo_marketdata.binance_futures import FundingObservation
from investalo_marketdata.binance_futures_hourly import HourlySnapshot
from investalo_marketdata.futures_research_profile import load_economic_protocol
from investalo_marketdata.snapshot import canonical
from investalo_trading.timeframe_research import ResearchCandle

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "economic_preflight_cli", ROOT / "infra/scripts/preflight-futures-capital.py")
CLI = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CLI)
D = Decimal


def fixture(root):
    protocol_raw = (ROOT / "docs/research-protocols/futures-capital-economics-20261112.json").read_bytes()
    cases = load_economic_protocol(protocol_raw)
    protocol = json.loads(protocol_raw)
    opened = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end = opened + timedelta(hours=1)
    protocol.update(start="2024-01-01T00:00:00Z", end_exclusive="2024-01-01T01:00:00Z",
                    expected_h1_bars_per_stream=1)
    docs = root / "docs/research-protocols"
    docs.mkdir(parents=True)
    (docs / "futures-capital-economics-20261112.json").write_text(canonical(protocol))
    directory = root / "infra/local/futures-h1-research-data/20261112-native-network"
    directory.mkdir(parents=True)
    streams = []
    for symbol in protocol["symbols"]:
        for kind in ("trade", "mark", "funding"):
            rows = tuple(FundingObservation(
                opened + timedelta(milliseconds=i * 9), D(".001"), None, "Regular")
                for i in range(3)) if kind == "funding" else (
                    ResearchCandle(f"BINANCE:{symbol}:USDT-M:{kind}", opened, end,
                                   D(100), D(110), D(90), D(99)),)
            snapshot = HourlySnapshot(symbol, kind, opened, end, end, rows)
            text = canonical(snapshot.record())
            filename = f"{symbol}-{kind}.json"
            (directory / filename).write_text(text)
            streams.append({
                "symbol": symbol, "kind": kind, "file": filename, "rows": len(rows),
                "data_digest": snapshot.data_digest, "file_sha256": hashlib.sha256(text.encode()).hexdigest()})
    receipt = canonical({"protocol_sha256": protocol["source_protocol_sha256"], "streams": streams}).encode()
    (docs / "futures-h1-history-receipt-20261112.json").write_bytes(receipt)
    return cases, hashlib.sha256(receipt).hexdigest()


def run(root, output, cases, receipt_digest):
    with patch.object(CLI, "ROOT", root), patch.object(CLI, "SOURCE_RECEIPT_SHA256", receipt_digest), \
            patch.object(CLI, "load_economic_protocol", return_value=cases), \
            patch.object(CLI.sys, "argv", ["preflight-futures-capital.py", str(output)]), \
            redirect_stdout(io.StringIO()):
        CLI.main()


class EconomicPreflightTests(unittest.TestCase):
    def test_complete_fifteen_native_files_ten_profiles_and_bounded_digest_work(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            cases, receipt_digest = fixture(root)
            output = root / "output"
            counts = {}
            original = HourlySnapshot.data_digest.fget

            def counted(snapshot):
                key = snapshot.symbol, snapshot.kind
                counts[key] = counts.get(key, 0) + 1
                return original(snapshot)

            with patch.object(HourlySnapshot, "data_digest", property(counted)):
                run(root, output, cases, receipt_digest)
            receipt = json.loads((output / "receipt.json").read_bytes())
            self.assertEqual(receipt["native_price_rows"], 10)
            self.assertEqual(receipt["native_funding_rows"], 15)
            self.assertEqual(receipt["funding_exact_hour_rows"], 5)
            self.assertEqual(receipt["maximum_simultaneous_settlements"], 5)
            self.assertEqual(len(receipt["profiles"]), 10)
            self.assertTrue(all(r["funding_reference_counts"]["H1_open_approximation"] == 15
                                for r in receipt["profiles"]))
            self.assertFalse(receipt["performance_evaluated"])
            self.assertTrue(all(count <= 6 for (s, kind), count in counts.items() if kind == "funding"))

    def test_corrupt_native_source_never_writes_a_success_receipt(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            cases, receipt_digest = fixture(root)
            source = root / "infra/local/futures-h1-research-data/20261112-native-network/BNBUSDT-trade.json"
            source.write_text(source.read_text() + "\n")
            output = root / "output"
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                run(root, output, cases, receipt_digest)
            self.assertFalse((output / "receipt.json").exists())

    def test_existing_output_is_never_replaced(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            cases, receipt_digest = fixture(root)
            output = root / "output"
            output.mkdir()
            marker = output / "receipt.json"
            marker.write_text("existing-acknowledgement")
            with self.assertRaises(FileExistsError):
                run(root, output, cases, receipt_digest)
            self.assertEqual(marker.read_text(), "existing-acknowledgement")


if __name__ == "__main__":
    unittest.main()
