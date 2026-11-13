#!/usr/bin/env python3
"""Run frozen native cases or the explicit H1 entry comparison; create-only."""
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / name) for name in ("packages/trading/src", "packages/marketdata/src")]

from investalo_marketdata.binance_futures_hourly import load_hourly_snapshot
from investalo_marketdata.futures_capital_backtest import run_scenario, validate_cohort, VERSION
from investalo_marketdata.futures_research_profile import PROTOCOL_SHA256, load_economic_protocol, ModerateEconomicScenario
from investalo_marketdata.futures_grid_profile import MODERATE_PROTOCOL_FILE, MODERATE_PROTOCOL_SHA256
from decimal import Decimal
from investalo_marketdata.snapshot import canonical, decode_json, iso

PREFLIGHT_SHA256 = "2252c6f78054a482a2eb67ecdc344d517aeb46083ce518141ccf0c00b549064c"
CASH_PROTOCOL_SHA256 = "1dfc67d29dcc5f89e72a610d43823b7041470810f10e3757d7fd2d135effb4fa"
H1_PROTOCOL_SHA256 = "23aefed3d96ff6cb9eb6b404209fc67f227529904131463941ec0c2fb7cb39f1"
BASELINE_RECEIPT_SHA256 = "979880a5b9fdcadc1a8aa8f11f23e7e1af158c86b68d4ea3d27c2b282470476e"
REALIZED_PROTOCOL_SHA256 = "719716bcc813c1fa22de769c2b86ed43d72b4e0d29a9d133065c06cf0cbf339a"
H1_RECEIPT_SHA256 = "3c6fdfb5b1c5ec6129f9bc7e4c4f1368ec19761f06e0d628707f8b72f12ed130"
RESERVED_PROTOCOL_SHA256 = "b1892df1eac4a66f157b0576b1efef7017f0e62bccc10c2bedb110441316be21"
REALIZED_RECEIPT_SHA256 = "893bfedeb260b9f4b44589c2719a9135e4876ceda72c87f6285a5294b0c952db"
GRID_PROTOCOL_SHA256 = "8f24a3f0d9a7ba0af3daf497bf5ed2925a5478db35da138ed96a2b95afe84a8d"
RESERVED_RECEIPT_SHA256 = "4e7d902c7127b317932c75e3b3878ffcaa3971c7863f077f477d2ca490713cec"
LEVERAGE_PROTOCOL_SHA256 = "c2d458f9a62331e94c96865fa7bc4a78039a3996e7de89180abc716edc2a2ac3"
GRID_RECEIPT_SHA256 = "727911a2f49e9814c9aa488ad365a4e451dc7ae86bd933d0d522acb9f95debfd"
LEVERAGE_RECEIPT_SHA256 = "a1c7c03a0e6487f22024edf586d5a0378e88fe16beed764e4af4de1e00786dde"


def cash_protocol():
    raw = (ROOT / "docs/research-protocols/futures-capital-cash-20261112.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != CASH_PROTOCOL_SHA256:
        raise ValueError("frozen corrected cash protocol changed")
    return CASH_PROTOCOL_SHA256


def h1_protocol():
    raw = (ROOT / "docs/research-protocols/futures-capital-h1-entry-20261112.json").read_bytes()
    baseline = (ROOT / "docs/research-protocols/futures-capital-cash-market-receipt-20261112.json").read_bytes()
    if (hashlib.sha256(raw).hexdigest() != H1_PROTOCOL_SHA256
            or hashlib.sha256(baseline).hexdigest() != BASELINE_RECEIPT_SHA256):
        raise ValueError("frozen H1 comparison or verified H4 baseline changed")
    return H1_PROTOCOL_SHA256


def realized_protocol():
    raw = (ROOT / "docs/research-protocols/futures-capital-h1-realized-cost-20261112.json").read_bytes()
    baseline = (ROOT / "docs/research-protocols/futures-capital-h1-entry-market-receipt-20261112.json").read_bytes()
    if (hashlib.sha256(raw).hexdigest() != REALIZED_PROTOCOL_SHA256
            or hashlib.sha256(baseline).hexdigest() != H1_RECEIPT_SHA256):
        raise ValueError("frozen realized-cost comparison or verified H1 baseline changed")
    return REALIZED_PROTOCOL_SHA256


def reserved_protocol():
    raw = (ROOT / "docs/research-protocols/futures-capital-h1-reserved-cash-20261113.json").read_bytes()
    baseline = (ROOT / "docs/research-protocols/futures-capital-h1-realized-cost-market-receipt-20261112.json").read_bytes()
    if (hashlib.sha256(raw).hexdigest() != RESERVED_PROTOCOL_SHA256
            or hashlib.sha256(baseline).hexdigest() != REALIZED_RECEIPT_SHA256):
        raise ValueError("frozen reserved-budget comparison or verified Q44 baseline changed")
    return RESERVED_PROTOCOL_SHA256


def grid_protocol():
    bindings = {
        "docs/research-protocols/futures-capital-current-grid-20261113.json": GRID_PROTOCOL_SHA256,
        "docs/research-protocols/futures-capital-h1-reserved-cash-market-receipt-20261113.json": RESERVED_RECEIPT_SHA256,
        "docs/research-protocols/futures-bitget-classic-contracts-20261113.json": "2fd4704081bdf1df22d45b56780cfd7c1ffc6c18cb8dac97b9a6c83e331091f6",
        "docs/research-protocols/futures-bitget-classic-contracts-receipt-20261113.json": "61c50ac6bc85b86ee176f1c7d926153d899f16c4b4cbeec35437a1a1a37d6e5c",
    }
    for name, expected in bindings.items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
            raise ValueError("frozen grid protocol/source/baseline changed")
    return GRID_PROTOCOL_SHA256


def leverage_protocol():
    grid_protocol()
    for name, expected in (
        ("futures-capital-grid-leverage-20261113.json", LEVERAGE_PROTOCOL_SHA256),
        ("futures-capital-current-grid-market-receipt-20261113.json", GRID_RECEIPT_SHA256),
    ):
        if hashlib.sha256((ROOT / "docs/research-protocols" / name).read_bytes()).hexdigest() != expected:
            raise ValueError("frozen leverage comparison or verified 2x grid reference changed")
    return LEVERAGE_PROTOCOL_SHA256


def grid_reference():
    """Reuse the fully restored 2x result, rechecking all four local output bytes."""
    raw = (ROOT / "docs/research-protocols/futures-capital-current-grid-market-receipt-20261113.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != GRID_RECEIPT_SHA256:
        raise ValueError("foreign grid reference receipt")
    receipt = decode_json(raw)
    if (not receipt["full_journal_restore_verified"]
            or not receipt["implementation_start_end_verified"]
            or receipt["protocol_sha256"] != GRID_PROTOCOL_SHA256
            or len(receipt["reports"]) != 1 or len(receipt["artifacts"]) != 4
            or receipt["reports"][0]["scenario_id"] != "base-h1-2x"):
        raise ValueError("complete original 2x grid reference required")
    folder = ROOT / "infra/local/futures-capital-research/20261113-h1-current-grid"
    expected = {f"base-h1-2x/{name}" for name in
                ("journal.jsonl", "equity.jsonl", "closed-baskets.json", "report.json")}
    if {a["file"] for a in receipt["artifacts"]} != expected:
        raise ValueError("fixed reference artifacts required")
    for artifact in receipt["artifacts"]:
        path = folder / artifact["file"]
        h = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                h.update(block)
        if path.stat().st_size != artifact["bytes"] or h.hexdigest() != artifact["sha256"]:
            raise ValueError("original 2x artifact changed")
    return receipt["reports"][0]


def moderate_protocol():
    leverage_protocol()
    if hashlib.sha256((ROOT / MODERATE_PROTOCOL_FILE).read_bytes()).hexdigest() != MODERATE_PROTOCOL_SHA256:
        raise ValueError("frozen moderate leverage protocol changed")
    return MODERATE_PROTOCOL_SHA256


def leverage_references():
    """Verify all twelve previous output bytes without repeating native jobs."""
    baseline = grid_reference()
    raw = (ROOT / "docs/research-protocols/futures-capital-grid-leverage-market-receipt-20261113.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != LEVERAGE_RECEIPT_SHA256:
        raise ValueError("foreign higher leverage reference receipt")
    receipt = decode_json(raw)
    ids = ("base-h1-5x", "base-h1-10x")
    expected = {f"{s}/{n}" for s in ids for n in
                ("journal.jsonl", "equity.jsonl", "closed-baskets.json", "report.json")}
    if (not receipt["full_journal_restore_verified"] or not receipt["implementation_start_end_verified"]
            or receipt["protocol_sha256"] != LEVERAGE_PROTOCOL_SHA256
            or receipt["reference_report"] != baseline
            or tuple(r["scenario_id"] for r in receipt["reports"]) != ids
            or len(receipt["artifacts"]) != 8
            or {a["file"] for a in receipt["artifacts"]} != expected):
        raise ValueError("complete higher leverage references required")
    folder = ROOT / "infra/local/futures-capital-research/20261113-h1-grid-leverage"
    for artifact in receipt["artifacts"]:
        path = folder / artifact["file"]
        h = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                h.update(block)
        if path.stat().st_size != artifact["bytes"] or h.hexdigest() != artifact["sha256"]:
            raise ValueError("original higher leverage artifact changed")
    return [baseline, *receipt["reports"]]


IMPLEMENTATION_FILES = (
    "packages/trading/src/investalo_trading/futures_risk.py",
    "packages/trading/src/investalo_trading/futures_ledger.py",
    "packages/trading/src/investalo_trading/futures_capital_research.py",
    "packages/trading/src/investalo_trading/futures_capital_signals.py",
    "packages/trading/src/investalo_trading/futures_capital_journal.py",
    "packages/marketdata/src/investalo_marketdata/futures_research_profile.py",
    "packages/marketdata/src/investalo_marketdata/futures_capital_backtest.py",
    "infra/scripts/backtest-futures-capital.py",
)
GRID_IMPLEMENTATION_FILES = (*IMPLEMENTATION_FILES,
    "packages/trading/src/investalo_trading/futures_capital_grid.py",
    "packages/marketdata/src/investalo_marketdata/futures_grid_profile.py",
    "packages/marketdata/src/investalo_marketdata/futures_broker_calibration.py")


def implementation_hashes(files):
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in files}


def load_sources():
    raw = (ROOT / "docs/research-protocols/futures-capital-preflight-receipt-20261112.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != PREFLIGHT_SHA256:
        raise ValueError("frozen source/economic preflight changed")
    receipt = decode_json(raw)
    if receipt["protocol_sha256"] != PROTOCOL_SHA256 or len(receipt["artifacts"]) != 15:
        raise ValueError("foreign native preflight")
    source = ROOT / "infra/local/futures-h1-research-data/20261112-native-network"
    streams, digests = {}, []
    for entry in receipt["artifacts"]:
        filename = f'{entry["symbol"]}-{entry["kind"]}.json'
        if filename != entry["file"]:
            raise ValueError("fixed native filename required")
        path = source / filename
        if path.stat().st_size > 16 * 1024 * 1024:
            raise ValueError("source exceeds bounded size")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != entry["file_sha256"]:
            raise ValueError("native source hash mismatch")
        stream = load_hourly_snapshot(raw.decode())
        if (stream.data_digest != entry["data_digest"] or len(stream.rows) != entry["rows"]
                or stream.symbol != entry["symbol"] or stream.kind != entry["kind"]):
            raise ValueError("native dataset binding mismatch")
        streams[stream.symbol, stream.kind] = stream
        digests.append(entry["data_digest"])
    validate_cohort(streams)
    anchor = streams["BNBUSDT", "trade"]
    if iso(anchor.start) != "2022-08-01T00:00:00Z" or iso(anchor.end) != "2025-08-01T00:00:00Z":
        raise ValueError("frozen research window required; no holdout")
    return streams, tuple(sorted(digests))


def progress(scenario_id, hours, equity):
    print(f"{scenario_id}: {hours}/26304 closed hours, model equity {equity:.2f}", flush=True)


def main():
    scenarios = load_economic_protocol(
        (ROOT / "docs/research-protocols/futures-capital-economics-20261112.json").read_bytes())
    corrected = len(sys.argv) == 3 and sys.argv[1] == "--cash-budgets"
    moderate = len(sys.argv) == 3 and sys.argv[1] == "--h1-grid-moderate-leverage"
    leverage_grids = moderate or len(sys.argv) == 3 and sys.argv[1] == "--h1-grid-leverage"
    grids = leverage_grids or len(sys.argv) == 3 and sys.argv[1] == "--h1-current-grids"
    reserved = grids or len(sys.argv) == 3 and sys.argv[1] == "--h1-reserved-cash"
    realized = reserved or len(sys.argv) == 3 and sys.argv[1] == "--h1-realized-costs"
    h1 = realized or len(sys.argv) == 3 and sys.argv[1] == "--h1-entries"
    if not corrected and not h1 and (len(sys.argv) != 2 or sys.argv[1].startswith("--")):
        raise SystemExit("usage: backtest-futures-capital.py [--cash-budgets|--h1-entries|--h1-realized-costs|--h1-reserved-cash|--h1-current-grids|--h1-grid-leverage|--h1-grid-moderate-leverage] NEW_OUTPUT_DIRECTORY")
    budget_protocol = (moderate_protocol() if moderate else leverage_protocol() if leverage_grids else grid_protocol() if grids else reserved_protocol() if reserved else realized_protocol() if realized else h1_protocol() if h1
                       else cash_protocol() if corrected else None)
    reference = leverage_references() if moderate else grid_reference() if leverage_grids else None
    if moderate:
        base = next(s for s in scenarios if s.scenario_id == "base-h1-2x")
        scenarios = tuple(ModerateEconomicScenario(f"base-h1-{v}x", 1, Decimal(v),
                          "base", base.path, base.costs) for v in (3, 4))
    elif leverage_grids:
        scenarios = tuple(s for s in scenarios if s.scenario_id in ("base-h1-5x", "base-h1-10x"))
        if tuple(s.scenario_id for s in scenarios) != ("base-h1-5x", "base-h1-10x"):
            raise ValueError("complete ordered native leverage cases required")
    elif h1:
        scenarios = tuple(s for s in scenarios if s.scenario_id == "base-h1-2x")
    protocol_digest = budget_protocol or PROTOCOL_SHA256
    output = Path(sys.argv[-1]).resolve()
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    implementation_files = GRID_IMPLEMENTATION_FILES if grids else IMPLEMENTATION_FILES
    before_hashes = implementation_hashes(implementation_files) if grids else None
    # Small development host: retain one cohort, one journal, one scenario.
    streams, digests = load_sources()
    reports = []
    for scenario in scenarios:
        print(f"{scenario.scenario_id}: verified sources; starting full market replay and restore", flush=True)
        report = run_scenario(streams, scenario, output / scenario.scenario_id,
                              protocol_digest, digests, progress=progress,
                              cash_budget_protocol=budget_protocol, entry_hours=1 if h1 else 4,
                              realized_exit_costs=realized, reserved_cash=reserved, current_grids=grids,
                              grid_leverage_comparison=leverage_grids, moderate_grid_leverage=moderate)
        reports.append(report)
        print(f"{scenario.scenario_id}: restored complete journal; net {report['net_pnl']}", flush=True)
    artifacts = []
    for scenario in scenarios:
        for name in ("journal.jsonl", "equity.jsonl", "closed-baskets.json", "report.json"):
            path = output / scenario.scenario_id / name
            h = hashlib.sha256()
            with path.open("rb") as handle:
                for block in iter(lambda: handle.read(1024 * 1024), b""):
                    h.update(block)
            artifacts.append({"file": f"{scenario.scenario_id}/{name}",
                              "bytes": path.stat().st_size, "sha256": h.hexdigest()})
    after_hashes = implementation_hashes(implementation_files)
    frozen_protocol = moderate_protocol() if moderate else leverage_protocol() if leverage_grids else grid_protocol() if grids else None
    if grids and (after_hashes != before_hashes or frozen_protocol != budget_protocol):
        raise ValueError("grid implementation/reference changed during fold; no success receipt")
    if leverage_grids and (leverage_references() if moderate else grid_reference()) != reference:
        raise ValueError("2x reference changed during leverage fold; no success receipt")
    receipt = {
        "schema_version": VERSION, "completed_at": iso(datetime.now(timezone.utc)),
        "protocol_sha256": protocol_digest, "economic_protocol_sha256": PROTOCOL_SHA256,
        "preflight_sha256": PREFLIGHT_SHA256,
        "budget_variant": "own-cash-active-ranges" if corrected or h1 else "historical-gross-all-slots",
        "entry_timeframe": "H1" if h1 else "H4",
        "baseline_receipt_sha256": GRID_RECEIPT_SHA256 if leverage_grids else RESERVED_RECEIPT_SHA256 if grids else REALIZED_RECEIPT_SHA256 if reserved else H1_RECEIPT_SHA256 if realized else BASELINE_RECEIPT_SHA256 if h1 else None,
        "realized_exit_costs": realized,
        "research_start": "2022-08-01T00:00:00Z", "research_end_exclusive": "2025-08-01T00:00:00Z",
        "implementation_sha256": hashlib.sha256(
            (ROOT / "packages/marketdata/src/investalo_marketdata/futures_capital_backtest.py").read_bytes()).hexdigest(),
        "implementation_files": after_hashes,
        "reports": reports, "artifacts": artifacts, "performance_evaluated": True,
        "full_journal_restore_verified": True, "holdout_requested": False,
        "python_version": sys.version.split()[0], "parallel_scenarios": 1,
        "historical_broker_rules_verified": False, "execution_enabled": False,
    }
    if reserved:
        receipt["budget_variant"] = "own-wallet-costs-isolated-funding"
        receipt["reserved_cash"] = True
    if grids:
        receipt.update(
            current_grids=True, grid_source_sha256="2fd4704081bdf1df22d45b56780cfd7c1ffc6c18cb8dac97b9a6c83e331091f6",
            implementation_start_end_verified=True, broker_admission_verified=False,
            comparison="current-bitget-grids-on-native-binance-h1-2x")
    if leverage_grids:
        receipt.update(
            comparison="current-bitget-grids-native-binance-h1-fixed-leverage-2-5-10",
            grid_leverage_comparison=True, reference_report=reference,
            reference_artifacts_verified=True, reference_native_job_repeated=False)
    if moderate:
        receipt.pop("reference_report")
        receipt.update(
            comparison="current-bitget-grids-native-binance-h1-fixed-leverage-2-3-4-5-10",
            moderate_grid_leverage=True, reference_reports=reference,
            higher_leverage_receipt_sha256=LEVERAGE_RECEIPT_SHA256)
    with (output / "receipt.json").open("x") as handle:
        handle.write(canonical(receipt) + "\n")
    print(f"all {len(scenarios)} declared comparisons complete: {output / 'receipt.json'}", flush=True)


if __name__ == "__main__":
    main()
