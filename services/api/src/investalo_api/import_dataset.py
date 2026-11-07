"""Operator-only immutable snapshot import, without network access or output of bars."""
import argparse
import hashlib
import json
from pathlib import Path
from uuid import UUID, uuid4

from investalo_marketdata import dump_snapshot, load_snapshot
from psycopg.types.json import Jsonb

from .database import connect
from .research_spec import public_source
from .settings import Settings


def import_dataset(settings: Settings, *, tenant_id: UUID, purpose: str, payload: str | bytes) -> UUID:
    if purpose not in ("research", "test", "holdout") or len(payload) > 8388608:
        raise ValueError("Invalid research import")
    snapshot = load_snapshot(payload)
    if snapshot.synthetic and purpose != "test":
        raise ValueError("Synthetic snapshots require purpose=test")
    if not 1 <= len(snapshot.candles) <= 10000:
        raise ValueError("Research snapshot size unsupported")
    source = snapshot.source.record()
    public_source(source)  # Reject unreviewed source types before persistence.
    canonical = dump_snapshot(snapshot)
    if len(canonical.encode()) > 8388608:
        raise ValueError("Canonical snapshot exceeds bounded import")
    content_digest = hashlib.sha256(canonical.encode()).hexdigest()
    with connect(settings) as db:
        if db.execute("SELECT current_user AS name").fetchone()["name"] != "investalo_migration":
            raise ValueError("Snapshot import requires investalo_migration")
        row = db.execute(
            "INSERT INTO platform.research_datasets("
            "tenant_id,id,purpose,symbol,timeframe,source,synthetic,bar_count,starts_at,ends_at,"
            "data_digest,content_digest,coverage_complete,snapshot) "
            "VALUES(%s,%s,%s,%s,'4h',%s,%s,%s,%s,%s,%s,%s,%s,%s) "
            "ON CONFLICT(tenant_id,purpose,symbol,data_digest) DO NOTHING RETURNING id",
            (tenant_id, uuid4(), purpose, snapshot.symbol, Jsonb(source), snapshot.synthetic,
             len(snapshot.candles), snapshot.candles[0].open_time, snapshot.candles[-1].close_time,
             snapshot.data_digest, content_digest, snapshot.coverage.complete,
             Jsonb(json.loads(canonical))),
        ).fetchone()
        if row is None:
            row = db.execute(
                "SELECT id,content_digest FROM platform.research_datasets WHERE tenant_id=%s AND purpose=%s "
                "AND symbol=%s AND data_digest=%s",
                (tenant_id, purpose, snapshot.symbol, snapshot.data_digest),
            ).fetchone()
            if row is None or row["content_digest"] != content_digest:
                # The candle digest excludes retrieval time and coverage. Never
                # silently treat changed provenance as the already frozen input.
                raise ValueError("Existing immutable snapshot provenance differs")
        return row["id"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant-id", type=UUID, required=True)
    parser.add_argument("--purpose", choices=("research", "test", "holdout"), required=True)
    parser.add_argument("--file", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.file.stat().st_size > 8388608:
            raise ValueError("Snapshot exceeds bounded import")
        identifier = import_dataset(
            Settings.from_environment(), tenant_id=args.tenant_id,
            purpose=args.purpose, payload=args.file.read_bytes(),
        )
    except Exception:
        raise SystemExit("Research import rejected; no snapshot contents emitted") from None
    print(f"Immutable research dataset imported: dataset_id={identifier}")


if __name__ == "__main__":
    main()
