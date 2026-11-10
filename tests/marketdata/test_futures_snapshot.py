import json
import unittest
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from investalo_trading import Candle, PaperSimulator
from investalo_marketdata.snapshot import (
    H4, MAX_BARS, SnapshotSource, load_snapshot, make_snapshot, to_trading_candles,
)
from investalo_marketdata.futures_snapshot import (
    ENDPOINTS, FUNDING_ENDPOINT, MARKET, MAX_FUNDING_EVENTS, SYMBOLS,
    FundingEvent, FundingSnapshot, FuturesSource, candle_symbol,
    dump_funding_snapshot, dump_futures_snapshot, funding_rate,
    load_funding_snapshot, load_futures_snapshot, make_futures_snapshot,
)

D = Decimal
START = datetime(2020, 1, 1, tzinfo=timezone.utc)
RETRIEVED = datetime(2021, 1, 1, tzinfo=timezone.utc)


def bar(index=0, *, symbol="BTCUSDT", kind="trade", close="100.123456789012345678"):
    return Candle(candle_symbol(symbol, kind), START + index * H4, START + (index + 1) * H4,
                  D("100"), D("102"), D("98"), D(close))


def snapshot(kind="trade", symbol="BTCUSDT", rows=None, **kwargs):
    candles = tuple(rows) if rows is not None else tuple(
        bar(i, symbol=symbol, kind=kind) for i in range(2)
    )
    return make_futures_snapshot(symbol, kind, candles, FuturesSource(kind, RETRIEVED), **kwargs)


def funding(events=None, **kwargs):
    return FundingSnapshot("BTCUSDT", RETRIEVED, START, START + timedelta(days=2),
                           tuple(events) if events is not None else (
                               FundingEvent(START, D("0.0001")),
                               FundingEvent(START + H4, D("-0.00025")),
                           ), **kwargs)


class FuturesSnapshotTests(unittest.TestCase):
    def test_roundtrip_exact_decimal_and_frozen_typed_records(self):
        result = snapshot()
        encoded = dump_futures_snapshot(result)
        self.assertEqual(load_futures_snapshot(encoded.encode()), result)
        self.assertEqual(dump_futures_snapshot(load_futures_snapshot(encoded)), encoded)
        self.assertIn('"100.123456789012345678"', encoded)
        self.assertEqual(result.market, MARKET)
        with self.assertRaises(FrozenInstanceError):
            result.symbol = "ETHUSDT"
        with self.assertRaises(FrozenInstanceError):
            result.source.price_kind = "index"
        with self.assertRaises(ValueError):
            replace(result, candles=list(result.candles))
        with self.assertRaises(TypeError):
            ENDPOINTS["trade"] = "https://example.test/history"

    def test_market_and_each_price_kind_have_separate_data_identity(self):
        values = [snapshot(kind) for kind in ENDPOINTS]
        self.assertEqual(len({value.data_digest for value in values}), 3)
        for result in values:
            self.assertIn(result.price_kind, result.candles[0].symbol)
            self.assertEqual(result.source.url, ENDPOINTS[result.price_kind])
            self.assertEqual(load_futures_snapshot(dump_futures_snapshot(result)), result)
            # The legacy converter preserves the suffix, so the spot core rejects it.
            converted = to_trading_candles(result)
            self.assertEqual(converted[0].symbol, candle_symbol("BTCUSDT", result.price_kind))
            with self.assertRaises(ValueError):
                PaperSimulator().run(converted)
        spot = make_snapshot("BTC/USDT", tuple(
            replace(item, symbol="BTC/USDT") for item in values[0].candles
        ), SnapshotSource("bitget", "3",
                          "https://api.bitget.com/api/v3/market/history-candles", RETRIEVED),
                             synthetic=False)
        self.assertNotEqual(spot.data_digest, values[0].data_digest)
        with self.assertRaises(ValueError):
            load_snapshot(dump_futures_snapshot(values[0]))

    def test_retrieval_and_request_do_not_change_price_data_identity(self):
        original = snapshot()
        later = replace(original, source=FuturesSource("trade", RETRIEVED + timedelta(days=1)))
        shortfall = snapshot(requested_start=START - H4, requested_end=START + 3 * H4)
        self.assertEqual(original.data_digest, later.data_digest)
        self.assertEqual(original.data_digest, shortfall.data_digest)
        self.assertFalse(shortfall.coverage.complete)
        self.assertEqual(shortfall.coverage.record()["missing_leading_bars"], 1)
        self.assertEqual(shortfall.coverage.record()["missing_trailing_bars"], 1)
        self.assertIsNone(original.coverage.complete)
        self.assertTrue(snapshot(requested_start=START, requested_end=START + 2 * H4).coverage.complete)

    def test_candidate_symbols_are_exact_and_not_evidence_of_history(self):
        self.assertEqual(len(SYMBOLS), 20)
        for symbol in SYMBOLS:
            with self.subTest(symbol=symbol):
                result = snapshot(symbol=symbol)
                self.assertIsNone(result.coverage.complete)
                self.assertEqual(load_futures_snapshot(dump_futures_snapshot(result)), result)
        for symbol in ("BTC/USDT", "BTCUSDT_UMCBL", "DOGEUSDT", None, ["BTCUSDT"]):
            with self.subTest(symbol=symbol), self.assertRaises(ValueError):
                candle_symbol(symbol, "trade")
        for kind in ("spot", "last", None, ["mark"]):
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                candle_symbol("BTCUSDT", kind)

    def test_schema_source_market_price_kind_and_candle_tampering_fail(self):
        for field, value in (
            ("schema_version", "marketdata-snapshot/1"), ("market", "spot"),
            ("timeframe", "1h"), ("symbol", "DOGEUSDT"), ("price_kind", "mark"),
            ("data_digest", "0" * 64), ("unexpected", True),
        ):
            raw = json.loads(dump_futures_snapshot(snapshot()))
            raw[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                load_futures_snapshot(json.dumps(raw))
        for field, value in (("url", FUNDING_ENDPOINT), ("venue", "csv"), ("api_version", "3"),
                             ("kind", "synthetic"), ("price_kind", "index")):
            raw = json.loads(dump_futures_snapshot(snapshot()))
            raw["source"][field] = value
            with self.subTest(source=field), self.assertRaises(ValueError):
                load_futures_snapshot(json.dumps(raw))
        raw = json.loads(dump_futures_snapshot(snapshot()))
        raw["candles"][0]["close"] = "99"
        with self.assertRaisesRegex(ValueError, "digest"):
            load_futures_snapshot(json.dumps(raw))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            load_futures_snapshot('{"market":"spot","market":"futures"}')

    def test_coverage_false_claims_and_malformed_bounds_fail(self):
        for field, value in (
            ("complete", True), ("complete", 0), ("missing_leading_bars", True),
            ("missing_trailing_bars", -1), ("actual_start", "2020-01-01T04:00:00Z"),
            ("requested_start", ""), ("requested_end", []),
        ):
            raw = json.loads(dump_futures_snapshot(snapshot()))
            raw["coverage"][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                load_futures_snapshot(json.dumps(raw))
        with self.assertRaises(ValueError):
            snapshot(requested_start=START + H4, requested_end=START + 2 * H4)
        with self.assertRaises(ValueError):
            snapshot(requested_start=START, requested_end=START + (MAX_BARS + 1) * H4)
        with self.assertRaises(ValueError):
            snapshot(requested_start=START, requested_end=RETRIEVED + H4)

    def test_duplicate_gapped_out_of_order_unclosed_and_wrong_identity_fail(self):
        for rows in ((bar(), bar()), (bar(), bar(2)), (bar(1), bar()),
                     (bar(kind="mark"),), (replace(bar(), symbol="BTCUSDT"),), ()):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                snapshot(rows=rows)
        with self.assertRaises(ValueError):
            replace(snapshot(), source=FuturesSource("mark", RETRIEVED))
        with self.assertRaisesRegex(ValueError, "unclosed"):
            make_futures_snapshot("BTCUSDT", "trade", (bar(),),
                                  FuturesSource("trade", START + H4 - timedelta(microseconds=1)))
        with self.assertRaises(ValueError):
            FuturesSource("trade", datetime.now(timezone.utc) + timedelta(days=1))
        with self.assertRaises(ValueError):
            FuturesSource("trade", datetime(2020, 1, 1))
        with self.assertRaises(ValueError):
            replace(snapshot(), candles=(bar(),) * (MAX_BARS + 1))
        raw = json.loads(dump_futures_snapshot(snapshot()))
        raw["candles"][0]["high"] = "99"
        with self.assertRaises(ValueError):
            load_futures_snapshot(json.dumps(raw))


class FundingSnapshotTests(unittest.TestCase):
    def test_signed_fractional_rates_precision_and_roundtrip(self):
        result = funding()
        encoded = dump_funding_snapshot(result)
        self.assertIn('"-0.00025"', encoded)
        self.assertEqual(load_funding_snapshot(encoded.encode()), result)
        self.assertEqual(dump_funding_snapshot(load_funding_snapshot(encoded)), encoded)
        self.assertEqual(result.events[1].rate, D("-0.00025"))
        for rate in ("-1", "1", "0", "-0", "-0.000000000000000000000001"):
            with self.subTest(rate=rate):
                self.assertEqual(funding_rate(rate), D(rate))
        with self.assertRaises(FrozenInstanceError):
            result.events[0].rate = D("0")
        with self.assertRaises(ValueError):
            FundingEvent(START, 0.1)

    def test_event_timestamps_rates_market_and_window_bound_into_digest(self):
        original = funding()
        for changed in (
            replace(original, symbol="ETHUSDT"),
            replace(original, requested_end=START + timedelta(days=3)),
            funding((FundingEvent(START, D("-0.0001")),)),
            funding((FundingEvent(START + timedelta(seconds=1), D("0.0001")),)),
        ):
            self.assertNotEqual(original.data_digest, changed.data_digest)
        self.assertEqual(original.data_digest,
                         replace(original, retrieved_at=RETRIEVED + H4).data_digest)
        self.assertNotEqual(funding(()).data_digest,
                            funding((FundingEvent(START, D("0")),)).data_digest)

    def test_empty_sparse_and_irregular_events_never_claim_complete_or_impute_zero(self):
        for result in (
            funding(()),
            funding((FundingEvent(START + timedelta(minutes=13), D("-0.001")),)),
            funding((FundingEvent(START, D("0.001")),
                     FundingEvent(START + timedelta(hours=17), D("0.002")))),
        ):
            raw = json.loads(dump_funding_snapshot(result))
            self.assertEqual(len(raw["events"]), len(result.events))
            self.assertNotIn("complete", raw)
            self.assertNotIn("cadence", raw)
            self.assertEqual(load_funding_snapshot(json.dumps(raw)), result)
            raw["complete"] = True
            with self.assertRaises(ValueError):
                load_funding_snapshot(json.dumps(raw))

    def test_signed_rate_bounds_and_resource_work_are_limited(self):
        for value in (1, 0.1, True, None, "NaN", "-Infinity", "-1.01", "1.01",
                      "-1e-25", "-1e999", "-0." + "1" * 37, "1" * 100, "--0.01"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                funding_rate(value)
        with self.assertRaises(ValueError):
            funding((FundingEvent(START, D("0")),) * (MAX_FUNDING_EVENTS + 1))
        with self.assertRaises(ValueError):
            replace(funding(), events=list(funding().events))
        with self.assertRaises(ValueError):
            load_funding_snapshot(" " * (16 * 1024 * 1024 + 1))

    def test_events_unique_sorted_inside_half_open_window(self):
        event = FundingEvent(START, D("0.0001"))
        later = FundingEvent(START + H4, D("0.0002"))
        for events in ((event, event), (later, event),
                       (FundingEvent(START - timedelta(seconds=1), D("0")),),
                       (FundingEvent(START + timedelta(days=2), D("0")),)):
            with self.subTest(events=events), self.assertRaises(ValueError):
                funding(events)
        with self.assertRaises(ValueError):
            replace(funding(), requested_start=START + timedelta(days=2))
        with self.assertRaises(ValueError):
            replace(funding(), requested_end=RETRIEVED + H4)
        with self.assertRaises(ValueError):
            FundingEvent(datetime(2020, 1, 1), D("0"))

    def test_funding_tamper_unknown_source_schema_and_fields_fail(self):
        for field, value in (("schema_version", "funding/2"), ("market", "spot"),
                             ("symbol", "BTC/USDT"), ("data_digest", "bad")):
            raw = json.loads(dump_funding_snapshot(funding()))
            raw[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                load_funding_snapshot(json.dumps(raw))
        for field, value in (("url", ENDPOINTS["trade"]), ("api_version", "3"),
                             ("kind", "synthetic")):
            raw = json.loads(dump_funding_snapshot(funding()))
            raw["source"][field] = value
            with self.subTest(source=field), self.assertRaises(ValueError):
                load_funding_snapshot(json.dumps(raw))
        for field, value in (("rate", "0.00025"), ("timestamp", "2020-01-01T05:00:00Z"),
                             ("complete", True)):
            raw = json.loads(dump_funding_snapshot(funding()))
            raw["events"][1][field] = value
            with self.subTest(event=field), self.assertRaises(ValueError):
                load_funding_snapshot(json.dumps(raw))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            load_funding_snapshot('{"symbol":"BTCUSDT","symbol":"ETHUSDT"}')


if __name__ == "__main__":
    unittest.main()
