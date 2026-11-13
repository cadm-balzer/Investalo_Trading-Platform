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
from investalo_marketdata.futures_research_profile import PROTOCOL_SHA256, load_economic_protocol
from investalo_marketdata.snapshot import canonical, decode_json, iso

PREFLIGHT_SHA256 = "2252c6f78054a482a2eb67ecdc344d517aeb46083ce518141ccf0c00b549064c"
CASH_PROTOCOL_SHA256 = "1dfc67d29dcc5f89e72a610d43823b7041470810f10e3757d7fd2d135effb4fa"
H1_PROTOCOL_SHA256 = "23aefed3d96ff6cb9eb6b404209fc67f227529904131463941ec0c2fb7cb39f1"
BASELINE_RECEIPT_SHA256 = "979880a5b9fdcadc1a8aa8f11f23e7e1af158c86b68d4ea3d27c2b282470476e"
REALIZED_PROTOCOL_SHA256 = "719716bcc813c1fa22de769c2b86ed43d72b4e0d29a9d133065c06cf0cbf339a"
H1_RECEIPT_SHA256 = "3c6fdfb5b1c5ec6129f9bc7e4c4f1368ec19761f06e0d628707f8b72f12ed130"
RESERVED_PROTOCOL_SHA256 = "b1892df1eac4a66f157b0576b1efef7017f0e62bccc10c2bedb110441316be21"
REALIZED_RECEIPT_SHA256 = "893bfedeb260b9f4b44589c2719a9135e4876ceda72c87f6285a5294b0c952db"


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
    reserved = len(sys.argv) == 3 and sys.argv[1] == "--h1-reserved-cash"
    realized = len(sys.argv) == 3 and sys.argv[1] in ("--h1-realized-costs", "--h1-reserved-cash")
    h1 = len(sys.argv) == 3 and sys.argv[1] in ("--h1-entries", "--h1-realized-costs", "--h1-reserved-cash")
    if not corrected and not h1 and (len(sys.argv) != 2 or sys.argv[1].startswith("--")):
        raise SystemExit("usage: backtest-futures-capital.py [--cash-budgets|--h1-entries|--h1-realized-costs|--h1-reserved-cash] NEW_OUTPUT_DIRECTORY")
    budget_protocol = (reserved_protocol() if reserved else realized_protocol() if realized else h1_protocol() if h1
                       else cash_protocol() if corrected else None)
    if h1:
        scenarios = tuple(s for s in scenarios if s.scenario_id == "base-h1-2x")
    protocol_digest = budget_protocol or PROTOCOL_SHA256
    output = Path(sys.argv[-1]).resolve()
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    # Small development host: retain one cohort, one journal, one scenario.
    streams, digests = load_sources()
    reports = []
    for scenario in scenarios:
        print(f"{scenario.scenario_id}: verified sources; starting full market replay and restore", flush=True)
        report = run_scenario(streams, scenario, output / scenario.scenario_id,
                              protocol_digest, digests, progress=progress,
                              cash_budget_protocol=budget_protocol, entry_hours=1 if h1 else 4,
                              realized_exit_costs=realized, reserved_cash=reserved)
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
    receipt = {
        "schema_version": VERSION, "completed_at": iso(datetime.now(timezone.utc)),
        "protocol_sha256": protocol_digest, "economic_protocol_sha256": PROTOCOL_SHA256,
        "preflight_sha256": PREFLIGHT_SHA256,
        "budget_variant": "own-cash-active-ranges" if corrected or h1 else "historical-gross-all-slots",
        "entry_timeframe": "H1" if h1 else "H4",
        "baseline_receipt_sha256": REALIZED_RECEIPT_SHA256 if reserved else H1_RECEIPT_SHA256 if realized else BASELINE_RECEIPT_SHA256 if h1 else None,
        "realized_exit_costs": realized,
        "research_start": "2022-08-01T00:00:00Z", "research_end_exclusive": "2025-08-01T00:00:00Z",
        "implementation_sha256": hashlib.sha256(
            (ROOT / "packages/marketdata/src/investalo_marketdata/futures_capital_backtest.py").read_bytes()).hexdigest(),
        "implementation_files": {
            name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in (
                "packages/trading/src/investalo_trading/futures_risk.py",
                "packages/trading/src/investalo_trading/futures_ledger.py",
                "packages/trading/src/investalo_trading/futures_capital_research.py",
                "packages/trading/src/investalo_trading/futures_capital_signals.py",
                "packages/trading/src/investalo_trading/futures_capital_journal.py",
                "packages/marketdata/src/investalo_marketdata/futures_research_profile.py",
                "packages/marketdata/src/investalo_marketdata/futures_capital_backtest.py",
                "infra/scripts/backtest-futures-capital.py",
            )
        },
        "reports": reports, "artifacts": artifacts, "performance_evaluated": True,
        "full_journal_restore_verified": True, "holdout_requested": False,
        "python_version": sys.version.split()[0], "parallel_scenarios": 1,
        "historical_broker_rules_verified": False, "execution_enabled": False,
    }
    if reserved:
        receipt["budget_variant"] = "own-wallet-costs-isolated-funding"
        receipt["reserved_cash"] = True
    with (output / "receipt.json").open("x") as handle:
        handle.write(canonical(receipt) + "\n")
    print(f"all {len(scenarios)} declared comparisons complete: {output / 'receipt.json'}", flush=True)


if __name__ == "__main__":
    main()
