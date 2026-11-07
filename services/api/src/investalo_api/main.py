"""Authenticated persistence foundation; live and broker dispatch are absent."""
import hashlib
import json
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict
import psycopg
from psycopg.types.json import Jsonb

from .auth import Assertion, authenticate
from .body_limit import BodyLimitMiddleware
from .credential_action import action_context
from .passkeys import create_passkey_router
from .passkey_action_proofs import create_passkey_action_router
from .database import SCHEMA_VERSION, assert_runtime, connect, transaction
from .settings import Settings
from .research_result import publish_result
from .research_spec import public_source, specification


class BacktestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    symbol: Literal["BTC/USDT", "ETH/USDT"]
    timeframe: Literal["4h"] = "4h"
    dataset_id: UUID | None = None


Identity = Annotated[Assertion, Depends(authenticate)]


def _job(row: dict) -> dict:
    return {
        "id": str(row["id"]), "kind": row["kind"], "status": row["status"],
        "payload": row["payload"], "created_at": row["created_at"].isoformat(),
        "result_summary": publish_result(row.get("result_summary"), summary=True),
    }


JOURNAL_EVENTS = {
    "entry_blocked": "Einstieg durch eine geprüfte Regel blockiert.",
    "cancel_order": "Simulierter Auftrag zur Stornierung vorgemerkt.",
    "protection_updated": "Schutzgrenze aktualisiert.",
    "data_rejected": "Marktdatenprüfung fehlgeschlagen.",
    "manual_reserve_available": "Manuelle Reserve kann geprüft werden.",
    "simulated_order_cancelled": "Simulierter Auftrag storniert.",
    "paper_fill": "Simulierter Paper-Fill protokolliert.",
    "risk_stop": "Unabhängige Risikogrenze ausgelöst.",
}


def _journal(row: dict) -> dict:
    # Free-form persistence can contain operational/private data. Only reviewed
    # public fields and fixed messages cross this boundary.
    event_type = row["event_type"] if row["event_type"] in JOURNAL_EVENTS else "event"
    result = {
        "id": str(row["id"]), "account_id": str(row["account_id"]),
        "event_type": event_type, "created_at": row["created_at"].isoformat(),
        "message": JOURNAL_EVENTS.get(event_type, "Tradingereignis protokolliert."),
    }
    payload = row["payload"]
    if isinstance(payload, dict) and payload.get("symbol") in ("BTC/USDT", "ETH/USDT", "XAUUSD"):
        result["symbol"] = payload["symbol"]
    return result


def create_app(settings: Settings | None = None) -> FastAPI:
    application = FastAPI(title="Investalo API", docs_url=None, redoc_url=None, openapi_url=None)
    application.state.settings = settings if settings is not None else Settings.from_environment()
    application.include_router(create_passkey_router(application.state.settings))
    application.include_router(create_passkey_action_router(application.state.settings))

    @application.exception_handler(RequestValidationError)
    async def invalid_request(_request: Request, _error: RequestValidationError):
        return JSONResponse({"detail": "Invalid request"}, status_code=422)

    @application.middleware("http")
    async def privacy(request: Request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @application.get("/health/live")
    def live():
        return {"status": "ok"}

    @application.get("/health/ready")
    def ready():
        configuration = application.state.settings
        if not configuration.internal_key or not configuration.oidc_issuer:
            return JSONResponse({"status": "unavailable"}, status_code=503)
        try:
            with connect(configuration) as connection:
                assert_runtime(connection)
                present = connection.execute(
                    "SELECT 1 FROM platform.schema_migrations WHERE version=%s",
                    (SCHEMA_VERSION,),
                ).fetchone()
                if not present:
                    return JSONResponse({"status": "unavailable"}, status_code=503)
        except (psycopg.Error, HTTPException):
            return JSONResponse({"status": "unavailable"}, status_code=503)
        return {"status": "ok"}

    @application.get("/v1/trading-config")
    def trading_config():
        return {
            "mode": "paper", "live_enabled": False,
            "assets": ["BTC/USDT", "ETH/USDT"], "timeframe": "4h", "leverage": "1",
            "initial_equity": "10000", "principal_per_asset": "500",
            "cost_reserve_per_asset": "5", "regular_stages": 5,
            "manual_reserve": True, "daily_loss_limit": "0.06",
            "initial_loss_limit": "0.08", "first_fill_price_exit": "0.45",
            "simulation_only": True,
        }

    @application.get("/v1/me")
    def me(identity: Identity):
        with transaction(application.state.settings, identity, tenant_required=False) as (db, user):
            memberships = db.execute(
                "SELECT m.tenant_id,t.name AS tenant_name,m.role FROM platform.memberships m "
                "JOIN platform.tenants t ON t.id=m.tenant_id "
                "WHERE m.user_id=%s AND m.active ORDER BY t.name,m.tenant_id",
                (user["id"],),
            ).fetchall()
            return {
                "user": {"id": str(user["id"]), "subject": identity.subject, "auth_epoch": user["auth_epoch"]},
                "memberships": [
                    {**row, "tenant_id": str(row["tenant_id"])} for row in memberships
                ],
                "live_enabled": False,
            }

    @application.get("/v1/overview")
    def overview(identity: Identity):
        with transaction(application.state.settings, identity) as (db, user):
            accounts = db.execute(
                "SELECT id,name,broker,mode,currency,status FROM platform.accounts "
                "ORDER BY created_at,id LIMIT 50"
            ).fetchall()
            positions = db.execute(
                "SELECT account_id,symbol,quantity,average_price,observed_at "
                "FROM platform.positions ORDER BY observed_at DESC LIMIT 100"
            ).fetchall()
            journal = db.execute(
                "SELECT id,account_id,event_type,payload,created_at FROM platform.journal "
                "ORDER BY created_at DESC,id LIMIT 50"
            ).fetchall()
            jobs = db.execute(
                "SELECT id,kind,status,payload,created_at,result_summary FROM platform.jobs "
                "ORDER BY created_at DESC,id LIMIT 20"
            ).fetchall()
            # Empty persistence stays empty; no invented balances or performance.
            return jsonable_encoder({
                "mode": "paper", "live_enabled": False, "tenant_id": str(identity.tenant_id),
                "role": user["role"], "accounts": accounts, "positions": positions,
                "journal": [_journal(row) for row in journal], "jobs": [_job(row) for row in jobs],
            }, custom_encoder={Decimal: str})

    @application.get("/v1/credential-actions/{account_id}")
    def credential_actions(account_id: UUID, identity: Identity):
        with transaction(application.state.settings, identity) as (db, user):
            if user["role"] not in ("owner", "trader"):
                raise HTTPException(403, "Access denied")
            return action_context(db, account_id, identity)

    @application.get("/v1/jobs")
    def jobs(identity: Identity, limit: Annotated[int, Query(ge=1, le=100)] = 20):
        with transaction(application.state.settings, identity) as (db, _user):
            rows = db.execute(
                "SELECT id,kind,status,payload,created_at,result_summary FROM platform.jobs "
                "ORDER BY created_at DESC,id LIMIT %s", (limit,),
            ).fetchall()
            return {"tenant_id": str(identity.tenant_id), "jobs": [_job(row) for row in rows]}

    @application.get("/v1/jobs/{job_id}")
    def job_detail(job_id: UUID, identity: Identity):
        with transaction(application.state.settings, identity) as (db, _user):
            row = db.execute(
                "SELECT id,kind,status,payload,created_at,result,result_summary,failure_code "
                "FROM platform.jobs WHERE id=%s", (job_id,),
            ).fetchone()
            if not row:
                raise HTTPException(404, "Job unavailable")
            return {
                "tenant_id": str(identity.tenant_id), **_job(row),
                "result": publish_result(row["result"]), "failure_code": row["failure_code"],
            }

    @application.get("/v1/datasets")
    def datasets(identity: Identity):
        with transaction(application.state.settings, identity) as (db, _user):
            rows = db.execute(
                "SELECT id,symbol,timeframe,source,synthetic,bar_count,starts_at,ends_at,"
                "data_digest,purpose,coverage_complete FROM platform.research_datasets "
                "WHERE purpose IN ('research','test') ORDER BY created_at DESC,id LIMIT 100"
            ).fetchall()
            return {"tenant_id": str(identity.tenant_id), "datasets": [
                {
                    "id": str(row["id"]), "symbol": row["symbol"], "timeframe": row["timeframe"],
                    "source": public_source(row["source"]), "synthetic": row["synthetic"],
                    "bar_count": row["bar_count"], "start": row["starts_at"].isoformat(),
                    "end": row["ends_at"].isoformat(), "data_digest": row["data_digest"],
                    "purpose": row["purpose"], "coverage_complete": row["coverage_complete"],
                } for row in rows
            ]}

    @application.post("/v1/backtests", status_code=202)
    def backtest(
        body: BacktestRequest, identity: Identity,
        idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
    ):
        payload = body.model_dump(mode="json", exclude_none=True)
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        with transaction(application.state.settings, identity) as (db, user):
            if user["role"] not in ("owner", "trader", "researcher"):
                raise HTTPException(403, "Access denied")
            # Resolve retries before selecting newer data: one request key always
            # points at the originally frozen dataset, even after new imports.
            existing = db.execute(
                "SELECT id,kind,status,payload,created_at,result_summary,payload_hash "
                "FROM platform.jobs WHERE tenant_id=%s AND idempotency_key=%s",
                (identity.tenant_id, idempotency_key),
            ).fetchone()
            if existing:
                if existing["payload_hash"] != digest:
                    raise HTTPException(409, "Idempotency key already used")
                return {"tenant_id": str(identity.tenant_id), **_job(existing)}
            # Serialize concurrent equal-key requests before resolving the
            # snapshot. Locks are transaction-scoped; no raw input enters SQL.
            db.execute("SELECT pg_advisory_xact_lock(%s)", (
                int.from_bytes(hashlib.sha256(
                    f"{identity.tenant_id}:{idempotency_key}".encode()
                ).digest()[:8], "big", signed=True),
            ))
            existing = db.execute(
                "SELECT id,kind,status,payload,created_at,result_summary,payload_hash "
                "FROM platform.jobs WHERE tenant_id=%s AND idempotency_key=%s",
                (identity.tenant_id, idempotency_key),
            ).fetchone()
            if existing:
                if existing["payload_hash"] != digest:
                    raise HTTPException(409, "Idempotency key already used")
                return {"tenant_id": str(identity.tenant_id), **_job(existing)}
            if body.dataset_id is None:
                dataset = db.execute(
                    "SELECT id,data_digest FROM platform.research_datasets WHERE symbol=%s "
                    "AND purpose='research' AND NOT synthetic ORDER BY created_at DESC,id LIMIT 1",
                    (body.symbol,),
                ).fetchone()
            else:
                dataset = db.execute(
                    "SELECT id,data_digest FROM platform.research_datasets WHERE id=%s AND symbol=%s "
                    "AND purpose IN ('research','test')", (body.dataset_id, body.symbol),
                ).fetchone()
            if not dataset:
                raise HTTPException(409, "dataset_unavailable")
            frozen = specification()
            payload = {**payload, "dataset_id": str(dataset["id"]), "data_digest": dataset["data_digest"]}
            row = db.execute(
                "INSERT INTO platform.jobs(id,tenant_id,created_by,kind,payload,payload_hash,idempotency_key,"
                "dataset_id,strategy_version,configuration_digest,cost_digest,frozen_specification) "
                "VALUES (%s,%s,%s,'backtest',%s,%s,%s,%s,%s,%s,%s,%s) "
                "RETURNING id,kind,status,payload,created_at,result_summary",
                (uuid4(), identity.tenant_id, user["id"], Jsonb(payload), digest, idempotency_key,
                 dataset["id"], frozen["strategy_version"], frozen["configuration_digest"],
                 frozen["cost_digest"], Jsonb(frozen)),
            ).fetchone()
            return {"tenant_id": str(identity.tenant_id), **_job(row)}

    # The last added middleware wraps the parser and all other middleware.
    application.add_middleware(BodyLimitMiddleware)
    return application


app = create_app()
