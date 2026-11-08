import assert from "node:assert/strict";
import { createHash, generateKeyPairSync, randomBytes, sign } from "node:crypto";
import test from "node:test";
import { isoCBOR } from "@simplewebauthn/server/helpers";
import { generatePasskeyAuthenticationOptions, verifyPasskeyAssertion } from "../src/lib/passkey-verifier.ts";
import {
  browserBytes, browserEncoded, parseBrowserProofStart, parseBrowserProofGrant,
  parseBrowserProofConfirmation, serializeBrowserProofAssertion,
} from "../src/lib/passkey-browser-proof.ts";

const ACCOUNT = "10000000-0000-0000-0000-000000000001";
const CONNECTION = "20000000-0000-0000-0000-000000000002";
const ATTEMPT = "30000000-0000-0000-0000-000000000003";
const GRANT = "40000000-0000-0000-0000-000000000004";
const RP = "cockpit.local.test", ORIGIN = `https://${RP}:8443`;
const now = () => Math.floor(Date.now() / 1000);
const encoded = (value: Uint8Array) => Buffer.from(value).toString("base64url");
function fixture() {
  const started = now(), challenge = encoded(randomBytes(32)), token = encoded(randomBytes(32));
  const target = { action: "register", platform_account_id: ACCOUNT, connection_id: CONNECTION };
  const wire = { attempt_id: ATTEMPT, confirmation_token: token,
    preview: { target, accountName: "Synthetic check account", expiresAt: started + 120, execution_enabled: false },
    options: { challenge, rpId: RP, timeout: 120_000, userVerification: "required",
      allowCredentials: [{ id: encoded(randomBytes(32)), type: "public-key" }] } };
  const grant = { grant_id: GRANT, grant: { target, accountName: wire.preview.accountName,
    checkedAt: started, expiresAt: started + 120, confirmationToken: token, execution_enabled: false } };
  return { started, wire, grant };
}
test("browser assertion conversion preserves bytes through actual P256 signature verification", async () => {
  const f = fixture(), id = f.wire.options.allowCredentials[0].id, userHandle = randomBytes(32);
  const { publicKey, privateKey } = generateKeyPairSync("ec", { namedCurve: "prime256v1" });
  const jwk = publicKey.export({ format: "jwk" });
  const cose = isoCBOR.encode(new Map<number, number | Uint8Array>([
    [1, 2], [3, -7], [-1, 1], [-2, new Uint8Array(Buffer.from(jwk.x!, "base64url"))],
    [-3, new Uint8Array(Buffer.from(jwk.y!, "base64url"))],
  ]));
  const expected = { tenantId: ACCOUNT, userId: CONNECTION, rpId: RP, origin: ORIGIN,
    challenge: f.wire.options.challenge, startedAt: f.started, expiresAt: f.started + 120,
    credential: { tenantId: ACCOUNT, userId: CONNECTION, id, publicKey: new Uint8Array(cose),
      counter: 0, userHandle: encoded(userHandle) } };
  const generated = await generatePasskeyAuthenticationOptions(expected);
  f.wire.options = JSON.parse(JSON.stringify(generated));
  const prepared = parseBrowserProofStart(f.wire, ACCOUNT, "register", RP);
  assert.equal(browserEncoded(prepared.options.challenge as ArrayBuffer, 32, 32), expected.challenge);
  const client = Buffer.from(JSON.stringify({ type: "webauthn.get", challenge: expected.challenge, origin: ORIGIN, crossOrigin: false }));
  const counter = Buffer.alloc(4); counter.writeUInt32BE(1);
  const authenticator = Buffer.concat([createHash("sha256").update(RP).digest(), Buffer.from([5]), counter]);
  const signature = sign("sha256", Buffer.concat([authenticator, createHash("sha256").update(client).digest()]), privateKey);
  const raw = { id, type: "public-key", rawId: browserBytes(id, 1, 1023),
    authenticatorAttachment: "platform", getClientExtensionResults: () => ({}),
    response: { clientDataJSON: browserBytes(encoded(client), 1, 4096),
      authenticatorData: browserBytes(encoded(authenticator), 37, 1024),
      signature: browserBytes(encoded(signature), 1, 1024), userHandle: browserBytes(encoded(userHandle), 1, 64) } };
  const response = serializeBrowserProofAssertion(raw as unknown as PublicKeyCredential);
  const verified = await verifyPasskeyAssertion(response, expected);
  assert.equal(verified.newCounter, 1);
  assert.equal(verified.credentialId, id);
  const grant = parseBrowserProofGrant(f.grant, prepared);
  parseBrowserProofConfirmation({ status: "verified", execution_enabled: false,
    action: "register", platform_account_id: ACCOUNT }, grant);
});
test("browser credentials, targets and preview are exact bounded projections", () => {
  const f = fixture(), start = parseBrowserProofStart(f.wire, ACCOUNT, "register", RP, f.started);
  assert.deepEqual(Object.keys(start.preview), ["target", "accountName", "expiresAt", "execution_enabled"]);
  assert.equal(start.preview.execution_enabled, false);
  assert.equal(start.options.userVerification, "required");
  const grant = parseBrowserProofGrant(f.grant, start, f.started);
  assert.equal(grant.confirmationToken, start.confirmation_token);
});
for (const [label, mutate] of [
  ["unreviewed execution", (f: ReturnType<typeof fixture>) => { (f.wire.preview.execution_enabled as boolean) = true; }],
  ["different account", (f: ReturnType<typeof fixture>) => { f.wire.preview.target.platform_account_id = CONNECTION; }],
  ["different action", (f: ReturnType<typeof fixture>) => { f.wire.preview.target.action = "revoke"; }],
  ["different RP", (f: ReturnType<typeof fixture>) => { f.wire.options.rpId = "attacker.invalid"; }],
  ["optional UV", (f: ReturnType<typeof fixture>) => { f.wire.options.userVerification = "preferred"; }],
  ["expired preview", (f: ReturnType<typeof fixture>) => { f.wire.preview.expiresAt = f.started; }],
  ["private response field", (f: ReturnType<typeof fixture>) => { Object.assign(f.wire, { credential: "private sentinel" }); }],
  ["ambiguous token", (f: ReturnType<typeof fixture>) => { f.wire.confirmation_token += "="; }],
  ["extra allowed credential", (f: ReturnType<typeof fixture>) => { f.wire.options.allowCredentials.push(f.wire.options.allowCredentials[0]); }],
] as const) {
  test(`browser rejects ${label} before requesting a passkey`, () => {
    const f = fixture(); mutate(f);
    assert.throws(() => parseBrowserProofStart(f.wire, ACCOUNT, "register", RP, f.started));
  });
}
test("another tab's grant cannot replace this preview", () => {
  const f = fixture(), start = parseBrowserProofStart(f.wire, ACCOUNT, "register", RP, f.started);
  f.grant.grant.confirmationToken = encoded(randomBytes(32));
  assert.throws(() => parseBrowserProofGrant(f.grant, start, f.started));
});
test("an execution-enabled or different-action final receipt cannot show success", () => {
  const f = fixture(), start = parseBrowserProofStart(f.wire, ACCOUNT, "register", RP, f.started);
  const grant = parseBrowserProofGrant(f.grant, start, f.started);
  for (const receipt of [
    { status: "verified", execution_enabled: true, action: "register", platform_account_id: ACCOUNT },
    { status: "verified", execution_enabled: false, action: "revoke", platform_account_id: ACCOUNT },
    { status: "verified", execution_enabled: false, action: "register", platform_account_id: ACCOUNT, secret: "sentinel" },
  ]) assert.throws(() => parseBrowserProofConfirmation(receipt, grant));
});
test("null authenticator, mismatched credential ID and extensions are rejected", () => {
  assert.throws(() => serializeBrowserProofAssertion(null));
  const id = encoded(randomBytes(32)), rawId = browserBytes(id, 1, 1023);
  assert.throws(() => serializeBrowserProofAssertion({ type: "public-key", id: "other", rawId } as PublicKeyCredential));
  assert.throws(() => serializeBrowserProofAssertion({ type: "public-key", id, rawId,
    getClientExtensionResults: () => ({ credProps: { rk: true } }) } as unknown as PublicKeyCredential));
});
