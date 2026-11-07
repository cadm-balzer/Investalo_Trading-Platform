"""Exact signed GET bytes. No caller URL, generic order method or serialization."""
from __future__ import annotations

import base64
import hashlib
import hmac
from types import MappingProxyType
from collections.abc import Mapping
from urllib.parse import urlencode

from .models import BitgetRejected, ErrorCode, ProductType

ORIGIN = "https://api.bitget.com"
INFO_PATH = "/api/v2/spot/account/info"
SPOT_PATH = "/api/v2/spot/account/assets"
FUTURES_PATH = "/api/v2/mix/account/accounts"
ALLOWLIST = frozenset((INFO_PATH, SPOT_PATH, FUTURES_PATH))


class Credentials:
    __slots__ = ("_api_key", "_secret_key", "_passphrase")

    def __init__(self, api_key: str, secret_key: str, passphrase: str):
        for value in (api_key, passphrase):
            if (not isinstance(value, str) or not 1 <= len(value) <= 256
                    or value != value.strip() or any(not 32 <= ord(c) <= 126 for c in value)):
                raise BitgetRejected(ErrorCode.INVALID_CREDENTIALS)
        if not isinstance(secret_key, str) or not 1 <= len(secret_key) <= 1024:
            raise BitgetRejected(ErrorCode.INVALID_CREDENTIALS)
        try:
            encoded = secret_key.encode("utf-8")
        except UnicodeError:
            raise BitgetRejected(ErrorCode.INVALID_CREDENTIALS) from None
        if (not 1 <= len(encoded) <= 1024
                or any(ord(c) < 32 or ord(c) == 127 for c in secret_key)):
            raise BitgetRejected(ErrorCode.INVALID_CREDENTIALS)
        object.__setattr__(self, "_api_key", api_key)
        object.__setattr__(self, "_secret_key", encoded)
        object.__setattr__(self, "_passphrase", passphrase)

    def __setattr__(self, name, value):
        raise AttributeError("Credentials are immutable")

    def __repr__(self):
        return "Credentials(<redacted>)"

    def __reduce_ex__(self, protocol):
        raise TypeError("Credentials serialization denied")


def hmac_sha256_base64(key: bytes, message: bytes) -> str:
    """Primitive for reviewed test vectors; never dispatches requests."""
    return base64.b64encode(hmac.new(key, message, hashlib.sha256).digest()).decode("ascii")


def validate_target(path: str, parameters: tuple[tuple[str, str], ...]):
    if not isinstance(path, str) or path not in ALLOWLIST or not isinstance(parameters, tuple):
        raise BitgetRejected(ErrorCode.INVALID_REQUEST)
    if any(not isinstance(pair, tuple) or len(pair) != 2 or
           not all(isinstance(value, str) for value in pair) for pair in parameters):
        raise BitgetRejected(ErrorCode.INVALID_REQUEST)
    if path == INFO_PATH and parameters != ():
        raise BitgetRejected(ErrorCode.INVALID_REQUEST)
    if path == SPOT_PATH and parameters != (("assetType", "all"),):
        raise BitgetRejected(ErrorCode.INVALID_REQUEST)
    if path == FUTURES_PATH and (
        len(parameters) != 1 or parameters[0][0] != "productType"
        or parameters[0][1] not in tuple(value.value for value in ProductType)
    ):
        raise BitgetRejected(ErrorCode.INVALID_REQUEST)

class RedactedHeaders(Mapping):
    """Trusted transport may read values; incidental repr/str never prints them."""
    __slots__ = ("_values",)

    def __init__(self, values: dict[str, str]):
        object.__setattr__(self, "_values", MappingProxyType(dict(values)))

    def __getitem__(self, key):
        return self._values[key]

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)

    def __repr__(self):
        return "RedactedHeaders(<redacted>)"

    __str__ = __repr__

    def __setattr__(self, name, value):
        raise AttributeError("Headers are immutable")

    def __reduce_ex__(self, protocol):
        raise TypeError("Headers serialization denied")


class SignedReadRequest:
    __slots__ = ("path", "parameters", "url", "method", "body", "_headers")

    def __init__(self, credentials: Credentials, path: str, parameters: tuple[tuple[str, str], ...],
                 timestamp_ms: int, *, method: str = "GET", body: bytes = b""):
        if (not isinstance(credentials, Credentials) or method != "GET" or body != b""
                or type(timestamp_ms) is not int or not 0 <= timestamp_ms < 10**15):
            raise BitgetRejected(ErrorCode.INVALID_REQUEST)
        validate_target(path, parameters)
        target = path + ("?" + urlencode(parameters) if parameters else "")
        timestamp = str(timestamp_ms)
        signature = hmac_sha256_base64(credentials._secret_key,
                                      (timestamp + "GET" + target).encode("ascii"))
        object.__setattr__(self, "path", path)
        object.__setattr__(self, "parameters", parameters)
        object.__setattr__(self, "url", ORIGIN + target)
        object.__setattr__(self, "method", "GET")
        object.__setattr__(self, "body", b"")
        object.__setattr__(self, "_headers", RedactedHeaders({
            "ACCESS-KEY": credentials._api_key, "ACCESS-SIGN": signature,
            "ACCESS-TIMESTAMP": timestamp, "ACCESS-PASSPHRASE": credentials._passphrase,
            "locale": "en-US", "Accept": "application/json", "Content-Type": "application/json",
        }))

    @property
    def headers(self):
        return self._headers

    def validate(self):
        validate_target(self.path, self.parameters)
        expected = ORIGIN + self.path + ("?" + urlencode(self.parameters) if self.parameters else "")
        if self.method != "GET" or self.body != b"" or self.url != expected:
            raise BitgetRejected(ErrorCode.INVALID_REQUEST)

    def __setattr__(self, name, value):
        raise AttributeError("Signed requests are immutable")

    def __repr__(self):
        return "SignedReadRequest(<redacted>)"

    def __reduce_ex__(self, protocol):
        raise TypeError("Signed request serialization denied")
