#!/usr/bin/env python3
"""Rolled-back018 preflight, optional application to the isolated fixture only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


def sql(statement, database="investalo_credentials_checks"):
    if database not in ("investalo_credentials_checks", "investalo"):
        raise ValueError()
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(["bash", str(root/"infra/scripts/compose.sh"), "exec", "-T", "postgres",
        "psql", "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1", "-v", "VERBOSITY=sqlstate",
        "-U", "investalo_admin", "-d", database], input=statement, text=True, capture_output=True, timeout=30)
    if result.returncode:
        code = re.search(r"ERROR:\s+([0-9A-Z]{5})\b", result.stderr)
        print("FAIL: PostgreSQL state "+(code.group(1) if code else "unknown"), flush=True)
        raise ValueError()
    return result.stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply-reviewed", action="store_true")
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise ValueError()
    root = Path(__file__).resolve().parents[2]
    directory = root/"services/api/migrations"
    recorded = dict(json.loads(sql(
        "SELECT json_agg(json_build_array(version,checksum)) FROM platform.schema_migrations;")))
    for number in range(1, 18):
        path, = directory.glob(f"{number:03}_*.sql")
        if recorded.get(path.stem) != hashlib.sha256(path.read_bytes()).hexdigest():
            raise ValueError()
    development_query = ("SELECT json_agg(json_build_array(version,checksum) ORDER BY version)"
                         " FROM platform.schema_migrations;")
    development = sql(development_query, database="investalo")
    print("PASS: immutable fixture001–017 verified", flush=True)
    path = directory/"018_demo_trading_credentials.sql"
    content, checksum = path.read_text(), hashlib.sha256(path.read_bytes()).hexdigest()
    if path.stem in recorded:
        if recorded[path.stem] != checksum:
            raise ValueError()
        print("PASS: immutable fixture018 matches", flush=True)
    else:
        preflight = """
RESET ROLE;
DO $$ DECLARE proc_row record; n integer;
BEGIN
 SELECT count(*) INTO n FROM pg_proc p JOIN pg_namespace s ON s.oid=p.pronamespace
  WHERE s.nspname='platform' AND p.proname IN
   ('demo_trading_authorities_valid','demo_credential_owned_profile',
    'demo_trading_credential_create','demo_trading_credential_read',
    'demo_trading_credential_rewrap','demo_trading_credential_revoke',
    'demo_credential_profile_metadata','demo_trading_credential_passkey_metadata',
    'demo_trading_credential_action_context');
 IF n<>9 THEN RAISE EXCEPTION 'function set'; END IF;
 FOR proc_row IN SELECT p.*,s.nspname FROM pg_proc p JOIN pg_namespace s ON s.oid=p.pronamespace
  WHERE s.nspname='platform' AND p.proname IN
   ('demo_trading_authorities_valid','demo_credential_owned_profile',
    'demo_trading_credential_create','demo_trading_credential_read',
    'demo_trading_credential_rewrap','demo_trading_credential_revoke',
    'demo_credential_profile_metadata','demo_trading_credential_passkey_metadata',
    'demo_trading_credential_action_context')
 LOOP
  IF proc_row.proowner<>(SELECT oid FROM pg_roles WHERE rolname='investalo_migration')
    OR proc_row.proconfig<>ARRAY['search_path=pg_catalog']
    OR EXISTS(SELECT FROM aclexplode(coalesce(proc_row.proacl,acldefault('f',proc_row.proowner))) a
              WHERE a.grantee=0 AND a.privilege_type='EXECUTE')
    OR has_function_privilege('investalo_research_worker',proc_row.oid,'EXECUTE')
    OR has_function_privilege('investalo_runtime',proc_row.oid,'EXECUTE')
       <> (proc_row.proname='demo_trading_credential_action_context')
    OR has_function_privilege('investalo_credentials_worker',proc_row.oid,'EXECUTE')
       <> (proc_row.proname IN ('demo_trading_credential_create','demo_trading_credential_read',
                         'demo_trading_credential_rewrap','demo_trading_credential_revoke'))
    OR proc_row.prosecdef <> (proc_row.proname IN ('demo_credential_owned_profile',
       'demo_trading_credential_create','demo_trading_credential_read',
       'demo_trading_credential_rewrap','demo_trading_credential_revoke',
       'demo_trading_credential_action_context')) THEN
    RAISE EXCEPTION 'function boundary'; END IF;
 END LOOP;
 IF NOT EXISTS(SELECT FROM pg_class WHERE oid='platform.demo_credential_connections'::regclass
       AND relrowsecurity AND relforcerowsecurity)
   OR NOT EXISTS(SELECT FROM pg_constraint WHERE conrelid='platform.demo_credential_connections'::regclass
       AND contype='u' AND conkey=ARRAY[(SELECT attnum FROM pg_attribute
       WHERE attrelid='platform.demo_credential_connections'::regclass AND attname='broker_uid')]) THEN
   RAISE EXCEPTION 'registry boundary'; END IF;
END $$;
SET LOCAL ROLE investalo_migration;
DO $$ BEGIN
 IF NOT platform.demo_trading_authorities_valid('["coow","cpow","stow"]')
   OR platform.demo_trading_authorities_valid('["coow","cpow","stow","wwow"]')
   OR platform.demo_trading_authorities_valid('["stow","cpow","coow"]')
   OR platform.demo_trading_authorities_valid(NULL) THEN RAISE EXCEPTION 'rights boundary'; END IF;
END $$;
RESET ROLE; SET LOCAL SESSION AUTHORIZATION investalo_runtime;
DO $$ BEGIN
 BEGIN
  PERFORM platform.demo_trading_credential_create(NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,1,1);
  RAISE EXCEPTION 'unexpected write privilege';
 EXCEPTION WHEN insufficient_privilege THEN NULL; END;
 BEGIN
  PERFORM platform.demo_trading_credential_action_context(NULL,0,1);
  RAISE EXCEPTION 'unexpected missing actor';
 EXCEPTION WHEN insufficient_privilege THEN NULL; END;
 BEGIN
  PERFORM 1 FROM platform.demo_credential_connections;
  RAISE EXCEPTION 'unexpected table privilege';
 EXCEPTION WHEN insufficient_privilege THEN NULL; END;
END $$;
RESET SESSION AUTHORIZATION;
ROLLBACK;
"""
        sql("BEGIN; SET LOCAL ROLE investalo_migration;\n"+content+preflight)
        print("PASS:018 DDL/rights/registry/actor/ACL/owner/searchpath preflight rolled back", flush=True)
        if args.apply_reviewed:
            sql("BEGIN; SELECT pg_advisory_xact_lock(724809361); SET LOCAL ROLE investalo_migration;\n"
                + content + f"\nINSERT INTO platform.schema_migrations(version,checksum)"
                f" VALUES('{path.stem}','{checksum}'); COMMIT;")
            print("PASS:018 applied ONLY to investalo_credentials_checks", flush=True)
    if development != sql(development_query, database="investalo"):
        raise ValueError()
    print("PASS: actual development migration set unchanged")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("Demo trading store preparation rejected; sensitive output suppressed") from None
