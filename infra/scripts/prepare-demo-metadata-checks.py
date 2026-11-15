#!/usr/bin/env python3
"""Rolled-back017 metadata/ACL preflight; optional fixture-only application."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply-reviewed", action="store_true")
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise ValueError()
    root = Path(__file__).resolve().parents[2]
    sql = runpy.run_path(str(root / "infra/scripts/prepare-paper-storage-checks.py"))["sql"]
    directory = root / "services/api/migrations"
    recorded = dict(json.loads(sql(
        "SELECT json_agg(json_build_array(version,checksum)) FROM platform.schema_migrations;")))
    for number in range(1, 17):
        path, = directory.glob(f"{number:03}_*.sql")
        if recorded.get(path.stem) != hashlib.sha256(path.read_bytes()).hexdigest():
            raise ValueError()
    development = sql("SELECT json_agg(json_build_array(version,checksum) ORDER BY version) "
                      "FROM platform.schema_migrations;", database="investalo")
    print("PASS: fixture001–016 immutable checksums verified", flush=True)
    path = directory / "017_demo_credential_action_context.sql"
    content, checksum = path.read_text(), hashlib.sha256(path.read_bytes()).hexdigest()
    if path.stem in recorded:
        if recorded[path.stem] != checksum:
            raise ValueError()
        print("PASS: immutable fixture017 matches", flush=True)
    else:
        sql("BEGIN; SET LOCAL ROLE investalo_migration;\n" + content + """
RESET ROLE; SET LOCAL SESSION AUTHORIZATION investalo_runtime;
DO $$ BEGIN
 BEGIN
  PERFORM platform.demo_credential_action_context(NULL,0,1);
  RAISE EXCEPTION 'unexpected missing-actor permission';
 EXCEPTION WHEN insufficient_privilege THEN NULL; END;
 BEGIN
  PERFORM 1 FROM platform.demo_credential_connections;
  RAISE EXCEPTION 'unexpected private table permission';
 EXCEPTION WHEN insufficient_privilege THEN NULL; END;
END $$;
RESET SESSION AUTHORIZATION; SET LOCAL ROLE investalo_migration;
DO $$ BEGIN
 IF NOT EXISTS(SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
     WHERE n.nspname='platform' AND p.proname='demo_credential_action_context'
     AND p.prosecdef AND p.proconfig=ARRAY['search_path=pg_catalog']
     AND p.proowner=(SELECT oid FROM pg_roles WHERE rolname='investalo_migration')
     AND has_function_privilege('investalo_runtime',p.oid,'EXECUTE')
     AND NOT has_function_privilege('investalo_research_worker',p.oid,'EXECUTE')
     AND NOT has_function_privilege('investalo_credentials_worker',p.oid,'EXECUTE')) THEN
   RAISE EXCEPTION 'function boundary'; END IF;
END $$;
ROLLBACK;
""")
        print("PASS:017 DDL/actor/ACL/owner/searchpath preflight fully rolled back", flush=True)
        if args.apply_reviewed:
            sql("BEGIN; SELECT pg_advisory_xact_lock(724809361); SET LOCAL ROLE investalo_migration;\n"
                + content + f"\nINSERT INTO platform.schema_migrations(version,checksum)"
                f" VALUES('{path.stem}','{checksum}'); COMMIT;")
            print("PASS: reviewed017 applied ONLY to investalo_credentials_checks", flush=True)
    if development != sql("SELECT json_agg(json_build_array(version,checksum) ORDER BY version) "
                          "FROM platform.schema_migrations;", database="investalo"):
        raise ValueError()
    print("PASS: development migration set unchanged")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("Demo metadata fixture preparation rejected; sensitive output suppressed") from None
