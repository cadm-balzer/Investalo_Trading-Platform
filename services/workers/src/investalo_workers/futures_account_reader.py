"""Explicit private actor delegation, scoped RLS reads only; no API assertion."""
from dataclasses import dataclass, field
from datetime import datetime, timezone

import psycopg
from psycopg.rows import dict_row

from investalo_trading.futures_ledger import timestamp
from investalo_trading.futures_paper_account import PaperAccountBinding, PaperSettingsEvidence


class PaperAccountRejected(RuntimeError):
    """Generic account/settings read rejection, without SQL or connection details."""


@dataclass(frozen=True)
class FuturesPaperAccountReader:
    binding: PaperAccountBinding
    connection_parameters: dict = field(repr=False)
    clock: object = lambda: datetime.now(timezone.utc)

    def __call__(self):
        if type(self.binding) is not PaperAccountBinding:
            raise PaperAccountRejected("own private actor delegation required")
        b = self.binding
        try:
            with psycopg.connect(**self.connection_parameters, row_factory=dict_row) as db:
                db.execute("SET TRANSACTION READ ONLY")
                db.execute("SET LOCAL statement_timeout='3000ms'")
                db.execute("SET LOCAL lock_timeout='1000ms'")
                role = db.execute(
                    "SELECT current_user name,session_user login,rolsuper,rolbypassrls,"
                    "rolcreaterole,rolcreatedb FROM pg_roles WHERE rolname=current_user").fetchone()
                if (not role or role["name"] != "investalo_runtime" or role["login"] != "investalo_runtime"
                        or any(role[k] for k in ("rolsuper", "rolbypassrls", "rolcreaterole", "rolcreatedb"))):
                    raise ValueError("restricted runtime LOGIN required")
                db.execute(
                    "SELECT set_config('app.oidc_issuer',%s,true),set_config('app.oidc_subject',%s,true)",
                    (b.oidc_issuer, b.oidc_subject))
                user = db.execute(
                    "SELECT id,auth_epoch,reauth_after FROM platform.users "
                    "WHERE id=%s AND oidc_issuer=%s AND oidc_subject=%s AND active",
                    (b.user_id, b.oidc_issuer, b.oidc_subject)).fetchone()
                if (not user or user["auth_epoch"] != b.auth_epoch
                        or b.authorized_at < user["reauth_after"]):
                    raise ValueError("revoked delegated actor")
                db.execute("SELECT set_config('app.user_id',%s,true)", (b.user_id,))
                membership = db.execute(
                    "SELECT role FROM platform.memberships WHERE tenant_id=%s AND user_id=%s AND active",
                    (b.tenant_id, b.user_id)).fetchone()
                if not membership or membership["role"] not in ("owner", "trader"):
                    raise ValueError("current own owner/trader delegation required")
                db.execute("SELECT set_config('app.tenant_id',%s,true)", (b.tenant_id,))
                row = db.execute(
                    "SELECT a.status,s.revision,s.basket_limit FROM platform.accounts a "
                    "LEFT JOIN platform.futures_paper_settings s ON s.tenant_id=a.tenant_id AND s.account_id=a.id "
                    "WHERE a.tenant_id=%s AND a.id=%s AND a.broker='bitget' AND a.mode='paper' "
                    "AND a.currency='USDT'", (b.tenant_id, b.account_id)).fetchone()
                if not row or row["status"] != "ready":
                    raise ValueError("own ready Classic USDT Paper account required")
                now = timestamp(self.clock())
                if b.authorized_at > now:
                    raise ValueError("future delegated actor")
                return PaperSettingsEvidence(b.tenant_id, b.account_id, b.binding_digest,
                                             row["revision"] or 0, row["basket_limit"] or 5, now)
        except Exception:
            raise PaperAccountRejected("own Paper account/settings unavailable") from None
