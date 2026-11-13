"""Read-only audit against real reducers and synthetic native market inputs."""
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
import fcntl
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from investalo_marketdata.futures_admission_audit import audit_admissions, audit_json
from investalo_marketdata.futures_capital_backtest import run_scenario
from investalo_marketdata.binance_futures import FundingObservation
from test_futures_capital_backtest import fixture, cases, AT

D = Decimal


class CapitalAdmissionAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = TemporaryDirectory()
        cls.root = Path(cls.directory.name)
        cls.samples = {}
        for mode in ("normal", "premium", "funding"):
            streams = fixture(hours=48 if mode == "funding" else 20)
            if mode == "premium":
                for key, stream in tuple(streams.items()):
                    if key[1] == "mark":
                        streams[key] = replace(stream, rows=tuple(replace(
                            bar, **{name: getattr(bar, name) * D("1.001")
                                    for name in ("open", "high", "low", "close")})
                            for bar in stream.rows))
            if mode == "funding":
                for key, stream in tuple(streams.items()):
                    if key[1] == "funding":
                        streams[key] = replace(stream, rows=(FundingObservation(
                            AT + timedelta(hours=31), D(".1"), None, "Regular"),))
                    else:
                        streams[key] = replace(stream, rows=tuple(
                            replace(bar, open=D(124 if i < 31 else 110),
                                    high=D(124 if i < 31 else 110) * D("1.01"),
                                    low=D(124 if i < 31 else 110) * D(".995"),
                                    close=D(124 if i < 31 else 110)) if i >= 24 else bar
                            for i, bar in enumerate(stream.rows)))
            bindings = tuple(sorted(s.data_digest for s in streams.values()))
            output = cls.root / mode
            report = run_scenario(
                streams, cases()[0], output, "a" * 64, bindings,
                cash_budget_protocol="a" * 64, entry_hours=1,
                realized_exit_costs=True, reserved_cash=True)
            path = output / "journal.jsonl"
            cls.samples[mode] = (path, dict(
                profile_digest=report["profile_digest"], protocol_digest="a" * 64,
                dataset_digests=bindings, receipt=report["journal_receipt"],
                expected_rejections=report["capital_rejections"]))

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def audit(self, mode="normal", **overrides):
        path, args = self.samples[mode]
        return audit_admissions(path, **(args | overrides))

    def test_exact_allowed_entries_restore_without_writing_source(self):
        path, _ = self.samples["normal"]
        before = path.read_bytes(), path.stat().st_mtime_ns, path.stat().st_mode
        report = self.audit()
        self.assertEqual(report["accepted_entries"], 5)
        self.assertEqual(report["rejected_attempts"], 0)
        self.assertTrue(report["full_journal_restore_verified"])
        self.assertFalse(report["execution_enabled"])
        self.assertFalse(report["counterfactual_performance_evaluated"])
        self.assertEqual(before, (path.read_bytes(), path.stat().st_mtime_ns, path.stat().st_mode))

    def test_mark_premium_rejections_have_actual_capital_and_overlapping_reasons(self):
        report = self.audit("premium")
        self.assertEqual(report["accepted_entries"], 0)
        self.assertEqual(report["rejected_attempts"], 20)
        self.assertEqual(report["reason_counts"], {
            "fill_bound_below_mark": 20, "initial_margin_requirement": 20})
        self.assertEqual(report["rejected_cycle_stages"], 5)
        row = report["rejections"][0]
        self.assertEqual(row["stage"], 1)
        self.assertEqual(D(row["funding_net"]), 0)
        self.assertEqual(D(row["margin_committed"]), 0)
        self.assertGreater(D(row["mark_price"]), D(row["maximum_fill_price"]))
        self.assertGreater(D(row["declared_margin_shortfall"]), 0)
        self.assertEqual(D(row["available_isolated_after_entry"]), D(row["own_entry_capital"]))
        self.assertGreater(D(row["account_cash_after_entry"]), D(row["own_entry_capital"]))
        self.assertEqual(row["declared_initial_margin"], row["mark_initial_margin"])

    def test_final_receipt_and_counters_are_not_optional(self):
        _, args = self.samples["normal"]
        for override in (
            {"receipt": args["receipt"] | {"head": "0" * 64}},
            {"expected_rejections": {"initial_margin_requirement": 1}},
            {"receipt": args["receipt"] | {"execution_enabled": True}},
            {"expected_rejections": {"initial_margin_requirement": True}},
        ):
            with self.subTest(override=override), self.assertRaises(ValueError):
                self.audit(**override)

    def test_complete_rejection_evidence_exports_exact_decimal_strings_to_binary_file(self):
        report = self.audit("premium")
        raw = audit_json(report)
        self.assertIsInstance(raw, bytes)
        self.assertEqual(json.loads(raw), report)
        self.assertTrue(raw.endswith(b"\n"))
        self.assertIsInstance(report["rejections"][0]["declared_margin_shortfall"], str)
        path = self.root / "binary-export"
        with path.open("xb") as handle:
            handle.write(raw)
        self.assertEqual(path.read_bytes(), raw)
        with self.assertRaises(FileExistsError):
            path.open("xb")

    def test_funding_depletion_has_real_isolated_deficit_and_unused_manual_capital(self):
        report = self.audit("funding")
        self.assertEqual(report["accepted_entries"], 5)
        self.assertGreater(report["rejected_attempts"], 0)
        self.assertEqual(set(report["reason_counts"]), {"initial_margin_requirement"})
        row = report["rejections"][0]
        self.assertEqual(row["stage"], 2)
        self.assertLess(D(row["funding_net"]), 0)
        self.assertGreater(D(row["cost_restored"]), 0)
        self.assertLess(D(row["isolated_balance"]), D(row["margin_committed"]))
        self.assertGreater(D(row["declared_margin_shortfall"]), 0)
        self.assertGreater(D(row["unused_regular_capital"]), 0)
        self.assertGreater(D(row["manual_capital"]), 0)
        self.assertLess(D(row["restoration_capacity"]), D(".00000001"))

    def test_exact_profile_protocol_and_dataset_bindings(self):
        for override in ({"profile_digest": "b" * 64}, {"protocol_digest": "b" * 64},
                         {"dataset_digests": ("b" * 64,)}):
            with self.subTest(override=override), self.assertRaises(ValueError):
                self.audit(**override)

    def copied(self, name, data):
        path = self.root / name
        path.write_bytes(data)
        path.chmod(0o600)
        return path

    def test_chain_tampering_and_incomplete_lines_fail(self):
        path, args = self.samples["normal"]
        raw = path.read_bytes()
        records = raw.splitlines(keepends=True)
        changed = json.loads(records[1])
        changed["head"] = "0" * 64
        variants = (b"".join((records[0], json.dumps(changed).encode() + b"\n", *records[2:])),
                    raw[:-1], raw + b'{"duplicate":1,"duplicate":2}\n')
        for i, data in enumerate(variants):
            with self.subTest(i=i), self.assertRaises(ValueError):
                audit_admissions(self.copied(f"bad-{i}", data), **args)

    def test_missing_allowed_fill_fails_before_accepting_changed_chain(self):
        path, args = self.samples["normal"]
        records = path.read_bytes().splitlines(keepends=True)
        index = next(i for i, line in enumerate(records[1:], 1)
                     if json.loads(line)["command"]["kind"] == "entry")
        with self.assertRaisesRegex(ValueError, "missing allowed market entry"):
            audit_admissions(self.copied("missing-fill", b"".join(records[:index])), **args)

    def test_private_file_symlink_and_active_writer_are_rejected(self):
        path, args = self.samples["normal"]
        foreign = self.copied("foreign-mode", path.read_bytes())
        foreign.chmod(0o644)
        with self.assertRaises(ValueError):
            audit_admissions(foreign, **args)
        link = self.root / "symlink"
        link.symlink_to(path)
        with self.assertRaises(OSError):
            audit_admissions(link, **args)
        hard = self.root / "hardlink"
        os.link(foreign, hard)
        foreign.chmod(0o600)
        with self.assertRaises(ValueError):
            audit_admissions(hard, **args)
        with path.open("rb") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):
                self.audit()
