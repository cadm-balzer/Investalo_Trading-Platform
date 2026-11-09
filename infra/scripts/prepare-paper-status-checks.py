#!/usr/bin/env python3
"""Rollback preflight, then optionally apply reviewed011 ONLY to fixture DB."""
import argparse
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
    root = Path(__file__).resolve().parents[2]
    if os.geteuid() != 0:
        raise ValueError()
    prep = runpy.run_path(str(root/"infra/scripts/prepare-paper-storage-checks.py"))
    sql = prep["sql"]
    directory = root/"services/api/migrations"
    recorded = dict(json.loads(sql(
        "SELECT json_agg(json_build_array(version,checksum)) FROM platform.schema_migrations;")))
    for number in range(1, 11):
        path, = directory.glob(f"{number:03}_*.sql")
        if recorded.get(path.stem) != hashlib.sha256(path.read_bytes()).hexdigest():
            raise ValueError()
    path = directory/"011_paper_status.sql"
    content, digest = path.read_text(), hashlib.sha256(path.read_bytes()).hexdigest()
    if path.stem in recorded:
        if recorded[path.stem] != digest:
            raise ValueError()
        print("PASS: immutable fixture011 matches")
        return
    tenant, foreign, user, account, foreign_account = [uuid4() for _ in range(5)]
    sql(f"""
BEGIN; SET LOCAL ROLE investalo_migration;
{content}
INSERT INTO platform.tenants(id,name) VALUES('{tenant}','Paper status preflight'),
('{foreign}','Foreign paper status preflight');
INSERT INTO platform.users(id,oidc_issuer,oidc_subject)
VALUES('{user}','https://paper-status.invalid','{user}');
INSERT INTO platform.memberships(tenant_id,user_id,role) VALUES('{tenant}','{user}','viewer');
INSERT INTO platform.accounts(tenant_id,id,name,broker,mode,currency)
VALUES('{tenant}','{account}','Own Paper','bitget','paper','USDT'),
('{foreign}','{foreign_account}','Foreign Paper','bitget','paper','USDT');
RESET ROLE; SET LOCAL SESSION AUTHORIZATION investalo_runtime;
SELECT set_config('app.user_id','{user}',true),set_config('app.tenant_id','{tenant}',true),
set_config('app.oidc_issuer','https://paper-status.invalid',true),
set_config('app.oidc_subject','{user}',true);
DO $$
DECLARE epoch bigint;
BEGIN
 SELECT auth_epoch INTO epoch FROM platform.users WHERE id='{user}';
 IF (SELECT count(*) FROM platform.paper_status_rows(epoch,clock_timestamp()))<>1
    OR (SELECT account_id FROM platform.paper_status_rows(epoch,clock_timestamp()))<>'{account}'::uuid THEN
  RAISE EXCEPTION 'Own paper projection rejected';
 END IF;
 PERFORM set_config('app.tenant_id','{foreign}',true);
 BEGIN
  PERFORM platform.paper_status_rows(epoch,clock_timestamp());
  RAISE EXCEPTION 'Foreign membership accepted';
 EXCEPTION WHEN insufficient_privilege THEN NULL; END;
 PERFORM set_config('app.tenant_id','',true);
 BEGIN
  PERFORM platform.paper_status_rows(epoch,clock_timestamp());
  RAISE EXCEPTION 'Missing context accepted';
 EXCEPTION WHEN insufficient_privilege THEN NULL; END;
END $$;
ROLLBACK;
""")
    print("PASS:011 DDL, actual runtime own/foreign/missing-context preflight fully rolled back")
    if args.apply_reviewed:
        sql("BEGIN; SELECT pg_advisory_xact_lock(724809361); SET LOCAL ROLE investalo_migration;\n"
            +content+f"\nINSERT INTO platform.schema_migrations(version,checksum)"
            f" VALUES('{path.stem}','{digest}'); COMMIT;")
        print("PASS: reviewed011 applied ONLY to fixture database")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("Paper status fixture preparation rejected; sensitive output suppressed") from None
