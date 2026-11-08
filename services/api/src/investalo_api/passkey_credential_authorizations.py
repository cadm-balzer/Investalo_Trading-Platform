"""Gated trusted-BFF purpose preparation and explicit credential consent.

Only body digests cross this boundary. Original OIDC claims are preserved, and
neither a proof-only confirmation nor this receipt executes a credential write.
"""
import re
from time import time
import unicodedata
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import Field, field_validator

from .database import transaction
from .passkey_action_proofs import (
    ATTEMPT_COLUMNS, GRANT_COLUMNS, ConfirmRequest, Identity, Target,
    PrepareRequest as ProofPrepareRequest, _check_binding, _query, _unavailable,
    publish_attempt, publish_grant,
)
from .passkeys import (
    _canonical_uuid, _configuration, _execute, _safe_int, decode_b64url, parse_request,
    valid_rp,
)
from .settings import Settings


class PrepareRequest(ProofPrepareRequest):
    body_sha256: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$", repr=False)


class AuthorizeRequest(ConfirmRequest):
    authorization_id: str

    @field_validator("authorization_id")
    @classmethod
    def canonical_authorization(cls, value):
        return _canonical_uuid(value)


PREPARE_COLUMNS = ("authorization_id", *ATTEMPT_COLUMNS, "metadata_sha256")
RECEIPT_FIELDS = frozenset((
    "kind", "authorization_id", "proof_id", "grant_id", "tenant_id", "user_id",
    "subject", "auth_epoch", "oidc_issuer", "oidc_auth_time", "rp_id", "origin",
    "session_binding", "session_expires_at", "passkey_id", "passkey_version", "target",
    "prepared_at", "checked_at", "authorized_at", "expires_at", "metadata_sha256", "body_sha256",
))
METADATA_DIGEST = "encode(sha256(convert_to(metadata::text,'UTF8')),'hex') AS metadata_sha256"


def _digest(value):
    return isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value) is not None


def _origin(value, rp_id=None):
    """Same canonical HTTPS DNS origin grammar as008 and the IP-038 contract."""
    if not isinstance(value, str) or len(value) > 255:
        return False
    match = re.fullmatch(r"https://([a-z0-9.-]+)(?::([1-9][0-9]{0,4}))?", value)
    if match is None:
        return False
    host, port = match.groups()
    try:
        valid_rp(host)
    except ValueError:
        return False
    return (
        "." in host and not host.rsplit(".", 1)[-1].isdigit()
        and (rp_id is None or host == rp_id)
        and (port is None or int(port) <= 65535 and int(port) != 443)
    )


def _purpose_configuration(settings, identity):
    rp_id = _configuration(settings, identity)
    origin = settings.passkey_origin
    if not _origin(origin, rp_id) or not _origin(identity.oidc_issuer):
        raise _unavailable()
    try:
        valid_subject = (
            isinstance(identity.subject, str) and 1 <= len(identity.subject.encode("utf-8")) <= 255
            and not any(unicodedata.category(char) in ("Cc", "Cf", "Cs") for char in identity.subject)
        )
    except UnicodeError:
        valid_subject = False
    if not valid_subject or not _safe_int(identity.oidc_auth_time, minimum=1):
        raise HTTPException(403, "Access denied")
    return rp_id, origin


def _live_assertion(identity):
    # SQL can wait on actor/account/factor locks. The authenticated transport
    # assertion must still be live when a durable result is accepted.
    if not _safe_int(identity.expires_at, minimum=1) or identity.expires_at <= int(time()):
        raise HTTPException(401, "Authentication required")


def publish_preparation(row, identity, user_id, rp_id, request):
    if (
        not isinstance(row, dict) or set(row) != set(PREPARE_COLUMNS)
        or not isinstance(row["authorization_id"], UUID)
        or row["authorization_id"] == row["attempt_id"]
        or not _digest(row["metadata_sha256"])
    ):
        raise _unavailable()
    attempt = publish_attempt({field: row[field] for field in ATTEMPT_COLUMNS}, identity, user_id, rp_id)
    _check_binding(attempt, request)
    if attempt["target"] != request.target.model_dump(exclude_unset=True):
        raise HTTPException(409, "Concurrent change")
    if (
        attempt["challenge"] != request.challenge
        or attempt["confirmation_hash"] != request.confirmation_hash
        or attempt["session_expires_at"] != request.session_expires_at
    ):
        raise _unavailable()
    _live_assertion(identity)
    return {"authorization_id": str(row["authorization_id"]),
            "metadata_sha256": row["metadata_sha256"], "attempt": attempt}


def publish_authorization(receipt, identity, user_id, rp_id, origin, request, grant, metadata_sha256):
    """Accept only the exact durable receipt matching the still-locked grant."""
    try:
        if not isinstance(receipt, dict) or set(receipt) != RECEIPT_FIELDS:
            raise ValueError()
        for field in ("authorization_id", "proof_id", "grant_id", "tenant_id", "user_id", "passkey_id"):
            _canonical_uuid(receipt[field])
        if len({receipt["authorization_id"], receipt["proof_id"], receipt["grant_id"]}) != 3:
            raise ValueError()
        expected = {
            "kind": "passkey-credential-authorization/1",
            "authorization_id": request.authorization_id, "grant_id": request.grant_id,
            "proof_id": grant["attempt_id"], "tenant_id": str(identity.tenant_id),
            "user_id": str(user_id), "subject": identity.subject, "auth_epoch": identity.auth_epoch,
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
        # Python's True == 1 must not make a malformed target/version pass.
        if type(receipt["target"]) is not dict:
            raise ValueError()
        Target.model_validate(receipt["target"])
    except (ValueError, TypeError, AttributeError, KeyError):
        raise _unavailable() from None
    _live_assertion(identity)
    return {"status": "authorized", "execution_enabled": False, "authorization": receipt}


def create_passkey_credential_authorization_router(settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/v1/passkey-credential-authorizations")
    # Default404 precedes authentication, parsing and all database access.
    if settings.passkey_credential_authorizations is not True:
        return router

    @router.post("/prepare")
    async def prepare(request: Request, identity: Identity):
        body = parse_request(await request.body(), PrepareRequest)
        rp_id, origin = _purpose_configuration(settings, identity)
        with transaction(settings, identity) as (db, user):
            row = _query(db, "passkey_credential_prepare", PREPARE_COLUMNS, (
                UUID(body.target.platform_account_id), body.target.action,
                UUID(body.target.connection_id) if body.target.action == "register" else None,
                rp_id, origin, decode_b64url(body.challenge, 32, 32),
                bytes.fromhex(body.session_binding), bytes.fromhex(body.confirmation_hash),
                body.body_sha256, body.session_expires_at, identity.auth_epoch, identity.oidc_auth_time,
            ))
            response = publish_preparation(row, identity, user["id"], rp_id, body)
        return response

    @router.post("/authorize")
    async def authorize(request: Request, identity: Identity):
        body = parse_request(await request.body(), AuthorizeRequest)
        rp_id, origin = _purpose_configuration(settings, identity)
        with transaction(settings, identity) as (db, user):
            # Read before confirmation:007 read-grant correctly rejects an
            # already confirmed proof. Its locks survive until this TX commits.
            row = _query(db, "passkey_action_read_grant", (*GRANT_COLUMNS, METADATA_DIGEST), (
                UUID(body.grant_id), rp_id, bytes.fromhex(body.session_binding),
                identity.auth_epoch, identity.oidc_auth_time,
            ))
            if not isinstance(row, dict) or set(row) != {*GRANT_COLUMNS, "metadata_sha256"}:
                raise _unavailable()
            metadata_sha256 = row["metadata_sha256"]
            grant = publish_grant({field: row[field] for field in GRANT_COLUMNS}, identity, user["id"], rp_id)
            _check_binding(grant, body)
            if grant["grant_id"] != body.grant_id or grant["confirmation_hash"] != body.confirmation_hash:
                raise HTTPException(403, "Access denied")
            _live_assertion(identity)
            result = _execute(db,
                "SELECT platform.passkey_credential_authorize(%s,%s,%s,%s,%s,%s,%s,%s) AS receipt",
                (UUID(body.authorization_id), UUID(body.grant_id), rp_id, origin,
                 bytes.fromhex(body.session_binding), bytes.fromhex(body.confirmation_hash),
                 identity.auth_epoch, identity.oidc_auth_time),
            ).fetchone()
            if not isinstance(result, dict) or set(result) != {"receipt"}:
                raise _unavailable()
            response = publish_authorization(result["receipt"], identity, user["id"], rp_id, origin,
                                             body, grant, metadata_sha256)
        return response

    return router
