"""Frozen reference input guards, with metadata and synthetic substitutions."""

import json
from pathlib import Path
import runpy
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
CHECKER = runpy.run_path(str(ROOT / "infra/scripts/check-portfolio-research.py"))


class PortfolioResearchGuards(unittest.TestCase):
    def fixture(self, root):
        original = root / CHECKER["ORIGINAL"]
        original.parent.mkdir(parents=True)
        original.write_text((ROOT / CHECKER["ORIGINAL"]).read_text())
        record = CHECKER["protocol"](root)
        (root / CHECKER["FROZEN"]).write_text(json.dumps(record))
        return record

    def test_frozen_protocol_survives_json_roundtrip_and_matches_checked_in_record(self):
        expected = CHECKER["protocol"]()
        self.assertEqual(expected, json.loads(json.dumps(expected)))
        self.assertEqual(expected, json.loads((ROOT / CHECKER["FROZEN"]).read_text()))
        self.assertEqual(expected["frozen_policy"]["symbol_priority"], ["BTCUSDT", "ETHUSDT"])

    def test_changed_frozen_policy_rejected_before_dataset_read(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record = self.fixture(root)
            record["scope"] = "evaluate_holdout"
            (root / CHECKER["FROZEN"]).write_text(json.dumps(record))
            with patch.dict(CHECKER["inputs"].__globals__, {"load_snapshot": unittest.mock.Mock()}) as _:
                with self.assertRaisesRegex(ValueError, "frozen portfolio"):
                    CHECKER["inputs"](root)
                CHECKER["inputs"].__globals__["load_snapshot"].assert_not_called()

    def test_symlink_is_rejected_before_snapshot_parse(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            data = root / "infra/local/research-data"
            data.mkdir(parents=True)
            target = data / "substitute.json"
            target.write_text("{}")
            (data / "btc-research-three-year-20261108.json").symlink_to(target)
            with self.assertRaisesRegex(ValueError, "fixed regular"):
                CHECKER["inputs"](root)

    def test_holdout_digest_substitution_is_rejected_before_candle_conversion(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            data = root / "infra/local/research-data"
            data.mkdir(parents=True)
            (data / "btc-research-three-year-20261108.json").write_text("{}")
            original = json.loads((root / CHECKER["ORIGINAL"]).read_text())
            fake = SimpleNamespace(
                synthetic=False, symbol="BTC/USDT",
                data_digest=original["assets"][0]["holdout"]["data_digest"],
            )
            parsed = unittest.mock.Mock(return_value=fake)
            convert = unittest.mock.Mock()
            with patch.dict(CHECKER["inputs"].__globals__, {
                "load_snapshot": parsed, "to_trading_candles": convert,
            }):
                with self.assertRaisesRegex(ValueError, "research input"):
                    CHECKER["inputs"](root)
            parsed.assert_called_once()
            convert.assert_not_called()


if __name__ == "__main__":
    unittest.main()
