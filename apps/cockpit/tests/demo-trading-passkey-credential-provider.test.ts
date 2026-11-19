import assert from "node:assert/strict";
import { randomBytes } from "node:crypto";
import test from "node:test";
import {
  createDemoTradingPasskeyCredentialPorts, type DemoTradingCredentialProviderOptions,
} from "../src/lib/demo-trading-passkey-credential-provider.ts";
import { now, id } from "./fixtures/demo-trading-passkey-credential-fixture.ts";
import type { DemoTradingCredentialActionMetadata } from "../src/lib/demo-trading-credential-action-contracts.ts";
import type { ProofSession } from "../src/lib/demo-trading-passkey-action-proof-state.ts";

function fixture() {
  const token = () => randomBytes(32).toString("base64url");
  const bound: ProofSession = { handle: token(), origin: "https://cockpit.fixture.invalid",
    session: { issuer: "https://idp.fixture.invalid", subject: "original-subject",
      tenantId: id(1), authEpoch: 0, oidcAuthTime: now - 3600, expiresAt: now + 200,
      csrf: token(), displayName: "Fixture", tenantName: "Fixture" } };
  const metadata: DemoTradingCredentialActionMetadata = { tenant_id: id(1), auth_epoch: 0,
    purpose: "demo_futures_spot_trading", profile: "bitget-classic-demo-trading-secret/1", environment: "demo",
    account: { id: id(2), name: "Own DemoTrading", broker: "bitget", mode: "bitget_demo",
      currency: "USDT", status: "ready" }, connection: null, key_authorities: null };
  const f = { bound, actual: structuredClone(bound), offset: 0, metadata,
    calls: [] as { session: unknown; path: string; options: unknown }[], keys: 0, executions: 0,
    after: () => {}, executionError: false };
  const options: DemoTradingCredentialProviderOptions = {
    authorized: bound, current: async () => f.actual, now: () => now + f.offset,
    api: async (session, path, options) => {
      f.calls.push({ session, path, options }); f.after();
      return structuredClone(f.metadata);
    },
    credentialKey: async () => { f.keys++; f.after(); return new Uint8Array(32).fill(17); },
    execute: async () => {
      f.executions++; f.after();
      if (f.executionError) throw new Error("synthetic unknown completion");
      return { connection_id: id(3), credential_revision: 1, storage_version: 1, status: "active" };
    },
    randomToken: token, randomUuid: () => id(3),
  };
  return { f, options, ports: createDemoTradingPasskeyCredentialPorts(options) };
}

test("own GET reader binds immutable original principal and exact DemoTrading metadata", async () => {
  const { f, ports } = fixture();
  const session = structuredClone(f.bound.session);
  const result = await ports.metadata(session, id(2));
  assert.deepEqual(result, f.metadata);
  assert.deepEqual(f.calls, [{ session, path: `/v1/bitget-demo-trading/credential-actions/${id(2)}`,
    options: { method: "GET" } }]);
  assert.ok(Object.isFrozen(f.calls[0].session));
  assert.ok(Object.isFrozen(result));
  assert.equal(f.keys + f.executions, 0);
});

for (const change of ["mode", "tenant", "account", "epoch", "private"]) {
  test(`own GET projection rejects ${change}`, async () => {
    const { f, ports } = fixture();
    const value = f.metadata as unknown as Record<string, unknown>;
    const account = value.account as Record<string, unknown>;
    if (change === "mode") account.mode = "read_only";
    if (change === "account") account.id = id(9);
    if (change === "tenant") value.tenant_id = id(9);
    if (change === "epoch") value.auth_epoch = 1;
    if (change === "private") value.envelope = "synthetic private";
    await assert.rejects(ports.metadata(f.bound.session, id(2)));
    assert.equal(f.keys + f.executions, 0);
  });
}
for (const change of ["subject", "tenantId", "authEpoch", "oidcAuthTime", "expiresAt", "csrf", "handle", "origin"]) {
  test(`changed original ${change} blocks before dispatch and after asynchronous read`, async () => {
    const { f, ports } = fixture();
    const mutate = () => {
      const actual = f.actual as unknown as Record<string, unknown>;
      const session = actual.session as Record<string, unknown>;
      if (change === "handle") actual.handle = randomBytes(32).toString("base64url");
      else if (change === "origin") actual.origin = "https://foreign.fixture.invalid";
      else session[change] = change === "subject" ? "foreign-subject"
        : change === "tenantId" ? id(9) : change === "csrf" ? randomBytes(32).toString("base64url")
        : (session[change] as number) + 1;
    };
    mutate();
    await assert.rejects(ports.metadata(f.bound.session, id(2)));
    assert.equal(f.calls.length, 0);
    f.actual = structuredClone(f.bound);
    f.after = mutate;
    await assert.rejects(ports.metadata(f.bound.session, id(2)));
    assert.equal(f.calls.length, 1);
  });
}

test("foreign caller principal is rejected before any API dispatch", async () => {
  const { f, ports } = fixture();
  await assert.rejects(ports.metadata({ ...f.bound.session, oidcAuthTime: now }, id(2)));
  await assert.rejects(ports.metadata(f.bound.session, "../private"));
  assert.equal(f.calls.length, 0);
});

test("only own proof/consent POST paths are forwarded, preserving the original principal", async () => {
  const { f, ports } = fixture();
  for (const action of ["prepare", "claim", "finish", "grant", "authorize"]) {
    await ports.request(f.bound.session, `/v1/bitget-demo-trading/passkey-authorizations/${action}`, { opaque: "digest" });
  }
  assert.equal(f.calls.length, 5);
  assert.ok(f.calls.every(call => JSON.stringify(call.options) ===
    JSON.stringify({ method: "POST", body: '{"opaque":"digest"}' })));
  for (const path of ["/v1/passkey-action-proofs/claim", "/v1/credential-actions/private",
    "/v1/bitget-demo-trading/passkey-authorizations/authorize?retry=1",
    "/v1/credentials/bitget-demo-trading/register"]) {
    await assert.rejects(ports.request(f.bound.session, path, {}));
  }
  assert.equal(f.calls.length, 5);
});

test("trusted callbacks and original session are captured before caller mutation", async () => {
  const { f, options, ports } = fixture();
  (options as unknown as Record<string, unknown>).api = () => { throw new Error("replacement"); };
  (f.bound.session as unknown as Record<string, unknown>).subject = "mutated";
  assert.equal((await ports.metadata(f.actual.session, id(2)) as DemoTradingCredentialActionMetadata).account.id, id(2));
  assert.equal((f.calls[0].session as ProofSession["session"]).subject, "original-subject");
});

test("expiry during trusted key acquisition or execution suppresses success", async () => {
  for (const phase of ["key", "execute"]) {
    const { f, ports } = fixture();
    f.after = () => { f.offset = 200; };
    await assert.rejects(phase === "key" ? ports.credentialKey() : ports.execute("synthetic", "unchanged"));
    assert.equal(f.keys + f.executions, 1);
    assert.equal(f.calls.length, 0);
  }
});

test("unknown private completion is propagated once without API/body forwarding or retry", async () => {
  const { f, ports } = fixture();
  f.executionError = true;
  await assert.rejects(ports.execute("synthetic", "unchanged"));
  assert.equal(f.executions, 1);
  assert.equal(f.calls.length, 0);
});
