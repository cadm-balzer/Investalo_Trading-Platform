import test, { afterEach } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { readFileSync } from "node:fs";
import ts from "typescript";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import * as signals from "../src/lib/demo-signals-contract.ts";
import * as account from "../src/lib/demo-account-contract.ts";
import * as authorized from "../src/lib/authorized-session.ts";
import * as metadata from "../src/lib/demo-trading-credential-action-contracts.ts";
import * as objects from "../src/lib/passkey-enrollment-state.ts";
import * as ids from "../src/lib/credential-action-contracts.ts";
import * as startup from "../src/lib/demo-startup-contract.ts";
import * as btc from "../src/lib/demo-btc-test-contract.ts";

const id = (n: number) => `00000000-0000-0000-0000-${String(n).padStart(12, "0")}`;
const tenant = id(1), ownAccount = id(2), origin = "https://cockpit.investalo.de";
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
function data(): signals.DemoSignals {
  const observed = new Date(), end = Math.floor(observed.getTime()/3600000)*3600000;
  return { schema: "investalo-demo-signals/1", tenant_id: tenant, account_id: ownAccount,
    source: "bitget_classic_demo", execution_enabled: false, observed_at: observed.toISOString(),
    timeframe: "H1", rsi_period: 14, warmup_bars: 300, next_candle_close: new Date(end+3600000).toISOString(),
    assets: signals.DEMO_SIGNAL_SYMBOLS.map(symbol => ({
      symbol, status: "confirmed", rsi: "44.9084789229005868326486570935569389",
      previous_rsi: "45.2464900279309912923872658746447030", below_count: 0,
      close_price: "60403.5", candle_closed_at: new Date(end).toISOString(),
      fetched_at: observed.toISOString(), entry_condition: "waiting_rsi",
    })) };
}

test("Demo source/account binding and exact fixed seven-symbol projection", () => {
  const original = data();
  assert.deepEqual(signals.parseDemoSignals(original, tenant, ownAccount), original);
});
test("foreign account, fake enabled state, Paper data or private fields are rejected", () => {
  for (const fields of [{ tenant_id: ownAccount }, { account_id: tenant }, { execution_enabled: true },
    { source: "paper" }, { envelope: "private" }, { timeframe: "H4" }, { warmup_bars: 14 }]) {
    assert.throws(() => signals.parseDemoSignals({ ...data(), ...fields }, tenant, ownAccount));
  }
});
test("missing, duplicate, future, stale candle and fabricated confirmations fail", () => {
  for (const mutate of [
    (d: any) => d.assets.pop(), (d: any) => d.assets[1] = d.assets[0],
    (d: any) => d.assets[0].candle_closed_at = d.next_candle_close,
    (d: any) => d.assets[0].candle_closed_at = "2020-01-01T00:00:00Z",
    (d: any) => d.assets[0].below_count = 2,
    (d: any) => d.assets[0].rsi = "100.000000000000000000000000000001",
    (d: any) => d.assets[0].rsi = "-0",
    (d: any) => d.assets[0].fetched_at = d.next_candle_close,
  ]) {
    const d = data(); mutate(d);
    assert.throws(() => signals.parseDemoSignals(d, tenant, ownAccount));
  }
});
test("exact unrounded RSI30 comparisons survive JavaScript numeric rounding", () => {
  for (const [rsi, prior, count, condition] of [
    ["29.999999999999999999999999999", "29.5", 2, "confirmed"],
    ["29.999999999999999999999999999", "30", 1, "waiting_confirmation"],
    ["30", "29.5", 0, "waiting_rsi"],
    ["30.000000000000000000000000001", "29.5", 0, "waiting_rsi"],
    ["0", "0", 2, "confirmed"],
  ] as const) {
    const d = data();
    Object.assign(d.assets[0], { rsi, previous_rsi: prior, below_count: count, entry_condition: condition });
    assert.equal(signals.parseDemoSignals(d, tenant).assets[0].below_count, count);
  }
  assert.equal(signals.rsiRelation("29.999999999999999999999999999"), -1);
  assert.equal(signals.rsiRelation("30"), 0);
  assert.equal(signals.rsiRelation("30.000000000000000000000000001"), 1);
});
test("unavailable source stays unknown instead of RSI zero or a buy condition", () => {
  const d = data();
  Object.assign(d.assets[0], { status: "unavailable", rsi: null, previous_rsi: null, below_count: null,
    close_price: null, candle_closed_at: null, fetched_at: null, entry_condition: "unavailable" });
  assert.deepEqual(signals.parseDemoSignals(d, tenant).assets[0], d.assets[0]);
  d.assets[0].rsi = "0";
  assert.throws(() => signals.parseDemoSignals(d, tenant));
});
const panel = load("../src/components/demo-signals.tsx", {
  "../lib/demo-signals-contract": signals,
  "./demo-control": load("../src/components/demo-control.tsx", {
    "../lib/demo-signals-contract": signals,
    "../lib/demo-control-contract": await import("../src/lib/demo-control-contract.ts"),
  }),
});
test("RSI table shows threshold distance, last-close time and no prediction of purchase time", () => {
  const html = renderToStaticMarkup(React.createElement(panel.DemoSignalRows, {
    data: signals.parseDemoSignals(data(), tenant), stale: false, positions: [],
  }));
  assert.match(html, /44,91/); assert.match(html, /14,91 RSI-Punkte/);
  assert.match(html, /Wartet auf RSI unter 30/); assert.match(html, /Kerzenschluss:/);
  assert.match(html, /H1-Schlusskurs/); assert.doesNotMatch(html, /Kauf in .*Minuten/);
});
test("stale table and existing foreign/unknown stage never claim a fresh executable entry", () => {
  const html = renderToStaticMarkup(React.createElement(panel.DemoSignalRows, {
    data: signals.parseDemoSignals(data(), tenant), stale: true,
    positions: [{ symbol: "BTCUSDT" }] as any,
  }));
  assert.match(html, /Datenstand veraltet/); assert.doesNotMatch(html, /Wartet auf RSI unter 30/);
  assert.match(html, /Nachkaufstaffel noch nicht zugeordnet/);
});
test("control remains explicit and cannot claim an operative worker", () => {
  const html = renderToStaticMarkup(React.createElement(panel.DemoSignalsPanel, {
    tenantId: tenant, accountId: ownAccount, positions: [],
  }));
  assert.match(html, /NOCH NICHT GESTARTET/);
  assert.match(html, /disabled=""[^>]*>Demo-Start anfordern/);
  assert.match(html, /Handelsworker wird noch angebunden/);
  assert.match(html, /sechste Stufe manuell/);
  assert.doesNotMatch(html, /DEMOHANDEL AKTIV/);
});

const originalFlag = process.env.COCKPIT_DEMO_ACCOUNT_SYNC;
afterEach(() => {
  if (originalFlag === undefined) delete process.env.COCKPIT_DEMO_ACCOUNT_SYNC;
  else process.env.COCKPIT_DEMO_ACCOUNT_SYNC = originalFlag;
});
function fixture() {
  process.env.COCKPIT_DEMO_ACCOUNT_SYNC = "1";
  const session = { tenantId: tenant, subject: "original", issuer: "https://auth.fixture.invalid",
    authEpoch: 3, oidcAuthTime: Math.floor(Date.now()/1000)-3600,
    csrf: Buffer.alloc(32, 7).toString("base64url"), expiresAt: Math.floor(Date.now()/1000)+3600 };
  const f = { current: { handle: "original-handle", session } as any, reads: 0, revoked: false,
    mutate: () => {}, response: data(), meCalls: 0 };
  const server = load("../src/lib/demo-account-server.ts", {
    "server-only": {}, "./auth.ts": { getBoundSession: async () => f.current },
    "./config.ts": { getConfig: async () => ({ origin }) },
    "./authorized-session.ts": authorized, "./passkey-enrollment-state.ts": objects,
    "./credential-action-contracts.ts": ids, "./demo-account-contract.ts": account,
    "./demo-startup-contract.ts": startup, "./demo-btc-test-contract.ts": btc,
    "./demo-signals-contract.ts": signals, "./demo-trading-credential-action-contracts.ts": metadata,
    "./backend.ts": { apiRequest: async (_s: unknown, path: string) => {
      if (path === "/v1/me") {
        f.meCalls++;
        return { user: { id: id(4), subject: "original", auth_epoch: 3 },
          memberships: [{ tenant_id: tenant, tenant_name: "fixture", role: "owner" }], live_enabled: false };
      }
      return { tenant_id: tenant, auth_epoch: 3, purpose: "demo_futures_spot_trading",
        profile: "bitget-classic-demo-trading-secret/1", environment: "demo",
        account: { id: ownAccount, name: "Demo", broker: "bitget", mode: "bitget_demo", currency: "USDT", status: "ready" },
        connection: { connection_id: id(3), credential_revision: 1, storage_version: 1,
          status: f.revoked ? "revoked" : "active" }, key_authorities: ["coow", "cpow", "stow"] };
    } },
    "./demo-trading-passkey-credential-browser-server.ts": { runtime: async () => ({
      accountId: ownAccount, check: async () => {}, identity: { readAccount: async (_b: unknown, _u: unknown, target: any) => {
        assert.equal(target.inspection, "signals");
        f.reads++; f.mutate(); return f.response;
      } },
    }) },
  });
  // Reproduce Next's internal listener origin; browser Origin is independently public.
  const request = () => new Request("http://0.0.0.0:3000/api/bitget-demo/signals",
    { headers: { "sec-fetch-site": "same-origin", origin } });
  return { f, server, request };
}
test("actual BFF signal branch preserves proxy origin, source contract and fresh before/after metadata", async () => {
  const { f, server, request } = fixture();
  const result = await server.handleDemoAccount(request(), true);
  assert.equal(result.status, 200); assert.equal(f.reads, 1); assert.equal(f.meCalls, 2);
  assert.deepEqual(await result.json(), f.response); assert.equal(result.headers.get("cache-control"), "no-store");
});
test("anonymous, cross-origin, unrecognized query and default-off signal reads never reach source", async () => {
  const { f, server, request } = fixture();
  f.current = null;
  assert.equal((await server.handleDemoAccount(request(), true)).status, 401);
  assert.equal(f.reads, 0);
  const fresh = fixture();
  for (const req of [
    new Request(request().url, { headers: { "sec-fetch-site": "cross-site", origin } }),
    new Request(request().url, { headers: { "sec-fetch-site": "same-origin", origin: "https://evil.invalid" } }),
    new Request(request().url+"?symbol=BTCUSDT", { headers: { "sec-fetch-site": "same-origin", origin } }),
  ]) assert.equal((await fresh.server.handleDemoAccount(req, true)).status, 503);
  assert.equal(fresh.f.reads, 0);
  delete process.env.COCKPIT_DEMO_ACCOUNT_SYNC;
  assert.equal((await fresh.server.handleDemoAccount(fresh.request(), true)).status, 404);
});
test("source completion cannot publish after epoch or credential revocation", async () => {
  for (const mutation of ["epoch", "credential"] as const) {
    const { f, server, request } = fixture();
    f.mutate = () => {
      if (mutation === "credential") f.revoked = true;
      else f.current = { ...f.current, session: { ...f.current.session, authEpoch: 4 } };
    };
    const result = await server.handleDemoAccount(request(), true);
    assert.equal(result.status, 503); assert.equal(f.reads, 1);
    assert.doesNotMatch(await result.text(), /44\.908|original-handle|envelope/);
  }
});
