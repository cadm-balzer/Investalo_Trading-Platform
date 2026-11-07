#!/usr/bin/env python3
"""Check role-drift rejection in the isolated local fixture DB, then rollback."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
COMMAND = [
    "bash", str(ROOT / "infra/scripts/compose.sh"), "exec", "-T", "postgres",
    "psql", "--no-psqlrc", "--username", "investalo_admin",
    "--dbname", "investalo_credentials_checks", "--tuples-only", "--no-align",
    "--set", "ON_ERROR_STOP=1", "--set", "VERBOSITY=sqlstate",
]
MEMBERSHIP = """
SELECT count(*)=1 AND NOT bool_or(m.admin_option)
FROM pg_catalog.pg_auth_members m
JOIN pg_catalog.pg_roles r ON r.oid=m.member
JOIN pg_catalog.pg_roles g ON g.oid=m.roleid
WHERE r.rolname='investalo_credentials_tests_a'
  AND g.rolname='investalo_credentials_worker';
"""


def run(command: str):
    return subprocess.run(COMMAND, input=command, text=True, capture_output=True)


def main() -> None:
    initial = run(MEMBERSHIP)
    if initial.returncode or initial.stdout.strip() != "t":
        raise RuntimeError("Unexpected fixture membership; no change attempted.")
    baseline = run("""
SET SESSION AUTHORIZATION investalo_credentials_tests_a;
SELECT count(*)=1 FROM platform.credential_context();
""")
    if baseline.returncode or baseline.stdout.strip().splitlines()[-1:] != ["t"]:
        raise RuntimeError("Fixture identity is not authorized; no change attempted.")
    result = run("""
BEGIN;
GRANT investalo_credentials_worker TO investalo_credentials_tests_a WITH ADMIN OPTION;
SET SESSION AUTHORIZATION investalo_credentials_tests_a;
SELECT 'credential-guard-ready';
SELECT * FROM platform.credential_context();
""")
    # ON_ERROR_STOP closes this psql connection on rejection. Its uncommitted
    # GRANT is rolled back by PostgreSQL even when the guard unexpectedly allows
    # the call; no COMMIT command is ever sent.
    final = run(MEMBERSHIP)
    if final.returncode or final.stdout.strip() != "t":
        raise RuntimeError("Fixture membership rollback verification failed.")
    if (not result.returncode or "ERROR:  42501" not in result.stderr
            or result.stdout.strip().splitlines()[-1:] != ["credential-guard-ready"]):
        raise RuntimeError("Role-drift guard did not return expected SQLSTATE.")
    print("Admin-option drift rejected (42501); original membership restored.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError):
        print("Role-drift check failed; raw SQL output suppressed.", file=sys.stderr)
        sys.exit(1)
