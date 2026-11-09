#!/usr/bin/env python3
"""Stable local fixture account/LOGIN. Verify or refuse; never rebind or migrate."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import secrets
import stat
from uuid import UUID, uuid4

ROLE = "investalo_paper_development"
DATABASE = "investalo_credentials_checks"


def protected(path, uid, mode):
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != uid
            or stat.S_IMODE(info.st_mode) != mode or info.st_nlink != 1):
        raise ValueError()
    return path.read_text()


def write_new(path, value, mode, uid):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    with os.fdopen(fd, "w") as stream:
        os.fchown(stream.fileno(), uid, uid)
        stream.write(value)
        stream.flush()
        os.fsync(stream.fileno())


def manifest(value):
    if (set(value) != {"schema", "database", "role", "tenant", "account", "state"}
            or value["schema"] != "paper-development/1" or value["database"] != DATABASE
            or value["role"] != ROLE or value["state"] not in ("prepared", "bound")):
        raise ValueError()
    for name in ("tenant", "account"):
        if str(UUID(value[name])) != value[name]:
            raise ValueError()
    return value


def check_roles_sql():
    return f"""
DO $$
BEGIN
 IF EXISTS(SELECT FROM pg_roles WHERE rolname IN ('{ROLE}','investalo_paper_worker')
   AND (rolsuper OR rolbypassrls OR rolcreaterole OR rolcreatedb OR rolreplication
     OR (rolname='{ROLE}' AND NOT rolcanlogin)
     OR (rolname='investalo_paper_worker' AND rolcanlogin))) THEN
   RAISE EXCEPTION 'Paper role drift';
 END IF;
 IF NOT EXISTS(SELECT FROM pg_roles WHERE rolname='investalo_paper_worker') THEN
   RAISE EXCEPTION 'Reviewed Paper group required';
 END IF;
 IF EXISTS(SELECT FROM pg_auth_members m JOIN pg_roles r ON r.oid=m.member
   JOIN pg_roles p ON p.oid=m.roleid
   WHERE (r.rolname IN ('{ROLE}','investalo_paper_worker')
          AND (r.rolname='investalo_paper_worker' OR p.rolname<>'investalo_paper_worker'
               OR m.admin_option))
     OR p.rolname='{ROLE}') THEN RAISE EXCEPTION 'Paper membership drift'; END IF;
END $$;
"""


def verify(sql, value):
    t, a = value["tenant"], value["account"]
    sql(check_roles_sql(), "postgres")
    sql(f"""
DO $$
BEGIN
 IF NOT EXISTS(SELECT FROM pg_roles WHERE rolname='{ROLE}')
   OR NOT pg_has_role('{ROLE}','investalo_paper_worker','MEMBER')
   OR NOT has_database_privilege('{ROLE}','{DATABASE}','CONNECT')
   OR has_database_privilege('{ROLE}','investalo','CONNECT') THEN
   RAISE EXCEPTION 'Paper grants drift';
 END IF;
 IF has_schema_privilege('{ROLE}','platform','CREATE')
   OR EXISTS(SELECT FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
     WHERE n.nspname='platform' AND c.relkind IN ('r','p')
       AND has_table_privilege('{ROLE}',c.oid,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE')) THEN
   RAISE EXCEPTION 'Paper direct rights drift';
 END IF;
 IF NOT has_function_privilege('{ROLE}','platform.paper_read()','EXECUTE')
   OR NOT has_function_privilege('{ROLE}','platform.paper_initialize(text,text)','EXECUTE')
   OR NOT has_function_privilege('{ROLE}','platform.paper_commit(bigint,text,text,text)','EXECUTE')
   OR EXISTS(SELECT FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
     WHERE n.nspname='platform' AND p.prosecdef AND has_function_privilege('{ROLE}',p.oid,'EXECUTE')
       AND p.oid NOT IN ('platform.paper_read()'::regprocedure,
         'platform.paper_initialize(text,text)'::regprocedure,
         'platform.paper_commit(bigint,text,text,text)'::regprocedure)) THEN
   RAISE EXCEPTION 'Paper function capability drift';
 END IF;
 IF NOT EXISTS(SELECT FROM platform.paper_role_bindings b JOIN platform.accounts a
   ON (a.tenant_id,a.id)=(b.tenant_id,b.account_id)
   WHERE b.database_role='{ROLE}' AND b.tenant_id='{t}' AND b.account_id='{a}'
     AND b.active AND a.mode='paper' AND a.broker='bitget' AND a.currency='USDT'
     AND a.status IN ('ready','paused')) THEN RAISE EXCEPTION 'Paper binding drift'; END IF;
END $$;
""")


def prepare(root, sql, verify_only=False):
    local = root/"infra/local"
    info = local.lstat()
    if (os.geteuid() != 0 or not stat.S_ISDIR(info.st_mode) or info.st_uid != 0
            or stat.S_IMODE(info.st_mode) != 0o700):
        raise ValueError()
    protected(local/"READY", 0, 0o400)
    recorded = dict(json.loads(sql(
        "SELECT json_agg(json_build_array(version,checksum)) FROM platform.schema_migrations;")))
    for number in range(1, 13):
        path, = (root/"services/api/migrations").glob(f"{number:03}_*.sql")
        if recorded.get(path.stem) != hashlib.sha256(path.read_bytes()).hexdigest():
            raise ValueError()
    password_path = local/"paper_development_password"
    manifest_path = local/"paper_development.json"
    env_path = local/"paper_development.env"
    if manifest_path.exists() or manifest_path.is_symlink():
        value = manifest(json.loads(protected(manifest_path, 0, 0o600)))
    else:
        if verify_only or sql(f"SELECT count(*) FROM pg_roles WHERE rolname='{ROLE}';", "postgres") != "0":
            raise ValueError()
        value = {"schema": "paper-development/1", "database": DATABASE, "role": ROLE,
                 "tenant": str(uuid4()), "account": str(uuid4()), "state": "prepared"}
        write_new(manifest_path, json.dumps(value, sort_keys=True)+"\n", 0o600, 0)
    if not password_path.exists() and not password_path.is_symlink():
        if verify_only or value["state"] == "bound":
            raise ValueError()
        write_new(password_path, secrets.token_urlsafe(48), 0o400, 10003)
    password = protected(password_path, 10003, 0o400)
    if not re.fullmatch(r"[A-Za-z0-9_-]{64}", password):
        raise ValueError()
    if value["state"] == "prepared":
        if verify_only:
            raise ValueError()
        t, a = value["tenant"], value["account"]
        sql(f"""
BEGIN; SELECT pg_advisory_xact_lock(724809361);
{check_roles_sql()}
DO $$
BEGIN
 IF EXISTS(SELECT FROM pg_roles WHERE rolname='{ROLE}') AND NOT EXISTS(
   SELECT FROM platform.paper_role_bindings WHERE database_role='{ROLE}'
     AND tenant_id='{t}' AND account_id='{a}' AND active) THEN
   RAISE EXCEPTION 'Prepared Paper identity binding drift';
 END IF;
 IF NOT EXISTS(SELECT FROM pg_roles WHERE rolname='{ROLE}') THEN
   CREATE ROLE {ROLE} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION
     NOBYPASSRLS PASSWORD '{password}';
 END IF;
 GRANT investalo_paper_worker TO {ROLE};
 GRANT CONNECT ON DATABASE {DATABASE} TO {ROLE};
END $$;
INSERT INTO platform.tenants(id,name) VALUES('{t}','Persistent Paper development')
  ON CONFLICT(id) DO NOTHING;
INSERT INTO platform.accounts(tenant_id,id,name,broker,mode,currency,status)
  VALUES('{t}','{a}','Persistent development Paper','bitget','paper','USDT','ready')
  ON CONFLICT(tenant_id,id) DO NOTHING;
INSERT INTO platform.paper_role_bindings(database_role,tenant_id,account_id)
  VALUES('{ROLE}','{t}','{a}') ON CONFLICT(database_role) DO NOTHING;
COMMIT;
""")
        verify(sql, value)
        # Retrying a crash uses the prepared IDs, never creates another account.
        value = {**value, "state": "bound"}
        temporary = local/f"paper-development-{uuid4()}.tmp"
        write_new(temporary, json.dumps(value, sort_keys=True)+"\n", 0o600, 0)
        os.replace(temporary, manifest_path)
    else:
        verify(sql, value)
    expected = f"PAPER_TENANT_ID={value['tenant']}\nPAPER_ACCOUNT_ID={value['account']}\n"
    if env_path.exists() or env_path.is_symlink():
        if protected(env_path, 0, 0o600) != expected:
            raise ValueError()
    elif verify_only:
        raise ValueError()
    else:
        write_new(env_path, expected, 0o600, 0)
    return env_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    prep = runpy.run_path(str(root/"infra/scripts/prepare-paper-storage-checks.py"))
    local = root/"infra/local"
    info = local.lstat()
    if (os.geteuid() != 0 or not stat.S_ISDIR(info.st_mode) or info.st_uid != 0
            or stat.S_IMODE(info.st_mode) != 0o700):
        raise ValueError()
    fd = os.open(local/"paper-development.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "r+") as stream:
        if protected(local/"paper-development.lock", 0, 0o600) != "":
            raise ValueError()
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        path = prepare(root, prep["sql"], args.verify_only)
    print(f"PASS: stable local fixture Paper identity; environment file: {path}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("Paper development provisioning rejected; sensitive output suppressed") from None
