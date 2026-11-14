import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import ts from "typescript";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import * as contracts from "../src/lib/futures-paper-assets-contracts.ts";

const tenant = "00000000-0000-4000-8000-000000000001", account = "00000000-0000-4000-8000-000000000002";
function data(): any {
  return { schema_version: "futures-paper-assets/1", tenant_id: tenant, mode: "paper", live_enabled: false,
    accounts: [{ account_id: account, account_name: "Eigenes Futures-Paperkonto", snapshot: {
      revision: 3, observed_at: "2026-11-01T16:00:01+00:00", indicator_at: "2026-11-01T16:00:00+00:00",
      next_signal_check: "2026-11-01T17:00:00+00:00", data_fresh: true, rsi_period: 14, timeframe: "H1",
      assets: ["BNBUSDT", "BTCUSDT", "ETHUSDT"].map(symbol => ({
        symbol, rsi: "25.1234", rsi_confirmations: 2, rearmed: false, reference_bid: "100",
        position: { quantity: "5.8", average_entry: "100.01", leverage: "2",
          regular_entries: 1, last_entry_price: "100.01" },
        next_buy: { stage: 2, maximum_fill_price: "95.00", status: "waiting_rearm", reasons: [] },
      })),
    } }] };
}
const require = createRequire(import.meta.url);
function load(path: string, inject: Record<string, unknown>) {
  const compiled = ts.transpileModule(readFileSync(new URL(path, import.meta.url), "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const module = { exports: {} as any };
  new Function("require", "module", "exports", compiled)(
    (name: string) => inject[name] ?? require(name), module, module.exports);
  return module.exports;
}
const panel = load("../src/components/futures-paper-assets.tsx", {
  "../lib/futures-paper-assets-contracts": contracts,
  "./futures-asset-refresh": { FuturesAssetRefresh: () => null },
});
function render(value: unknown) {
  return renderToStaticMarkup(React.createElement(panel.FuturesAssetsPanel, {
    data: value === null ? null : contracts.parseFuturesAssets(value, tenant),
  }));
}
test("own asset view accepts zero RSI and rejects other tenant or historical/live status", () => {
  const d = data();
  d.accounts[0].snapshot.assets[0].rsi = "0";
  assert.equal(contracts.parseFuturesAssets(d, tenant).accounts[0].snapshot!.assets[0].rsi, "0");
  for (const change of [{ tenant_id: account }, { mode: "live" }, { live_enabled: true },
    { schema_version: "backtest-result/1" }])
    assert.throws(() => contracts.parseFuturesAssets({ ...d, ...change }, tenant));
});
test("invalid RSI, duplicates, inconsistent stage and nonfinite values fail", () => {
  for (const modify of [
    (a: any) => a.rsi = "NaN", (a: any) => a.rsi = "101", (a: any) => a.rsi = "-1",
    (a: any) => a.position.quantity = "0", (a: any) => a.position.leverage = "10",
    (a: any) => a.next_buy.stage = 4, (a: any) => a.next_buy.maximum_fill_price = null,
    (a: any) => a.next_buy.status = "buy_now", (a: any) => a.next_buy.reasons = ["arbitrary_text"],
  ]) {
    const d = data();
    modify(d.accounts[0].snapshot.assets[0]);
    assert.throws(() => contracts.parseFuturesAssets(d, tenant));
  }
  const duplicate = data();
  duplicate.accounts[0].snapshot.assets[1].symbol = "BNBUSDT";
  assert.throws(() => contracts.parseFuturesAssets(duplicate, tenant));
});
test("stale or missing indicators cannot masquerade as fresh buying conditions", () => {
  for (const change of [{ data_fresh: false }, { indicator_at: null },
    { indicator_at: "2026-11-01T17:00:00+00:00" }, { next_signal_check: "2026-11-01T16:00:00+00:00" }]) {
    const d = data();
    Object.assign(d.accounts[0].snapshot, change);
    assert.throws(() => contracts.parseFuturesAssets(d, tenant));
  }
});
test("asset table presents exact fill ceiling, position, RSI time and unresolved rearm", () => {
  const html = render(data());
  assert.match(html, /25\.12/);
  assert.match(html, /Ø Einstieg 100\.01 USDT/);
  assert.match(html, /Ausführung höchstens 95\.00 USDT/);
  assert.match(html, /Kaufstufe 2/);
  assert.match(html, /Wartet auf RSI-Rearm über 30/);
  assert.match(html, /RSI-Kerzenschluss/);
  assert.match(html, /Nächster H1-Signalcheck/);
  assert.match(html, /nicht vorhersagen/);
  assert.match(html, /sechste Stufe bleibt manuell/);
});
test("unavailable runtime differs from flat basket; stage6 and stale state stay explicit", () => {
  assert.match(render(null), /derzeit nicht verfügbar/);
  const missing = data();
  missing.accounts[0].snapshot = null;
  const missingHtml = render(missing);
  assert.match(missingHtml, /Positionen sind noch nicht verfügbar/);
  assert.doesNotMatch(missingHtml, /Kein offener Basket/);
  const d = data(), a = d.accounts[0].snapshot.assets[0];
  a.position = null;
  a.next_buy = { stage: 1, maximum_fill_price: null, status: "waiting_rsi", reasons: [] };
  assert.match(render(d), /Kein offener Basket/);
  const manual = d.accounts[0].snapshot.assets[1];
  manual.position.regular_entries = 5;
  manual.next_buy.stage = 6;
  manual.next_buy.status = "manual_only";
  assert.match(render(d), /Manuelle Stufe 6/);
  assert.match(render(d), /kein automatischer Kauf/);
  d.accounts[0].snapshot.data_fresh = false;
  for (const asset of d.accounts[0].snapshot.assets) {
    asset.next_buy.status = "blocked";
    asset.next_buy.reasons = ["data_stale"];
  }
  assert.match(render(d), /Datenstand veraltet/);
});
test("dashboard reads asset status only behind opt-in and binds parser to current tenant", async () => {
  let calls = 0;
  const session = { tenantId: tenant, csrf: "csrf", displayName: "Tester", tenantName: "Eigenes Konto", expiresAt: 2e9 };
  const empty = { mode: "paper", live_enabled: false, tenant_id: tenant, accounts: [], positions: [], journal: [], jobs: [] };
  const dashboard = load("../src/components/dashboard.tsx", {
    "next/link": { default: "a" },
    "@/lib/auth": { getSession: async () => session },
    "@/lib/backend": { BackendError: class extends Error {}, apiRequest: async (_s: unknown, path: string) => {
      if (path === "/v1/futures-paper-assets") { calls++; return data(); }
      return empty;
    } },
    "@/lib/contracts": { parseOverview: (v: unknown) => v },
    "@/lib/backtest-contracts": {},
    "./icons": { Icon: () => null, Brand: () => null },
    "./login": {}, "./backtest-form": {}, "./backtest-result": {},
    "./paper-status": {}, "./futures-paper-settings": {}, "./futures-recovery": {},
    "./futures-paper-assets": panel,
    "@/lib/futures-paper-assets-contracts": contracts,
    "@/lib/futures-paper-settings-contracts": {}, "@/lib/paper-status-contracts": {}, "@/lib/futures-recovery-contracts": {},
  });
  const previous = process.env.COCKPIT_FUTURES_PAPER_ASSETS_PREVIEW;
  try {
    delete process.env.COCKPIT_FUTURES_PAPER_ASSETS_PREVIEW;
    const disabled = renderToStaticMarkup(await dashboard.DashboardPage({ section: "overview" }));
    assert.doesNotMatch(disabled, /Handelsassets/);
    assert.equal(calls, 0);
    process.env.COCKPIT_FUTURES_PAPER_ASSETS_PREVIEW = "1";
    const enabled = renderToStaticMarkup(await dashboard.DashboardPage({ section: "overview" }));
    assert.match(enabled, /Handelsassets/);
    assert.equal(calls, 1);
  } finally {
    if (previous === undefined) delete process.env.COCKPIT_FUTURES_PAPER_ASSETS_PREVIEW;
    else process.env.COCKPIT_FUTURES_PAPER_ASSETS_PREVIEW = previous;
  }
});
