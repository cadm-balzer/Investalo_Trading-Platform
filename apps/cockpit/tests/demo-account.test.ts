import test, { afterEach } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import ts from "typescript";
import * as contract from "../src/lib/demo-account-contract.ts";
import * as authorization from "../src/lib/authorized-session.ts";
import * as metadataContract from "../src/lib/demo-trading-credential-action-contracts.ts";
import * as objectContract from "../src/lib/passkey-enrollment-state.ts";
import * as uuidContract from "../src/lib/credential-action-contracts.ts";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import https from "node:https";
import { createHash, createHmac } from "node:crypto";
import * as proof from "../src/lib/demo-trading-passkey-action-proof-state.ts";
import { demoTlsFixture } from "./helpers/demo-trading-private-identity-fixture.ts";
import { SYNTHETIC_DEMO_TLS } from "./helpers/demo-private-tls-material.ts";

const require = createRequire(import.meta.url);
const originalFlag = process.env.COCKPIT_DEMO_ACCOUNT_SYNC;
afterEach(() => {
  if (originalFlag === undefined) delete process.env.COCKPIT_DEMO_ACCOUNT_SYNC;
  else process.env.COCKPIT_DEMO_ACCOUNT_SYNC = originalFlag;
});
function load(path: string, inject: Record<string, unknown>) {
  const compiled = ts.transpileModule(readFileSync(new URL(path, import.meta.url), "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const module = { exports: {} as any };
  new Function("require", "module", "exports", compiled)(
    (name: string) => Object.hasOwn(inject, name) ? inject[name] : require(name), module, module.exports);
  return module.exports;
}
const id = (n: number) => `00000000-0000-0000-0000-${String(n).padStart(12, "0")}`;
function view(): contract.DemoAccount {
  return { schema: "investalo-demo-account/1", tenant_id: id(1), account_id: id(2),
    observed_at: new Date().toISOString(), currency: "USDT", wallet: { equity: "50000.25",
      available: "49000", locked: null, unrealized_pnl: "-100", isolated_margin: "1000", crossed_margin: "0" },
    positions: [{ symbol: "BTCUSDT", side: "long", quantity: "0.1", entry_price: "60000", mark_price: "59000",
      unrealized_pnl: "-100", leverage: "2", margin_mode: "isolated", liquidation_price: null }] };
}
test("contract preserves exact decimals, unknown fields and nullable liquidation price", () => {
  const original = view();
  assert.deepEqual(contract.parseDemoAccount(original, id(1), id(2)), original);
  const empty = view(); empty.positions = [];
  assert.deepEqual(contract.parseDemoAccount(empty, id(1)).positions, []);
});
test("foreign tenants/accounts, private fields and malformed numbers cannot reach the UI", () => {
  const cases = [() => ({ ...view(), tenant_id: id(9) }), () => ({ ...view(), account_id: id(9) }),
    () => ({ ...view(), envelope: "private" }), () => ({ ...view(), wallet: { ...view().wallet, equity: "NaN" } }),
    () => ({ ...view(), positions: [...view().positions, ...view().positions] }),
    () => ({ ...view(), positions: [{ ...view().positions[0], symbol: "<script>" }] })];
  for (const make of cases) assert.throws(() => contract.parseDemoAccount(make(), id(1), id(2)));
});
function fixture() {
  process.env.COCKPIT_DEMO_ACCOUNT_SYNC = "1";
  delete (globalThis as any)[Symbol.for("investalo.demo-account-cache/1")];
  const session = { tenantId: id(1), subject: "synthetic", issuer: "https://idp.fixture.invalid", authEpoch: 3,
    oidcAuthTime: Math.floor(Date.now()/1000)-3600, csrf: Buffer.alloc(32, 7).toString("base64url"),
    expiresAt: Math.floor(Date.now()/1000)+3600 };
  const f = { current: { handle: "fixture-handle", session } as any, reads: 0, revoked: false,
    mutate: () => {}, fail: false };
  const metadata = () => ({ tenant_id: id(1), auth_epoch: 3, purpose: "demo_futures_spot_trading",
    profile: "bitget-classic-demo-trading-secret/1", environment: "demo",
    account: { id: id(2), name: "Demo", broker: "bitget", mode: "bitget_demo", currency: "USDT", status: "ready" },
    connection: { connection_id: id(3), credential_revision: 1, storage_version: 1,
      status: f.revoked ? "revoked" : "active" }, key_authorities: ["coow", "cpow", "stow"] });
  const server = load("../src/lib/demo-account-server.ts", {
    "server-only": {}, "./auth.ts": { getBoundSession: async () => f.current },
    "./config.ts": { getConfig: async () => ({ origin: "https://cockpit.fixture.invalid" }) },
    "./authorized-session.ts": authorization, "./passkey-enrollment-state.ts": objectContract,
    "./credential-action-contracts.ts": uuidContract, "./demo-account-contract.ts": contract,
    "./demo-trading-credential-action-contracts.ts": metadataContract,
    "./backend.ts": { apiRequest: async (_session: unknown, path: string) => path === "/v1/me" ?
      { user: { id: id(4), subject: "synthetic", auth_epoch: 3 },
        memberships: [{ tenant_id: id(1), tenant_name: "fixture", role: "owner" }], live_enabled: false } : metadata() },
    "./demo-trading-passkey-credential-browser-server.ts": { runtime: async () => ({
      accountId: id(2), check: async () => {}, identity: { readAccount: async () => {
        f.reads++; f.mutate(); if (f.fail) throw new Error("private broker details"); return view();
      } },
    }) },
  });
  const request = () => new Request("https://cockpit.fixture.invalid/api/bitget-demo/account",
    { headers: { "sec-fetch-site": "same-origin" } });
  return { f, server, request };
}
test("public read defaults off and unauthenticated read returns 401 without native access", async () => {
  const { f, server, request } = fixture();
  delete process.env.COCKPIT_DEMO_ACCOUNT_SYNC;
  assert.equal((await server.handleDemoAccount(request())).status, 404);
  process.env.COCKPIT_DEMO_ACCOUNT_SYNC = "1"; f.current = null;
  assert.equal((await server.handleDemoAccount(request())).status, 401); assert.equal(f.reads, 0);
});
test("active original session gets private data once; cache still rechecks revocation", async () => {
  process.env.COCKPIT_DEMO_ACCOUNT_SYNC = "1";
  const { f, server, request } = fixture();
  const first = await server.handleDemoAccount(request());
  assert.equal(first.status, 200); assert.equal(first.headers.get("cache-control"), "no-store");
  assert.equal((await first.json()).wallet.equity, "50000.25");
  assert.equal((await server.handleDemoAccount(request())).status, 200); assert.equal(f.reads, 1);
  f.revoked = true;
  assert.equal((await server.handleDemoAccount(request())).status, 503); assert.equal(f.reads, 1);
});
test("session replacement and revocation during native read discard the view", async () => {
  for (const change of ["session", "revoked"]) {
    const { f, server, request } = fixture();
    f.mutate = () => { if (change === "revoked") f.revoked = true; else f.current = { ...f.current, handle: "replacement" }; };
    const response = await server.handleDemoAccount(request());
    assert.equal(response.status, 503); assert.doesNotMatch(await response.text(), /50000|private/);
  }
});
test("cross-site requests and broker failures never disclose provider details", async () => {
  const { f, server, request } = fixture();
  assert.equal((await server.handleDemoAccount(new Request(request().url,
    { headers: { "sec-fetch-site": "cross-site" } }))).status, 503);
  assert.equal(f.reads, 0); f.fail = true;
  const response = await server.handleDemoAccount(request());
  assert.equal(response.status, 503); assert.doesNotMatch(await response.text(), /private broker/);
});
test("initial actual panel SSR offers refresh and invents no balances or positions", () => {
  const component = load("../src/components/demo-account.tsx", {
    "../lib/demo-account-contract": contract,
    "next/link": { default: ({ href, children }: any) => React.createElement("a", { href }, children) },
  });
  const html = renderToStaticMarkup(React.createElement(component.DemoAccountPanel, { tenantId: id(1) }));
  assert.match(html, /Bitget Futures-Konto|Aktualisieren/);
  assert.match(html, /werden geladen/);
  assert.doesNotMatch(html, /50000|keine offenen|API-Key/);
});
test("readonly adapter sends exact separate signed purpose and independent session over real mTLS", async t => {
  let calls = 0, published = view();
  const key = Buffer.alloc(32, 7), now = Math.floor(Date.now()/1000);
  const native = await demoTlsFixture(t, (request, response) => {
    calls++;
    assert.equal(request.method, "POST");
    assert.equal(request.url, "/v1/bitget-demo-trading/account-read");
    const token = request.headers.authorization!.slice(7), [a, b, c] = token.split(".");
    assert.equal(c, createHmac("sha256", key).update(`${a}.${b}`).digest("base64url"));
    const claims = JSON.parse(Buffer.from(b, "base64url").toString());
    const context = JSON.parse(Buffer.from(request.headers["x-investalo-credential-context"] as string, "base64url").toString());
    assert.equal(claims.kind, "investalo-demo-account-read/1");
    assert.equal(claims.aud, "investalo-demo-account-read");
    assert.equal(claims.oidc_auth_time, now-3600);
    assert.equal(context.subject, "original");
    assert.equal(claims.session_binding, context.session_binding);
    let body = "";
    request.on("data", chunk => { body += chunk; });
    request.on("end", () => {
      assert.equal(claims.body_sha256, createHash("sha256").update(body).digest("hex"));
      assert.deepEqual(Object.keys(JSON.parse(body)).sort(),
        ["platform_account_id", "connection_id", "credential_revision", "storage_version"].sort());
      const wire = JSON.stringify(published);
      response.writeHead(200, { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(wire) });
      response.end(wire);
    });
  });
  // The fixture substitutes only the destination socket; all actual adapter wire/TLS checks run.
  const executor = load("../src/lib/demo-account-executor.ts", {
    "./demo-account-contract.ts": contract, "./demo-trading-passkey-action-proof-state.ts": proof,
    "node:https": { default: { request: (_uri: URL, options: any, callback: any) =>
      https.request(new URL(native.origin), options, callback) } },
  });
  const input = { origin: "https://demo-trading-executor.cockpit.internal:9443",
    oidcIssuer: "https://idp.fixture.invalid", userId: id(4), signingKey: key,
    authorized: { handle: Buffer.alloc(32, 2).toString("base64url"), origin: "https://cockpit.fixture.invalid",
      session: { subject: "original", issuer: "https://idp.fixture.invalid", oidcAuthTime: now-3600,
        tenantId: id(1), authEpoch: 3, csrf: Buffer.alloc(32, 3).toString("base64url"), expiresAt: now+3600 } },
    target: { platform_account_id: id(2), connection_id: id(3), credential_revision: 1, storage_version: 1 },
    tls: { ca: Buffer.from(SYNTHETIC_DEMO_TLS.ca), certificate: Buffer.from(SYNTHETIC_DEMO_TLS.clientCertificate),
      privateKey: Buffer.from(SYNTHETIC_DEMO_TLS.clientPrivateKey) },
  };
  assert.deepEqual(await executor.readDemoAccount(input), published);
  published = { ...view(), tenant_id: id(99) };
  await assert.rejects(executor.readDemoAccount(input), /DEMO_ACCOUNT_UNAVAILABLE/);
  assert.equal(calls, 2);
});
