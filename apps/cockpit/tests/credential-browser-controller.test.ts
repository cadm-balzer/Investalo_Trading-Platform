import assert from "node:assert/strict";
import test from "node:test";
import { CredentialBrowserController, type CredentialBrowserPorts } from "../src/lib/credential-browser-controller.ts";
import { buildBrowserCredentialBody } from "../src/lib/credential-browser-body.ts";
import type { ActionTarget } from "../src/lib/credential-action-contracts.ts";

const account = "10000000-0000-0000-0000-000000000001", connection = "20000000-0000-0000-0000-000000000002";
const initialNow = 1_800_000_000, rp = "cockpit.local.test";
const triple = { api_key: "synthetic-key-sentinel", secret: "synthetic-secret-sentinel", passphrase: "synthetic-passphrase-sentinel" };
function deferred<T>() {
  let resolve!: (value: T) => void, reject!: (reason: unknown) => void;
  const promise = new Promise<T>((ok, no) => { resolve = ok; reject = no; });
  return { promise, resolve, reject };
}
function fixture(action: "register" | "replace" | "revoke" = "register",
  override: Partial<CredentialBrowserPorts> = {}) {
  let now = initialNow;
  const target: ActionTarget = action === "register" ? { action, platform_account_id: account, connection_id: connection }
    : { action, platform_account_id: account, connection_id: connection, expected_revision: 3, expected_storage: 6 };
  const start = { flow_token: Buffer.alloc(32, 1).toString("base64url"), preview: {
    target, accountName: "Synthetic account", expiresAt: initialNow + 120, execution_enabled: false,
  }, options: { rpId: rp, challenge: Buffer.alloc(32, 2).toString("base64url"), timeout: 120_000,
    allowCredentials: [{ id: Buffer.alloc(32, 3).toString("base64url"), type: "public-key" }], userVerification: "required" } };
  const finish = { flow_token: Buffer.alloc(32, 4).toString("base64url"), grant: { target,
    accountName: start.preview.accountName, checkedAt: initialNow, expiresAt: initialNow + 120, execution_enabled: false } };
  const result = { connection_id: connection, credential_revision: action === "register" ? 1 : action === "replace" ? 4 : 3,
    storage_version: action === "register" ? 1 : 7, status: action === "revoke" ? "revoked" : "active" };
  const calls: { phase: string; body: Record<string, unknown>; signal: AbortSignal }[] = [];
  const controller = new CredentialBrowserController({
    rpId: rp, now: () => now,
    async authenticate() { return { signed: true }; },
    async post(phase, body, signal) {
      calls.push({ phase, body, signal });
      return phase === "start" ? start : phase === "finish" ? finish : result;
    },
    ...override,
  });
  return { controller, calls, target, start, finish, result, setNow: (value: number) => { now = value; } };
}
for (const action of ["register", "replace", "revoke"] as const) {
  test(`page controller ${action} requires separate consent and preserves exact private body`, async () => {
    const f = fixture(action);
    await f.controller.prepare(account, action, action === "revoke" ? undefined : triple);
    assert.equal(f.controller.snapshot().phase, "prepared");
    const safe = JSON.stringify(f.controller.snapshot());
    for (const secret of [...Object.values(triple), f.start.flow_token]) assert.equal(safe.includes(secret), false);
    await f.controller.execute(true);
    assert.equal(f.calls.some(call => call.phase === "execute"), false);
    await f.controller.assertPasskey();
    await f.controller.execute(false);
    assert.equal(f.calls.some(call => call.phase === "execute"), false);
    await f.controller.execute(true);
    const execution = f.calls.find(call => call.phase === "execute")!;
    assert.equal(execution.body.body, buildBrowserCredentialBody(f.target, action === "revoke" ? undefined : triple));
    assert.deepEqual(execution.body.consent, { kind: "credential-write", confirmed: true });
    assert.equal(f.controller.snapshot().phase, "complete");
    assert.deepEqual(f.controller.snapshot().result, f.result);
    await f.controller.execute(true);
    await f.controller.prepare(account, action, action === "revoke" ? undefined : triple);
    assert.equal(f.calls.filter(call => call.phase === "execute").length, 1);
    assert.equal(f.calls.filter(call => call.phase === "start").length, 1);
  });
}
test("page controller blocks duplicate prepares while a response is outstanding", async () => {
  const gate = deferred<unknown>();
  let calls = 0;
  const f = fixture("register", { async post() { calls++; return gate.promise; } });
  const first = f.controller.prepare(account, "register", triple);
  await f.controller.prepare(account, "register", triple);
  assert.equal(calls, 1);
  gate.resolve(f.start); await first;
  assert.equal(f.controller.snapshot().phase, "prepared");
});
test("abandoning preparation aborts its signal and ignores late replies", async () => {
  const gate = deferred<unknown>();
  let signal!: AbortSignal;
  const f = fixture("register", { async post(_phase, _body, received) { signal = received; return gate.promise; } });
  const pending = f.controller.prepare(account, "register", triple);
  f.controller.abandon();
  assert.equal(signal.aborted, true);
  gate.resolve(f.start); await pending;
  assert.equal(f.controller.snapshot().phase, "input");
  await f.controller.assertPasskey(); await f.controller.execute(true);
  assert.equal(f.controller.snapshot().preview, null);
});
test("leaving during authenticator interaction prevents a later finish request", async () => {
  const gate = deferred<unknown>();
  const f = fixture("register", { authenticate: async () => gate.promise });
  await f.controller.prepare(account, "register", triple);
  const pending = f.controller.assertPasskey();
  f.controller.abandon(); gate.resolve({ signed: true }); await pending;
  assert.deepEqual(f.calls.map(call => call.phase), ["start"]);
  assert.equal(f.controller.snapshot().phase, "input");
});
test("expired preview clears state and cannot trigger authenticator or execute", async () => {
  let authentications = 0;
  const f = fixture("register", { async authenticate() { authentications++; return {}; } });
  await f.controller.prepare(account, "register", triple);
  f.setNow(initialNow + 120); f.controller.expire();
  await f.controller.assertPasskey(); await f.controller.execute(true);
  assert.equal(f.controller.snapshot().phase, "failed");
  assert.equal(f.controller.snapshot().preview, null);
  assert.equal(authentications, 0);
  assert.deepEqual(f.calls.map(call => call.phase), ["start"]);
});
test("unknown execution response remains terminal and is never claimed to be rolled back", async () => {
  const f = fixture();
  const gate = deferred<unknown>();
  let executions = 0;
  const unknown = fixture("register", { async post(phase) {
    if (phase === "start") return f.start;
    if (phase === "finish") return f.finish;
    executions++; return gate.promise;
  } });
  await unknown.controller.prepare(account, "register", triple);
  await unknown.controller.assertPasskey();
  const pending = unknown.controller.execute(true);
  await unknown.controller.execute(true);
  gate.reject(new Error("synthetic private failure sentinel")); await pending;
  await unknown.controller.execute(true);
  assert.equal(executions, 1);
  assert.equal(unknown.controller.snapshot().phase, "failed");
  assert.match(unknown.controller.snapshot().message, /Ergebnis nicht bestätigt/);
  assert.equal(unknown.controller.snapshot().message.includes("failure sentinel"), false);
  assert.equal(unknown.controller.snapshot().result, null);
});
test("expiry during execution ignores late success and preserves uncertain outcome", async () => {
  const normal = fixture(), gate = deferred<unknown>();
  let now = initialNow;
  const f = fixture("register", { now: () => now, async post(phase) {
    return phase === "start" ? normal.start : phase === "finish" ? normal.finish : gate.promise;
  } });
  await f.controller.prepare(account, "register", triple); await f.controller.assertPasskey();
  const pending = f.controller.execute(true);
  now += 120; f.controller.expire();
  gate.resolve(normal.result); await pending;
  assert.equal(f.controller.snapshot().phase, "failed");
  assert.match(f.controller.snapshot().message, /Ergebnis nicht bestätigt/);
  assert.equal(f.controller.snapshot().result, null);
});
test("disposed controller drops late private state without publishing", async () => {
  const gate = deferred<unknown>();
  const f = fixture("register", { async post() { return gate.promise; } });
  let updates = 0;
  f.controller.subscribe(() => { updates++; });
  const pending = f.controller.prepare(account, "register", triple);
  f.controller.dispose();
  const before = updates;
  gate.resolve(f.start); await pending;
  assert.equal(updates, before);
  await f.controller.execute(true);
  assert.equal(updates, before);
});
test("revoke carrying credentials is rejected before any request", async () => {
  const f = fixture("revoke");
  await f.controller.prepare(account, "revoke", triple);
  assert.deepEqual(f.calls, []);
  assert.equal(f.controller.snapshot().phase, "failed");
});
