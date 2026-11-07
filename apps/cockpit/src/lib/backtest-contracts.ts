export type CryptoSymbol = "BTC/USDT" | "ETH/USDT";
export type Source = { venue: string; api_version: string; url: string | null; retrieved_at: string };
export type Costs = {
  fee_rate: string; spread_fraction: string; slippage_fraction: string;
  initial_equity: string; basket_principal: string; basket_cost_reserve: string;
};
export type Coverage = {
  requested_start: string | null; requested_end: string | null;
  actual_start: string; actual_end: string; complete: boolean | null;
  missing_leading_bars: number | null; missing_trailing_bars: number | null;
};
export type ResultSummary = {
  schema_version: "backtest-result/1"; symbol: CryptoSymbol; timeframe: "4h";
  strategy_version: "crypto-basket/1.0.0"; data_digest: string; simulation_data_digest: string; configuration_digest: string; cost_digest: string;
  source: Source; synthetic: boolean; bar_count: number; start: string; end: string;
  net_pnl: string; maximum_drawdown_fraction: string; profit_factor: string | null;
  closed_basket_count: number; cost_assumptions: Costs; equity_curve_sampled: boolean; coverage: Coverage;
  validation: { status: "not_evaluated"; reason: string };
};
export type BacktestResult = ResultSummary & {
  equity_curve: { at: string; equity: string }[];
};
export type Dataset = {
  id: string; symbol: CryptoSymbol; timeframe: "4h"; source: Source; synthetic: boolean;
  bar_count: number; start: string; end: string; data_digest: string;
  purpose: "research" | "test"; coverage_complete: boolean | null;
};
export type BacktestJob = {
  id: string; kind: "backtest"; status: "QUEUED" | "RUNNING" | "SUCCEEDED" | "FAILED";
  payload: { symbol: CryptoSymbol; timeframe: "4h"; dataset_id?: string; data_digest?: string };
  created_at: string; result_summary: ResultSummary | null;
};
export type JobDetail = BacktestJob & { tenant_id: string; result: BacktestResult | null; failure_code: string | null };
const rejected = () => new Error("BACKTEST_DATA_REJECTED");
const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
export function isUuid(value: unknown): value is string { return typeof value === "string" && uuidPattern.test(value); }
function record(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw rejected();
  return value as Record<string, unknown>;
}
function bool(value: unknown): boolean { if (typeof value !== "boolean") throw rejected(); return value; }
function integer(value: unknown, min: number, max: number): number {
  if (!Number.isSafeInteger(value) || (value as number) < min || (value as number) > max) throw rejected();
  return value as number;
}
function text(value: unknown, max: number): string {
  if (typeof value !== "string" || !value || value.length > max || /[\u0000-\u001f\u007f]/.test(value)) throw rejected();
  return value;
}
export function decimal(value: unknown, min = -1e12, max = 1e12): number {
  if (typeof value !== "string" || value.length > 64 || !/^-?(0|[1-9]\d{0,17})(\.\d{1,62})?$/.test(value)) throw rejected();
  const number = Number(value);
  if (!Number.isFinite(number) || number < min || number > max) throw rejected();
  return number;
}
function decimalString(value: unknown, min = -1e12, max = 1e12): string { decimal(value, min, max); return value as string; }
function timestamp(value: unknown): string {
  const raw = text(value, 35);
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$/.test(raw) || !Number.isFinite(Date.parse(raw))) throw rejected();
  const year = Number(raw.slice(0, 4)), month = Number(raw.slice(5, 7)), day = Number(raw.slice(8, 10));
  if (year < 1970 || month < 1 || month > 12 || day < 1 || day > new Date(Date.UTC(year, month, 0)).getUTCDate() ||
    Number(raw.slice(11, 13)) > 23 || Number(raw.slice(14, 16)) > 59 || Number(raw.slice(17, 19)) > 59) throw rejected();
  return raw;
}
function symbol(value: unknown): CryptoSymbol { if (value !== "BTC/USDT" && value !== "ETH/USDT") throw rejected(); return value; }
function timeframe(value: unknown): "4h" { if (value !== "4h") throw rejected(); return value; }
function digest(value: unknown): string { if (typeof value !== "string" || !/^[a-f0-9]{64}$/.test(value)) throw rejected(); return value; }
function id(value: unknown): string { if (!isUuid(value)) throw rejected(); return value; }
function tenant(value: unknown, tenantId: string): Record<string, unknown> {
  const raw = record(value);
  if (raw.tenant_id !== tenantId) throw rejected();
  return raw;
}
function source(value: unknown, synthetic: boolean): Source {
  const raw = record(value);
  const venue = text(raw.venue, 32), api_version = text(raw.api_version, 32), retrieved_at = timestamp(raw.retrieved_at);
  // CSV imports may explicitly contain synthetic fixtures. Provenance and the
  // synthetic warning describe different facts and must not be conflated.
  if (venue === "csv" && api_version === "csv-v1" && raw.url === null) return { venue, api_version, url: null, retrieved_at };
  if (synthetic) {
    if (venue !== "synthetic" || api_version !== "fixture-v1" || raw.url !== null) throw rejected();
    return { venue, api_version, url: null, retrieved_at };
  }
  if (venue !== "bitget" || api_version !== "3" || typeof raw.url !== "string" || raw.url.length > 2048) throw rejected();
  const endpoint = new URL(raw.url);
  if (endpoint.protocol !== "https:" || endpoint.hostname !== "api.bitget.com" || endpoint.port ||
    endpoint.username || endpoint.password || endpoint.pathname !== "/api/v3/market/history-candles" || endpoint.hash) throw rejected();
  // The browser receives only the reviewed public endpoint, never arbitrary
  // query parameters, host names, extra source fields or internal persistence.
  return { venue, api_version, retrieved_at, url: `${endpoint.origin}${endpoint.pathname}` };
}
function period(raw: Record<string, unknown>): { start: string; end: string } {
  const start = timestamp(raw.start), end = timestamp(raw.end);
  if (Date.parse(start) >= Date.parse(end)) throw rejected();
  return { start, end };
}
function coverage(value: unknown, actual: { start: string; end: string }): Coverage {
  const raw = record(value), actual_start = timestamp(raw.actual_start), actual_end = timestamp(raw.actual_end);
  if (Date.parse(actual_start) !== Date.parse(actual.start) || Date.parse(actual_end) !== Date.parse(actual.end)) throw rejected();
  if (raw.requested_start === null && raw.requested_end === null) {
    if (raw.complete !== null || raw.missing_leading_bars !== null || raw.missing_trailing_bars !== null) throw rejected();
    return { requested_start: null, requested_end: null, actual_start, actual_end, complete: null, missing_leading_bars: null, missing_trailing_bars: null };
  }
  const requested_start = timestamp(raw.requested_start), requested_end = timestamp(raw.requested_end);
  const leading = (Date.parse(actual_start) - Date.parse(requested_start)) / 14_400_000;
  const trailing = (Date.parse(requested_end) - Date.parse(actual_end)) / 14_400_000;
  const missing_leading_bars = integer(raw.missing_leading_bars, 0, 10_000);
  const missing_trailing_bars = integer(raw.missing_trailing_bars, 0, 10_000);
  const complete = bool(raw.complete);
  if (!Number.isInteger(leading) || !Number.isInteger(trailing) || leading !== missing_leading_bars ||
    trailing !== missing_trailing_bars || complete !== (leading === 0 && trailing === 0)) throw rejected();
  return { requested_start, requested_end, actual_start, actual_end, complete, missing_leading_bars, missing_trailing_bars };
}
export function parseResult(value: unknown, includeCurve = false): ResultSummary | BacktestResult {
  const raw = record(value);
  if (raw.schema_version !== "backtest-result/1" || raw.strategy_version !== "crypto-basket/1.0.0") throw rejected();
  const synthetic = bool(raw.synthetic), costs = record(raw.cost_assumptions), validation = record(raw.validation);
  if (validation.status !== "not_evaluated") throw rejected();
  const actual = period(raw);
  const result: ResultSummary = {
    schema_version: "backtest-result/1", symbol: symbol(raw.symbol), timeframe: timeframe(raw.timeframe),
    strategy_version: "crypto-basket/1.0.0", data_digest: digest(raw.data_digest), simulation_data_digest: digest(raw.simulation_data_digest),
    configuration_digest: digest(raw.configuration_digest), cost_digest: digest(raw.cost_digest),
    source: source(raw.source, synthetic), synthetic, bar_count: integer(raw.bar_count, 1, 10_000), ...actual,
    net_pnl: decimalString(raw.net_pnl), maximum_drawdown_fraction: decimalString(raw.maximum_drawdown_fraction, 0, 1),
    profit_factor: raw.profit_factor === null ? null : decimalString(raw.profit_factor, 0, 1e9),
    closed_basket_count: integer(raw.closed_basket_count, 0, 10_000), equity_curve_sampled: bool(raw.equity_curve_sampled),
    coverage: coverage(raw.coverage, actual),
    cost_assumptions: {
      fee_rate: decimalString(costs.fee_rate, 0, 1), spread_fraction: decimalString(costs.spread_fraction, 0, 1),
      slippage_fraction: decimalString(costs.slippage_fraction, 0, 1), initial_equity: decimalString(costs.initial_equity, 0.01),
      basket_principal: decimalString(costs.basket_principal, 0.01), basket_cost_reserve: decimalString(costs.basket_cost_reserve, 0),
    },
    // API reasons are not displayed verbatim: no unknown operational text can
    // leak through a persistence result into the cockpit.
    validation: { status: "not_evaluated", reason: "Unabhängige Holdout-Prüfung und Freigabe stehen aus." },
  };
  if (typeof validation.reason !== "string" || validation.reason.length > 500) throw rejected();
  if (!includeCurve) return result;
  if (!Array.isArray(raw.equity_curve) || raw.equity_curve.length < 1 || raw.equity_curve.length > 2000 ||
    raw.equity_curve.length > result.bar_count * 4 + 1) throw rejected();
  let previous = -Infinity;
  const equity_curve = raw.equity_curve.map(point => {
    const item = record(point), at = timestamp(item.at), ms = Date.parse(at);
    if (ms < previous || ms < Date.parse(result.start) || ms > Date.parse(result.end)) throw rejected();
    previous = ms;
    return { at, equity: decimalString(item.equity, 0) };
  });
  return { ...result, equity_curve };
}
export function parseDatasets(value: unknown, tenantId: string): Dataset[] {
  const raw = tenant(value, tenantId);
  if (!Array.isArray(raw.datasets) || raw.datasets.length > 1000) throw rejected();
  const seen = new Set<string>();
  return raw.datasets.map(value => {
    const item = record(value), datasetId = id(item.id), synthetic = bool(item.synthetic);
    if (seen.has(datasetId) || !["research", "test"].includes(item.purpose as string) ||
      (synthetic && item.purpose !== "test")) throw rejected();
    seen.add(datasetId);
    return { id: datasetId, symbol: symbol(item.symbol), timeframe: timeframe(item.timeframe), source: source(item.source, synthetic),
      synthetic, bar_count: integer(item.bar_count, 1, 10_000), ...period(item), data_digest: digest(item.data_digest),
      purpose: item.purpose as "research" | "test", coverage_complete: item.coverage_complete === null ? null : bool(item.coverage_complete) };
  });
}
export function parseJob(value: unknown): BacktestJob {
  const raw = record(value), payload = record(raw.payload);
  // Persisted API states are lowercase; the presentation uses uppercase.
  // Normalize only the reviewed enum, never arbitrary casing or unknown states.
  const statuses: Record<string, BacktestJob["status"]> = {
    queued: "QUEUED", running: "RUNNING", succeeded: "SUCCEEDED", failed: "FAILED",
    QUEUED: "QUEUED", RUNNING: "RUNNING", SUCCEEDED: "SUCCEEDED", FAILED: "FAILED",
  };
  if (raw.kind !== "backtest" || typeof raw.status !== "string" || !Object.hasOwn(statuses, raw.status)) throw rejected();
  const status = statuses[raw.status];
  const safePayload = { symbol: symbol(payload.symbol), timeframe: timeframe(payload.timeframe),
    ...(payload.dataset_id === undefined ? {} : { dataset_id: id(payload.dataset_id) }),
    ...(payload.data_digest === undefined ? {} : { data_digest: digest(payload.data_digest) }) };
  const result = raw.result_summary == null ? null : parseResult(raw.result_summary);
  if (result && (status !== "SUCCEEDED" || result.symbol !== safePayload.symbol ||
    (safePayload.data_digest !== undefined && result.data_digest !== safePayload.data_digest))) throw rejected();
  return { id: id(raw.id), kind: "backtest", status,
    payload: safePayload, created_at: timestamp(raw.created_at), result_summary: result };
}
export function parseJobResponse(value: unknown, tenantId: string): BacktestJob {
  return parseJob(tenant(value, tenantId));
}
export function parseJobDetail(value: unknown, tenantId: string, jobId: string): JobDetail {
  const raw = tenant(value, tenantId), job = parseJob(raw);
  if (job.id !== jobId || !isUuid(jobId)) throw rejected();
  const result = raw.result === null ? null : parseResult(raw.result, true) as BacktestResult;
  if ((job.status === "SUCCEEDED") !== (result !== null) ||
    (result && (result.symbol !== job.payload.symbol ||
      (job.payload.data_digest !== undefined && result.data_digest !== job.payload.data_digest)))) throw rejected();
  if (result && job.result_summary && JSON.stringify(parseResult(result)) !== JSON.stringify(job.result_summary)) throw rejected();
  const allowedFailures = ["dataset_missing", "snapshot_invalid", "configuration_mismatch", "simulation_failed", "attempts_exhausted"];
  if (raw.failure_code !== null && (typeof raw.failure_code !== "string" || !allowedFailures.includes(raw.failure_code))) throw rejected();
  if (job.status !== "FAILED" && raw.failure_code !== null) throw rejected();
  return { ...job, tenant_id: tenantId, result, failure_code: raw.failure_code as string | null };
}
export function parseBacktestRequest(value: unknown): { symbol: CryptoSymbol; timeframe: "4h"; dataset_id?: string } {
  const raw = record(value);
  if (Object.keys(raw).some(key => !["symbol", "timeframe", "dataset_id"].includes(key))) throw rejected();
  return { symbol: symbol(raw.symbol), timeframe: timeframe(raw.timeframe),
    ...(raw.dataset_id === undefined ? {} : { dataset_id: id(raw.dataset_id) }) };
}
