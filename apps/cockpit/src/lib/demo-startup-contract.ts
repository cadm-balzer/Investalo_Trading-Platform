import { amount, exactObject, parseDemoAccount, type DemoAccount } from "./demo-account-contract.ts";

export const STARTUP_SYMBOLS = ["AVAXUSDT", "BNBUSDT", "BTCUSDT", "ETHUSDT", "LINKUSDT", "SOLUSDT", "XRPUSDT"] as const;
export const ORDER_CATEGORIES = ["live", "partially_filled", "normal_plan", "track_plan", "profit_loss"] as const;
export const STARTUP_BLOCKERS = ["initial_balance_changed", "wallet_unknown", "wallet_collateral",
  "positions_present", "orders_present", "order_pages_incomplete", "configuration_mismatch"] as const;
export type DemoStartup = { schema: "investalo-demo-startup/1"; account: DemoAccount; observed_at: string;
  configurations: { symbol: string; margin_mode: "isolated" | "crossed" | null;
    position_mode: "one_way_mode" | "hedge_mode" | null; asset_mode: "single" | "union" | null;
    long_leverage: string | null; matches: boolean }[];
  orders: { category: typeof ORDER_CATEGORIES[number]; count: number; pages: number; complete: boolean }[];
  blockers: typeof STARTUP_BLOCKERS[number][]; expected_initial_usdt: "10000";
  pending_scope_verified: false; costs_verified: false; execution_enabled: false };
export type DemoBTCReadiness = Omit<DemoStartup, "schema"> & { schema: "investalo-demo-btc-readiness/1" };
const fail = () => new Error("DEMO_STARTUP_REJECTED");
export function parseDemoStartup(value: unknown, tenant: string, accountId?: string): DemoStartup {
  return { ...parseReadiness(value, tenant, accountId, "investalo-demo-startup/1", STARTUP_SYMBOLS),
    schema: "investalo-demo-startup/1" };
}
export function parseDemoBTCReadiness(value: unknown, tenant: string, accountId?: string): DemoBTCReadiness {
  return { ...parseReadiness(value, tenant, accountId, "investalo-demo-btc-readiness/1", ["BTCUSDT"]),
    schema: "investalo-demo-btc-readiness/1" };
}
function parseReadiness(value: unknown, tenant: string, accountId: string | undefined,
  schema: string, symbols: readonly string[]): Omit<DemoStartup, "schema"> {
  const v = exactObject(value, ["schema", "account", "observed_at", "configurations", "orders", "blockers",
    "expected_initial_usdt", "pending_scope_verified", "costs_verified", "execution_enabled"]);
  if (v.schema !== schema || v.expected_initial_usdt !== "10000" ||
    v.pending_scope_verified !== false || v.costs_verified !== false || v.execution_enabled !== false) throw fail();
  const account = parseDemoAccount(v.account, tenant, accountId);
  if (typeof v.observed_at !== "string" || v.observed_at.length > 40 ||
    !/(?:Z|\+00:00)$/.test(v.observed_at) || !Number.isFinite(Date.parse(v.observed_at)) ||
    Date.parse(v.observed_at) > Date.parse(account.observed_at)) throw fail();
  if (!Array.isArray(v.configurations) || v.configurations.length !== symbols.length) throw fail();
  const configurations = v.configurations.map((value, i) => {
    const c = exactObject(value, ["symbol", "margin_mode", "position_mode", "asset_mode", "long_leverage", "matches"]);
    if (c.symbol !== symbols[i] || ![null, "isolated", "crossed"].includes(c.margin_mode as any) ||
      ![null, "one_way_mode", "hedge_mode"].includes(c.position_mode as any) ||
      ![null, "single", "union"].includes(c.asset_mode as any) || typeof c.matches !== "boolean") throw fail();
    const leverage = amount(c.long_leverage);
    if (c.matches && (c.margin_mode !== "isolated" || c.position_mode !== "one_way_mode" ||
      c.asset_mode !== "single" || leverage === null || !/^0*2(?:\.0+)?$/.test(leverage))) throw fail();
    return { ...c, long_leverage: leverage } as DemoStartup["configurations"][number];
  });
  if (!Array.isArray(v.orders) || v.orders.length !== ORDER_CATEGORIES.length) throw fail();
  const orders = v.orders.map((value, i) => {
    const o = exactObject(value, ["category", "count", "pages", "complete"]);
    if (o.category !== ORDER_CATEGORIES[i] || !Number.isInteger(o.count) || Number(o.count) < 0 ||
      Number(o.count) > 1000 || !Number.isInteger(o.pages) || Number(o.pages) < 1 || Number(o.pages) > 10 ||
      typeof o.complete !== "boolean") throw fail();
    return o as DemoStartup["orders"][number];
  });
  if (!Array.isArray(v.blockers) || v.blockers.some(b => !STARTUP_BLOCKERS.includes(b)) ||
    JSON.stringify(v.blockers) !== JSON.stringify([...new Set(v.blockers)].sort())) throw fail();
  for (const [blocker, required] of [
    ["configuration_mismatch", configurations.some(c => !c.matches)],
    ["orders_present", orders.some(o => o.count > 0)],
    ["order_pages_incomplete", orders.some(o => !o.complete)],
    ["positions_present", account.positions.length > 0],
  ] as const) if (required !== v.blockers.includes(blocker)) throw fail();
  const { wallet } = account;
  const changed = wallet.equity !== null && wallet.available !== null &&
    (!/^0*10000(?:\.0+)?$/.test(wallet.equity) || !/^0*10000(?:\.0+)?$/.test(wallet.available));
  if (changed !== v.blockers.includes("initial_balance_changed") ||
    Object.values(wallet).some(v => v === null) && !v.blockers.includes("wallet_unknown")) throw fail();
  return { account, observed_at: v.observed_at, configurations, orders,
    blockers: [...v.blockers], expected_initial_usdt: "10000",
    pending_scope_verified: false, costs_verified: false, execution_enabled: false };
}
