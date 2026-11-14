"""Own-account read contract; source reader is injected by trusted runtime only."""
from datetime import datetime, timezone

from fastapi import HTTPException
from investalo_trading.futures_paper_view import asset_snapshot


def read_assets(db, identity, reader, *, now=None):
    rows = db.execute(
        "SELECT id,name,status FROM platform.accounts "
        "WHERE tenant_id=%s AND broker='bitget' AND mode='paper' AND currency='USDT' "
        "ORDER BY created_at,id LIMIT 20", (identity.tenant_id,),
    ).fetchall()
    accounts = []
    now = now or datetime.now(timezone.utc)
    for row in rows:
        account_id = str(row["id"])
        try:
            state = reader(str(identity.tenant_id), account_id) if reader is not None else None
            snapshot = (asset_snapshot(state, tenant_id=str(identity.tenant_id), account_id=account_id,
                                       now=now, account_ready=row["status"] == "ready")
                        if state is not None else None)
        except Exception:
            # No foreign raw state, reader path or runtime exception in HTTP.
            raise HTTPException(503, "Futures status unavailable") from None
        accounts.append({"account_id": account_id, "account_name": row["name"], "snapshot": snapshot})
    return {"schema_version": "futures-paper-assets/1", "tenant_id": str(identity.tenant_id),
            "mode": "paper", "live_enabled": False, "accounts": accounts}
