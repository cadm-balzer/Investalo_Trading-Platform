import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import ts from "typescript";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import * as contracts from "../src/lib/futures-recovery-contracts.ts";
import * as security from "../src/lib/security.ts";
import { NextRequest } from "next/server.js";

const tenant = "00000000-0000-4000-8000-000000000001", account = "00000000-0000-4000-8000-000000000002";
function data() {
  return { schema_version: "futures-recovery-status/1", tenant_id: tenant, mode: "paper", live_enabled: false,
    observed_at: "2026-11-13T12:00:00Z", assets: [{
      account_id: account, symbol: "SOLUSDT", cycle: 3, revision: 20, state_digest: "a".repeat(64),
      liquidated_at: "2026-11-12T12:00:00Z", net_loss: "399.68", leverage: "5",
      available_capital: "1600", required_capital: "2000",
      reasons: ["new_basket_budget_missing"], allowed: false,
    }] };
}
const source = readFileSync(new URL("../src/components/futures-recovery.tsx", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
}).outputText;
const panel = { exports: {} as any };
const require = createRequire(import.meta.url);
new Function("require", "module", "exports", compiled)((name: string) => {
  if (name === "next/navigation") return { useRouter: () => ({ refresh() {} }) };
  if (name === "@/lib/futures-recovery-contracts") return contracts;
  return require(name);
}, panel, panel.exports);
function render(value: unknown, summary = false) {
  return renderToStaticMarkup(React.createElement(panel.exports.FuturesRecoveryPanel, {
    data: value === null ? null : contracts.parseRecoveryStatus(value, tenant), csrf: "test", summary,
  }));
}

test("own current status whitelists fields and rejects historical/live/foreign results", () => {
  const d = data();
  assert.deepEqual(contracts.parseRecoveryStatus({ ...d, secret: "not-public" }, tenant), d);
  for (const change of [{ tenant_id: account }, { mode: "research" }, { live_enabled: true }, { schema_version: "futures-capital-market/1" }])
    assert.throws(() => contracts.parseRecoveryStatus({ ...d, ...change }, tenant));
});
test("contradictory permission, duplicate assets and unknown reasons are rejected", () => {
  const d = data(), a = d.assets[0];
  for (const change of [{ allowed: true }, { reasons: ["unknown"] }, { liquidated_at: "2027-01-01T00:00:00Z" },
    { net_loss: "-399.68" }, { cycle: 0 }, { leverage: "11" }, { state_digest: "foreign" }])
    assert.throws(() => contracts.parseRecoveryStatus({ ...d, assets: [{ ...a, ...change }] }, tenant));
  assert.throws(() => contracts.parseRecoveryStatus({ ...d, assets: [a, a] }, tenant));
});
test("homepage shows asset blocker and portfolio link; details explain real shortfall and manual button", () => {
  const home = render(data(), true), detail = render(data());
  assert.match(home, /Handelsblocker: Liquidation/);
  assert.match(home, /SOLUSDT/);
  assert.match(home, /portfolio#futures-recovery/);
  assert.match(detail, /399,68/);
  assert.match(detail, /Das vollständige Kapital/);
  assert.match(detail, /disabled=""[^>]*>Wiederbeleben/);
  assert.match(detail, /neuen RSI-Signal/);
  assert.equal(render({ ...data(), assets: [] }), "");
  assert.match(render(null), /nicht verfügbar/);
});
test("manual request binds exact account/cycle/revision/state and forbids browser reconciliation/actor claims", () => {
  const x = { account_id: account, symbol: "SOLUSDT", cycle: 3, revision: 20, state_digest: "a".repeat(64),
    event_id: "00000000-0000-4000-8000-000000000003", consent: true };
  assert.deepEqual(contracts.parseRecoveryRequest(x), x);
  for (const change of [{ consent: false }, { actor_id: "other" }, { position_flat: true }, { revision: -1 }])
    assert.throws(() => contracts.parseRecoveryRequest({ ...x, ...change }));
});

test("recovery route is default off and enforces Origin/CSRF before forwarding own bound request", async () => {
  const routeSource = readFileSync(new URL("../src/app/api/futures/recovery/route.ts", import.meta.url), "utf8");
  const route = { exports: {} as any };
  const output = ts.transpileModule(routeSource, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
  const calls: any[] = [];
  let currentSession: any = { tenantId: tenant, csrf: "test" };
  new Function("require", "module", "exports", output)((name: string) => {
    if (name === "@/lib/auth") return { getSession: async () => currentSession };
    if (name === "@/lib/config") return { getConfig: async () => ({ origin: "https://cockpit.investalo.de" }) };
    if (name === "@/lib/security") return security;
    if (name === "@/lib/futures-recovery-contracts") return contracts;
    if (name === "@/lib/backend") return {
      BackendError: class extends Error {},
      apiRequest: async (...args: any[]) => { calls.push(args); return { ...data(), assets: [] }; },
    };
    return require(name);
  }, route, route.exports);
  const body = { account_id: account, symbol: "SOLUSDT", cycle: 3, revision: 20,
    state_digest: "a".repeat(64), event_id: "00000000-0000-4000-8000-000000000003", consent: true };
  function req(headers: Record<string, string> = {}, contents: unknown = body) {
    return new NextRequest("https://cockpit.investalo.de/api/futures/recovery", { method: "POST",
      headers: { Origin: "https://cockpit.investalo.de", "Content-Type": "application/json", "x-csrf-token": "test", ...headers },
      body: JSON.stringify(contents) });
  }
  const previous = process.env.COCKPIT_FUTURES_RECOVERY_PREVIEW;
  try {
    delete process.env.COCKPIT_FUTURES_RECOVERY_PREVIEW;
    assert.equal((await route.exports.POST(req())).status, 404);
    assert.equal(calls.length, 0);
    process.env.COCKPIT_FUTURES_RECOVERY_PREVIEW = "1";
    assert.equal((await route.exports.POST(req({ Origin: "https://foreign.invalid" }))).status, 400);
    assert.equal((await route.exports.POST(req({ "x-csrf-token": "wrong" }))).status, 400);
    assert.equal((await route.exports.POST(req({}, { ...body, position_flat: true }))).status, 400);
    currentSession = null;
    assert.equal((await route.exports.POST(req())).status, 401);
    assert.equal(calls.length, 0);
    currentSession = { tenantId: tenant, csrf: "test" };
    assert.equal((await route.exports.POST(req())).status, 200);
    assert.equal(calls.length, 1);
    assert.equal(calls[0][0], currentSession);
    assert.equal(calls[0][1], "/v1/futures-recovery");
    assert.deepEqual(JSON.parse(calls[0][2].body), body);
    assert.equal(calls[0][2].idempotencyKey, body.event_id);
  } finally {
    if (previous === undefined) delete process.env.COCKPIT_FUTURES_RECOVERY_PREVIEW;
    else process.env.COCKPIT_FUTURES_RECOVERY_PREVIEW = previous;
  }
});
