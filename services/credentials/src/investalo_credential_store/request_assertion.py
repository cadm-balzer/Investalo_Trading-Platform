"""Dedicated, request-bound service assertions; no token minting or HTTP intake."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import time
from urllib.parse import urlsplit
from uuid import UUID

from .models import _PrivateImmutable

TARGETS = {
    action: f"/v1/credentials/bitget/{action}"
    for action in ("register", "replace", "revoke")
}
MAX_BODY_BYTES = 4096


class OnboardingRejected(ValueError):
    """Only fixed error codes cross the service boundary."""
    CODES = frozenset(("authentication_required", "invalid_request", "access_denied",
                       "concurrent_change", "identity_conflict", "broker_rejected",
                       "unavailable", "key_unavailable", "authentication_failed",
                       "invalid_record", "crypto_failure", "invalid_context"))

    def __init__(self, code: str):
        self.code = code if code in self.CODES else "unavailable"
        super().__init__(self.code)


class ActionAssertion(_PrivateImmutable):
    __slots__ = ("subject", "issuer", "tenant_id", "auth_epoch", "nonce",
                 "auth_time", "started_at", "expires_at")

    def __init__(self, *, subject, issuer, tenant_id, auth_epoch, nonce,
                 auth_time, started_at, expires_at):
        for field, value in locals().copy().items():
            if field != "self":
                object.__setattr__(self, field, value)


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError()
        result[key] = value
    return result


def _decode(value: str) -> bytes:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError()
    decoded = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    if base64.urlsafe_b64encode(decoded).rstrip(b"=").decode("ascii") != value:
        raise ValueError()
    return decoded


def _uuid(value):
    if type(value) is not str:
        raise ValueError()
    parsed = UUID(value)
    if str(parsed) != value:
        raise ValueError()
    return parsed


class RequestVerifier(_PrivateImmutable):
    """The caller supplies a separately provisioned BFF-to-credential secret."""
    __slots__ = ("_key", "_issuer", "_clock")

    def __init__(self, *, key: bytes, oidc_issuer: str, clock=time.time):
        try:
            uri = urlsplit(oidc_issuer)
            if (type(key) is not bytes or not 32 <= len(key) <= 128
                    or type(oidc_issuer) is not str or len(oidc_issuer) > 255
                    or uri.scheme != "https" or not uri.hostname
                    or uri.username or uri.password or uri.query or uri.fragment
                    or not callable(clock)):
                raise ValueError()
        except (ValueError, TypeError, AttributeError):
            raise OnboardingRejected("invalid_context") from None
        object.__setattr__(self, "_key", key)
        object.__setattr__(self, "_issuer", oidc_issuer)
        object.__setattr__(self, "_clock", clock)

    def verify(self, token: str, *, action: str, body: bytes) -> ActionAssertion:
        try:
            if (type(token) is not str or not 1 <= len(token) <= 8192
                    or type(action) is not str or action not in TARGETS
                    or type(body) is not bytes or not 1 <= len(body) <= MAX_BODY_BYTES):
                raise ValueError()
            header64, payload64, signature64 = token.split(".")
            header = json.loads(_decode(header64), object_pairs_hook=_object)
            if header != {"alg": "HS256", "typ": "JWT"}:
                raise ValueError()
            expected = hmac.digest(self._key, f"{header64}.{payload64}".encode("ascii"), "sha256")
            if not hmac.compare_digest(expected, _decode(signature64)):
                raise ValueError()
            claims = json.loads(_decode(payload64), object_pairs_hook=_object)
            fields = {"iss", "aud", "sub", "oidc_iss", "oidc_auth_time", "oidc_amr",
                      "step_up_started_at", "tenant_id", "auth_epoch", "jti",
                      "iat", "exp", "htm", "htu", "body_sha256"}
            if type(claims) is not dict or set(claims) != fields:
                raise ValueError()
            for field in ("iat", "exp", "oidc_auth_time", "step_up_started_at", "auth_epoch"):
                if type(claims[field]) is not int or not 0 <= claims[field] < 2**63:
                    raise ValueError()
            current = int(self._clock())
            amr = claims["oidc_amr"]
            if (claims["iss"] != "investalo-bff" or claims["aud"] != "investalo-credentials"
                    or claims["oidc_iss"] != self._issuer
                    or type(claims["sub"]) is not str or not 1 <= len(claims["sub"]) <= 255
                    or any(ord(c) < 32 or ord(c) == 127 for c in claims["sub"])
                    or type(amr) is not list or not 1 <= len(amr) <= 8
                    or any(type(item) is not str or not re.fullmatch(r"[a-z0-9_-]{1,32}", item) for item in amr)
                    or len(set(amr)) != len(amr) or "mfa" not in amr
                    or not current - 60 <= claims["iat"] <= current + 5
                    or not current < claims["exp"] <= min(current + 60, claims["iat"] + 60)
                    or not current - 300 <= claims["step_up_started_at"] <= claims["oidc_auth_time"]
                    or not current - 120 <= claims["oidc_auth_time"] <= min(current + 5, claims["iat"] + 5)
                    or claims["htm"] != "POST" or claims["htu"] != TARGETS[action]
                    or claims["body_sha256"] != hashlib.sha256(body).hexdigest()):
                raise ValueError()
            return ActionAssertion(
                subject=claims["sub"], issuer=claims["oidc_iss"],
                tenant_id=_uuid(claims["tenant_id"]), auth_epoch=claims["auth_epoch"],
                nonce=_uuid(claims["jti"]), auth_time=claims["oidc_auth_time"],
                started_at=claims["step_up_started_at"], expires_at=claims["exp"],
            )
        except Exception:
            raise OnboardingRejected("authentication_required") from None
