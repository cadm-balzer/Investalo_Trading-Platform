"""Allowlisted metadata only; no broker calls, credential objects or ciphertext."""
from uuid import UUID

from fastapi import HTTPException
import psycopg

from .auth import Assertion


JS_SAFE_INTEGER = 9_007_199_254_740_991
_COLUMNS = (
    "tenant_id", "auth_epoch", "account_id", "account_name", "account_broker",
    "account_mode", "account_status", "connection_id", "credential_revision",
    "storage_version", "connection_status",
)
_QUERY = "SELECT " + ",".join(_COLUMNS) + " FROM platform.credential_action_context(%s)"


def _safe_integer(value, *, minimum=0) -> bool:
    return type(value) is int and minimum <= value <= JS_SAFE_INTEGER


def publish_context(row: dict, account_id: UUID, identity: Assertion) -> dict:
    """Reject malformed/foreign DB results before constructing the public shape."""
    if (
        not isinstance(row, dict) or set(row) != set(_COLUMNS)
        or not isinstance(row["tenant_id"], UUID) or row["tenant_id"] != identity.tenant_id
        or not isinstance(row["account_id"], UUID) or row["account_id"] != account_id
        or not _safe_integer(row["auth_epoch"])
        or not isinstance(row["account_name"], str) or not 1 <= len(row["account_name"]) <= 120
        or any(ord(character) < 32 or ord(character) == 127 for character in row["account_name"])
        or row["account_broker"] != "bitget" or row["account_mode"] != "read_only"
        or row["account_status"] not in ("disconnected", "ready", "paused")
    ):
        raise HTTPException(503, "Service unavailable")
    if row["auth_epoch"] != identity.auth_epoch:
        raise HTTPException(401, "Reauthentication required")
    connection = None
    fields = ("connection_id", "credential_revision", "storage_version", "connection_status")
    if any(row[field] is not None for field in fields):
        if (
            not isinstance(row["connection_id"], UUID)
            or not _safe_integer(row["credential_revision"], minimum=1)
            or not _safe_integer(row["storage_version"], minimum=1)
            or row["connection_status"] not in ("active", "revoked")
        ):
            raise HTTPException(503, "Service unavailable")
        connection = {
            "connection_id": str(row["connection_id"]),
            "credential_revision": row["credential_revision"],
            "storage_version": row["storage_version"], "status": row["connection_status"],
        }
    return {
        "tenant_id": str(row["tenant_id"]), "auth_epoch": row["auth_epoch"],
        "account": {
            "id": str(row["account_id"]), "name": row["account_name"],
            "broker": row["account_broker"], "mode": row["account_mode"],
            "status": row["account_status"],
        },
        "connection": connection,
    }


def action_context(db, account_id: UUID, identity: Assertion) -> dict:
    # No fallback SELECT on private tables if the additive migration is absent.
    try:
        row = db.execute(_QUERY, (account_id,)).fetchone()
    except psycopg.errors.InsufficientPrivilege:
        raise HTTPException(403, "Access denied") from None
    except psycopg.Error:
        raise HTTPException(503, "Service unavailable") from None
    return publish_context(row, account_id, identity)
