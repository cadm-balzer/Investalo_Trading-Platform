import { createHash, randomUUID } from "node:crypto";
import { SignJWT } from "jose";
import { canonicalUuid, credentialInteger, parseActionTarget } from "./credential-action-contracts.ts";
import type { ActionTarget } from "./credential-action-contracts.ts";

export const CREDENTIAL_ACTION_TARGETS = Object.freeze({
  register: "/v1/credentials/bitget/register",
  replace: "/v1/credentials/bitget/replace",
  revoke: "/v1/credentials/bitget/revoke",
});
export type CredentialMfaIdentity = Readonly<{
  subject: string; issuer: string; authTime: number; amr: readonly string[];
}>;
export type CredentialActionTokenInput = {
  /** Dedicated binary action key; never reuse the ordinary API or session key. */
  key: Uint8Array; oidcIssuer: string; identity: CredentialMfaIdentity;
  tenantId: string; authEpoch: number; startedAt: number;
  target: ActionTarget; body: string; now?: number;
};
const rejected = () => new Error("CREDENTIAL_ACTION_TOKEN_REJECTED");

/** Duplicate-free JSON: JSON.parse alone silently replaces repeated keys. */
function bodyObject(body: string): Record<string, unknown> {
  const parsed: unknown = JSON.parse(body);
  let at = 0;
  const space = () => { while (/\s/.test(body[at] ?? "") && at < body.length) at++; };
  const quoted = (): string => {
    const start = at++;
    while (at < body.length) {
      if (body[at] === "\\") { at += 2; continue; }
      if (body[at++] === '"') return JSON.parse(body.slice(start, at)) as string;
    }
    throw rejected();
  };
  const walk = (depth: number): void => {
    if (depth > 4) throw rejected();
    space();
    if (body[at] === "{") {
      at++; space(); const seen = new Set<string>();
      if (body[at] === "}") { at++; return; }
      do {
        space(); const key = quoted(); space();
        if (seen.has(key) || body[at++] !== ":") throw rejected();
        seen.add(key); walk(depth + 1); space();
        if (body[at] === "}") { at++; return; }
      } while (body[at++] === ",");
      throw rejected();
    }
    if (body[at] === "[") throw rejected(); // None of the private request fields is an array.
    if (body[at] === '"') { quoted(); return; }
    while (at < body.length && !/[,\s}]/.test(body[at])) at++;
  };
  walk(0); space();
  if (at !== body.length || !parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw rejected();
  return parsed as Record<string, unknown>;
}
function exactFields(item: Record<string, unknown>, fields: readonly string[]): void {
  const actual = Object.keys(item);
  if (actual.length !== fields.length || actual.some(key => !fields.includes(key))) throw rejected();
}
function validateBody(body: string, target: ActionTarget): void {
  const item = bodyObject(body), fields = ["platform_account_id", "connection_id"];
  if (target.action !== "register") fields.push("expected_revision", "expected_storage");
  if (target.action !== "revoke") fields.push("credentials");
  exactFields(item, fields);
  if (item.platform_account_id !== target.platform_account_id || item.connection_id !== target.connection_id ||
    (target.action !== "register" && (item.expected_revision !== target.expected_revision ||
      item.expected_storage !== target.expected_storage))) throw rejected();
  if (target.action !== "revoke") {
    const triple = item.credentials;
    if (!triple || typeof triple !== "object" || Array.isArray(triple)) throw rejected();
    exactFields(triple as Record<string, unknown>, ["api_key", "secret", "passphrase"]);
    for (const [name, maximum] of [["api_key", 256], ["secret", 1024], ["passphrase", 256]] as const) {
      const value = (triple as Record<string, unknown>)[name];
      if (typeof value !== "string" || !value || value.length > maximum ||
        !value.isWellFormed() || /[\p{Cc}\p{Cf}\p{Cs}]/u.test(value)) throw rejected();
    }
  }
}
/** Trusted server primitive. It does not verify an IdP token or prove MFA by itself. */
export async function createCredentialActionToken(input: CredentialActionTokenInput): Promise<string> {
  try {
    if (!(input.key instanceof Uint8Array) || input.key.byteLength < 32 || input.key.byteLength > 128 ||
      typeof input.oidcIssuer !== "string" || !input.oidcIssuer || input.oidcIssuer.length > 255 ||
      /[\u0000-\u0020\u007f]/.test(input.oidcIssuer)) throw rejected();
    const issuer = new URL(input.oidcIssuer);
    if (issuer.protocol !== "https:" || !issuer.hostname || issuer.username || issuer.password ||
      issuer.search || issuer.hash) throw rejected();
    const identity = input.identity;
    if (identity.issuer !== input.oidcIssuer || typeof identity.subject !== "string" || !identity.subject ||
      identity.subject.length > 255 || !identity.subject.isWellFormed() ||
      /[\u0000-\u001f\u007f]/.test(identity.subject) || !Array.isArray(identity.amr) ||
      identity.amr.length < 1 || identity.amr.length > 8 ||
      identity.amr.some(value => typeof value !== "string" || !/^[a-z0-9_-]{1,32}$/.test(value)) ||
      new Set(identity.amr).size !== identity.amr.length || !identity.amr.includes("mfa")) throw rejected();
    const now = credentialInteger(input.now ?? Math.floor(Date.now() / 1000), 1);
    const authTime = credentialInteger(identity.authTime, 1), startedAt = credentialInteger(input.startedAt, 1);
    const authEpoch = credentialInteger(input.authEpoch), tenant = canonicalUuid(input.tenantId);
    if (now > Number.MAX_SAFE_INTEGER - 60 || authTime < startedAt || authTime < now - 120 ||
      authTime > now + 5 || startedAt < now - 300 || startedAt > now + 5 ||
      typeof input.body !== "string" || !input.body.isWellFormed()) throw rejected();
    const body = Buffer.from(input.body, "utf8");
    if (body.length < 1 || body.length > 4096) throw rejected();
    const target = parseActionTarget(input.target);
    validateBody(input.body, target);
    // Snapshot mutable inputs before the asynchronous signing operation.
    const key = new Uint8Array(input.key), amr = [...identity.amr];
    return await new SignJWT({
      oidc_iss: input.oidcIssuer, oidc_auth_time: authTime, oidc_amr: amr,
      step_up_started_at: startedAt, tenant_id: tenant, auth_epoch: authEpoch,
      htm: "POST", htu: CREDENTIAL_ACTION_TARGETS[target.action],
      body_sha256: createHash("sha256").update(body).digest("hex"),
    }).setProtectedHeader({ alg: "HS256", typ: "JWT" })
      .setIssuer("investalo-bff").setAudience("investalo-credentials").setSubject(identity.subject)
      .setIssuedAt(now).setExpirationTime(now + 60).setJti(randomUUID()).sign(key);
  } catch {
    // Neither broker input nor the dedicated key may appear in exceptions.
    throw rejected();
  }
}
