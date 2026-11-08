/** Public synthetic fixtures only; no durable authorization is actually issued. */
import { createHash } from "node:crypto";
import type { CredentialAction } from "../../src/lib/credential-action-contracts.ts";
import {
  PASSKEY_CREDENTIAL_KIND, type PasskeyCredentialAuthorization,
  type PasskeyCredentialContext, type PasskeyCredentialTokenInput,
} from "../../src/lib/passkey-credential-token.ts";

export const now = 1_700_000_000;
export const key = new Uint8Array(32).fill(57);
export const id = (value: number) => `00000000-0000-0000-0000-${value.toString().padStart(12, "0")}`;
export const hash = (wire: string) => createHash("sha256").update(wire, "utf8").digest("hex");
export function signing(action: CredentialAction = "register"): PasskeyCredentialTokenInput {
  const context: PasskeyCredentialContext = {
    tenantId: id(11), userId: id(12), subject: "opaque-fixture-sub",
    authEpoch: 4, oidcIssuer: "https://identity.fixture.invalid", oidcAuthTime: now - 3600,
    origin: "https://cockpit.fixture.invalid:8443",
    sessionBinding: "b".repeat(64), sessionExpiresAt: now + 200,
  };
  const target = { action, platform_account_id: id(13), connection_id: id(14),
    ...(action === "register" ? {} : { expected_revision: 2, expected_storage: 3 }) };
  const { action: _action, ...bound } = target;
  const body = JSON.stringify({ ...bound, ...(action === "revoke" ? {} : {
    credentials: { api_key: "SYNTHETIC-FIXTURE-KEY", secret: "synthetic-päß-/1e0",
      passphrase: "fixture-passphrase" },
  }) });
  const authorization: PasskeyCredentialAuthorization = {
    kind: PASSKEY_CREDENTIAL_KIND, authorization_id: id(15), proof_id: id(16), grant_id: id(17),
    tenant_id: context.tenantId, user_id: context.userId, subject: context.subject,
    auth_epoch: context.authEpoch, oidc_issuer: context.oidcIssuer, oidc_auth_time: context.oidcAuthTime,
    origin: context.origin, rp_id: "cockpit.fixture.invalid",
    session_binding: context.sessionBinding, session_expires_at: context.sessionExpiresAt,
    passkey_id: id(18), passkey_version: 2, target: target as PasskeyCredentialAuthorization["target"],
    prepared_at: now - 10, checked_at: now - 2, authorized_at: now - 1, expires_at: now + 90,
    metadata_sha256: "c".repeat(64), body_sha256: hash(body),
  };
  return { key: new Uint8Array(key), context, authorization, body, clock: () => now };
}
