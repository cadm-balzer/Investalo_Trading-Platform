"""Own safe Demo metadata, never a private credential read or write grant."""
from uuid import UUID

from fastapi import APIRouter, HTTPException
import psycopg

from .database import transaction
from .demo_passkey_authorizations import Identity, _live_assertion, _metadata
from .settings import Settings


def action_context(db, account_id: UUID, identity) -> dict:
    try:
        row = db.execute(
            "SELECT platform.demo_credential_action_context(%s,%s,%s) AS metadata",
            (account_id, identity.auth_epoch, identity.oidc_auth_time),
        ).fetchone()
    except psycopg.errors.InsufficientPrivilege:
        raise HTTPException(403, "Access denied") from None
    except psycopg.Error:
        # An absent017 has no fallback query against private tables.
        raise HTTPException(503, "Service unavailable") from None
    if type(row) is not dict or set(row) != {"metadata"}:
        raise HTTPException(503, "Service unavailable")
    metadata = _metadata(row["metadata"], identity)
    if metadata["account"]["id"] != str(account_id):
        raise HTTPException(503, "Service unavailable")
    return metadata


def create_demo_credential_action_router(settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/v1/bitget-demo/credential-actions")
    if settings.demo_credential_metadata is not True:
        return router

    @router.get("/{account_id}")
    def metadata(account_id: UUID, identity: Identity):
        _live_assertion(identity)
        with transaction(settings, identity) as (db, user):
            if user["role"] not in ("owner", "trader"):
                raise HTTPException(403, "Access denied")
            response = action_context(db, account_id, identity)
        # A completed read never renews the original signed assertion.
        _live_assertion(identity)
        return response

    return router
