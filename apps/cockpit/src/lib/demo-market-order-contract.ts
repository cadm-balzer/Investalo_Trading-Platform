import { amount, exactObject } from "./demo-account-contract.ts";
import { canonicalUuid, credentialInteger } from "./credential-action-contracts.ts";
import { parseDemoBTCMarketTest, type DemoBTCMarketTest } from "./demo-btc-test-contract.ts";

export const MARKET_CONFIRMATION = "btc-demo-market-long-isolated-2x-estimate-20-usdt";
export const MARKET_CLOSE_CONFIRMATION = "btc-demo-market-close-owned-long-reduce-only";
export type MarketConsent = { platform_account_id: string; connection_id: string; credential_revision: 1;
  storage_version: number; command_id: string; intent_sha256: string; outbox_receipt: {
    schema: "bitget-classic-demo-outbox/1"; outbox_id: string; binding_digest: string; revision: number;
    head: string; state_digest: string }; confirmation: typeof MARKET_CONFIRMATION | typeof MARKET_CLOSE_CONFIRMATION };
export type MarketPrepared = { schema: "investalo-demo-market-prepared/1"; report: DemoBTCMarketTest;
  consent_request: MarketConsent; expires_ms: number };
export type MarketStatus = { schema: "investalo-demo-market-status/1"; command_id: string;
  state: "prepared" | "submission_unknown" | "acknowledged" | "live" | "partially_filled" | "filled" | "canceled";
  requested_quantity_btc: string; filled_quantity_btc: string | null; average_price_usdt: string | null;
  reported_fee_usdt: string | null; observed_ms: number | null; position_matched: boolean; order_resubmit_allowed: false };
export type MarketClosePrepared = { schema: "investalo-demo-market-close-prepared/1"; tenant_id: string; account_id: string;
  quantity_btc: string; reference_price_usdt: string; estimated_notional_usdt: string; observed_ms: number;
  consent_request: MarketConsent; expires_ms: number };
export type MarketCloseStatus = { schema: "investalo-demo-market-close-status/1"; order: MarketStatus;
  settlement: null | { observed_at: string; wallet: { equity: string | null; available: string | null;
    locked: string | null; unrealized_pnl: string | null; isolated_margin: string | null; crossed_margin: string | null };
    open_position_count: number; position_closed: boolean; opening_reported_fee_usdt: string | null } };
export type MarketPreparation = MarketPrepared | MarketClosePrepared;
export type MarketOutcome = MarketStatus | MarketCloseStatus;
const fail = () => new Error("MARKET_TEST_REJECTED");
const hash = (v: unknown) => { if (typeof v !== "string" || !/^[a-f0-9]{64}$/.test(v)) throw fail(); return v; };
export function parseMarketConsent(value: unknown, account: string,
  confirmation: MarketConsent["confirmation"] = MARKET_CONFIRMATION): MarketConsent {
  const v = exactObject(value, ["platform_account_id", "connection_id", "credential_revision", "storage_version",
    "command_id", "intent_sha256", "outbox_receipt", "confirmation"]);
  const r = exactObject(v.outbox_receipt, ["schema", "outbox_id", "binding_digest", "revision", "head", "state_digest"]);
  if (v.platform_account_id !== account || v.credential_revision !== 1 || v.confirmation !== confirmation ||
    r.schema !== "bitget-classic-demo-outbox/1") throw fail();
  return { platform_account_id: canonicalUuid(v.platform_account_id), connection_id: canonicalUuid(v.connection_id),
    credential_revision: 1, storage_version: credentialInteger(v.storage_version, 1),
    command_id: canonicalUuid(v.command_id), intent_sha256: hash(v.intent_sha256),
    outbox_receipt: { schema: r.schema, outbox_id: canonicalUuid(r.outbox_id),
      binding_digest: hash(r.binding_digest), revision: credentialInteger(r.revision, 1),
      head: hash(r.head), state_digest: hash(r.state_digest) }, confirmation };
}
export function parseMarketClosePrepared(value: unknown, tenant: string, account?: string): MarketClosePrepared {
  const v = exactObject(value, ["schema", "tenant_id", "account_id", "quantity_btc", "reference_price_usdt",
    "estimated_notional_usdt", "observed_ms", "consent_request", "expires_ms"]);
  if (v.schema !== "investalo-demo-market-close-prepared/1" || v.tenant_id !== tenant ||
    account && v.account_id !== account || !Number.isSafeInteger(v.observed_ms) || Number(v.observed_ms) < 0 ||
    !Number.isSafeInteger(v.expires_ms) || v.expires_ms !== Number(v.observed_ms)+30000) throw fail();
  const q = amount(v.quantity_btc, false)!, p = amount(v.reference_price_usdt, false)!,
    n = amount(v.estimated_notional_usdt, false)!;
  if ([q,p,n].some(x => !/^[0-9]+(?:\.[0-9]+)?$/.test(x) || compare(x,"0")<=0n)) throw fail();
  const decimal = (x: string) => { const [w,f=""] = x.split("."); return [BigInt(w+f),f.length] as const; };
  const [qi,qs]=decimal(q),[pi,ps]=decimal(p),[ni,ns]=decimal(n);
  if (qi*pi*10n**BigInt(ns)!==ni*10n**BigInt(qs+ps)) throw fail();
  return { schema: v.schema, tenant_id: canonicalUuid(v.tenant_id), account_id: canonicalUuid(v.account_id),
    quantity_btc:q,reference_price_usdt:p,estimated_notional_usdt:n,observed_ms:Number(v.observed_ms),
    expires_ms:Number(v.expires_ms),consent_request:parseMarketConsent(v.consent_request,String(v.account_id),MARKET_CLOSE_CONFIRMATION) };
}
export function parseMarketPrepared(value: unknown, tenant: string, account?: string): MarketPrepared {
  const v = exactObject(value, ["schema", "report", "consent_request", "expires_ms"]);
  if (v.schema !== "investalo-demo-market-prepared/1") throw fail();
  const report = parseDemoBTCMarketTest(v.report, tenant, account);
  if (!Number.isSafeInteger(v.expires_ms) || v.expires_ms !== report.preview.observed_ms + 30000) throw fail();
  return { schema: v.schema, report, consent_request: parseMarketConsent(v.consent_request,
    report.readiness.account.account_id), expires_ms: Number(v.expires_ms) };
}
function compare(a: string, b: string) {
  const [wa, fa = ""] = a.split("."), [wb, fb = ""] = b.split(".");
  return BigInt(wa+fa) * 10n ** BigInt(fb.length) - BigInt(wb+fb) * 10n ** BigInt(fa.length);
}
export function parseMarketStatus(value: unknown, command?: string): MarketStatus {
  const v = exactObject(value, ["schema", "command_id", "state", "requested_quantity_btc", "filled_quantity_btc",
    "average_price_usdt", "reported_fee_usdt", "observed_ms", "position_matched", "order_resubmit_allowed"]);
  if (v.schema !== "investalo-demo-market-status/1" || v.order_resubmit_allowed !== false ||
    typeof v.position_matched !== "boolean" ||
    !["prepared", "submission_unknown", "acknowledged", "live", "partially_filled", "filled", "canceled"].includes(v.state as string) ||
    command && v.command_id !== command) throw fail();
  const q = amount(v.requested_quantity_btc, false)!, filled = amount(v.filled_quantity_btc), price = amount(v.average_price_usdt);
  if (compare(q, "0") <= 0n || filled !== null && (compare(filled, "0") < 0n || compare(filled, q) > 0n) ||
    price !== null && compare(price, "0") <= 0n || price !== null && (filled === null || compare(filled, "0") === 0n) ||
    filled !== null && compare(filled, "0") > 0n && price === null ||
    v.state === "filled" && (filled === null || compare(filled, q) !== 0n) ||
    v.state === "partially_filled" && (filled === null || compare(filled, "0") <= 0n || compare(filled, q) >= 0n) ||
    ["prepared", "submission_unknown", "acknowledged"].includes(v.state as string) && filled !== null ||
    v.observed_ms !== null && (!Number.isSafeInteger(v.observed_ms) || Number(v.observed_ms) < 0)) throw fail();
  return { schema: v.schema, command_id: canonicalUuid(v.command_id), state: v.state as MarketStatus["state"],
    requested_quantity_btc: q, filled_quantity_btc: filled, average_price_usdt: price,
    reported_fee_usdt: amount(v.reported_fee_usdt), observed_ms: v.observed_ms as number | null,
    position_matched: v.position_matched, order_resubmit_allowed: false };
}
export function parseMarketOutcome(value: unknown, command?: string): MarketOutcome {
  if (!(value && typeof value==="object" && "schema" in value &&
    value.schema==="investalo-demo-market-close-status/1")) return parseMarketStatus(value,command);
  const v=exactObject(value,["schema","order","settlement"]),order=parseMarketStatus(v.order,command);
  if (v.settlement===null) return {schema:"investalo-demo-market-close-status/1",order,settlement:null};
  const s=exactObject(v.settlement,["observed_at","wallet","open_position_count","position_closed","opening_reported_fee_usdt"]);
  const w=exactObject(s.wallet,["equity","available","locked","unrealized_pnl","isolated_margin","crossed_margin"]);
  if (typeof s.observed_at!=="string" || !/(?:Z|\+00:00)$/.test(s.observed_at) ||
    !Number.isFinite(Date.parse(s.observed_at)) || !Number.isSafeInteger(s.open_position_count) ||
    Number(s.open_position_count)<0 || Number(s.open_position_count)>100 || typeof s.position_closed!=="boolean") throw fail();
  const wallet=Object.fromEntries(Object.entries(w).map(([k,val])=>[k,amount(val)])) as NonNullable<MarketCloseStatus["settlement"]>["wallet"];
  if (s.position_closed && (s.open_position_count!==0 || order.state!=="filled" || !order.position_matched ||
    [wallet.locked,wallet.unrealized_pnl,wallet.isolated_margin,wallet.crossed_margin].some(x=>x===null || compare(x,"0")!==0n))) throw fail();
  return {schema:"investalo-demo-market-close-status/1",order,settlement:{observed_at:s.observed_at,wallet,
    open_position_count:Number(s.open_position_count),position_closed:s.position_closed,
    opening_reported_fee_usdt:amount(s.opening_reported_fee_usdt)}};
}
