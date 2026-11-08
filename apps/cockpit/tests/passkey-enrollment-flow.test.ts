import assert from "node:assert/strict";
import { createHash, generateKeyPairSync, randomBytes } from "node:crypto";
import { mkdtemp, readFile, readdir, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test, { type TestContext } from "node:test";
import { isoCBOR } from "@simplewebauthn/server/helpers";
import type { PublicKeyCredentialCreationOptionsJSON } from "@simplewebauthn/server";
import type { Session } from "../src/lib/auth.ts";
import {
  beginEnrollmentFlow, finishEnrollmentFlow, type EnrollmentFlowPorts,
  type EnrollmentSession, type StoredEnrollmentAttempt,
} from "../src/lib/passkey-enrollment-flow.ts";
import type { PasskeyRecord } from "../src/lib/passkey-enrollment-state.ts";
import { EncryptedStore } from "../src/lib/store.ts";

const TENANT = "10000000-0000-0000-0000-000000000001";
const USER = "20000000-0000-0000-0000-000000000002";
const CLAIM = "30000000-0000-0000-0000-000000000003";
const KEY = "40000000-0000-0000-0000-000000000004";
const ORIGIN = "https://cockpit.local.test:8443";
const b64 = (bytes: Uint8Array) => Buffer.from(bytes).toString("base64url");
const token = () => b64(randomBytes(32));
const copy = <T>(value: T): T => structuredClone(value);

async function fixture(t: TestContext) {
  const directory = await mkdtemp(join(tmpdir(), "investalo-enrollment-flow-"));
  t.after(() => rm(directory, { recursive: true, force: true }));
  const store = new EncryptedStore(directory, token());
  const initialTime = Math.floor(Date.now() / 1000);
  const session: Session = { issuer: "https://auth.local.test:8443", subject: "synthetic-subject",
    oidcAuthTime: initialTime - 300, tenantId: TENANT, authEpoch: 4, expiresAt: initialTime + 1800,
    displayName: "Synthetic", tenantName: "Fixture", csrf: token() };
  const f = {
    directory, store, session, clock: initialTime, bound: { handle: token(), session, origin: ORIGIN } as EnrollmentSession | null,
    userHandle: token(), ticket: token(), record: null as PasskeyRecord | null, claimed: false, committed: false,
    requests: [] as { path: string; body: Readonly<Record<string, unknown>>; session: Session }[],
    contexts: 0, consumes: 0, sawPersistedFactor: false, saved: [] as StoredEnrollmentAttempt[],
    hook: async (_phase: string) => {},
    claimChange: (_value: Record<string, unknown>) => {},
    recordChange: (_value: Record<string, unknown>) => {},
    contextChange: (_value: Record<string, unknown>) => {},
  };
  const ports: EnrollmentFlowPorts = {
    async current() { await f.hook("current"); return f.bound; },
    async context(principal) {
      assert.equal(principal.oidcAuthTime, session.oidcAuthTime);
      f.contexts++;
      const value: Record<string, unknown> = { tenant_id: TENANT, user_id: USER,
        auth_epoch: 4, rp_id: "cockpit.local.test", credential: copy(f.record) };
      if (f.committed && f.record) f.sawPersistedFactor = true;
      f.contextChange(value);
      await f.hook(`context:${f.contexts}`);
      return value;
    },
    async request(principal, path, body) {
      f.requests.push({ path, body: copy(body), session: copy(principal) });
      if (path === "/v1/passkeys/enrollment/claim") {
        if (f.claimed || body.token !== f.ticket) throw new Error("synthetic claim already consumed");
        f.claimed = true; // Receipt is returned only after this durable API claim.
        const claim: Record<string, unknown> = { claim_id: CLAIM, user_handle: f.userHandle,
          expires_at: new Date((f.clock + 120) * 1000).toISOString(), tenant_id: TENANT,
          user_id: USER, auth_epoch: 4, rp_id: "cockpit.local.test" };
        f.claimChange(claim);
        await f.hook("claim");
        return claim;
      }
      assert.equal(path, "/v1/passkeys/enrollment/finish");
      assert(f.claimed); assert(!f.committed);
      f.record = { passkey_id: KEY, tenant_id: TENANT, user_id: USER, rp_id: "cockpit.local.test",
        credential_id: body.credential_id as string, user_handle: f.userHandle, public_key: body.public_key as string,
        sign_count: body.sign_count as number, backup_eligible: body.backup_eligible as boolean,
        backed_up: body.backed_up as boolean, storage_version: 1, status: "active", enrollment_epoch: 4 };
      f.committed = true;
      const receipt = copy(f.record) as unknown as Record<string, unknown>;
      f.recordChange(receipt);
      await f.hook("finish");
      return receipt;
    },
    attempts: {
      async put(id, value) {
        assert(f.claimed, "API invitation claim must be committed before persisting the browser attempt");
        assert.equal(value.sessionExpiresAt, f.session.expiresAt);
        f.saved.push(value);
        await store.put(id, value);
        await f.hook("put");
      },
      async get(id) { const value = await store.get(id); await f.hook("get"); return value; },
      async consume(id) {
        f.consumes++;
        const value = await store.consume(id);
        await f.hook("consume");
        return value;
      },
    },
    now: () => f.clock,
    randomToken: token,
  };
  return { f, ports };
}
function registration(options: PublicKeyCredentialCreationOptionsJSON, overrides: { challenge?: string; flags?: number } = {}) {
  const { publicKey } = generateKeyPairSync("ec", { namedCurve: "prime256v1" });
  const jwk = publicKey.export({ format: "jwk" }), credentialId = randomBytes(32);
  const cose = new Map<number, number | Uint8Array>([[1, 2], [3, -7], [-1, 1],
    [-2, new Uint8Array(Buffer.from(jwk.x!, "base64url"))], [-3, new Uint8Array(Buffer.from(jwk.y!, "base64url"))]]);
  const length = Buffer.alloc(2); length.writeUInt16BE(credentialId.length);
  const rpHash = createHash("sha256").update(options.rp.id!).digest();
  const authData = Buffer.concat([rpHash, Buffer.from([overrides.flags ?? 0x45]), Buffer.alloc(4),
    Buffer.alloc(16), length, credentialId, isoCBOR.encode(cose)]);
  const attestation = new Map<string, string | Uint8Array | Map<string, never>>([
    ["fmt", "none"], ["authData", new Uint8Array(authData)], ["attStmt", new Map<string, never>()],
  ]);
  const client = Buffer.from(JSON.stringify({ type: "webauthn.create", challenge: overrides.challenge ?? options.challenge,
    origin: ORIGIN, crossOrigin: false }));
  return { id: b64(credentialId), rawId: b64(credentialId), type: "public-key",
    authenticatorAttachment: "platform", clientExtensionResults: { credProps: { rk: true } },
    response: { clientDataJSON: b64(client), attestationObject: b64(isoCBOR.encode(attestation)) } };
}
async function rejected(promise: Promise<unknown>) {
  await assert.rejects(promise, error => {
    assert.equal((error as Error).message, "PASSKEY_ENROLLMENT_REJECTED");
    assert.equal((error as Error).cause, undefined);
    return true;
  });
}

test("complete BFF enrollment commits claim, encrypts one attempt and verifies a real P256 candidate without changing OIDC claims", async t => {
  const { f, ports } = await fixture(t);
  const started = await beginEnrollmentFlow(ports, f.ticket);
  assert.deepEqual(Object.keys(started).sort(), ["attempt_id", "options"]);
  assert.equal(started.options.user.id, f.userHandle);
  assert.equal(started.options.rp.id, "cockpit.local.test");
  assert.equal(started.options.attestation, "none");
  const files = await readdir(f.directory);
  assert.equal(files.length, 1);
  const encrypted = await readFile(join(f.directory, files[0]), "utf8");
  assert(!encrypted.includes(f.ticket)); assert(!encrypted.includes(started.options.challenge));
  const input = registration(started.options);
  await finishEnrollmentFlow(ports, started.attempt_id, input);
  assert(f.committed); assert.equal(f.record!.credential_id, input.id);
  assert.equal(f.record!.status, "active"); assert.equal(f.record!.sign_count, 0);
  assert.equal(f.consumes, 1); assert.deepEqual(await readdir(f.directory), []);
  assert.deepEqual(f.requests.map(value => value.path),
    ["/v1/passkeys/enrollment/claim", "/v1/passkeys/enrollment/finish"]);
  for (const call of f.requests) assert.deepEqual(call.session, f.session);
  assert.equal(f.requests[0].body.session_binding, f.requests[1].body.session_binding);
  assert.equal(f.requests[1].body.claim_id, CLAIM);
  assert(!JSON.stringify(f.requests[1].body).includes(f.ticket));
  assert(f.sawPersistedFactor, "success requires an authoritative factor readback after the write");
  assert.equal(f.session.oidcAuthTime, f.clock - 300);
});

test("enrollment lifetime is capped by the original browser session expiry", async t => {
  const { f, ports } = await fixture(t);
  f.session.expiresAt = f.clock + 40;
  const result = await beginEnrollmentFlow(ports, f.ticket);
  assert.equal(result.options.timeout, 40_000);
  assert.equal(f.saved[0].expiresAt, f.clock + 40);
});

test("invalid tickets and absent or expired sessions cause no claim or attempt", async t => {
  const { f, ports } = await fixture(t);
  for (const value of [null, f.ticket + "=", token().slice(1), true, { token: f.ticket }]) {
    await rejected(beginEnrollmentFlow(ports, value));
  }
  f.session.expiresAt = f.clock;
  await rejected(beginEnrollmentFlow(ports, f.ticket));
  f.bound = null;
  await rejected(beginEnrollmentFlow(ports, f.ticket));
  assert.equal(f.requests.length, 0); assert.equal(f.saved.length, 0);
});

test("a foreign factor context rejects before claiming the invitation", async t => {
  const { f, ports } = await fixture(t);
  f.contextChange = value => { value.user_id = "foreign-user"; };
  await rejected(beginEnrollmentFlow(ports, f.ticket));
  assert.equal(f.requests.length, 0);
});

test("an already enrolled factor prevents any second invitation claim", async t => {
  const { f, ports } = await fixture(t), started = await beginEnrollmentFlow(ports, f.ticket);
  await finishEnrollmentFlow(ports, started.attempt_id, registration(started.options));
  f.ticket = token(); f.claimed = false;
  await rejected(beginEnrollmentFlow(ports, f.ticket));
  assert.equal(f.claimed, false); assert.equal(f.requests.length, 2);
});

for (const [field, value] of [
  ["tenant_id", "10000000-0000-0000-0000-000000000009"],
  ["user_id", "20000000-0000-0000-0000-000000000009"],
  ["auth_epoch", 5], ["rp_id", "foreign.local.test"], ["claim_id", "not-a-uuid"],
  ["user_handle", token() + "="], ["expires_at", "invalid"], ["expires_at", "1970-01-01T00:00:00Z"],
  ["private", "synthetic-never-publish"],
] as const) {
  test(`strict claim receipt rejects ${field} mismatch after durable invitation claim`, async t => {
    const { f, ports } = await fixture(t);
    f.claimChange = claim => { claim[field] = value; };
    await rejected(beginEnrollmentFlow(ports, f.ticket));
    assert(f.claimed); assert.equal(f.saved.length, 0); assert.equal(f.committed, false);
  });
}

for (const phase of ["claim", "put"]) {
  test(`session rotation while awaiting ${phase} cannot publish enrollment options`, async t => {
    const { f, ports } = await fixture(t);
    f.hook = async name => { if (name === phase) f.bound = { ...f.bound!, handle: token() }; };
    await rejected(beginEnrollmentFlow(ports, f.ticket));
    assert(f.claimed); assert.equal(f.committed, false);
  });
}

test("current session/CSRF/OIDC/epoch/origin/expiry are all bound before an attempt can be consumed", async t => {
  const { f, ports } = await fixture(t), started = await beginEnrollmentFlow(ports, f.ticket);
  const original = copy(f.bound!);
  for (const modify of [
    (value: EnrollmentSession) => ({ ...value, handle: token() }),
    (value: EnrollmentSession) => ({ ...value, session: { ...value.session, csrf: token() } }),
    (value: EnrollmentSession) => ({ ...value, session: { ...value.session, oidcAuthTime: value.session.oidcAuthTime + 1 } }),
    (value: EnrollmentSession) => ({ ...value, session: { ...value.session, authEpoch: 5 } }),
    (value: EnrollmentSession) => ({ ...value, origin: "https://foreign.local.test:8443" }),
    (value: EnrollmentSession) => ({ ...value, session: { ...value.session, expiresAt: value.session.expiresAt + 1 } }),
  ]) {
    f.bound = modify(copy(original));
    await rejected(finishEnrollmentFlow(ports, started.attempt_id, registration(started.options)));
    assert.equal(f.consumes, 0);
    assert(await f.store.get(started.attempt_id), "foreign context cannot burn another browser's attempt");
  }
  f.bound = original;
  await finishEnrollmentFlow(ports, started.attempt_id, registration(started.options));
  assert(f.committed);
});

test("malformed or wrong-challenge registration burns the matching attempt and cannot be retried", async t => {
  const { f, ports } = await fixture(t), started = await beginEnrollmentFlow(ports, f.ticket);
  await rejected(finishEnrollmentFlow(ports, started.attempt_id, registration(started.options, { challenge: token() })));
  assert.equal(f.consumes, 1); assert.equal(await f.store.get(started.attempt_id), null);
  await rejected(finishEnrollmentFlow(ports, started.attempt_id, registration(started.options)));
  assert.equal(f.committed, false);
});

test("concurrent complete callbacks can consume and persist a registration only once", async t => {
  const { f, ports } = await fixture(t), started = await beginEnrollmentFlow(ports, f.ticket);
  const input = registration(started.options);
  const results = await Promise.allSettled([
    finishEnrollmentFlow(ports, started.attempt_id, input), finishEnrollmentFlow(ports, started.attempt_id, input),
  ]);
  assert.equal(results.filter(value => value.status === "fulfilled").length, 1);
  assert.equal(results.filter(value => value.status === "rejected").length, 1);
  assert.equal(f.requests.filter(value => value.path.endsWith("/finish")).length, 1);
  assert(f.committed);
});

test("crash after atomic consume leaves no attempt and cannot reopen the consumed claim", async t => {
  const { f, ports } = await fixture(t), started = await beginEnrollmentFlow(ports, f.ticket);
  f.hook = async phase => { if (phase === "consume") throw new Error("synthetic crash"); };
  await rejected(finishEnrollmentFlow(ports, started.attempt_id, registration(started.options)));
  assert.equal(await f.store.get(started.attempt_id), null); assert.equal(f.committed, false);
  f.hook = async () => {};
  await rejected(finishEnrollmentFlow(ports, started.attempt_id, registration(started.options)));
  await rejected(beginEnrollmentFlow(ports, f.ticket));
});

test("legacy or tampered stored attempts missing original session expiry fail closed without consume", async t => {
  const { f, ports } = await fixture(t), started = await beginEnrollmentFlow(ports, f.ticket);
  const stored = copy(f.saved[0]) as unknown as Record<string, unknown>;
  delete stored.sessionExpiresAt;
  await f.store.put(started.attempt_id, stored as unknown as StoredEnrollmentAttempt);
  await rejected(finishEnrollmentFlow(ports, started.attempt_id, registration(started.options)));
  assert.equal(f.consumes, 0); assert.equal(f.committed, false);
});

for (const phase of ["get", "consume", "context:5", "context:6"]) {
  test(`context rotation at ${phase} prevents persistence after an asynchronous boundary`, async t => {
    const { f, ports } = await fixture(t), started = await beginEnrollmentFlow(ports, f.ticket);
    f.hook = async name => { if (name === phase) f.bound = { ...f.bound!, session: { ...f.bound!.session, csrf: token() } }; };
    await rejected(finishEnrollmentFlow(ports, started.attempt_id, registration(started.options)));
    assert.equal(f.committed, false);
  });
}

test("expiry during callback reads or crypto context work fails before the API write", async t => {
  const { f, ports } = await fixture(t), started = await beginEnrollmentFlow(ports, f.ticket);
  f.hook = async phase => { if (phase === "context:6") f.clock += 120; };
  await rejected(finishEnrollmentFlow(ports, started.attempt_id, registration(started.options)));
  assert.equal(f.committed, false); assert.equal(await f.store.get(started.attempt_id), null);
});

test("new factor or epoch while registration is being checked prevents the API write", async t => {
  const { f, ports } = await fixture(t), started = await beginEnrollmentFlow(ports, f.ticket);
  f.contextChange = value => { if (f.contexts === 6) value.auth_epoch = 5; };
  await rejected(finishEnrollmentFlow(ports, started.attempt_id, registration(started.options)));
  assert.equal(f.committed, false);
});

for (const [field, value] of [
  ["status", "revoked"], ["storage_version", 2], ["enrollment_epoch", 5],
  ["credential_id", token()], ["user_handle", token()], ["public_key", token()],
  ["sign_count", 1], ["backup_eligible", true], ["backed_up", true],
  ["private", "synthetic-never-publish"],
] as const) {
  test(`finish receipt ${field} mismatch never publishes success after possible commit`, async t => {
    const { f, ports } = await fixture(t), started = await beginEnrollmentFlow(ports, f.ticket);
    f.recordChange = valueRecord => { valueRecord[field] = value; };
    await rejected(finishEnrollmentFlow(ports, started.attempt_id, registration(started.options)));
    assert(f.committed); assert.equal(await f.store.get(started.attempt_id), null);
  });
}

for (const change of ["session", "origin", "expiry", "factor"]) {
  test(`post-write ${change} change prevents publishing a stale successful registration`, async t => {
    const { f, ports } = await fixture(t), started = await beginEnrollmentFlow(ports, f.ticket);
    f.hook = async phase => {
      if (phase !== "finish") return;
      if (change === "session") f.bound = { ...f.bound!, handle: token() };
      if (change === "origin") f.bound = { ...f.bound!, origin: "https://foreign.local.test:8443" };
      if (change === "expiry") f.clock += 120;
      if (change === "factor") f.record = { ...f.record!, status: "revoked", storage_version: 2 };
    };
    await rejected(finishEnrollmentFlow(ports, started.attempt_id, registration(started.options)));
    assert(f.committed); assert.equal(await f.store.get(started.attempt_id), null);
  });
}

test("session rotation during authoritative post-write readback prevents publishing success", async t => {
  const { f, ports } = await fixture(t), started = await beginEnrollmentFlow(ports, f.ticket);
  f.hook = async phase => {
    if (phase === "context:7") f.bound = { ...f.bound!, session: { ...f.bound!.session, csrf: token() } };
  };
  await rejected(finishEnrollmentFlow(ports, started.attempt_id, registration(started.options)));
  assert(f.committed); assert(f.sawPersistedFactor);
});

test("authoritative post-write readback must agree with the exact saved factor", async t => {
  const { f, ports } = await fixture(t), started = await beginEnrollmentFlow(ports, f.ticket);
  f.contextChange = value => {
    if (f.contexts === 7) value.credential = { ...f.record!, sign_count: 1, storage_version: 2 };
  };
  await rejected(finishEnrollmentFlow(ports, started.attempt_id, registration(started.options)));
  assert(f.committed); assert(f.sawPersistedFactor);
});

test("registered synced zero-counter candidates retain backup state without granting an action", async t => {
  const { f, ports } = await fixture(t), started = await beginEnrollmentFlow(ports, f.ticket);
  await finishEnrollmentFlow(ports, started.attempt_id, registration(started.options, { flags: 0x5d }));
  assert.equal(f.record!.sign_count, 0); assert.equal(f.record!.backup_eligible, true);
  assert.equal(f.record!.backed_up, true);
  assert.equal(f.requests.length, 2); assert(!f.requests.some(value => value.path.includes("action")));
});
