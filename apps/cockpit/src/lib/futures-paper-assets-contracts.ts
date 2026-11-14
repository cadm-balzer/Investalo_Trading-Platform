/** Current acknowledged own Paper view; no order authority. */
export const buyStates = {
  blocked: "Kaufprüfung gesperrt", warming: "Indikatoren werden aufgebaut",
  manual_only: "Manuelle Reserve · kein automatischer Kauf",
  waiting_rearm: "Wartet auf RSI-Rearm über 30",
  waiting_rsi: "Wartet auf RSI unter 30",
  waiting_confirmation: "Wartet auf zweiten Kerzenschluss unter 30",
  waiting_price: "Wartet auf weiteren Preisrückgang",
  waiting_signal_check: "Wartet auf nächsten H1-Kerzenschluss",
  signal_confirmed: "RSI-Bedingung erfüllt · Ausführung noch zu prüfen",
} as const;
export const buyReasons = {
  account_unavailable: "Konto pausiert oder nicht bereit",
  liquidation_stop: "Asset nach Liquidation gesperrt",
  account_halt: "Kontoprüfung oder Liquidationsabgleich erforderlich",
  exit_protection: "Ausstiegsschutz aktiv",
  data_stale: "Aktuelle Quotes oder H1-Kerzen fehlen",
  capacity_full: "Alle finanzierten Basketplätze belegt",
} as const;
export type FuturesAsset = {
  symbol: string; rsi: string | null; rsi_confirmations: number; rearmed: boolean; reference_bid: string;
  position: null | { quantity: string; average_entry: string; leverage: string; regular_entries: number;
    last_entry_price: string };
  next_buy: { stage: number; maximum_fill_price: string | null; status: keyof typeof buyStates;
    reasons: (keyof typeof buyReasons)[] };
};
export type FuturesAssetSnapshot = {
  revision: number; observed_at: string; indicator_at: string | null; next_signal_check: string;
  data_fresh: boolean; rsi_period: 14; timeframe: "H1"; assets: FuturesAsset[];
};
export type FuturesAssets = {
  schema_version: "futures-paper-assets/1"; tenant_id: string; mode: "paper"; live_enabled: false;
  accounts: { account_id: string; account_name: string; snapshot: FuturesAssetSnapshot | null }[];
};
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
function rejected(): never { throw new Error("FUTURES_ASSETS_REJECTED"); }
function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return rejected();
  return value as Record<string, unknown>;
}
function integer(value: unknown, min: number, max: number): number {
  if (!Number.isSafeInteger(value) || (value as number) < min || (value as number) > max) return rejected();
  return value as number;
}
function amount(value: unknown, zero = false): string {
  if (typeof value !== "string" || value.length > 64 ||
      !/^\d+(?:\.\d+)?(?:[eE][+-]?\d{1,3})?$/.test(value) ||
      !Number.isFinite(Number(value)) || Number(value) < 0 || (!zero && Number(value) === 0)) return rejected();
  return value;
}
function time(value: unknown): string {
  if (typeof value !== "string" || value.length > 40 ||
      !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)$/.test(value) ||
      !Number.isFinite(Date.parse(value))) return rejected();
  return value;
}
function asset(value: unknown): FuturesAsset {
  const a = object(value), n = object(a.next_buy);
  if (typeof a.symbol !== "string" || !/^[A-Z0-9]{2,16}USDT$/.test(a.symbol) ||
      typeof a.rearmed !== "boolean" || typeof n.status !== "string" ||
      !Object.hasOwn(buyStates, n.status) || !Array.isArray(n.reasons) ||
      n.reasons.length > 6 || new Set(n.reasons).size !== n.reasons.length ||
      n.reasons.some(r => typeof r !== "string" || !Object.hasOwn(buyReasons, r))) return rejected();
  const rsi = a.rsi === null ? null : amount(a.rsi, true);
  if (rsi !== null && Number(rsi) > 100) return rejected();
  const p = a.position === null ? null : object(a.position);
  const position = p === null ? null : {
    quantity: amount(p.quantity), average_entry: amount(p.average_entry), leverage: amount(p.leverage),
    regular_entries: integer(p.regular_entries, 1, 5), last_entry_price: amount(p.last_entry_price),
  };
  if (position && Number(position.leverage) !== 2) return rejected();
  const next = { stage: integer(n.stage, 1, 6),
    maximum_fill_price: n.maximum_fill_price === null ? null : amount(n.maximum_fill_price),
    status: n.status as keyof typeof buyStates, reasons: n.reasons as (keyof typeof buyReasons)[] };
  if ((position === null && (next.stage !== 1 || next.maximum_fill_price !== null)) ||
      (position && (next.stage !== position.regular_entries + 1 || next.maximum_fill_price === null)) ||
      (next.status === "blocked") !== (next.reasons.length > 0) ||
      (next.status === "manual_only" && next.stage !== 6)) return rejected();
  return { symbol: a.symbol, rsi, rsi_confirmations: integer(a.rsi_confirmations, 0, 2),
    rearmed: a.rearmed, reference_bid: amount(a.reference_bid), position, next_buy: next };
}
export function parseFuturesAssets(value: unknown, tenantId: string): FuturesAssets {
  const x = object(value);
  if (x.schema_version !== "futures-paper-assets/1" || !uuid.test(tenantId) ||
      x.tenant_id !== tenantId || x.mode !== "paper" || x.live_enabled !== false ||
      !Array.isArray(x.accounts) || x.accounts.length > 20) return rejected();
  const accounts = x.accounts.map(value => {
    const a = object(value);
    if (typeof a.account_id !== "string" || !uuid.test(a.account_id) ||
        typeof a.account_name !== "string" || !a.account_name.length || a.account_name.length > 200) return rejected();
    let snapshot: FuturesAssetSnapshot | null = null;
    if (a.snapshot !== null) {
      const s = object(a.snapshot);
      if (typeof s.data_fresh !== "boolean" || s.rsi_period !== 14 || s.timeframe !== "H1" ||
          !Array.isArray(s.assets) || s.assets.length < 3 || s.assets.length > 7) return rejected();
      const assets = s.assets.map(asset);
      if (new Set(assets.map(a => a.symbol)).size !== assets.length) return rejected();
      const observed = time(s.observed_at), indicator = s.indicator_at === null ? null : time(s.indicator_at);
      const next = time(s.next_signal_check);
      if ((indicator && Date.parse(indicator) > Date.parse(observed)) ||
          Date.parse(next) <= Date.parse(observed) ||
          (s.data_fresh && (!indicator || assets.some(a => a.next_buy.reasons.includes("data_stale")))) ||
          (!s.data_fresh && assets.some(a => !a.next_buy.reasons.includes("data_stale")))) return rejected();
      snapshot = { revision: integer(s.revision, 0, Number.MAX_SAFE_INTEGER), observed_at: observed,
        indicator_at: indicator, next_signal_check: next, data_fresh: s.data_fresh,
        rsi_period: 14, timeframe: "H1", assets };
    }
    return { account_id: a.account_id, account_name: a.account_name, snapshot };
  });
  if (new Set(accounts.map(a => a.account_id)).size !== accounts.length) return rejected();
  return { schema_version: "futures-paper-assets/1", tenant_id: tenantId, mode: "paper", live_enabled: false, accounts };
}
