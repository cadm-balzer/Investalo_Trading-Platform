import test from "node:test";
import assert from "node:assert/strict";
import { jwtVerify } from "jose";
import {
  createPasskeyCredentialActionToken, parsePasskeyCredentialAuthorization,
  PASSKEY_CREDENTIAL_AUDIENCE, PASSKEY_CREDENTIAL_KIND,
  type PasskeyCredentialAuthorization, type PasskeyCredentialContext,
} from "../src/lib/passkey-credential-token.ts";
import { CREDENTIAL_ACTION_TARGETS } from "../src/lib/credential-action-token.ts";
import { hash, id, key, now, signing } from "./fixtures/passkey-credential-fixture.ts";

const receipt = (input = signing()) => input.authorization as PasskeyCredentialAuthorization;
const rejection = /PASSKEY_CREDENTIAL_TOKEN_REJECTED/;
for (const action of ["register", "replace", "revoke"] as const) {
  test(`passkey contract signs ${action} with old OIDC time and separate fresh proof`, async () => {
    const input = signing(action), source = receipt(input);
    const token = await createPasskeyCredentialActionToken(input);
    const { payload, protectedHeader } = await jwtVerify(token, key, {
      audience: PASSKEY_CREDENTIAL_AUDIENCE, issuer: "investalo-bff", algorithms: ["HS256"],
      currentDate: new Date(now * 1000),
    });
    assert.deepEqual(protectedHeader, { alg: "HS256", typ: "JWT" });
    assert.equal(payload.authorization_kind, PASSKEY_CREDENTIAL_KIND);
    assert.equal(payload.oidc_auth_time, now - 3600);
    assert.equal(payload.passkey_checked_at, now - 2);
    assert.equal(payload.exp, now + 60);
    assert.equal(payload.htm, "POST"); assert.equal(payload.htu, CREDENTIAL_ACTION_TARGETS[action]);
    assert.deepEqual(payload.target, source.target);
    assert.equal(payload.metadata_sha256, source.metadata_sha256);
    assert.equal(payload.body_sha256, hash(input.body));
    assert.equal(payload.oidc_amr, undefined);
    assert.ok(!JSON.stringify(payload).includes("SYNTHETIC") && !JSON.stringify(payload).includes("synthetic-päß"));
    await assert.rejects(jwtVerify(token, key, { audience: "investalo-credentials",
      currentDate: new Date(now * 1000) }));
  });
}
test("bounded assertion cannot outlive durable authorization or original session", async () => {
  const input = signing();
  const short = { ...receipt(input), expires_at: now + 4, session_expires_at: now + 4 };
  const token = await createPasskeyCredentialActionToken({ ...input, authorization: short,
    context: { ...input.context, sessionExpiresAt: now + 4 } });
  assert.equal((await jwtVerify(token, key, { currentDate: new Date(now * 1000) })).payload.exp, now + 4);
});
test("receipt and target snapshot are immutable data properties", () => {
  const input = signing("replace");
  const parsed = parsePasskeyCredentialAuthorization(input.authorization, input.context, input.body, now);
  assert.ok(Object.isFrozen(parsed) && Object.isFrozen(parsed.target));
  assert.throws(() => { (parsed.target as { expected_revision: number }).expected_revision = 99; });
  const accessor = { ...receipt(input) };
  Object.defineProperty(accessor, "subject", { get: () => "SYNTHETIC-SECRET", enumerable: true });
  assert.throws(() => parsePasskeyCredentialAuthorization(accessor, input.context, input.body, now), rejection);
});
for (const [name, patch] of [
  ["purpose", { kind: "passkey-proof-only/1" }],
  ["purpose ID aliases proof", { authorization_id: id(16) }],
  ["purpose ID aliases grant", { authorization_id: id(17) }],
  ["grant aliases proof", { grant_id: id(16) }],
  ["uppercase UUID", { proof_id: "ABCDEFAB-ABCD-ABCD-ABCD-ABCDEFABCDEF" }],
  ["wrong tenant", { tenant_id: id(99) }],
  ["wrong user", { user_id: id(99) }],
  ["wrong subject", { subject: "other-user" }],
  ["wrong epoch", { auth_epoch: 3 }],
  ["invented OIDC time", { oidc_auth_time: now - 2 }],
  ["wrong issuer", { oidc_issuer: "https://other.fixture.invalid" }],
  ["wrong origin", { origin: "https://cockpit.fixture.invalid" }],
  ["wrong RP", { rp_id: "other.fixture.invalid" }],
  ["wrong session", { session_binding: "d".repeat(64) }],
  ["extended session", { session_expires_at: now + 201 }],
  ["unverified initial factor", { passkey_version: 1 }],
  ["unsafe factor version", { passkey_version: Number.MAX_SAFE_INTEGER + 1 }],
  ["boolean version", { passkey_version: true }],
  ["unsafe hash", { metadata_sha256: "C".repeat(64) }],
  ["wrong body hash", { body_sha256: "a".repeat(64) }],
  ["old step", { prepared_at: now - 301 }],
  ["step after proof", { prepared_at: now - 1 }],
  ["stale proof", { checked_at: now - 121, prepared_at: now - 130 }],
  ["future proof", { checked_at: now + 1, authorized_at: now + 1 }],
  ["authorization before proof", { authorized_at: now - 3 }],
  ["future authorization", { authorized_at: now + 1 }],
  ["expired authority", { expires_at: now }],
  ["authority beyond proof", { expires_at: now + 119 }],
  ["authority beyond session", { expires_at: now + 201 }],
  ["zero proof time", { checked_at: 0 }],
  ["private field", { public_key: "SYNTHETIC-PRIVATE-FIELD" }],
] as const) {
  test(`receipt rejects ${name}`, async () => {
    const input = signing();
    await assert.rejects(createPasskeyCredentialActionToken({ ...input,
      authorization: { ...receipt(input), ...patch } }), rejection);
  });
}
test("proof-only public confirmation and007 internal grant cannot issue credentials", async () => {
  const input = signing();
  for (const authorization of [
    { status: "verified", execution_enabled: false, action: "register", platform_account_id: id(13) },
    { ...receipt(input), kind: undefined, execution_enabled: false },
    { ...receipt(input), kind: undefined },
  ]) await assert.rejects(createPasskeyCredentialActionToken({ ...input, authorization }), rejection);
});
for (const origin of ["http://cockpit.fixture.invalid", "https://cockpit.fixture.invalid/",
  "https://cockpit.fixture.invalid:443", "https://user@cockpit.fixture.invalid",
  "https://127.0.0.1", "https://cockpit.fixture.invalid/path",
  "https://Cockpit.fixture.invalid", "https://cockpit.fixture.invalid#secret",
  "https://cockpit.fixture.invalid?secret", "https://localhost",
  "https://cockpit.fixture.invalid:0", "https://cockpit.123"]) {
  test(`canonical configured origin rejects ${origin}`, async () => {
    const input = signing();
    await assert.rejects(createPasskeyCredentialActionToken({ ...input,
      context: { ...input.context, origin }, authorization: { ...receipt(input), origin } }), rejection);
  });
}
test("trusted context itself rejects malformed identity, hash, time and extra fields", async () => {
  const input = signing();
  for (const patch of [{ authEpoch: true }, { userId: null }, { subject: "hidden\u200b" },
    { subject: "é".repeat(128) }, { oidcAuthTime: 0 }, { sessionBinding: "b".repeat(63) },
    { sessionExpiresAt: 1.5 }, { extra: true }]) {
    await assert.rejects(createPasskeyCredentialActionToken({ ...input,
      context: { ...input.context, ...patch } as unknown as PasskeyCredentialContext }), rejection);
  }
});
for (const [name, edit] of [
  ["whitespace tampering", (body: string) => body + " "],
  ["different account", (body: string) => body.replace(id(13), id(99))],
  ["different connection", (body: string) => body.replace(id(14), id(99))],
  ["CAS change", (body: string) => body.replace('"expected_storage":3', '"expected_storage":4')],
  ["decimal integer", (body: string) => body.replace('"expected_storage":3', '"expected_storage":3.0')],
  ["exponential integer", (body: string) => body.replace('"expected_storage":3', '"expected_storage":3e0')],
  ["duplicate field", (body: string) => body.replace('{"platform_account_id":', '{"platform_account_id":"x","platform_account_id":')],
  ["escaped duplicate", (body: string) => body.replace('{"platform_account_id":', '{"platform_\\u0061ccount_id":"x","platform_account_id":')],
  ["extra triple field", (body: string) => body.replace('"credentials":{', '"credentials":{"broker_uid":"x",')],
  ["hidden characters", (body: string) => body.replace("fixture-passphrase", "hidden\\u200b")],
  ["unsafe UTF8 budget", (body: string) => body.replace("fixture-passphrase", "é".repeat(129))],
  ["missing credential", (body: string) => body.replace('"api_key"', '"wrong_key"')],
] as const) {
  test(`private body rejects ${name}`, async () => {
    const input = signing("replace"), body = edit(input.body);
    const authorization = { ...receipt(input), body_sha256: name === "whitespace tampering" ? receipt(input).body_sha256 : hash(body) };
    await assert.rejects(createPasskeyCredentialActionToken({ ...input, body, authorization }), rejection);
  });
}
test("raw whitespace and UTF8 are preserved when their exact bytes were authorized", async () => {
  const input = signing("replace"), body = " \n" + input.body + "\t";
  const token = await createPasskeyCredentialActionToken({ ...input, body,
    authorization: { ...receipt(input), body_sha256: hash(body) } });
  assert.equal((await jwtVerify(token, key, { currentDate: new Date(now * 1000) })).payload.body_sha256, hash(body));
});
test("revoke cannot carry a triple and registration cannot carry versions", async () => {
  for (const action of ["register", "revoke"] as const) {
    const input = signing(action), data = JSON.parse(input.body);
    if (action === "register") data.expected_revision = 1;
    else data.credentials = { api_key: "SYNTHETIC", secret: "synthetic", passphrase: "synthetic" };
    const body = JSON.stringify(data);
    await assert.rejects(createPasskeyCredentialActionToken({ ...input, body,
      authorization: { ...receipt(input), body_sha256: hash(body) } }), rejection);
  }
});
test("mutable receipt, context and key inputs cannot change an in-flight signature", async () => {
  const input = signing("replace"), source = receipt(input);
  const signingResult = createPasskeyCredentialActionToken(input);
  (source as { user_id: string }).user_id = id(99);
  (source.target as { expected_storage: number }).expected_storage = 99;
  (input.context as { subject: string }).subject = "other-user";
  input.key.fill(0);
  const token = await signingResult;
  const payload = (await jwtVerify(token, key, { currentDate: new Date(now * 1000) })).payload;
  assert.equal(payload.user_id, id(12));
  assert.equal((payload.target as { expected_storage: number }).expected_storage, 3);
  assert.equal(payload.sub, "opaque-fixture-sub");
});
test("slow signing, clock rollback and unsafe clocks never publish an assertion", async () => {
  for (const finished of [now + 60, now - 1, Number.MAX_SAFE_INTEGER, NaN, 0, 1.5]) {
    let calls = 0;
    await assert.rejects(createPasskeyCredentialActionToken({ ...signing(),
      clock: () => ++calls === 1 ? now : finished }), rejection);
  }
});
test("static errors contain no credential, receipt or signing-key values", async () => {
  for (const input of [{ ...signing(), key: new Uint8Array(31) },
    { ...signing(), body: "SYNTHETIC-SECRET" }, { ...signing(), authorization: null }]) {
    try { await createPasskeyCredentialActionToken(input); assert.fail("expected rejection"); }
    catch (error) { assert.equal(String(error), "Error: PASSKEY_CREDENTIAL_TOKEN_REJECTED"); }
  }
});
test("signing twice is repeatable; this contract cannot claim persistent replay prevention", async () => {
  const input = signing(), left = await createPasskeyCredentialActionToken(input),
    right = await createPasskeyCredentialActionToken(input);
  const claims = await Promise.all([left, right].map(token =>
    jwtVerify(token, key, { currentDate: new Date(now * 1000) })));
  assert.equal(claims[0].payload.authorization_id, claims[1].payload.authorization_id);
  assert.notEqual(claims[0].payload.jti, claims[1].payload.jti);
});
