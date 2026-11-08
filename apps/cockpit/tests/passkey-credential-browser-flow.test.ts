import assert from "node:assert/strict";
import { createHash, generateKeyPairSync, randomBytes, randomUUID, sign } from "node:crypto";
import test from "node:test";
import { isoCBOR } from "@simplewebauthn/server/helpers";
import {
  createPasskeyCredentialBrowserFlow, type PasskeyCredentialBrowserOptions,
} from "../src/lib/passkey-credential-browser-flow.ts";
import { buildBrowserCredentialBody } from "../src/lib/credential-browser-body.ts";
import { actionProofBinding, type ActionProofAttempt, type ActionProofGrant,
  type ProofSession } from "../src/lib/passkey-action-proof-state.ts";
import type { CredentialAction, CredentialActionMetadata } from "../src/lib/credential-action-contracts.ts";
import type { PasskeyContext } from "../src/lib/passkey-enrollment-state.ts";
import type { PasskeyCredentialPorts, SafeOnboardingResult } from "../src/lib/passkey-credential-flow.ts";
import { PASSKEY_CREDENTIAL_KIND } from "../src/lib/passkey-credential-token.ts";

const id = (n: number) => `00000000-0000-0000-0000-${n.toString().padStart(12, "0")}`;
const TENANT = id(1), USER = id(2), ACCOUNT = id(3), CONNECTION = id(4), FACTOR = id(5);
const RP = "cockpit.fixture.invalid", ORIGIN = `https://${RP}:8443`;
const token = () => randomBytes(32).toString("base64url");
const hash = (value: string | Uint8Array) => createHash("sha256").update(value).digest();
const clone = <T>(value: T): T => structuredClone(value);
const TRIPLE = Object.freeze({ api_key: "synthetic-browser-api", secret: "synthetic-browser-secret-ß",
  passphrase: "synthetic-browser-passphrase" });
const CONSENT = Object.freeze({ kind: "credential-write" as const, confirmed: true as const });
const rejected = (error: unknown) => {
  assert.equal((error as Error).message, "PASSKEY_CREDENTIAL_BROWSER_FLOW_REJECTED");
  assert.equal((error as Error).cause, undefined);
  return true;
};
function barrier() {
  let open!: () => void, entered!: () => void;
  const pending = new Promise<void>(resolve => { open = resolve; });
  const reached = new Promise<void>(resolve => { entered = resolve; });
  return { open, reached, wait: async () => { entered(); await pending; } };
}

/** Real P256 verification/signing; fake API models only this wrapper's effects. */
function fixture(action: CredentialAction = "register",
  options: Partial<PasskeyCredentialBrowserOptions> = {}) {
  const started = Math.floor(Date.now() / 1000), { publicKey, privateKey } =
    generateKeyPairSync("ec", { namedCurve: "prime256v1" });
  const jwk = publicKey.export({ format: "jwk" });
  const cose = isoCBOR.encode(new Map<number, number | Uint8Array>([
    [1, 2], [3, -7], [-1, 1], [-2, Buffer.from(jwk.x!, "base64url")], [-3, Buffer.from(jwk.y!, "base64url")],
  ]));
  const state = {
    bound: { handle: token(), origin: ORIGIN, session: { subject: "synthetic-browser-subject",
      issuer: "https://idp.fixture.invalid", oidcAuthTime: started - 3600, tenantId: TENANT,
      authEpoch: 4, expiresAt: started + 1800, csrf: token(), displayName: "Fixture", tenantName: "Fixture" } } as ProofSession,
    context: { tenant_id: TENANT, user_id: USER, auth_epoch: 4, rp_id: RP,
      credential: { passkey_id: FACTOR, tenant_id: TENANT, user_id: USER, rp_id: RP,
        credential_id: token(), user_handle: token(), public_key: Buffer.from(cose).toString("base64url"),
        sign_count: 0, backup_eligible: false, backed_up: false, storage_version: 1,
        status: "active", enrollment_epoch: 4 } } as PasskeyContext,
    metadata: { tenant_id: TENANT, auth_epoch: 4, account: { id: ACCOUNT, name: "Synthetic account",
      broker: "bitget", mode: "read_only", status: action === "register" ? "disconnected" : "ready" },
      connection: action === "register" ? null : { connection_id: CONNECTION,
        credential_revision: 2, storage_version: 3, status: "active" } } as CredentialActionMetadata,
    attempt: null as ActionProofAttempt | null, grant: null as ActionProofGrant | null,
    authorization: randomUUID(), bodyHash: "", offset: 0, attemptLifetime: 120,
    events: [] as string[], requests: [] as unknown[], executed: 0,
    hooks: new Map<string, () => void | Promise<void>>(),
  };
  const now = () => Math.floor(Date.now() / 1000) + state.offset;
  const ports: PasskeyCredentialPorts = {
    now, randomToken: token, randomUuid: () => CONNECTION,
    current: async () => { await state.hooks.get("current")?.(); return clone(state.bound); },
    context: async () => clone(state.context),
    metadata: async () => clone(state.metadata),
    request: async (session, path, body) => {
      const event = path.split("/").at(-1)!;
      state.events.push(event); state.requests.push(clone(body));
      assert.equal(body.session_binding, actionProofBinding(state.bound));
      let value: unknown;
      if (event === "prepare") {
        state.bodyHash = body.body_sha256 as string;
        state.attempt = { attempt_id: randomUUID(), tenant_id: TENANT, user_id: USER,
          auth_epoch: 4, rp_id: RP, target: body.target as ActionProofAttempt["target"],
          metadata: clone(state.metadata), credential: clone(state.context.credential!),
          session_binding: body.session_binding as string, challenge: body.challenge as string,
          confirmation_hash: body.confirmation_hash as string, prepared_at: now(),
          expires_at: now() + state.attemptLifetime, session_expires_at: session.expiresAt };
        value = { authorization_id: state.authorization, metadata_sha256: "c".repeat(64), attempt: clone(state.attempt) };
      } else if (event === "claim") {
        value = clone(state.attempt);
      } else if (event === "finish") {
        state.context = { ...state.context, credential: { ...state.context.credential!,
          sign_count: body.new_counter as number, backed_up: false, storage_version: 2 } };
        state.grant = { grant_id: randomUUID(), attempt_id: state.attempt!.attempt_id, tenant_id: TENANT,
          user_id: USER, auth_epoch: 4, rp_id: RP, target: state.attempt!.target,
          metadata: state.attempt!.metadata, passkey_id: FACTOR, passkey_version: 2,
          session_binding: state.attempt!.session_binding, confirmation_hash: state.attempt!.confirmation_hash,
          checked_at: body.checked_at as number, expires_at: (body.checked_at as number) + 120,
          session_expires_at: session.expiresAt };
        value = clone(state.grant);
      } else if (event === "grant") {
        value = clone(state.grant);
      } else if (event === "authorize") {
        const grant = state.grant!, attempt = state.attempt!;
        value = { status: "authorized", execution_enabled: false, authorization: {
          kind: PASSKEY_CREDENTIAL_KIND, authorization_id: state.authorization, proof_id: attempt.attempt_id,
          grant_id: grant.grant_id, tenant_id: TENANT, user_id: USER, subject: session.subject,
          auth_epoch: 4, oidc_issuer: session.issuer, oidc_auth_time: session.oidcAuthTime, rp_id: RP,
          origin: ORIGIN, session_binding: grant.session_binding, session_expires_at: session.expiresAt,
          passkey_id: FACTOR, passkey_version: 2, target: grant.target, prepared_at: attempt.prepared_at,
          checked_at: grant.checked_at, authorized_at: now(), expires_at: grant.expires_at,
          metadata_sha256: "c".repeat(64), body_sha256: state.bodyHash,
        } };
      } else throw new Error("SYNTHETIC_PRIVATE_API_FAILURE");
      await state.hooks.get(event)?.();
      return value;
    },
    credentialKey: async () => { state.events.push("key"); return new Uint8Array(32).fill(41); },
    execute: async (_signed, body) => {
      state.events.push("execute"); state.executed++;
      assert.equal(body, buildBrowserCredentialBody(state.grant!.target,
        action === "revoke" ? undefined : TRIPLE));
      const target = state.grant!.target;
      const result: SafeOnboardingResult = { connection_id: CONNECTION,
        credential_revision: target.action === "register" ? 1 :
          target.expected_revision + (target.action === "replace" ? 1 : 0),
        storage_version: target.action === "register" ? 1 : target.expected_storage + 1,
        status: target.action === "revoke" ? "revoked" : "active" };
      state.metadata = { ...state.metadata, connection: result };
      await state.hooks.get("execute")?.();
      return result;
    },
  };
  const flow = createPasskeyCredentialBrowserFlow({
    portsFor: () => ports, now, randomToken: token,
    acceptCredentials: (kind, triple) => kind === "revoke" ? triple === undefined :
      JSON.stringify(triple) === JSON.stringify(TRIPLE),
    ...options,
  });
  const start = () => flow.start(state.bound, ACCOUNT, action, action === "revoke" ? undefined : TRIPLE);
  function assertion(challenge: string) {
    const client = Buffer.from(JSON.stringify({ type: "webauthn.get", challenge, origin: ORIGIN, crossOrigin: false }));
    const count = Buffer.alloc(4); count.writeUInt32BE(1);
    const data = Buffer.concat([hash(RP), Buffer.from([0x05]), count]);
    return { id: state.context.credential!.credential_id, rawId: state.context.credential!.credential_id,
      type: "public-key", clientExtensionResults: {}, response: {
        clientDataJSON: client.toString("base64url"), authenticatorData: data.toString("base64url"),
        signature: sign("sha256", Buffer.concat([data, hash(client)]), privateKey).toString("base64url"),
        userHandle: state.context.credential!.user_handle,
      } };
  }
  async function proved() {
    const prepared = await start();
    const granted = await flow.finish(state.bound, prepared.flow_token, assertion(prepared.options.challenge));
    const body = buildBrowserCredentialBody(prepared.preview.target, action === "revoke" ? undefined : TRIPLE);
    return { prepared, granted, body };
  }
  return { state, ports, flow, now, start, assertion, proved };
}

for (const action of ["register", "replace", "revoke"] as const) {
  test(`browser ${action}: rotates handles, explicit consent and exact private body`, async () => {
    const x = fixture(action), { prepared, granted, body } = await x.proved();
    assert.notEqual(granted.flow_token, prepared.flow_token);
    assert.equal(granted.grant.execution_enabled, false);
    assert(granted.grant.expiresAt <= prepared.preview.expiresAt);
    assert.deepEqual(Object.keys(prepared).sort(), ["flow_token", "options", "preview"]);
    assert.deepEqual(Object.keys(granted).sort(), ["flow_token", "grant"]);
    for (const value of [prepared, granted, ...x.state.requests]) {
      assert.equal(JSON.stringify(value).includes(TRIPLE.secret), false);
      assert.equal(JSON.stringify(value).includes(TRIPLE.api_key), false);
      assert.equal(JSON.stringify(value).includes(TRIPLE.passphrase), false);
    }
    const result = await x.flow.execute(x.state.bound, granted.flow_token, body, CONSENT);
    assert.equal(result.status, action === "revoke" ? "revoked" : "active");
    assert.equal(x.state.executed, 1);
    await assert.rejects(x.flow.execute(x.state.bound, granted.flow_token, body, CONSENT), rejected);
    assert.equal(x.state.executed, 1);
    assert(!x.state.events.includes("confirm"));
  });
}

test("unaccepted keys and revoke with a triple reject before preparation/provider reads", async () => {
  const x = fixture();
  await assert.rejects(x.flow.start(x.state.bound, ACCOUNT, "register", { ...TRIPLE, secret: "other" }), rejected);
  await assert.rejects(x.flow.start(x.state.bound, ACCOUNT, "revoke", TRIPLE), rejected);
  assert.deepEqual(x.state.events, []);
});

test("start reservations enforce capacity before slow current/API awaits", async () => {
  const x = fixture("register", { capacity: 1, perSession: 1 }), gate = barrier();
  x.state.hooks.set("current", gate.wait);
  const first = x.start();
  await gate.reached;
  try {
    await assert.rejects(x.start(), rejected);
    assert.equal(x.state.events.includes("prepare"), false);
  } finally { gate.open(); }
  const prepared = await first;
  x.flow.cancel(x.state.bound, prepared.flow_token);
  assert.equal((await x.start()).preview.target.action, "register");
});

test("per-binding capacity and global capacity count independent in-flight starts", async () => {
  const x = fixture("register", { capacity: 2, perSession: 1 }), gate = barrier();
  x.state.hooks.set("current", gate.wait);
  const first = x.start();
  await gate.reached;
  const other = { ...x.state.bound, handle: token() };
  // The provider is intentionally bound to the initial actor, so this second
  // reservation will fail after release, but holds global capacity meanwhile.
  const second = x.flow.start(other, ACCOUNT, "register", TRIPLE);
  try {
    await assert.rejects(x.start(), rejected);
    await assert.rejects(x.flow.start({ ...other, handle: token() }, ACCOUNT, "register", TRIPLE), rejected);
  } finally { gate.open(); }
  const prepared = await first;
  await assert.rejects(second, rejected);
  x.flow.cancel(x.state.bound, prepared.flow_token);
});

test("foreign handle, CSRF, epoch, original OIDC or origin cannot consume the owner's handle", async () => {
  const x = fixture(), prepared = await x.start();
  const variants = [
    { ...x.state.bound, handle: token() },
    { ...x.state.bound, session: { ...x.state.bound.session, csrf: token() } },
    { ...x.state.bound, session: { ...x.state.bound.session, authEpoch: 5 } },
    { ...x.state.bound, session: { ...x.state.bound.session, oidcAuthTime: x.state.bound.session.oidcAuthTime + 1 } },
    { ...x.state.bound, origin: "https://other.fixture.invalid" },
  ];
  for (const bound of variants) {
    await assert.rejects(x.flow.finish(bound, prepared.flow_token, {}), rejected);
    assert.throws(() => x.flow.cancel(bound, prepared.flow_token), rejected);
  }
  assert(!x.state.events.includes("claim"));
  const grant = await x.flow.finish(x.state.bound, prepared.flow_token, x.assertion(prepared.options.challenge));
  assert.notEqual(grant.flow_token, prepared.flow_token);
});

test("parallel finish consumes handle before committed claim or verification awaits", async () => {
  const x = fixture("register", { capacity: 1, perSession: 1 }), prepared = await x.start(), gate = barrier();
  x.state.hooks.set("claim", gate.wait);
  const first = x.flow.finish(x.state.bound, prepared.flow_token, x.assertion(prepared.options.challenge));
  await gate.reached;
  try {
    await assert.rejects(x.flow.finish(x.state.bound, prepared.flow_token, {}), rejected);
    await assert.rejects(x.start(), rejected);
    assert.throws(() => x.flow.cancel(x.state.bound, prepared.flow_token), rejected);
    assert.equal(x.state.events.filter(event => event === "claim").length, 1);
  } finally { gate.open(); }
  await first;
});

test("malformed owner assertion burns continuation and matching durable claim exactly once", async () => {
  const x = fixture(), prepared = await x.start();
  await assert.rejects(x.flow.finish(x.state.bound, prepared.flow_token, {}), rejected);
  await assert.rejects(x.flow.finish(x.state.bound, prepared.flow_token,
    x.assertion(prepared.options.challenge)), rejected);
  assert.equal(x.state.events.filter(event => event === "claim").length, 1);
  assert(!x.state.events.includes("authorize"));
});

for (const wrong of ["body", "consent"] as const) {
  test(`owner ${wrong} rejection consumes grant handle without authorizing`, async () => {
    const x = fixture(), { granted, body } = await x.proved();
    await assert.rejects(x.flow.execute(x.state.bound, granted.flow_token,
      wrong === "body" ? body + " " : body,
      wrong === "consent" ? { kind: "credential-write", confirmed: false } as never : CONSENT), rejected);
    await assert.rejects(x.flow.execute(x.state.bound, granted.flow_token, body, CONSENT), rejected);
    assert(!x.state.events.includes("authorize"));
  });
}

test("pending execution holds admission until actual promise settles, even after expiry", async () => {
  const x = fixture("register", { capacity: 1, perSession: 1 }), { granted, body } = await x.proved(), gate = barrier();
  x.state.hooks.set("execute", gate.wait);
  const execution = x.flow.execute(x.state.bound, granted.flow_token, body, CONSENT);
  await gate.reached;
  try {
    x.state.offset = 121;
    await assert.rejects(x.start(), rejected);
    await assert.rejects(x.flow.execute(x.state.bound, granted.flow_token, body, CONSENT), rejected);
    assert.equal(x.state.executed, 1);
  } finally { gate.open(); }
  await assert.rejects(execution, rejected);
});

test("unknown execution response is terminal and never dispatches another attempt", async () => {
  const x = fixture(), { granted, body } = await x.proved();
  x.state.hooks.set("execute", () => { throw new Error("synthetic-secret-private-response"); });
  await assert.rejects(x.flow.execute(x.state.bound, granted.flow_token, body, CONSENT), rejected);
  await assert.rejects(x.flow.execute(x.state.bound, granted.flow_token, body, CONSENT), rejected);
  assert.equal(x.state.executed, 1);
});

test("expiry sweep releases stored continuation but never extends its preparation deadline", async () => {
  const x = fixture("register", { capacity: 1, perSession: 1 });
  x.state.attemptLifetime = 100;
  const { prepared, granted } = await x.proved();
  assert.equal(granted.grant.expiresAt, prepared.preview.expiresAt);
  assert(granted.grant.expiresAt < x.state.grant!.expires_at);
  x.state.offset = 100;
  await assert.rejects(x.flow.execute(x.state.bound, granted.flow_token, "", CONSENT), rejected);
  assert(!x.state.events.includes("authorize"));
  assert.equal((await x.start()).preview.target.action, "register");
});

test("expired in-flight preparation keeps capacity until it fails, then permits a fresh start", async () => {
  const x = fixture("register", { capacity: 1, perSession: 1 }), gate = barrier();
  x.state.hooks.set("prepare", gate.wait);
  const first = x.start();
  await gate.reached;
  try {
    x.state.offset = 120;
    await assert.rejects(x.start(), rejected);
  } finally { gate.open(); }
  await assert.rejects(first, rejected);
  x.state.hooks.delete("prepare"); x.state.offset = 0;
  assert.equal((await x.start()).preview.execution_enabled, false);
});

test("owner cancellation releases capacity and leaves the old handle terminal", async () => {
  const x = fixture("register", { capacity: 1, perSession: 1 }), prepared = await x.start();
  x.flow.cancel(x.state.bound, prepared.flow_token);
  assert.throws(() => x.flow.cancel(x.state.bound, prepared.flow_token), rejected);
  await assert.rejects(x.flow.finish(x.state.bound, prepared.flow_token, {}), rejected);
  assert.equal((await x.start()).preview.target.action, "register");
});

test("continuation store cannot be restored by JSON or another factory", async () => {
  const x = fixture(), prepared = JSON.parse(JSON.stringify(await x.start()));
  const other = fixture();
  await assert.rejects(other.flow.finish(x.state.bound, prepared.flow_token, {}), rejected);
  assert.deepEqual(Object.keys(x.flow).sort(), ["cancel", "execute", "finish", "start"]);
  assert.equal(JSON.stringify(x.flow), "{}");
});

test("trusted random collisions fail closed without reusing a consumed handle", async () => {
  const fixed = token(), x = fixture("register", { randomToken: () => fixed });
  const prepared = await x.start();
  await assert.rejects(x.flow.finish(x.state.bound, prepared.flow_token,
    x.assertion(prepared.options.challenge)), rejected);
  await assert.rejects(x.flow.finish(x.state.bound, prepared.flow_token, {}), rejected);
});

test("private data fields in ports and invalid provider/admission configuration reject statically", async () => {
  const x = fixture();
  const flow = createPasskeyCredentialBrowserFlow({
    portsFor: () => ({ ...x.ports, secret: TRIPLE.secret }), now: x.now,
    randomToken: token, acceptCredentials: () => true,
  });
  await assert.rejects(flow.start(x.state.bound, ACCOUNT, "register", TRIPLE), rejected);
  assert.deepEqual(x.state.events, []);
  const base = { portsFor: () => x.ports, now: x.now, randomToken: token, acceptCredentials: () => true };
  for (const change of [{ acceptCredentials: undefined }, { capacity: 0 }, { capacity: 129 },
    { perSession: 0 }, { perSession: 9 }, { capacity: 1, perSession: 2 }, { secret: TRIPLE.secret }]) {
    assert.throws(() => createPasskeyCredentialBrowserFlow({ ...base, ...change } as never), rejected);
  }
});
