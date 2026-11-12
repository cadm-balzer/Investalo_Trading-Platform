#!/usr/bin/env python3
"""Run all ten frozen native research cases, create-only; no network or holdout."""
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
    if len(sys.argv) != 2:
        raise SystemExit("usage: backtest-futures-capital.py NEW_OUTPUT_DIRECTORY (all ten frozen cases)")
    output = Path(sys.argv[1]).resolve()
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    # Small development host: retain one cohort, one journal, one scenario.
    streams, digests = load_sources()
    reports = []
    for scenario in scenarios:
        print(f"{scenario.scenario_id}: verified sources; starting full market replay and restore", flush=True)
        report = run_scenario(streams, scenario, output / scenario.scenario_id,
                              PROTOCOL_SHA256, digests, progress=progress)
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
        "protocol_sha256": PROTOCOL_SHA256, "preflight_sha256": PREFLIGHT_SHA256,
        "research_start": "2022-08-01T00:00:00Z", "research_end_exclusive": "2025-08-01T00:00:00Z",
        "implementation_sha256": hashlib.sha256(
            (ROOT / "packages/marketdata/src/investalo_marketdata/futures_capital_backtest.py").read_bytes()).hexdigest(),
        "reports": reports, "artifacts": artifacts, "performance_evaluated": True,
        "full_journal_restore_verified": True, "holdout_requested": False,
        "python_version": sys.version.split()[0], "parallel_scenarios": 1,
        "historical_broker_rules_verified": False, "execution_enabled": False,
    }
    with (output / "receipt.json").open("x") as handle:
        handle.write(canonical(receipt) + "\n")
    print(f"all ten declared comparisons complete: {output / 'receipt.json'}", flush=True)


if __name__ == "__main__":
    main()
