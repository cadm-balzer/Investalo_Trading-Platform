import { canonicalUuid } from "./credential-action-contracts.ts";
import { exactObject } from "./demo-account-contract.ts";
import { DEMO_SIGNAL_SYMBOLS as SYMBOLS } from "./demo-signals-contract.ts";

export const DEMO_START_CONFIRMATION = "H1-Demohandel mit 2× isoliert anfordern";
export type DemoControlInput = {
  expected_revision: number; action: "start" | "pause"; basket_limit: number; assets: string[];
};
export type DemoControl = {
  schema: "investalo-demo-h1-control/1"; tenant_id: string; account_id: string;
  revision: number; basket_limit: number; assets: string[];
  status: "not_started" | "start_requested" | "paused" | "authorization_changed";
  requested_at: string | null; worker_state: "not_installed" | "waiting" | "running" | "paused" | "blocked" | "offline";
  execution_enabled: boolean; worker_detail?: string; worker_seen_at?: string | null;
};
const fail = () => new Error("DEMO_CONTROL_UNCONFIRMED");
export function controlSettings(limit: unknown, assets: unknown) {
  if (!Number.isSafeInteger(limit) || (limit as number) < 3 || (limit as number) > 7 ||
    !Array.isArray(assets) || !assets.length || assets.length > SYMBOLS.length ||
    assets.some(v => typeof v !== "string" || !SYMBOLS.includes(v as typeof SYMBOLS[number])) ||
    new Set(assets).size !== assets.length) throw fail();
  return { basket_limit: limit as number, assets: SYMBOLS.filter(v => assets.includes(v)) as string[] };
}
export function parseControlInput(value: unknown): DemoControlInput {
  const v = exactObject(value, ["expected_revision", "action", "basket_limit", "assets", "confirmation"]);
  if (!Number.isSafeInteger(v.expected_revision) || (v.expected_revision as number) < 0 ||
    (v.expected_revision as number) >= Number.MAX_SAFE_INTEGER ||
    !["start", "pause"].includes(v.action as string) ||
    v.confirmation !== (v.action === "start" ? DEMO_START_CONFIRMATION : "pause")) throw fail();
  return { expected_revision: v.expected_revision as number, action: v.action as "start" | "pause",
    ...controlSettings(v.basket_limit, v.assets) };
}
export function parseDemoControl(value: unknown, tenant: string, account: string): DemoControl {
  const keys = ["schema", "tenant_id", "account_id", "revision", "basket_limit",
    "assets", "status", "requested_at", "worker_state", "execution_enabled"];
  const v = exactObject(value, typeof value === "object" && value && "worker_detail" in value ?
    [...keys, "worker_detail", "worker_seen_at"] : keys);
  if (v.schema !== "investalo-demo-h1-control/1" || canonicalUuid(v.tenant_id) !== tenant ||
    canonicalUuid(v.account_id) !== account || !Number.isSafeInteger(v.revision) || (v.revision as number) < 0 ||
    !["not_started", "start_requested", "paused", "authorization_changed"].includes(v.status as string) ||
    !["not_installed", "waiting", "running", "paused", "blocked", "offline"].includes(v.worker_state as string) ||
    typeof v.execution_enabled !== "boolean" ||
    ["not_installed", "paused", "blocked", "offline"].includes(v.worker_state as string) && v.execution_enabled !== false ||
    "worker_detail" in v && (typeof v.worker_detail !== "string" || v.worker_detail.length > 128 ||
      v.worker_seen_at !== null && (typeof v.worker_seen_at !== "string" || !Number.isFinite(Date.parse(v.worker_seen_at)))) ||
    (v.revision === 0 ? v.requested_at !== null || v.status !== "not_started" :
      typeof v.requested_at !== "string" || !Number.isFinite(Date.parse(v.requested_at)) ||
      new Date(v.requested_at).toISOString() !== v.requested_at || v.status === "not_started")) throw fail();
  const settings = controlSettings(v.basket_limit, v.assets);
  if (JSON.stringify(settings.assets) !== JSON.stringify(v.assets)) throw fail();
  return v as DemoControl;
}
