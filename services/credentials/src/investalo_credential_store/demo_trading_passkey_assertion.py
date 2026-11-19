"""Own Demo Trading assertion domain; no conversion of read-purpose proofs."""
import hashlib
import hmac
from types import MappingProxyType

from .models import _PrivateImmutable
from .passkey_request_assertion import (
    PasskeyRequestContext, PasskeyRequestVerifier, MAX_SAFE_INTEGER, MAX_BODY_BYTES,
    _FIELDS, _UUID_FIELDS, _TIME_FIELDS, _json, _decode, _uuid, _integer, _text,
    _digest, _target, _body,
)
from .request_assertion import OnboardingRejected

TARGETS = MappingProxyType({a: f"/v1/credentials/bitget-demo-trading/{a}" for a in ("register", "revoke")})
AUTHORIZATION_KIND = "passkey-demo-trading-credential-authorization/1"
AUDIENCE = "investalo-credentials-demo-trading-passkey"


class DemoTradingPasskeyActionAssertion(_PrivateImmutable):
    __slots__ = tuple(sorted(_FIELDS))

    def __init__(self, **claims):
        for field in self.__slots__:
            object.__setattr__(self, field, claims[field])


class DemoTradingPasskeyRequestVerifier(PasskeyRequestVerifier):
    """Own key/domain/type; inherited strict trusted constructor only."""
    __slots__ = ()

    def verify(self, token: str, *, action: str, body: bytes,
               context: PasskeyRequestContext) -> DemoTradingPasskeyActionAssertion:
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
            if action == "revoke" and claims["target"]["expected_revision"] != 1:
                raise ValueError()
            _body(body, claims["target"])
            return DemoTradingPasskeyActionAssertion(**claims)
        except Exception:
            raise OnboardingRejected("authentication_required") from None
