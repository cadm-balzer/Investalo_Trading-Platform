#!/usr/bin/env python3
"""Verify stable provisioning and rolled-back drift, then real restricted sessions."""
import hashlib
import json
from pathlib import Path
import runpy
import subprocess


def main():
    root = Path(__file__).resolve().parents[2]
    provision = runpy.run_path(str(root/"infra/scripts/provision-paper-development.py"))
    sql = runpy.run_path(str(root/"infra/scripts/prepare-paper-storage-checks.py"))["sql"]
    local = root/"infra/local"
    value = provision["manifest"](json.loads(provision["protected"](
        local/"paper_development.json", 0, 0o600)))
    paths = [local/name for name in (
        "paper_development.json", "paper_development.env", "paper_development_password")]
    before = [hashlib.sha256(p.read_bytes()).digest() for p in paths]
    account = value["account"]
    counts_sql = (
        f"SELECT json_build_array((SELECT count(*) FROM platform.accounts WHERE id='{account}'),"
        f"(SELECT count(*) FROM platform.paper_checkpoints WHERE account_id='{account}'),"
        f"(SELECT count(*) FROM platform.paper_journal WHERE account_id='{account}'));")
    counts = sql(counts_sql)
    provision["prepare"](root, sql)
    provision["prepare"](root, sql, True)
    assert before == [hashlib.sha256(p.read_bytes()).digest() for p in paths]
    assert counts == sql(counts_sql)
    statements = []
    provision["verify"](lambda statement, *_: statements.append(statement), value)
    verify_sql = "\n".join(statements)
    role = provision["ROLE"]
    probes = [
        f"ALTER ROLE {role} CREATEROLE;",
        f"GRANT SELECT ON platform.paper_checkpoints TO {role};",
        f"GRANT EXECUTE ON FUNCTION platform.research_tenant() TO {role};",
        f"UPDATE platform.paper_role_bindings SET active=false WHERE database_role='{role}';",
    ]
    for change in probes:
        try:
            sql("BEGIN;\n"+change+"\n"+verify_sql+"\nROLLBACK;")
        except ValueError:
            pass  # ON_ERROR_STOP disconnect rolls the entire probe back.
        else:
            raise AssertionError("Drift accepted")
        provision["verify"](sql, value)
    print("PASS: provisioning preserves identity/files/rows; four actual drift probes rolled back")
    result = subprocess.run([
        "bash", str(root/"infra/scripts/compose.sh"),
        "--env-file", str(local/"paper_development.env"),
        "--file", str(root/"infra/compose.paper-development.yaml"),
        "--profile", "paper-development", "run", "--rm", "--no-deps", "-T",
        "paper-development", "python", "-",
    ], input=(root/"tests/infra/check_paper_development_runtime.py").read_text(),
       text=True, capture_output=True, timeout=60)
    if result.returncode:
        raise ValueError()
    # Child has only fixed messages; do not forward connection diagnostics/stderr.
    print(result.stdout.strip())


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("Paper development acceptance rejected; sensitive output suppressed") from None
