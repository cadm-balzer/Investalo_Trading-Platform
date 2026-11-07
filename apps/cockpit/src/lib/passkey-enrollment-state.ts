import { canonicalUuid, credentialInteger } from "./credential-action-contracts.ts";
import { sameSecret, sha256 } from "./security.ts";
import type { Session } from "./auth.ts";
import type { RegistrationExpectedContext } from "./passkey-registration.ts";

export type PasskeyRecord = Readonly<{
  passkey_id: string; tenant_id: string; user_id: string; rp_id: string;
  credential_id: string; user_handle: string; public_key: string; sign_count: number;
  backup_eligible: boolean; backed_up: boolean; storage_version: number;
  status: "active" | "revoked"; enrollment_epoch: number;
}>;
export type PasskeyContext = Readonly<{
  tenant_id: string; user_id: string; auth_epoch: number; rp_id: string;
  credential: PasskeyRecord | null;
}>;
export type EnrollmentAttempt = RegistrationExpectedContext & Readonly<{
  claimId: string; binding: string; authEpoch: number;
}>;
const rejected = () => new Error("PASSKEY_ENROLLMENT_REJECTED");
export function exactObject(value: unknown, fields: readonly string[]): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value) ||
    ![Object.prototype, null].includes(Object.getPrototypeOf(value))) throw rejected();
  const keys = Reflect.ownKeys(value);
  if (keys.length !== fields.length || fields.some(field => !Object.hasOwn(value, field)) ||
    keys.some(key => typeof key !== "string" || !fields.includes(key) ||
      !Object.hasOwn(Object.getOwnPropertyDescriptor(value, key)!, "value"))) throw rejected();
  return value as Record<string, unknown>;
}
export function canonicalBytes(value: unknown, minimum: number, maximum: number): string {
  if (typeof value !== "string" || value.length > Math.ceil(maximum * 4 / 3) ||
    !/^[A-Za-z0-9_-]+$/.test(value)) throw rejected();
  const bytes = Buffer.from(value, "base64url");
  if (bytes.length < minimum || bytes.length > maximum || bytes.toString("base64url") !== value) throw rejected();
  return value;
}
export function parsePasskeyRecord(value: unknown, owner: { tenantId: string; userId: string; rpId: string }): PasskeyRecord {
  const item = exactObject(value, ["passkey_id", "tenant_id", "user_id", "rp_id", "credential_id",
    "user_handle", "public_key", "sign_count", "backup_eligible", "backed_up",
    "storage_version", "status", "enrollment_epoch"]);
  if (canonicalUuid(item.tenant_id) !== owner.tenantId || canonicalUuid(item.user_id) !== owner.userId ||
    item.rp_id !== owner.rpId || typeof item.backup_eligible !== "boolean" || typeof item.backed_up !== "boolean" ||
    (item.backed_up && !item.backup_eligible) || !["active", "revoked"].includes(item.status as string)) throw rejected();
  const sign_count = credentialInteger(item.sign_count);
  if (sign_count > 0xffff_ffff) throw rejected();
  return Object.freeze({ passkey_id: canonicalUuid(item.passkey_id), tenant_id: owner.tenantId, user_id: owner.userId,
    rp_id: owner.rpId, credential_id: canonicalBytes(item.credential_id, 1, 1023),
    user_handle: canonicalBytes(item.user_handle, 32, 32), public_key: canonicalBytes(item.public_key, 1, 2048),
    sign_count, backup_eligible: item.backup_eligible, backed_up: item.backed_up,
    storage_version: credentialInteger(item.storage_version, 1), status: item.status as PasskeyRecord["status"],
    enrollment_epoch: credentialInteger(item.enrollment_epoch) });
}
export function parsePasskeyContext(value: unknown, expected: { tenantId: string; authEpoch: number; rpId: string }): PasskeyContext {
  const item = exactObject(value, ["tenant_id", "user_id", "auth_epoch", "rp_id", "credential"]);
  const tenantId = canonicalUuid(expected.tenantId), userId = canonicalUuid(item.user_id);
  if (item.tenant_id !== tenantId || credentialInteger(item.auth_epoch) !== expected.authEpoch ||
    item.rp_id !== expected.rpId) throw rejected();
  return Object.freeze({ tenant_id: tenantId, user_id: userId, auth_epoch: expected.authEpoch, rp_id: expected.rpId,
    credential: item.credential === null ? null : parsePasskeyRecord(item.credential, { tenantId, userId, rpId: expected.rpId }) });
}
/** Includes opaque browser session and CSRF binding; no ticket/identity in logs or URLs. */
export function enrollmentBinding(handle: string, session: Session): string {
  canonicalBytes(handle, 32, 32); canonicalBytes(session.csrf, 32, 32);
  return sha256(JSON.stringify(["passkey-enrollment-v1", handle, session.csrf,
    session.issuer, session.subject, session.tenantId, session.authEpoch, session.oidcAuthTime]));
}
export function assertEnrollment(
  attempt: EnrollmentAttempt, handle: string, session: Session, current: PasskeyContext, now = Math.floor(Date.now() / 1000),
): void {
  if (!Number.isSafeInteger(now) || now <= 0 || !Number.isSafeInteger(session.expiresAt) || session.expiresAt <= now ||
    !Number.isSafeInteger(attempt.startedAt) || !Number.isSafeInteger(attempt.expiresAt) ||
    attempt.startedAt > now || attempt.expiresAt <= now || attempt.expiresAt > attempt.startedAt + 120 ||
    !sameSecret(attempt.binding, enrollmentBinding(handle, session)) ||
    attempt.tenantId !== session.tenantId ||
    attempt.authEpoch !== session.authEpoch || current.auth_epoch !== attempt.authEpoch ||
    current.tenant_id !== attempt.tenantId || current.user_id !== attempt.userId ||
    current.rp_id !== attempt.rpId || current.credential !== null) throw rejected();
}
/** Reject duplicate JSON keys including escaped spellings before JSON.parse. */
export function parseEnrollmentJson(wire: string): Record<string, unknown> {
  try { return enrollmentJson(wire); } catch { throw rejected(); }
}
function enrollmentJson(wire: string): Record<string, unknown> {
  if (!wire.isWellFormed() || Buffer.byteLength(wire) > 16_384) throw rejected();
  let at = 0, nodes = 0;
  const space = () => { while (at < wire.length && /[ \t\r\n]/.test(wire[at])) at++; };
  const quoted = (): string => {
    if (wire[at++] !== '"') throw rejected();
    const start = at - 1;
    while (at < wire.length) {
      if (wire[at] === "\\") { at += 2; continue; }
      if (wire[at++] === '"') return JSON.parse(wire.slice(start, at));
    }
    throw rejected();
  };
  const walk = (depth: number): void => {
    if (depth > 5 || ++nodes > 160) throw rejected();
    space();
    const close = wire[at] === "{" ? "}" : wire[at] === "[" ? "]" : null;
    if (close) {
      at++; space(); const seen = new Set<string>();
      if (wire[at] === close) { at++; return; }
      while (at < wire.length) {
        if (close === "}") {
          space(); const key = quoted(); space();
          if (seen.has(key) || wire[at++] !== ":") throw rejected();
          seen.add(key);
        }
        walk(depth + 1); space();
        if (wire[at] === close) { at++; return; }
        if (wire[at++] !== ",") throw rejected();
      }
      throw rejected();
    }
    if (wire[at] === '"') { quoted(); return; }
    const start = at;
    while (at < wire.length && !/[,\s}\]]/.test(wire[at])) at++;
    if (start === at) throw rejected();
  };
  walk(0); space();
  if (at !== wire.length) throw rejected();
  const value: unknown = JSON.parse(wire);
  if (!value || typeof value !== "object" || Array.isArray(value)) throw rejected();
  return value as Record<string, unknown>;
}
