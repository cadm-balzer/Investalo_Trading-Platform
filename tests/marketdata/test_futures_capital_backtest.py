"""Economic end-to-end market job checks with declared synthetic native sources."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from investalo_marketdata.binance_futures import FundingObservation
from investalo_marketdata.binance_futures_hourly import HourlySnapshot, SYMBOLS
from investalo_marketdata.futures_capital_backtest import run_scenario, validate_cohort
from investalo_marketdata.futures_research_profile import load_economic_protocol
from investalo_trading.snapshot import digest, primitive, _record_fields, _record_hints
from investalo_trading.capital_digest import digest as fast_digest, _encoded

D = Decimal
ROOT = Path(__file__).resolve().parents[2]
AT = datetime(2024, 1, 1, tzinfo=timezone.utc)


def fixture(*, crash=False, hours=80):
    end = AT + timedelta(hours=hours)
    streams = {}
    for symbol in SYMBOLS:
        for kind in ("trade", "mark"):
            from investalo_trading.timeframe_research import ResearchCandle
            bars = []
            for i in range(hours):
                price = D(130) - D(i // 4) * 2 if i < 64 else D(
                    100 if i < 68 or i >= 76 else 120)
                low = D(20) if crash and i == 65 else price * D(".995")
                bars.append(ResearchCandle(f"BINANCE:{symbol}:USDT-M:{kind}",
                                          AT + timedelta(hours=i), AT + timedelta(hours=i + 1),
                                          price, price * D("1.01"), low, price))
            streams[symbol, kind] = HourlySnapshot(symbol, kind, AT, end, end, tuple(bars))
        rows = tuple(FundingObservation(AT + timedelta(hours=h, milliseconds=ms),
                                       D(rate), None, "Regular")
                     for h, ms, rate in ((0, 0, ".0001"), (64, 0, ".0001"),
                                         (64, 18, "-.0002"), (72, 0, ".0001")) if h < hours)
        streams[symbol, "funding"] = HourlySnapshot(symbol, "funding", AT, end, end, rows)
    return streams


def cases():
    return load_economic_protocol(
        (ROOT / "docs/research-protocols/futures-capital-economics-20261112.json").read_bytes())


def run(streams, scenario, output):
    return run_scenario(streams, scenario, output, "a" * 64,
                        tuple(sorted({s.data_digest for s in streams.values()})))


class CapitalMarketBacktestTests(unittest.TestCase):
    def test_corrected_policy_is_bound_and_fully_restores_native_journal(self):
        from investalo_trading.futures_capital_research import CapitalCashPlan
        with TemporaryDirectory() as directory:
            output = Path(directory) / "cash"
            report = run_scenario(fixture(), cases()[0], output, "b" * 64,
                                  tuple(sorted({s.data_digest for s in fixture().values()})),
                                  cash_budget_protocol="b" * 64)
            self.assertEqual(report["capital_policy"], CapitalCashPlan.capital_policy)
            self.assertTrue(report["full_journal_restore_verified"])
            self.assertEqual(report["maximum_active_baskets"], 5)
            self.assertNotIn("6", report["stage_fill_counts"])
            header = json.loads((output / "journal.jsonl").open().readline())
            self.assertEqual(header["profile"]["plan"]["capital_policy"], CapitalCashPlan.capital_policy)
            self.assertEqual(header["protocol_digest"], "b" * 64)

    def test_complete_native_job_funding_stages_net_and_full_restore(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / "run"
            report = run(fixture(), cases()[0], output)
            self.assertTrue(report["full_journal_restore_verified"])
            self.assertFalse(report["execution_enabled"])
            self.assertGreater(report["closed_baskets"], 0)
            self.assertGreater(int(report["stage_fill_counts"]["1"]), 0)
            self.assertEqual(report["maximum_active_baskets"], 5)
            self.assertNotIn("6", report["stage_fill_counts"])
            self.assertEqual(D(report["final_equity"]) - D(10000), D(report["net_pnl"]))
            rows = [json.loads(s) for s in (output / "journal.jsonl").read_text().splitlines()[1:]]
            native = [r["command"]["at"] for r in rows if r["command"]["kind"] == "funding_batch"]
            self.assertIn("2024-01-03T16:00:00.018000+00:00", native)
            first_entry = next(r["command"] for r in rows if r["command"]["kind"] == "entry")
            self.assertEqual(first_entry["at"], "2024-01-03T16:00:02+00:00")
            curve = [json.loads(s) for s in (output / "equity.jsonl").read_text().splitlines()]
            self.assertEqual(len(curve), 81)
            self.assertEqual(D(curve[-1]["equity"]), D(report["final_equity"]))

    def test_gap_liquidations_are_terminal_and_unused_stages_not_lost(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / "run"
            report = run(fixture(crash=True), cases()[4], output)
            self.assertEqual(report["liquidations"], 5)
            self.assertEqual(report["stage_fill_counts"], {"1": 5})
            self.assertGreater(D(report["unused_liquidated_stage_capital"]), 0)
            self.assertGreater(D(report["declared_insurance_credit"]), 0)
            self.assertLess(D(report["net_pnl"]), 0)
            self.assertEqual(report["end_open_baskets"], [])
            closed = json.loads((output / "closed-baskets.json").read_text())
            self.assertTrue(all(r["liquidated"] and r["stages"] == 1 for r in closed))

    def test_open_end_valued_without_forced_profit_exit(self):
        streams = fixture(hours=68)
        for symbol in SYMBOLS:
            source = streams[symbol, "funding"]
            streams[symbol, "funding"] = replace(source, rows=tuple(r for r in source.rows if r.timestamp < source.end))
        with TemporaryDirectory() as directory:
            report = run(streams, cases()[0], Path(directory) / "run")
            self.assertEqual(report["closed_baskets"], 0)
            self.assertEqual(len(report["end_open_baskets"]), 5)
            self.assertLess(D(report["open_net_pnl"]), 0)
            self.assertEqual(D(report["net_pnl"]), D(report["open_net_pnl"]))

    def test_foreign_or_incomplete_axes_fail_before_output(self):
        streams = fixture()
        del streams["BTCUSDT", "mark"]
        with TemporaryDirectory() as directory:
            output = Path(directory) / "run"
            with self.assertRaisesRegex(ValueError, "complete"):
                run(streams, cases()[0], output)
            self.assertFalse(output.exists())
        streams = fixture()
        source = streams["BTCUSDT", "mark"]
        streams["BTCUSDT", "mark"] = replace(
            source, start=source.start + timedelta(hours=1), rows=source.rows[1:])
        with self.assertRaisesRegex(ValueError, "window"):
            validate_cohort(streams)

    def test_existing_output_cannot_be_reused(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / "run"
            output.mkdir()
            sentinel = output / "journal.jsonl"
            sentinel.write_text("preserve")
            with self.assertRaises(FileExistsError):
                run(fixture(), cases()[0], output)
            self.assertEqual(sentinel.read_text(), "preserve")

    def test_digest_cache_preserves_bytes_and_new_immutable_replacements(self):
        profile = cases()[0].profile()
        before = primitive(profile)
        self.assertEqual(profile.profile_digest, type(profile).profile_digest.func(profile))
        self.assertEqual(profile.plan.plan_digest, type(profile.plan).plan_digest.func(profile.plan))
        self.assertEqual(primitive(profile), before)
        changed = replace(profile, protection_hours=4)
        self.assertNotEqual(changed.profile_digest, profile.profile_digest)
        self.assertEqual(changed.profile_digest, type(changed).profile_digest.func(changed))
        self.assertEqual(_record_fields.cache_info().maxsize, 128)
        self.assertEqual(_record_hints.cache_info().maxsize, 128)
        for value in (profile, profile.plan, (profile, "ä", D(".0001"), AT, None, True, 3),
                      {"nested": [1, "ä", False]}, ("a", ("b", D("2.00")))):
            self.assertEqual(fast_digest(value), digest(value))
        self.assertEqual(_encoded(profile), json.dumps(
            primitive(profile), sort_keys=True, separators=(",", ":"), allow_nan=False))

    def test_omitting_empty_flat_quotes_preserves_all_economic_results(self):
        streams, scenario = fixture(crash=True), cases()[4]
        bindings = tuple(sorted({s.data_digest for s in streams.values()}))
        with TemporaryDirectory() as directory:
            optimized = run_scenario(streams, scenario, Path(directory) / "optimized", "a" * 64, bindings)
            complete = run_scenario(streams, scenario, Path(directory) / "complete", "a" * 64, bindings,
                                    full_flat_quotes=True)
            for key in ("net_pnl", "fees", "funding_net", "declared_insurance_credit",
                        "maximum_event_drawdown_pct", "stage_fill_counts", "capital_rejections",
                        "account_warning_hours", "time_weighted_posted_margin", "liquidations",
                        "end_open_baskets", "final_halt_reasons"):
                with self.subTest(key=key):
                    self.assertEqual(optimized[key], complete[key])


if __name__ == "__main__":
    unittest.main()
