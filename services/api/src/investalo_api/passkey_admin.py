"""Migration-operator enrollment/revocation; manual email approval, no mail send."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import stat
import sys
from uuid import UUID

import psycopg

from .database import connect
from .passkeys import REGISTRY_COLUMNS, SAFE_INTEGER, encode_b64url, publish_credential, valid_rp
from .settings import Settings


def _operator(db):
    row = db.execute(
        "SELECT session_user AS login,current_user AS current,rolsuper,rolbypassrls,rolcreaterole,"
        "rolcreatedb,rolreplication FROM pg_catalog.pg_roles WHERE rolname=session_user"
    ).fetchone()
    if (
        not row or row["login"] != "investalo_migration" or row["current"] != "investalo_migration"
        or any(row[field] for field in ("rolsuper", "rolbypassrls", "rolcreaterole", "rolcreatedb", "rolreplication"))
    ):
        raise ValueError("Passkey operation requires migration identity")


def _approval(email_confirmed, confirmation_reference):
    if email_confirmed is not True or not isinstance(confirmation_reference, UUID):
        raise ValueError("Explicit email approval and confirmation reference required")


def _output_file(path: Path) -> int:
    """Create once through an owned, non-writable-by-others directory descriptor."""
    parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        info = os.fstat(parent)
        if info.st_uid != os.geteuid() or info.st_mode & 0o022:
            raise ValueError("Unsafe enrollment output directory")
        fd = os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != 0o600:
            os.close(fd)
            raise ValueError("Unsafe enrollment output file")
        return fd
    finally:
        os.close(parent)


def issue(
    settings: Settings, *, tenant_id: UUID, user_id: UUID, rp_id: str, auth_epoch: int,
    confirmation_reference: UUID, email_confirmed: bool, output_file: Path, ttl_seconds: int = 600,
) -> UUID:
    _approval(email_confirmed, confirmation_reference)
    valid_rp(rp_id)
    if (
        not isinstance(tenant_id, UUID) or not isinstance(user_id, UUID)
        or type(auth_epoch) is not int or not 0 <= auth_epoch <= SAFE_INTEGER
        or type(ttl_seconds) is not int or not 1 <= ttl_seconds <= 600
    ):
        raise ValueError("Invalid enrollment parameters")
    # Reserve the output before issuing a DB ticket; an existing file/symlink
    # can never cause a secret-bearing overwrite or a new ticket creation.
    fd = _output_file(Path(output_file))
    try:
        token, handle = secrets.token_bytes(32), secrets.token_bytes(32)
        expires = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        with connect(settings) as db:
            _operator(db)
            row = db.execute(
                "SELECT platform.passkey_issue_enrollment(%s,%s,%s,%s,%s,%s,%s,%s) AS ticket_id",
                (tenant_id, user_id, rp_id, hashlib.sha256(token).digest(), handle,
                 auth_epoch, expires, confirmation_reference),
            ).fetchone()
            if not row or set(row) != {"ticket_id"} or not isinstance(row["ticket_id"], UUID):
                raise ValueError("Enrollment unavailable")
            payload = json.dumps({
                "ticket_id": str(row["ticket_id"]), "tenant_id": str(tenant_id), "user_id": str(user_id),
                "rp_id": rp_id, "auth_epoch": auth_epoch, "expires_at": expires.isoformat(),
                "token": encode_b64url(token),
            }, ensure_ascii=True) + "\n"
            # Write before commit: a local output failure rolls back the issue.
            # If the commit outcome is unknown, preserve the protected artifact
            # and require operator reconciliation; never retry/overwrite blindly.
            with os.fdopen(fd, "w", encoding="utf-8", closefd=False) as output:
                output.write(payload)
                output.flush()
                os.fsync(fd)
        return row["ticket_id"]
    except (psycopg.Error, OSError):
        raise ValueError("Enrollment unavailable; reconcile before retry") from None
    finally:
        os.close(fd)


def revoke(
    settings: Settings, *, passkey_id: UUID, expected_storage: int,
    confirmation_reference: UUID, email_confirmed: bool,
) -> dict:
    _approval(email_confirmed, confirmation_reference)
    if (
        not isinstance(passkey_id, UUID) or type(expected_storage) is not int
        or not 1 <= expected_storage < SAFE_INTEGER
    ):
        raise ValueError("Invalid revocation parameters")
    try:
        with connect(settings) as db:
            _operator(db)
            row = db.execute(
                "SELECT " + ",".join(REGISTRY_COLUMNS) + " FROM platform.passkey_admin_revoke(%s,%s,%s)",
                (passkey_id, expected_storage, confirmation_reference),
            ).fetchone()
            if not isinstance(row, dict) or not isinstance(row.get("tenant_id"), UUID) or not isinstance(row.get("user_id"), UUID):
                raise ValueError("Revocation unavailable")
            result = publish_credential(row, tenant_id=row["tenant_id"], user_id=row["user_id"], rp_id=valid_rp(row.get("rp_id")))
            if result["passkey_id"] != str(passkey_id) or result["status"] != "revoked" or result["storage_version"] != expected_storage + 1:
                raise ValueError("Revocation unavailable")
        # Admin output contains only operation receipt IDs/version, never keys.
        return {"passkey_id": result["passkey_id"], "storage_version": result["storage_version"], "status": "revoked"}
    except psycopg.Error:
        raise ValueError("Revocation unavailable; reconcile before retry") from None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="operation", required=True)
    enroll = commands.add_parser("issue")
    enroll.add_argument("--tenant-id", type=UUID, required=True)
    enroll.add_argument("--user-id", type=UUID, required=True)
    enroll.add_argument("--rp-id", required=True)
    enroll.add_argument("--auth-epoch", type=int, required=True)
    enroll.add_argument("--ttl-seconds", type=int, default=600)
    enroll.add_argument("--output-file", type=Path, required=True)
    remove = commands.add_parser("revoke")
    remove.add_argument("--passkey-id", type=UUID, required=True)
    remove.add_argument("--expected-storage", type=int, required=True)
    for command in (enroll, remove):
        command.add_argument("--email-confirmed", action="store_true", required=True)
        command.add_argument("--confirmation-reference", type=UUID, required=True)
    values = vars(parser.parse_args(argv))
    operation = values.pop("operation")
    try:
        settings = Settings.from_environment()
        if operation == "issue":
            issue(settings, **values)
            print("Enrollment ticket written to protected output file; no email sent.")
        else:
            revoke(settings, **values)
            print("Passkey revoked; user authentication epoch advanced.")
        return 0
    except Exception:
        # Database exceptions, filenames, inputs and bearer tickets are private.
        print("Passkey operation unavailable; inspect protected state before retry.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
