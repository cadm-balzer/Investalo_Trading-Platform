import base64
import hashlib
import hmac
import json
import time
from uuid import uuid4

import pytest

from investalo_api.settings import Settings


@pytest.fixture
def settings():
    # Ephemeral test credential generated per test; never a runtime default.
    return Settings(internal_key=uuid4().hex + uuid4().hex, oidc_issuer="https://idp.test")


def token(settings, *, method="GET", target="/v1/me", body=b"", claims=None, header=None):
    now = int(time.time())
    values = {
        "iss": "investalo-bff", "aud": "investalo-api", "sub": "opaque-subject",
        "oidc_iss": settings.oidc_issuer, "iat": now, "exp": now + 30,
        "oidc_auth_time": now, "jti": str(uuid4()),
        "htm": method, "htu": target, "body_sha256": hashlib.sha256(body).hexdigest(),
    }
    values.update(claims or {})
    encode = lambda value: base64.urlsafe_b64encode(value).rstrip(b"=").decode()
    prefix = encode(json.dumps(header or {"alg": "HS256", "typ": "JWT"}).encode())
    payload = encode(json.dumps(values).encode())
    signature = encode(hmac.digest(settings.internal_key.encode(), f"{prefix}.{payload}".encode(), "sha256"))
    return f"{prefix}.{payload}.{signature}"
