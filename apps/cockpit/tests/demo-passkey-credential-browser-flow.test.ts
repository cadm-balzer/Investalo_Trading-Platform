import assert from "node:assert/strict";
import { createHash, generateKeyPairSync, randomBytes, randomUUID, sign } from "node:crypto";
import test from "node:test";
import { isoCBOR } from "@simplewebauthn/server/helpers";
import {
  createDemoPasskeyCredentialBrowserFlow, type DemoPasskeyCredentialBrowserOptions,
} from "../src/lib/demo-passkey-credential-browser-flow.ts";
import { buildBrowserCredentialBody } from "../src/lib/credential-browser-body.ts";
import { actionProofBinding, type DemoActionProofAttempt, type DemoActionProofGrant,
  type ProofSession } from "../src/lib/demo-passkey-action-proof-state.ts";
import type { DemoCredentialAction, DemoCredentialActionMetadata } from "../src/lib/demo-credential-action-contracts.ts";
import type { PasskeyContext } from "../src/lib/passkey-enrollment-state.ts";
import type { DemoPasskeyCredentialPorts, DemoSafeOnboardingResult } from "../src/lib/demo-passkey-credential-flow.ts";
import { DEMO_PASSKEY_CREDENTIAL_KIND } from "../src/lib/demo-passkey-credential-token.ts";
import { handleDemoPasskeyCredentialHttp, type DemoCredentialHttpRequests } from "../src/lib/demo-passkey-credential-http.ts";
import { jwtVerify } from "jose";
import { createDemoCredentialPrivateIdentity } from "../src/lib/demo-credential-private-identity.ts";
import { createDemoCredentialPrivateProvider } from "../src/lib/demo-credential-private-provider.ts";
import { demoTlsFixture, identityFixture } from "./helpers/demo-private-identity-fixture.ts";

const id = (n: number) => `00000000-0000-0000-0000-${n.toString().padStart(12, "0")}`;
const TENANT = id(1), USER = id(2), ACCOUNT = id(3), CONNECTION = id(4), FACTOR = id(5);
const RP = "cockpit.fixture.invalid", ORIGIN = `https://${RP}:8443`;
const token = () => randomBytes(32).toString("base64url");
const hash = (value: string | Uint8Array) => createHash("sha256").update(value).digest();
const clone = <T>(value: T): T => structuredClone(value);
const TRIPLE = Object.freeze({ api_key: "synthetic-browser-api", secret: "synthetic-browser-secret-ß",
  passphrase: "synthetic-browser-passphrase" });
const CONSENT = Object.freeze({ kind: "demo-credential-write" as const, confirmed: true as const });
const rejected = (error: unknown) => {
  assert.equal((error as Error).message, "DEMO_PASSKEY_CREDENTIAL_BROWSER_FLOW_REJECTED");
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
function fixture(action: DemoCredentialAction = "register",
  options: Partial<DemoPasskeyCredentialBrowserOptions> = {}) {
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
    metadata: { tenant_id: TENANT, auth_epoch: 4, purpose: "demo_read_only", profile: "bitget-classic-demo-read-secret/1", environment: "demo", account: { id: ACCOUNT, name: "Synthetic account",
      broker: "bitget", mode: "bitget_demo", currency: "USDT", status: "ready" },
      connection: action === "register" ? null : { connection_id: CONNECTION,
        credential_revision: 1, storage_version: 3, status: "active" } } as DemoCredentialActionMetadata,
    attempt: null as DemoActionProofAttempt | null, grant: null as DemoActionProofGrant | null,
    authorization: randomUUID(), bodyHash: "", offset: 0, attemptLifetime: 120,
    events: [] as string[], requests: [] as unknown[], executed: 0,
    hooks: new Map<string, () => void | Promise<void>>(),
  };
  const now = () => Math.floor(Date.now() / 1000) + state.offset;
  const ports: DemoPasskeyCredentialPorts = {
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
          auth_epoch: 4, rp_id: RP, target: body.target as DemoActionProofAttempt["target"],
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
          kind: DEMO_PASSKEY_CREDENTIAL_KIND, authorization_id: state.authorization, proof_id: attempt.attempt_id,
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
      const result: DemoSafeOnboardingResult = { connection_id: CONNECTION,
        credential_revision: target.action === "register" ? 1 :
          1,
        storage_version: target.action === "register" ? 1 : target.expected_storage + 1,
        status: target.action === "revoke" ? "revoked" : "active" };
      state.metadata = { ...state.metadata, connection: result };
      await state.hooks.get("execute")?.();
      return result;
    },
  };
  const flow = createDemoPasskeyCredentialBrowserFlow({
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

for (const action of ["register", "revoke"] as const) {
  test(`own HTTP/P256/${action} composes private files and actual mTLS with synthetic API/executor`, async t => {
    const x = fixture(action);
    let signing: Uint8Array;
    const tls = await demoTlsFixture(t, (request, response) => {
      const chunks: Buffer[] = [];
      request.on("data", value => chunks.push(value));
      request.on("end", () => {
        void (async () => {
          assert.equal((request.socket as import("node:tls").TLSSocket).authorized, true);
          const body = Buffer.concat(chunks).toString("utf8");
          const signed = (request.headers.authorization ?? "").replace(/^Bearer /, "");
          const { payload } = await jwtVerify(signed, signing, {
            issuer: "investalo-bff", audience: "investalo-credentials-demo-passkey",
          });
          const context = JSON.parse(Buffer.from(
            request.headers["x-investalo-credential-context"] as string, "base64url").toString());
          assert.equal(payload.authorization_kind, DEMO_PASSKEY_CREDENTIAL_KIND);
          assert.equal(payload.body_sha256, hash(body).toString("hex"));
          assert.equal(payload.htm, "POST");
          assert.equal(payload.htu, `/v1/credentials/bitget-demo/${action}`);
          assert.equal(context.user_id, USER);
          assert.equal(context.oidc_auth_time, x.state.bound.session.oidcAuthTime);
          assert.equal(context.session_binding, actionProofBinding(x.state.bound));
          assert.equal(request.url, `/v1/credentials/bitget-demo/${action}`);
          assert.deepEqual(payload.target, x.state.grant!.target);
          assert.equal(body, buildBrowserCredentialBody(x.state.grant!.target,
            action === "revoke" ? undefined : TRIPLE));
          // Synthetic receipt model only: no PG consume or native broker claim.
          x.state.executed++;
          const result = { connection_id: CONNECTION, credential_revision: 1,
            storage_version: action === "register" ? 1 : 4, status: action === "register" ? "active" : "revoked" };
          x.state.metadata = { ...x.state.metadata, connection: result as DemoCredentialActionMetadata["connection"] };
          const output = JSON.stringify(result);
          response.writeHead(200, { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(output) });
          response.end(output);
        })().catch(() => { response.writeHead(500); response.end(); });
      });
    });
    const files = await identityFixture(t, tls.origin);
    signing = files.signing;
    const identity = await createDemoCredentialPrivateIdentity(files.spec, x.now);
    const ports = await createDemoCredentialPrivateProvider({
      authorized: x.state.bound, identity, current: x.ports.current, now: x.now,
      randomToken: token, randomUuid: () => CONNECTION,
      api: async (session, path, options) => {
        if (path === "/v1/passkeys/context") return x.ports.context(session);
        if (path === `/v1/bitget-demo/credential-actions/${ACCOUNT}`) return x.ports.metadata(session, ACCOUNT);
        return x.ports.request(session, path, JSON.parse(options.body!));
      },
    });
    const flow = createDemoPasskeyCredentialBrowserFlow({ portsFor: () => ports, now: x.now,
      randomToken: token, acceptCredentials: () => true });
    async function post(phase: "start" | "finish" | "execute", input: unknown) {
      const request = new Request(`${ORIGIN}/api/credentials/bitget-demo/passkey/${phase}`, {
        method: "POST", headers: { "Content-Type": "application/json", Origin: ORIGIN,
          "Sec-Fetch-Site": "same-origin", "X-CSRF-Token": x.state.bound.session.csrf },
        body: JSON.stringify(input),
      });
      return handleDemoPasskeyCredentialHttp(request, phase, {
        enabled: () => true, origin: async () => ORIGIN, session: async () => x.state.bound, now: x.now,
        execute: async (input, authorized) => {
          if (phase === "start") {
            const body = input as DemoCredentialHttpRequests["start"];
            return flow.start(authorized, body.platform_account_id, body.action, body.credentials);
          }
          if (phase === "finish") {
            const body = input as DemoCredentialHttpRequests["finish"];
            return flow.finish(authorized, body.flow_token, body.credential);
          }
          const body = input as DemoCredentialHttpRequests["execute"];
          return flow.execute(authorized, body.flow_token, body.body, body.consent);
        },
      });
    }
    const started = await post("start", { platform_account_id: ACCOUNT, action,
      ...(action === "register" ? { credentials: TRIPLE } : {}) });
    assert.equal(started.status, 200);
    const prepared = await started.json();
    const finished = await post("finish", { flow_token: prepared.flow_token,
      credential: x.assertion(prepared.options.challenge) });
    assert.equal(finished.status, 200);
    const grant = await finished.json(), input = { flow_token: grant.flow_token,
      body: buildBrowserCredentialBody(prepared.preview.target, action === "revoke" ? undefined : TRIPLE),
      consent: CONSENT };
    assert.equal((await post("execute", input)).status, 200);
    assert.equal((await post("execute", input)).status, 400);
    assert.equal(x.state.executed, 1);
  });

  test(`own browser HTTP ${action} reaches actual P256 verification, own consent and one executor dispatch`, async () => {
    const x = fixture(action);
    async function post<P extends keyof DemoCredentialHttpRequests>(phase: P, input: DemoCredentialHttpRequests[P]) {
      const request = new Request(`${ORIGIN}/api/credentials/bitget-demo/passkey/${phase}`, {
        method: "POST", headers: { Origin: ORIGIN, "Sec-Fetch-Site": "same-origin",
          "X-CSRF-Token": x.state.bound.session.csrf, "Content-Type": "application/json" },
        body: JSON.stringify(input),
      });
      return handleDemoPasskeyCredentialHttp(request, phase, {
        enabled: () => true, origin: async () => ORIGIN, session: async () => clone(x.state.bound), now: x.now,
        execute: async (value, bound) => {
          if (phase === "start") {
            const start = value as DemoCredentialHttpRequests["start"];
            return x.flow.start(bound, start.platform_account_id, start.action, start.credentials);
          }
          if (phase === "finish") {
            const finish = value as DemoCredentialHttpRequests["finish"];
            return x.flow.finish(bound, finish.flow_token, finish.credential);
          }
          const execute = value as DemoCredentialHttpRequests["execute"];
          return x.flow.execute(bound, execute.flow_token, execute.body, execute.consent);
        },
      });
    }
    const start = await post("start", { platform_account_id: ACCOUNT, action,
      ...(action === "register" ? { credentials: TRIPLE } : {}) });
    assert.equal(start.status, 200);
    const prepared = await start.json();
    assert.equal(JSON.stringify(prepared).includes(TRIPLE.secret), false);
    const finish = await post("finish", { flow_token: prepared.flow_token,
      credential: x.assertion(prepared.options.challenge) });
    assert.equal(finish.status, 200);
    const grant = await finish.json();
    const input = { flow_token: grant.flow_token,
      body: buildBrowserCredentialBody(prepared.preview.target, action === "register" ? TRIPLE : undefined),
      consent: CONSENT };
    const execute = await post("execute", input);
    assert.equal(execute.status, 200);
    assert.equal((await execute.json()).credential_revision, 1);
    assert.equal(x.state.executed, 1);
    assert.equal((await post("execute", input)).status, 400);
    assert.equal(x.state.executed, 1);
  });

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
      wrong === "consent" ? { kind: "demo-credential-write", confirmed: false } as never : CONSENT), rejected);
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
  const flow = createDemoPasskeyCredentialBrowserFlow({
    portsFor: () => ({ ...x.ports, secret: TRIPLE.secret }), now: x.now,
    randomToken: token, acceptCredentials: () => true,
  });
  await assert.rejects(flow.start(x.state.bound, ACCOUNT, "register", TRIPLE), rejected);
  assert.deepEqual(x.state.events, []);
  const base = { portsFor: () => x.ports, now: x.now, randomToken: token, acceptCredentials: () => true };
  for (const change of [{ acceptCredentials: undefined }, { capacity: 0 }, { capacity: 129 },
    { perSession: 0 }, { perSession: 9 }, { capacity: 1, perSession: 2 }, { secret: TRIPLE.secret }]) {
    assert.throws(() => createDemoPasskeyCredentialBrowserFlow({ ...base, ...change } as never), rejected);
  }
});
