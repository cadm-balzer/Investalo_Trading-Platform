"""Trusted BFF action-proof lifecycle, separate from broker credential execution.

The API authenticates request-bound BFF assertions and commits the one-use claim
before BFF WebAuthn verification. Neither this API nor SQL verifies signatures.
Original OIDC auth_time is unchanged; checked_at records the fresh passkey proof.
"""
from time import time
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .auth import Assertion, authenticate
from .database import transaction
from .credential_action import publish_context
from .passkeys import (
    SAFE_INTEGER, REGISTRY_COLUMNS, _canonical_uuid, _configuration,
    _encoded_db_bytes, _execute, _safe_int, decode_b64url, parse_request,
    publish_credential,
)
from .settings import Settings


Identity = Annotated[Assertion, Depends(authenticate)]


class Target(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    action: Literal["register", "replace", "revoke"]
    platform_account_id: str
    connection_id: str
    expected_revision: int | None = Field(default=None, ge=1, le=SAFE_INTEGER)
    expected_storage: int | None = Field(default=None, ge=1, le=SAFE_INTEGER - 1)

    @field_validator("platform_account_id", "connection_id")
    @classmethod
    def canonical_id(cls, value):
        return _canonical_uuid(value)

    @model_validator(mode="after")
    def exact_action_shape(self):
        versions = {"expected_revision", "expected_storage"}
        if self.action == "register":
            if self.model_fields_set & versions:
                raise ValueError("Registration cannot carry versions")
        elif not versions <= self.model_fields_set or self.expected_revision is None or self.expected_storage is None:
            raise ValueError("Existing connection versions required")
        elif self.action == "replace" and self.expected_revision == SAFE_INTEGER:
            raise ValueError("Credential revision exhausted")
        return self


class BoundRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    session_binding: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$", repr=False)


class PrepareRequest(BoundRequest):
    target: Target
    challenge: str = Field(min_length=43, max_length=43, repr=False)
    confirmation_hash: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$", repr=False)
    session_expires_at: int = Field(ge=1, le=SAFE_INTEGER)

    @field_validator("challenge")
    @classmethod
    def canonical_challenge(cls, value):
        decode_b64url(value, 32, 32)
        return value


class AttemptRequest(BoundRequest):
    attempt_id: str

    @field_validator("attempt_id")
    @classmethod
    def canonical_attempt(cls, value):
        return _canonical_uuid(value)


class FinishRequest(AttemptRequest):
    new_counter: int = Field(ge=0, le=0xffff_ffff)
    backup_eligible: bool
    backed_up: bool
    checked_at: int = Field(ge=1, le=SAFE_INTEGER)

    @model_validator(mode="after")
    def backup_consistency(self):
        if self.backed_up and not self.backup_eligible:
            raise ValueError("Invalid backup state")
        return self


class GrantRequest(BoundRequest):
    grant_id: str

    @field_validator("grant_id")
    @classmethod
    def canonical_grant(cls, value):
        return _canonical_uuid(value)


class ConfirmRequest(GrantRequest):
    confirmation_hash: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$", repr=False)


ATTEMPT_COLUMNS = (
    "attempt_id", "tenant_id", "user_id", "auth_epoch", "rp_id", "target", "metadata",
    "passkey_id", "passkey_storage", "sign_count", "backup_eligible", "backed_up",
    "credential_id", "user_handle", "public_key", "enrollment_epoch",
    "session_binding", "challenge", "confirmation_hash",
    "prepared_at", "expires_at", "session_expires_at",
)
GRANT_COLUMNS = (
    "grant_id", "attempt_id", "tenant_id", "user_id", "auth_epoch", "rp_id",
    "target", "metadata", "passkey_id", "passkey_version", "session_binding",
    "confirmation_hash", "checked_at", "expires_at", "session_expires_at",
)


def _unavailable():
    return HTTPException(503, "Service unavailable")


def _hex_bytes(value):
    if not isinstance(value, (bytes, memoryview)) or len(value) != 32:
        raise _unavailable()
    return bytes(value).hex()


def _metadata(value, identity):
    """Validate the exact safe005 shape before publishing its frozen snapshot."""
    try:
        if not isinstance(value, dict) or set(value) != {"tenant_id", "auth_epoch", "account", "connection"}:
            raise ValueError()
        account, connection = value["account"], value["connection"]
        if not isinstance(account, dict) or set(account) != {"id", "name", "broker", "mode", "status"}:
            raise ValueError()
        if connection is not None and (
            not isinstance(connection, dict)
            or set(connection) != {"connection_id", "credential_revision", "storage_version", "status"}
        ):
            raise ValueError()
        account_id = UUID(_canonical_uuid(account["id"]))
        row = {
            "tenant_id": UUID(_canonical_uuid(value["tenant_id"])), "auth_epoch": value["auth_epoch"],
            "account_id": account_id, "account_name": account["name"], "account_broker": account["broker"],
            "account_mode": account["mode"], "account_status": account["status"],
            "connection_id": UUID(_canonical_uuid(connection["connection_id"])) if connection else None,
            "credential_revision": connection["credential_revision"] if connection else None,
            "storage_version": connection["storage_version"] if connection else None,
            "connection_status": connection["status"] if connection else None,
        }
        return publish_context(row, account_id, identity)
    except (ValueError, TypeError, AttributeError, KeyError, HTTPException):
        raise _unavailable() from None


def _target(value, metadata):
    try:
        parsed = Target.model_validate(value)
        result = parsed.model_dump(exclude_unset=True)
        if parsed.platform_account_id != metadata["account"]["id"]:
            raise ValueError()
        connection = metadata["connection"]
        if parsed.action == "register":
            if connection is not None or metadata["account"]["status"] == "paused":
                raise ValueError()
        elif (
            connection is None or connection["status"] != "active"
            or parsed.connection_id != connection["connection_id"]
            or parsed.expected_revision != connection["credential_revision"]
            or parsed.expected_storage != connection["storage_version"]
            or parsed.action == "replace" and metadata["account"]["status"] == "paused"
        ):
            raise ValueError()
        return result
    except (ValueError, TypeError, AttributeError, KeyError):
        raise _unavailable() from None


def _owner(row, identity, user_id, rp_id, columns):
    if (
        not isinstance(row, dict) or set(row) != set(columns)
        or not isinstance(row["attempt_id"], UUID)
        or row["tenant_id"] != identity.tenant_id or row["user_id"] != user_id
        or not isinstance(row["tenant_id"], UUID) or not isinstance(row["user_id"], UUID)
        or row["rp_id"] != rp_id or not _safe_int(row["auth_epoch"])
        or row["auth_epoch"] != identity.auth_epoch
        or not _safe_int(row["session_expires_at"], minimum=1)
        or not _safe_int(row["expires_at"], minimum=1)
        or row["expires_at"] > row["session_expires_at"]
        or row["expires_at"] <= int(time())
    ):
        raise _unavailable()
    metadata = _metadata(row["metadata"], identity)
    return {
        "attempt_id": str(row["attempt_id"]), "tenant_id": str(identity.tenant_id),
        "user_id": str(user_id), "auth_epoch": identity.auth_epoch, "rp_id": rp_id,
        "target": _target(row["target"], metadata), "metadata": metadata,
        "session_binding": _hex_bytes(row["session_binding"]),
        "confirmation_hash": _hex_bytes(row["confirmation_hash"]),
        "expires_at": row["expires_at"], "session_expires_at": row["session_expires_at"],
    }


def publish_attempt(row, identity, user_id, rp_id):
    result = _owner(row, identity, user_id, rp_id, ATTEMPT_COLUMNS)
    if (
        not _safe_int(row["prepared_at"], minimum=1) or row["prepared_at"] > int(time())
        or row["expires_at"] <= row["prepared_at"]
        or row["expires_at"] > row["prepared_at"] + 120
        or not _safe_int(row["passkey_storage"], minimum=1, maximum=SAFE_INTEGER - 1)
        or row["enrollment_epoch"] != identity.auth_epoch
    ):
        raise _unavailable()
    key = {field: row[field] for field in REGISTRY_COLUMNS if field in row}
    key.update(storage_version=row["passkey_storage"], status="active")
    credential = publish_credential(key, tenant_id=identity.tenant_id, user_id=user_id, rp_id=rp_id)
    return {**result, "credential": credential,
            "challenge": _encoded_db_bytes(row["challenge"], 32, 32),
            "prepared_at": row["prepared_at"]}


def publish_grant(row, identity, user_id, rp_id):
    result = _owner(row, identity, user_id, rp_id, GRANT_COLUMNS)
    if (
        not isinstance(row["grant_id"], UUID) or not isinstance(row["passkey_id"], UUID)
        or not _safe_int(row["passkey_version"], minimum=2)
        or not _safe_int(row["checked_at"], minimum=1) or row["checked_at"] > int(time())
        or row["expires_at"] <= row["checked_at"] or row["expires_at"] > row["checked_at"] + 120
    ):
        raise _unavailable()
    return {**result, "grant_id": str(row["grant_id"]), "passkey_id": str(row["passkey_id"]),
            "passkey_version": row["passkey_version"], "checked_at": row["checked_at"]}


def _query(db, function, columns, values):
    return _execute(
        db, "SELECT " + ",".join(columns) + " FROM platform." + function + "(" +
        ",".join(["%s"] * len(values)) + ")", values,
    ).fetchone()


def _check_binding(response, request):
    if response["session_binding"] != request.session_binding:
        raise _unavailable()


def create_passkey_action_router(settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/v1/passkey-action-proofs")

    @router.post("/prepare")
    async def prepare(request: Request, identity: Identity):
        body = parse_request(await request.body(), PrepareRequest)
        rp_id = _configuration(settings, identity)
        with transaction(settings, identity) as (db, user):
            row = _query(db, "passkey_action_prepare", ATTEMPT_COLUMNS, (
                UUID(body.target.platform_account_id), body.target.action,
                UUID(body.target.connection_id) if body.target.action == "register" else None,
                rp_id, decode_b64url(body.challenge, 32, 32), bytes.fromhex(body.session_binding),
                bytes.fromhex(body.confirmation_hash), body.session_expires_at,
                identity.auth_epoch, identity.oidc_auth_time,
            ))
            response = publish_attempt(row, identity, user["id"], rp_id)
            _check_binding(response, body)
            if response["target"] != body.target.model_dump(exclude_unset=True):
                # SQL derives current metadata. Never silently upgrade a stale
                # browser preview to a newly prepared target/version.
                raise HTTPException(409, "Concurrent change")
            if (
                response["challenge"] != body.challenge
                or response["confirmation_hash"] != body.confirmation_hash
                or response["session_expires_at"] != body.session_expires_at
            ):
                raise _unavailable()
        return response

    @router.post("/claim")
    async def claim(request: Request, identity: Identity):
        body = parse_request(await request.body(), AttemptRequest)
        rp_id = _configuration(settings, identity)
        with transaction(settings, identity) as (db, user):
            row = _query(db, "passkey_action_claim", ATTEMPT_COLUMNS, (
                UUID(body.attempt_id), rp_id, bytes.fromhex(body.session_binding),
                identity.auth_epoch, identity.oidc_auth_time,
            ))
            response = publish_attempt(row, identity, user["id"], rp_id)
            _check_binding(response, body)
            if response["attempt_id"] != body.attempt_id:
                raise _unavailable()
        # Commit the one-use claim before replying to BFF crypto verification.
        return response

    @router.post("/finish")
    async def finish(request: Request, identity: Identity):
        body = parse_request(await request.body(), FinishRequest)
        rp_id = _configuration(settings, identity)
        with transaction(settings, identity) as (db, user):
            row = _query(db, "passkey_action_finish", GRANT_COLUMNS, (
                UUID(body.attempt_id), rp_id, bytes.fromhex(body.session_binding),
                body.new_counter, body.backup_eligible, body.backed_up, body.checked_at,
                identity.auth_epoch, identity.oidc_auth_time,
            ))
            response = publish_grant(row, identity, user["id"], rp_id)
            _check_binding(response, body)
            if response["attempt_id"] != body.attempt_id or response["checked_at"] != body.checked_at:
                raise _unavailable()
        return response

    @router.post("/grant")
    async def grant(request: Request, identity: Identity):
        body = parse_request(await request.body(), GrantRequest)
        rp_id = _configuration(settings, identity)
        with transaction(settings, identity) as (db, user):
            row = _query(db, "passkey_action_read_grant", GRANT_COLUMNS, (
                UUID(body.grant_id), rp_id, bytes.fromhex(body.session_binding),
                identity.auth_epoch, identity.oidc_auth_time,
            ))
            response = publish_grant(row, identity, user["id"], rp_id)
            _check_binding(response, body)
            if response["grant_id"] != body.grant_id:
                raise _unavailable()
        return response

    @router.post("/confirm")
    async def confirm(request: Request, identity: Identity):
        body = parse_request(await request.body(), ConfirmRequest)
        rp_id = _configuration(settings, identity)
        with transaction(settings, identity) as (db, user):
            row = _query(db, "passkey_action_confirm", GRANT_COLUMNS, (
                UUID(body.grant_id), rp_id, bytes.fromhex(body.session_binding),
                bytes.fromhex(body.confirmation_hash), identity.auth_epoch, identity.oidc_auth_time,
            ))
            response = publish_grant(row, identity, user["id"], rp_id)
            _check_binding(response, body)
            if response["grant_id"] != body.grant_id or response["confirmation_hash"] != body.confirmation_hash:
                raise _unavailable()
        return {"status": "verified", "execution_enabled": False, "proof": response}

    return router
