"""Public native minute evidence, explicit uncertainty and protected archive."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
from pathlib import Path
import runpy
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from investalo_marketdata.bitget import milliseconds
from investalo_marketdata.futures_settlement_source import (
    BitgetSettlementSource, MINUTE, REFERENCE_POLICY, SYMBOLS,
    SettlementEvidence, fetch_settlement_json, mark_url,
)
from investalo_marketdata.snapshot import canonical, decode_json
from investalo_trading.snapshot import _decode

D = Decimal
AT = datetime(2026, 11, 14, 16, tzinfo=timezone.utc)
NOW = AT + 2 * MINUTE + timedelta(seconds=5)


class Provider:
    def __init__(self, mutate=None):
        self.urls, self.mutate = [], mutate

    def fetch(self, url):
        self.urls.append(url)
        query = parse_qs(urlsplit(url).query)
        symbol = query["symbol"][0]
        kind = "mark" if "granularity" in query else "funding"
        if kind == "funding":
            rows = [{"symbol": symbol, "fundingTime": str(milliseconds(AT - timedelta(hours=8) * i)),
                     "fundingRate": "-0.0001" if SYMBOLS.index(symbol) % 2 else "0.0002"}
                    for i in range(3)]
        else:
            p = D(100 + SYMBOLS.index(symbol))
            rows = [[str(milliseconds(AT + MINUTE * i)), str(p), str(p + 1), str(p - 1),
                     str(p + D(".25")), "0", "0"] for i in (-1, 0, 1)]
        payload = {"code": "00000", "requestTime": milliseconds(NOW), "data": rows}
        if self.mutate:
            self.mutate(kind, payload)
        return payload

    def collect(self):
        return BitgetSettlementSource(self.fetch, lambda: NOW, lambda _: None).collect(AT)


class FuturesSettlementSourceTests(unittest.TestCase):
    def test_exact_native_rate_and_minute_axis_have_explicit_uncertainty_and_roundtrip(self):
        provider = Provider()
        evidence = provider.collect()
        self.assertEqual(len(provider.urls), 10)
        self.assertEqual(evidence.funding[1].rate, D("-.0001"))
        self.assertEqual(evidence.minutes[0].open, D(100))
        self.assertEqual(evidence.minutes[0].high, D(101))
        self.assertEqual(evidence.minutes[0].close_time, AT + MINUTE)
        self.assertTrue(all(m.open_time == f.settled_at for m, f in zip(evidence.minutes, evidence.funding)))
        record = evidence.record()
        self.assertEqual(record["reference_policy"], REFERENCE_POLICY)
        self.assertFalse(record["reference_enabled"])
        self.assertFalse(record["exact_settlement_mark_available"])
        self.assertFalse(record["execution_enabled"])
        self.assertFalse(hasattr(evidence, "paper_settlement"))
        restored = _decode(SettlementEvidence, decode_json(canonical(record))["observation"])
        self.assertEqual(restored, evidence)
        self.assertEqual(restored.data_digest, hashlib.sha256(canonical(record).encode()).hexdigest())

    def test_canonical_transport_rejects_private_foreign_extra_or_shifted_urls_before_io(self):
        url = mark_url(SYMBOLS[0], AT)
        wrong = (url.replace("api.bitget.com", "other.invalid"), url + "#fragment", url + "&extra=1",
                 url + "&symbol=BTCUSDT", url.replace("granularity=1m", "granularity=1H"),
                 url.replace("history-mark-candles", "place-order"), url.replace("USDT-FUTURES", "SPOT"))
        with patch("investalo_marketdata.futures_settlement_source.build_opener") as opener:
            for bad in wrong:
                with self.subTest(url=bad), self.assertRaises(ValueError):
                    fetch_settlement_json(bad)
            opener.assert_not_called()

    def test_transport_is_unsigned_get_bounded_and_has_no_retry(self):
        with patch("investalo_marketdata.futures_settlement_source.build_opener") as opener:
            response = opener.return_value.open.return_value.__enter__.return_value
            response.read.return_value = b'{"code":"00000","data":[]}'
            fetch_settlement_json(mark_url(SYMBOLS[0], AT))
            request = opener.return_value.open.call_args.args[0]
            self.assertEqual(request.get_method(), "GET")
            self.assertEqual(set(k.lower() for k in request.headers), {"accept", "user-agent"})
            self.assertEqual(opener.return_value.open.call_args.kwargs["timeout"], 5)
            response.read.assert_called_once_with(256 * 1024 + 1)
            opener.return_value.open.side_effect = TimeoutError
            with self.assertRaises(TimeoutError):
                fetch_settlement_json(mark_url(SYMBOLS[0], AT))
            self.assertEqual(opener.return_value.open.call_count, 2)

    def test_missing_native_rate_is_never_zero_or_forecast_and_bad_history_rejects(self):
        def missing(kind, p):
            if kind == "funding":
                p["data"].pop(0)
        def duplicate(kind, p):
            if kind == "funding":
                p["data"].append(deepcopy(p["data"][0]))
        def foreign(kind, p):
            if kind == "funding":
                p["data"][0]["symbol"] = "FOREIGN"
        def shifted(kind, p):
            if kind == "funding":
                p["data"][0]["fundingTime"] = str(milliseconds(AT + timedelta(seconds=1)))
        for mutate in (missing, duplicate, foreign, shifted):
            with self.subTest(mutate=mutate.__name__), self.assertRaises(ValueError):
                Provider(mutate).collect()

    def test_missing_duplicate_unaligned_ohlc_or_foreign_minute_rejects(self):
        def missing(kind, p):
            if kind == "mark":
                p["data"].pop(1)
        def duplicate(kind, p):
            if kind == "mark":
                p["data"][2] = deepcopy(p["data"][1])
        def unaligned(kind, p):
            if kind == "mark":
                p["data"][1][0] = str(milliseconds(AT + timedelta(seconds=1)))
        def ohlc(kind, p):
            if kind == "mark":
                p["data"][1][2] = "1"
        def wrong_window(kind, p):
            if kind == "mark":
                p["data"][1][0] = str(milliseconds(AT + 2 * MINUTE))
        for mutate in (missing, duplicate, unaligned, ohlc, wrong_window):
            with self.subTest(mutate=mutate.__name__), self.assertRaises(ValueError):
                Provider(mutate).collect()

    def test_future_or_rounded_target_is_rejected_before_network(self):
        provider = Provider()
        source = BitgetSettlementSource(provider.fetch, lambda: NOW, lambda _: None)
        for target in (NOW, AT + timedelta(seconds=1), AT - timedelta(hours=73)):
            with self.subTest(target=target), self.assertRaises(ValueError):
                source.collect(target)
        self.assertFalse(provider.urls)
        with self.assertRaises(ValueError):
            mark_url("XMRUSDT", AT)

    def test_stale_future_failed_provider_clocks_and_collection_deadline_stop(self):
        for delta in (-31, 1):
            def bad_clock(kind, payload):
                payload["requestTime"] = milliseconds(NOW + timedelta(seconds=delta))
            with self.subTest(delta=delta), self.assertRaises(ValueError):
                Provider(bad_clock).collect()
        provider = Provider()
        times = iter((NOW, NOW, NOW, NOW - timedelta(seconds=1)))
        with self.assertRaisesRegex(ValueError, "clock regressed"):
            BitgetSettlementSource(provider.fetch, lambda: next(times), lambda _: None).collect(AT)
        times = iter((NOW, NOW, NOW + timedelta(seconds=26)))
        with self.assertRaisesRegex(ValueError, "deadline"):
            BitgetSettlementSource(provider.fetch, lambda: next(times), lambda _: None).collect(AT)

    def test_typed_restored_evidence_rejects_foreign_native_axes_or_response_urls(self):
        value = Provider().collect()
        wrong = ({"funding": value.funding[::-1]}, {"minutes": value.minutes[:-1]},
                 {"funding": (replace(value.funding[0], settled_at=AT + MINUTE),) + value.funding[1:]},
                 {"reads": (replace(value.reads[0], url="https://other.invalid"),) + value.reads[1:]})
        for changes in wrong:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(value, **changes)

    def test_capture_files_are_create_only_owned_read_back_before_final_receipt(self):
        root = Path(__file__).resolve().parents[2]
        namespace = runpy.run_path(str(root / "infra/scripts/capture-futures-settlement-source.py"))
        capture = namespace["capture"]
        provider = Provider()
        capture.__globals__["fetch_settlement_json"] = provider.fetch
        capture.__globals__["BitgetSettlementSource"] = lambda fetch: BitgetSettlementSource(
            fetch, lambda: NOW, lambda _: None)
        with TemporaryDirectory() as folder:
            output = Path(folder) / "capture"
            result = capture(output, AT)
            self.assertEqual(output.stat().st_mode & 0o777, 0o700)
            receipt = decode_json((output / "receipt.json").read_bytes())
            self.assertFalse(receipt["reference_enabled"])
            self.assertEqual(len(receipt["response_hashes"]), 10)
            for entry in receipt["response_hashes"]:
                path = output / entry["file"]
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), entry["sha256"])
            self.assertEqual(hashlib.sha256((output / "receipt.json").read_bytes()).hexdigest(),
                             result["receipt_sha256"])
            original = (output / "receipt.json").read_bytes()
            with self.assertRaises(FileExistsError):
                capture(output, AT)
            self.assertEqual((output / "receipt.json").read_bytes(), original)

    def test_failed_capture_keeps_partial_evidence_without_success_receipt(self):
        root = Path(__file__).resolve().parents[2]
        capture = runpy.run_path(str(root / "infra/scripts/capture-futures-settlement-source.py"))["capture"]
        provider = Provider(lambda kind, p: p.update(code="failed"))
        capture.__globals__["fetch_settlement_json"] = provider.fetch
        capture.__globals__["BitgetSettlementSource"] = lambda fetch: BitgetSettlementSource(
            fetch, lambda: NOW, lambda _: None)
        with TemporaryDirectory() as folder:
            output = Path(folder) / "failed"
            with self.assertRaises(ValueError):
                capture(output, AT)
            self.assertTrue((output / "response-01.json").exists())
            self.assertFalse((output / "receipt.json").exists())
