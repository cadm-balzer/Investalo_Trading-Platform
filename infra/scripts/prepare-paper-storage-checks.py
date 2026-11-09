#!/usr/bin/env python3
"""Provision isolated paper test LOGIN; preflight010, optionally apply reviewed010."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import sys
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "packages/trading/src"))
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from investalo_trading import PaperRunner, Quote

ROOT = Path(__file__).resolve().parents[2]
LOCAL = ROOT / "infra/local"
MIGRATIONS = ROOT / "services/api/migrations"
DATABASE = "investalo_credentials_checks"


def sql(statement, database=DATABASE):
    result = subprocess.run([
        "bash", str(ROOT / "infra/scripts/compose.sh"), "exec", "-T", "postgres",
        "psql", "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1",
        "-U", "investalo_admin", "-d", database,
    ], input=statement, text=True, capture_output=True, timeout=30)
    if result.returncode:
        raise ValueError("Paper fixture preparation rejected")
    return result.stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply-reviewed", action="store_true")
    parser.add_argument("--rotate-test-secret", action="store_true",
                        help="Rotate ONLY the synthetic paper test LOGIN password.")
    args = parser.parse_args()
    if os.geteuid() != 0 or not (LOCAL / "READY").is_file() or LOCAL.is_symlink():
        raise ValueError()
    path = LOCAL / "paper_test_password"
    if not path.exists() and not path.is_symlink():
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o400)
        with os.fdopen(fd, "w") as stream:
            stream.write(secrets.token_urlsafe(48))
        os.chown(path, 10003, 10003)
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != 10003 or info.st_gid != 10003
            or stat.S_IMODE(info.st_mode) != 0o400):
        raise ValueError()
    if args.rotate_test_secret:
        fd = os.open(path, os.O_WRONLY | os.O_TRUNC | os.O_NOFOLLOW)
        with os.fdopen(fd, "w") as stream:
            stream.write(secrets.token_urlsafe(48))
    password = path.read_text()
    if not re.fullmatch("[A-Za-z0-9_-]{64}", password):
        raise ValueError()
    # Fixed role identifiers, strict generated secret on stdin, never argv/output.
    rotation = f"ALTER ROLE investalo_paper_tests PASSWORD '{password}';" if args.rotate_test_secret else ""
    sql(f"""
BEGIN;
SELECT pg_advisory_xact_lock(724809361);
DO $$
BEGIN
 IF EXISTS(SELECT FROM pg_roles WHERE rolname IN ('investalo_paper_worker','investalo_paper_tests')
   AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolbypassrls OR rolreplication
     OR (rolname='investalo_paper_worker' AND rolcanlogin)
     OR (rolname='investalo_paper_tests' AND NOT rolcanlogin))) THEN
   RAISE EXCEPTION 'Paper role drift';
 END IF;
 IF EXISTS(SELECT FROM pg_auth_members m JOIN pg_roles child ON child.oid=m.member
   JOIN pg_roles parent ON parent.oid=m.roleid
   WHERE child.rolname IN ('investalo_paper_worker','investalo_paper_tests')
   AND (child.rolname='investalo_paper_worker' OR parent.rolname<>'investalo_paper_worker'
        OR m.admin_option)) THEN RAISE EXCEPTION 'Paper membership drift'; END IF;
 IF NOT EXISTS(SELECT FROM pg_roles WHERE rolname='investalo_paper_worker') THEN
   CREATE ROLE investalo_paper_worker NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
     NOREPLICATION NOBYPASSRLS;
 END IF;
 IF NOT EXISTS(SELECT FROM pg_roles WHERE rolname='investalo_paper_tests') THEN
   CREATE ROLE investalo_paper_tests LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
     NOREPLICATION NOBYPASSRLS PASSWORD '{password}';
 END IF;
 GRANT investalo_paper_worker TO investalo_paper_tests;
 GRANT CONNECT ON DATABASE investalo_credentials_checks TO investalo_paper_tests;
 {rotation}
END $$;
COMMIT;
""", "postgres")
    if args.rotate_test_secret:
        print("PASS: ONLY synthetic paper test LOGIN secret rotated")
    sql("SELECT pg_reload_conf();", "postgres")
    recorded = dict(json.loads(sql(
        "SELECT json_agg(json_build_array(version,checksum)) FROM platform.schema_migrations;"
    )))
    files = sorted(MIGRATIONS.glob("*.sql"))
    for file in files:
        if file.name.startswith("010_"):
            continue
        if recorded.get(file.stem) != hashlib.sha256(file.read_bytes()).hexdigest():
            raise ValueError()
    file = MIGRATIONS / "010_paper_state.sql"
    content = file.read_text()
    checksum = hashlib.sha256(file.read_bytes()).hexdigest()
    if file.stem in recorded:
        if recorded[file.stem] != checksum:
            raise ValueError()
        print("PASS: immutable fixture010 checksum matches")
    else:
        tenant, account = uuid4(), uuid4()
        runner = PaperRunner(str(tenant), str(account))
        at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        initial = runner.start(at)
        first = runner.quote(initial, Quote("BTCUSDT", at, Decimal(100), Decimal(100)), now=at).checkpoint
        at += timedelta(seconds=1)
        second = runner.quote(first, Quote("BTCUSDT", at, Decimal(101), Decimal(101)), now=at).checkpoint
        payloads = [runner.dump(c) for c in (initial, first, second)]
        hashes = [hashlib.sha256(p.encode()).hexdigest() for p in payloads]
        literals = ["'" + p.replace("'", "''") + "'" for p in payloads]
        sql("BEGIN; SET LOCAL ROLE investalo_migration;\n" + content + f"""
INSERT INTO platform.tenants(id,name) VALUES('{tenant}','Rolled-back paper preflight');
INSERT INTO platform.accounts(tenant_id,id,name,broker,mode,currency,status)
 VALUES('{tenant}','{account}','Synthetic paper','bitget','paper','USDT','ready');
INSERT INTO platform.paper_role_bindings(database_role,tenant_id,account_id)
 VALUES('investalo_paper_tests','{tenant}','{account}');
RESET ROLE; SET LOCAL SESSION AUTHORIZATION investalo_paper_tests;
SELECT platform.paper_initialize({literals[0]},'{hashes[0]}');
SELECT platform.paper_commit(0,'{hashes[0]}',{literals[1]},'{hashes[1]}');
RESET SESSION AUTHORIZATION; SET LOCAL ROLE investalo_migration;
CREATE FUNCTION platform.paper_preflight_failure() RETURNS trigger LANGUAGE plpgsql AS
 'BEGIN RAISE EXCEPTION ''Synthetic failure'' USING ERRCODE=''P9999''; END';
CREATE TRIGGER paper_preflight_failure BEFORE UPDATE ON platform.paper_checkpoints
 FOR EACH ROW EXECUTE FUNCTION platform.paper_preflight_failure();
RESET ROLE; SET LOCAL SESSION AUTHORIZATION investalo_paper_tests;
DO $$
BEGIN
 BEGIN
  PERFORM platform.paper_commit(1,'{hashes[1]}',{literals[2]},'{hashes[2]}');
  RAISE EXCEPTION 'Expected preflight failure';
 EXCEPTION WHEN SQLSTATE 'P9999' THEN NULL;
 END;
 IF (platform.paper_read()->>'revision')::bigint<>1 THEN
  RAISE EXCEPTION 'Preflight rollback rejected';
 END IF;
END $$;
RESET SESSION AUTHORIZATION; SET LOCAL ROLE investalo_migration;
DO $$
BEGIN
 IF (SELECT count(*) FROM platform.paper_journal WHERE tenant_id='{tenant}')<>1 THEN
  RAISE EXCEPTION 'Preflight journal rollback rejected';
 END IF;
END $$;
ROLLBACK;
""")
        print("PASS: fixture010 DDL, bound worker commit and atomic failure preflight fully rolled back")
        if args.apply_reviewed:
            sql("BEGIN; SELECT pg_advisory_xact_lock(724809361); SET LOCAL ROLE investalo_migration;\n"
                + content + f"\nINSERT INTO platform.schema_migrations(version,checksum)"
                f" VALUES('{file.stem}','{checksum}'); COMMIT;")
            print("PASS: reviewed010 applied ONLY to isolated fixture database")
    print("PASS: separate paper test LOGIN prepared; normal database unchanged")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("Paper fixture preparation rejected; sensitive output suppressed.", file=sys.stderr)
        sys.exit(1)
