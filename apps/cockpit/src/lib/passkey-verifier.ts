import {
  generateAuthenticationOptions,
  verifyAuthenticationResponse,
  type AuthenticationResponseJSON,
  type CredentialDeviceType,
  type PublicKeyCredentialRequestOptionsJSON,
} from "@simplewebauthn/server";
import { canonicalUuid } from "./credential-action-contracts.ts";

/** Trusted registry/configuration and server challenge; never populated from an assertion. */
export type PasskeyExpectedContext = Readonly<{
  tenantId: string; userId: string; rpId: string; origin: string;
  challenge: string; startedAt: number; expiresAt: number;
  credential: Readonly<{
    tenantId: string; userId: string; id: string; publicKey: Uint8Array;
    counter: number; userHandle: string;
  }>;
}>;
export type VerifiedPasskeyAssertion = Readonly<{
  credentialId: string; newCounter: number; deviceType: CredentialDeviceType;
  backedUp: boolean; checkedAt: number;
}>;
const MAX_WIRE_BYTES = 16_384;
const rejected = () => new Error("PASSKEY_ASSERTION_REJECTED");

function record(value: unknown, required: readonly string[], optional: readonly string[] = []): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value) ||
    ![Object.prototype, null].includes(Object.getPrototypeOf(value))) throw rejected();
  const keys = Reflect.ownKeys(value);
  if (keys.length > required.length + optional.length ||
    keys.some(key => typeof key !== "string" || ![...required, ...optional].includes(key)) ||
    required.some(key => !Object.hasOwn(value, key)) ||
    keys.some(key => !Object.hasOwn(Object.getOwnPropertyDescriptor(value, key)!, "value"))) throw rejected();
  return value as Record<string, unknown>;
}

function base64url(value: unknown, minimum: number, maximum: number): { text: string; bytes: Uint8Array<ArrayBuffer> } {
  if (typeof value !== "string" || value.length > Math.ceil(maximum * 4 / 3) ||
    !/^[A-Za-z0-9_-]+$/.test(value)) throw rejected();
  const decoded = Buffer.from(value, "base64url");
  if (decoded.length < minimum || decoded.length > maximum || decoded.toString("base64url") !== value) throw rejected();
  return { text: value, bytes: new Uint8Array(decoded) };
}
function integer(value: unknown, minimum = 0, maximum = Number.MAX_SAFE_INTEGER): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < minimum || value > maximum) throw rejected();
  return value;
}
function clock(expected: { startedAt: number; expiresAt: number }, now: number): void {
  integer(now, 1);
  integer(expected.startedAt, 1, Number.MAX_SAFE_INTEGER - 120);
  integer(expected.expiresAt, 1);
  if (expected.startedAt > now || expected.expiresAt <= now ||
    expected.expiresAt <= expected.startedAt || expected.expiresAt > expected.startedAt + 120) throw rejected();
}

/** Bound depth and duplicate keys before JSON.parse; no arrays are needed in this wire contract. */
function jsonObject(wire: string, maximum: number): Record<string, unknown> {
  if (typeof wire !== "string" || wire.length > maximum || !wire.isWellFormed() ||
    Buffer.byteLength(wire, "utf8") > maximum) throw rejected();
  let at = 0, nodes = 0;
  const space = () => { while (at < wire.length && /[ \t\r\n]/.test(wire[at])) at++; };
  const quoted = (): string => {
    if (wire[at] !== '"') throw rejected();
    const start = at++;
    while (at < wire.length) {
      if (wire[at] === "\\") { at += 2; continue; }
      if (wire[at++] === '"') return JSON.parse(wire.slice(start, at)) as string;
    }
    throw rejected();
  };
  const walk = (depth: number): void => {
    if (depth > 4 || ++nodes > 64) throw rejected();
    space();
    if (wire[at] === "{") {
      at++; space();
      const seen = new Set<string>();
      if (wire[at] === "}") { at++; return; }
      while (at < wire.length) {
        space(); const key = quoted(); space();
        if (seen.has(key) || wire[at++] !== ":") throw rejected();
        seen.add(key); walk(depth + 1); space();
        if (wire[at] === "}") { at++; return; }
        if (wire[at++] !== ",") throw rejected();
      }
      throw rejected();
    }
    if (wire[at] === "[") throw rejected();
    if (wire[at] === '"') { quoted(); return; }
    const start = at;
    while (at < wire.length && !/[,\s}]/.test(wire[at])) at++;
    if (at === start) throw rejected();
  };
  walk(0); space();
  if (at !== wire.length) throw rejected();
  const parsed: unknown = JSON.parse(wire);
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw rejected();
  return parsed as Record<string, unknown>;
}

function context(value: PasskeyExpectedContext, now: number): PasskeyExpectedContext {
  const expected = record(value, ["tenantId", "userId", "rpId", "origin", "challenge", "startedAt", "expiresAt", "credential"]);
  const tenantId = canonicalUuid(expected.tenantId), userId = canonicalUuid(expected.userId);
  const stored = record(expected.credential, ["tenantId", "userId", "id", "publicKey", "counter", "userHandle"]);
  if (canonicalUuid(stored.tenantId) !== tenantId || canonicalUuid(stored.userId) !== userId) throw rejected();
  if (typeof expected.rpId !== "string" || expected.rpId.length > 253 ||
    !/^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(expected.rpId) ||
    (!expected.rpId.includes(".") && expected.rpId !== "localhost") || /^[0-9.]+$/.test(expected.rpId) ||
    typeof expected.origin !== "string" || expected.origin.length > 512) throw rejected();
  const origin = new URL(expected.origin);
  if (origin.protocol !== "https:" || origin.origin !== expected.origin || origin.username || origin.password ||
    origin.hostname !== expected.rpId) throw rejected();
  const challenge = base64url(expected.challenge, 32, 64).text;
  const startedAt = integer(expected.startedAt, 1), expiresAt = integer(expected.expiresAt, 1);
  clock({ startedAt, expiresAt }, now);
  if (!(stored.publicKey instanceof Uint8Array) || stored.publicKey.byteLength < 1 || stored.publicKey.byteLength > 2048) throw rejected();
  // Snapshot all mutable caller-owned bytes before asynchronous verification.
  return { tenantId, userId, rpId: expected.rpId, origin: expected.origin, challenge, startedAt, expiresAt,
    credential: { tenantId, userId, id: base64url(stored.id, 1, 1023).text,
      publicKey: new Uint8Array(stored.publicKey), counter: integer(stored.counter, 0, 0xffff_ffff),
      userHandle: base64url(stored.userHandle, 1, 64).text } };
}

function assertion(value: unknown): AuthenticationResponseJSON {
  const item = record(value, ["id", "rawId", "type", "response", "clientExtensionResults"], ["authenticatorAttachment"]);
  const id = base64url(item.id, 1, 1023).text;
  if (base64url(item.rawId, 1, 1023).text !== id || item.type !== "public-key" ||
    (item.authenticatorAttachment !== undefined && item.authenticatorAttachment !== "platform" &&
      item.authenticatorAttachment !== "cross-platform")) throw rejected();
  // We request no client extensions. Never pass arbitrary nested extension input to the library.
  record(item.clientExtensionResults, []);
  const response = record(item.response, ["clientDataJSON", "authenticatorData", "signature"], ["userHandle"]);
  const clientDataJSON = base64url(response.clientDataJSON, 1, 4096);
  const clientText = new TextDecoder("utf-8", { fatal: true }).decode(clientDataJSON.bytes);
  const client = record(jsonObject(clientText, 4096), ["type", "challenge", "origin"], ["crossOrigin"]);
  if (client.type !== "webauthn.get" || typeof client.challenge !== "string" || typeof client.origin !== "string" ||
    (Object.hasOwn(client, "crossOrigin") && client.crossOrigin !== false)) throw rejected();
  // topOrigin is deliberately absent from the allowlist, including an empty topOrigin.
  const projected: AuthenticationResponseJSON = { id, rawId: id, type: "public-key", clientExtensionResults: {},
    response: { clientDataJSON: clientDataJSON.text,
      authenticatorData: base64url(response.authenticatorData, 37, 1024).text,
      signature: base64url(response.signature, 1, 1024).text } };
  if (response.userHandle !== undefined && response.userHandle !== null) {
    projected.response.userHandle = base64url(response.userHandle, 1, 64).text;
  }
  return projected;
}

/** Parse HTTP wire JSON without silently replacing duplicate security fields. */
export function parsePasskeyAssertion(wire: string): AuthenticationResponseJSON {
  try { return assertion(jsonObject(wire, MAX_WIRE_BYTES)); } catch { throw rejected(); }
}

/** The caller generates, stores, binds and consumes this unpredictable challenge exactly once. */
export async function generatePasskeyAuthenticationOptions(
  expected: PasskeyExpectedContext, now = Math.floor(Date.now() / 1000),
): Promise<PublicKeyCredentialRequestOptionsJSON> {
  try {
    const bound = context(expected, now);
    return await generateAuthenticationOptions({ rpID: bound.rpId,
      challenge: base64url(bound.challenge, 32, 64).bytes,
      allowCredentials: [{ id: bound.credential.id }], userVerification: "required",
      timeout: (bound.expiresAt - now) * 1000 });
  } catch { throw rejected(); }
}

/**
 * Cryptographic assertion verification only. No enrollment, registry authority,
 * single-use storage, counter CAS, authentication grant or account action is supplied.
 */
export async function verifyPasskeyAssertion(
  response: unknown, expected: PasskeyExpectedContext, now?: number,
): Promise<VerifiedPasskeyAssertion> {
  try {
    const checkedAt = now ?? Math.floor(Date.now() / 1000);
    const bound = context(expected, checkedAt), input = assertion(response);
    if (input.id !== bound.credential.id ||
      (input.response.userHandle !== undefined && input.response.userHandle !== bound.credential.userHandle)) throw rejected();
    const result = await verifyAuthenticationResponse({ response: input, expectedChallenge: bound.challenge,
      expectedOrigin: bound.origin, expectedRPID: bound.rpId, expectedType: "webauthn.get",
      requireUserVerification: true, credential: { id: bound.credential.id,
        publicKey: new Uint8Array(bound.credential.publicKey), counter: bound.credential.counter } });
    const finishedAt = now ?? Math.floor(Date.now() / 1000);
    clock(bound, finishedAt);
    if (!result.verified || !result.authenticationInfo.userVerified ||
      result.authenticationInfo.credentialID !== bound.credential.id) throw rejected();
    return Object.freeze({ credentialId: bound.credential.id,
      newCounter: integer(result.authenticationInfo.newCounter, 0, 0xffff_ffff),
      deviceType: result.authenticationInfo.credentialDeviceType,
      backedUp: result.authenticationInfo.credentialBackedUp, checkedAt: finishedAt });
  } catch {
    // Never propagate a library error containing challenge, origin or credential material.
    throw rejected();
  }
}
