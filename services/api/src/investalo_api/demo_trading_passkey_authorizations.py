"""Default-off trusted-BFF Demo Trading API; digests only, no key intake.

Only own019 entry functions issue Trading authority. Passive wire codecs and
the original006 factor publisher are shared; Normal and Demo Read routes retain
their original metadata and authorization domains.
"""
from time import time
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import Field

from .database import transaction
from .passkey_action_proofs import (
    ATTEMPT_COLUMNS, GRANT_COLUMNS, AttemptRequest, FinishRequest, GrantRequest,
    Identity, Target as NormalTarget, _check_binding, _hex_bytes, _query, _unavailable,
)
from .passkey_credential_authorizations import (
    AuthorizeRequest, METADATA_DIGEST, PREPARE_COLUMNS, RECEIPT_FIELDS,
    _digest, _live_assertion, _purpose_configuration,
)
from .passkeys import (
    REGISTRY_COLUMNS, SAFE_INTEGER, _canonical_uuid, _encoded_db_bytes, _execute, _safe_int,
    decode_b64url, parse_request, publish_credential,
)
from .passkey_action_proofs import PrepareRequest as ProofPrepareRequest
from .settings import Settings


class Target(NormalTarget):
    action: Literal["register", "revoke"]
    # Demo keys remain revision1. Only storage may advance through KEK rewrap.
    expected_revision: int | None = Field(default=None, ge=1, le=1)


class PrepareRequest(ProofPrepareRequest):
    target: Target
    body_sha256: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$", repr=False)


# Public wire contract mirrors immutable018 and the native trading policy.
# The API publishes declared rights; it does not certify native key provenance.
_REQUIRED_AUTHORITIES = frozenset(("coow", "cpow", "stow"))
_ALLOWED_AUTHORITIES = _REQUIRED_AUTHORITIES | frozenset((
    "stor", "coor", "cpor", "smor", "ttor", "wtor", "taxr", "chor", "p2pr",
))


def _authorities(value, connection):
    if connection is None:
        if value is not None:
            raise ValueError()
        return None
    if (type(value) is not list or not 3 <= len(value) <= len(_ALLOWED_AUTHORITIES)
            or any(type(item) is not str or item not in _ALLOWED_AUTHORITIES for item in value)
            or not _REQUIRED_AUTHORITIES <= set(value) or len(set(value)) != len(value)
            or value != sorted(value)):
        raise ValueError()
    return list(value)


def _metadata(value, identity):
    """Exact own019 public snapshot, excluding UID, provenance and ciphertext."""
    try:
        if type(value) is not dict or set(value) != {
            "tenant_id", "auth_epoch", "purpose", "profile", "environment", "account", "connection", "key_authorities",
        }:
            raise ValueError()
        if (
            value["purpose"] != "demo_futures_spot_trading"
            or value["profile"] != "bitget-classic-demo-trading-secret/1"
            or value["environment"] != "demo"
            or UUID(_canonical_uuid(value["tenant_id"])) != identity.tenant_id
            or not _safe_int(value["auth_epoch"]) or value["auth_epoch"] != identity.auth_epoch
        ):
            raise ValueError()
        account, connection = value["account"], value["connection"]
        if type(account) is not dict or set(account) != {"id", "name", "broker", "mode", "currency", "status"}:
            raise ValueError()
        _canonical_uuid(account["id"])
        if (
            not isinstance(account["name"], str) or not 1 <= len(account["name"]) <= 120
            or any(ord(c) < 32 or ord(c) == 127 for c in account["name"])
            or account["broker"] != "bitget" or account["mode"] != "bitget_demo"
            or account["currency"] != "USDT" or account["status"] not in ("disconnected", "ready", "paused")
        ):
            raise ValueError()
        if connection is not None:
            if type(connection) is not dict or set(connection) != {
                "connection_id", "credential_revision", "storage_version", "status",
            }:
                raise ValueError()
            _canonical_uuid(connection["connection_id"])
            if (
                not _safe_int(connection["credential_revision"], minimum=1, maximum=1)
                or not _safe_int(connection["storage_version"], minimum=1)
                or connection["status"] not in ("active", "revoked")
            ):
                raise ValueError()
        rights = _authorities(value["key_authorities"], connection)
        return {**value, "key_authorities": rights, "account": dict(account),
                "connection": dict(connection) if connection is not None else None}
    except (ValueError, TypeError, AttributeError, KeyError):
        raise _unavailable() from None


def _target(value, metadata):
    try:
        target = Target.model_validate(value)
        if target.platform_account_id != metadata["account"]["id"]:
            raise ValueError()
        connection = metadata["connection"]
        if target.action == "register":
            if connection is not None or metadata["account"]["status"] != "ready":
                raise ValueError()
        elif (
            connection is None or connection["status"] != "active"
            or target.connection_id != connection["connection_id"]
            or target.expected_revision != connection["credential_revision"]
            or target.expected_storage != connection["storage_version"]
        ):
            raise ValueError()
        return target.model_dump(exclude_unset=True)
    except (ValueError, TypeError, AttributeError, KeyError):
        raise _unavailable() from None


def _owner(row, identity, user_id, rp_id, columns):
    if (
        type(row) is not dict or set(row) != set(columns)
        or not isinstance(row["attempt_id"], UUID)
        or not isinstance(row["tenant_id"], UUID) or row["tenant_id"] != identity.tenant_id
        or not isinstance(row["user_id"], UUID) or row["user_id"] != user_id
        or row["rp_id"] != rp_id or not _safe_int(row["auth_epoch"]) or row["auth_epoch"] != identity.auth_epoch
        or not _safe_int(row["session_expires_at"], minimum=1)
        or not _safe_int(row["expires_at"], minimum=1)
        or row["expires_at"] > row["session_expires_at"] or row["expires_at"] <= int(time())
    ):
        raise _unavailable()
    metadata = _metadata(row["metadata"], identity)
    _live_assertion(identity)
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
        or row["expires_at"] <= row["prepared_at"] or row["expires_at"] > row["prepared_at"] + 120
        or not _safe_int(row["passkey_storage"], minimum=1, maximum=SAFE_INTEGER - 1)
        or not _safe_int(row["enrollment_epoch"]) or row["enrollment_epoch"] != identity.auth_epoch
    ):
        raise _unavailable()
    key = {field: row[field] for field in REGISTRY_COLUMNS if field in row}
    key.update(storage_version=row["passkey_storage"], status="active")
    credential = publish_credential(key, tenant_id=identity.tenant_id, user_id=user_id, rp_id=rp_id)
    return {**result, "credential": credential, "challenge": _encoded_db_bytes(row["challenge"], 32, 32),
            "prepared_at": row["prepared_at"]}


def publish_grant(row, identity, user_id, rp_id):
    result = _owner(row, identity, user_id, rp_id, GRANT_COLUMNS)
    if (
        not isinstance(row["grant_id"], UUID) or not isinstance(row["passkey_id"], UUID)
        or row["grant_id"] == row["attempt_id"]
        or not _safe_int(row["passkey_version"], minimum=2)
        or not _safe_int(row["checked_at"], minimum=1) or row["checked_at"] > int(time())
        or row["expires_at"] <= row["checked_at"] or row["expires_at"] > row["checked_at"] + 120
    ):
        raise _unavailable()
    return {**result, "grant_id": str(row["grant_id"]), "passkey_id": str(row["passkey_id"]),
            "passkey_version": row["passkey_version"], "checked_at": row["checked_at"]}


def publish_preparation(row, identity, user_id, rp_id, request):
    if (
        type(row) is not dict or set(row) != set(PREPARE_COLUMNS)
        or not isinstance(row["authorization_id"], UUID) or row["authorization_id"] == row["attempt_id"]
        or not _digest(row["metadata_sha256"])
    ):
        raise _unavailable()
    attempt = publish_attempt({field: row[field] for field in ATTEMPT_COLUMNS}, identity, user_id, rp_id)
    _check_binding(attempt, request)
    if attempt["target"] != request.target.model_dump(exclude_unset=True):
        raise HTTPException(409, "Concurrent change")
    if (
        attempt["challenge"] != request.challenge or attempt["confirmation_hash"] != request.confirmation_hash
        or attempt["session_expires_at"] != request.session_expires_at
    ):
        raise _unavailable()
    return {"authorization_id": str(row["authorization_id"]),
            "metadata_sha256": row["metadata_sha256"], "attempt": attempt}


def publish_authorization(receipt, identity, user_id, rp_id, origin, request, grant, metadata_sha256):
    try:
        if type(receipt) is not dict or set(receipt) != RECEIPT_FIELDS:
            raise ValueError()
        for field in ("authorization_id", "proof_id", "grant_id", "tenant_id", "user_id", "passkey_id"):
            _canonical_uuid(receipt[field])
        if len({receipt["authorization_id"], receipt["proof_id"], receipt["grant_id"]}) != 3:
            raise ValueError()
        expected = {
            "kind": "passkey-demo-trading-credential-authorization/1",
            "authorization_id": request.authorization_id, "grant_id": request.grant_id,
            "proof_id": grant["attempt_id"], "tenant_id": str(identity.tenant_id), "user_id": str(user_id),
            "subject": identity.subject, "auth_epoch": identity.auth_epoch,
            "oidc_issuer": identity.oidc_issuer, "oidc_auth_time": identity.oidc_auth_time,
            "rp_id": rp_id, "origin": origin, "session_binding": request.session_binding,
            "session_expires_at": grant["session_expires_at"], "passkey_id": grant["passkey_id"],
            "passkey_version": grant["passkey_version"], "target": grant["target"],
            "checked_at": grant["checked_at"], "expires_at": grant["expires_at"],
            "metadata_sha256": metadata_sha256,
        }
        if any(receipt[field] != value for field, value in expected.items()):
            raise ValueError()
        for field in ("auth_epoch", "oidc_auth_time", "session_expires_at", "passkey_version",
                      "prepared_at", "checked_at", "authorized_at", "expires_at"):
            if not _safe_int(receipt[field], minimum=0 if field == "auth_epoch" else 1):
                raise ValueError()
        if receipt["passkey_version"] < 2 or not _digest(metadata_sha256) or not _digest(receipt["body_sha256"]):
            raise ValueError()
        now = int(time())
        if not (
            receipt["oidc_auth_time"] <= now + 5
            and now - 300 <= receipt["prepared_at"] <= receipt["checked_at"]
            and now - 120 <= receipt["checked_at"] <= receipt["authorized_at"] <= now
            and receipt["authorized_at"] < receipt["expires_at"]
            and now < receipt["expires_at"] <= min(receipt["checked_at"] + 120, receipt["session_expires_at"])
        ):
            raise ValueError()
        if type(receipt["target"]) is not dict:
            raise ValueError()
        Target.model_validate(receipt["target"])
    except (ValueError, TypeError, AttributeError, KeyError):
        raise _unavailable() from None
    _live_assertion(identity)
    return {"status": "authorized", "execution_enabled": False, "authorization": receipt}


def _after_commit(identity, expires_at):
    _live_assertion(identity)
    if expires_at <= int(time()):
        raise _unavailable()


def create_demo_trading_passkey_authorization_router(settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/v1/bitget-demo-trading/passkey-authorizations")
    # Independent opt-in; Normal/Read flags never expose this route family.
    if settings.demo_trading_passkey_authorizations is not True:
        return router

    @router.post("/prepare")
    async def prepare(request: Request, identity: Identity):
        body = parse_request(await request.body(), PrepareRequest)
        rp_id, origin = _purpose_configuration(settings, identity)
        with transaction(settings, identity) as (db, user):
            row = _query(db, "demo_trading_passkey_credential_prepare", PREPARE_COLUMNS, (
                UUID(body.target.platform_account_id), body.target.action,
                UUID(body.target.connection_id) if body.target.action == "register" else None,
                rp_id, origin, decode_b64url(body.challenge, 32, 32),
                bytes.fromhex(body.session_binding), bytes.fromhex(body.confirmation_hash),
                body.body_sha256, body.session_expires_at, identity.auth_epoch, identity.oidc_auth_time,
            ))
            response = publish_preparation(row, identity, user["id"], rp_id, body)
        _after_commit(identity, response["attempt"]["expires_at"])
        return response

    @router.post("/claim")
    async def claim(request: Request, identity: Identity):
        body = parse_request(await request.body(), AttemptRequest)
        rp_id, _ = _purpose_configuration(settings, identity)
        with transaction(settings, identity) as (db, user):
            row = _query(db, "demo_trading_passkey_action_claim", ATTEMPT_COLUMNS, (
                UUID(body.attempt_id), rp_id, bytes.fromhex(body.session_binding),
                identity.auth_epoch, identity.oidc_auth_time,
            ))
            response = publish_attempt(row, identity, user["id"], rp_id)
            _check_binding(response, body)
            if response["attempt_id"] != body.attempt_id:
                raise _unavailable()
        # Claim must commit before the BFF accepts/verifies a WebAuthn verdict.
        _after_commit(identity, response["expires_at"])
        return response

    @router.post("/finish")
    async def finish(request: Request, identity: Identity):
        body = parse_request(await request.body(), FinishRequest)
        rp_id, _ = _purpose_configuration(settings, identity)
        with transaction(settings, identity) as (db, user):
            row = _query(db, "demo_trading_passkey_action_finish", GRANT_COLUMNS, (
                UUID(body.attempt_id), rp_id, bytes.fromhex(body.session_binding),
                body.new_counter, body.backup_eligible, body.backed_up, body.checked_at,
                identity.auth_epoch, identity.oidc_auth_time,
            ))
            response = publish_grant(row, identity, user["id"], rp_id)
            _check_binding(response, body)
            if response["attempt_id"] != body.attempt_id or response["checked_at"] != body.checked_at:
                raise _unavailable()
        _after_commit(identity, response["expires_at"])
        return response

    @router.post("/grant")
    async def grant(request: Request, identity: Identity):
        body = parse_request(await request.body(), GrantRequest)
        rp_id, _ = _purpose_configuration(settings, identity)
        with transaction(settings, identity) as (db, user):
            row = _query(db, "demo_trading_passkey_action_read_grant", GRANT_COLUMNS, (
                UUID(body.grant_id), rp_id, bytes.fromhex(body.session_binding),
                identity.auth_epoch, identity.oidc_auth_time,
            ))
            response = publish_grant(row, identity, user["id"], rp_id)
            _check_binding(response, body)
            if response["grant_id"] != body.grant_id:
                raise _unavailable()
        _after_commit(identity, response["expires_at"])
        return response

    @router.post("/authorize")
    async def authorize(request: Request, identity: Identity):
        body = parse_request(await request.body(), AuthorizeRequest)
        rp_id, origin = _purpose_configuration(settings, identity)
        with transaction(settings, identity) as (db, user):
            row = _query(db, "demo_trading_passkey_action_read_grant", (*GRANT_COLUMNS, METADATA_DIGEST), (
                UUID(body.grant_id), rp_id, bytes.fromhex(body.session_binding),
                identity.auth_epoch, identity.oidc_auth_time,
            ))
            if type(row) is not dict or set(row) != {*GRANT_COLUMNS, "metadata_sha256"}:
                raise _unavailable()
            metadata_sha256 = row["metadata_sha256"]
            grant = publish_grant({field: row[field] for field in GRANT_COLUMNS}, identity, user["id"], rp_id)
            _check_binding(grant, body)
            if grant["grant_id"] != body.grant_id or grant["confirmation_hash"] != body.confirmation_hash:
                raise HTTPException(403, "Access denied")
            result = _execute(db,
                "SELECT platform.demo_trading_passkey_credential_authorize(%s,%s,%s,%s,%s,%s,%s,%s) AS receipt",
                (UUID(body.authorization_id), UUID(body.grant_id), rp_id, origin,
                 bytes.fromhex(body.session_binding), bytes.fromhex(body.confirmation_hash),
                 identity.auth_epoch, identity.oidc_auth_time),
            ).fetchone()
            if type(result) is not dict or set(result) != {"receipt"}:
                raise _unavailable()
            response = publish_authorization(result["receipt"], identity, user["id"], rp_id, origin,
                                             body, grant, metadata_sha256)
        _after_commit(identity, response["authorization"]["expires_at"])
        return response

    return router
