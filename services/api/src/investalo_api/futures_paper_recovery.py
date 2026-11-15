"""Authenticated own Paper recovery only; browser never supplies reconciliation."""
from datetime import datetime, timezone
from typing import Annotated, Literal
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from investalo_trading.futures_paper_recovery import PaperRecoveryRequest, recovery_snapshot


class RecoveryBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    account_id: Annotated[str, Field(pattern=r"^[0-9a-f-]{36}$")]
    symbol: Annotated[str, Field(pattern=r"^[A-Z0-9]{2,16}USDT$")]
    cycle: Annotated[int, Field(ge=1, le=2**53-2)]
    revision: Annotated[int, Field(ge=0, le=2**53-2)]
    state_digest: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    event_id: Annotated[str, Field(pattern=r"^[0-9a-f-]{36}$")]
    consent: Literal[True]

    @field_validator("consent", mode="before")
    @classmethod
    def explicit_consent(cls, value):
        if value is not True:
            raise ValueError("explicit boolean manual consent required")
        return value


def read_recovery(db, identity, user, reader, executor, *, now=None):
    now = now or datetime.now(timezone.utc)
    recover = getattr(reader, "recovery", None)
    if not callable(recover):
        raise HTTPException(503, "Futures status unavailable")
    accounts = db.execute(
        "SELECT a.id,a.status,s.revision,s.basket_limit FROM platform.accounts a "
        "LEFT JOIN platform.futures_paper_settings s ON s.tenant_id=a.tenant_id AND s.account_id=a.id "
        "WHERE a.tenant_id=%s AND a.broker='bitget' AND a.mode='paper' AND a.currency='USDT' "
        "ORDER BY a.created_at,a.id LIMIT 20",
        (identity.tenant_id,)).fetchall()
    assets, known = [], 0
    try:
        for account in accounts:
            state = recover(str(identity.tenant_id), str(account["id"]))
            if state is None:
                continue
            if (state.tenant_id, state.account_id) != (str(identity.tenant_id), str(account["id"])):
                raise ValueError("foreign current Paper recovery")
            known += 1
            planned = (state.settings_revision, state.configured_limit) == (
                account["revision"] or 0, account["basket_limit"] or 5)
            available = getattr(executor, "available", None)
            executable = callable(available) and available(
                str(identity.tenant_id), str(account["id"]), str(user["id"]))
            assets.extend(recovery_snapshot(state, now,
                account_ready=account["status"] == "ready" and planned,
                can_edit=user["role"] in ("owner", "trader"), executable=executable))
    except Exception:
        raise HTTPException(503, "Futures status unavailable") from None
    if not known:
        raise HTTPException(503, "Futures status unavailable")
    return dict(schema_version="futures-recovery-status/1", tenant_id=str(identity.tenant_id),
                mode="paper", live_enabled=False, observed_at=now.isoformat(), assets=assets)


def write_recovery(db, identity, user, body, reader, executor):
    if user["role"] not in ("owner", "trader"):
        raise HTTPException(403, "Access denied")
    if executor is None:
        raise HTTPException(503, "Futures recovery unavailable")
    try:
        account_id = str(UUID(body.account_id))
        event_id = str(UUID(body.event_id))
        if account_id != body.account_id or event_id != body.event_id:
            raise ValueError("canonical UUID required")
    except ValueError:
        raise HTTPException(400, "Invalid request") from None
    own = db.execute(
        "SELECT id FROM platform.accounts WHERE tenant_id=%s AND id=%s "
        "AND broker='bitget' AND mode='paper' AND currency='USDT' AND status='ready'",
        (identity.tenant_id, account_id)).fetchone()
    if not own:
        raise HTTPException(404, "Not found")
    request = PaperRecoveryRequest(str(identity.tenant_id), account_id, str(user["id"]),
        "BITGET:" + body.symbol, body.cycle, body.revision, body.state_digest, event_id, body.consent)
    try:
        executor(request)
    except PermissionError:
        raise HTTPException(403, "Access denied") from None
    except ValueError:
        raise HTTPException(409, "Recovery changed or blocked; reload") from None
    except Exception:
        # Includes writer-busy, fsync uncertainty and post-commit publication loss. No retry.
        raise HTTPException(503, "Recovery unconfirmed; reload") from None
    result = read_recovery(db, identity, user, reader, executor)
    if any(a["account_id"] == account_id and a["symbol"] == body.symbol for a in result["assets"]):
        raise HTTPException(503, "Recovery unconfirmed; reload")
    return result
