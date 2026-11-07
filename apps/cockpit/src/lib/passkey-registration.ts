import { webcrypto } from "node:crypto";
import {
  generateRegistrationOptions, verifyRegistrationResponse,
  type PublicKeyCredentialCreationOptionsJSON, type RegistrationResponseJSON,
} from "@simplewebauthn/server";
import { decodeAttestationObject, decodeCredentialPublicKey, isoCBOR } from "@simplewebauthn/server/helpers";
import { canonicalUuid } from "./credential-action-contracts.ts";

/** Owner, opaque handle and challenge come exclusively from the trusted enrollment ticket/session. */
export type RegistrationExpectedContext = Readonly<{
  tenantId: string; userId: string; rpId: string; origin: string;
  challenge: string; userHandle: string; startedAt: number; expiresAt: number;
}>;
/** Candidate only: none attestation does not prove private-key possession. */
export type RegisteredPasskeyCandidate = Readonly<{
  credentialId: string; publicKey: Uint8Array; userHandle: string;
  counter: number; backupEligible: boolean; backedUp: boolean;
}>;
const rejected = () => new Error("PASSKEY_REGISTRATION_REJECTED");
const TRANSPORTS = ["ble", "cable", "hybrid", "internal", "nfc", "smart-card", "usb"];
function record(value: unknown, required: readonly string[], optional: readonly string[] = []): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value) ||
    ![Object.prototype, null].includes(Object.getPrototypeOf(value))) throw rejected();
  const keys = Reflect.ownKeys(value);
  if (keys.length > required.length + optional.length ||
    required.some(key => !Object.hasOwn(value, key)) ||
    keys.some(key => typeof key !== "string" || ![...required, ...optional].includes(key) ||
      !Object.hasOwn(Object.getOwnPropertyDescriptor(value, key)!, "value"))) throw rejected();
  return value as Record<string, unknown>;
}
function encoded(value: unknown, minimum: number, maximum: number): { text: string; bytes: Uint8Array<ArrayBuffer> } {
  if (typeof value !== "string" || value.length > Math.ceil(maximum * 4 / 3) || !/^[A-Za-z0-9_-]+$/.test(value)) throw rejected();
  const bytes = Buffer.from(value, "base64url");
  if (bytes.length < minimum || bytes.length > maximum || bytes.toString("base64url") !== value) throw rejected();
  return { text: value, bytes: new Uint8Array(bytes) };
}
function clock(bound: { startedAt: number; expiresAt: number }, now: number): void {
  if (![bound.startedAt, bound.expiresAt, now].every(value => Number.isSafeInteger(value) && value > 0) ||
    bound.startedAt > Number.MAX_SAFE_INTEGER - 120 || bound.startedAt > now ||
    bound.expiresAt <= now || bound.expiresAt <= bound.startedAt || bound.expiresAt > bound.startedAt + 120) throw rejected();
}
function context(value: RegistrationExpectedContext, now: number): RegistrationExpectedContext {
  const item = record(value, ["tenantId", "userId", "rpId", "origin", "challenge", "userHandle", "startedAt", "expiresAt"]);
  const tenantId = canonicalUuid(item.tenantId), userId = canonicalUuid(item.userId);
  if (typeof item.rpId !== "string" || item.rpId.length > 253 ||
    !/^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(item.rpId) ||
    (!item.rpId.includes(".") && item.rpId !== "localhost") || /^[0-9.]+$/.test(item.rpId) ||
    typeof item.origin !== "string" || item.origin.length > 512) throw rejected();
  const origin = new URL(item.origin);
  if (origin.protocol !== "https:" || origin.origin !== item.origin || origin.hostname !== item.rpId ||
    origin.username || origin.password) throw rejected();
  const bound = { tenantId, userId, rpId: item.rpId, origin: item.origin,
    challenge: encoded(item.challenge, 32, 32).text, userHandle: encoded(item.userHandle, 32, 32).text,
    startedAt: item.startedAt as number, expiresAt: item.expiresAt as number };
  clock(bound, now);
  return bound;
}

/** Strict bounded JSON with duplicate detection before allocation by JSON.parse. */
function jsonObject(wire: string, maximum: number): Record<string, unknown> {
  if (typeof wire !== "string" || wire.length > maximum || !wire.isWellFormed() ||
    Buffer.byteLength(wire, "utf8") > maximum) throw rejected();
  let at = 0, nodes = 0;
  const space = () => { while (at < wire.length && /[ \t\r\n]/.test(wire[at])) at++; };
  const quoted = () => {
    if (wire[at] !== '"') throw rejected();
    const start = at++;
    while (at < wire.length) {
      if (wire[at] === "\\") { at += 2; continue; }
      if (wire[at++] === '"') return JSON.parse(wire.slice(start, at)) as string;
    }
    throw rejected();
  };
  const walk = (depth: number): void => {
    if (depth > 4 || ++nodes > 128) throw rejected();
    space();
    if (wire[at] === "{") {
      at++; space(); const seen = new Set<string>();
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
    if (wire[at] === "[") {
      at++; space();
      if (wire[at] === "]") { at++; return; }
      while (at < wire.length) {
        walk(depth + 1); space();
        if (wire[at] === "]") { at++; return; }
        if (wire[at++] !== ",") throw rejected();
      }
      throw rejected();
    }
    if (wire[at] === '"') { quoted(); return; }
    const start = at;
    while (at < wire.length && !/[,\s}\]]/.test(wire[at])) at++;
    if (at === start) throw rejected();
  };
  walk(0); space();
  if (at !== wire.length) throw rejected();
  const parsed: unknown = JSON.parse(wire);
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw rejected();
  return parsed as Record<string, unknown>;
}

function registration(value: unknown): RegistrationResponseJSON {
  const item = record(value, ["id", "rawId", "type", "response", "clientExtensionResults"], ["authenticatorAttachment"]);
  const id = encoded(item.id, 1, 1023).text;
  if (encoded(item.rawId, 1, 1023).text !== id || item.type !== "public-key" ||
    (item.authenticatorAttachment !== undefined && !["platform", "cross-platform"].includes(item.authenticatorAttachment as string))) throw rejected();
  const extensions = record(item.clientExtensionResults, [], ["credProps"]);
  if (extensions.credProps !== undefined) {
    const properties = record(extensions.credProps, ["rk"]);
    if (properties.rk !== true) throw rejected();
  }
  const response = record(item.response, ["clientDataJSON", "attestationObject"],
    ["authenticatorData", "publicKey", "publicKeyAlgorithm", "transports"]);
  const clientDataJSON = encoded(response.clientDataJSON, 1, 4096);
  const client = record(jsonObject(new TextDecoder("utf-8", { fatal: true }).decode(clientDataJSON.bytes), 4096),
    ["type", "challenge", "origin"], ["crossOrigin"]);
  if (client.type !== "webauthn.create" || typeof client.challenge !== "string" || typeof client.origin !== "string" ||
    (Object.hasOwn(client, "crossOrigin") && client.crossOrigin !== false)) throw rejected();
  // No topOrigin is accepted, even when crossOrigin is omitted or false.
  const projected: RegistrationResponseJSON = { id, rawId: id, type: "public-key", clientExtensionResults: {},
    response: { clientDataJSON: clientDataJSON.text, attestationObject: encoded(response.attestationObject, 1, 4096).text } };
  if (extensions.credProps !== undefined) projected.clientExtensionResults = { credProps: { rk: true } };
  if (response.authenticatorData !== undefined) projected.response.authenticatorData = encoded(response.authenticatorData, 55, 2048).text;
  if (response.publicKey !== undefined) projected.response.publicKey = encoded(response.publicKey, 1, 1024).text;
  if (response.publicKeyAlgorithm !== undefined) {
    if (response.publicKeyAlgorithm !== -7) throw rejected();
    projected.response.publicKeyAlgorithm = -7;
  }
  if (response.transports !== undefined) {
    if (!Array.isArray(response.transports) || response.transports.length > TRANSPORTS.length ||
      response.transports.some(value => typeof value !== "string" || !TRANSPORTS.includes(value)) ||
      new Set(response.transports).size !== response.transports.length) throw rejected();
    projected.response.transports = [...response.transports];
  }
  return projected;
}

/** Library decoders only, constrained to a small none/EC2-P256 record before any attestation verifier. */
function noneAttestation(response: RegistrationResponseJSON) {
  const bytes = encoded(response.response.attestationObject, 1, 4096).bytes;
  const attestation = decodeAttestationObject(bytes);
  if (!(attestation instanceof Map) || attestation.size !== 3 ||
    !["fmt", "authData", "attStmt"].every(field => attestation.has(field)) ||
    attestation.get("fmt") !== "none" || !(attestation.get("attStmt") instanceof Map) ||
    attestation.get("attStmt").size !== 0) throw rejected();
  if (!Buffer.from(isoCBOR.encode(attestation)).equals(Buffer.from(bytes))) throw rejected();
  const authData: unknown = attestation.get("authData");
  if (!(authData instanceof Uint8Array) || authData.length < 56 || authData.length > 2048) throw rejected();
  // M1 requests no authenticator extensions. AT is mandatory; ED is excluded.
  if (!(authData[32] & 0x40) || (authData[32] & 0x80)) throw rejected();
  const idLength = (authData[53] << 8) | authData[54];
  if (idLength < 1 || idLength > 1023 || 55 + idLength >= authData.length ||
    Buffer.from(authData.slice(55, 55 + idLength)).toString("base64url") !== response.id) throw rejected();
  const publicKey = new Uint8Array(authData.slice(55 + idLength));
  if (publicKey.length > 256) throw rejected();
  const cose = decodeCredentialPublicKey(publicKey) as unknown as Map<number, number | Uint8Array>;
  if (!(cose instanceof Map) || cose.size !== 5 || ![1, 3, -1, -2, -3].every(field => cose.has(field)) ||
    cose.get(1) !== 2 || cose.get(3) !== -7 || cose.get(-1) !== 1 ||
    !Buffer.from(isoCBOR.encode(cose)).equals(Buffer.from(publicKey))) throw rejected();
  const x = cose.get(-2), y = cose.get(-3);
  if (!(x instanceof Uint8Array) || !(y instanceof Uint8Array) || x.length !== 32 || y.length !== 32) throw rejected();
  if (response.response.authenticatorData !== undefined &&
    !Buffer.from(encoded(response.response.authenticatorData, 55, 2048).bytes).equals(Buffer.from(authData))) throw rejected();
  return { authData, publicKey, x: Buffer.from(x).toString("base64url"), y: Buffer.from(y).toString("base64url") };
}

export function parsePasskeyRegistration(wire: string): RegistrationResponseJSON {
  try { return registration(jsonObject(wire, 16_384)); } catch { throw rejected(); }
}
export async function generatePasskeyRegistrationOptions(
  expected: RegistrationExpectedContext, now = Math.floor(Date.now() / 1000),
): Promise<PublicKeyCredentialCreationOptionsJSON> {
  try {
    const bound = context(expected, now);
    return await generateRegistrationOptions({ rpName: "Investalo", rpID: bound.rpId,
      userName: bound.userHandle, userDisplayName: "Investalo", userID: encoded(bound.userHandle, 32, 32).bytes,
      challenge: encoded(bound.challenge, 32, 32).bytes, timeout: (bound.expiresAt - now) * 1000,
      attestationType: "none", supportedAlgorithmIDs: [-7],
      authenticatorSelection: { residentKey: "required", userVerification: "required" } });
  } catch { throw rejected(); }
}
/**
 * No administrative authorization, single-use consume or global credential uniqueness is supplied.
 * With fmt=none there is no attestation signature. This result cannot authorize a sensitive action:
 * require a separate fresh challenge assertion proving private-key possession plus UV/UP.
 */
export async function verifyPasskeyRegistration(
  value: unknown, expected: RegistrationExpectedContext, now?: number,
): Promise<RegisteredPasskeyCandidate> {
  try {
    const bound = context(expected, now ?? Math.floor(Date.now() / 1000)), input = registration(value);
    const decoded = noneAttestation(input);
    // WebCrypto validates the actual EC point, which none attestation itself does not do.
    const key = await webcrypto.subtle.importKey("jwk", { kty: "EC", crv: "P-256",
      x: decoded.x, y: decoded.y, ext: true }, { name: "ECDSA", namedCurve: "P-256" }, true, ["verify"]);
    if (input.response.publicKey !== undefined &&
      !Buffer.from(await webcrypto.subtle.exportKey("spki", key)).equals(
        Buffer.from(encoded(input.response.publicKey, 1, 1024).bytes))) throw rejected();
    const result = await verifyRegistrationResponse({ response: input, expectedChallenge: bound.challenge,
      expectedOrigin: bound.origin, expectedRPID: bound.rpId, expectedType: "webauthn.create",
      requireUserPresence: true, requireUserVerification: true, supportedAlgorithmIDs: [-7] });
    clock(bound, now ?? Math.floor(Date.now() / 1000));
    if (!result.verified || !result.registrationInfo.userVerified || result.registrationInfo.fmt !== "none" ||
      result.registrationInfo.credential.id !== input.id ||
      !Buffer.from(result.registrationInfo.credential.publicKey).equals(Buffer.from(decoded.publicKey))) throw rejected();
    const counter = result.registrationInfo.credential.counter;
    if (!Number.isSafeInteger(counter) || counter < 0 || counter > 0xffff_ffff) throw rejected();
    return Object.freeze({ credentialId: input.id, publicKey: new Uint8Array(decoded.publicKey),
      userHandle: bound.userHandle, counter, backupEligible: result.registrationInfo.credentialDeviceType === "multiDevice",
      backedUp: result.registrationInfo.credentialBackedUp });
  } catch { throw rejected(); }
}
