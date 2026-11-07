"""Explicit private-service codec; plaintext never has a general serializer."""
from enum import StrEnum
import json
import unicodedata

from investalo_bitget import Credentials
from investalo_credentials import SecretPayload, MAX_PAYLOAD_BYTES

SCHEMA_VERSION = "bitget-credentials/1"


class PayloadErrorCode(StrEnum):
    INVALID_PAYLOAD = "invalid_bitget_payload"


class PayloadRejected(ValueError):
    def __init__(self, code: PayloadErrorCode = PayloadErrorCode.INVALID_PAYLOAD):
        self.code = PayloadErrorCode.INVALID_PAYLOAD
        super().__init__(self.code.value)


def _validate(api_key: object, secret: object, passphrase: object) -> Credentials:
    if (any(type(value) is not str for value in (api_key, secret, passphrase))
            or len(api_key) > 256 or len(passphrase) > 256 or len(secret) > 1024
            or any(unicodedata.category(character) in ("Cc", "Cf", "Cs")
                   for value in (api_key, secret, passphrase) for character in value)):
        raise PayloadRejected() from None
    # Reuse the adapter's exact credential constraints; no independent triple
    # normalization, trimming or alternative broker/signature interpretation.
    return Credentials(api_key, secret, passphrase)


def _canonical(api_key: str, secret: str, passphrase: str) -> bytes:
    return json.dumps({"schema_version": SCHEMA_VERSION, "api_key": api_key,
                       "secret": secret, "passphrase": passphrase},
                      ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def encode_credentials(credentials: Credentials) -> SecretPayload:
    """Explicit plaintext boundary for the trusted store; no implicit logging."""
    try:
        if not isinstance(credentials, Credentials):
            raise PayloadRejected() from None
        # Existing adapter deliberately exposes no general serializer. Private
        # slots are accessed only at this explicit internal-service boundary.
        api_key = credentials._api_key
        secret = credentials._secret_key.decode("utf-8")
        passphrase = credentials._passphrase
        _validate(api_key, secret, passphrase)
        return SecretPayload(_canonical(api_key, secret, passphrase))
    except PayloadRejected:
        raise
    except Exception:
        raise PayloadRejected() from None


def _object(pairs: list[tuple]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise PayloadRejected() from None
        result[key] = value
    return result


def decode_credentials(payload: SecretPayload) -> Credentials:
    """Only exact canonical versioned bytes become adapter credentials."""
    try:
        if not isinstance(payload, SecretPayload):
            raise PayloadRejected() from None
        raw_bytes = payload.reveal()
        if type(raw_bytes) is not bytes or not 1 <= len(raw_bytes) <= MAX_PAYLOAD_BYTES:
            raise PayloadRejected() from None
        raw = json.loads(raw_bytes.decode("utf-8"), object_pairs_hook=_object,
                         parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        if (not isinstance(raw, dict) or set(raw) != {"schema_version", "api_key", "secret", "passphrase"}
                or type(raw["schema_version"]) is not str or raw["schema_version"] != SCHEMA_VERSION):
            raise PayloadRejected() from None
        credentials = _validate(raw["api_key"], raw["secret"], raw["passphrase"])
        if raw_bytes != _canonical(raw["api_key"], raw["secret"], raw["passphrase"]):
            raise PayloadRejected() from None
        return credentials
    except PayloadRejected:
        raise
    except Exception:
        raise PayloadRejected() from None
