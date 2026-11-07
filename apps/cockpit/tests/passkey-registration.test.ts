import assert from "node:assert/strict";
import { createHash, generateKeyPairSync, randomBytes, sign, type KeyObject } from "node:crypto";
import test from "node:test";
import { isoCBOR } from "@simplewebauthn/server/helpers";
import {
  generatePasskeyRegistrationOptions, parsePasskeyRegistration, verifyPasskeyRegistration,
  type RegistrationExpectedContext,
} from "../src/lib/passkey-registration.ts";
import { verifyPasskeyAssertion, type PasskeyExpectedContext } from "../src/lib/passkey-verifier.ts";

const NOW = 1_794_060_000;
const b64 = (bytes: Uint8Array) => Buffer.from(bytes).toString("base64url");
const hash = (value: string | Uint8Array) => createHash("sha256").update(value).digest();
function fixture() {
  const { publicKey, privateKey } = generateKeyPairSync("ec", { namedCurve: "prime256v1" });
  const jwk = publicKey.export({ format: "jwk" });
  const cose = new Map<number, number | Uint8Array>([
    [1, 2], [3, -7], [-1, 1], [-2, new Uint8Array(Buffer.from(jwk.x!, "base64url"))],
    [-3, new Uint8Array(Buffer.from(jwk.y!, "base64url"))],
  ]);
  const expected: RegistrationExpectedContext = {
    tenantId: "10000000-0000-0000-0000-000000000001",
    userId: "20000000-0000-0000-0000-000000000002",
    rpId: "cockpit.local.test", origin: "https://cockpit.local.test:8443",
    challenge: b64(randomBytes(32)), userHandle: b64(randomBytes(32)), startedAt: NOW - 1, expiresAt: NOW + 119,
  };
  return { expected, publicKey, privateKey, cose, id: randomBytes(32) };
}
function registration(f: ReturnType<typeof fixture>, options: {
  flags?: number; counter?: number; rpId?: string; client?: Record<string, unknown>; clientText?: string;
  cose?: Map<number, number | Uint8Array>; credentialId?: Uint8Array; fmt?: string;
  attStmt?: Map<string, number | string | Uint8Array>;
} = {}) {
  const clientData = Buffer.from(options.clientText ?? JSON.stringify({
    type: "webauthn.create", challenge: f.expected.challenge, origin: f.expected.origin, crossOrigin: false,
    ...options.client,
  }));
  const counter = Buffer.alloc(4), idLength = Buffer.alloc(2);
  counter.writeUInt32BE(options.counter ?? 0);
  const credentialId = options.credentialId ?? f.id;
  idLength.writeUInt16BE(credentialId.length);
  const authData = Buffer.concat([hash(options.rpId ?? f.expected.rpId), Buffer.from([options.flags ?? 0x45]),
    counter, Buffer.alloc(16), idLength, credentialId, isoCBOR.encode(options.cose ?? f.cose)]);
  const attestation = new Map<string, string | Uint8Array | Map<string, number | string | Uint8Array>>([
    ["fmt", options.fmt ?? "none"], ["authData", new Uint8Array(authData)], ["attStmt", options.attStmt ?? new Map()],
  ]);
  return { id: b64(credentialId), rawId: b64(credentialId), type: "public-key",
    authenticatorAttachment: "platform", clientExtensionResults: { credProps: { rk: true } },
    response: { clientDataJSON: b64(clientData), attestationObject: b64(isoCBOR.encode(attestation)) } };
}
async function reject(input: unknown, expected: RegistrationExpectedContext, now = NOW) {
  await assert.rejects(verifyPasskeyRegistration(input, expected, now), error => {
    assert.equal((error as Error).message, "PASSKEY_REGISTRATION_REJECTED");
    assert.equal((error as Error).cause, undefined);
    return true;
  });
}
function firstAssertion(expected: PasskeyExpectedContext, privateKey: KeyObject) {
  const client = Buffer.from(JSON.stringify({
    type: "webauthn.get", challenge: expected.challenge, origin: expected.origin, crossOrigin: false,
  }));
  const counter = Buffer.alloc(4); counter.writeUInt32BE(1);
  const authenticatorData = Buffer.concat([hash(expected.rpId), Buffer.from([0x05]), counter]);
  return { id: expected.credential.id, rawId: expected.credential.id, type: "public-key", clientExtensionResults: {},
    response: { clientDataJSON: b64(client), authenticatorData: b64(authenticatorData),
      signature: b64(sign("sha256", Buffer.concat([authenticatorData, hash(client)]), privateKey)),
      userHandle: expected.credential.userHandle } };
}

test("registration options require UV/discoverable key, exact ES256, none attestation and opaque 32-byte handle", async () => {
  const f = fixture(), options = await generatePasskeyRegistrationOptions(f.expected, NOW);
  assert.deepEqual(options.rp, { name: "Investalo", id: f.expected.rpId });
  assert.equal(options.challenge, f.expected.challenge);
  assert.equal(options.user.id, f.expected.userHandle);
  assert.equal(Buffer.from(options.user.id, "base64url").length, 32);
  assert.equal(options.timeout, 119_000);
  assert.equal(options.attestation, "none");
  assert.deepEqual(options.pubKeyCredParams, [{ alg: -7, type: "public-key" }]);
  assert.deepEqual(options.authenticatorSelection, { residentKey: "required", requireResidentKey: true, userVerification: "required" });
  assert.deepEqual(options.extensions, { credProps: true }); // v14 requests this automatically
});

test("real EC2-P256 COSE key in none attestation returns only a pending persistable candidate", async () => {
  const f = fixture(), input = registration(f);
  const candidate = await verifyPasskeyRegistration(parsePasskeyRegistration(JSON.stringify(input)), f.expected, NOW);
  assert.deepEqual(Object.keys(candidate).sort(), ["backedUp", "backupEligible", "counter", "credentialId", "publicKey", "userHandle"]);
  assert.equal(candidate.credentialId, input.id);
  assert.deepEqual(candidate.publicKey, isoCBOR.encode(f.cose));
  assert.equal(candidate.userHandle, f.expected.userHandle);
  assert.equal(candidate.counter, 0);
  assert.equal(candidate.backupEligible, false);
  assert.equal(candidate.backedUp, false);
  assert(Object.isFrozen(candidate));
});

test("none attestation has no possession signature; a separate fresh assertion must prove the new private key", async () => {
  const f = fixture(), candidate = await verifyPasskeyRegistration(registration(f), f.expected, NOW);
  const expected: PasskeyExpectedContext = { tenantId: f.expected.tenantId, userId: f.expected.userId,
    rpId: f.expected.rpId, origin: f.expected.origin, challenge: b64(randomBytes(32)),
    startedAt: NOW, expiresAt: NOW + 120, credential: { tenantId: f.expected.tenantId, userId: f.expected.userId,
      id: candidate.credentialId, publicKey: candidate.publicKey, counter: candidate.counter, userHandle: candidate.userHandle } };
  assert.notEqual(expected.challenge, f.expected.challenge);
  assert.equal((await verifyPasskeyAssertion(firstAssertion(expected, f.privateKey), expected, NOW)).newCounter, 1);
  await assert.rejects(verifyPasskeyAssertion(firstAssertion(expected, fixture().privateKey), expected, NOW),
    { message: "PASSKEY_ASSERTION_REJECTED" });
});

test("zero-counter synced registrations retain backup eligibility/state without issuing authentication claims", async () => {
  const f = fixture(), candidate = await verifyPasskeyRegistration(registration(f, { flags: 0x5d }), f.expected, NOW);
  assert.equal(candidate.counter, 0);
  assert.equal(candidate.backupEligible, true);
  assert.equal(candidate.backedUp, true);
  await reject(registration(f, { flags: 0x55 }), f.expected); // backed up without eligible
});

test("registration requires independent UP and UV flags and attested credential data", async () => {
  const f = fixture();
  for (const flags of [0x40, 0x41, 0x44, 0x05]) await reject(registration(f, { flags }), f.expected);
});

test("wrong registration challenge, origin, RP-ID hash and operation are rejected", async () => {
  const f = fixture();
  await reject(registration(f, { client: { challenge: b64(randomBytes(32)) } }), f.expected);
  await reject(registration(f, { client: { origin: "https://foreign.local.test:8443" } }), f.expected);
  await reject(registration(f, { client: { type: "webauthn.get" } }), f.expected);
  await reject(registration(f, { rpId: "foreign.local.test" }), f.expected);
});

test("every topOrigin and true/nonboolean crossOrigin fails explicitly before the library", async () => {
  const f = fixture();
  for (const client of [
    { crossOrigin: true }, { crossOrigin: true, topOrigin: f.expected.origin },
    { crossOrigin: false, topOrigin: f.expected.origin }, { topOrigin: "" },
    { crossOrigin: "false" }, { crossOrigin: null },
  ]) await reject(registration(f, { client }), f.expected);
});

test("credential ID must be canonical and agree across id/rawId and authenticator data", async () => {
  const f = fixture(), input = registration(f), foreign = b64(randomBytes(32));
  await reject({ ...input, rawId: foreign }, f.expected);
  await reject({ ...input, id: foreign, rawId: foreign }, f.expected);
  await reject({ ...input, id: input.id + "=", rawId: input.rawId + "=" }, f.expected);
  await reject(registration(f, { credentialId: randomBytes(1024) }), f.expected);
  await reject({ ...input, id: "Zh", rawId: "Zh" }, f.expected);
  const maximum = registration(f, { credentialId: randomBytes(1023) });
  assert.equal((await verifyPasskeyRegistration(maximum, f.expected, NOW)).credentialId, maximum.id);
});

test("only none attestation and an empty attestation statement are accepted", async () => {
  const f = fixture();
  await reject(registration(f, { fmt: "packed" }), f.expected);
  await reject(registration(f, { fmt: "unknown" }), f.expected);
  await reject(registration(f, { attStmt: new Map([["sig", randomBytes(32)]]) }), f.expected);
});

test("ES256 key material is strictly EC2/P256 with two valid 32-byte curve coordinates", async () => {
  const f = fixture();
  for (const [field, value] of [[3, -8], [1, 3], [-1, 2], [-2, randomBytes(31)], [-3, randomBytes(33)]] as const) {
    const cose = new Map(f.cose); cose.set(field, value);
    await reject(registration(f, { cose }), f.expected);
  }
  const invalidPoint = new Map(f.cose); invalidPoint.set(-2, new Uint8Array(32)); invalidPoint.set(-3, new Uint8Array(32));
  await reject(registration(f, { cose: invalidPoint }), f.expected);
  const additional = new Map(f.cose); additional.set(99, 1);
  await reject(registration(f, { cose: additional }), f.expected);
});

test("native optional SPKI/authenticator data/algorithm are bounded and checked against authoritative COSE", async () => {
  const f = fixture(), input = registration(f);
  const raw = isoCBOR.decodeFirst(Buffer.from(input.response.attestationObject, "base64url")) as Map<string, unknown>;
  const response = { ...input.response, authenticatorData: b64(raw.get("authData") as Uint8Array),
    publicKey: b64(f.publicKey.export({ format: "der", type: "spki" })), publicKeyAlgorithm: -7, transports: ["internal", "hybrid"] };
  assert.equal((await verifyPasskeyRegistration(parsePasskeyRegistration(JSON.stringify({ ...input, response })), f.expected, NOW)).credentialId, input.id);
  await reject({ ...input, response: { ...response, publicKey: b64(fixture().publicKey.export({ format: "der", type: "spki" })) } }, f.expected);
  await reject({ ...input, response: { ...response, authenticatorData: b64(randomBytes(100)) } }, f.expected);
  await reject({ ...input, response: { ...response, publicKeyAlgorithm: -257 } }, f.expected);
  await reject({ ...input, response: { ...response, transports: ["future-unknown"] } }, f.expected);
  await reject({ ...input, response: { ...response, transports: ["internal", "internal"] } }, f.expected);
});

test("credProps.rk false fails requested discoverability while absent credProps has no invented proof", async () => {
  const f = fixture(), input = registration(f);
  assert.equal((await verifyPasskeyRegistration({ ...input, clientExtensionResults: {} }, f.expected, NOW)).credentialId, input.id);
  for (const extensions of [{ credProps: { rk: false } }, { credProps: { rk: "true" } },
    { credProps: { rk: true, private: true } }, { unknown: true }]) {
    await reject({ ...input, clientExtensionResults: extensions }, f.expected);
  }
});

test("trusted owner IDs, handle, challenge and host context reject coercion and noncanonical forms", async () => {
  const f = fixture(), input = registration(f);
  for (const change of [
    { tenantId: "foreign-subject" }, { userId: true }, { challenge: b64(randomBytes(31)) },
    { challenge: b64(randomBytes(33)) }, { userHandle: b64(randomBytes(31)) }, { userHandle: b64(randomBytes(33)) },
    { userHandle: f.expected.userHandle + "=" }, { rpId: "local.test" }, { origin: f.expected.origin + "/" },
    { origin: "http://cockpit.local.test:8443" }, { origin: "https://password:secret@cockpit.local.test:8443" },
  ]) await reject(input, { ...f.expected, ...change } as RegistrationExpectedContext);
});

test("lifetime is bounded to 120 seconds with strict start and expiry boundaries", async () => {
  const f = fixture(), input = registration(f);
  for (const change of [
    { startedAt: NOW + 1 }, { startedAt: NaN }, { expiresAt: Infinity },
    { expiresAt: f.expected.startedAt + 121 }, { expiresAt: NOW },
  ]) await reject(input, { ...f.expected, ...change });
  await reject(input, f.expected, f.expected.expiresAt);
  await assert.rejects(generatePasskeyRegistrationOptions(f.expected, f.expected.expiresAt),
    { message: "PASSKEY_REGISTRATION_REJECTED" });
});

test("duplicate and escaped duplicate JSON keys are rejected in wire and client data", async () => {
  const f = fixture(), input = registration(f), wire = JSON.stringify(input);
  assert.throws(() => parsePasskeyRegistration(wire.replace('{"id":', `{"id":"${input.id}","id":`)),
    { message: "PASSKEY_REGISTRATION_REJECTED" });
  assert.throws(() => parsePasskeyRegistration(wire.replace('"rawId":', `"raw\\u0049d":"${input.rawId}","rawId":`)),
    { message: "PASSKEY_REGISTRATION_REJECTED" });
  const clientText = `{"type":"webauthn.create","challenge":"${f.expected.challenge}","origin":"${f.expected.origin}","ori\\u0067in":"${f.expected.origin}"}`;
  await reject(registration(f, { clientText }), f.expected);
});

test("oversized, malformed, nested, unknown or accessor-bearing browser input fails statically", async () => {
  const f = fixture(), input = registration(f);
  for (const wire of [" ".repeat(16_385), "null", "[]", "{", '{"a":{"b":{"c":{"d":{"e":{}}}}}}']) {
    assert.throws(() => parsePasskeyRegistration(wire), { message: "PASSKEY_REGISTRATION_REJECTED" });
  }
  await reject({ ...input, private: "never-log-this" }, f.expected);
  await reject({ ...input, response: { ...input.response, secret: true } }, f.expected);
  for (const response of [
    { ...input.response, attestationObject: "*" },
    { ...input.response, attestationObject: b64(randomBytes(4097)) },
    { ...input.response, clientDataJSON: b64(Buffer.from([0xc3, 0x28])) },
    { ...input.response, clientDataJSON: b64(randomBytes(4097)) },
  ]) await reject({ ...input, response }, f.expected);
  let touched = false; const accessor = { ...input };
  Object.defineProperty(accessor, "id", { get: () => { touched = true; throw new Error("never-log-this"); } });
  await reject(accessor, f.expected);
  assert.equal(touched, false);
});

test("malformed CBOR, trailing attestation bytes and unexpected authData extensions are rejected", async () => {
  const f = fixture(), input = registration(f);
  await reject({ ...input, response: { ...input.response, attestationObject: b64(Buffer.from([0xa3])) } }, f.expected);
  await reject({ ...input, response: { ...input.response,
    attestationObject: b64(Buffer.concat([Buffer.from(input.response.attestationObject, "base64url"), Buffer.from([0])])) } }, f.expected);
  await reject(registration(f, { flags: 0xc5 }), f.expected);
});

test("mutable browser strings are projected before asynchronous validation and metadata services stay offline", async () => {
  const f = fixture(), input = registration(f), originalFetch = globalThis.fetch;
  globalThis.fetch = async () => { throw new Error("NETWORK_NOT_ALLOWED"); };
  try {
    const promise = verifyPasskeyRegistration(input, f.expected, NOW);
    input.id = b64(randomBytes(32));
    input.response.attestationObject = "corrupt";
    assert.equal((await promise).credentialId, b64(f.id));
  } finally { globalThis.fetch = originalFetch; }
});
