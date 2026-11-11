"""Create-only availability receipts do not claim economic acceptance."""
import importlib.util
import io
from contextlib import redirect_stdout
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from investalo_marketdata.futures_funding import FundingHistoryResult, FundingPage, funding_url
from investalo_marketdata.futures_snapshot import FundingEvent, FundingSnapshot, load_funding_snapshot
from investalo_marketdata.snapshot import decode_json

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "funding_import", ROOT / "infra/scripts/import-futures-funding.py")
SCRIPT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SCRIPT)


class FundingImportTests(unittest.TestCase):
    def test_changed_protocol_fails_before_directory_creation_or_network(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / "new"
            with patch.object(SCRIPT.sys, "argv", ["import", str(output)]), \
                    patch.object(Path, "read_bytes", return_value=b"{}"), \
                    patch.object(SCRIPT, "fetch_funding_json") as fetch, \
                    self.assertRaisesRegex(ValueError, "protocol changed"):
                SCRIPT.main()
            fetch.assert_not_called()
            self.assertFalse(output.exists())

    def test_existing_output_is_preserved_and_not_fetched(self):
        with TemporaryDirectory() as directory:
            marker = Path(directory) / "existing.json"
            marker.write_text("preserved")
            with patch.object(SCRIPT.sys, "argv", ["import", directory]), \
                    patch.object(SCRIPT, "fetch_funding_json") as fetch, \
                    self.assertRaises(FileExistsError):
                SCRIPT.main()
            fetch.assert_not_called()
            self.assertEqual(marker.read_text(), "preserved")

    def test_failed_fetch_has_no_retry_or_success_receipt(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / "new"
            with patch.object(SCRIPT.sys, "argv", ["import", str(output)]), \
                    patch.object(SCRIPT, "fetch_funding_json", side_effect=TimeoutError) as fetch, \
                    self.assertRaises(TimeoutError):
                SCRIPT.main()
            self.assertEqual(fetch.call_count, 1)
            self.assertFalse((output / "receipt.json").exists())

    def test_recent_events_never_fill_old_requested_window(self):
        class RecentOnly:
            def __init__(self, fetch):
                pass

            def fetch_history(self, symbol, *, start, end, retrieved_at):
                recent = datetime(2026, 10, 1, tzinfo=timezone.utc)
                return FundingHistoryResult(
                    FundingSnapshot(symbol, retrieved_at, start, end, ()),
                    FundingSnapshot(symbol, retrieved_at, recent, retrieved_at,
                                    (FundingEvent(recent, Decimal("0.0001")),)),
                    (FundingPage(1, funding_url(symbol, 1), "synthetic", 1, recent, recent),),
                    "empty_page",
                )

        with TemporaryDirectory() as directory:
            output = Path(directory) / "new"
            with patch.object(SCRIPT.sys, "argv", ["import", str(output)]), \
                    patch.object(SCRIPT, "BitgetFundingHistoryAdapter", RecentOnly), \
                    redirect_stdout(io.StringIO()):
                SCRIPT.main()
            receipt = decode_json((output / "receipt.json").read_bytes())
            self.assertFalse(receipt["all_windows_match_declared_calendar"])
            self.assertFalse(receipt["net_backtest_ready"])
            self.assertFalse(receipt["historical_schedule_verified"])
            self.assertFalse(receipt["performance_evaluated"])
            self.assertFalse(receipt["holdout_requested"])
            for stream in receipt["streams"]:
                self.assertEqual(stream["coverage"]["missing_events"], 3288)
                for name, count in (("requested", 0), ("recent-observed", 1)):
                    artifact = stream["artifacts"][name]
                    snapshot = load_funding_snapshot((output / artifact["file"]).read_bytes())
                    self.assertEqual(len(snapshot.events), count)
                    self.assertEqual(snapshot.data_digest, artifact["data_digest"])

    def test_second_symbol_failure_cannot_publish_partial_success_receipt(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / "new"
            with patch.object(SCRIPT.sys, "argv", ["import", str(output)]), \
                    patch.object(SCRIPT, "fetch_funding_json",
                                 side_effect=[{"code": "00000", "data": []}, TimeoutError]), \
                    redirect_stdout(io.StringIO()), self.assertRaises(TimeoutError):
                SCRIPT.main()
            self.assertTrue((output / "BTCUSDT-requested-funding.json").exists())
            self.assertFalse((output / "receipt.json").exists())


if __name__ == "__main__":
    unittest.main()
