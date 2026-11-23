import { canonicalUuid } from "./credential-action-contracts.ts";

export type DemoPosition = { symbol: string; side: "long" | "short"; quantity: string;
  entry_price: string | null; mark_price: string | null; unrealized_pnl: string | null;
  leverage: string | null; margin_mode: "isolated" | "crossed"; liquidation_price: string | null };
export type DemoAccount = { schema: "investalo-demo-account/1"; tenant_id: string; account_id: string;
  observed_at: string; currency: "USDT";
  wallet: { equity: string | null; available: string | null; locked: string | null;
    unrealized_pnl: string | null; isolated_margin: string | null; crossed_margin: string | null };
  positions: DemoPosition[] };
export type DemoAccountTarget = { platform_account_id: string; connection_id: string;
  credential_revision: 1; storage_version: number; inspection?: "startup" | "btc-test" };
const fail = () => new Error("DEMO_ACCOUNT_REJECTED");
// Shared by the browser and BFF; keep this module free of Node/secret imports.
export function exactObject(value: unknown, fields: readonly string[]): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value) ||
    ![Object.prototype, null].includes(Object.getPrototypeOf(value))) throw fail();
  const keys = Reflect.ownKeys(value);
  if (keys.length !== fields.length || fields.some(field => !Object.hasOwn(value, field)) ||
    keys.some(key => typeof key !== "string" || !fields.includes(key) ||
      !Object.hasOwn(Object.getOwnPropertyDescriptor(value, key)!, "value"))) throw fail();
  return value as Record<string, unknown>;
}
export function amount(value: unknown, nullable = true): string | null {
  if (value === null && nullable) return null;
  if (typeof value !== "string" || value.length > 96 ||
    !/^-?[0-9]+(?:\.[0-9]+)?$/.test(value) || !Number.isFinite(Number(value)) || Math.abs(Number(value)) > 1e30) throw fail();
  return value;
}
export function parseDemoAccount(value: unknown, tenant: string, account?: string): DemoAccount {
  const v = exactObject(value, ["schema", "tenant_id", "account_id", "observed_at", "currency", "wallet", "positions"]);
  if (v.schema !== "investalo-demo-account/1" || v.currency !== "USDT" ||
    canonicalUuid(v.tenant_id) !== canonicalUuid(tenant) ||
    account && canonicalUuid(v.account_id) !== canonicalUuid(account)) throw fail();
  canonicalUuid(v.account_id);
  if (typeof v.observed_at !== "string" || v.observed_at.length > 40 ||
    !/(?:Z|\+00:00)$/.test(v.observed_at) || !Number.isFinite(Date.parse(v.observed_at))) throw fail();
  const w = exactObject(v.wallet, ["equity", "available", "locked", "unrealized_pnl", "isolated_margin", "crossed_margin"]);
  const wallet = Object.fromEntries(Object.entries(w).map(([key, val]) => [key, amount(val)])) as DemoAccount["wallet"];
  if (!Array.isArray(v.positions) || v.positions.length > 100) throw fail();
  const seen = new Set<string>();
  const positions = v.positions.map(value => {
    const p = exactObject(value, ["symbol", "side", "quantity", "entry_price", "mark_price",
      "unrealized_pnl", "leverage", "margin_mode", "liquidation_price"]);
    if (typeof p.symbol !== "string" || !/^[A-Z0-9]{2,30}$/.test(p.symbol) ||
      !["long", "short"].includes(p.side as string) || !["isolated", "crossed"].includes(p.margin_mode as string)) throw fail();
    const key = `${p.symbol}:${p.side}`;
    if (seen.has(key)) throw fail();
    seen.add(key);
    const quantity = amount(p.quantity, false)!;
    if (Number(quantity) <= 0) throw fail();
    return { symbol: p.symbol, side: p.side as DemoPosition["side"], quantity,
      entry_price: amount(p.entry_price), mark_price: amount(p.mark_price),
      unrealized_pnl: amount(p.unrealized_pnl), leverage: amount(p.leverage),
      margin_mode: p.margin_mode as DemoPosition["margin_mode"], liquidation_price: amount(p.liquidation_price) };
  });
  return { schema: v.schema, tenant_id: v.tenant_id as string, account_id: v.account_id as string,
    observed_at: v.observed_at, currency: "USDT", wallet, positions };
}
