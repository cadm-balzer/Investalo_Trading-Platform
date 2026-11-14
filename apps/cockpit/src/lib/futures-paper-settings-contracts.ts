export const capacityReasons = {
  futures_runtime_missing: "Paperstand noch nicht angeschlossen",
  capacity_unavailable: "Kapitalstand derzeit nicht verfügbar",
  instrument_data_unavailable: "Aktuelle Instrumentdaten fehlen",
  stale_instrument_data: "Instrumentdaten sind veraltet",
  stale_futures_cash: "Paperkapital oder Quotes sind veraltet",
  account_unavailable: "Paperkonto ist pausiert oder nicht bereit",
  paper_runtime_blocked: "Paperbetrieb benötigt einen Abgleich",
  paper_settings_pending: "Worker hat die gespeicherte Grenze noch nicht übernommen",
  reserved_cash_shortfall: "Verfügbare Mittel decken die bestehenden Reserven nicht",
  candidate_pool_insufficient: "Weniger als drei geeignete Handelsassets verfügbar",
  range_below_market_minimum: "Basketbudget unterschreitet die aktuellen Mindestorders",
  full_ranges_not_funded: "Weniger als drei vollständige Ranges finanzierbar",
  await_basket_closure: "Finanzierte Plätze sind belegt; neue Baskets warten auf Abschlüsse",
  current_full_ranges: "Vollständige Ranges mit aktuellem Paperkapital finanzierbar",
} as const;
export type PaperCapacity = {
  observed_at: string; instrument_at: string; unposted_cash: string; reserved_cash: string;
  free_cash: string; range_budget: string; minimum_range: string;
  active_baskets: number; funded_capacity: number; eligible_assets: number; additional_baskets: number;
};
export type BasketSetting = {
  account_id: string; account_name: string; revision: number; basket_limit: number;
  saved: boolean; can_edit: boolean; leverage: "2"; runtime_ready: boolean;
  recommendation: number | null; recommendation_reason: keyof typeof capacityReasons;
  capacity: PaperCapacity | null;
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
function amount(value: unknown): string {
  if (typeof value !== "string" || value.length > 64 ||
      !/^\d+(?:\.\d+)?(?:[eE][+-]?\d{1,3})?$/.test(value) ||
      !Number.isFinite(Number(value)) || Number(value) < 0) throw new Error("SETTINGS_REJECTED");
  return value;
}
function time(value: unknown): string {
  if (typeof value !== "string" || value.length > 40 ||
      !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)$/.test(value) ||
      !Number.isFinite(Date.parse(value))) throw new Error("SETTINGS_REJECTED");
  return value;
}
function capacity(value: unknown): PaperCapacity | null {
  if (value === null || value === undefined) return null; // Previous default-off response.
  const c = object(value);
  const result = {
    observed_at: time(c.observed_at), instrument_at: time(c.instrument_at),
    unposted_cash: amount(c.unposted_cash), reserved_cash: amount(c.reserved_cash),
    free_cash: amount(c.free_cash), range_budget: amount(c.range_budget), minimum_range: amount(c.minimum_range),
    active_baskets: integer(c.active_baskets, 0, 7), funded_capacity: integer(c.funded_capacity, 3, 7),
    eligible_assets: integer(c.eligible_assets, 0, 7), additional_baskets: integer(c.additional_baskets, 0, 7),
  };
  if (Number(result.range_budget) <= 0 || Number(result.minimum_range) <= 0 ||
      result.active_baskets > result.funded_capacity ||
      result.additional_baskets > result.funded_capacity) throw new Error("SETTINGS_REJECTED");
  return result;
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
      a.leverage !== "2" || typeof a.runtime_ready !== "boolean" ||
      typeof a.recommendation_reason !== "string" ||
      !Object.hasOwn(capacityReasons, a.recommendation_reason)) throw new Error("SETTINGS_REJECTED");
    const detail = capacity(a.capacity);
    const recommendation = a.recommendation === null ? null : integer(a.recommendation, 3, 7);
    const reason = a.recommendation_reason as keyof typeof capacityReasons;
    if (a.runtime_ready !== (recommendation !== null) ||
        (recommendation !== null && (!detail ||
          !["current_full_ranges", "await_basket_closure"].includes(reason) ||
          recommendation > Math.min(detail.funded_capacity, detail.eligible_assets, Number(a.basket_limit)))))
      throw new Error("SETTINGS_REJECTED");
    const revision = integer(a.revision, 0, Number.MAX_SAFE_INTEGER);
    if (a.saved !== (revision > 0)) throw new Error("SETTINGS_REJECTED");
    return { account_id: a.account_id, account_name: a.account_name, revision,
      basket_limit: integer(a.basket_limit, 3, 7), saved: a.saved, can_edit: a.can_edit,
      leverage: "2", runtime_ready: a.runtime_ready, recommendation,
      recommendation_reason: reason, capacity: detail } satisfies BasketSetting;
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
