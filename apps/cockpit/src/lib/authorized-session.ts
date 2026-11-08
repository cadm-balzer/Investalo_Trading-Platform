import type { Session } from "./auth.ts";
import { canonicalUuid, credentialInteger } from "./credential-action-contracts.ts";
import { canonicalBytes } from "./passkey-enrollment-state.ts";
import { sameSecret } from "./security.ts";

/** Keep the session that actually authorized HTTP Origin/CSRF checks immutable. */
export function snapshotAuthorizedSession(value: Session, now = Math.floor(Date.now() / 1000)): Readonly<Session> {
  canonicalUuid(value.tenantId); canonicalBytes(value.csrf, 32, 32);
  credentialInteger(value.authEpoch); credentialInteger(value.oidcAuthTime, 1);
  credentialInteger(value.expiresAt, 1); credentialInteger(now, 1);
  const issuer = new URL(value.issuer);
  if (issuer.protocol !== "https:" || issuer.origin !== value.issuer ||
    typeof value.subject !== "string" || !value.subject || value.subject.length > 255 ||
    /[\u0000-\u001f\u007f]/.test(value.subject) || value.oidcAuthTime > now + 5 ||
    value.expiresAt <= now) throw new Error("SESSION_AUTHORIZATION_REJECTED");
  return Object.freeze({ ...value });
}
export function assertAuthorizedSession(expected: Readonly<Session>, actual: Session, now = Math.floor(Date.now() / 1000)): void {
  const current = snapshotAuthorizedSession(actual, now);
  snapshotAuthorizedSession(expected, now);
  if (expected.issuer !== current.issuer || expected.subject !== current.subject ||
    expected.tenantId !== current.tenantId || expected.authEpoch !== current.authEpoch ||
    expected.oidcAuthTime !== current.oidcAuthTime || expected.expiresAt !== current.expiresAt ||
    !sameSecret(expected.csrf, current.csrf)) throw new Error("SESSION_AUTHORIZATION_REJECTED");
}
