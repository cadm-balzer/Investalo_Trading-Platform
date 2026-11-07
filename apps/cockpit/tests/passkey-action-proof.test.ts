/**
 * Actual none/ES256 registration and P256 assertion verification across the
 * injected BFF protocol. Fake transport models receipts, not PostgreSQL safety:
 * committed claims/locks/RLS have their separate real-DB tests.
 */
import assert from "node:assert/strict";
import { createHash, generateKeyPairSync, randomBytes, sign } from "node:crypto";
import test from "node:test";
import { isoCBOR } from "@simplewebauthn/server/helpers";
import {
  beginPasskeyActionProof, confirmPasskeyActionProof, finishPasskeyActionProof,
  readPasskeyActionGrant, type PasskeyActionPorts,
} from "../src/lib/passkey-action-proof.ts";
import {
  actionProofBinding, confirmationHash, type ActionProofAttempt, type ActionProofGrant,
  type ProofSession,
} from "../src/lib/passkey-action-proof-state.ts";
import { verifyPasskeyRegistration } from "../src/lib/passkey-registration.ts";
import type { CredentialActionMetadata } from "../src/lib/credential-action-contracts.ts";
import type { PasskeyContext, PasskeyRecord } from "../src/lib/passkey-enrollment-state.ts";

const TENANT = "10000000-0000-0000-0000-000000000001";
const USER = "20000000-0000-0000-0000-000000000002";
const KEY = "30000000-0000-0000-0000-000000000003";
const ACCOUNT = "40000000-0000-0000-0000-000000000004";
const CONNECTION = "50000000-0000-0000-0000-000000000005";
const ATTEMPT = "60000000-0000-0000-0000-000000000006";
const GRANT = "70000000-0000-0000-0000-000000000007";
const OTHER = "80000000-0000-0000-0000-000000000008";
const RP = "cockpit.local.test", ORIGIN = `https://${RP}:8443`;
const encoded = (bytes: Uint8Array) => Buffer.from(bytes).toString("base64url");
const token = () => randomBytes(32).toString("base64url");
const hash = (value: string | Uint8Array) => createHash("sha256").update(value).digest();
const clone = <T>(value: T): T => structuredClone(value);
const reject = (error: unknown) => {
  assert.equal((error as Error).message, "PASSKEY_ACTION_PROOF_REJECTED");
  assert.equal((error as Error).cause, undefined);
  return true;
};
async function fixture({ synced = false, registeredBackupEligible = synced }: {
  synced?: boolean; registeredBackupEligible?: boolean;
} = {}) {
  const started = Math.floor(Date.now() / 1000);
  const { publicKey, privateKey } = generateKeyPairSync("ec", { namedCurve: "prime256v1" });
  const jwk = publicKey.export({ format: "jwk" });
  const cose = new Map<number, number | Uint8Array>([
    [1, 2], [3, -7], [-1, 1], [-2, new Uint8Array(Buffer.from(jwk.x!, "base64url"))],
    [-3, new Uint8Array(Buffer.from(jwk.y!, "base64url"))],
  ]);
  const credentialId = randomBytes(32), userHandle = token(), enrollmentChallenge = token();
  const counter = Buffer.alloc(4), length = Buffer.alloc(2); length.writeUInt16BE(credentialId.length);
  const authData = Buffer.concat([hash(RP), Buffer.from([registeredBackupEligible ? 0x5d : 0x45]),
    counter, Buffer.alloc(16), length, credentialId, isoCBOR.encode(cose)]);
  const registration = { id: encoded(credentialId), rawId: encoded(credentialId), type: "public-key",
    clientExtensionResults: { credProps: { rk: true } }, response: {
      clientDataJSON: encoded(Buffer.from(JSON.stringify({
        type: "webauthn.create", challenge: enrollmentChallenge, origin: ORIGIN, crossOrigin: false,
      }))),
      attestationObject: encoded(isoCBOR.encode(new Map<string, string | Uint8Array | Map<string, number | string | Uint8Array>>([
        ["fmt", "none"], ["authData", new Uint8Array(authData)], ["attStmt", new Map()],
      ]))),
    } };
  const candidate = await verifyPasskeyRegistration(registration, {
    tenantId: TENANT, userId: USER, rpId: RP, origin: ORIGIN, userHandle,
    challenge: enrollmentChallenge, startedAt: started, expiresAt: started + 120,
  });
  const originalKey: PasskeyRecord = { passkey_id: KEY, tenant_id: TENANT, user_id: USER, rp_id: RP,
    credential_id: candidate.credentialId, user_handle: candidate.userHandle,
    public_key: encoded(candidate.publicKey), sign_count: candidate.counter,
    backup_eligible: candidate.backupEligible, backed_up: candidate.backedUp,
    storage_version: 1, status: "active", enrollment_epoch: 4 };
  const f = {
    bound: { handle: token(), origin: ORIGIN, session: { subject: "opaque-fixture-owner",
      issuer: "https://idp.fixture.invalid", oidcAuthTime: started - 300, tenantId: TENANT,
      authEpoch: 4, expiresAt: started + 1800, csrf: token(), displayName: "Fixture",
      tenantName: "Fixture tenant" } } as ProofSession,
    context: { tenant_id: TENANT, user_id: USER, auth_epoch: 4, rp_id: RP,
      credential: clone(originalKey) } as PasskeyContext,
    metadata: { tenant_id: TENANT, auth_epoch: 4, account: {
      id: ACCOUNT, name: "Fixture read-only account", broker: "bitget", mode: "read_only", status: "disconnected",
    }, connection: null } as CredentialActionMetadata,
    attempt: null as ActionProofAttempt | null, grant: null as ActionProofGrant | null,
    claimed: false, consumed: false, offset: 0,
    events: [] as string[], requests: [] as { path: string; body: Record<string, unknown> }[],
    principals: [] as ProofSession["session"][],
    hooks: new Map<string, () => void | Promise<void>>(),
  };
  const now = () => Math.floor(Date.now() / 1000) + f.offset;
  const ports: PasskeyActionPorts = {
    current: async () => clone(f.bound), now, randomToken: token, randomUuid: () => CONNECTION,
    context: async session => { f.principals.push(clone(session)); return clone(f.context); },
    metadata: async (session, accountId) => {
      assert.equal(accountId, ACCOUNT); f.principals.push(clone(session)); return clone(f.metadata);
    },
    request: async (session, path, body) => {
      f.principals.push(clone(session));
      const event = path.split("/").at(-1)!;
      f.events.push(event); f.requests.push({ path, body: clone(body) });
      assert.equal(body.session_binding, actionProofBinding(f.bound));
      let receipt: unknown;
      if (event === "prepare") {
        f.attempt = { attempt_id: ATTEMPT, tenant_id: TENANT, user_id: USER, auth_epoch: 4, rp_id: RP,
          target: body.target as ActionProofAttempt["target"], metadata: clone(f.metadata),
          credential: clone(f.context.credential!), session_binding: body.session_binding as string,
          challenge: body.challenge as string, confirmation_hash: body.confirmation_hash as string,
          prepared_at: now(), expires_at: now() + 120, session_expires_at: session.expiresAt };
        receipt = clone(f.attempt);
      } else if (event === "claim") {
        assert.equal(body.attempt_id, ATTEMPT);
        if (f.claimed || !f.attempt) throw new Error("transport-denied");
        f.claimed = true; receipt = clone(f.attempt);
      } else if (event === "finish") {
        assert(f.claimed && f.attempt); assert.equal(body.attempt_id, ATTEMPT);
        const key = f.context.credential!;
        f.context = { ...f.context, credential: { ...key, sign_count: body.new_counter as number,
          backed_up: body.backed_up as boolean, storage_version: key.storage_version + 1 } };
        f.grant = { grant_id: GRANT, attempt_id: ATTEMPT, tenant_id: TENANT, user_id: USER,
          auth_epoch: 4, rp_id: RP, target: f.attempt.target, metadata: f.attempt.metadata,
          passkey_id: KEY, passkey_version: f.context.credential!.storage_version,
          session_binding: f.attempt.session_binding, confirmation_hash: f.attempt.confirmation_hash,
          checked_at: body.checked_at as number, expires_at: (body.checked_at as number) + 120,
          session_expires_at: session.expiresAt };
        receipt = clone(f.grant);
      } else if (event === "grant" || event === "confirm") {
        assert.equal(body.grant_id, GRANT);
        if (!f.grant || f.consumed) throw new Error("transport-denied");
        if (event === "confirm") {
          assert.equal(body.confirmation_hash, f.grant.confirmation_hash);
          f.consumed = true;
        }
        receipt = event === "confirm"
          ? { status: "verified", execution_enabled: false, proof: clone(f.grant) }
          : clone(f.grant);
      } else { throw new Error("unexpected transport path"); }
      await f.hooks.get(event)?.();
      return receipt;
    },
  };
  function assertion(challenge: string, changes: { key?: typeof privateKey; origin?: string; flags?: number;
    counter?: number; challenge?: string } = {}) {
    const client = Buffer.from(JSON.stringify({ type: "webauthn.get", challenge: changes.challenge ?? challenge,
      origin: changes.origin ?? ORIGIN, crossOrigin: false }));
    const count = Buffer.alloc(4); count.writeUInt32BE(changes.counter ?? (synced ? 0 : 1));
    const data = Buffer.concat([hash(RP), Buffer.from([changes.flags ?? (synced ? 0x1d : 0x05)]), count]);
    return { id: originalKey.credential_id, rawId: originalKey.credential_id,
      type: "public-key", clientExtensionResults: {}, response: {
        clientDataJSON: encoded(client), authenticatorData: encoded(data),
        signature: encoded(sign("sha256", Buffer.concat([data, hash(client)]), changes.key ?? privateKey)),
        userHandle: originalKey.user_handle,
      } };
  }
  async function begin() { return beginPasskeyActionProof(ports, ACCOUNT, "register"); }
  async function proved() {
    const begin = await beginPasskeyActionProof(ports, ACCOUNT, "register");
    return { begin, result: await finishPasskeyActionProof(ports, begin.attempt_id,
      assertion(begin.options.challenge), begin.confirmation_token) };
  }
  return { f, ports, privateKey, candidate, enrollmentChallenge, originalKey, assertion, begin, proved };
}

test("actual none registration candidate needs a separate fresh signed assertion before a target-bound grant", async () => {
  const x = await fixture(), original = clone(x.f.bound.session), start = await x.begin();
  assert.notEqual(start.options.challenge, x.enrollmentChallenge);
  assert.equal(start.options.userVerification, "required");
  assert.deepEqual(start.options.allowCredentials, [{ id: x.candidate.credentialId, type: "public-key" }]);
  assert.equal(x.f.grant, null);
  const finished = await finishPasskeyActionProof(x.ports, start.attempt_id,
    x.assertion(start.options.challenge), start.confirmation_token);
  assert.deepEqual(x.f.events, ["prepare", "claim", "finish"]);
  assert.equal(x.f.context.credential!.storage_version, 2);
  assert.equal(finished.grant.execution_enabled, false);
  assert.equal(finished.grant.checkedAt > original.oidcAuthTime, true);
  assert.equal(finished.grant.accountName, x.f.metadata.account.name);
  assert.deepEqual(Object.keys(finished.grant).sort(),
    ["accountName", "checkedAt", "confirmationToken", "execution_enabled", "expiresAt", "target"]);
  assert.equal(await readPasskeyActionGrant(x.ports, finished.grant_id, start.confirmation_token)
    .then(view => view.confirmationToken), start.confirmation_token);
  assert.deepEqual(await confirmPasskeyActionProof(x.ports, finished.grant_id, start.confirmation_token),
    { status: "verified", execution_enabled: false, action: "register", platform_account_id: ACCOUNT });
  assert.equal(x.f.consumed, true);
  assert.deepEqual(x.f.bound.session, original);
  for (const principal of x.f.principals) assert.deepEqual(principal, original);
});

test("synchronized counter0→0 still requires a consumed challenge and advances durable factor version", async () => {
  const x = await fixture({ synced: true }), { begin, result } = await x.proved();
  assert.equal(x.f.context.credential!.sign_count, 0);
  assert.equal(x.f.context.credential!.storage_version, 2);
  await assert.rejects(finishPasskeyActionProof(x.ports, begin.attempt_id,
    x.assertion(begin.options.challenge), begin.confirmation_token), reject);
  assert.equal(x.f.events.filter(event => event === "finish").length, 1);
  await confirmPasskeyActionProof(x.ports, result.grant_id, begin.confirmation_token);
  await assert.rejects(confirmPasskeyActionProof(x.ports, result.grant_id, begin.confirmation_token), reject);
  assert.equal(x.f.events.filter(event => event === "confirm").length, 1);
});

for (const failure of ["wrong-key", "wrong-challenge", "wrong-origin", "missing-uv", "malformed"] as const) {
  test(`a committed claim with ${failure} publishes no grant and is never restored`, async () => {
    const x = await fixture(), start = await x.begin();
    const other = generateKeyPairSync("ec", { namedCurve: "prime256v1" }).privateKey;
    const response = failure === "malformed" ? {} : x.assertion(start.options.challenge, {
      ...(failure === "wrong-key" ? { key: other } : {}),
      ...(failure === "wrong-challenge" ? { challenge: token() } : {}),
      ...(failure === "wrong-origin" ? { origin: "https://foreign.fixture.invalid" } : {}),
      ...(failure === "missing-uv" ? { flags: 0x01 } : {}),
    });
    await assert.rejects(finishPasskeyActionProof(x.ports, start.attempt_id, response, start.confirmation_token), reject);
    assert.equal(x.f.claimed, true); assert.equal(x.f.grant, null);
    assert.equal(x.f.events.includes("finish"), false);
    await assert.rejects(finishPasskeyActionProof(x.ports, start.attempt_id,
      x.assertion(start.options.challenge), start.confirmation_token), reject);
  });
}

test("a valid signature cannot change the registered backup eligibility", async () => {
  const x = await fixture(), start = await x.begin();
  await assert.rejects(finishPasskeyActionProof(x.ports, start.attempt_id,
    x.assertion(start.options.challenge, { flags: 0x1d }), start.confirmation_token), reject);
  assert.equal(x.f.grant, null); assert.equal(x.f.events.includes("finish"), false);
});

test("stale preview token is rejected before durable consume and leaves the latest grant usable", async () => {
  const x = await fixture(), { begin, result } = await x.proved();
  await assert.rejects(confirmPasskeyActionProof(x.ports, result.grant_id, token()), reject);
  assert.equal(x.f.consumed, false); assert.equal(x.f.events.includes("confirm"), false);
  assert.deepEqual(await confirmPasskeyActionProof(x.ports, result.grant_id, begin.confirmation_token),
    { status: "verified", execution_enabled: false, action: "register", platform_account_id: ACCOUNT });
});

for (const field of ["handle", "csrf", "subject", "issuer", "epoch", "origin", "oidc-time", "session-expiry"] as const) {
  test(`session ${field} change during an API await rejects preparation without browser options`, async () => {
    const x = await fixture();
    x.f.hooks.set("prepare", () => {
      const session = { ...x.f.bound.session };
      if (field === "csrf") session.csrf = token();
      if (field === "subject") session.subject = "different-user";
      if (field === "issuer") session.issuer = "https://different.fixture.invalid";
      if (field === "epoch") session.authEpoch++;
      if (field === "oidc-time") session.oidcAuthTime++;
      if (field === "session-expiry") session.expiresAt++;
      x.f.bound = { ...x.f.bound, session,
        ...(field === "handle" ? { handle: token() } : {}),
        ...(field === "origin" ? { origin: `https://${RP}` } : {}) };
    });
    await assert.rejects(x.begin(), reject);
  });
}

for (const drift of ["account", "key-version", "key-revoked", "user-owner", "expired"] as const) {
  test(`live ${drift} drift after durable claim cannot publish a proof`, async () => {
    const x = await fixture(), start = await x.begin();
    x.f.hooks.set("claim", () => {
      if (drift === "account") x.f.metadata = { ...x.f.metadata,
        account: { ...x.f.metadata.account, name: "Changed preview" } };
      if (drift === "key-version") x.f.context = { ...x.f.context,
        credential: { ...x.f.context.credential!, storage_version: 2 } };
      if (drift === "key-revoked") x.f.context = { ...x.f.context,
        credential: { ...x.f.context.credential!, status: "revoked" } };
      if (drift === "user-owner") x.f.context = { ...x.f.context, user_id: OTHER,
        credential: { ...x.f.context.credential!, user_id: OTHER } };
      if (drift === "expired") x.f.offset = 120;
    });
    await assert.rejects(finishPasskeyActionProof(x.ports, start.attempt_id,
      x.assertion(start.options.challenge), start.confirmation_token), reject);
    assert.equal(x.f.claimed, true); assert.equal(x.f.events.includes("finish"), false);
  });
}

test("factor drift while finishing cannot publish a usable preview despite a committed transport result", async () => {
  const x = await fixture(), start = await x.begin();
  x.f.hooks.set("finish", () => { x.f.context = { ...x.f.context,
    credential: { ...x.f.context.credential!, storage_version: 3 } }; });
  await assert.rejects(finishPasskeyActionProof(x.ports, start.attempt_id,
    x.assertion(start.options.challenge), start.confirmation_token), reject);
  assert(x.f.grant); assert.equal(x.f.consumed, false);
});

test("transport loss after claim remains consumed; original secret errors never escape", async () => {
  const x = await fixture(), start = await x.begin();
  x.f.hooks.set("claim", () => { throw new Error("private-transport-sentinel"); });
  await assert.rejects(finishPasskeyActionProof(x.ports, start.attempt_id,
    x.assertion(start.options.challenge), start.confirmation_token), reject);
  x.f.hooks.delete("claim");
  await assert.rejects(finishPasskeyActionProof(x.ports, start.attempt_id,
    x.assertion(start.options.challenge), start.confirmation_token), reject);
  assert.equal(x.f.claimed, true); assert.equal(x.f.grant, null);
});

test("preview projection cannot silently accept extra receipt data or another actor", async () => {
  for (const bad of ["extra", "actor", "target"] as const) {
    const x = await fixture();
    const original = x.ports.request;
    const ports: PasskeyActionPorts = { ...x.ports, request: async (session, path, body) => {
      const wire = await original(session, path, body);
      return path.endsWith("/prepare") ? {
        ...(wire as ActionProofAttempt),
        ...(bad === "extra" ? { privateKey: "private-sentinel" } : {}),
        ...(bad === "actor" ? { user_id: OTHER } : {}),
        ...(bad === "target" ? { target: { ...(wire as ActionProofAttempt).target, connection_id: OTHER } } : {}),
      } : wire;
    } };
    await assert.rejects(beginPasskeyActionProof(ports, ACCOUNT, "register"), reject);
  }
});

test("read/confirmation reject changed account metadata and do not consume the durable grant", async () => {
  const x = await fixture(), { begin, result } = await x.proved();
  x.f.metadata = { ...x.f.metadata, account: { ...x.f.metadata.account, status: "paused" } };
  await assert.rejects(readPasskeyActionGrant(x.ports, result.grant_id, begin.confirmation_token), reject);
  await assert.rejects(confirmPasskeyActionProof(x.ports, result.grant_id, begin.confirmation_token), reject);
  assert.equal(x.f.consumed, false); assert.equal(x.f.events.includes("confirm"), false);
});

test("session binding and confirmation hash do not contain raw browser secrets", async () => {
  const x = await fixture(), start = await x.begin();
  const binding = actionProofBinding(x.f.bound);
  assert.match(binding, /^[a-f0-9]{64}$/);
  assert.equal(binding.includes(x.f.bound.handle), false);
  assert.equal(binding.includes(x.f.bound.session.csrf), false);
  assert.equal(x.f.attempt!.confirmation_hash, confirmationHash(start.confirmation_token));
  for (const request of x.f.requests) assert.equal(JSON.stringify(request.body).includes(start.confirmation_token), false);
});

test("confirmation receipt requires the exact verification-only wrapper and matching durable proof", async () => {
  for (const bad of ["execution", "status", "extra", "proof"] as const) {
    const x = await fixture(), { begin, result } = await x.proved();
    const request = x.ports.request;
    const ports: PasskeyActionPorts = { ...x.ports, request: async (session, path, body) => {
      const wire = await request(session, path, body);
      if (!path.endsWith("/confirm")) return wire;
      return { ...(wire as Record<string, unknown>),
        ...(bad === "execution" ? { execution_enabled: true } : {}),
        ...(bad === "status" ? { status: "executed" } : {}),
        ...(bad === "extra" ? { credential_token: "private-sentinel" } : {}),
        ...(bad === "proof" ? { proof: { ...x.f.grant!, grant_id: OTHER } } : {}) };
    } };
    await assert.rejects(confirmPasskeyActionProof(ports, result.grant_id, begin.confirmation_token), reject);
  }
});
