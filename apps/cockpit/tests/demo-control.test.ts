import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, rm, readFile, writeFile, chmod, symlink, link, readdir } from "node:fs/promises";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { createRequire } from "node:module";
import ts from "typescript";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import * as controls from "../src/lib/demo-control-contract.ts";
import * as states from "../src/lib/demo-control-state.ts";
import * as signals from "../src/lib/demo-signals-contract.ts";
import * as authorized from "../src/lib/authorized-session.ts";
import * as ids from "../src/lib/credential-action-contracts.ts";
import * as objects from "../src/lib/passkey-enrollment-state.ts";
import * as metadata from "../src/lib/demo-trading-credential-action-contracts.ts";
import * as security from "../src/lib/security.ts";
import * as bodyReader from "../src/lib/demo-btc-order-consent.ts";
const id = (n: number) => `00000000-0000-0000-0000-${String(n).padStart(12, "0")}`;
const b: states.DemoControlBinding = { tenant_id: id(1), account_id: id(2), user_id: id(3), subject: "synthetic",
  auth_epoch: 1, connection_id: id(4), credential_revision: 1, storage_version: 1 };
const NOW = 1800000000, secret = "synthetic-control-secret-of-at-least-32-bytes";
const request = (revision = 0, action: "start" | "pause" = "start") =>
  ({ expected_revision: revision, action, basket_limit: 3, assets: ["BTCUSDT", "ETHUSDT"] });
async function fixture(t: test.TestContext) {
  const root = await mkdtemp(join(tmpdir(), "investalo-demo-control-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  const directory = join(root, "control");
  return { root, directory, store: new states.DemoControlStore(directory, secret),
    file: join(directory, `${b.tenant_id}.${b.account_id}.json`) };
}
test("actual fsync/readback start, restart, pause and resume preserve user settings without enabling orders", async t => {
  const x = await fixture(t);
  assert.equal((await x.store.summary(b)).status, "not_started");
  const start = await x.store.change(b, request(), NOW, async () => {});
  assert.equal(start.status, "start_requested"); assert.equal(start.execution_enabled, false);
  const restarted = new states.DemoControlStore(x.directory, secret);
  assert.deepEqual(await restarted.summary(b), start);
  assert.equal((await restarted.change(b, request(1, "pause"), NOW+1, async () => {})).status, "paused");
  assert.equal((await restarted.change(b, request(2), NOW+2, async () => {})).revision, 3);
  assert.doesNotMatch(await readFile(x.file, "utf8"), /access_token|csrf|session_binding|api_key|passphrase/);
  assert.doesNotMatch(JSON.stringify(start), /user_id|subject|connection_id|storage_version/);
});
test("epoch, actor, native connection and key version changes invalidate the earlier start", async t => {
  const x = await fixture(t);
  await x.store.change(b, request(), NOW, async () => {});
  for (const changed of [{ auth_epoch: 2 }, { user_id: id(9) }, { subject: "other" },
    { connection_id: id(9) }, { storage_version: 2 }]) {
    const current = { ...b, ...changed };
    assert.equal((await x.store.summary(current)).status, "authorization_changed");
  }
  const current = { ...b, auth_epoch: 2 };
  assert.equal((await x.store.change(current, request(1, "pause"), NOW+1, async () => {})).status, "paused");
});
test("stale duplicate and concurrent commands cannot replace the persisted choice", async t => {
  const x = await fixture(t);
  let entered!: () => void, release!: () => void;
  const reached = new Promise<void>(r => { entered = r; }), wait = new Promise<void>(r => { release = r; });
  const writing = x.store.change(b, request(), NOW, async () => { entered(); await wait; });
  await reached;
  await assert.rejects(x.store.change(b, request(), NOW, async () => {}));
  release(); await writing;
  await assert.rejects(x.store.change(b, request(), NOW, async () => {}));
  assert.equal((await x.store.summary(b)).revision, 1);
});
test("revocation at final publication guard leaves old state and removes uncommitted temporary file", async t => {
  const x = await fixture(t);
  await x.store.change(b, request(), NOW, async () => {});
  const original = await readFile(x.file);
  await assert.rejects(x.store.change(b, request(1, "pause"), NOW+1, async () => { throw new Error("revoked"); }));
  assert.deepEqual(await readFile(x.file), original);
  assert.deepEqual(await readdir(x.directory), [x.file.split("/").at(-1)]);
});
test("modified intent, different signing material and copied account file fail closed", async t => {
  const x = await fixture(t);
  await x.store.change(b, request(), NOW, async () => {});
  await assert.rejects(new states.DemoControlStore(x.directory, secret+"foreign").summary(b));
  const raw = await readFile(x.file, "utf8"), wire = JSON.parse(raw);
  wire.payload = wire.payload.replace('"action":"start"', '"action":"pause"');
  await writeFile(x.file, JSON.stringify(wire));
  await assert.rejects(x.store.summary(b));
  await writeFile(x.file, raw);
  const foreign = { ...b, account_id: id(9) };
  await writeFile(join(x.directory, `${b.tenant_id}.${foreign.account_id}.json`), raw, { mode: 0o600 });
  await assert.rejects(x.store.summary(foreign));
});
test("private permissions, symlink and hardlink checks protect persisted start requests", async t => {
  const x = await fixture(t);
  await x.store.change(b, request(), NOW, async () => {});
  await chmod(x.file, 0o644); await assert.rejects(x.store.summary(b)); await chmod(x.file, 0o600);
  await link(x.file, join(x.directory, "second"));
  await assert.rejects(x.store.summary(b)); await rm(join(x.directory, "second"));
  await rm(x.file); await symlink(join(x.root, "foreign"), x.file);
  await assert.rejects(x.store.summary(b));
});
test("exact Demo settings reject live/fixed leverage overrides, empty/foreign candidates and unsafe revisions", () => {
  const value = { ...request(), confirmation: controls.DEMO_START_CONFIRMATION };
  assert.deepEqual(controls.parseControlInput(value), request());
  for (const patch of [{ leverage: 10 }, { live_enabled: true }, { confirmation: "other" },
    { basket_limit: 2 }, { basket_limit: 8 }, { assets: [] }, { assets: ["BTCUSDT", "BTCUSDT"] },
    { assets: ["SBTCSUSDT"] }, { expected_revision: -1 }, { expected_revision: Number.MAX_SAFE_INTEGER }]) {
    assert.throws(() => controls.parseControlInput({ ...value, ...patch }));
  }
});
const require = createRequire(import.meta.url);
function load(path: string, inject: Record<string, unknown>) {
  const compiled = ts.transpileModule(readFileSync(new URL(path, import.meta.url), "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const module = { exports: {} as any };
  new Function("require", "module", "exports", compiled)(
    (name: string) => Object.hasOwn(inject, name) ? inject[name] : require(name), module, module.exports);
  return module.exports;
}
async function httpFixture(t: test.TestContext) {
  const x = await fixture(t), globalKey = Symbol.for("investalo.demo-h1-control-store/1");
  const old = process.env.COCKPIT_DEMO_H1_CONTROL;
  process.env.COCKPIT_DEMO_H1_CONTROL = "1"; delete (globalThis as any)[globalKey];
  t.after(() => { delete (globalThis as any)[globalKey];
    if (old === undefined) delete process.env.COCKPIT_DEMO_H1_CONTROL; else process.env.COCKPIT_DEMO_H1_CONTROL = old; });
  const now = Math.floor(Date.now()/1000), origin = "https://cockpit.investalo.de";
  const f = { current: { handle: "synthetic-original-handle", session: { tenantId: b.tenant_id, subject: b.subject,
    issuer: "https://auth.cockpit.investalo.de", authEpoch: 1, oidcAuthTime: now-60, expiresAt: now+3600,
    csrf: Buffer.alloc(32, 1).toString("base64url") } } as any, role: "owner", reads: 0, revoked: false,
    mutate: () => {}, user: b.user_id, identities: 0 };
  const server = load("../src/lib/demo-control-server.ts", {
    "server-only": {}, "./auth.ts": { getBoundSession: async () => f.current },
    "./config.ts": { getConfig: async () => ({ origin, stateDir: x.root, sessionSecret: secret }) },
    "./authorized-session.ts": authorized, "./credential-action-contracts.ts": ids,
    "./passkey-enrollment-state.ts": objects, "./demo-control-state.ts": states, "./demo-control-contract.ts": controls,
    "./security.ts": security, "./demo-btc-order-consent.ts": bodyReader,
    "./demo-trading-credential-action-contracts.ts": metadata,
    "./demo-trading-passkey-credential-browser-server.ts": { runtime: async () => ({
      accountId: b.account_id, check: async () => {}, identity: { forSession: (_s: unknown, user: string) => {
        f.identities++; if (user !== b.user_id) throw new Error(); return {}; } },
    }) },
    "./backend.ts": { apiRequest: async (_s: unknown, path: string) => {
      f.reads++;
      if (path === "/v1/me") return { user: { id: f.user, subject: b.subject, auth_epoch: b.auth_epoch },
        memberships: [{ tenant_id: b.tenant_id, tenant_name: "synthetic", role: f.role }], live_enabled: false };
      f.mutate();
      return { tenant_id: b.tenant_id, auth_epoch: 1, purpose: "demo_futures_spot_trading",
        profile: "bitget-classic-demo-trading-secret/1", environment: "demo",
        account: { id: b.account_id, name: "Demo", broker: "bitget", mode: "bitget_demo", currency: "USDT", status: "ready" },
        connection: { connection_id: b.connection_id, credential_revision: 1, storage_version: 1,
          status: f.revoked ? "revoked" : "active" }, key_authorities: ["coow", "cpow", "stow"] };
    } },
  });
  const req = (action?: "start" | "pause", revision = 0) => new Request("http://0.0.0.0:3000/api/bitget-demo/control", {
    method: action ? "POST" : "GET", headers: { origin, "sec-fetch-site": "same-origin",
      ...(action ? { "Content-Type": "application/json", "X-CSRF-Token": f.current?.session.csrf ?? "" } : {}) },
    ...(action ? { body: JSON.stringify({ ...request(revision, action),
      confirmation: action === "start" ? controls.DEMO_START_CONFIRMATION : "pause" }) } : {}) });
  return { x, f, server, req };
}
test("actual BFF GET/start/pause use original proxy session, current role/key and durable store", async t => {
  const { server, req } = await httpFixture(t);
  const initial = await server.handleDemoControl(req());
  assert.equal(initial.status, 200); assert.equal((await initial.json()).revision, 0);
  const start = await server.handleDemoControl(req("start"));
  assert.equal(start.status, 200); assert.equal(start.headers.get("cache-control"), "no-store");
  assert.equal((await start.json()).status, "start_requested");
  const stale = await server.handleDemoControl(req("pause"));
  assert.equal(stale.status, 503);
  assert.equal((await (await server.handleDemoControl(req("pause", 1))).json()).status, "paused");
});
test("anonymous, disabled, foreign browser, CSRF, queries, viewers and foreign pilot cannot write", async t => {
  const { f, server, req } = await httpFixture(t);
  const original = f.current;
  f.current = null; assert.equal((await server.handleDemoControl(req())).status, 401); f.current = original;
  process.env.COCKPIT_DEMO_H1_CONTROL = "0";
  assert.equal((await server.handleDemoControl(req("start"))).status, 404);
  process.env.COCKPIT_DEMO_H1_CONTROL = "1";
  for (const [header, value] of [["origin", "https://foreign.invalid"], ["sec-fetch-site", "cross-site"],
    ["x-csrf-token", "foreign"]]) {
    const input = req("start"); input.headers.set(header, value);
    assert.equal((await server.handleDemoControl(input)).status, 503); assert.equal(input.bodyUsed, false);
  }
  const query = new Request(req().url+"?mode=live", { headers: req().headers });
  assert.equal((await server.handleDemoControl(query)).status, 503);
  f.role = "viewer";
  assert.equal((await server.handleDemoControl(req("start"))).status, 503);
  f.role = "owner"; f.user = id(9);
  assert.equal((await server.handleDemoControl(req("start"))).status, 503);
});
test("key revoked during body intake denies publication; changed session after commit requires status recovery", async t => {
  const { x, f, server, req } = await httpFixture(t);
  let count = 0;
  f.mutate = () => { if (++count === 2) f.revoked = true; };
  assert.equal((await server.handleDemoControl(req("start"))).status, 503);
  assert.equal((await new states.DemoControlStore(join(x.root, "demo-h1-control"), secret).summary(b)).revision, 0);
  f.revoked = false; count = 0;
  f.mutate = () => { if (++count === 3) f.current.handle = "changed-original-handle"; };
  assert.equal((await server.handleDemoControl(req("start"))).status, 503);
  // Request was committed once before final BFF publication failed. GET recovers it.
  f.mutate = () => {};
  const current = await server.handleDemoControl(req());
  assert.equal(current.status, 200); assert.equal((await current.json()).revision, 1);
});
test("browser contract refuses false activation and another tenant; initial view stays explicit", async t => {
  const x = await fixture(t), result = await x.store.summary(b);
  assert.throws(() => controls.parseDemoControl({ ...result, execution_enabled: true }, b.tenant_id, b.account_id));
  assert.throws(() => controls.parseDemoControl(result, id(9), b.account_id));
  const view = load("../src/components/demo-control.tsx", {
    "../lib/demo-signals-contract": signals, "../lib/demo-control-contract": controls,
  });
  const html = renderToStaticMarkup(React.createElement(view.DemoControlPanel, {
    tenantId: b.tenant_id, accountId: b.account_id, csrf: "synthetic",
  }));
  assert.match(html, /NOCH NICHT GESTARTET/); assert.match(html, /Demo-Start anfordern/);
  assert.match(html, /Pausieren/); assert.match(html, /Eigenkapital-Margin/);
  assert.match(html, /Handelsworker wird noch angebunden/);
  assert.doesNotMatch(html, /DEMOHANDEL AKTIV/);
});
