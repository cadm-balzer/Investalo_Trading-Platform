import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import ts from "typescript";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { NextRequest } from "next/server.js";
import * as contracts from "../src/lib/futures-paper-settings-contracts.ts";
import * as security from "../src/lib/security.ts";

const tenant = "00000000-0000-4000-8000-000000000001", account = "00000000-0000-4000-8000-000000000002";
function data() {
  return { schema_version: "futures-paper-settings/1", tenant_id: tenant, mode: "paper", live_enabled: false,
    accounts: [{ account_id: account, account_name: "Eigenes Paperkonto", revision: 0, basket_limit: 5,
      saved: false, can_edit: true, leverage: "2", runtime_ready: false,
      recommendation: null, recommendation_reason: "futures_runtime_missing" }] };
}
const require = createRequire(import.meta.url);
function load(path: string, inject: Record<string, unknown>) {
  const source = readFileSync(new URL(path, import.meta.url), "utf8");
  const compiled = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const module = { exports: {} as any };
  new Function("require", "module", "exports", compiled)(
    (name: string) => inject[name] ?? require(name), module, module.exports);
  return module.exports;
}
test("settings validate own Paper account and never accept invented runtime/recommendation", () => {
  const d = data();
  assert.deepEqual(contracts.parseBasketSettings({ ...d, secret: "hidden" }, tenant), d);
  for (const change of [{ tenant_id: account }, { live_enabled: true }, { mode: "live" }])
    assert.throws(() => contracts.parseBasketSettings({ ...d, ...change }, tenant));
  for (const change of [{ basket_limit: 8 }, { basket_limit: true }, { revision: -1 }, { saved: true },
    { leverage: "5" }, { runtime_ready: true }, { recommendation: 7 }, { account_name: "" }])
    assert.throws(() => contracts.parseBasketSettings({ ...d, accounts: [{ ...d.accounts[0], ...change }] }, tenant));
  assert.throws(() => contracts.parseBasketSettings({ ...d, accounts: [d.accounts[0], d.accounts[0]] }, tenant));
});
test("request whitelist excludes cash, leverage and automatic profit authority", () => {
  const body = { account_id: account, expected_revision: 0, basket_limit: 7 };
  assert.deepEqual(contracts.parseBasketSettingsRequest(body), body);
  for (const change of [{ cash: "100000" }, { leverage: "10" }, { funded_capacity: 7 }, { expected_revision: true }])
    assert.throws(() => contracts.parseBasketSettingsRequest({ ...body, ...change }));
});
test("panel offers3–7 with profit staging and preserves open reserves; viewer controls disabled", () => {
  const panel = load("../src/components/futures-paper-settings.tsx", {
    "next/navigation": { useRouter: () => ({ refresh() {} }) },
    "@/lib/futures-paper-settings-contracts": contracts,
  });
  function render(value: unknown) {
    return renderToStaticMarkup(React.createElement(panel.FuturesPaperSettingsPanel, {
      data: value === null ? null : contracts.parseBasketSettings(value, tenant), csrf: "test",
    }));
  }
  const html = render(data());
  assert.match(html, /value="3"/);
  assert.match(html, /value="7"/);
  assert.match(html, /Gewinnetappen/);
  assert.match(html, /manuelle Reserve/);
  assert.match(html, /Kapitalempfehlung ausstehend/);
  const d = data();
  d.accounts[0].can_edit = false;
  assert.match(render(d), /<select[^>]*disabled=""/);
  assert.match(render(null), /derzeit nicht verfügbar/);
});
test("BFF default off, Origin/CSRF/auth/body checked before forwarding only own settings", async () => {
  const calls: any[] = [];
  let currentSession: any = { tenantId: tenant, csrf: "test" };
  let answer: unknown = { ...data(), accounts: [{ ...data().accounts[0], saved: true, revision: 1, basket_limit: 3 }] };
  const route = load("../src/app/api/futures/settings/route.ts", {
    "next/server": require("next/server.js"),
    "@/lib/futures-paper-settings-contracts": contracts,
    "@/lib/security": security,
    "@/lib/config": { getConfig: async () => ({ origin: "https://cockpit.investalo.de" }) },
    "@/lib/auth": { getSession: async () => currentSession },
    "@/lib/backend": {
      BackendError: class extends Error {},
      apiRequest: async (...args: any[]) => { calls.push(args); return answer; },
    },
  });
  const body = { account_id: account, expected_revision: 0, basket_limit: 3 };
  function req(headers: Record<string, string> = {}, contents: unknown = body) {
    return new NextRequest("https://cockpit.investalo.de/api/futures/settings", { method: "POST",
      headers: { Origin: "https://cockpit.investalo.de", "Content-Type": "application/json", "x-csrf-token": "test", ...headers },
      body: JSON.stringify(contents) });
  }
  const previous = process.env.COCKPIT_FUTURES_PAPER_SETTINGS_PREVIEW;
  try {
    delete process.env.COCKPIT_FUTURES_PAPER_SETTINGS_PREVIEW;
    assert.equal((await route.POST(req())).status, 404);
    process.env.COCKPIT_FUTURES_PAPER_SETTINGS_PREVIEW = "1";
    assert.equal((await route.POST(req({ Origin: "https://foreign.invalid" }))).status, 400);
    assert.equal((await route.POST(req({ "x-csrf-token": "wrong" }))).status, 400);
    assert.equal((await route.POST(req({}, { ...body, cash: "100000" }))).status, 400);
    assert.equal((await route.POST(req({}, { ...body, expected_revision: true }))).status, 400);
    currentSession = null;
    assert.equal((await route.POST(req())).status, 401);
    assert.equal(calls.length, 0);
    currentSession = { tenantId: tenant, csrf: "test" };
    const result = await route.POST(req());
    assert.equal(result.status, 200);
    assert.equal(result.headers.get("cache-control"), "no-store");
    assert.equal(calls.length, 1);
    assert.equal(calls[0][0], currentSession);
    assert.equal(calls[0][1], `/v1/futures-paper-settings/${account}`);
    assert.deepEqual(JSON.parse(calls[0][2].body), { expected_revision: 0, basket_limit: 3 });
    for (const change of [{ account_id: tenant }, { revision: 2 }, { basket_limit: 7 }]) {
      answer = { ...data(), accounts: [{ ...data().accounts[0], saved: true, revision: 1, basket_limit: 3, ...change }] };
      assert.equal((await route.POST(req())).status, 400);
    }
  } finally {
    if (previous === undefined) delete process.env.COCKPIT_FUTURES_PAPER_SETTINGS_PREVIEW;
    else process.env.COCKPIT_FUTURES_PAPER_SETTINGS_PREVIEW = previous;
  }
});
