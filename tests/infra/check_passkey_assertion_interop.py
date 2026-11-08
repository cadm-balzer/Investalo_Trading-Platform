"""Offline real TS/Jose->Python HS256 interoperability, only synthetic fixtures."""
import base64
import hashlib
import hmac
import json
from pathlib import Path
import subprocess
import sys
from uuid import UUID

from investalo_credential_store.passkey_request_assertion import (
    PasskeyRequestContext, PasskeyRequestVerifier,
)
from investalo_credential_store.request_assertion import OnboardingRejected, RequestVerifier

ROOT = Path(__file__).resolve().parents[2]
KEY = bytes([57]) * 32  # Same public synthetic fixture key; never a runtime secret.
CHECKS = 0


def check(value):
    global CHECKS
    if not value:
        raise RuntimeError("Offline interoperability assertion failed")
    CHECKS += 1


def reject(callback):
    try:
        callback()
    except OnboardingRejected as failure:
        check(failure.code == "authentication_required")
    else:
        raise RuntimeError("Offline interoperability rejection missing")


def b64(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def claims(token):
    encoded = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))


def resign(payload):
    # A trusted-service test signer allows malformed authenticated contracts.
    encoded = b64(b'{"alg":"HS256","typ":"JWT"}') + "." + b64(
        json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    return encoded + "." + b64(hmac.digest(KEY, encoded.encode("ascii"), "sha256"))


def main():
    completed = subprocess.run(
        ["node", "--experimental-strip-types", "tests/fixtures/emit-passkey-credential-fixtures.ts"],
        cwd=ROOT / "apps/cockpit", capture_output=True, timeout=30,
    )
    if completed.returncode or len(completed.stdout) > 100_000:
        raise RuntimeError("Offline TypeScript fixture generation failed")
    rows = json.loads(completed.stdout)
    check(len(rows) == 6)
    for row in rows:
        source, expected, current = row["authorization"], row["context"], row["now"]
        context = PasskeyRequestContext(
            tenant_id=UUID(expected["tenantId"]), user_id=UUID(expected["userId"]),
            subject=expected["subject"], auth_epoch=expected["authEpoch"],
            oidc_auth_time=expected["oidcAuthTime"], session_binding=expected["sessionBinding"],
            session_expires_at=expected["sessionExpiresAt"],
        )
        verifier = PasskeyRequestVerifier(key=KEY, oidc_issuer=expected["oidcIssuer"],
                                         origin=expected["origin"], clock=lambda: current)
        legacy = RequestVerifier(key=KEY, oidc_issuer=expected["oidcIssuer"], clock=lambda: current)
        body, action, token = row["body"].encode("utf-8"), row["action"], row["token"]
        verified = verifier.verify(token, action=action, body=body, context=context)
        check(verified.oidc_auth_time == current - 3600)
        check(verified.passkey_checked_at == source["checked_at"])
        check(verified.authorization_id == UUID(source["authorization_id"]))
        check(verified.proof_id == UUID(source["proof_id"]) and verified.grant_id == UUID(source["grant_id"]))
        check(verified.passkey_id == UUID(source["passkey_id"]) and verified.passkey_version == source["passkey_version"])
        check(dict(verified.target) == source["target"])
        check(verified.body_sha256 == hashlib.sha256(body).hexdigest())
        check(verified.metadata_sha256 == source["metadata_sha256"])
        check(verified.exp == min(current + 60, source["expires_at"]))
        check("oidc_amr" not in claims(token))
        # Authentication is repeatable. Persistence, consent and single-use
        # authorization issuance are not supplied or claimed by this checkpoint.
        check(verifier.verify(token, action=action, body=body, context=context).jti == verified.jti)
        reject(lambda: legacy.verify(token, action=action, body=body))
        reject(lambda: verifier.verify(row["legacy_token"], action=action, body=body, context=context))
        reject(lambda: verifier.verify(token, action=action, body=body + b" ", context=context))
        reject(lambda: verifier.verify(token, action="replace" if action != "replace" else "revoke",
                                       body=body, context=context))
        wrong = PasskeyRequestContext(
            tenant_id=context.tenant_id, user_id=UUID(int=99), subject=context.subject,
            auth_epoch=context.auth_epoch, oidc_auth_time=context.oidc_auth_time,
            session_binding=context.session_binding, session_expires_at=context.session_expires_at,
        )
        reject(lambda: verifier.verify(token, action=action, body=body, context=wrong))
        mutated = {**claims(token), "oidc_auth_time": source["checked_at"]}
        reject(lambda: verifier.verify(resign(mutated), action=action, body=body, context=context))
        expired = PasskeyRequestVerifier(key=KEY, oidc_issuer=expected["oidcIssuer"],
                                        origin=expected["origin"], clock=lambda: verified.exp)
        reject(lambda: expired.verify(token, action=action, body=body, context=context))
    print(f"PASS: {CHECKS} offline TS/Jose/Python checks; no DB issuance, HTTP, broker or replay consumption.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Never publish driver output, tokens or fixture body bytes on failure.
        print("FAIL: offline passkey assertion interoperability unavailable.", file=sys.stderr)
        raise SystemExit(1) from None
