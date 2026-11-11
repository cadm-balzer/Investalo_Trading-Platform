"""Synthetic signed settlements and hostile pagination; no performance claims."""
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest
from unittest.mock import Mock, patch

from investalo_marketdata.futures_funding import (
    MAX_PAGES, BitgetFundingHistoryAdapter, FundingExpectation, audit_funding_coverage,
    fetch_funding_json, funding_url, regular_funding_expectation,
)
from investalo_marketdata.futures_snapshot import FundingEvent, FundingSnapshot
from investalo_marketdata.snapshot import iso

UTC = timezone.utc
START = datetime(2023, 1, 1, tzinfo=UTC)
END = START + timedelta(days=1)
RETRIEVED = START + timedelta(days=2)
D = Decimal


def row(at, rate="0.0001", symbol="BTCUSDT"):
    return {"symbol": symbol, "fundingTime": str(int(at.timestamp()) * 1000), "fundingRate": rate}


def page(*rows):
    return {"code": "00000", "data": list(rows)}


def fetch(pages, *, start=START, end=END):
    calls = Mock(side_effect=pages)
    sleep = Mock()
    result = BitgetFundingHistoryAdapter(calls, sleep).fetch_history(
        "BTCUSDT", start=start, end=end, retrieved_at=RETRIEVED)
    return result, calls, sleep


def expectation():
    return regular_funding_expectation("BTCUSDT", START, END, interval_hours=8,
                                       assumptions_digest="synthetic-eight-hour-assumption")


class FundingHistoryTests(unittest.TestCase):
    def test_signed_zero_rates_and_requested_exclusive_end(self):
        result, calls, _ = fetch([page(
            row(END), row(START + timedelta(hours=16), "-0.0001"),
            row(START + timedelta(hours=8), "0"), row(START, "0.0002"),
        )])
        self.assertEqual([e.rate for e in result.requested.events], [D(".0002"), 0, D("-.0001")])
        self.assertEqual(len(result.observed.events), 4)
        self.assertEqual(result.termination, "reached_requested_start")
        self.assertEqual(calls.call_count, 1)

    def test_recent_only_provider_exhaustion_is_not_three_year_coverage(self):
        recent = START + timedelta(days=1, hours=8)
        result, calls, sleep = fetch([page(row(recent)), page()])
        self.assertFalse(result.requested.events)
        self.assertEqual(len(result.observed.events), 1)
        self.assertEqual(len(result.pages), 2)
        self.assertEqual(result.termination, "empty_page")
        self.assertEqual(calls.call_count, 2)
        sleep.assert_called_once_with(.1)
        audit = audit_funding_coverage(result.requested, expectation())
        self.assertEqual(audit["missing_events"], 3)
        self.assertFalse(audit["complete_against_declared_calendar"])

    def test_empty_first_page_is_an_empty_observation_not_zero_funding(self):
        result, calls, _ = fetch([page()])
        self.assertFalse(result.observed.events)
        self.assertFalse(result.requested.events)
        self.assertEqual(calls.call_count, 1)
        self.assertEqual(audit_funding_coverage(result.requested, expectation())["missing_events"], 3)

    def test_same_overlap_is_deduplicated_but_hole_remains_visible(self):
        latest, middle = START + timedelta(hours=16), START + timedelta(hours=8)
        result, calls, _ = fetch([page(row(latest), row(middle)),
                                 page(row(middle), row(START))])
        self.assertEqual(len(result.requested.events), 3)
        self.assertEqual(calls.call_count, 2)
        self.assertTrue(audit_funding_coverage(result.requested, expectation())[
            "complete_against_declared_calendar"])

    def test_revised_overlap_or_nonprogressing_page_fails(self):
        latest, middle = START + timedelta(hours=16), START + timedelta(hours=8)
        for second in (page(row(middle, "0.2"), row(START)),
                       page(row(latest), row(middle))):
            calls = Mock(side_effect=[page(row(latest), row(middle)), second])
            with self.subTest(second=second), self.assertRaises(ValueError):
                BitgetFundingHistoryAdapter(calls, Mock()).fetch_history(
                    "BTCUSDT", start=START, end=END, retrieved_at=RETRIEVED)
            self.assertEqual(calls.call_count, 2)

    def test_duplicate_or_ascending_rows_are_rejected(self):
        for rows in ((row(START), row(START)), (row(START), row(END))):
            with self.subTest(rows=rows), self.assertRaisesRegex(ValueError, "descending"):
                fetch([page(*rows)])

    def test_bad_provider_shape_and_wrong_symbol_fail(self):
        for body in ({"code": "40000", "data": []}, {"code": "00000", "data": {}},
                     page(row(START, symbol="ETHUSDT")), page(*[row(END)] * 101),
                     page({"symbol": "BTCUSDT", "fundingTime": "1", "fundingRate": "0", "other": 1})):
            with self.subTest(body=body), self.assertRaises(ValueError):
                fetch([body])

    def test_timestamp_and_rate_bounds_reject_float_future_or_bad_strings(self):
        for field, value in (
            ("fundingTime", 1), ("fundingTime", "-1"), ("fundingTime", "９９"),
            ("fundingTime", "9" * 16), ("fundingTime", "9" * 15),
            ("fundingTime", str(int(RETRIEVED.timestamp()) * 1000)),
            ("fundingRate", .1), ("fundingRate", "NaN"), ("fundingRate", "1.01"),
        ):
            data = row(START)
            data[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                fetch([page(data)])

    def test_page_capacity_is_terminal_without_success_result(self):
        calls = Mock(side_effect=[page(row(START + timedelta(hours=200 - i)))
                                 for i in range(MAX_PAGES)])
        with self.assertRaisesRegex(ValueError, "page capacity"):
            BitgetFundingHistoryAdapter(calls, Mock()).fetch_history(
                "BTCUSDT", start=START, end=END,
                retrieved_at=START + timedelta(days=20))
        self.assertEqual(calls.call_count, MAX_PAGES)

    def test_failed_transport_is_not_retried(self):
        calls = Mock(side_effect=TimeoutError("synthetic"))
        with self.assertRaises(TimeoutError):
            BitgetFundingHistoryAdapter(calls, Mock()).fetch_history(
                "BTCUSDT", start=START, end=END, retrieved_at=RETRIEVED)
        self.assertEqual(calls.call_count, 1)

    def test_invalid_window_symbol_or_future_retrieval_does_not_fetch(self):
        for values in (
            {"start": END, "end": START, "symbol": "BTCUSDT", "retrieved_at": RETRIEVED},
            {"start": START, "end": END, "symbol": "BTC/USDT", "retrieved_at": RETRIEVED},
            {"start": START, "end": RETRIEVED, "symbol": "BTCUSDT", "retrieved_at": END},
        ):
            calls = Mock()
            with self.subTest(values=values), self.assertRaises(ValueError):
                BitgetFundingHistoryAdapter(calls, Mock()).fetch_history(**values)
            calls.assert_not_called()

    def test_transport_rejects_changed_origin_path_query_and_secrets_before_io(self):
        good = funding_url("BTCUSDT", 1)
        for url in (
            good.replace("api.bitget.com", "example.com"),
            good.replace("history-fund-rate", "accounts"),
            good + "&apiKey=synthetic", good + "&pageNo=2", good.replace("pageSize=100", "pageSize=101"),
            good.replace("pageNo=1", "pageNo=0"), good.replace("pageNo=1", "pageNo=101"),
            good.replace("https:", "http:"),
        ):
            with self.subTest(url=url), patch(
                    "investalo_marketdata.futures_funding.build_opener") as opener, \
                    self.assertRaises(ValueError):
                fetch_funding_json(url)
            opener.assert_not_called()

    def test_transport_uses_bounded_response_and_no_redirect_handler(self):
        body = b'{"code":"00000","data":[]}'
        response = Mock()
        response.read.return_value = body
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        with patch("investalo_marketdata.futures_funding.build_opener") as opener:
            opener.return_value.open.return_value = response
            self.assertEqual(fetch_funding_json(funding_url("BTCUSDT", 1)), page())
        self.assertEqual(response.read.call_args.args[0], 262145)
        self.assertEqual(opener.call_args.args[0].__class__.__name__, "_NoRedirect")
        request = opener.return_value.open.call_args.args[0]
        self.assertEqual(request.get_method(), "GET")
        self.assertNotIn("Authorization", request.headers)
        self.assertEqual(opener.return_value.open.call_args.kwargs["timeout"], 10)

    def test_oversized_json_response_fails(self):
        response = Mock()
        response.read.return_value = b" " * 262145
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        with patch("investalo_marketdata.futures_funding.build_opener") as opener, \
                self.assertRaises(ValueError):
            opener.return_value.open.return_value = response
            fetch_funding_json(funding_url("BTCUSDT", 1))


class FundingCoverageTests(unittest.TestCase):
    def test_zero_is_present_and_completeness_never_activates_performance(self):
        calendar = expectation()
        snapshot = FundingSnapshot("BTCUSDT", RETRIEVED, START, END,
                                   tuple(FundingEvent(t, D("0")) for t in calendar.settlements))
        result = audit_funding_coverage(snapshot, calendar)
        self.assertTrue(result["complete_against_declared_calendar"])
        self.assertEqual(result["missing_events"], 0)
        self.assertFalse(result["historical_schedule_verified"])
        self.assertFalse(result["performance_evaluated"])
        self.assertFalse(result["execution_enabled"])

    def test_interior_missing_settlement_is_not_hidden_by_matching_endpoints(self):
        calendar = expectation()
        snapshot = FundingSnapshot("BTCUSDT", RETRIEVED, START, END, (
            FundingEvent(START, D("0")), FundingEvent(START + timedelta(hours=16), D("0"))))
        result = audit_funding_coverage(snapshot, calendar)
        self.assertFalse(result["complete_against_declared_calendar"])
        self.assertEqual(result["missing_events"], 1)
        self.assertEqual(result["first_missing"], iso(START + timedelta(hours=8)))

    def test_unexpected_settlement_and_explicit_cadence_change(self):
        times = (START, START + timedelta(hours=4), START + timedelta(hours=8),
                 START + timedelta(hours=16))
        snapshot = FundingSnapshot("BTCUSDT", RETRIEVED, START, END,
                                   tuple(FundingEvent(t, D("0")) for t in times))
        result = audit_funding_coverage(snapshot, expectation())
        self.assertEqual(result["missing_events"], 0)
        self.assertEqual(result["unexpected_events"], 1)
        changed = FundingExpectation("BTCUSDT", START, END, times, "synthetic-change-calendar")
        self.assertTrue(audit_funding_coverage(snapshot, changed)["complete_against_declared_calendar"])
        self.assertNotEqual(changed.expectation_digest, expectation().expectation_digest)

    def test_foreign_window_or_symbol_is_rejected(self):
        snapshot = FundingSnapshot("BTCUSDT", RETRIEVED, START, END, ())
        for other in (replace(expectation(), symbol="ETHUSDT"),
                      replace(expectation(), end=END + timedelta(hours=1))):
            with self.subTest(other=other), self.assertRaises(ValueError):
                audit_funding_coverage(snapshot, other)

    def test_empty_unordered_naive_or_oversized_calendar_is_rejected(self):
        for times in ((), (START, START), (START.replace(tzinfo=None),),
                      (END,), tuple(START for _ in range(10001))):
            with self.subTest(times=len(times)), self.assertRaises(ValueError):
                replace(expectation(), settlements=times)

    def test_regular_calendar_bounds_rounding_and_immutability(self):
        for hours in (0, 25, True, 8.0):
            with self.subTest(hours=hours), self.assertRaises(ValueError):
                regular_funding_expectation("BTCUSDT", START, END,
                                            interval_hours=hours, assumptions_digest="synthetic")
        with self.assertRaises(ValueError):
            regular_funding_expectation("BTCUSDT", START, START + timedelta(days=4000),
                                        interval_hours=8, assumptions_digest="synthetic")
        result = regular_funding_expectation("BTCUSDT", START, END + timedelta(seconds=1),
                                            interval_hours=8, assumptions_digest="synthetic")
        self.assertEqual(len(result.settlements), 4)
        with self.assertRaises(FrozenInstanceError):
            result.symbol = "ETHUSDT"


if __name__ == "__main__":
    unittest.main()
