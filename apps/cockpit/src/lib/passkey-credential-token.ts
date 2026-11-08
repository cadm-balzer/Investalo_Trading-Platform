/**
 * Trusted-server contract. Durable purpose authority comes from008; injected
 * private orchestration supplies the receipt without exposing a browser route.
 * A proof-only007 confirmation is never a credential-write authorization.
 */
import { createHash, randomUUID } from "node:crypto";
import { isIP } from "node:net";
import { SignJWT } from "jose";
import { canonicalUuid, credentialInteger, parseActionTarget, type ActionTarget } from "./credential-action-contracts.ts";
import { CREDENTIAL_ACTION_TARGETS } from "./credential-action-token.ts";
import { exactObject, parseEnrollmentJson } from "./passkey-enrollment-state.ts";

export const PASSKEY_CREDENTIAL_KIND = "passkey-credential-authorization/1";
export const PASSKEY_CREDENTIAL_AUDIENCE = "investalo-credentials-passkey";
export type PasskeyCredentialContext = Readonly<{
  tenantId: string; userId: string; subject: string; authEpoch: number;
  oidcIssuer: string; oidcAuthTime: number; origin: string;
  sessionBinding: string; sessionExpiresAt: number;
}>;
export type PasskeyCredentialAuthorization = Readonly<{
  kind: typeof PASSKEY_CREDENTIAL_KIND;
  authorization_id: string; proof_id: string; grant_id: string;
  tenant_id: string; user_id: string; subject: string; auth_epoch: number;
  oidc_issuer: string; oidc_auth_time: number; rp_id: string; origin: string;
  session_binding: string; session_expires_at: number;
  passkey_id: string; passkey_version: number; target: ActionTarget;
  prepared_at: number; checked_at: number; authorized_at: number; expires_at: number;
  metadata_sha256: string; body_sha256: string;
}>;
export type PasskeyCredentialTokenInput = Readonly<{
  /** Separate provisioned identity, never an API/session key. Only injected tests exist. */
  key: Uint8Array; context: PasskeyCredentialContext; authorization: unknown;
  body: string; clock?: () => number;
}>;
const failure = () => new Error("PASSKEY_CREDENTIAL_TOKEN_REJECTED");
const CONTEXT_FIELDS = ["tenantId", "userId", "subject", "authEpoch", "oidcIssuer",
  "oidcAuthTime", "origin", "sessionBinding", "sessionExpiresAt"];
const RECEIPT_FIELDS = ["kind", "authorization_id", "proof_id", "grant_id", "tenant_id",
  "user_id", "subject", "auth_epoch", "oidc_issuer", "oidc_auth_time", "rp_id", "origin",
  "session_binding", "session_expires_at", "passkey_id", "passkey_version", "target",
  "prepared_at", "checked_at", "authorized_at", "expires_at", "metadata_sha256", "body_sha256"];
function text(value: unknown, maximum: number): string {
  if (typeof value !== "string" || !value || !value.isWellFormed() ||
    Buffer.byteLength(value, "utf8") > maximum || /[\p{Cc}\p{Cf}\p{Cs}]/u.test(value)) throw failure();
  return value;
}
function digest(value: unknown): string {
  if (typeof value !== "string" || !/^[a-f0-9]{64}$/.test(value)) throw failure();
  return value;
}
function httpsOrigin(value: unknown): string {
  const wire = text(value, 255), uri = new URL(wire), host = uri.hostname;
  if (uri.protocol !== "https:" || uri.origin !== wire || uri.username || uri.password ||
    isIP(host) || host.length > 253 || !host.includes(".") || /^[0-9]+$/.test(host.split(".").at(-1)!) ||
    (uri.port !== "" && (Number(uri.port) < 1 || Number(uri.port) > 65535)) ||
    host.split(".").some(label => !/^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(label))) throw failure();
  return wire;
}
function time(value: unknown): number { return credentialInteger(value, 1); }
function clockTime(clock: () => number): number {
  const now = time(clock());
  if (now > Number.MAX_SAFE_INTEGER - 300) throw failure();
  return now;
}
function contextSnapshot(value: PasskeyCredentialContext): PasskeyCredentialContext {
  const item = exactObject(value, CONTEXT_FIELDS);
  return Object.freeze({
    tenantId: canonicalUuid(item.tenantId), userId: canonicalUuid(item.userId),
    subject: text(item.subject, 255), authEpoch: credentialInteger(item.authEpoch),
    oidcIssuer: httpsOrigin(item.oidcIssuer), oidcAuthTime: time(item.oidcAuthTime),
    origin: httpsOrigin(item.origin), sessionBinding: digest(item.sessionBinding),
    sessionExpiresAt: time(item.sessionExpiresAt),
  });
}
function integerWire(wire: string): void {
  // JSON.parse rounds numbers and turns1.0/1e0 into integers. The Python contract
  // requires integer wire values too. Skip quoted content, including escapes.
  for (let at = 0; at < wire.length; at++) {
    if (wire[at] === '"') {
      while (++at < wire.length) {
        if (wire[at] === "\\") at++;
        else if (wire[at] === '"') break;
      }
    } else if (/[0-9.-]/.test(wire[at])) {
      const start = at;
      while (at < wire.length && !/[,}\] \t\r\n]/.test(wire[at])) at++;
      if (!/^(0|[1-9][0-9]*)$/.test(wire.slice(start, at))) throw failure();
      at--;
    }
  }
}
/** Validate exact private body bytes without issuing authority or retaining secrets. */
export function validatePasskeyCredentialBody(wire: string, expected: ActionTarget): Uint8Array {
  try { return privateBody(wire, parseActionTarget(expected)); }
  catch { throw failure(); }
}
function privateBody(wire: string, target: ActionTarget): Uint8Array {
  if (typeof wire !== "string" || !wire.isWellFormed() || Buffer.byteLength(wire) < 1 ||
    Buffer.byteLength(wire) > 4096) throw failure();
  const fields = ["platform_account_id", "connection_id"];
  if (target.action !== "register") fields.push("expected_revision", "expected_storage");
  if (target.action !== "revoke") fields.push("credentials");
  const item = exactObject(parseEnrollmentJson(wire), fields);
  integerWire(wire);
  if (item.platform_account_id !== target.platform_account_id || item.connection_id !== target.connection_id ||
    (target.action !== "register" && (item.expected_revision !== target.expected_revision ||
      item.expected_storage !== target.expected_storage))) throw failure();
  if (target.action !== "revoke") {
    const triple = exactObject(item.credentials, ["api_key", "secret", "passphrase"]);
    text(triple.api_key, 256); text(triple.secret, 1024); text(triple.passphrase, 256);
  }
  return Buffer.from(wire, "utf8");
}
/** Structural validation of a trusted receipt, not DB issuance or replay protection. */
export function parsePasskeyCredentialAuthorization(
  value: unknown, expected: PasskeyCredentialContext, body: string, now: number,
): PasskeyCredentialAuthorization {
  try {
    const context = contextSnapshot(expected), item = exactObject(value, RECEIPT_FIELDS);
    clockTime(() => now);
    if (item.kind !== PASSKEY_CREDENTIAL_KIND) throw failure();
    const result: PasskeyCredentialAuthorization = Object.freeze({
      kind: PASSKEY_CREDENTIAL_KIND, authorization_id: canonicalUuid(item.authorization_id),
      proof_id: canonicalUuid(item.proof_id), grant_id: canonicalUuid(item.grant_id),
      tenant_id: canonicalUuid(item.tenant_id), user_id: canonicalUuid(item.user_id),
      subject: text(item.subject, 255), auth_epoch: credentialInteger(item.auth_epoch),
      oidc_issuer: httpsOrigin(item.oidc_issuer), oidc_auth_time: time(item.oidc_auth_time),
      rp_id: text(item.rp_id, 253), origin: httpsOrigin(item.origin),
      session_binding: digest(item.session_binding), session_expires_at: time(item.session_expires_at),
      passkey_id: canonicalUuid(item.passkey_id), passkey_version: credentialInteger(item.passkey_version, 2),
      target: parseActionTarget(item.target), prepared_at: time(item.prepared_at),
      checked_at: time(item.checked_at), authorized_at: time(item.authorized_at),
      expires_at: time(item.expires_at), metadata_sha256: digest(item.metadata_sha256),
      body_sha256: digest(item.body_sha256),
    });
    if (new Set([result.authorization_id, result.proof_id, result.grant_id]).size !== 3 ||
      result.tenant_id !== context.tenantId || result.user_id !== context.userId ||
      result.subject !== context.subject || result.auth_epoch !== context.authEpoch ||
      result.oidc_issuer !== context.oidcIssuer || result.oidc_auth_time !== context.oidcAuthTime ||
      result.origin !== context.origin || result.rp_id !== new URL(context.origin).hostname ||
      result.session_binding !== context.sessionBinding || result.session_expires_at !== context.sessionExpiresAt ||
      result.oidc_auth_time > now + 5 || result.prepared_at < now - 300 ||
      result.prepared_at > result.checked_at || result.checked_at < now - 120 ||
      result.checked_at > result.authorized_at || result.authorized_at > now ||
      result.expires_at <= now || result.expires_at <= result.authorized_at ||
      result.expires_at > Math.min(result.checked_at + 120, result.session_expires_at) ||
      createHash("sha256").update(validatePasskeyCredentialBody(body, result.target)).digest("hex") !== result.body_sha256) throw failure();
    return result;
  } catch { throw failure(); }
}
export async function createPasskeyCredentialActionToken(input: PasskeyCredentialTokenInput): Promise<string> {
  try {
    if (!(input.key instanceof Uint8Array) || input.key.byteLength < 32 || input.key.byteLength > 128) throw failure();
    const clock = input.clock ?? (() => Math.floor(Date.now() / 1000));
    if (typeof clock !== "function") throw failure();
    const now = clockTime(clock), context = contextSnapshot(input.context), body = input.body;
    const receipt = parsePasskeyCredentialAuthorization(input.authorization, context, body, now);
    const key = new Uint8Array(input.key), expires = Math.min(now + 60, receipt.expires_at);
    const token = await new SignJWT({
      authorization_kind: receipt.kind, authorization_id: receipt.authorization_id,
      proof_id: receipt.proof_id, grant_id: receipt.grant_id,
      tenant_id: receipt.tenant_id, user_id: receipt.user_id, auth_epoch: receipt.auth_epoch,
      oidc_iss: receipt.oidc_issuer, oidc_auth_time: receipt.oidc_auth_time,
      rp_id: receipt.rp_id, origin: receipt.origin, session_binding: receipt.session_binding,
      session_expires_at: receipt.session_expires_at, passkey_id: receipt.passkey_id,
      passkey_version: receipt.passkey_version, passkey_started_at: receipt.prepared_at,
      passkey_checked_at: receipt.checked_at, passkey_authorized_at: receipt.authorized_at,
      authorization_expires_at: receipt.expires_at, metadata_sha256: receipt.metadata_sha256,
      target: receipt.target, body_sha256: receipt.body_sha256,
      htm: "POST", htu: CREDENTIAL_ACTION_TARGETS[receipt.target.action],
    }).setProtectedHeader({ alg: "HS256", typ: "JWT" }).setIssuer("investalo-bff")
      .setAudience(PASSKEY_CREDENTIAL_AUDIENCE).setSubject(receipt.subject)
      .setIssuedAt(now).setExpirationTime(expires).setJti(randomUUID()).sign(key);
    // Slow signing cannot publish an expired assertion. Caller still must recheck
    // its actual session/DB authority; this pure primitive has no persistence.
    const finished = clockTime(clock);
    if (finished < now || finished >= expires) throw failure();
    parsePasskeyCredentialAuthorization(receipt, context, body, finished);
    return token;
  } catch { throw failure(); }
}
