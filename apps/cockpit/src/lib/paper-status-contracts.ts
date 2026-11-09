import { decimal } from "./backtest-contracts.ts";

export type PaperPosition = { symbol: "BTCUSDT" | "ETHUSDT"; quantity: string; average_price: string | null; protected: boolean; risk_stopped: boolean };
export type PaperSnapshot = {
  revision: number; observed_at: string; cash: string; equity: string | null; valuation_fresh: boolean;
  trading_day: string; day_start_equity: string; daily_baseline_ready: boolean; halted: boolean; positions: PaperPosition[];
};
export type PaperAccount = {
  id: string; name: string; status: "ready" | "paused" | "disconnected"; snapshot: PaperSnapshot | null;
  journal: { revision: number; at: string; input_kind: "quote" | "bar"; fill_count: number; messages: string[] }[];
};
export type PaperStatus = { schema_version: "paper-status/1"; mode: "paper"; live_enabled: false; tenant_id: string; accounts: PaperAccount[] };
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
function time(value: unknown): value is string {
  return typeof value === "string" && value.length <= 40 && /^\d{4}-\d\d-\d\dT.*(?:Z|\+00:00)$/.test(value) && Number.isFinite(Date.parse(value));
}
function bool(value: unknown) { return typeof value === "boolean"; }
function integer(value: unknown) { return typeof value === "number" && Number.isSafeInteger(value) && value >= 0; }
function amount(value: unknown) {
  if (typeof value !== "string") return false;
  try { decimal(value, 0, 1e24); return true; } catch { return false; }
}
function object(value: unknown): value is Record<string, any> { return !!value && typeof value === "object" && !Array.isArray(value); }

/** Rebuild whitelisted output before any response/component receives tenant data. */
export function parsePaperStatus(value: unknown, tenantId: string): PaperStatus {
  const reject = () => { throw new Error("PAPER_STATUS_REJECTED"); };
  if (!object(value) || value.schema_version !== "paper-status/1" || value.mode !== "paper" ||
      value.live_enabled !== false || value.tenant_id !== tenantId || !uuid.test(tenantId) ||
      !Array.isArray(value.accounts) || value.accounts.length > 20) return reject();
  const ids = new Set<string>();
  const accounts: PaperAccount[] = value.accounts.map((a: unknown) => {
    if (!object(a) || typeof a.id !== "string" || !uuid.test(a.id) || ids.has(a.id) ||
        typeof a.name !== "string" || !a.name.length || a.name.length > 200 ||
        !["ready", "paused", "disconnected"].includes(a.status) || !Array.isArray(a.journal) || a.journal.length > 20) return reject();
    ids.add(a.id);
    let snapshot: PaperSnapshot | null = null;
    if (a.snapshot !== null) {
      const s = a.snapshot;
      if (!object(s) || !integer(s.revision) || !time(s.observed_at) || !amount(s.cash) ||
          !(s.equity === null || amount(s.equity)) || !amount(s.day_start_equity) ||
          !bool(s.valuation_fresh) || !bool(s.daily_baseline_ready) || !bool(s.halted) ||
          typeof s.trading_day !== "string" || !/^\d{4}-\d\d-\d\d$/.test(s.trading_day) ||
          !Array.isArray(s.positions) || s.positions.length !== 2) return reject();
      const positions: PaperPosition[] = s.positions.map((p: unknown, i: number) => {
        if (!object(p) || p.symbol !== ["BTCUSDT", "ETHUSDT"][i] || !amount(p.quantity) ||
            !(p.average_price === null || amount(p.average_price)) || !bool(p.protected) || !bool(p.risk_stopped)) return reject();
        return { symbol: p.symbol, quantity: p.quantity, average_price: p.average_price, protected: p.protected, risk_stopped: p.risk_stopped };
      });
      snapshot = { revision: s.revision, observed_at: s.observed_at, cash: s.cash, equity: s.equity,
        valuation_fresh: s.valuation_fresh, trading_day: s.trading_day, day_start_equity: s.day_start_equity,
        daily_baseline_ready: s.daily_baseline_ready, halted: s.halted, positions };
    }
    let previous = snapshot ? snapshot.revision+1 : 0;
    const journal = a.journal.map((j: unknown) => {
      if (!object(j) || !integer(j.revision) || j.revision <= 0 || j.revision >= previous || !time(j.at) ||
          !["quote", "bar"].includes(j.input_kind) || !integer(j.fill_count) || j.fill_count > 20 ||
          !Array.isArray(j.messages) || j.messages.length > 100 ||
          !j.messages.every((m: unknown) => typeof m === "string" && m.length <= 100)) return reject();
      previous = j.revision;
      return { revision: j.revision, at: j.at, input_kind: j.input_kind, fill_count: j.fill_count, messages: [...j.messages] };
    });
    return { id: a.id, name: a.name, status: a.status, snapshot, journal };
  });
  return { schema_version: "paper-status/1", mode: "paper", live_enabled: false, tenant_id: tenantId, accounts };
}
