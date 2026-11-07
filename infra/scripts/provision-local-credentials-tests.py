#!/usr/bin/env python3
"""Provision fixed test-only LOGINs and an isolated credential fixture database."""
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
LOCAL = ROOT / "infra/local"
DATABASE = "investalo_credentials_checks"
GROUP = "investalo_credentials_worker"
ROLES = {
    "investalo_credentials_tests_a": "credentials_test_password_a",
    "investalo_credentials_tests_b": "credentials_test_password_b",
    "investalo_credentials_tests_unbound": "credentials_test_password_unbound",
}


def sql(command: str, database: str = "postgres") -> str:
    result = subprocess.run(
        ["bash", str(ROOT / "infra/scripts/compose.sh"), "exec", "-T", "postgres",
         "psql", "--no-psqlrc", "--username", "investalo_admin", "--dbname", database,
         "--tuples-only", "--no-align", "--set", "ON_ERROR_STOP=1"],
        input=command, capture_output=True, text=True,
    )
    if result.returncode:
        raise RuntimeError("Credential test provisioning failed; SQL output suppressed.")
    return result.stdout.strip()


def prepare_roles(passwords: dict[str, str]) -> None:
    if set(passwords) != set(ROLES) or any(
        not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{64}", value)
        for value in passwords.values()
    ):
        raise RuntimeError("Unexpected test-role or secret format.")
    role_list = ",".join("'" + role + "'" for role in (*ROLES, GROUP))
    statements = [f"""
BEGIN;
SELECT pg_catalog.pg_advisory_xact_lock(1380275026,2);
DO $$
BEGIN
  IF EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname IN ({role_list})
    AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls
      OR (rolname='{GROUP}' AND rolcanlogin)
      OR (rolname<>'{GROUP}' AND NOT rolcanlogin))) THEN
    RAISE EXCEPTION 'Credential role has unexpected privileges';
  END IF;
  IF EXISTS (
    SELECT FROM pg_catalog.pg_auth_members membership
    JOIN pg_catalog.pg_roles member_role ON member_role.oid=membership.member
    JOIN pg_catalog.pg_roles parent_role ON parent_role.oid=membership.roleid
    WHERE member_role.rolname IN ({role_list})
      AND (member_role.rolname='{GROUP}' OR parent_role.rolname<>'{GROUP}'
           OR membership.admin_option)
  ) THEN
    RAISE EXCEPTION 'Credential role has unexpected memberships';
  END IF;
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname='{GROUP}') THEN
    CREATE ROLE {GROUP} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
      NOREPLICATION NOBYPASSRLS;
  END IF;
"""]
    for role, password in passwords.items():
        # Fixed names and restricted generated literals, exclusively on stdin.
        statements.append(f"""
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname='{role}') THEN
    CREATE ROLE {role} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
      NOREPLICATION NOBYPASSRLS PASSWORD '{password}';
  END IF;
  GRANT {GROUP} TO {role};
""")
    statements.append("END $$;\nCOMMIT;")
    sql("\n".join(statements))


def prepare_database() -> None:
    existing = sql(
        "SELECT pg_catalog.pg_get_userbyid(datdba) FROM pg_catalog.pg_database "
        f"WHERE datname='{DATABASE}';"
    )
    if existing and existing != "investalo_migration":
        raise RuntimeError("Unexpected fixture-database owner.")
    if not existing:
        sql(f"CREATE DATABASE {DATABASE} OWNER investalo_migration;")
    # The test LOGINs can connect only to this fixture database. The production
    # credential service identity and key provider are not configured by this.
    sql(f"""
BEGIN;
REVOKE ALL ON DATABASE {DATABASE} FROM PUBLIC;
GRANT CONNECT ON DATABASE {DATABASE} TO investalo_runtime,investalo_research_tests,
  {','.join(ROLES)};
COMMIT;
""")
    sql("""
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE,CREATE ON SCHEMA public TO investalo_migration;
""", DATABASE)


def main() -> None:
    if os.geteuid() != 0 or not (LOCAL / "READY").exists():
        raise RuntimeError("Requires initialized local development and root.")
    passwords = {}
    for role, name in ROLES.items():
        location = LOCAL / name
        if location.is_symlink():
            raise RuntimeError("Unexpected test-secret symlink.")
        if not location.exists():
            fd = os.open(location, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o400)
            with os.fdopen(fd, "w") as stream:
                stream.write(secrets.token_urlsafe(48))
            os.chown(location, 10003, 10003)
        stat = location.stat()
        if stat.st_uid != 10003 or stat.st_mode & 0o777 != 0o400:
            raise RuntimeError("Unexpected test-secret ownership or permissions.")
        passwords[role] = location.read_text()
    prepare_roles(passwords)
    prepare_database()
    print("Three test-only credential LOGINs and isolated fixture database prepared.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError):
        print("Credential test provisioning refused or failed; no sensitive output.", file=sys.stderr)
        sys.exit(1)
