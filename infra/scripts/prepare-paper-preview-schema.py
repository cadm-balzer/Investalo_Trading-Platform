#!/usr/bin/env python3
"""Preflight reviewed008–012; explicit application to the existing development DB."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
from uuid import uuid4


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply-reviewed-development", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    base = runpy.run_path(str(root/"infra/scripts/provision-paper-development.py"))
    base["protected"](root/"infra/local/READY", 0, 0o400)
    if os.geteuid() != 0:
        raise ValueError()
    sql = runpy.run_path(str(root/"infra/scripts/prepare-paper-storage-checks.py"))["sql"]
    files = sorted((root/"services/api/migrations").glob("*.sql"))
    expected = {p.stem: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    query = "SELECT json_agg(json_build_array(version,checksum)) FROM platform.schema_migrations;"
    fixture = dict(json.loads(sql(query)))
    normal = dict(json.loads(sql(query, "investalo")))
    if len(files) != 12 or fixture != expected or normal not in (
            dict(list(expected.items())[:7]), expected):
        raise ValueError()
    sql(base["check_roles_sql"](), "postgres")
    if normal == expected:
        print("PASS: development012 and fixture012 immutable hashes match")
        return
    contents = "\n".join(p.read_text() for p in files[7:])
    # Full ordered DDL and actual restricted own/foreign-context projection;
    # all rows/grants/functions in this transaction are discarded.
    tenant, foreign, user, account, other = [uuid4() for _ in range(5)]
    probe = f"""
INSERT INTO platform.tenants(id,name) VALUES('{tenant}','Paper preview preflight'),
('{foreign}','Foreign preview preflight');
INSERT INTO platform.users(id,oidc_issuer,oidc_subject,reauth_after)
VALUES('{user}','https://preview-preflight.invalid','{user}',clock_timestamp());
INSERT INTO platform.memberships(tenant_id,user_id,role) VALUES('{tenant}','{user}','viewer');
INSERT INTO platform.accounts(tenant_id,id,name,broker,mode,currency)
VALUES('{tenant}','{account}','Own Paper','bitget','paper','USDT'),
('{foreign}','{other}','Foreign Paper','bitget','paper','USDT');
RESET ROLE; SET LOCAL SESSION AUTHORIZATION investalo_runtime;
SELECT set_config('app.user_id','{user}',true),set_config('app.tenant_id','{tenant}',true),
set_config('app.oidc_issuer','https://preview-preflight.invalid',true),
set_config('app.oidc_subject','{user}',true);
DO $$
DECLARE epoch bigint;
BEGIN
 SELECT auth_epoch INTO epoch FROM platform.users WHERE id='{user}';
 IF (SELECT count(*) FROM platform.paper_status_rows(epoch,clock_timestamp()))<>1
    OR (SELECT account_id FROM platform.paper_status_rows(epoch,clock_timestamp()))<>'{account}'::uuid
    OR has_table_privilege(SESSION_USER,'platform.paper_checkpoints','INSERT,UPDATE,DELETE') THEN
   RAISE EXCEPTION 'Preview read projection rejected';
 END IF;
 BEGIN
  PERFORM platform.paper_status_rows(epoch+1,clock_timestamp());
  RAISE EXCEPTION 'Stale epoch accepted';
 EXCEPTION WHEN insufficient_privilege THEN NULL; END;
 BEGIN
  PERFORM platform.paper_status_rows(epoch,clock_timestamp()-interval '1 day');
  RAISE EXCEPTION 'Old authentication accepted';
 EXCEPTION WHEN insufficient_privilege THEN NULL; END;
 PERFORM set_config('app.tenant_id','{foreign}',true);
 BEGIN
  PERFORM platform.paper_status_rows(epoch,clock_timestamp());
  RAISE EXCEPTION 'Foreign context accepted';
 EXCEPTION WHEN insufficient_privilege THEN NULL; END;
END $$;
RESET SESSION AUTHORIZATION; SET LOCAL ROLE investalo_migration;
UPDATE platform.memberships SET active=false WHERE tenant_id='{tenant}' AND user_id='{user}';
RESET ROLE; SET LOCAL SESSION AUTHORIZATION investalo_runtime;
SELECT set_config('app.tenant_id','{tenant}',true);
DO $$
DECLARE epoch bigint:=0;
BEGIN
 BEGIN
  PERFORM platform.paper_status_rows(epoch,clock_timestamp());
  RAISE EXCEPTION 'Revoked membership accepted';
 EXCEPTION WHEN insufficient_privilege THEN NULL; END;
END $$;
"""
    sql("BEGIN; SET LOCAL ROLE investalo_migration;\n"+contents+probe+"\nROLLBACK;", "investalo")
    if dict(json.loads(sql(query, "investalo"))) != normal:
        raise ValueError()
    print("PASS: complete008–012 DDL/runtime own/foreign/epoch/OIDC/revocation preflight rolled back")
    if args.apply_reviewed_development:
        ledger = "\n".join(
            f"INSERT INTO platform.schema_migrations(version,checksum) VALUES('{p.stem}','{expected[p.stem]}');"
            for p in files[7:])
        sql("BEGIN; SELECT pg_advisory_xact_lock(724809361); SET LOCAL ROLE investalo_migration;\n"
            +contents+"\n"+ledger+"\nCOMMIT;", "investalo")
        if dict(json.loads(sql(query, "investalo"))) != expected:
            raise ValueError()
        print("PASS: reviewed008–012 applied atomically ONLY to existing development investalo")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("Paper preview schema rejected; sensitive output suppressed") from None
