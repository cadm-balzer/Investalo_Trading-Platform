#!/usr/bin/env python3
"""Own simulated development account in the already approved public-preview tenant."""
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

ROLE = "investalo_paper_preview"
DATABASE = "investalo"
ISSUER = "https://auth.cockpit.investalo.de"


def public_identity(value):
    if (set(value) != {"username", "subject", "issuer", "tenant_name", "user_id", "tenant_id"}
            or value["username"] != "pilot" or value["issuer"] != ISSUER
            or value["tenant_name"] != "Lokale Entwicklung"):
        raise ValueError()
    for key in ("subject", "user_id", "tenant_id"):
        if str(UUID(value[key])) != value[key]:
            raise ValueError()
    return value


def manifest(value, actor):
    if (set(value) != {"schema", "database", "role", "user_id", "tenant", "account", "state"}
            or value["schema"] != "paper-preview/1" or value["database"] != DATABASE
            or value["role"] != ROLE or value["state"] not in ("prepared", "bound")
            or value["user_id"] != actor["user_id"] or value["tenant"] != actor["tenant_id"]
            or str(UUID(value["account"])) != value["account"]):
        raise ValueError()
    return value


def owner_sql(actor):
    return f"""
DO $$
BEGIN
 IF NOT EXISTS(SELECT FROM platform.users u JOIN platform.memberships m ON m.user_id=u.id
   JOIN platform.tenants t ON t.id=m.tenant_id
   WHERE u.id='{actor['user_id']}' AND u.oidc_issuer='{ISSUER}'
     AND u.oidc_subject='{actor['subject']}' AND u.active AND m.active AND m.role='owner'
     AND m.tenant_id='{actor['tenant_id']}' AND t.name='Lokale Entwicklung') THEN
   RAISE EXCEPTION 'Public development owner drift';
 END IF;
END $$;
"""


def prepare(root, base, sql, verify_only=False):
    local = root/"infra/local"
    info = local.lstat()
    if (os.geteuid() != 0 or not stat.S_ISDIR(info.st_mode) or info.st_uid != 0
            or stat.S_IMODE(info.st_mode) != 0o700):
        raise ValueError()
    base["protected"](local/"READY", 0, 0o400)
    actor = public_identity(json.loads(base["protected"](local/"public-preview-identity.json", 0, 0o600)))
    ledger = dict(json.loads(sql(
        "SELECT json_agg(json_build_array(version,checksum)) FROM platform.schema_migrations;")))
    expected = {p.stem: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted((root/"services/api/migrations").glob("*.sql"))}
    if len(expected) != 12 or ledger != expected:
        raise ValueError()
    sql(owner_sql(actor))
    paths = {key: local/name for key, name in (
        ("manifest", "paper_preview.json"), ("password", "paper_preview_password"),
        ("env", "paper_preview.env"))}
    path = paths["manifest"]
    if path.exists() or path.is_symlink():
        value = manifest(json.loads(base["protected"](path, 0, 0o600)), actor)
    else:
        if verify_only or sql(f"SELECT count(*) FROM pg_roles WHERE rolname='{ROLE}';", "postgres") != "0":
            raise ValueError()
        value = {"schema": "paper-preview/1", "database": DATABASE, "role": ROLE,
                 "user_id": actor["user_id"], "tenant": actor["tenant_id"],
                 "account": str(uuid4()), "state": "prepared"}
        base["write_new"](path, json.dumps(value, sort_keys=True)+"\n", 0o600, 0)
    path = paths["password"]
    if not path.exists() and not path.is_symlink():
        if verify_only or value["state"] == "bound":
            raise ValueError()
        base["write_new"](path, secrets.token_urlsafe(48), 0o400, 10003)
    password = base["protected"](path, 10003, 0o400)
    if not re.fullmatch(r"[A-Za-z0-9_-]{64}", password):
        raise ValueError()
    if value["state"] == "prepared":
        if verify_only:
            raise ValueError()
        # Recovery after an acknowledged/unknown earlier commit is verification,
        # never repair of an existing role's grants or account binding.
        if sql(f"SELECT count(*) FROM pg_roles WHERE rolname='{ROLE}';", "postgres") == "1":
            base["verify"](sql, value, preview=True)
        t, a = value["tenant"], value["account"]
        sql(f"""
BEGIN; SELECT pg_advisory_xact_lock(724809361);
{owner_sql(actor)}
{base['check_roles_sql'](True)}
DO $$
BEGIN
 IF EXISTS(SELECT FROM pg_roles WHERE rolname='{ROLE}') AND NOT EXISTS(
   SELECT FROM platform.paper_role_bindings WHERE database_role='{ROLE}'
     AND tenant_id='{t}' AND account_id='{a}' AND active) THEN
   RAISE EXCEPTION 'Prepared preview binding drift';
 END IF;
 IF NOT EXISTS(SELECT FROM pg_roles WHERE rolname='{ROLE}') THEN
   CREATE ROLE {ROLE} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION
     NOBYPASSRLS PASSWORD '{password}';
 END IF;
 GRANT investalo_paper_worker TO {ROLE};
 GRANT CONNECT ON DATABASE investalo TO {ROLE};
END $$;
INSERT INTO platform.accounts(tenant_id,id,name,broker,mode,currency,status)
VALUES('{t}','{a}','Crypto-Paper · Entwicklung','bitget','paper','USDT','ready')
ON CONFLICT(tenant_id,id) DO NOTHING;
INSERT INTO platform.paper_role_bindings(database_role,tenant_id,account_id)
VALUES('{ROLE}','{t}','{a}') ON CONFLICT(database_role) DO NOTHING;
COMMIT;
""")
        base["verify"](sql, value, preview=True)
        value = {**value, "state": "bound"}
        temp = local/f"paper-preview-{uuid4()}.tmp"
        base["write_new"](temp, json.dumps(value, sort_keys=True)+"\n", 0o600, 0)
        os.replace(temp, paths["manifest"])
    else:
        base["verify"](sql, value, preview=True)
    sql(owner_sql(actor))
    expected_env = f"PAPER_TENANT_ID={value['tenant']}\nPAPER_ACCOUNT_ID={value['account']}\n"
    if paths["env"].exists() or paths["env"].is_symlink():
        if base["protected"](paths["env"], 0, 0o600) != expected_env:
            raise ValueError()
    elif verify_only:
        raise ValueError()
    else:
        base["write_new"](paths["env"], expected_env, 0o600, 0)
    return paths["env"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    base = runpy.run_path(str(root/"infra/scripts/provision-paper-development.py"))
    raw = runpy.run_path(str(root/"infra/scripts/prepare-paper-storage-checks.py"))["sql"]
    sql = lambda statement, database=DATABASE: raw(statement, database)
    # Validate directory before opening the host-only provisioning lock.
    local = root/"infra/local"
    info = local.lstat()
    if (os.geteuid() != 0 or not stat.S_ISDIR(info.st_mode)
            or info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o700):
        raise ValueError()
    fd = os.open(local/"paper-preview.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "r+") as stream:
        if base["protected"](local/"paper-preview.lock", 0, 0o600) != "":
            raise ValueError()
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        sql(f"""
DO $$
BEGIN
 IF EXISTS(SELECT FROM pg_hba_file_rules WHERE error IS NOT NULL)
   OR NOT EXISTS(SELECT FROM pg_hba_file_rules
     WHERE type='hostssl' AND database=ARRAY['investalo']::text[]
       AND user_name=ARRAY['{ROLE}']::text[] AND auth_method='scram-sha-256') THEN
   RAISE EXCEPTION 'Exact preview TLS HBA rule required';
 END IF;
END $$;
""", "postgres")
        path = prepare(root, base, sql, args.verify_only)
        if not args.verify_only:
            if sql("SELECT pg_reload_conf();", "postgres") != "t":
                raise ValueError()
    print(f"PASS: own simulated preview account; environment file: {path}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("Paper preview provisioning rejected; reconcile before retry;"
                         " sensitive output suppressed") from None
