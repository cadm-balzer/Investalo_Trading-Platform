export type BasketSetting = {
  account_id: string; account_name: string; revision: number; basket_limit: number;
  saved: boolean; can_edit: boolean; leverage: "2"; runtime_ready: false;
  recommendation: null; recommendation_reason: "futures_runtime_missing";
};
export type BasketSettings = {
  schema_version: "futures-paper-settings/1"; tenant_id: string;
  mode: "paper"; live_enabled: false; accounts: BasketSetting[];
};
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("SETTINGS_REJECTED");
  return value as Record<string, unknown>;
}
function integer(value: unknown, min: number, max: number): number {
  if (!Number.isSafeInteger(value) || (value as number) < min || (value as number) > max)
    throw new Error("SETTINGS_REJECTED");
  return value as number;
}
export function parseBasketSettings(value: unknown, tenantId: string): BasketSettings {
  const x = object(value);
  if (x.schema_version !== "futures-paper-settings/1" || !uuid.test(tenantId) ||
    x.tenant_id !== tenantId || x.mode !== "paper" || x.live_enabled !== false ||
    !Array.isArray(x.accounts) || x.accounts.length > 20) throw new Error("SETTINGS_REJECTED");
  const accounts = x.accounts.map(value => {
    const a = object(value);
    if (typeof a.account_id !== "string" || !uuid.test(a.account_id) ||
      typeof a.account_name !== "string" || a.account_name.length < 1 || a.account_name.length > 200 ||
      typeof a.saved !== "boolean" || typeof a.can_edit !== "boolean" ||
      a.leverage !== "2" || a.runtime_ready !== false || a.recommendation !== null ||
      a.recommendation_reason !== "futures_runtime_missing") throw new Error("SETTINGS_REJECTED");
    const revision = integer(a.revision, 0, Number.MAX_SAFE_INTEGER);
    if (a.saved !== (revision > 0)) throw new Error("SETTINGS_REJECTED");
    return { account_id: a.account_id, account_name: a.account_name, revision,
      basket_limit: integer(a.basket_limit, 3, 7), saved: a.saved, can_edit: a.can_edit,
      leverage: "2", runtime_ready: false, recommendation: null,
      recommendation_reason: "futures_runtime_missing" } satisfies BasketSetting;
  });
  if (new Set(accounts.map(a => a.account_id)).size !== accounts.length) throw new Error("SETTINGS_REJECTED");
  return { schema_version: "futures-paper-settings/1", tenant_id: tenantId, mode: "paper", live_enabled: false, accounts };
}
export function parseBasketSettingsRequest(value: unknown) {
  const x = object(value);
  if (Object.keys(x).sort().join(",") !== "account_id,basket_limit,expected_revision" ||
      typeof x.account_id !== "string" || !uuid.test(x.account_id)) throw new Error("SETTINGS_REJECTED");
  return { account_id: x.account_id, expected_revision: integer(x.expected_revision, 0, Number.MAX_SAFE_INTEGER-1),
    basket_limit: integer(x.basket_limit, 3, 7) };
}
