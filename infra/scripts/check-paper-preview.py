#!/usr/bin/env python3
"""Actual preview identity/idempotence/isolation and safe Compose/runtime checks."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import subprocess


CHILD = """
from investalo_workers.paper_preview_once import require_preview
from investalo_workers.paper_main import configured_worker
from investalo_workers.settings import WorkerSettings
import psycopg
require_preview()
settings=WorkerSettings.from_environment()
with settings.connect() as db:
    row=db.execute("SELECT current_database() AS database,current_user AS role,"
                   "current_user=session_user AS direct").fetchone()
    assert row == {"database":"investalo","role":"investalo_paper_preview","direct":True}
    assert not db.execute("SELECT has_table_privilege(current_user,"
        "'platform.paper_checkpoints','SELECT,INSERT,UPDATE,DELETE') AS allowed").fetchone()["allowed"]
try:
    with psycopg.connect(**{**settings.parameters,"dbname":"investalo_credentials_checks"}):
        raise AssertionError("Fixture access accepted")
except psycopg.OperationalError:
    pass
worker=configured_worker()
saved=worker.store.read()
if saved is not None:
    assert worker.runner.restore(worker.runner.dump(saved)) == saved
print("PASS: actual normal Paper TLS LOGIN, fixture/direct-table denial and own readback")
"""


def command(args, *, input=None):
    result = subprocess.run(args, input=input, text=True, capture_output=True, timeout=60)
    if result.returncode:
        raise ValueError()
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--active", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    base = runpy.run_path(str(root/"infra/scripts/provision-paper-development.py"))
    preview = runpy.run_path(str(root/"infra/scripts/provision-paper-preview.py"))
    raw = runpy.run_path(str(root/"infra/scripts/prepare-paper-storage-checks.py"))["sql"]
    sql = lambda statement, database="investalo": raw(statement, database)
    local = root/"infra/local"
    actor = preview["public_identity"](json.loads(base["protected"](
        local/"public-preview-identity.json", 0, 0o600)))
    value = preview["manifest"](json.loads(base["protected"](local/"paper_preview.json", 0, 0o600)), actor)
    paths = [local/name for name in ("paper_preview.json", "paper_preview_password", "paper_preview.env")]
    hashes = [hashlib.sha256(p.read_bytes()).digest() for p in paths]
    account = value["account"]
    query = (f"SELECT json_build_array((SELECT count(*) FROM platform.accounts WHERE id='{account}'),"
             f"(SELECT count(*) FROM platform.paper_checkpoints WHERE account_id='{account}'),"
             f"(SELECT count(*) FROM platform.paper_journal WHERE account_id='{account}'));")
    rows = sql(query)
    preview["prepare"](root, base, sql)
    preview["prepare"](root, base, sql, True)
    assert rows == sql(query) and hashes == [hashlib.sha256(p.read_bytes()).digest() for p in paths]
    # Assert existing-role recovery cannot repair revoked grants. Only synthetic
    # role privileges change within this aborted transaction, never public identity.
    guard = []
    base["verify"](lambda statement, *_: guard.append(statement), value, preview=True)
    for change in (
        "REVOKE CONNECT ON DATABASE investalo FROM investalo_paper_preview;",
        "GRANT SELECT ON platform.paper_checkpoints TO investalo_paper_preview;",
        "GRANT EXECUTE ON FUNCTION platform.research_tenant() TO investalo_paper_preview;",
        "UPDATE platform.paper_role_bindings SET active=false WHERE database_role='investalo_paper_preview';",
    ):
        try:
            sql("BEGIN;\n"+change+"\n"+"\n".join(guard)+"\nROLLBACK;")
        except ValueError:
            pass
        else:
            raise AssertionError("Preview drift accepted")
        base["verify"](sql, value, preview=True)
    compose = [
        "bash", str(root/"infra/scripts/compose.sh"),
        "--env-file", str(local/"paper_preview.env"),
        "--file", str(root/"infra/compose.public-preview.yaml"),
        "--file", str(root/"infra/compose.paper-preview.yaml"),
        "--profile", "paper-preview",
    ]
    rendered = json.loads(command(compose+["config", "--format", "json"]))["services"]
    assert rendered["api"]["environment"]["API_PAPER_STATUS_PREVIEW"] == "1"
    assert rendered["cockpit"]["environment"]["COCKPIT_PAPER_STATUS_PREVIEW"] == "1"
    for service, sensitive, display in (
        ("api", "API_PASSKEY_CREDENTIAL_AUTHORIZATIONS", "API_PAPER_STATUS_PREVIEW"),
        ("cockpit", "COCKPIT_PASSKEY_PROOF_PREVIEW", "COCKPIT_PAPER_STATUS_PREVIEW"),
    ):
        assert rendered[service]["environment"].get(sensitive) != "1"
        data = json.loads(command(["docker", "inspect", f"investalo-local-{service}-1"]))[0]
        env = dict(line.split("=", 1) for line in data["Config"]["Env"])
        assert env.get(sensitive) != "1"
        if args.active:
            assert env.get(display) == "1"
    assert rendered["paper-preview-once"].get("ports", []) == []
    assert rendered["paper-preview-once"]["restart"] == "no"
    print("PASS: stable own provisioning, four rolled-back drift probes and sensitive flags disabled")
    output = command(compose+["run", "--rm", "--no-deps", "-T", "paper-preview-once", "python", "-"],
                     input=CHILD)
    print(output.strip())


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("Paper preview acceptance rejected; sensitive output suppressed") from None
