import test, { afterEach } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import ts from "typescript";
import * as contract from "../src/lib/demo-account-contract.ts";
import * as startupContract from "../src/lib/demo-startup-contract.ts";
import * as btcContract from "../src/lib/demo-btc-test-contract.ts";
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
function startupView(): startupContract.DemoStartup {
  const account = view();
  account.wallet = { equity: "10000", available: "10000", locked: "0", unrealized_pnl: "0",
    isolated_margin: "0", crossed_margin: "0" };
  account.positions = [];
  return { schema: "investalo-demo-startup/1", account, observed_at: account.observed_at,
    configurations: startupContract.STARTUP_SYMBOLS.map(symbol => ({
      symbol, margin_mode: "isolated", position_mode: "one_way_mode", asset_mode: "single", long_leverage: "2", matches: true })),
    orders: startupContract.ORDER_CATEGORIES.map(category => ({ category, count: 0, pages: 1, complete: true })),
    blockers: [], expected_initial_usdt: "10000", pending_scope_verified: false, costs_verified: false, execution_enabled: false };
}
function btcView(): btcContract.DemoBTCTest {
  const start = startupView();
  return { schema: "investalo-demo-btc-test/1", observed_at: start.observed_at,
    readiness: { ...start, schema: "investalo-demo-btc-readiness/1",
      configurations: start.configurations.filter(c => c.symbol === "BTCUSDT") },
    preview: { schema: "investalo-demo-btc-test-preview/1", symbol: "BTCUSDT", environment: "demo",
      product_type: "USDT-FUTURES", side: "long", order_type: "limit", force: "ioc", leverage: 2,
      margin_mode: "isolated", quantity_btc: "0.0003", limit_price_usdt: "60060.1",
      quote_ask_usdt: "60000.1", maximum_notional_usdt: "18.01803",
      initial_margin_estimate_usdt: "9.009015", notional_cap_usdt: "20",
      fees_verified: false, account_verified: false, native_max_quantity_btc: null,
      maximum_quantity_verified: false, submission_enabled: false,
      observed_ms: Date.parse(start.observed_at), source_sha256: ["a".repeat(64), "b".repeat(64)] },
    unknown_wallet_fields: [], execution_enabled: false };
}
function marketView(): btcContract.DemoBTCMarketTest {
  const old = btcView();
  return { ...old, schema: "investalo-demo-btc-market-preview-report/1", preview: {
    schema: "bitget-classic-btc-demo-market-test/1", symbol: "BTCUSDT", environment: "demo",
    order_type: "market", side: "long", leverage: 2, margin_mode: "isolated",
    quantity_btc: "0.0003", reference_price_usdt: "60000", estimated_notional_usdt: "18",
    estimated_margin_usdt: "9", planning_notional_usdt: "18.18", planning_cap_usdt: "20",
    price_buffer_percent: "1", execution_price_guaranteed: false,
    native_max_market_quantity_btc: null, observed_ms: old.preview.observed_ms, submission_enabled: false } };
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
    "./demo-startup-contract.ts": startupContract,
    "./demo-btc-test-contract.ts": btcContract,
    "./demo-trading-credential-action-contracts.ts": metadataContract,
    "./backend.ts": { apiRequest: async (_session: unknown, path: string) => path === "/v1/me" ?
      { user: { id: id(4), subject: "synthetic", auth_epoch: 3 },
        memberships: [{ tenant_id: id(1), tenant_name: "fixture", role: "owner" }], live_enabled: false } : metadata() },
    "./demo-trading-passkey-credential-browser-server.ts": { runtime: async () => ({
      accountId: id(2), check: async () => {}, identity: { readAccount: async (_bound: unknown, _user: unknown, target: any) => {
        f.reads++; f.mutate(); if (f.fail) throw new Error("private broker details");
        return target.inspection === "startup" ? startupView() :
          target.inspection === "btc-test" ? btcView() :
          target.inspection === "btc-market" ? marketView() : view();
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
    "../lib/demo-startup-contract": startupContract,
    "./demo-startup": { DemoStartupReport: () => null },
    "./demo-btc-test": { DemoBTCTestReport: () => null },
    "./demo-market-order": { DemoMarketOrder: () => null },
    "../lib/demo-btc-test-contract": btcContract,
    "next/link": { default: ({ href, children }: any) => React.createElement("a", { href }, children) },
  });
  const html = renderToStaticMarkup(React.createElement(component.DemoAccountPanel, { tenantId: id(1) }));
  assert.match(html, /Bitget Futures-Konto|Aktualisieren/);
  assert.match(html, /werden geladen/);
  assert.doesNotMatch(html, /50000|keine offenen|API-Key/);
});

test("Market report preserves estimates unknown max and rejects guarantees or altered sizing", () => {
  const report = marketView();
  assert.deepEqual(btcContract.parseDemoBTCMarketTest(report, id(1), id(2)), report);
  for (const changes of [{ force: "ioc" }, { execution_price_guaranteed: true },
    { planning_notional_usdt: "20.01" }, { estimated_notional_usdt: "19" },
    { native_max_market_quantity_btc: "0.0001" }, { reference_price_usdt: "NaN" },
    { order_type: "limit" }]) {
    assert.throws(() => btcContract.parseDemoBTCMarketTest({
      ...report, preview: { ...report.preview, ...changes } }, id(1), id(2)));
  }
  assert.throws(() => btcContract.parseDemoBTCTest(report, id(1), id(2)));
  assert.throws(() => btcContract.parseDemoBTCMarketTest(report, id(9), id(2)));
});

test("Market inspection bypasses numeric cache and retains session guard and strict selector", async () => {
  const { f, server, request } = fixture();
  const inspect = () => new Request(request().url + "?inspection=btc-market", {
    headers: { "sec-fetch-site": "same-origin" } });
  assert.equal((await server.handleDemoAccount(request())).status, 200);
  for (let i=0; i<2; i++) {
    const result = await server.handleDemoAccount(inspect());
    assert.equal(result.status, 200);
    assert.equal((await result.json()).preview.order_type, "market");
  }
  assert.equal(f.reads, 3);
  assert.equal((await server.handleDemoAccount(new Request(inspect().url + "&symbol=ETHUSDT",
    { headers: { "sec-fetch-site": "same-origin" } }))).status, 503);
  f.mutate = () => { f.revoked = true; };
  assert.equal((await server.handleDemoAccount(inspect())).status, 503);
});

test("Market preview UI describes estimated amounts without a guaranteed price or send button", () => {
  const component = load("../src/components/demo-btc-test.tsx", { "./demo-startup": {
    DemoStartupReport: () => null } });
  const html = renderToStaticMarkup(React.createElement(component.DemoBTCTestReport, { data: marketView() }));
  assert.match(html, /Market-Ausführung/);
  assert.match(html, /Geschätzter Positionswert/);
  assert.match(html, /1 % Preispuffer/);
  assert.doesNotMatch(html, /Limitpreis|Maximaler Positionswert|<button/);
});
test("readonly adapter sends exact separate signed purpose and independent session over real mTLS", async t => {
  let calls = 0, published: contract.DemoAccount | startupContract.DemoStartup | btcContract.DemoBTCTest | btcContract.DemoBTCMarketTest = view(),
    inspecting: "startup" | "btc-test" | "btc-market" | undefined;
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
        ["platform_account_id", "connection_id", "credential_revision", "storage_version", ...(inspecting ? ["inspection"] : [])].sort());
      if (inspecting) assert.equal(JSON.parse(body).inspection, inspecting);
      const wire = JSON.stringify(published);
      response.writeHead(200, { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(wire) });
      response.end(wire);
    });
  });
  // The fixture substitutes only the destination socket; all actual adapter wire/TLS checks run.
  const executor = load("../src/lib/demo-account-executor.ts", {
    "./demo-account-contract.ts": contract, "./demo-startup-contract.ts": startupContract,
    "./demo-btc-test-contract.ts": btcContract,
    "./demo-trading-passkey-action-proof-state.ts": proof,
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
  inspecting = "startup"; published = startupView();
  const inspectionInput = { ...input, target: { ...input.target, inspection: "startup" } };
  assert.deepEqual(await executor.readDemoAccount(inspectionInput), published);
  published = view(); // Ordinary balances cannot satisfy a requested startup check.
  await assert.rejects(executor.readDemoAccount(inspectionInput), /DEMO_ACCOUNT_UNAVAILABLE/);
  inspecting = "btc-test"; published = btcView();
  const btcInput = { ...input, target: { ...input.target, inspection: "btc-test" } };
  assert.deepEqual(await executor.readDemoAccount(btcInput), published);
  published = startupView();
  await assert.rejects(executor.readDemoAccount(btcInput), /DEMO_ACCOUNT_UNAVAILABLE/);
  inspecting = "btc-market"; published = marketView();
  const marketInput = { ...input, target: { ...input.target, inspection: "btc-market" } };
  assert.deepEqual(await executor.readDemoAccount(marketInput), published);
  published = btcView();
  await assert.rejects(executor.readDemoAccount(marketInput), /DEMO_ACCOUNT_UNAVAILABLE/);
  assert.equal(calls, 8);
});
test("startup contract rejects authority flags, leaked IDs, missing axes and a fake matching profile", () => {
  const report = startupView(); report.observed_at = report.account.observed_at;
  assert.deepEqual(startupContract.parseDemoStartup(report, id(1), id(2)), report);
  const bad = [{ ...report, execution_enabled: true }, { ...report, pending_scope_verified: true },
    { ...report, costs_verified: true }, { ...report, private_key: "secret" },
    { ...report, configurations: report.configurations.slice(1) },
    { ...report, orders: report.orders.slice(1) },
    { ...report, configurations: report.configurations.map(c => ({ ...c, long_leverage: "10" })) },
    { ...report, configurations: report.configurations.map(c => ({ ...c, long_leverage: "2.0000000000000000001" })) },
    { ...report, account: { ...report.account, wallet: { ...report.account.wallet, available: "10000.0000000000000000001" } } },
    { ...report, orders: report.orders.map(o => ({ ...o, orderId: "foreign-private" })) }];
  for (const value of bad) assert.throws(() => startupContract.parseDemoStartup(value, id(1), id(2)));
  assert.throws(() => startupContract.parseDemoStartup(report, id(99), id(2)));
});
test("startup always bypasses balance cache and validates original session after inspection", async () => {
  const { f, server, request } = fixture();
  assert.equal((await server.handleDemoAccount(request())).status, 200);
  const inspect = () => new Request(`${request().url}?inspection=startup`,
    { headers: { "sec-fetch-site": "same-origin" } });
  const result = await server.handleDemoAccount(inspect());
  assert.equal(result.status, 200); assert.equal((await result.json()).schema, "investalo-demo-startup/1");
  assert.equal(f.reads, 2);
  assert.equal((await server.handleDemoAccount(request())).status, 200);
  assert.equal(f.reads, 2); // Startup never overwrites the numeric balance cache.
  f.mutate = () => { f.current = { ...f.current, handle: "replacement" }; };
  assert.equal((await server.handleDemoAccount(inspect())).status, 503);
});
test("only exact startup query is admitted and cross-site inspection never calls the executor", async () => {
  const { f, server, request } = fixture();
  for (const query of ["?inspection=trade", "?inspection=startup&inspection=startup", "?inspection=startup&symbol=BTCUSDT"]) {
    assert.equal((await server.handleDemoAccount(new Request(request().url + query,
      { headers: { "sec-fetch-site": "same-origin" } }))).status, 503);
  }
  assert.equal((await server.handleDemoAccount(new Request(request().url + "?inspection=startup",
    { headers: { "sec-fetch-site": "cross-site" } }))).status, 503);
  assert.equal(f.reads, 0);
});
test("actual report renders needed settings and pending counts without a trading button", () => {
  const component = load("../src/components/demo-startup.tsx", {});
  const report = startupView();
  report.blockers = ["configuration_mismatch", "orders_present"];
  report.configurations[2] = { ...report.configurations[2], long_leverage: "10", matches: false };
  report.orders[4].count = 2;
  const html = renderToStaticMarkup(React.createElement(component.DemoStartupReport, { data: report }));
  assert.match(html, /BTCUSDT/); assert.match(html, /10×/);
  assert.match(html, /Take-Profit \/ Stop-Loss: 2/);
  assert.match(html, /ORDERVERSAND NOCH AUS/);
  assert.doesNotMatch(html, /<button|API-Key|orderId/);
});
test("BTC preview preserves exact sizing and rejects forged authority, cap, margin and foreign scope", () => {
  const report = btcView();
  assert.deepEqual(btcContract.parseDemoBTCTest(report, id(1), id(2)), report);
  for (const change of [
    { maximum_notional_usdt: "20.000000000000000001" },
    { initial_margin_estimate_usdt: "9.009015000000000001" },
    { quantity_btc: "0.000300000000000000001" }, { limit_price_usdt: "60060.2" },
    { leverage: 10 }, { environment: "live" }, { submission_enabled: true },
    { account_verified: true }, { maximum_quantity_verified: true }, { private_key: "secret" },
  ]) assert.throws(() => btcContract.parseDemoBTCTest({ ...report, preview: { ...report.preview, ...change } }, id(1), id(2)));
  assert.throws(() => btcContract.parseDemoBTCTest(report, id(9), id(2)));
  assert.throws(() => btcContract.parseDemoBTCTest({ ...report, execution_enabled: true }, id(1), id(2)));
  assert.throws(() => startupContract.parseDemoStartup(report.readiness, id(1), id(2)));
  const maximum = { ...report, preview: { ...report.preview, native_max_quantity_btc: "0.0002",
    maximum_quantity_verified: true } };
  assert.throws(() => btcContract.parseDemoBTCTest(maximum, id(1), id(2)));
});
test("BTC query bypasses balance cache and discards proposal on original session replacement", async () => {
  const { f, server, request } = fixture();
  await server.handleDemoAccount(request());
  const inspect = () => new Request(request().url + "?inspection=btc-test", {
    headers: { "sec-fetch-site": "same-origin" } });
  assert.equal((await server.handleDemoAccount(inspect())).status, 200);
  assert.equal((await server.handleDemoAccount(inspect())).status, 200);
  assert.equal(f.reads, 3);
  await server.handleDemoAccount(request());
  assert.equal(f.reads, 3);
  f.mutate = () => { f.current = { ...f.current, handle: "replacement" }; };
  assert.equal((await server.handleDemoAccount(inspect())).status, 503);
});
test("BTC inspection cannot select arbitrary coins or repeated parameters or cross-site origin", async () => {
  const { f, server, request } = fixture();
  for (const query of ["?inspection=btc-test&symbol=ETHUSDT", "?inspection=btc-test&inspection=btc-test"]) {
    assert.equal((await server.handleDemoAccount(new Request(request().url + query, {
      headers: { "sec-fetch-site": "same-origin" } }))).status, 503);
  }
  assert.equal((await server.handleDemoAccount(new Request(request().url + "?inspection=btc-test",
    { headers: { "sec-fetch-site": "cross-site" } }))).status, 503);
  assert.equal(f.reads, 0);
});
test("BTC report explains exact values and missing fields without claiming an order is submitted", () => {
  const startup = load("../src/components/demo-startup.tsx", {});
  const component = load("../src/components/demo-btc-test.tsx", { "./demo-startup": startup });
  const report = btcView();
  report.unknown_wallet_fields = ["grant"];
  report.readiness.blockers = ["wallet_unknown"];
  assert.deepEqual(btcContract.parseDemoBTCTest(report, id(1), id(2)), report);
  const html = renderToStaticMarkup(React.createElement(component.DemoBTCTestReport, { data: report }));
  assert.match(html, /0.0003/); assert.match(html, /Bonusguthaben/);
  assert.match(html, /9,009015/); assert.match(html, /maximale Ordermenge/);
  assert.doesNotMatch(html, /<button|orderId|private_key/);
});
