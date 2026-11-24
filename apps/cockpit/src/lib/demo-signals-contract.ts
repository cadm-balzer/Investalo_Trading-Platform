import { canonicalUuid } from "./credential-action-contracts.ts";
import { amount, exactObject } from "./demo-account-contract.ts";

export const DEMO_SIGNAL_SYMBOLS = ["AVAXUSDT", "BNBUSDT", "BTCUSDT", "ETHUSDT",
  "LINKUSDT", "SOLUSDT", "XRPUSDT"] as const;
export type DemoSignalAsset = {
  symbol: typeof DEMO_SIGNAL_SYMBOLS[number]; status: "confirmed" | "unavailable";
  rsi: string | null; previous_rsi: string | null; below_count: number | null;
  close_price: string | null; candle_closed_at: string | null; fetched_at: string | null;
  entry_condition: "confirmed" | "waiting_confirmation" | "waiting_rsi" | "unavailable";
};
export type DemoSignals = {
  schema: "investalo-demo-signals/1"; tenant_id: string; account_id: string;
  source: "bitget_classic_demo"; execution_enabled: false; observed_at: string;
  timeframe: "H1"; rsi_period: 14; warmup_bars: 300; next_candle_close: string;
  assets: DemoSignalAsset[];
};
const rejected = () => new Error("DEMO_SIGNALS_REJECTED");
const H1 = 3600000;
export function rsiRelation(value: string): -1 | 0 | 1 {
  const [whole, fraction = ""] = value.split(".");
  const integer = BigInt(whole);
  return integer < 30n ? -1 : integer > 30n || /[1-9]/.test(fraction) ? 1 : 0;
}
function time(value: unknown): string {
  if (typeof value !== "string" || value.length > 40 ||
      !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)$/.test(value) ||
      !Number.isFinite(Date.parse(value))) throw rejected();
  return value;
}
export function parseDemoSignals(value: unknown, tenant: string, account?: string): DemoSignals {
  const v = exactObject(value, ["schema", "tenant_id", "account_id", "source", "execution_enabled",
    "observed_at", "timeframe", "rsi_period", "warmup_bars", "next_candle_close", "assets"]);
  if (v.schema !== "investalo-demo-signals/1" || v.source !== "bitget_classic_demo" ||
      canonicalUuid(v.tenant_id) !== canonicalUuid(tenant) ||
      account && canonicalUuid(v.account_id) !== canonicalUuid(account) ||
      v.execution_enabled !== false || v.timeframe !== "H1" || v.rsi_period !== 14 ||
      v.warmup_bars !== 300 || !Array.isArray(v.assets) || v.assets.length !== DEMO_SIGNAL_SYMBOLS.length)
    throw rejected();
  canonicalUuid(v.account_id);
  const observed = time(v.observed_at), next = time(v.next_candle_close);
  const closed = Math.floor(Date.parse(observed) / H1) * H1;
  if (Date.parse(next) !== closed + H1) throw rejected();
  const assets = v.assets.map((value, i): DemoSignalAsset => {
    const a = exactObject(value, ["symbol", "status", "rsi", "previous_rsi", "below_count",
      "close_price", "candle_closed_at", "fetched_at", "entry_condition"]);
    if (a.symbol !== DEMO_SIGNAL_SYMBOLS[i] || !["confirmed", "unavailable"].includes(a.status as string))
      throw rejected();
    if (a.status === "unavailable") {
      if (["rsi", "previous_rsi", "below_count", "close_price", "candle_closed_at", "fetched_at"]
        .some(field => a[field] !== null) || a.entry_condition !== "unavailable") throw rejected();
      return { symbol: DEMO_SIGNAL_SYMBOLS[i], status: "unavailable", rsi: null, previous_rsi: null,
        below_count: null, close_price: null, candle_closed_at: null, fetched_at: null,
        entry_condition: "unavailable" };
    }
    const rsi = amount(a.rsi, false)!, previous = amount(a.previous_rsi, false)!;
    const price = amount(a.close_price, false)!;
    const candle = time(a.candle_closed_at), fetched = time(a.fetched_at);
    if (rsi.startsWith("-") || previous.startsWith("-") ||
        [rsi, previous].some(n => BigInt(n.split(".")[0]) > 100n ||
          BigInt(n.split(".")[0]) === 100n && /[1-9]/.test(n.split(".")[1] ?? "")) ||
        Number(price) <= 0 || ![0, 1, 2].includes(a.below_count as number) ||
        Date.parse(candle) !== closed || Date.parse(fetched) < closed || Date.parse(fetched) > Date.parse(observed))
      throw rejected();
    // Validate signs with decimal strings, not rounded browser display values.
    const below = (n: string) => rsiRelation(n) < 0;
    const count = below(rsi) ? (below(previous) ? 2 : 1) : 0;
    const condition = count === 2 ? "confirmed" : count === 1 ? "waiting_confirmation" : "waiting_rsi";
    if (a.below_count !== count || a.entry_condition !== condition) throw rejected();
    return { symbol: DEMO_SIGNAL_SYMBOLS[i], status: "confirmed", rsi, previous_rsi: previous,
      below_count: count, close_price: price, candle_closed_at: candle, fetched_at: fetched,
      entry_condition: condition };
  });
  return { schema: "investalo-demo-signals/1", tenant_id: v.tenant_id as string,
    account_id: v.account_id as string, source: "bitget_classic_demo", execution_enabled: false,
    observed_at: observed, timeframe: "H1", rsi_period: 14, warmup_bars: 300,
    next_candle_close: next, assets };
}
