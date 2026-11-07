#!/usr/bin/env python3
"""Bind the existing synthetic login to its explicit research tenant on the public issuer.

Operator-only development preview. Preserve the original local issuer/user,
tenant, worker binding, factors and credentials. Never print passwords or factors.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import UUID

ROOT = Path(__file__).resolve().parents[2]
LOCAL = ROOT / "infra/local"
ISSUER = "https://auth.cockpit.investalo.de"
SPEC = importlib.util.spec_from_file_location(
    "preview_preparation", ROOT / "infra/scripts/prepare-public-preview.py"
)
preparation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preparation)


def source_identity(value: object) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != {"username", "subject", "issuer", "tenant_name"} \
            or value["username"] != "pilot" \
            or value["issuer"] != "https://auth.cockpit.local.test:8443" \
            or value["tenant_name"] != "Lokale Entwicklung" \
            or not isinstance(value["subject"], str):
        raise RuntimeError("Requires the original synthetic local identity.")
    if str(UUID(value["subject"])) != value["subject"]:
        raise RuntimeError("Invalid synthetic subject.")
    return value


def operator_program(subject: str) -> str:
    # Input is a canonical UUID, passed over stdin, never through a shell.
    subject = str(UUID(subject))
    return f"""
import json
from investalo_api.database import connect
from investalo_api.provision import provision
from investalo_api.settings import Settings
settings = Settings.from_environment()
with connect(settings) as db:
    if db.execute("SELECT current_user AS name").fetchone()["name"] != "investalo_migration":
        raise RuntimeError("Operator identity required")
    rows = db.execute(
        "SELECT m.tenant_id FROM platform.users u "
        "JOIN platform.memberships m ON m.user_id=u.id "
        "JOIN platform.tenants t ON t.id=m.tenant_id "
        "WHERE u.oidc_issuer=%s AND u.oidc_subject=%s AND u.active "
        "AND m.active AND m.role='owner' AND t.name=%s",
        ("https://auth.cockpit.local.test:8443", {subject!r}, "Lokale Entwicklung"),
    ).fetchall()
    if len(rows) != 1:
        raise RuntimeError("Expected exactly one existing synthetic owner tenant")
    tenant_id = rows[0]["tenant_id"]
user_id, result_tenant = provision(
    settings, issuer={ISSUER!r}, subject={subject!r},
    tenant_name="Lokale Entwicklung", role="owner", tenant_id=tenant_id,
)
if result_tenant != tenant_id:
    raise RuntimeError("Unexpected tenant")
print(json.dumps({{"user_id":str(user_id),"tenant_id":str(tenant_id)}}))
"""


def provision(subject: str) -> dict[str, str]:
    result = subprocess.run(
        ["bash", str(ROOT / "infra/scripts/compose.sh"), "--profile", "tools",
         "run", "--rm", "--no-deps", "-T", "migrate", "python", "-"],
        input=operator_program(subject), text=True, capture_output=True,
    )
    if result.returncode:
        # Unknown commit outcomes must be reconciled before an operator retry.
        raise RuntimeError("Preview binding not confirmed; reconcile before retry.")
    value = json.loads(result.stdout)
    if not isinstance(value, dict) or set(value) != {"user_id", "tenant_id"} \
            or any(not isinstance(item, str) or str(UUID(item)) != item for item in value.values()):
        raise RuntimeError("Preview binding receipt rejected; reconcile before retry.")
    return value


def save_manifest(value: dict[str, str]) -> None:
    path = LOCAL / "public-preview-identity.json"
    content = json.dumps(value, sort_keys=True) + "\n"
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        if preparation.read_owned(path, 0, 0o600) != content:
            raise RuntimeError("Existing public binding differs; kept unchanged.")
        return
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--development-preview", action="store_true", required=True)
    parser.parse_args()
    if os.geteuid() != 0:
        raise RuntimeError("Requires root to read the protected synthetic identity.")
    # Preparation validates the protected directory, original template and .invalid user.
    # Its idempotent comparison never activates services or provisions identities.
    preparation.main(["--development-preview"])
    value = source_identity(json.loads(preparation.read_owned(LOCAL / "test-identity.json", 0, 0o600)))
    manifest = LOCAL / "public-preview-identity.json"
    if manifest.exists() or manifest.is_symlink():
        existing = json.loads(preparation.read_owned(manifest, 0, 0o600))
        expected = {**value, "issuer": ISSUER}
        if not isinstance(existing, dict) or set(existing) != set(expected) | {"user_id", "tenant_id"} \
                or any(existing[key] != item for key, item in expected.items()) \
                or any(not isinstance(existing[key], str) or str(UUID(existing[key])) != existing[key]
                       for key in ("user_id", "tenant_id")):
            raise RuntimeError("Existing public binding differs; kept unchanged.")
    output = {**value, "issuer": ISSUER, **provision(value["subject"])}
    save_manifest(output)
    print("Public preview login bound to the explicit existing synthetic research tenant.")
    print("Original identity, factors, worker, datasets and credentials kept unchanged.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, UnicodeError, ValueError):
        print("Preview binding not confirmed; inspect protected state before retry.", file=sys.stderr)
        sys.exit(1)
