import test from "node:test";
import assert from "node:assert/strict";
import { parsePaperStatus } from "../src/lib/paper-status-contracts.ts";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import ts from "typescript";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

// Compile only this server component with the existing pinned TypeScript.
// No new browser/test tooling or network required.
const source = readFileSync(new URL("../src/components/paper-status.tsx", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
}).outputText;
const panelModule = { exports: {} as any };
new Function("require", "module", "exports", compiled)(createRequire(import.meta.url), panelModule, panelModule.exports);
const render = (value: unknown) => renderToStaticMarkup(React.createElement(panelModule.exports.PaperStatusPanel, {
  data: value === null ? null : parsePaperStatus(value, tenant),
}));

const tenant = "00000000-0000-4000-8000-000000000001", account = "00000000-0000-4000-8000-000000000002";
function data() {
  return {
    schema_version: "paper-status/1", tenant_id: tenant, mode: "paper", live_enabled: false,
    accounts: [{ id: account, name: "Paper", status: "ready", snapshot: {
      revision: 1, observed_at: "2026-01-01T12:00:00Z", cash: "10000", equity: "10000",
      valuation_fresh: true, trading_day: "2026-01-01", day_start_equity: "10000",
      daily_baseline_ready: true, day_basis_model: false, halted: false, positions: ["BTCUSDT", "ETHUSDT"].map(symbol =>
        ({ symbol, quantity: "0", average_price: null, protected: false, risk_stopped: false })),
    }, journal: [{ revision: 1, at: "2026-01-01T12:00:00Z", input_kind: "quote", fill_count: 0, messages: [] }] }],
  };
}
test("paper status preserves confirmed zero positions and explicit baseline gate", () => {
  const input = data(); input.accounts[0].snapshot.daily_baseline_ready = false;
  const parsed = parsePaperStatus(input, tenant);
  assert.equal(parsed.accounts[0].snapshot?.positions[0].quantity, "0");
  assert.equal(parsed.accounts[0].snapshot?.daily_baseline_ready, false);
  assert.equal(parsed.accounts[0].journal[0].fill_count, 0);
});
test("unstarted accounts remain unstarted without invented balances", () => {
  const input: any = data(); input.accounts[0].snapshot = null; input.accounts[0].journal = [];
  assert.equal(parsePaperStatus(input, tenant).accounts[0].snapshot, null);
});
test("private and unknown fields are removed at every public boundary", () => {
  const input: any = data();
  input.checkpoint = "private"; input.accounts[0].envelope = "private";
  input.accounts[0].snapshot.raw_quotes = "private"; input.accounts[0].journal[0].input_digest = "private";
  input.accounts[0].snapshot.positions[0].manual_authorization = "private";
  assert.ok(!JSON.stringify(parsePaperStatus(input, tenant)).includes("private"));
});
for (const [name, mutate] of [
  ["foreign tenant", (x: any) => { x.tenant_id = account; }],
  ["live mode", (x: any) => { x.live_enabled = true; }],
  ["duplicate account", (x: any) => { x.accounts.push(x.accounts[0]); }],
  ["unsafe revision", (x: any) => { x.accounts[0].snapshot.revision = Number.MAX_SAFE_INTEGER+1; }],
  ["nonfinite cash", (x: any) => { x.accounts[0].snapshot.cash = "NaN"; }],
  ["negative quantity", (x: any) => { x.accounts[0].snapshot.positions[0].quantity = "-1"; }],
  ["wrong symbols", (x: any) => { x.accounts[0].snapshot.positions.reverse(); }],
  ["oversized journal", (x: any) => { x.accounts[0].journal = Array(21).fill(x.accounts[0].journal[0]); }],
  ["uncommitted journal revision", (x: any) => { x.accounts[0].journal[0].revision = 2; }],
] as const) test(`paper status rejects ${name}`, () => {
  const input = data(); mutate(input); assert.throws(() => parsePaperStatus(input, tenant));
});
test("server panel displays saved funds and never claims running execution", () => {
  const html = render(data());
  assert.ok(html.includes("10.000,00"));
  assert.ok(html.includes("Letzter gespeicherter Input"));
  assert.ok(!html.includes("Worker läuft"));
});
test("server panel makes missing daily baseline a visible buy block", () => {
  const input = data(); input.accounts[0].snapshot.daily_baseline_ready = false;
  assert.ok(render(input).includes("Tagesbasis fehlt. Neue Käufe gesperrt."));
});
test("server panel labels stale valuation and unstarted accounts explicitly", () => {
  const input: any = data(); input.accounts[0].snapshot.valuation_fresh = false;
  assert.ok(render(input).includes("Historische Bewertung"));
  input.accounts[0].snapshot = null; input.accounts[0].journal = [];
  const html = render(input);
  assert.ok(html.includes("Noch kein bestätigter Paperstand"));
  assert.ok(!html.includes("10.000,00"));
});
test("server panel distinguishes unavailable provider from empty account list", () => {
  assert.ok(render(null).includes("momentan nicht verfügbar"));
  const input = data(); input.accounts = [];
  assert.ok(render(input).includes("Noch kein eigenes Crypto-Paperkonto"));
});
test("model midnight basis and day journal are explicitly labeled", () => {
  const input: any = data();
  input.accounts[0].snapshot.day_basis_model = true;
  input.accounts[0].journal[0].input_kind = "day";
  const html = render(input);
  assert.ok(html.includes("Modellbewertung um 00:00 UTC"));
  assert.ok(html.includes("Tagesbewertung"));
});
