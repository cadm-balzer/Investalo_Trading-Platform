"""Bounded, isolated AES-GCM credential envelopes. No persistence or transport."""
from __future__ import annotations

import base64
import binascii
import json
import re
import secrets
from enum import StrEnum
from types import MappingProxyType
from uuid import UUID

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

SCHEMA_VERSION = "credential-envelope/1"
MAX_PAYLOAD_BYTES = 4096
MAX_DOCUMENT_BYTES = 8192
MAX_KEY_SLOTS = 32
NONCE_BYTES = 12
KEY_BYTES = 32
TAG_BYTES = 16


class ErrorCode(StrEnum):
    INVALID_BINDING = "invalid_binding"
    INVALID_PAYLOAD = "invalid_payload"
    INVALID_KEYRING = "invalid_keyring"
    INVALID_ENVELOPE = "invalid_envelope"
    KEY_UNAVAILABLE = "key_unavailable"
    AUTHENTICATION_FAILED = "authentication_failed"
    CRYPTO_FAILURE = "crypto_failure"


class EnvelopeRejected(ValueError):
    """Safe static code: no values, backend messages or chained secret errors."""
    def __init__(self, code: ErrorCode):
        if not isinstance(code, ErrorCode):
            code = ErrorCode.INVALID_ENVELOPE
        self.code = code
        super().__init__(code.value)


class _PrivateImmutable:
    __slots__ = ()

    def __setattr__(self, name, value):
        raise AttributeError("Immutable private object")

    def __repr__(self):
        return type(self).__name__ + "(<redacted>)"

    __str__ = __repr__

    def __reduce_ex__(self, protocol):
        raise TypeError("Private object serialization denied")


def _version_id(value: object, code: ErrorCode) -> str:
    if not isinstance(value, str) or len(value) > 64 or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", value):
        raise EnvelopeRejected(code)
    return value


def _uid(value: object, *, parent: bool = False) -> str:
    if parent and value == "0":
        return "0"
    if not isinstance(value, str) or len(value) > 20 or not re.fullmatch(r"[1-9][0-9]{0,19}", value):
        raise EnvelopeRejected(ErrorCode.INVALID_BINDING)
    return value


def _canonical(value: dict) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("ascii")


class AADBinding(_PrivateImmutable):
    __slots__ = ("tenant_id", "user_id", "platform_account_id", "connection_id",
                 "broker_uid", "parent_uid", "credential_revision", "broker",
                 "account_family", "connection_mode")

    def __init__(self, *, tenant_id: UUID, user_id: UUID, platform_account_id: UUID,
                 connection_id: UUID, broker_uid: str, parent_uid: str | None,
                 credential_revision: int, broker: str = "bitget",
                 account_family: str = "classic_v2", connection_mode: str = "real_read_only"):
        identifiers = (tenant_id, user_id, platform_account_id, connection_id)
        if any(not isinstance(value, UUID) for value in identifiers):
            raise EnvelopeRejected(ErrorCode.INVALID_BINDING)
        _uid(broker_uid)
        if parent_uid is not None:
            _uid(parent_uid, parent=True)
        if (type(credential_revision) is not int or not 1 <= credential_revision <= 2**63 - 1
                or broker != "bitget" or account_family != "classic_v2"
                or connection_mode != "real_read_only"):
            raise EnvelopeRejected(ErrorCode.INVALID_BINDING)
        for name, value in (
            ("tenant_id", tenant_id), ("user_id", user_id),
            ("platform_account_id", platform_account_id), ("connection_id", connection_id),
            ("broker_uid", broker_uid), ("parent_uid", parent_uid),
            ("credential_revision", credential_revision), ("broker", broker),
            ("account_family", account_family), ("connection_mode", connection_mode),
        ):
            object.__setattr__(self, name, value)

    def _record(self) -> dict:
        return {
            "tenant_id": str(self.tenant_id), "user_id": str(self.user_id),
            "platform_account_id": str(self.platform_account_id),
            "connection_id": str(self.connection_id), "broker_uid": self.broker_uid,
            "parent_uid": self.parent_uid, "credential_revision": self.credential_revision,
            "broker": self.broker, "account_family": self.account_family,
            "connection_mode": self.connection_mode,
        }


class SecretPayload(_PrivateImmutable):
    __slots__ = ("_bytes",)

    def __init__(self, value: bytes):
        if type(value) is not bytes or not 1 <= len(value) <= MAX_PAYLOAD_BYTES:
            raise EnvelopeRejected(ErrorCode.INVALID_PAYLOAD)
        object.__setattr__(self, "_bytes", value)

    def reveal(self) -> bytes:
        """Explicit trusted-service boundary; never send to browser/logs/research."""
        return self._bytes


class KEKRing(_PrivateImmutable):
    __slots__ = ("_keys", "active_version")

    def __init__(self, entries: tuple[tuple[str, bytes], ...], *, active_version: str):
        if not isinstance(entries, tuple) or not 1 <= len(entries) <= MAX_KEY_SLOTS:
            raise EnvelopeRejected(ErrorCode.INVALID_KEYRING)
        keys = {}
        materials = set()
        for pair in entries:
            if not isinstance(pair, tuple) or len(pair) != 2:
                raise EnvelopeRejected(ErrorCode.INVALID_KEYRING)
            version, key = pair
            _version_id(version, ErrorCode.INVALID_KEYRING)
            if (version in keys or type(key) is not bytes or len(key) != KEY_BYTES
                    or key in materials):
                raise EnvelopeRejected(ErrorCode.INVALID_KEYRING)
            keys[version] = key
            materials.add(key)
        _version_id(active_version, ErrorCode.INVALID_KEYRING)
        if active_version not in keys:
            raise EnvelopeRejected(ErrorCode.INVALID_KEYRING)
        object.__setattr__(self, "_keys", MappingProxyType(keys))
        object.__setattr__(self, "active_version", active_version)

    def _key(self, version: str) -> bytes:
        if version not in self._keys:
            raise EnvelopeRejected(ErrorCode.KEY_UNAVAILABLE)
        return self._keys[version]


class Envelope(_PrivateImmutable):
    __slots__ = ("schema_version", "kek_id", "payload_nonce", "wrap_nonce", "wrapped_dek", "ciphertext")

    def __init__(self, *, kek_id: str, payload_nonce: bytes, wrap_nonce: bytes,
                 wrapped_dek: bytes, ciphertext: bytes, schema_version: str = SCHEMA_VERSION):
        if schema_version != SCHEMA_VERSION:
            raise EnvelopeRejected(ErrorCode.INVALID_ENVELOPE)
        _version_id(kek_id, ErrorCode.INVALID_ENVELOPE)
        if (type(payload_nonce) is not bytes or len(payload_nonce) != NONCE_BYTES
                or type(wrap_nonce) is not bytes or len(wrap_nonce) != NONCE_BYTES
                or type(wrapped_dek) is not bytes or len(wrapped_dek) != KEY_BYTES + TAG_BYTES
                or type(ciphertext) is not bytes or not TAG_BYTES < len(ciphertext) <= MAX_PAYLOAD_BYTES + TAG_BYTES):
            raise EnvelopeRejected(ErrorCode.INVALID_ENVELOPE)
        for name, value in (
            ("schema_version", schema_version), ("kek_id", kek_id),
            ("payload_nonce", payload_nonce), ("wrap_nonce", wrap_nonce),
            ("wrapped_dek", wrapped_dek), ("ciphertext", ciphertext),
        ):
            object.__setattr__(self, name, value)


def _aad(binding: AADBinding, *, kek_id: str | None = None) -> bytes:
    record = {"schema_version": SCHEMA_VERSION, "binding": binding._record()}
    if kek_id is None:
        record["domain"] = "investalo.credentials.payload"
    else:
        record["domain"] = "investalo.credentials.dek-wrap"
        record["kek_id"] = kek_id
    return _canonical(record)


def _arguments(binding: AADBinding, ring: KEKRing, envelope: Envelope | None = None):
    if not isinstance(binding, AADBinding):
        raise EnvelopeRejected(ErrorCode.INVALID_BINDING)
    if not isinstance(ring, KEKRing):
        raise EnvelopeRejected(ErrorCode.INVALID_KEYRING)
    if envelope is not None and not isinstance(envelope, Envelope):
        raise EnvelopeRejected(ErrorCode.INVALID_ENVELOPE)


def seal(payload: SecretPayload, binding: AADBinding, keyring: KEKRing) -> Envelope:
    _arguments(binding, keyring)
    if not isinstance(payload, SecretPayload):
        raise EnvelopeRejected(ErrorCode.INVALID_PAYLOAD)
    try:
        dek = secrets.token_bytes(KEY_BYTES)
        payload_nonce, wrap_nonce = secrets.token_bytes(NONCE_BYTES), secrets.token_bytes(NONCE_BYTES)
        ciphertext = AESGCM(dek).encrypt(payload_nonce, payload.reveal(), _aad(binding))
        wrapped = AESGCM(keyring._key(keyring.active_version)).encrypt(
            wrap_nonce, dek, _aad(binding, kek_id=keyring.active_version))
        return Envelope(kek_id=keyring.active_version, payload_nonce=payload_nonce,
                        wrap_nonce=wrap_nonce, wrapped_dek=wrapped, ciphertext=ciphertext)
    except EnvelopeRejected:
        raise
    except Exception:
        raise EnvelopeRejected(ErrorCode.CRYPTO_FAILURE) from None


def _authenticated(envelope: Envelope, binding: AADBinding, keyring: KEKRing) -> tuple[bytes, bytes]:
    _arguments(binding, keyring, envelope)
    if not isinstance(envelope, Envelope):
        raise EnvelopeRejected(ErrorCode.INVALID_ENVELOPE)
    key = keyring._key(envelope.kek_id)
    try:
        dek = AESGCM(key).decrypt(envelope.wrap_nonce, envelope.wrapped_dek,
                                  _aad(binding, kek_id=envelope.kek_id))
        if len(dek) != KEY_BYTES:
            raise EnvelopeRejected(ErrorCode.AUTHENTICATION_FAILED)
        plaintext = AESGCM(dek).decrypt(envelope.payload_nonce, envelope.ciphertext, _aad(binding))
        if not 1 <= len(plaintext) <= MAX_PAYLOAD_BYTES:
            raise EnvelopeRejected(ErrorCode.AUTHENTICATION_FAILED)
        return dek, plaintext
    except Exception:
        raise EnvelopeRejected(ErrorCode.AUTHENTICATION_FAILED) from None


def open_envelope(envelope: Envelope, expected_binding: AADBinding, keyring: KEKRing) -> SecretPayload:
    """The expected binding/revision comes from trusted state, not the envelope."""
    _, plaintext = _authenticated(envelope, expected_binding, keyring)
    return SecretPayload(plaintext)


def rewrap(envelope: Envelope, expected_binding: AADBinding, keyring: KEKRing) -> Envelope:
    """Authenticate BOTH old AEADs, then wrap the existing DEK with active KEK."""
    dek, _ = _authenticated(envelope, expected_binding, keyring)
    try:
        wrap_nonce = secrets.token_bytes(NONCE_BYTES)
        wrapped = AESGCM(keyring._key(keyring.active_version)).encrypt(
            wrap_nonce, dek, _aad(expected_binding, kek_id=keyring.active_version))
        return Envelope(kek_id=keyring.active_version, payload_nonce=envelope.payload_nonce,
                        wrap_nonce=wrap_nonce, wrapped_dek=wrapped, ciphertext=envelope.ciphertext)
    except EnvelopeRejected:
        raise
    except Exception:
        raise EnvelopeRejected(ErrorCode.CRYPTO_FAILURE) from None


def dump_envelope(envelope: Envelope) -> str:
    """Explicit ciphertext-only wire representation; never serializes secrets."""
    if not isinstance(envelope, Envelope):
        raise EnvelopeRejected(ErrorCode.INVALID_ENVELOPE)
    encode = lambda value: base64.b64encode(value).decode("ascii")
    return _canonical({
        "schema_version": envelope.schema_version, "kek_id": envelope.kek_id,
        "payload_nonce": encode(envelope.payload_nonce), "wrap_nonce": encode(envelope.wrap_nonce),
        "wrapped_dek": encode(envelope.wrapped_dek), "ciphertext": encode(envelope.ciphertext),
    }).decode("ascii")


def _object(pairs: list[tuple]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise EnvelopeRejected(ErrorCode.INVALID_ENVELOPE)
        result[key] = value
    return result


def _unbase64(value: object, maximum: int) -> bytes:
    if (not isinstance(value, str) or len(value) > 4 * ((maximum + 2) // 3)
            or not value.isascii()):
        raise EnvelopeRejected(ErrorCode.INVALID_ENVELOPE)
    try:
        result = base64.b64decode(value, validate=True)
        if len(result) > maximum or base64.b64encode(result).decode("ascii") != value:
            raise EnvelopeRejected(ErrorCode.INVALID_ENVELOPE)
        return result
    except (ValueError, binascii.Error):
        raise EnvelopeRejected(ErrorCode.INVALID_ENVELOPE) from None


def load_envelope(document: str | bytes) -> Envelope:
    if type(document) not in (str, bytes) or len(document) > MAX_DOCUMENT_BYTES:
        raise EnvelopeRejected(ErrorCode.INVALID_ENVELOPE)
    try:
        if isinstance(document, bytes):
            document = document.decode("utf-8")
        # Bound UTF-8 bytes as well without allocating an unbounded encoding.
        if len(document.encode("utf-8")) > MAX_DOCUMENT_BYTES:
            raise EnvelopeRejected(ErrorCode.INVALID_ENVELOPE)
        raw = json.loads(document, object_pairs_hook=_object,
                         parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        fields = {"schema_version", "kek_id", "payload_nonce", "wrap_nonce", "wrapped_dek", "ciphertext"}
        if not isinstance(raw, dict) or set(raw) != fields:
            raise EnvelopeRejected(ErrorCode.INVALID_ENVELOPE)
        return Envelope(
            schema_version=raw["schema_version"], kek_id=raw["kek_id"],
            payload_nonce=_unbase64(raw["payload_nonce"], NONCE_BYTES),
            wrap_nonce=_unbase64(raw["wrap_nonce"], NONCE_BYTES),
            wrapped_dek=_unbase64(raw["wrapped_dek"], KEY_BYTES + TAG_BYTES),
            ciphertext=_unbase64(raw["ciphertext"], MAX_PAYLOAD_BYTES + TAG_BYTES),
        )
    except EnvelopeRejected:
        raise
    except Exception:
        raise EnvelopeRejected(ErrorCode.INVALID_ENVELOPE) from None
