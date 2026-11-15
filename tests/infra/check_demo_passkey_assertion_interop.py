"""Offline real TS/Jose->Python own Demo verifier; synthetic public fixtures."""
import base64
import hashlib
import hmac
import json
from pathlib import Path
import subprocess
from uuid import UUID

from investalo_credential_store.demo_passkey_assertion import DemoPasskeyRequestVerifier
from investalo_credential_store.passkey_request_assertion import PasskeyRequestContext, PasskeyRequestVerifier
from investalo_credential_store.request_assertion import OnboardingRejected

ROOT = Path(__file__).resolve().parents[2]
KEY = bytes([57]) * 32
CHECKS = 0


def check(value):
    global CHECKS
    if not value:
        raise RuntimeError("Own offline interoperability assertion failed")
    CHECKS += 1


def reject(callback):
    try:
        callback()
    except OnboardingRejected as failure:
        check(failure.code == "authentication_required")
    else:
        raise RuntimeError("Own offline interoperability rejection missing")


def b64(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def resign(data):
    wire = b64(b'{"alg":"HS256","typ":"JWT"}') + "." + b64(json.dumps(data, separators=(",", ":")).encode())
    return wire + "." + b64(hmac.digest(KEY, wire.encode(), "sha256"))


def main():
    # Optional stdin is emitted by the independently pinned Node check container.
    import sys
    if "--stdin" in sys.argv:
        wire = sys.stdin.buffer.read(100_001)
    else:
        completed = subprocess.run(["node", "--experimental-strip-types",
            "tests/fixtures/emit-demo-passkey-credential-fixtures.ts"],
            cwd=ROOT/"apps/cockpit", capture_output=True, timeout=30)
        if completed.returncode:
            raise RuntimeError("Own TypeScript fixture generation failed")
        wire = completed.stdout
    if len(wire) > 100_000:
        raise RuntimeError("Own fixture budget exceeded")
    rows = json.loads(wire)
    check(len(rows) == 5)
    for row in rows:
        source, expected, now = row["authorization"], row["context"], row["now"]
        context = PasskeyRequestContext(tenant_id=UUID(expected["tenantId"]), user_id=UUID(expected["userId"]),
            subject=expected["subject"], auth_epoch=expected["authEpoch"], oidc_auth_time=expected["oidcAuthTime"],
            session_binding=expected["sessionBinding"], session_expires_at=expected["sessionExpiresAt"])
        options = dict(key=KEY, oidc_issuer=expected["oidcIssuer"], origin=expected["origin"], clock=lambda: now)
        demo, normal = DemoPasskeyRequestVerifier(**options), PasskeyRequestVerifier(**options)
        raw, action, token = row["body"].encode(), row["action"], row["token"]
        parsed = demo.verify(token, action=action, body=raw, context=context)
        check(parsed.authorization_kind == "passkey-demo-credential-authorization/1")
        check(parsed.aud == "investalo-credentials-demo-passkey")
        check(parsed.htu == "/v1/credentials/bitget-demo/" + action)
        check(parsed.oidc_auth_time == now - 3600)
        check(parsed.passkey_checked_at == source["checked_at"])
        check(parsed.authorization_id == UUID(source["authorization_id"]))
        check(parsed.proof_id == UUID(source["proof_id"]) and parsed.grant_id == UUID(source["grant_id"]))
        check(parsed.passkey_id == UUID(source["passkey_id"]) and parsed.passkey_version == source["passkey_version"])
        check(dict(parsed.target) == source["target"])
        check(parsed.body_sha256 == hashlib.sha256(raw).hexdigest())
        check(parsed.metadata_sha256 == source["metadata_sha256"])
        check(parsed.exp == min(now + 60, source["expires_at"]))
        reject(lambda: normal.verify(token, action=action, body=raw, context=context))
        reject(lambda: demo.verify(row["normal_token"], action=action, body=raw, context=context))
        reject(lambda: demo.verify(token, action=action, body=raw + b" ", context=context))
        reject(lambda: demo.verify(token, action="replace", body=raw, context=context))
        data = json.loads(base64.urlsafe_b64decode(token.split(".")[1] + "=" * (-len(token.split(".")[1]) % 4)))
        for changes in (
            {"aud": "investalo-credentials-passkey"},
            {"authorization_kind": "passkey-credential-authorization/1"},
            {"htu": "/v1/credentials/bitget/" + action},
            {"oidc_auth_time": source["checked_at"]},
            {"exp": now + 121},
            {"target": {**source["target"], "action": "replace"}},
        ):
            reject(lambda changes=changes: demo.verify(resign({**data, **changes}), action=action, body=raw, context=context))
    print(f"PASS: {CHECKS} own TS/Jose/Python interoperability checks; synthetic only")


if __name__ == "__main__":
    main()
