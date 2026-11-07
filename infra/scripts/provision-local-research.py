#!/usr/bin/env python3
"""Create/bind one local research login; never emit passwords or SQL errors."""
import argparse
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
from uuid import UUID

ROOT = Path(__file__).resolve().parents[2]
LOCAL = ROOT / "infra/local"


def sql(command: str, database: str = "postgres") -> str:
    result = subprocess.run(
        ["bash", str(ROOT / "infra/scripts/compose.sh"), "exec", "-T",
         "postgres", "psql", "--no-psqlrc", "--username", "investalo_admin",
         "--dbname", database, "--tuples-only", "--no-align",
         "--set", "ON_ERROR_STOP=1"],
        input=command, capture_output=True, text=True,
    )
    if result.returncode:
        raise RuntimeError("Local research provisioning failed; sensitive SQL output suppressed.")
    return result.stdout.strip()


def prepare_roles(role: str, password: str) -> None:
    """Validate existing roles and grant access in one rollback-safe transaction."""
    if role not in ("investalo_research_local", "investalo_research_tests"):
        raise RuntimeError("Unexpected research role.")
    if not isinstance(password, str) or not re.fullmatch(r"[A-Za-z0-9_-]{64}", password):
        raise RuntimeError("Unexpected research-secret format.")
    # Only fixed identifiers and the validated generated secret enter SQL.
    # Keep it on psql stdin: neither argv nor exception output contains it.
    literal = "'" + password.replace("'", "''") + "'"
    sql(f"""
BEGIN;
SELECT pg_catalog.pg_advisory_xact_lock(1380275026,1);
DO $$
BEGIN
  IF EXISTS (
    SELECT FROM pg_catalog.pg_roles
    WHERE rolname IN ('{role}','investalo_research_worker')
      AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls
        OR (rolname='investalo_research_worker' AND rolcanlogin)
        OR (rolname='{role}' AND NOT rolcanlogin))
  ) THEN
    RAISE EXCEPTION 'Research role has unexpected privileges';
  END IF;
  IF EXISTS (
    SELECT FROM pg_catalog.pg_auth_members membership
    JOIN pg_catalog.pg_roles member_role ON member_role.oid=membership.member
    JOIN pg_catalog.pg_roles parent_role ON parent_role.oid=membership.roleid
    WHERE member_role.rolname IN ('{role}','investalo_research_worker')
      AND (member_role.rolname='investalo_research_worker'
        OR parent_role.rolname<>'investalo_research_worker'
        OR membership.admin_option)
  ) THEN
    RAISE EXCEPTION 'Research role has unexpected memberships';
  END IF;
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname='investalo_research_worker') THEN
    CREATE ROLE investalo_research_worker NOLOGIN NOSUPERUSER NOCREATEDB
      NOCREATEROLE NOREPLICATION NOBYPASSRLS;
  END IF;
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname='{role}') THEN
    CREATE ROLE {role} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
      NOREPLICATION NOBYPASSRLS PASSWORD {literal};
  END IF;
  GRANT investalo_research_worker TO {role};
  GRANT CONNECT ON DATABASE investalo TO {role};
END $$;
COMMIT;
""")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bind-tenant", type=UUID)
    parser.add_argument("--test-role", action="store_true",
                        help="Prepare a separate integration-test identity.")
    parser.add_argument("--bind-local-test", action="store_true",
                        help="Bind the worker to the already provisioned .invalid test tenant.")
    args = parser.parse_args()
    if os.geteuid() != 0 or not (LOCAL / "READY").exists():
        raise RuntimeError("Requires initialized local development material and root.")
    if args.bind_local_test and (args.bind_tenant or args.test_role):
        raise RuntimeError("Local test binding cannot be combined with another binding.")
    data_directory = LOCAL / "research-data"
    if data_directory.is_symlink():
        raise RuntimeError("Unexpected research import directory.")
    data_directory.mkdir(mode=0o700, exist_ok=True)
    os.chown(data_directory, 10003, 10003)
    os.chmod(data_directory, 0o700)
    role = "investalo_research_tests" if args.test_role else "investalo_research_local"
    secret_name = "research_test_password" if args.test_role else "research_password"
    uid = 10003 if args.test_role else 10005
    password_file = LOCAL / secret_name
    if not password_file.exists():
        fd = os.open(password_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o400)
        with os.fdopen(fd, "w") as stream:
            stream.write(secrets.token_urlsafe(48))
        os.chown(password_file, uid, uid)
    stat = password_file.stat()
    if password_file.is_symlink() or stat.st_uid != uid or stat.st_mode & 0o777 != 0o400:
        raise RuntimeError("Unexpected research-secret ownership or permissions.")
    password = password_file.read_text()
    prepare_roles(role, password)
    tenant_uuid = args.bind_tenant
    if args.bind_local_test:
        identity = json.loads((LOCAL / "test-identity.json").read_text())
        if identity.get("username") != "pilot" or identity.get("issuer") != "https://auth.cockpit.local.test:8443":
            raise RuntimeError("Refusing unknown local test identity.")
        subject = str(UUID(identity["subject"]))
        value = sql(f"""SELECT m.tenant_id FROM platform.memberships m
JOIN platform.users u ON u.id=m.user_id JOIN platform.tenants t ON t.id=m.tenant_id
WHERE u.oidc_subject='{subject}' AND u.oidc_issuer='https://auth.cockpit.local.test:8443'
AND u.active AND m.active AND m.role='owner' AND t.name='Lokale Entwicklung';""", "investalo")
        tenant_uuid = UUID(value)
    if tenant_uuid is None:
        print("Local research role prepared; password retained in its protected file.")
        return
    tenant = str(tenant_uuid)
    current = sql(
        f"SELECT tenant_id FROM platform.research_role_bindings WHERE database_role='{role}';",
        "investalo",
    )
    if current and current != tenant:
        raise RuntimeError("Refusing to rebind an existing research identity to another tenant.")
    sql(f"""INSERT INTO platform.research_role_bindings(database_role,tenant_id)
VALUES ('{role}','{tenant}') ON CONFLICT(database_role) DO NOTHING;""", "investalo")
    # Nonsecret local manifest, protected like the rest of the test environment.
    manifest = LOCAL / ("research-test-binding.json" if args.test_role else "research-binding.json")
    if not manifest.exists():
        fd = os.open(manifest, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w") as stream:
            json.dump({"database_role": role, "tenant_id": tenant}, stream)
            stream.write("\n")
    print("Local research identity bound to one tenant; no broker or BFF credentials.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, ValueError):
        print("Local research provisioning refused or failed; no sensitive output.", file=sys.stderr)
        sys.exit(1)
