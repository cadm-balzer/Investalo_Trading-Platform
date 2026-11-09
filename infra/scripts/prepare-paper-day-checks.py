#!/usr/bin/env python3
"""Rollback a real bound-writer day preflight; optionally apply012 ONLY to fixture."""
import argparse
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import runpy
from uuid import uuid4


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply-reviewed", action="store_true")
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise ValueError()
    root = Path(__file__).resolve().parents[2]
    prep = runpy.run_path(str(root/"infra/scripts/prepare-paper-storage-checks.py"))
    sql = prep["sql"]
    from investalo_trading import Candle, PaperRunner
    directory = root/"services/api/migrations"
    recorded = dict(json.loads(sql(
        "SELECT json_agg(json_build_array(version,checksum)) FROM platform.schema_migrations;")))
    for number in range(1, 12):
        path, = directory.glob(f"{number:03}_*.sql")
        if recorded.get(path.stem) != hashlib.sha256(path.read_bytes()).hexdigest():
            raise ValueError()
    path = directory/"012_paper_day_basis.sql"
    content, checksum = path.read_text(), hashlib.sha256(path.read_bytes()).hexdigest()
    if path.stem in recorded:
        if recorded[path.stem] != checksum:
            raise ValueError()
        print("PASS: immutable fixture012 matches")
        return
    tenant, account = uuid4(), uuid4()
    runner = PaperRunner(str(tenant), str(account))
    at = datetime(2026, 1, 2, tzinfo=timezone.utc)
    old = runner.start(at-timedelta(seconds=1))
    bars = tuple(Candle(s, at-timedelta(hours=4), at,
                       Decimal(100), Decimal(100), Decimal(100), Decimal(100))
                 for s in ("BTCUSDT", "ETHUSDT"))
    day = runner.day(old, bars, now=at+timedelta(seconds=7)).checkpoint
    payloads = [runner.dump(cp) for cp in (old, day)]
    hashes = [hashlib.sha256(p.encode()).hexdigest() for p in payloads]
    literals = ["'"+p.replace("'", "''")+"'" for p in payloads]
    sql(f"""
BEGIN; SET LOCAL ROLE investalo_migration;
{content}
INSERT INTO platform.tenants(id,name) VALUES('{tenant}','Paper day preflight');
INSERT INTO platform.accounts(tenant_id,id,name,broker,mode,currency,status)
VALUES('{tenant}','{account}','Synthetic Paper','bitget','paper','USDT','ready');
INSERT INTO platform.paper_role_bindings(database_role,tenant_id,account_id)
VALUES('investalo_paper_tests','{tenant}','{account}') ON CONFLICT(database_role)
DO UPDATE SET tenant_id=excluded.tenant_id,account_id=excluded.account_id,active=true;
RESET ROLE; SET LOCAL SESSION AUTHORIZATION investalo_paper_tests;
SELECT platform.paper_initialize({literals[0]},'{hashes[0]}');
SELECT platform.paper_commit(0,'{hashes[0]}',{literals[1]},'{hashes[1]}');
SELECT platform.paper_commit(0,'{hashes[0]}',{literals[1]},'{hashes[1]}');
RESET SESSION AUTHORIZATION; SET LOCAL ROLE investalo_migration;
DO $$
BEGIN
 IF (SELECT count(*) FROM platform.paper_journal WHERE tenant_id='{tenant}'
     AND entry->>'input_kind'='day')<>1 THEN
   RAISE EXCEPTION 'Day replay duplicated';
 END IF;
 IF (SELECT checkpoint::jsonb#>>'{{checkpoint,state,account,trading_day}}'
     FROM platform.paper_checkpoints WHERE tenant_id='{tenant}')<>'2026-01-02' THEN
   RAISE EXCEPTION 'Day commit rejected';
 END IF;
END $$;
ROLLBACK;
""")
    print("PASS:012 DDL, actual bound writer/day/replay preflight fully rolled back")
    if args.apply_reviewed:
        sql("BEGIN; SELECT pg_advisory_xact_lock(724809361); SET LOCAL ROLE investalo_migration;\n"
            +content+f"\nINSERT INTO platform.schema_migrations(version,checksum)"
            f" VALUES('{path.stem}','{checksum}'); COMMIT;")
        print("PASS: reviewed012 applied ONLY to fixture database")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("Paper day fixture preparation rejected; sensitive output suppressed") from None
