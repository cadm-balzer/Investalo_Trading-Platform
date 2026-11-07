"""Compute from frozen data and publish only under an unexpired fenced lease."""
import hashlib
import json
from threading import Event, Thread
from decimal import localcontext

from psycopg.types.json import Jsonb
from investalo_marketdata import dump_snapshot, load_snapshot, to_trading_candles
from investalo_api.research_result import Result
from investalo_api.research_spec import cost_assumptions, public_source, simulator, specification

from .settings import WorkerSettings, assert_research_identity
from .health import mark_healthy


class SnapshotInvalid(ValueError):
    pass


class ConfigurationMismatch(ValueError):
    pass


def compute_result(job: dict, dataset: dict) -> dict:
    if (
        job["frozen_specification"] != specification()
        or any(job[name] != specification()[name] for name in
               ("strategy_version", "configuration_digest", "cost_digest"))
    ):
        raise ConfigurationMismatch("Frozen configuration differs")
    try:
        snapshot = load_snapshot(json.dumps(dataset["snapshot"]))
        canonical = dump_snapshot(snapshot)
        if (
            hashlib.sha256(canonical.encode()).hexdigest() != dataset["content_digest"]
            or snapshot.data_digest != dataset["data_digest"]
            or snapshot.data_digest != job["payload"]["data_digest"]
            or snapshot.symbol != job["payload"]["symbol"]
            or str(job["dataset_id"]) != job["payload"]["dataset_id"]
            or dataset["purpose"] == "holdout"
            or snapshot.synthetic and dataset["purpose"] != "test"
        ):
            raise ValueError("Snapshot binding differs")
    except Exception:
        raise SnapshotInvalid("Frozen snapshot rejected") from None
    simulation = simulator().run(
        to_trading_candles(snapshot), tenant_id=str(job["tenant_id"]),
        account_id=f"research:{job['job_id']}",
    )
    if (
        simulation.configuration_digest != job["configuration_digest"]
        or simulation.cost_digest != job["cost_digest"]
        or simulation.manual_fills_fabricated
    ):
        raise ConfigurationMismatch("Simulation differs from frozen configuration")
    full_curve = simulation.equity_curve
    indices = display_indices(full_curve)
    result = {
        "schema_version": "backtest-result/1", "symbol": snapshot.symbol, "timeframe": "4h",
        "strategy_version": simulation.strategy_version,
        "data_digest": snapshot.data_digest, "simulation_data_digest": simulation.data_digest,
        "configuration_digest": simulation.configuration_digest, "cost_digest": simulation.cost_digest,
        "source": public_source(snapshot.source.record()), "synthetic": snapshot.synthetic,
        "bar_count": len(snapshot.candles), "start": snapshot.candles[0].open_time.isoformat(),
        "end": snapshot.candles[-1].close_time.isoformat(), "coverage": snapshot.coverage.record(),
        "net_pnl": format(simulation.net_pnl, "f"),
        "maximum_drawdown_fraction": format(simulation.maximum_drawdown_fraction, "f"),
        "profit_factor": format(simulation.profit_factor, "f") if simulation.profit_factor is not None else None,
        "closed_basket_count": simulation.closed_basket_count,
        "equity_curve": [
            {"at": full_curve[index].at.isoformat(), "equity": format(full_curve[index].equity, "f")}
            for index in indices
        ],
        "equity_curve_sampled": len(full_curve) > 2000,
        "cost_assumptions": cost_assumptions(),
        "validation": {
            "status": "not_evaluated",
            "reason": (
                "Synthetische Testdaten sind kein wirtschaftlicher Leistungsnachweis."
                if snapshot.synthetic else
                "Unabhängiger Holdout, Kostenkalibrierung und Mindeststichprobe sind nicht bewertet."
            ),
        },
    }
    return Result.model_validate(result).model_dump(mode="json")


def display_indices(curve):
    """Metrics use full data; display preserves endpoints and the worst DD pair."""
    if len(curve) <= 2000:
        return range(len(curve))
    peak = 0
    worst_peak = worst_trough = 0
    worst_fraction = 0
    with localcontext() as context:
        context.prec = 36
        for index, point in enumerate(curve):
            if point.equity > curve[peak].equity:
                peak = index
            fraction = (curve[peak].equity - point.equity) / curve[peak].equity
            if fraction > worst_fraction:
                worst_fraction, worst_peak, worst_trough = fraction, peak, index
    protected = {
        0, len(curve)-1, worst_peak, worst_trough,
        min(range(len(curve)), key=lambda i: curve[i].equity),
        max(range(len(curve)), key=lambda i: curve[i].equity),
    }
    budget = 2000 - len(protected)
    uniform = {(index * (len(curve)-1)) // (budget-1) for index in range(budget)}
    return sorted(protected | uniform)


class Lease:
    def __init__(self, settings: WorkerSettings, job: dict, seconds: int):
        self.settings, self.job, self.seconds = settings, job, seconds
        self.stop_event, self.lost = Event(), Event()
        self.thread = Thread(target=self.maintain, daemon=True, name="research-lease")

    def maintain(self):
        while not self.stop_event.wait(self.seconds / 3):
            try:
                with self.settings.connect() as db:
                    assert_research_identity(db)
                    renewed = db.execute(
                        "SELECT platform.research_heartbeat(%s,%s,%s) AS accepted",
                        (self.job["job_id"], self.job["attempt_token"], self.seconds),
                    ).fetchone()["accepted"]
                if not renewed:
                    self.lost.set()
                    return
                mark_healthy()
            except Exception:
                self.lost.set()
                return

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_exc):
        self.stop_event.set()
        self.thread.join(timeout=4)


def run_once(settings: WorkerSettings, *, lease_seconds: int = 120) -> bool:
    with settings.connect() as db:
        tenant = assert_research_identity(db)
        job = db.execute(
            "SELECT * FROM platform.research_claim(%s)", (lease_seconds,),
        ).fetchone()
    if job is None:
        mark_healthy()
        return False
    if job["tenant_id"] != tenant:
        raise ValueError("Research tenant changed")
    mark_healthy()
    with Lease(settings, job, lease_seconds) as lease:
        code = None
        try:
            with settings.connect() as db:
                assert_research_identity(db)
                dataset = db.execute(
                    "SELECT snapshot,content_digest,data_digest,purpose "
                    "FROM platform.research_datasets WHERE tenant_id=%s AND id=%s",
                    (tenant, job["dataset_id"]),
                ).fetchone()
            if dataset is None:
                raise SnapshotInvalid("Frozen snapshot unavailable")
            result = compute_result(job, dataset)
        except SnapshotInvalid:
            code = "snapshot_invalid"
        except ConfigurationMismatch:
            code = "configuration_mismatch"
        except Exception:
            # No exception messages, stack traces, query inputs or credentials
            # become job failures or worker logs.
            code = "simulation_failed"
        if lease.lost.is_set():
            return True  # Discard stale work; expired lease can be reclaimed.
        with settings.connect() as db:
            assert_research_identity(db)
            if code:
                db.execute(
                    "SELECT platform.research_fail(%s,%s,%s)",
                    (job["job_id"], job["attempt_token"], code),
                )
            else:
                db.execute(
                    "SELECT platform.research_complete(%s,%s,%s)",
                    (job["job_id"], job["attempt_token"], Jsonb(result)),
                )
        mark_healthy()
    return True
