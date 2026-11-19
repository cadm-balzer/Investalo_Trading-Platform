#!/usr/bin/env python3
"""Rolled-back019 preflight; optional isolated-fixture application only."""
import argparse
import hashlib
import json
import os
from pathlib import Path

from importlib.util import spec_from_file_location, module_from_spec


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply-reviewed", action="store_true")
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise ValueError()
    root = Path(__file__).resolve().parents[2]
    module_spec = spec_from_file_location("trading_store_checks",
        root/"infra/scripts/prepare-demo-trading-store-checks.py")
    module = module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    sql = module.sql
    directory = root/"services/api/migrations"
    recorded = dict(json.loads(sql(
        "SELECT json_agg(json_build_array(version,checksum)) FROM platform.schema_migrations;")))
    for number in range(1, 19):
        path, = directory.glob(f"{number:03}_*.sql")
        if recorded.get(path.stem) != hashlib.sha256(path.read_bytes()).hexdigest():
            raise ValueError()
    query = ("SELECT json_agg(json_build_array(version,checksum) ORDER BY version)"
             " FROM platform.schema_migrations;")
    development = sql(query, database="investalo")
    print("PASS: immutable fixture001–018 verified", flush=True)
    path = directory/"019_demo_trading_passkey.sql"
    content, checksum = path.read_text(), hashlib.sha256(path.read_bytes()).hexdigest()
    if path.stem in recorded:
        if recorded[path.stem] != checksum:
            raise ValueError()
        print("PASS: immutable fixture019 matches", flush=True)
    else:
        preflight = """
RESET ROLE;
DO $$ DECLARE proc_row record; n integer;
BEGIN
 SELECT count(*) INTO n FROM pg_proc p JOIN pg_namespace s ON s.oid=p.pronamespace
 WHERE s.nspname='platform' AND (p.proname LIKE 'demo_trading_passkey_%'
   OR p.proname LIKE 'demo_trading_credential_%passkey%'
   OR p.proname='guard_demo_trading_passkey_credential_authorization');
 IF n<>18 THEN RAISE EXCEPTION 'function set'; END IF;
 FOR proc_row IN SELECT p.* FROM pg_proc p JOIN pg_namespace s ON s.oid=p.pronamespace
 WHERE s.nspname='platform' AND (p.proname LIKE 'demo_trading_passkey_%'
   OR p.proname LIKE 'demo_trading_credential_%passkey%'
   OR p.proname='guard_demo_trading_passkey_credential_authorization')
 LOOP
  IF proc_row.proowner<>(SELECT oid FROM pg_roles WHERE rolname='investalo_migration')
    OR proc_row.proconfig<>ARRAY['search_path=pg_catalog']
    OR EXISTS(SELECT FROM aclexplode(coalesce(proc_row.proacl,acldefault('f',proc_row.proowner))) a
              WHERE a.grantee=0 AND a.privilege_type='EXECUTE')
    OR has_function_privilege('investalo_research_worker',proc_row.oid,'EXECUTE')
    OR has_function_privilege('investalo_runtime',proc_row.oid,'EXECUTE')
       <> (proc_row.proname IN ('demo_trading_passkey_credential_prepare',
           'demo_trading_passkey_credential_authorize','demo_trading_passkey_action_claim',
           'demo_trading_passkey_action_finish','demo_trading_passkey_action_read_grant'))
    OR has_function_privilege('investalo_credentials_worker',proc_row.oid,'EXECUTE')
       <> (proc_row.proname IN ('demo_trading_credential_consume_passkey_authorization',
           'demo_trading_credential_lock_passkey_authorization',
           'demo_trading_credential_lock_passkey_execution',
           'demo_trading_credential_finish_passkey_authorization'))
    OR proc_row.prosecdef <> (proc_row.proname NOT IN (
           'guard_demo_trading_passkey_credential_authorization',
           'demo_trading_credential_passkey_metadata',
           'demo_trading_passkey_credential_receipt','demo_trading_passkey_credential_claims_valid'))
    THEN RAISE EXCEPTION 'function boundary'; END IF;
 END LOOP;
 SELECT count(*) INTO n FROM pg_class c JOIN pg_namespace s ON s.oid=c.relnamespace
 WHERE s.nspname='platform' AND c.relkind='r' AND c.relname IN (
   'demo_trading_passkey_credential_authorizations',
   'demo_trading_passkey_credential_authorization_audit',
   'demo_trading_passkey_credential_completion_audit')
 AND c.relrowsecurity AND c.relforcerowsecurity
 AND c.relowner=(SELECT oid FROM pg_roles WHERE rolname='investalo_migration')
 AND NOT has_table_privilege('investalo_runtime',c.oid,'SELECT')
 AND NOT has_table_privilege('investalo_credentials_worker',c.oid,'SELECT');
 IF n<>3 THEN RAISE EXCEPTION 'table boundary'; END IF;
END $$;
SET LOCAL SESSION AUTHORIZATION investalo_runtime;
DO $$ BEGIN
 BEGIN
  PERFORM platform.demo_trading_credential_consume_passkey_authorization('{}');
  RAISE EXCEPTION 'unexpected consume privilege';
 EXCEPTION WHEN insufficient_privilege THEN NULL; END;
 BEGIN
  PERFORM * FROM platform.demo_trading_passkey_action_claim(NULL,NULL,NULL,0,1);
  RAISE EXCEPTION 'unexpected missing actor';
 EXCEPTION WHEN insufficient_privilege THEN NULL; END;
END $$;
RESET SESSION AUTHORIZATION;
ROLLBACK;
"""
        sql("BEGIN; SET LOCAL ROLE investalo_migration;\n"+content+preflight)
        print("PASS:019 DDL/actor/ACL/RLS/owner/searchpath preflight rolled back", flush=True)
        if args.apply_reviewed:
            sql("BEGIN; SELECT pg_advisory_xact_lock(724809361); SET LOCAL ROLE investalo_migration;\n"
                +content+f"\nINSERT INTO platform.schema_migrations(version,checksum)"
                f" VALUES('{path.stem}','{checksum}'); COMMIT;")
            print("PASS:019 applied ONLY to investalo_credentials_checks", flush=True)
    if development != sql(query, database="investalo"):
        raise ValueError()
    print("PASS: actual development migration set unchanged")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("Demo trading passkey preparation rejected; sensitive output suppressed") from None
