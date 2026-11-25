#!/usr/bin/env python3
"""Verify immutable 001–019, roll back020 preflight, optionally apply fixture only."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

# Fixed existing fixture SQL wrapper suppresses private PostgreSQL output.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from importlib import import_module
sql = import_module("prepare-demo-trading-store-checks").sql


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply-reviewed", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    directory = root/"services/api/migrations"
    query = "SELECT json_agg(json_build_array(version,checksum) ORDER BY version) FROM platform.schema_migrations;"
    development = sql(query, database="investalo")
    recorded = dict(json.loads(sql(query)))
    for number in range(1, 20):
        path, = directory.glob(f"{number:03}_*.sql")
        if recorded.get(path.stem) != hashlib.sha256(path.read_bytes()).hexdigest():
            raise ValueError()
    path = directory/"020_demo_worker_credential_read.sql"
    checksum = hashlib.sha256(path.read_bytes()).hexdigest()
    if path.stem in recorded:
        if recorded[path.stem] != checksum:
            raise ValueError()
    else:
        assertions = """
RESET ROLE;
DO $$ DECLARE p record;
BEGIN
 SELECT x.* INTO STRICT p FROM pg_proc x
  WHERE x.oid='platform.demo_worker_credential_read(uuid,bigint,text,text,bigint,bigint,bigint,bigint)'::regprocedure;
 IF p.proowner<>(SELECT oid FROM pg_roles WHERE rolname='investalo_migration')
   OR p.proconfig<>ARRAY['search_path=pg_catalog'] OR NOT p.prosecdef
   OR EXISTS(SELECT FROM aclexplode(p.proacl) a WHERE a.grantee=0)
   OR has_function_privilege('investalo_runtime',p.oid,'EXECUTE')
   OR has_function_privilege('investalo_research_worker',p.oid,'EXECUTE')
   OR NOT has_function_privilege('investalo_credentials_worker',p.oid,'EXECUTE') THEN
   RAISE EXCEPTION 'worker function boundary';
 END IF;
END $$;
ROLLBACK;
"""
        sql("BEGIN; SET LOCAL ROLE investalo_migration;\n"+path.read_text()+assertions)
        print("PASS:020 owner/searchpath/ACL preflight rolled back", flush=True)
        if args.apply_reviewed:
            sql("BEGIN; SELECT pg_advisory_xact_lock(724809361); SET LOCAL ROLE investalo_migration;\n"
                +path.read_text()+f"\nINSERT INTO platform.schema_migrations(version,checksum)"
                f" VALUES('{path.stem}','{checksum}'); COMMIT;")
            print("PASS:020 applied only to isolated fixture", flush=True)
    if sql(query, database="investalo") != development:
        raise ValueError()
    print("PASS:001–019 verified; actual development migration set unchanged", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("Worker store preparation rejected; sensitive output suppressed") from None
