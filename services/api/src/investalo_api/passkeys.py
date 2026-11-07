"""Trusted BFF enrollment lifecycle; SQL storage is not WebAuthn verification."""
import base64
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
import psycopg

from .auth import Assertion, authenticate
from .database import transaction
from .settings import Settings


SAFE_INTEGER = 9_007_199_254_740_991
REGISTRY_COLUMNS = (
    "passkey_id", "tenant_id", "user_id", "rp_id", "credential_id", "user_handle",
    "public_key", "sign_count", "backup_eligible", "backed_up", "storage_version",
    "status", "enrollment_epoch",
)
CLAIM_COLUMNS = ("claim_id", "user_handle", "expires_at", "tenant_id", "user_id", "auth_epoch")
Identity = Annotated[Assertion, Depends(authenticate)]


def valid_rp(value: object) -> str:
    if (
        not isinstance(value, str) or not 1 <= len(value) <= 253
        or not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
                            r"(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*", value)
        or "." not in value and value != "localhost" or re.fullmatch(r"[0-9.]+", value)
    ):
        raise ValueError("Invalid relying party")
    return value


def decode_b64url(value: object, minimum: int, maximum: int) -> bytes:
    if (
        not isinstance(value, str) or len(value) > (maximum * 4 + 2) // 3
        or not re.fullmatch(r"[A-Za-z0-9_-]+", value)
    ):
        raise ValueError("Invalid encoding")
    try:
        decoded = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
    except ValueError:
        raise ValueError("Invalid encoding") from None
    if not minimum <= len(decoded) <= maximum or encode_b64url(decoded) != value:
        raise ValueError("Invalid encoding")
    return decoded


def encode_b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _canonical_uuid(value: str) -> str:
    try:
        if str(UUID(value)) != value:
            raise ValueError()
    except (ValueError, AttributeError):
        raise ValueError("Invalid identifier") from None
    return value


class ClaimRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    token: str = Field(min_length=43, max_length=43, repr=False)
    session_binding: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$", repr=False)

    @field_validator("token")
    @classmethod
    def token_is_canonical(cls, value: str) -> str:
        decode_b64url(value, 32, 32)
        return value


class FinishRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    claim_id: str
    session_binding: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$", repr=False)
    credential_id: str = Field(min_length=1, max_length=1364, repr=False)
    public_key: str = Field(min_length=1, max_length=2731, repr=False)
    sign_count: int = Field(ge=0, le=0xffff_ffff)
    backup_eligible: bool
    backed_up: bool

    @field_validator("claim_id")
    @classmethod
    def canonical_claim(cls, value: str) -> str:
        return _canonical_uuid(value)

    @field_validator("credential_id")
    @classmethod
    def bounded_id(cls, value: str) -> str:
        decode_b64url(value, 1, 1023)
        return value

    @field_validator("public_key")
    @classmethod
    def bounded_key(cls, value: str) -> str:
        decode_b64url(value, 1, 2048)
        return value

    @model_validator(mode="after")
    def backup_consistency(self):
        if self.backed_up and not self.backup_eligible:
            raise ValueError("Invalid backup state")
        return self


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate field")
        result[key] = value
    return result


def parse_request(wire: bytes, model):
    """Reject duplicate keys before model validation, never echo ticket material."""
    try:
        if not isinstance(wire, bytes) or len(wire) > 16_384:
            raise ValueError()
        def nonfinite(_value):
            raise ValueError()
        payload = json.loads(wire.decode("utf-8"), object_pairs_hook=_unique_object, parse_constant=nonfinite)
        return model.model_validate(payload)
    except (ValueError, TypeError, UnicodeError, ValidationError, RecursionError):
        raise HTTPException(422, "Invalid request") from None


def _safe_int(value, minimum=0, maximum=SAFE_INTEGER):
    return type(value) is int and minimum <= value <= maximum


def _encoded_db_bytes(value, minimum, maximum):
    if not isinstance(value, (bytes, memoryview)) or not minimum <= len(value) <= maximum:
        raise HTTPException(503, "Service unavailable")
    return encode_b64url(bytes(value))


def publish_credential(row, *, tenant_id: UUID, user_id: UUID, rp_id: str) -> dict:
    """An exact, owner-bound 13-column wire projection; no free-form fields."""
    if (
        not isinstance(row, dict) or set(row) != set(REGISTRY_COLUMNS)
        or not isinstance(row["passkey_id"], UUID)
        or row["tenant_id"] != tenant_id or row["user_id"] != user_id or row["rp_id"] != rp_id
        or not isinstance(row["tenant_id"], UUID) or not isinstance(row["user_id"], UUID)
        or not _safe_int(row["sign_count"], maximum=0xffff_ffff)
        or not _safe_int(row["storage_version"], minimum=1)
        or not _safe_int(row["enrollment_epoch"])
        or type(row["backup_eligible"]) is not bool or type(row["backed_up"]) is not bool
        or row["backed_up"] and not row["backup_eligible"]
        or row["status"] not in ("active", "revoked")
    ):
        raise HTTPException(503, "Service unavailable")
    return {
        "passkey_id": str(row["passkey_id"]), "tenant_id": str(tenant_id), "user_id": str(user_id),
        "rp_id": rp_id, "credential_id": _encoded_db_bytes(row["credential_id"], 1, 1023),
        "user_handle": _encoded_db_bytes(row["user_handle"], 32, 32),
        "public_key": _encoded_db_bytes(row["public_key"], 1, 2048),
        "sign_count": row["sign_count"], "backup_eligible": row["backup_eligible"],
        "backed_up": row["backed_up"], "storage_version": row["storage_version"],
        "status": row["status"], "enrollment_epoch": row["enrollment_epoch"],
    }


def _execute(db, query, values):
    try:
        return db.execute(query, values)
    except psycopg.Error as error:
        status, detail = {
            "42501": (403, "Access denied"), "40001": (409, "Concurrent change"),
            "22023": (422, "Invalid request"),
        }.get(error.sqlstate, (503, "Service unavailable"))
        raise HTTPException(status, detail) from None


def _configuration(settings: Settings, identity: Assertion):
    try:
        rp_id = valid_rp(getattr(settings, "passkey_rp_id", None))
    except ValueError:
        raise HTTPException(503, "Service unavailable") from None
    if identity.tenant_id is None or not _safe_int(identity.auth_epoch):
        raise HTTPException(403, "Access denied")
    return rp_id


def create_passkey_router(settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/v1/passkeys")

    @router.get("/context")
    def context(identity: Identity):
        rp_id = _configuration(settings, identity)
        with transaction(settings, identity) as (db, user):
            rows = _execute(
                db, "SELECT " + ",".join(REGISTRY_COLUMNS) + " FROM platform.passkey_read(%s,%s,%s)",
                (rp_id, identity.auth_epoch, identity.oidc_auth_time),
            ).fetchall()
            if len(rows) > 1:
                raise HTTPException(503, "Service unavailable")
            credential = publish_credential(rows[0], tenant_id=identity.tenant_id, user_id=user["id"], rp_id=rp_id) if rows else None
            response = {
                "tenant_id": str(identity.tenant_id), "user_id": str(user["id"]),
                "auth_epoch": identity.auth_epoch, "rp_id": rp_id, "credential": credential,
            }
        return response

    @router.post("/enrollment/claim")
    async def claim(request: Request, identity: Identity):
        body = parse_request(await request.body(), ClaimRequest)
        rp_id = _configuration(settings, identity)
        with transaction(settings, identity) as (db, user):
            row = _execute(
                db, "SELECT " + ",".join(CLAIM_COLUMNS) + " FROM platform.passkey_claim_enrollment(%s,%s,%s,%s,%s)",
                (hashlib.sha256(decode_b64url(body.token, 32, 32)).digest(), rp_id,
                 bytes.fromhex(body.session_binding), identity.auth_epoch, identity.oidc_auth_time),
            ).fetchone()
            if (
                not isinstance(row, dict) or set(row) != set(CLAIM_COLUMNS)
                or not isinstance(row["claim_id"], UUID) or row["tenant_id"] != identity.tenant_id
                or row["user_id"] != user["id"] or not _safe_int(row["auth_epoch"])
                or row["auth_epoch"] != identity.auth_epoch
                or not isinstance(row["expires_at"], datetime) or row["expires_at"].tzinfo is None
            ):
                raise HTTPException(503, "Service unavailable")
            response = {
                "claim_id": str(row["claim_id"]), "user_handle": _encoded_db_bytes(row["user_handle"], 32, 32),
                "expires_at": row["expires_at"].astimezone(timezone.utc).isoformat(),
                "tenant_id": str(identity.tenant_id), "user_id": str(user["id"]),
                "auth_epoch": row["auth_epoch"], "rp_id": rp_id,
            }
        # Exiting transaction commits the irrevocable ticket claim before a
        # response allows BFF crypto verification. No crypto is done by this API.
        return response

    @router.post("/enrollment/finish")
    async def finish(request: Request, identity: Identity):
        body = parse_request(await request.body(), FinishRequest)
        rp_id = _configuration(settings, identity)
        with transaction(settings, identity) as (db, user):
            row = _execute(
                db, "SELECT " + ",".join(REGISTRY_COLUMNS) +
                " FROM platform.passkey_finish_enrollment(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (UUID(body.claim_id), bytes.fromhex(body.session_binding),
                 decode_b64url(body.credential_id, 1, 1023), decode_b64url(body.public_key, 1, 2048),
                 body.sign_count, body.backup_eligible, body.backed_up, identity.auth_epoch, identity.oidc_auth_time),
            ).fetchone()
            # The claim selects its immutable RP. Reject another configured RP
            # before commit, rolling back the entire final enrollment/audit write.
            if isinstance(row, dict) and row.get("rp_id") != rp_id:
                raise HTTPException(403, "Access denied")
            response = publish_credential(row, tenant_id=identity.tenant_id, user_id=user["id"], rp_id=rp_id)
            if response["status"] != "active" or response["storage_version"] != 1 or response["enrollment_epoch"] != identity.auth_epoch:
                raise HTTPException(503, "Service unavailable")
            if any(response[field] != getattr(body, field) for field in (
                "credential_id", "public_key", "sign_count", "backup_eligible", "backed_up",
            )):
                raise HTTPException(503, "Service unavailable")
        return response

    return router
