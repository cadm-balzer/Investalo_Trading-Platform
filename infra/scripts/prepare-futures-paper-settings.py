#!/usr/bin/env python3
"""Fully rolled-back013 preflight; optional application ONLY to fixture database."""
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
    if os.geteuid() != 0:
        raise ValueError()
    root = Path(__file__).resolve().parents[2]
    sql = runpy.run_path(str(root/"infra/scripts/prepare-paper-storage-checks.py"))["sql"]
    directory = root/"services/api/migrations"
    recorded = dict(json.loads(sql(
        "SELECT json_agg(json_build_array(version,checksum)) FROM platform.schema_migrations;")))
    for number in range(1, 13):
        path, = directory.glob(f"{number:03}_*.sql")
        if recorded.get(path.stem) != hashlib.sha256(path.read_bytes()).hexdigest():
            raise ValueError("fixture migration mismatch")
    print("PASS: fixture001–012 immutable checksums verified", flush=True)
    development = sql("SELECT json_agg(json_build_array(version,checksum) ORDER BY version) "
                      "FROM platform.schema_migrations;", database="investalo")
    path = directory/"013_futures_paper_settings.sql"
    content = path.read_text()
    checksum = hashlib.sha256(path.read_bytes()).hexdigest()
    if path.stem in recorded:
        if recorded[path.stem] != checksum:
            raise ValueError("immutable013 mismatch")
        print("PASS: immutable fixture013 matches")
        return
    tenant, foreign, user, account, foreign_account = [uuid4() for _ in range(5)]
    sql(f"""
BEGIN; SET LOCAL ROLE investalo_migration;
{content}
INSERT INTO platform.tenants(id,name) VALUES('{tenant}','Futures planning preflight'),
('{foreign}','Foreign planning preflight');
INSERT INTO platform.users(id,oidc_issuer,oidc_subject)
VALUES('{user}','https://futures-planning.invalid','{user}');
INSERT INTO platform.memberships(tenant_id,user_id,role) VALUES('{tenant}','{user}','trader');
INSERT INTO platform.accounts(tenant_id,id,name,broker,mode,currency)
VALUES('{tenant}','{account}','Own Paper','bitget','paper','USDT'),
('{foreign}','{foreign_account}','Foreign Paper','bitget','paper','USDT');
RESET ROLE; SET LOCAL SESSION AUTHORIZATION investalo_runtime;
SELECT set_config('app.user_id','{user}',true),set_config('app.tenant_id','{tenant}',true),
set_config('app.oidc_issuer','https://futures-planning.invalid',true),
set_config('app.oidc_subject','{user}',true);
INSERT INTO platform.futures_paper_settings VALUES('{tenant}','{account}',1,5,now());
INSERT INTO platform.futures_paper_settings_audit
VALUES('{tenant}','{account}',1,'{user}',5,now());
DO $$
BEGIN
 IF (SELECT count(*) FROM platform.futures_paper_settings)<>1 THEN RAISE EXCEPTION 'own read'; END IF;
 BEGIN
  INSERT INTO platform.futures_paper_settings VALUES('{foreign}','{foreign_account}',1,5,now());
  RAISE EXCEPTION 'foreign write';
 EXCEPTION WHEN insufficient_privilege THEN NULL; END;
 BEGIN
  DELETE FROM platform.futures_paper_settings; RAISE EXCEPTION 'delete granted';
 EXCEPTION WHEN insufficient_privilege THEN NULL; END;
 BEGIN
  UPDATE platform.futures_paper_settings_audit SET basket_limit=7; RAISE EXCEPTION 'audit mutable';
 EXCEPTION WHEN insufficient_privilege THEN NULL; END;
 BEGIN
  INSERT INTO platform.futures_paper_settings_audit
  VALUES('{tenant}','{account}',2,'{foreign}',5,now());
  RAISE EXCEPTION 'foreign actor';
 EXCEPTION WHEN insufficient_privilege THEN NULL; END;
 PERFORM set_config('app.tenant_id','{foreign}',true);
 IF EXISTS(SELECT FROM platform.futures_paper_settings) THEN RAISE EXCEPTION 'foreign read'; END IF;
END $$;
ROLLBACK;
""")
    print("PASS:013 DDL/own/foreign/actor/immutable audit preflight fully rolled back")
    if args.apply_reviewed:
        sql("BEGIN; SELECT pg_advisory_xact_lock(724809361); SET LOCAL ROLE investalo_migration;\n"
            +content+f"\nINSERT INTO platform.schema_migrations(version,checksum)"
            f" VALUES('{path.stem}','{checksum}'); COMMIT;")
        print("PASS: reviewed013 applied ONLY to investalo_credentials_checks")
    if development != sql("SELECT json_agg(json_build_array(version,checksum) ORDER BY version) "
                          "FROM platform.schema_migrations;", database="investalo"):
        raise ValueError("development migration changed")
    print("PASS: development migration set unchanged")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("Futures planning fixture preparation rejected; sensitive output suppressed") from None
