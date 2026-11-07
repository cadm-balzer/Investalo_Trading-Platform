import assert from "node:assert/strict";
import { createHash, generateKeyPairSync, randomBytes, sign, type KeyObject } from "node:crypto";
import test from "node:test";
import {
  generatePasskeyAuthenticationOptions,
  parsePasskeyAssertion,
  verifyPasskeyAssertion,
  type PasskeyExpectedContext,
} from "../src/lib/passkey-verifier.ts";

const NOW = 1_794_050_000;
const TENANT = "10000000-0000-0000-0000-000000000001";
const USER = "20000000-0000-0000-0000-000000000002";
const FOREIGN = "30000000-0000-0000-0000-000000000003";
const b64 = (bytes: Uint8Array) => Buffer.from(bytes).toString("base64url");
const hash = (input: string | Uint8Array) => createHash("sha256").update(input).digest();
function fixture() {
  const { privateKey, publicKey } = generateKeyPairSync("ec", { namedCurve: "prime256v1" });
  const jwk = publicKey.export({ format: "jwk" });
  // COSE EC2 / ES256: {1:2, 3:-7, -1:1, -2:x, -3:y}.
  // Signing and verification remain in Node/OpenSSL and SimpleWebAuthn.
  const cose = Buffer.concat([Buffer.from([0xa5, 0x01, 0x02, 0x03, 0x26, 0x20, 0x01, 0x21, 0x58, 0x20]),
    Buffer.from(jwk.x!, "base64url"), Buffer.from([0x22, 0x58, 0x20]), Buffer.from(jwk.y!, "base64url")]);
  const expected: PasskeyExpectedContext = {
    tenantId: TENANT, userId: USER, rpId: "cockpit.local.test", origin: "https://cockpit.local.test:8443",
    challenge: b64(randomBytes(32)), startedAt: NOW - 2, expiresAt: NOW + 118,
    credential: { tenantId: TENANT, userId: USER, id: b64(randomBytes(32)), publicKey: new Uint8Array(cose),
      counter: 3, userHandle: b64(randomBytes(32)) },
  };
  return { privateKey, expected };
}
function assertion(expected: PasskeyExpectedContext, key: KeyObject, overrides: {
  client?: Record<string, unknown>; clientText?: string; rpId?: string; flags?: number; counter?: number;
} = {}) {
  const clientData = Buffer.from(overrides.clientText ?? JSON.stringify({
    type: "webauthn.get", challenge: expected.challenge, origin: expected.origin, crossOrigin: false,
    ...overrides.client,
  }), "utf8");
  const counter = Buffer.alloc(4);
  counter.writeUInt32BE(overrides.counter ?? 4);
  const authenticatorData = Buffer.concat([hash(overrides.rpId ?? expected.rpId),
    Buffer.from([overrides.flags ?? 0x05]), counter]);
  const signature = sign("sha256", Buffer.concat([authenticatorData, hash(clientData)]), key);
  return {
    id: expected.credential.id, rawId: expected.credential.id, type: "public-key",
    authenticatorAttachment: "platform", clientExtensionResults: {},
    response: { clientDataJSON: b64(clientData), authenticatorData: b64(authenticatorData),
      signature: b64(signature), userHandle: expected.credential.userHandle },
  };
}
async function rejected(response: unknown, expected: PasskeyExpectedContext, now = NOW) {
  await assert.rejects(verifyPasskeyAssertion(response, expected, now), error => {
    assert.equal((error as Error).message, "PASSKEY_ASSERTION_REJECTED");
    assert.equal((error as Error).cause, undefined);
    return true;
  });
}

test("authentication options preserve exact challenge, allow only the bound credential and require UV", async () => {
  const { expected } = fixture();
  const options = await generatePasskeyAuthenticationOptions(expected, NOW);
  assert.equal(options.challenge, expected.challenge);
  assert.equal(options.rpId, expected.rpId);
  assert.equal(options.userVerification, "required");
  assert.equal(options.timeout, 118_000);
  assert.deepEqual(options.allowCredentials, [{ id: expected.credential.id, type: "public-key" }]);
});

test("real EC-P256 COSE key and DER assertion signature produce only the public checked result", async () => {
  const { expected, privateKey } = fixture();
  const input = assertion(expected, privateKey);
  const verified = await verifyPasskeyAssertion(parsePasskeyAssertion(JSON.stringify(input)), expected, NOW);
  assert.deepEqual(verified, { credentialId: expected.credential.id, newCounter: 4,
    deviceType: "singleDevice", backedUp: false, checkedAt: NOW });
  assert(Object.isFrozen(verified));
});

test("a synced backed-up passkey may legitimately keep a zero counter", async () => {
  const { expected, privateKey } = fixture();
  const bound = { ...expected, credential: { ...expected.credential, counter: 0 } };
  const verified = await verifyPasskeyAssertion(assertion(bound, privateKey, { flags: 0x1d, counter: 0 }), bound, NOW);
  assert.deepEqual(verified, { credentialId: bound.credential.id, newCounter: 0,
    deviceType: "multiDevice", backedUp: true, checkedAt: NOW });
});

test("validly signed wrong challenge and origin do not authenticate", async () => {
  const { expected, privateKey } = fixture();
  await rejected(assertion(expected, privateKey, { client: { challenge: b64(randomBytes(32)) } }), expected);
  await rejected(assertion(expected, privateKey, { client: { origin: "https://foreign.local.test:8443" } }), expected);
  await rejected(assertion(expected, privateKey, { client: { type: "webauthn.create" } }), expected);
});

test("validly signed foreign RP-ID hash and wrong signing key do not authenticate", async () => {
  const { expected, privateKey } = fixture();
  await rejected(assertion(expected, privateKey, { rpId: "foreign.local.test" }), expected);
  await rejected(assertion(expected, fixture().privateKey), expected);
  const input = assertion(expected, privateKey);
  const bytes = Buffer.from(input.response.signature, "base64url");
  bytes[bytes.length - 1] ^= 1;
  await rejected({ ...input, response: { ...input.response, signature: b64(bytes) } }, expected);
});

test("both UP and UV are independently required in signed authenticator data", async () => {
  const { expected, privateKey } = fixture();
  for (const flags of [0, 1, 4]) await rejected(assertion(expected, privateKey, { flags }), expected);
});

test("library counter verification rejects repeated, decreasing and zero-after-nonzero assertions", async () => {
  const { expected, privateKey } = fixture();
  for (const counter of [0, 2, 3]) await rejected(assertion(expected, privateKey, { counter }), expected);
});

test("inconsistent backup flags are rejected even with a valid signature", async () => {
  const { expected, privateKey } = fixture();
  await rejected(assertion(expected, privateKey, { flags: 0x15 }), expected); // BS without BE
});

test("cross-origin assertions without topOrigin and any topOrigin are explicitly rejected", async () => {
  const { expected, privateKey } = fixture();
  for (const client of [
    { crossOrigin: true }, { crossOrigin: true, topOrigin: expected.origin },
    { crossOrigin: false, topOrigin: expected.origin }, { topOrigin: "" },
    { crossOrigin: "false" }, { crossOrigin: null },
  ]) await rejected(assertion(expected, privateKey, { client }), expected);
});

test("response id cannot select another key and rawId must match canonically", async () => {
  const { expected, privateKey } = fixture(), input = assertion(expected, privateKey);
  await rejected({ ...input, id: b64(randomBytes(32)), rawId: b64(randomBytes(32)) }, expected);
  const foreign = b64(randomBytes(32));
  await rejected({ ...input, id: foreign, rawId: foreign }, expected);
  await rejected({ ...input, rawId: expected.credential.id + "=" }, expected);
  await rejected({ ...input, id: expected.credential.id + "=", rawId: expected.credential.id + "=" }, expected);
  await rejected({ ...input, id: "Zh", rawId: "Zh" }, expected); // nonzero discarded padding bits
});

test("userHandle is bound when returned; absent or null handle is allowed for a bound non-discoverable credential", async () => {
  const { expected, privateKey } = fixture(), input = assertion(expected, privateKey);
  await rejected({ ...input, response: { ...input.response, userHandle: b64(randomBytes(32)) } }, expected);
  await rejected({ ...input, response: { ...input.response, userHandle: "" } }, expected);
  await rejected({ ...input, response: { ...input.response, userHandle: true } }, expected);
  const { userHandle: _unused, ...withoutHandle } = input.response;
  assert.equal((await verifyPasskeyAssertion({ ...input, response: withoutHandle }, expected, NOW)).newCounter, 4);
  assert.equal((await verifyPasskeyAssertion({ ...input, response: { ...input.response, userHandle: null } }, expected, NOW)).newCounter, 4);
});

test("registry credential owner must match both expected tenant and user", async () => {
  const { expected, privateKey } = fixture(), input = assertion(expected, privateKey);
  await rejected(input, { ...expected, credential: { ...expected.credential, tenantId: FOREIGN } });
  await rejected(input, { ...expected, credential: { ...expected.credential, userId: FOREIGN } });
  await rejected(input, { ...expected, tenantId: expected.tenantId.toUpperCase().replace("1", "A") });
});

test("challenge lifetime cannot exceed 120 seconds or start in the future and expires exactly at deadline", async () => {
  const { expected, privateKey } = fixture(), input = assertion(expected, privateKey);
  for (const bound of [
    { ...expected, startedAt: NOW + 1 }, { ...expected, expiresAt: expected.startedAt + 121 },
    { ...expected, expiresAt: NOW }, { ...expected, expiresAt: expected.startedAt },
    { ...expected, startedAt: NaN }, { ...expected, expiresAt: Infinity },
  ]) await rejected(input, bound);
  await rejected(input, expected, expected.expiresAt);
  await assert.rejects(generatePasskeyAuthenticationOptions(expected, expected.expiresAt), { message: "PASSKEY_ASSERTION_REJECTED" });
  assert.equal((await verifyPasskeyAssertion(input, expected, expected.expiresAt - 1)).checkedAt, expected.expiresAt - 1);
});

test("trusted challenge, credential key, handle and counter have explicit byte/integer bounds", async () => {
  const { expected, privateKey } = fixture(), input = assertion(expected, privateKey);
  for (const change of [
    { challenge: b64(randomBytes(31)) }, { challenge: b64(randomBytes(65)) }, { challenge: expected.challenge + "=" },
  ]) await rejected(input, { ...expected, ...change });
  for (const change of [
    { publicKey: new Uint8Array() }, { publicKey: new Uint8Array(2049) },
    { counter: -1 }, { counter: 1.5 }, { counter: 0x1_0000_0000 },
    { userHandle: b64(randomBytes(65)) }, { id: b64(randomBytes(1025)) },
  ]) await rejected(input, { ...expected, credential: { ...expected.credential, ...change } });
});

test("RP configuration is a single canonical HTTPS origin scoped to its trusted RP-ID", async () => {
  const { expected, privateKey } = fixture(), input = assertion(expected, privateKey);
  for (const change of [
    { origin: "http://cockpit.local.test:8443" }, { origin: expected.origin + "/" },
    { origin: "https://user:password@cockpit.local.test:8443" }, { origin: expected.origin + "?q=x" },
    { origin: "https://foreign.local.test" }, { rpId: "COCKPIT.local.test" }, { rpId: "local.test:8443" },
    { rpId: "local.test" }, // A parent-domain RP is excluded by the platform's exact-host configuration.
  ]) await rejected(input, { ...expected, ...change });
});

test("wire parser rejects duplicate fields including escaped duplicate keys in signed clientDataJSON", async () => {
  const { expected, privateKey } = fixture(), input = assertion(expected, privateKey);
  const wire = JSON.stringify(input);
  for (const duplicate of [
    wire.replace('{"id":', `{"id":"${input.id}","id":`),
    wire.replace('"rawId":', `"raw\\u0049d":"${input.rawId}","rawId":`),
    wire.replace('"signature":', `"signature":"${input.response.signature}","signature":`),
  ]) assert.throws(() => parsePasskeyAssertion(duplicate), { message: "PASSKEY_ASSERTION_REJECTED" });
  const clientText = `{"type":"webauthn.get","challenge":"${expected.challenge}","origin":"${expected.origin}","ori\\u0067in":"${expected.origin}"}`;
  await rejected(assertion(expected, privateKey, { clientText }), expected);
});

test("bounded wire/depth, malformed JSON/base64 and malformed UTF-8 all fail with static errors", async () => {
  const { expected, privateKey } = fixture(), input = assertion(expected, privateKey);
  for (const wire of [
    " ".repeat(16_385), "{", "null", "[]", '{"a":{"b":{"c":{"d":{"e":{}}}}}}',
    JSON.stringify(input).slice(0, -1), JSON.stringify({ ...input, unknown: "private-sentinel" }),
  ]) assert.throws(() => parsePasskeyAssertion(wire), { message: "PASSKEY_ASSERTION_REJECTED" });
  for (const change of [
    { clientDataJSON: b64(Buffer.from([0xc3, 0x28])) }, { clientDataJSON: b64(Buffer.alloc(4097, 32)) },
    { authenticatorData: b64(Buffer.alloc(36)) }, { authenticatorData: b64(Buffer.alloc(1025)) },
    { signature: "*" }, { signature: b64(Buffer.alloc(1025)) },
  ]) await rejected({ ...input, response: { ...input.response, ...change } }, expected);
});

test("response projection rejects private/unknown properties, nesting and getters without invoking them", async () => {
  const { expected, privateKey } = fixture(), input = assertion(expected, privateKey);
  await rejected({ ...input, privateKey: "never-logged" }, expected);
  await rejected({ ...input, clientExtensionResults: { deep: { value: "never-logged" } } }, expected);
  await rejected({ ...input, type: "password" }, expected);
  await rejected({ ...input, response: { ...input.response, unknown: true } }, expected);
  const getter = { ...input };
  let touched = false;
  Object.defineProperty(getter, "id", { enumerable: true, get: () => { touched = true; throw new Error("secret"); } });
  await rejected(getter, expected);
  assert.equal(touched, false);
});

test("mutable trusted key and response inputs are snapshotted before asynchronous signature verification", async () => {
  const { expected, privateKey } = fixture(), input = assertion(expected, privateKey);
  const pending = verifyPasskeyAssertion(input, expected, NOW);
  expected.credential.publicKey.fill(0);
  input.response.signature = "corrupt";
  input.id = b64(randomBytes(32));
  assert.equal((await pending).credentialId, expected.credential.id);
});
