"""Verify short-lived, request-bound assertions from the server-side BFF."""
from dataclasses import dataclass
import base64
import hashlib
import hmac
import json
import re
import time
from uuid import UUID

from fastapi import HTTPException, Request

from .settings import Settings


@dataclass(frozen=True)
class Assertion:
    subject: str
    oidc_issuer: str
    oidc_auth_time: int
    nonce: UUID
    expires_at: int
    tenant_id: UUID | None
    auth_epoch: int | None


def _reject() -> HTTPException:
    return HTTPException(401, "Authentication required")


def _decode(value: str) -> bytes:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError("Invalid encoding")
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate claim")
        result[key] = value
    return result


def verify(
    token: str, *, settings: Settings, method: str, target: str, body: bytes,
    now: int | None = None,
) -> Assertion:
    if not settings.internal_key or not settings.oidc_issuer:
        raise _reject()
    try:
        header64, payload64, signature64 = token.split(".")
        header = json.loads(_decode(header64), object_pairs_hook=_object)
        if header != {"alg": "HS256", "typ": "JWT"}:
            raise ValueError("Unsupported token header")
        expected = hmac.digest(
            settings.internal_key.encode("utf-8"),
            f"{header64}.{payload64}".encode("ascii"), "sha256",
        )
        if not hmac.compare_digest(expected, _decode(signature64)):
            raise ValueError("Invalid signature")
        claims = json.loads(_decode(payload64), object_pairs_hook=_object)
        if not isinstance(claims, dict):
            raise ValueError("Invalid claims object")
        current = int(time.time()) if now is None else now
        for key in ("iat", "exp", "oidc_auth_time"):
            if type(claims.get(key)) is not int:
                raise ValueError("Invalid timestamp")
        if (
            claims.get("iss") != "investalo-bff"
            or claims.get("aud") != "investalo-api"
            or claims.get("oidc_iss") != settings.oidc_issuer
            or not isinstance(claims.get("sub"), str)
            or not 1 <= len(claims["sub"]) <= 255
            or not current - 60 <= claims["iat"] <= current + 5
            or not current < claims["exp"] <= claims["iat"] + 60
            or not 0 <= claims["oidc_auth_time"] <= current + 5
            or claims.get("htm") != method.upper()
            or claims.get("htu") != target
            or claims.get("body_sha256") != hashlib.sha256(body).hexdigest()
        ):
            raise ValueError("Invalid claims")
        tenant_claim = claims.get("tenant_id")
        if tenant_claim is not None and not isinstance(tenant_claim, str):
            raise ValueError("Invalid tenant")
        if not isinstance(claims.get("jti"), str):
            raise ValueError("Invalid nonce")
        tenant = UUID(tenant_claim) if tenant_claim is not None else None
        epoch = claims.get("auth_epoch")
        if epoch is not None and (type(epoch) is not int or epoch < 0):
            raise ValueError("Invalid generation")
        if tenant is not None and epoch is None:
            raise ValueError("Missing generation")
        return Assertion(
            subject=claims["sub"], oidc_issuer=claims["oidc_iss"],
            oidc_auth_time=claims["oidc_auth_time"], nonce=UUID(claims["jti"]),
            expires_at=claims["exp"], tenant_id=tenant, auth_epoch=epoch,
        )
    except (ValueError, KeyError, TypeError, UnicodeError, json.JSONDecodeError):
        raise _reject() from None


async def authenticate(request: Request) -> Assertion:
    authorization = request.headers.get("authorization", "")
    if not authorization.startswith("Bearer ") or len(authorization) > 8192:
        raise _reject()
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 16384:
            raise HTTPException(413, "Request too large")
    # FastAPI's body parser can still read the signed original bytes.
    request._body = bytes(body)
    try:
        target = request.scope.get("raw_path", request.url.path.encode()).decode("ascii")
        if request.scope["query_string"]:
            target += "?" + request.scope["query_string"].decode("ascii")
    except UnicodeError:
        raise _reject() from None
    return verify(
        authorization[7:], settings=request.app.state.settings,
        method=request.method, target=target, body=bytes(body),
    )
