import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { jwtVerify } from "jose";
import {
  allowedCredentialActions, canonicalUuid, deriveActionTarget, parseAccountRequest,
  parseActionTarget, parseCredentialActionMetadata,
} from "../src/lib/credential-action-contracts.ts";
import type { CredentialActionMetadata, CredentialAction } from "../src/lib/credential-action-contracts.ts";
import { createCredentialActionToken, CREDENTIAL_ACTION_TARGETS } from "../src/lib/credential-action-token.ts";
import type { CredentialActionTokenInput } from "../src/lib/credential-action-token.ts";

const tenant = "00000000-0000-0000-0000-000000000011";
const account = "00000000-0000-0000-0000-000000000012";
const connection = "00000000-0000-0000-0000-000000000013";
const other = "00000000-0000-0000-0000-000000000014";
const now = 1_700_000_000;
const issuer = "https://identity.fixture.invalid";
const key = new Uint8Array(32).fill(37); // Public synthetic test material.
const current: CredentialActionMetadata = {
  tenant_id: tenant, auth_epoch: 4,
  account: { id: account, name: "Fixture Classic", broker: "bitget", mode: "read_only", status: "ready" },
  connection: null,
};
const expected = { tenantId: tenant, accountId: account, authEpoch: 4 };
function metadata(patch: Partial<CredentialActionMetadata> = {}): CredentialActionMetadata {
  return { ...current, ...patch };
}
function active(status: "ready" | "paused" = "ready"): CredentialActionMetadata {
  return metadata({
    account: { ...current.account, status },
    connection: { connection_id: connection, credential_revision: 2, storage_version: 3, status: "active" },
  });
}
function signing(action: CredentialAction = "register"): CredentialActionTokenInput {
  const target = action === "register" ? deriveActionTarget(current, action, { newConnectionId: connection }) :
    deriveActionTarget(active(), action);
  const { action: _action, ...bound } = target;
  const payload = { ...bound, ...(action === "revoke" ? {} :
    { credentials: { api_key: "SYNTHETIC_PUBLIC_FIXTURE", secret: "synthetic-secret", passphrase: "fixture-passphrase" } }) };
  return { key, oidcIssuer: issuer,
    identity: { subject: "opaque-fixture-sub", issuer, authTime: now - 1, amr: ["pwd", "otp", "mfa"] },
    tenantId: tenant, authEpoch: 4, startedAt: now - 2, now, target, body: JSON.stringify(payload) };
}
async function verified(input: CredentialActionTokenInput) {
  const token = await createCredentialActionToken(input);
  const result = await jwtVerify(token, key, {
    issuer: "investalo-bff", audience: "investalo-credentials", algorithms: ["HS256"],
    currentDate: new Date(now * 1000),
  });
  return { ...result, token };
}

test("account request rejects extra authority, noncanonical IDs and non-object shapes", () => {
  assert.deepEqual(parseAccountRequest({ platform_account_id: account }), { platform_account_id: account });
  for (const value of [null, [], account, {}, { platform_account_id: true },
    { platform_account_id: account, tenant_id: tenant }, { platform_account_id: account, action: "revoke" },
    { platform_account_id: account.replaceAll("-", "") }, { platform_account_id: `urn:uuid:${account}` }]) {
    assert.throws(() => parseAccountRequest(value), /CREDENTIAL_ACTION_REJECTED/);
  }
  assert.throws(() => canonicalUuid("abcdefab-abcd-abcd-abcd-abcdefabcdef".toUpperCase()));
  assert.throws(() => canonicalUuid(`{${account}}`));
  assert.throws(() => parseAccountRequest(Object.create({ platform_account_id: account })));
});
test("metadata is exact, tenant/account/epoch bound, safe and deeply frozen", () => {
  const result = parseCredentialActionMetadata(current, expected);
  assert.deepEqual(result, current);
  assert.ok(Object.isFrozen(result) && Object.isFrozen(result.account));
  assert.throws(() => { (result.account as { name: string }).name = "changed"; });
  for (const patch of [{ tenant_id: other }, { auth_epoch: 3 }, { auth_epoch: true },
    { auth_epoch: Number.MAX_SAFE_INTEGER + 1 }, { uid: "123" }, { connection: {} },
    { account: { ...current.account, id: other } }, { account: { ...current.account, broker: "mt5" } },
    { account: { ...current.account, mode: "paper" } }, { account: { ...current.account, status: "live" } },
    { account: { ...current.account, name: "secret\nmarker" } },
    { account: { ...current.account, credential: "secret" } }]) {
    assert.throws(() => parseCredentialActionMetadata({ ...current, ...patch }, expected), /CREDENTIAL_ACTION_REJECTED/);
  }
  assert.throws(() => parseCredentialActionMetadata(current, { ...expected, tenantId: other }));
  assert.throws(() => parseCredentialActionMetadata(current, { ...expected, authEpoch: true as unknown as number }));
});
test("connection metadata rejects invented state, missing or unsafe versions and private fields", () => {
  const source = active();
  assert.ok(Object.isFrozen(parseCredentialActionMetadata(source, expected).connection));
  for (const patch of [{ credential_revision: 0 }, { storage_version: -1 }, { storage_version: 1.5 },
    { credential_revision: true }, { storage_version: "3" }, { storage_version: Number.MAX_SAFE_INTEGER + 1 },
    { status: "ready" }, { connection_id: null }, { broker_uid: "123" }, { ciphertext: {} }]) {
    assert.throws(() => parseCredentialActionMetadata({ ...source, connection: { ...source.connection, ...patch } }, expected));
  }
  const { storage_version: _missing, ...incomplete } = source.connection!;
  assert.throws(() => parseCredentialActionMetadata({ ...source, connection: incomplete }, expected));
});
test("action availability preserves account mode, terminal revocation and paused-account revoke", () => {
  assert.deepEqual(allowedCredentialActions(current), ["register"]);
  assert.deepEqual(allowedCredentialActions(active()), ["replace", "revoke"]);
  assert.deepEqual(allowedCredentialActions(active("paused")), ["revoke"]);
  assert.deepEqual(allowedCredentialActions(metadata({ account: { ...current.account, status: "paused" } })), []);
  const source = active();
  const revoked = metadata({ ...source, connection: { ...source.connection!, status: "revoked" } });
  assert.deepEqual(allowedCredentialActions(revoked), []);
  assert.throws(() => deriveActionTarget(revoked, "register", { newConnectionId: other }));
  assert.throws(() => deriveActionTarget(active("paused"), "replace"));
  assert.throws(() => deriveActionTarget(current, "revoke"));
});
test("target creation binds server allocated connection or existing exact CAS versions", () => {
  const target = deriveActionTarget(current, "register", { newConnectionId: connection });
  assert.deepEqual(target, { action: "register", platform_account_id: account, connection_id: connection });
  assert.ok(Object.isFrozen(target));
  assert.throws(() => deriveActionTarget(current, "register"));
  assert.throws(() => deriveActionTarget(active(), "replace", { newConnectionId: other }));
  assert.deepEqual(deriveActionTarget(active(), "replace"), {
    action: "replace", platform_account_id: account, connection_id: connection, expected_revision: 2, expected_storage: 3,
  });
  for (const bad of [{ ...target, expected_revision: 1 }, { ...target, action: "REGISTER" },
    { ...deriveActionTarget(active(), "replace"), expected_revision: true },
    { ...deriveActionTarget(active(), "replace"), expected_storage: Number.MAX_SAFE_INTEGER }]) {
    assert.throws(() => parseActionTarget(bad), /CREDENTIAL_ACTION_REJECTED/);
  }
  const accessor = Object.defineProperty({ ...target }, "action", {
    get() { throw new Error("private-accessor-marker"); },
  });
  assert.throws(() => parseActionTarget(accessor), /CREDENTIAL_ACTION_REJECTED/);
});
test("safe integer limit fails closed instead of rounding next stored versions", () => {
  const record = active();
  const maxRevision = metadata({ ...record, connection: { ...record.connection!, credential_revision: Number.MAX_SAFE_INTEGER } });
  assert.deepEqual(allowedCredentialActions(maxRevision), ["revoke"]);
  const maxStorage = metadata({ ...record, connection: { ...record.connection!, storage_version: Number.MAX_SAFE_INTEGER } });
  assert.deepEqual(allowedCredentialActions(maxStorage), []);
});
test("signer interoperable claims are exact and bind each route plus unchanged UTF8 bytes", async () => {
  for (const action of ["register", "replace", "revoke"] as const) {
    const input = signing(action);
    input.body = ` \n${input.body}\n`; // Valid raw whitespace is included in the digest.
    const { payload, protectedHeader, token } = await verified(input);
    assert.deepEqual(protectedHeader, { alg: "HS256", typ: "JWT" });
    assert.deepEqual(Object.keys(payload).sort(), [
      "iss", "aud", "sub", "oidc_iss", "oidc_auth_time", "oidc_amr", "step_up_started_at", "tenant_id",
      "auth_epoch", "jti", "iat", "exp", "htm", "htu", "body_sha256",
    ].sort());
    assert.equal(payload.htm, "POST");
    assert.equal(payload.htu, CREDENTIAL_ACTION_TARGETS[action]);
    assert.equal(payload.tenant_id, tenant); assert.equal(payload.auth_epoch, 4);
    assert.equal(payload.oidc_auth_time, now - 1); assert.equal(payload.step_up_started_at, now - 2);
    assert.equal(payload.sub, "opaque-fixture-sub"); assert.equal(payload.oidc_iss, issuer);
    assert.deepEqual(payload.oidc_amr, ["pwd", "otp", "mfa"]);
    assert.equal(payload.body_sha256, createHash("sha256").update(input.body, "utf8").digest("hex"));
    assert.equal(payload.iat, now); assert.equal(payload.exp, now + 60);
    assert.match(payload.jti!, /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
    assert.equal(token.includes("synthetic-secret"), false);
  }
  const first = await verified(signing()), second = await verified(signing());
  assert.notEqual(first.payload.jti, second.payload.jti);
});
test("signer enforces dedicated binary key bounds and distinct audience", async () => {
  for (const value of [new Uint8Array(31), new Uint8Array(129), "x".repeat(32), null, [37, 37]]) {
    await assert.rejects(createCredentialActionToken({ ...signing(), key: value as Uint8Array }), /CREDENTIAL_ACTION_TOKEN_REJECTED/);
  }
  const { token } = await verified(signing());
  await assert.rejects(jwtVerify(token, key, { audience: "investalo-api", currentDate: new Date(now * 1000) }));
  await assert.rejects(jwtVerify(token, new Uint8Array(32).fill(38)));
  const maximum = await createCredentialActionToken({ ...signing(), key: new Uint8Array(128).fill(38) });
  assert.ok(maximum);
});
test("signer requires actual validated MFA identity context, not mere normal session claims", async () => {
  const input = signing();
  for (const patch of [{ issuer: "https://different.invalid" }, { subject: "" }, { subject: "secret\nmarker" },
    { subject: "\ud800" }, { subject: "x".repeat(256) }, { amr: [] }, { amr: ["pwd", "otp"] },
    { amr: ["mfa", "mfa"] }, { amr: ["MFA"] }, { amr: ["mfa", true] }, { amr: "mfa" },
    { amr: ["mfa", ...Array.from({ length: 8 }, (_, n) => `factor${n}`)] }]) {
    await assert.rejects(createCredentialActionToken({ ...input, identity: { ...input.identity, ...patch } as typeof input.identity }));
  }
  for (const oidcIssuer of ["http://identity.invalid", "https://user:pass@identity.invalid",
    "https://identity.invalid?a=secret", "https://identity.invalid#secret", "https://identity.invalid\n"]) {
    await assert.rejects(createCredentialActionToken({ ...input, oidcIssuer, identity: { ...input.identity, issuer: oidcIssuer } }));
  }
});
test("fresh authentication never predates stepup and enforces independent time windows", async () => {
  const input = signing();
  for (const [authTime, startedAt] of [[now - 2, now - 1], [now - 121, now - 122],
    [now, now - 301], [now + 6, now], [now, now + 6]]) {
    await assert.rejects(createCredentialActionToken({ ...input, startedAt, identity: { ...input.identity, authTime } }));
  }
  for (const [authTime, startedAt] of [[now - 120, now - 300], [now + 5, now + 5], [now, now]]) {
    await assert.doesNotReject(createCredentialActionToken({ ...input, startedAt, identity: { ...input.identity, authTime } }));
  }
  for (const value of [true, NaN, Infinity, 1.5, -1, "1700000000"]) {
    await assert.rejects(createCredentialActionToken({ ...input, startedAt: value as number }));
    await assert.rejects(createCredentialActionToken({ ...input, identity: { ...input.identity, authTime: value as number } }));
    await assert.rejects(createCredentialActionToken({ ...input, authEpoch: value as number }));
    await assert.rejects(createCredentialActionToken({ ...input, now: value as number }));
  }
});
test("body account, connection, versions and schema cannot diverge from stepup target", async () => {
  for (const action of ["register", "replace", "revoke"] as const) {
    const input = signing(action), body = JSON.parse(input.body) as Record<string, unknown>;
    for (const patch of [{ platform_account_id: other }, { connection_id: other },
      { roles: ["owner"] }, { tenant_id: other }, { action: "revoke" }]) {
      await assert.rejects(createCredentialActionToken({ ...input, body: JSON.stringify({ ...body, ...patch }) }));
    }
    if (action !== "register") {
      for (const patch of [{ expected_revision: 3 }, { expected_storage: 4 }, { expected_revision: true }]) {
        await assert.rejects(createCredentialActionToken({ ...input, body: JSON.stringify({ ...body, ...patch }) }));
      }
    }
    await assert.rejects(createCredentialActionToken({ ...input, body: JSON.stringify({
      ...body, credentials: { api_key: "x", secret: "x", passphrase: "x", uid: "123" },
    }) }));
  }
});
test("duplicate escaped keys, invalid JSON, arrays and ill-formed UTF8 are rejected without exposing body", async () => {
  const input = signing();
  for (const body of ["", "null", "[]", "{", "{}",
    input.body.replace('"connection_id":', `"connection_id":"${connection}","connection_id":`),
    input.body.replace('"connection_id":', `"\\u0063onnection_id":"${connection}","connection_id":`),
    input.body.replace('"api_key":', '"api_key":"same","api_key":'),
    JSON.stringify({ ...JSON.parse(input.body), credentials: { api_key: "x", secret: "x", passphrase: "x\nsecret" } }),
    input.body + "\ud800",
    input.body + " ".repeat(4097)]) {
    await assert.rejects(createCredentialActionToken({ ...input, body }), (error: unknown) => {
      assert.ok(error instanceof Error); assert.equal(error.message, "CREDENTIAL_ACTION_TOKEN_REJECTED");
      assert.equal(error.cause, undefined); assert.equal(String(error).includes("synthetic-secret"), false);
      return true;
    });
  }
});
test("body digest preserves exact Unicode and escape spelling without trimming secrets", async () => {
  const input = signing();
  const content = JSON.parse(input.body); content.credentials.passphrase = "  geprüft  ";
  input.body = JSON.stringify(content);
  const unicode = await verified(input);
  const escaped = await verified({ ...input, body: input.body.replace("ü", "\\u00fc") });
  assert.notEqual(unicode.payload.body_sha256, escaped.payload.body_sha256);
  assert.equal(unicode.payload.body_sha256, createHash("sha256").update(input.body, "utf8").digest("hex"));
});
