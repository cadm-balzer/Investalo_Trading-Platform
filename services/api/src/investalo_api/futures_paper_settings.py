"""Persist a Paper planning preference; current Futures balances remain absent."""
from typing import Annotated
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field


class BasketSettingsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    expected_revision: Annotated[int, Field(ge=0, le=2**53-2)]
    basket_limit: Annotated[int, Field(ge=3, le=7)]


def public_settings(account, row, *, can_edit):
    return {
        "account_id": str(account["id"]), "account_name": account["name"],
        "revision": row["revision"] if row else 0,
        "basket_limit": row["basket_limit"] if row else 5,
        "saved": row is not None, "can_edit": can_edit,
        "leverage": "2", "runtime_ready": False,
        # Never substitute Spot cash, historical end-MTM or user input.
        "recommendation": None, "recommendation_reason": "futures_runtime_missing",
    }


def read_settings(db, identity, user):
    rows = db.execute(
        "SELECT a.id,a.name,s.revision,s.basket_limit FROM platform.accounts a "
        "LEFT JOIN platform.futures_paper_settings s ON s.tenant_id=a.tenant_id AND s.account_id=a.id "
        "WHERE a.tenant_id=%s AND a.broker='bitget' AND a.mode='paper' AND a.currency='USDT' "
        "ORDER BY a.created_at,a.id LIMIT 20", (identity.tenant_id,),
    ).fetchall()
    return {
        "schema_version": "futures-paper-settings/1", "tenant_id": str(identity.tenant_id),
        "mode": "paper", "live_enabled": False,
        "accounts": [public_settings(r, r if r["revision"] is not None else None,
                                    can_edit=user["role"] in ("owner", "trader")) for r in rows],
    }


def write_settings(db, identity, user, account_id: UUID, body: BasketSettingsRequest):
    if user["role"] not in ("owner", "trader"):
        raise HTTPException(403, "Access denied")
    # Serialize even first creation without granting UPDATE on platform.accounts.
    db.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
               ("futures-paper-settings/"+str(identity.tenant_id)+"/"+str(account_id),))
    membership = db.execute(
        "SELECT role FROM platform.memberships WHERE tenant_id=%s AND user_id=%s "
        "AND active AND role IN ('owner','trader')",
        (identity.tenant_id, user["id"]),
    ).fetchone()
    if not membership:
        raise HTTPException(403, "Access denied")
    account = db.execute(
        "SELECT id,name FROM platform.accounts WHERE tenant_id=%s AND id=%s "
        "AND broker='bitget' AND mode='paper' AND currency='USDT'",
        (identity.tenant_id, account_id),
    ).fetchone()
    if not account:
        raise HTTPException(404, "Not found")
    current = db.execute(
        "SELECT revision,basket_limit FROM platform.futures_paper_settings "
        "WHERE tenant_id=%s AND account_id=%s FOR UPDATE", (identity.tenant_id, account_id),
    ).fetchone()
    if body.expected_revision != (current["revision"] if current else 0):
        raise HTTPException(409, "Settings changed; reload")
    revision = body.expected_revision + 1
    db.execute(
        "INSERT INTO platform.futures_paper_settings(tenant_id,account_id,revision,basket_limit) "
        "VALUES (%s,%s,%s,%s) ON CONFLICT(tenant_id,account_id) DO UPDATE "
        "SET revision=EXCLUDED.revision,basket_limit=EXCLUDED.basket_limit,updated_at=now()",
        (identity.tenant_id, account_id, revision, body.basket_limit),
    )
    db.execute(
        "INSERT INTO platform.futures_paper_settings_audit"
        "(tenant_id,account_id,revision,actor_id,basket_limit) VALUES (%s,%s,%s,%s,%s)",
        (identity.tenant_id, account_id, revision, user["id"], body.basket_limit),
    )
    return public_settings(account, {"revision": revision, "basket_limit": body.basket_limit}, can_edit=True)
