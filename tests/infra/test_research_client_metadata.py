import importlib.util
import json
from pathlib import Path
import unittest


spec = importlib.util.spec_from_file_location(
    "local_auth_metadata_checks", Path(__file__).with_name("check_local_auth.py"),
)
checks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checks)


class ResearchClientMetadataTests(unittest.TestCase):
    def record(self, **changes):
        return {
            "id": "00000000-0000-4000-8000-000000000001", "symbol": "ETH/USDT",
            "timeframe": "4h", "data_digest": "a" * 64, "purpose": "research",
            "synthetic": False, "source": {"venue": "bitget"}, **changes,
        }

    def page(self, *chunks):
        reader = checks.DatasetOptions()
        reader.feed("".join(
            "<script>self.__next_f.push(" + json.dumps([1, chunk]) + ")</script>"
            for chunk in chunks
        ))
        return reader

    def test_reads_exact_eth_metadata_from_pinned_json_client_props(self):
        item = self.record()
        page = self.page('1:{"datasets":[' + json.dumps(item) + "]}")
        self.assertEqual(page.client_dataset("ETH/USDT", "a" * 64), item["id"])

    def test_record_can_span_streamed_chunks(self):
        payload = '1:{"datasets":[' + json.dumps(self.record()) + "]}"
        page = self.page(payload[:100], payload[100:])
        self.assertEqual(page.client_dataset("ETH/USDT", "a" * 64), self.record()["id"])

    def test_rejects_wrong_digest_asset_holdout_and_synthetic_metadata(self):
        for changes in (
            {"data_digest": "b" * 64}, {"symbol": "BTC/USDT"},
            {"purpose": "holdout"}, {"synthetic": True}, {"id": "unexpected"},
            {"source": {"venue": "csv"}},
        ):
            with self.subTest(changes=changes):
                page = self.page(json.dumps(self.record(**changes)))
                self.assertIsNone(page.client_dataset("ETH/USDT", "a" * 64))

    def test_never_evaluates_script_or_uses_unrecognized_transport(self):
        reader = checks.DatasetOptions()
        reader.feed('<script>throw new Error("never execute")</script>')
        self.assertIsNone(reader.client_dataset("ETH/USDT", "a" * 64))
        reader = self.page("not JSON data")
        self.assertIsNone(reader.client_dataset("ETH/USDT", "a" * 64))

    def test_rejects_oversized_metadata(self):
        reader = self.page(" " * (2 * 1024 * 1024 + 1))
        with self.assertRaises(RuntimeError):
            reader.client_dataset("ETH/USDT", "a" * 64)


if __name__ == "__main__":
    unittest.main()
