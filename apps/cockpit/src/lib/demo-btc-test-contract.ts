import { amount, exactObject } from "./demo-account-contract.ts";
import { parseDemoBTCReadiness, type DemoBTCReadiness } from "./demo-startup-contract.ts";

export const BTC_WALLET_FIELDS = ["account_equity", "available", "locked", "isolated_margin",
  "crossed_margin", "unrealized_pnl", "coupon", "grant", "asset_mode"] as const;
export type BTCPreview = {
  schema: "investalo-demo-btc-test-preview/1"; symbol: "BTCUSDT"; environment: "demo";
  product_type: "USDT-FUTURES"; side: "long"; order_type: "limit"; force: "ioc";
  leverage: 2; margin_mode: "isolated"; quantity_btc: string; limit_price_usdt: string;
  quote_ask_usdt: string; maximum_notional_usdt: string; initial_margin_estimate_usdt: string;
  notional_cap_usdt: "20"; fees_verified: false; account_verified: false;
  native_max_quantity_btc: string | null; maximum_quantity_verified: boolean;
  submission_enabled: false; observed_ms: number; source_sha256: string[];
};
export type DemoBTCTest = { schema: "investalo-demo-btc-test/1"; observed_at: string;
  readiness: DemoBTCReadiness; preview: BTCPreview;
  unknown_wallet_fields: typeof BTC_WALLET_FIELDS[number][]; execution_enabled: false };
const fail = () => new Error("DEMO_BTC_TEST_REJECTED");
// Exact decimal comparisons; no rounded Number arithmetic for order values.
function decimal(value: string): [bigint, number] {
  const [whole, fraction = ""] = value.split(".");
  return [BigInt(whole + fraction), fraction.length];
}
function compare(a: [bigint, number], b: [bigint, number]) {
  return a[0] * 10n ** BigInt(b[1]) - b[0] * 10n ** BigInt(a[1]);
}
export function parseDemoBTCTest(value: unknown, tenant: string, accountId?: string): DemoBTCTest {
  const v = exactObject(value, ["schema", "observed_at", "readiness", "preview", "unknown_wallet_fields",
    "execution_enabled"]);
  if (v.schema !== "investalo-demo-btc-test/1" || v.execution_enabled !== false) throw fail();
  const readiness = parseDemoBTCReadiness(v.readiness, tenant, accountId);
  const p = exactObject(v.preview, ["schema", "symbol", "environment", "product_type", "side", "order_type",
    "force", "leverage", "margin_mode", "quantity_btc", "limit_price_usdt", "quote_ask_usdt",
    "maximum_notional_usdt", "initial_margin_estimate_usdt", "notional_cap_usdt", "fees_verified",
    "account_verified", "native_max_quantity_btc", "maximum_quantity_verified", "submission_enabled",
    "observed_ms", "source_sha256"]);
  for (const [key, expected] of Object.entries({ schema: "investalo-demo-btc-test-preview/1",
    symbol: "BTCUSDT", environment: "demo", product_type: "USDT-FUTURES", side: "long",
    order_type: "limit", force: "ioc", leverage: 2, margin_mode: "isolated", notional_cap_usdt: "20",
    fees_verified: false, account_verified: false, submission_enabled: false })) {
    if (p[key] !== expected) throw fail();
  }
  for (const key of ["quantity_btc", "limit_price_usdt", "quote_ask_usdt", "maximum_notional_usdt",
    "initial_margin_estimate_usdt"]) {
    const val = amount(p[key], false)!;
    if (!/^[0-9]+(?:\.[0-9]+)?$/.test(val) || decimal(val)[0] <= 0n) throw fail();
  }
  const qty = decimal(p.quantity_btc as string), price = decimal(p.limit_price_usdt as string),
    ask = decimal(p.quote_ask_usdt as string), notional = decimal(p.maximum_notional_usdt as string),
    margin = decimal(p.initial_margin_estimate_usdt as string);
  if (compare([qty[0] * price[0], qty[1] + price[1]], notional) !== 0n ||
    compare([margin[0] * 2n, margin[1]], notional) !== 0n || compare(notional, [20n, 0]) > 0n ||
    compare(price, ask) < 0n || compare(price, [ask[0] * 1001n, ask[1] + 3]) > 0n) throw fail();
  const maximum = amount(p.native_max_quantity_btc);
  if (typeof p.maximum_quantity_verified !== "boolean" || p.maximum_quantity_verified !== (maximum !== null) ||
    maximum !== null && (!/^[0-9]+(?:\.[0-9]+)?$/.test(maximum) ||
      decimal(maximum)[0] <= 0n || compare(qty, decimal(maximum)) > 0n)) throw fail();
  if (!Number.isSafeInteger(p.observed_ms) || Number(p.observed_ms) < 0 ||
    !Array.isArray(p.source_sha256) || p.source_sha256.length !== 2 ||
    p.source_sha256.some(s => typeof s !== "string" || !/^[0-9a-f]{64}$/.test(s))) throw fail();
  if (typeof v.observed_at !== "string" || v.observed_at.length > 40 || !/(?:Z|\+00:00)$/.test(v.observed_at) ||
    !Number.isFinite(Date.parse(v.observed_at)) || Date.parse(v.observed_at) > Date.parse(readiness.observed_at) ||
    Date.parse(v.observed_at) > Number(p.observed_ms)) throw fail();
  if (!Array.isArray(v.unknown_wallet_fields) ||
    v.unknown_wallet_fields.some(f => !BTC_WALLET_FIELDS.includes(f)) ||
    JSON.stringify(v.unknown_wallet_fields) !== JSON.stringify(BTC_WALLET_FIELDS.filter(f =>
      (v.unknown_wallet_fields as unknown[]).includes(f))) ||
    v.unknown_wallet_fields.length > 0 && !readiness.blockers.includes("wallet_unknown")) throw fail();
  return { schema: "investalo-demo-btc-test/1", observed_at: v.observed_at, readiness,
    preview: p as BTCPreview, unknown_wallet_fields: [...v.unknown_wallet_fields], execution_enabled: false };
}
