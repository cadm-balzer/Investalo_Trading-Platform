"""Isolated passkey receipt assertions, with no transport or execution authority.

Verification is repeatable authentication of the dedicated BFF assertion, not
receipt consumption or WebAuthn verification. Execution still requires a
purpose-specific durable authorization receipt and authoritative database
checks; no such consumer is supplied here.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import json
import re
import unicodedata
from types import MappingProxyType
from urllib.parse import urlsplit
from uuid import UUID

from .models import _PrivateImmutable
from .request_assertion import OnboardingRejected

MAX_SAFE_INTEGER = 9007199254740991
MAX_BODY_BYTES = 4096
TARGETS = MappingProxyType({
    action: f"/v1/credentials/bitget/{action}"
    for action in ("register", "replace", "revoke")
})
AUTHORIZATION_KIND = "passkey-credential-authorization/1"
AUDIENCE = "investalo-credentials-passkey"
_FIELDS = frozenset((
    "iss", "aud", "sub", "authorization_kind", "authorization_id", "proof_id",
    "grant_id", "tenant_id", "user_id", "auth_epoch", "oidc_iss",
    "oidc_auth_time", "rp_id", "origin", "session_binding", "session_expires_at",
    "passkey_id", "passkey_version", "passkey_started_at", "passkey_checked_at",
    "passkey_authorized_at", "authorization_expires_at", "metadata_sha256",
    "target", "iat", "exp", "jti", "htm", "htu", "body_sha256",
))
_UUID_FIELDS = (
    "authorization_id", "proof_id", "grant_id", "tenant_id", "user_id",
    "passkey_id", "jti",
)
_TIME_FIELDS = (
    "oidc_auth_time", "session_expires_at", "passkey_started_at",
    "passkey_checked_at", "passkey_authorized_at", "authorization_expires_at",
    "iat", "exp",
)


def _integer(value, minimum=1):
    if type(value) is not int or not minimum <= value <= MAX_SAFE_INTEGER:
        raise ValueError()
    return value


def _text(value, maximum):
    if (type(value) is not str or not value
            or any(unicodedata.category(char) in ("Cc", "Cf", "Cs") for char in value)
            or len(value.encode("utf-8")) > maximum):
        raise ValueError()
    return value


def _digest(value):
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError()
    return value


def _uuid(value):
    if type(value) is not str:
        raise ValueError()
    parsed = UUID(value)
    if str(parsed) != value:
        raise ValueError()
    return parsed


def _origin(value):
    """Only canonical HTTPS origins on ASCII dotted DNS names are accepted."""
    if type(value) is not str or len(value) > 255 or not value.isascii():
        raise ValueError()
    uri = urlsplit(value)
    host = uri.hostname
    if (uri.scheme != "https" or not host or host != host.lower()
            or uri.username is not None or uri.password is not None
            or uri.path or uri.query or uri.fragment or "." not in host
            or len(host) > 253):
        raise ValueError()
    labels = host.split(".")
    if (any(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) is None
            for label in labels) or labels[-1].isdigit()):
        raise ValueError()
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError()
    port = uri.port
    if port is not None and (not 1 <= port <= 65535 or port == 443):
        raise ValueError()
    canonical = "https://" + host + (f":{port}" if port is not None else "")
    if value != canonical:
        raise ValueError()
    return host


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError()
        result[key] = value
    return result


def _constant(_):
    raise ValueError()


def _json(raw):
    return json.loads(raw.decode("utf-8", errors="strict"),
                      object_pairs_hook=_object, parse_constant=_constant)


def _decode(value):
    if type(value) is not str or re.fullmatch(r"[A-Za-z0-9_-]+", value) is None:
        raise ValueError()
    decoded = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    if base64.urlsafe_b64encode(decoded).rstrip(b"=").decode("ascii") != value:
        raise ValueError()
    return decoded


def _target(value, action):
    fields = {"action", "platform_account_id", "connection_id"}
    if action != "register":
        fields |= {"expected_revision", "expected_storage"}
    if type(value) is not dict or set(value) != fields or value["action"] != action:
        raise ValueError()
    _uuid(value["platform_account_id"])
    _uuid(value["connection_id"])
    if action != "register":
        revision = _integer(value["expected_revision"])
        storage = _integer(value["expected_storage"])
        if storage == MAX_SAFE_INTEGER or (action == "replace" and revision == MAX_SAFE_INTEGER):
            raise ValueError()
    return MappingProxyType(dict(value))


def _body(raw, target):
    """Compare parsed fields without normalizing the signed raw body bytes."""
    body = _json(raw)
    fields = set(target) - {"action"}
    if target["action"] != "revoke":
        fields.add("credentials")
    if type(body) is not dict or set(body) != fields:
        raise ValueError()
    for field in set(target) - {"action"}:
        # JSON equality must not conflate 1, 1.0 and true.
        if type(body[field]) is not type(target[field]) or body[field] != target[field]:
            raise ValueError()
    if target["action"] != "revoke":
        triple = body["credentials"]
        if type(triple) is not dict or set(triple) != {"api_key", "secret", "passphrase"}:
            raise ValueError()
        for field, maximum in (("api_key", 256), ("secret", 1024), ("passphrase", 256)):
            _text(triple[field], maximum)


class PasskeyRequestContext(_PrivateImmutable):
    """Required trusted session/actor context; token claims cannot supply it."""
    __slots__ = ("tenant_id", "user_id", "subject", "auth_epoch", "oidc_auth_time",
                 "session_binding", "session_expires_at")

    def __init__(self, *, tenant_id: UUID, user_id: UUID, subject: str,
                 auth_epoch: int, oidc_auth_time: int, session_binding: str,
                 session_expires_at: int):
        try:
            if type(tenant_id) is not UUID or type(user_id) is not UUID:
                raise ValueError()
            _text(subject, 255)
            _integer(auth_epoch, 0)
            _integer(oidc_auth_time)
            _digest(session_binding)
            _integer(session_expires_at)
        except Exception:
            raise OnboardingRejected("invalid_context") from None
        for field in self.__slots__:
            object.__setattr__(self, field, locals()[field])


class PasskeyActionAssertion(_PrivateImmutable):
    """Private immutable claim projection; excludes plaintext broker input."""
    __slots__ = tuple(sorted(_FIELDS))

    def __init__(self, **claims):
        for field in self.__slots__:
            object.__setattr__(self, field, claims[field])


class PasskeyRequestVerifier(_PrivateImmutable):
    """Dedicated passkey audience/key; deliberately unrelated to RequestVerifier."""
    __slots__ = ("_key", "_issuer", "_origin", "_rp_id", "_clock")

    def __init__(self, *, key: bytes, oidc_issuer: str, origin: str, clock):
        try:
            if type(key) is not bytes or not 32 <= len(key) <= 128 or not callable(clock):
                raise ValueError()
            _origin(oidc_issuer)
            rp_id = _origin(origin)
        except Exception:
            raise OnboardingRejected("invalid_context") from None
        for field, value in (("_key", key), ("_issuer", oidc_issuer),
                             ("_origin", origin), ("_rp_id", rp_id), ("_clock", clock)):
            object.__setattr__(self, field, value)

    def verify(self, token: str, *, action: str, body: bytes,
               context: PasskeyRequestContext) -> PasskeyActionAssertion:
        """Authenticate repeatedly; never claim, consume, or execute a receipt."""
        try:
            if (type(token) is not str or not 1 <= len(token) <= 8192
                    or type(action) is not str or action not in TARGETS
                    or type(body) is not bytes or not 1 <= len(body) <= MAX_BODY_BYTES
                    or type(context) is not PasskeyRequestContext):
                raise ValueError()
            header64, payload64, signature64 = token.split(".")
            if _json(_decode(header64)) != {"alg": "HS256", "typ": "JWT"}:
                raise ValueError()
            expected = hmac.digest(self._key, f"{header64}.{payload64}".encode("ascii"), "sha256")
            if not hmac.compare_digest(expected, _decode(signature64)):
                raise ValueError()
            claims = _json(_decode(payload64))
            if type(claims) is not dict or set(claims) != _FIELDS:
                raise ValueError()
            claims = dict(claims)
            for field in _UUID_FIELDS:
                claims[field] = _uuid(claims[field])
            if len({claims[field] for field in ("authorization_id", "proof_id", "grant_id")}) != 3:
                raise ValueError()
            for field in _TIME_FIELDS:
                _integer(claims[field])
            _integer(claims["auth_epoch"], 0)
            _integer(claims["passkey_version"], 2)
            _text(claims["sub"], 255)
            for field in ("session_binding", "metadata_sha256", "body_sha256"):
                _digest(claims[field])
            if (claims["iss"] != "investalo-bff" or claims["aud"] != AUDIENCE
                    or claims["authorization_kind"] != AUTHORIZATION_KIND
                    or claims["oidc_iss"] != self._issuer or claims["origin"] != self._origin
                    or claims["rp_id"] != self._rp_id
                    or claims["htm"] != "POST" or claims["htu"] != TARGETS[action]
                    or claims["body_sha256"] != hashlib.sha256(body).hexdigest()):
                raise ValueError()
            for field in ("tenant_id", "user_id", "auth_epoch", "oidc_auth_time",
                          "session_binding", "session_expires_at"):
                if claims[field] != getattr(context, field):
                    raise ValueError()
            if claims["sub"] != context.subject:
                raise ValueError()
            current = _integer(self._clock())
            if current > MAX_SAFE_INTEGER - 300:
                raise ValueError()
            started, checked, authorized = (
                claims["passkey_started_at"], claims["passkey_checked_at"],
                claims["passkey_authorized_at"],
            )
            issued, expiry = claims["iat"], claims["exp"]
            authorization_expiry = claims["authorization_expires_at"]
            if (claims["oidc_auth_time"] > current + 5
                    or started < current - 300 or not started <= checked <= authorized <= issued
                    or not current - 120 <= checked <= current or authorized > current
                    or not current - 60 <= issued <= current + 5
                    or not current < expiry <= min(issued + 60, authorization_expiry)
                    or not authorized < authorization_expiry <= min(checked + 120, context.session_expires_at)
                    or context.session_expires_at <= current):
                raise ValueError()
            claims["target"] = _target(claims["target"], action)
            _body(body, claims["target"])
            return PasskeyActionAssertion(**claims)
        except Exception:
            raise OnboardingRejected("authentication_required") from None
