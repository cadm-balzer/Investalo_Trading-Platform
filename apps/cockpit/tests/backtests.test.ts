import test from "node:test";
import assert from "node:assert/strict";
import { decimal, parseBacktestRequest, parseDatasets, parseJobDetail, parseJobResponse, parseResult } from "../src/lib/backtest-contracts.ts";
import { parseOverview } from "../src/lib/contracts.ts";
import { equityGeometry } from "../src/lib/equity-curve.ts";
import { limitedBody } from "../src/lib/security.ts";

const tenant = "00000000-0000-4000-8000-000000000001";
const jobId = "00000000-0000-4000-8000-000000000002";
const datasetId = "00000000-0000-4000-8000-000000000003";
const hash = "a".repeat(64);
const source = { venue: "bitget", api_version: "3", url: "https://api.bitget.com/api/v3/market/history-candles", retrieved_at: "2026-11-07T12:00:00Z" };
function result() {
  return {
    schema_version: "backtest-result/1", symbol: "BTC/USDT", timeframe: "4h", strategy_version: "crypto-basket/1.0.0",
    data_digest: hash, simulation_data_digest: hash, configuration_digest: hash, cost_digest: hash, source, synthetic: false,
    bar_count: 3, start: "2025-01-01T00:00:00Z", end: "2025-01-01T08:00:00Z",
    net_pnl: "-0.123456789012345678", maximum_drawdown_fraction: "0.01", profit_factor: null, closed_basket_count: 0,
    cost_assumptions: { fee_rate: "0.001", spread_fraction: "0.0001", slippage_fraction: "0.0002", initial_equity: "10000", basket_principal: "500", basket_cost_reserve: "5" },
    validation: { status: "not_evaluated", reason: "independent_holdout_pending" },
    coverage: { requested_start: "2025-01-01T00:00:00Z", requested_end: "2025-01-01T08:00:00Z",
      actual_start: "2025-01-01T00:00:00Z", actual_end: "2025-01-01T08:00:00Z", complete: true,
      missing_leading_bars: 0, missing_trailing_bars: 0 },
    equity_curve_sampled: false,
    equity_curve: [
      { at: "2025-01-01T00:00:00Z", equity: "10000" },
      { at: "2025-01-01T04:00:00Z", equity: "9990.25" },
      { at: "2025-01-01T08:00:00Z", equity: "9999.876543210987654322" },
    ],
  };
}
function job() {
  return { tenant_id: tenant, id: jobId, kind: "backtest", status: "SUCCEEDED", payload: { symbol: "BTC/USDT", timeframe: "4h", dataset_id: datasetId },
    created_at: "2026-11-07T12:00:00Z", result_summary: null, result: result(), failure_code: null };
}
function dataset() {
  return { id: datasetId, symbol: "BTC/USDT", timeframe: "4h", source, synthetic: false, bar_count: 3,
    start: "2025-01-01T00:00:00Z", end: "2025-01-01T08:00:00Z", data_digest: hash, purpose: "research", coverage_complete: false };
}
test("job detail requires exact authenticated tenant and requested resource before projecting results", () => {
  const parsed = parseJobDetail(job(), tenant, jobId);
  assert.equal(parsed.result!.net_pnl, "-0.123456789012345678");
  assert.equal(parsed.result!.profit_factor, null);
  assert.equal(parsed.result!.validation.status, "not_evaluated");
  for (const patch of [{ tenant_id: datasetId }, { tenant_id: undefined }, { id: datasetId },
    { status: "LIVE" }, { status: "RUNNING" }, { result: null }, { payload: { symbol: "ETH/USDT", timeframe: "4h" } },
    { payload: { ...job().payload, data_digest: "b".repeat(64) } },
    { result_summary: { ...result(), net_pnl: "100" } }]) {
    assert.throws(() => parseJobDetail({ ...job(), ...patch }, tenant, jobId));
  }
});
test("pending and failed jobs show actual states but never arbitrary failure text or operational payloads", () => {
  const failed = { ...job(), status: "FAILED", result: null, failure_code: "snapshot_invalid" };
  assert.equal(parseJobDetail(failed, tenant, jobId).failure_code, "snapshot_invalid");
  assert.equal(parseJobDetail({ ...failed, status: "QUEUED", failure_code: null }, tenant, jobId).result, null);
  assert.throws(() => parseJobDetail({ ...failed, failure_code: "secret internal error" }, tenant, jobId));
  assert.throws(() => parseJobDetail({ ...failed, status: "RUNNING" }, tenant, jobId));
  const projected = parseJobDetail({ ...job(), private_account: "PRIVATE_SENTINEL", payload: { ...job().payload, key: "PRIVATE_SENTINEL" },
    result: { ...result(), secret: "PRIVATE_SENTINEL", validation: { status: "not_evaluated", reason: "PRIVATE_SENTINEL" },
      source: { ...source, internal_user: "PRIVATE_SENTINEL", url: `${source.url}?private=PRIVATE_SENTINEL` },
      equity_curve: result().equity_curve.map(point => ({ ...point, private_account: "PRIVATE_SENTINEL" })) } }, tenant, jobId);
  assert.equal(JSON.stringify(projected).includes("PRIVATE_SENTINEL"), false);
});
test("actual API lowercase states preserve migrated failures and real results without disconnecting the overview", () => {
  // Migration 002 marks old jobs without frozen inputs as dataset_missing.
  // Their payload intentionally has no dataset ID, digest or strategy snapshot.
  const legacy = { ...job(), status: "failed", payload: { symbol: "BTC/USDT", timeframe: "4h" },
    result_summary: null, result: null, failure_code: "dataset_missing" };
  const completed = { ...job(), id: datasetId, status: "succeeded", result_summary: result() };
  const overview = { mode: "paper", live_enabled: false, tenant_id: tenant,
    accounts: [], positions: [], journal: [], jobs: [legacy, completed] };
  const parsed = parseOverview(overview, tenant);
  assert.deepEqual(parsed.jobs.map(item => item.status), ["FAILED", "SUCCEEDED"]);
  assert.deepEqual(parsed.jobs[0].payload, { symbol: "BTC/USDT", timeframe: "4h" });
  assert.equal(parsed.jobs[0].result_summary, null);
  assert.equal(parsed.jobs[1].result_summary?.synthetic, false);
  assert.equal(parsed.jobs[1].result_summary?.net_pnl, result().net_pnl);
  assert.equal(parseJobDetail(legacy, tenant, jobId).failure_code, "dataset_missing");
  assert.equal(parseJobDetail(completed, tenant, datasetId).result?.synthetic, false);
  for (const status of ["queued", "running"]) {
    assert.equal(parseJobResponse({ ...legacy, status, failure_code: null }, tenant).status, status.toUpperCase());
  }
  for (const status of ["Failed", "FAILED ", "live", "__proto__", "constructor", null, 1]) {
    assert.throws(() => parseJobResponse({ ...legacy, status }, tenant));
  }
  assert.throws(() => parseJobDetail({ ...legacy, result_summary: result() }, tenant, jobId));
  assert.throws(() => parseOverview({ ...overview, tenant_id: datasetId }, tenant));
});
test("strict decimal strings reject infinity, extreme magnitudes, exponent syntax and non-string transport", () => {
  assert.equal(decimal("0.000000000000000001"), 1e-18);
  for (const value of ["Infinity", "NaN", "1e9", "1e999", "", " 2 ", "01", ".2", "2.", "9".repeat(65), "1000000000001", 2, null]) {
    assert.throws(() => decimal(value));
  }
  for (const patch of [{ net_pnl: "1e999" }, { profit_factor: "Infinity" }, { maximum_drawdown_fraction: "1.01" },
    { maximum_drawdown_fraction: "-0.1" }, { closed_basket_count: -1 }, { bar_count: 100001 },
    { cost_assumptions: { ...result().cost_assumptions, fee_rate: "-0.001" } },
    { cost_assumptions: { ...result().cost_assumptions, initial_equity: "0" } },
    { data_digest: "path/to/private/file" }, { schema_version: "unreviewed/2" }, { strategy_version: "private/unreviewed" },
    { start: "2025-02-30T00:00:00Z" }, { end: "2025-01-01T24:00:00Z" },
    { validation: { status: "validated", reason: "claim" } }]) {
    assert.throws(() => parseResult({ ...result(), ...patch }, true));
  }
});
test("equity data is finite, ordered, bounded to its period and capped before SVG publication", () => {
  const base = result();
  for (const equity_curve of [[], Array(2001).fill(base.equity_curve[0]), [...base.equity_curve].reverse(),
    [{ ...base.equity_curve[0], equity: "-1" }, base.equity_curve[1]],
    [{ ...base.equity_curve[0], equity: "NaN" }, base.equity_curve[1]],
    [{ ...base.equity_curve[0], at: "2024-12-31T23:59:59Z" }, base.equity_curve[1]],
    [base.equity_curve[0], { ...base.equity_curve[1], at: "2025-01-01T12:00:00Z" }]]) {
    assert.throws(() => parseResult({ ...base, equity_curve }, true));
  }
  assert.throws(() => parseResult({ ...base, equity_curve_sampled: undefined }, true));
  const geometry = equityGeometry(base.equity_curve);
  assert.equal(/NaN|Infinity/.test(geometry.points), false);
  const flat = equityGeometry(base.equity_curve.map(point => ({ ...point, equity: "10000" })));
  assert.equal(new Set(flat.points.split(" ").map(point => point.split(",")[1])).size, 1);
  assert.throws(() => equityGeometry([{ ...base.equity_curve[0], equity: "Infinity" }, base.equity_curve[1]]));
  const phases = [base.equity_curve[0], { ...base.equity_curve[0], equity: "9999.123456789012345678901234567890123456" }, ...base.equity_curve.slice(1)];
  assert.equal((parseResult({ ...base, equity_curve: phases }, true) as { equity_curve: unknown[] }).equity_curve.length, 4);
  const phaseGeometry = equityGeometry(phases).points.split(" ");
  assert.equal(phaseGeometry[0].split(",")[0], phaseGeometry[1].split(",")[0]);
  assert.notEqual(phaseGeometry[0].split(",")[1], phaseGeometry[1].split(",")[1]);
  assert.equal(/NaN|Infinity/.test(equityGeometry([base.equity_curve[0]]).points), false);
});
test("dataset metadata isolates tenants, rejects external resource leakage and marks fixture/CSV provenance", () => {
  const safe = parseDatasets({ tenant_id: tenant, datasets: [dataset()] }, tenant);
  assert.equal(safe[0].coverage_complete, false);
  assert.throws(() => parseDatasets({ tenant_id: datasetId, datasets: [dataset()] }, tenant));
  assert.throws(() => parseDatasets({ tenant_id: tenant, datasets: [dataset(), dataset()] }, tenant));
  assert.throws(() => parseDatasets({ tenant_id: tenant, datasets: Array(1001).fill(dataset()) }, tenant));
  for (const url of ["https://internal.test/data", "file:///private", "https://api.bitget.com@internal.test/data",
    "https://api.bitget.com/api/v3/private/account", "https://user:password@api.bitget.com/api/v3/market/history-candles"]) {
    assert.throws(() => parseDatasets({ tenant_id: tenant, datasets: [{ ...dataset(), source: { ...source, url } }] }, tenant));
  }
  const fixture = { ...dataset(), synthetic: true, purpose: "test", source: { ...source, venue: "synthetic", api_version: "fixture-v1", url: null } };
  assert.equal(parseDatasets({ tenant_id: tenant, datasets: [fixture] }, tenant)[0].synthetic, true);
  const csvSource = { ...source, venue: "csv", api_version: "csv-v1", url: null };
  assert.equal(parseDatasets({ tenant_id: tenant, datasets: [{ ...fixture, source: csvSource }] }, tenant)[0].synthetic, true);
  assert.equal(parseResult({ ...result(), synthetic: true, source: csvSource }).synthetic, true);
  assert.equal(parseDatasets({ tenant_id: tenant, datasets: [{ ...dataset(), purpose: "test" }] }, tenant)[0].synthetic, false);
  assert.equal(parseDatasets({ tenant_id: tenant, datasets: [{ ...dataset(), purpose: "test", source: csvSource }] }, tenant)[0].source.venue, "csv");
  assert.equal(parseDatasets({ tenant_id: tenant, datasets: [{ ...dataset(), coverage_complete: null }] }, tenant)[0].coverage_complete, null);
  assert.throws(() => parseDatasets({ tenant_id: tenant, datasets: [{ ...fixture, purpose: "research" }] }, tenant));
  assert.equal(parseDatasets({ tenant_id: tenant, datasets: [{ ...dataset(), source: { ...source, venue: "csv", api_version: "csv-v1", url: null } }] }, tenant)[0].source.venue, "csv");
});
test("history coverage describes only its requested window and rejects inconsistent completeness claims", () => {
  const unknown = { ...result().coverage, requested_start: null, requested_end: null, complete: null, missing_leading_bars: null, missing_trailing_bars: null };
  assert.equal(parseResult({ ...result(), coverage: unknown }).coverage.complete, null);
  const shortfall = { ...result().coverage, requested_start: "2024-12-31T20:00:00Z", complete: false, missing_leading_bars: 1 };
  assert.equal(parseResult({ ...result(), coverage: shortfall }).coverage.missing_leading_bars, 1);
  for (const coverage of [{ ...shortfall, complete: true }, { ...shortfall, missing_leading_bars: 0 },
    { ...shortfall, missing_leading_bars: -1 }, { ...shortfall, missing_trailing_bars: 10001 },
    { ...shortfall, requested_start: "2025-01-01T01:00:00Z" },
    { ...unknown, complete: false }, { ...unknown, requested_start: result().start },
    { ...result().coverage, actual_start: "2025-01-01T04:00:00Z" }]) {
    assert.throws(() => parseResult({ ...result(), coverage }));
  }
});
test("BFF request and enqueue response accept only crypto H4 IDs and authenticated safe job fields", () => {
  assert.deepEqual(parseBacktestRequest({ symbol: "ETH/USDT", timeframe: "4h", dataset_id: datasetId }), { symbol: "ETH/USDT", timeframe: "4h", dataset_id: datasetId });
  assert.deepEqual(parseBacktestRequest({ symbol: "BTC/USDT", timeframe: "4h" }), { symbol: "BTC/USDT", timeframe: "4h" });
  for (const patch of [{ symbol: "XAUUSD" }, { timeframe: "1m" }, { dataset_id: "../other-tenant" }, { dataset_id: null }, { tenant_id: tenant }, { api_key: "PRIVATE" }]) {
    assert.throws(() => parseBacktestRequest({ symbol: "BTC/USDT", timeframe: "4h", ...patch }));
  }
  assert.equal(parseJobResponse({ ...job(), status: "QUEUED" }, tenant).id, jobId);
  assert.throws(() => parseJobResponse({ ...job(), tenant_id: datasetId }, tenant));
  const overview = { mode: "paper", live_enabled: false, tenant_id: tenant, accounts: [], positions: [], journal: [], jobs: [{ ...job(), result_summary: result() }] };
  assert.equal(parseOverview(overview, tenant).jobs[0].result_summary?.net_pnl, result().net_pnl);
  assert.throws(() => parseOverview({ ...overview, jobs: [{ ...job(), result_summary: { ...result(), net_pnl: "NaN" } }] }, tenant));
});
test("backend transport body bound also applies to streaming replies without Content-Length", async () => {
  const body = new ReadableStream<Uint8Array>({ start(controller) {
    controller.enqueue(new Uint8Array(1024 * 1024));
    controller.enqueue(new Uint8Array(1024 * 1024));
    controller.enqueue(new Uint8Array(1));
    controller.close();
  } });
  await assert.rejects(limitedBody(new Request("https://response.invalid", { method: "POST", body, duplex: "half" } as RequestInit), 2 * 1024 * 1024), /BODY_TOO_LARGE/);
});
