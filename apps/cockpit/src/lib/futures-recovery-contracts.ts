/** Own-current paper status only; historical research results cannot pass. */
export const recoveryReasons = {
  manual_consent_required: "Manuelle Bestätigung fehlt.",
  reconciliation_stale: "Position und Aufträge müssen erneut abgeglichen werden.",
  position_not_flat: "Die Position ist noch nicht vollständig geschlossen.",
  orders_unresolved: "Der Auftragsstatus ist noch ungeklärt.",
  open_orders: "Es bestehen noch offene Aufträge.",
  liquidation_unbooked: "Die Liquidation ist noch nicht vollständig verbucht.",
  account_blocked: "Eine weitere Kontosperre besteht.",
  new_basket_budget_missing: "Das vollständige Kapital für einen neuen Basket fehlt.",
  runtime_unavailable: "Der Futures-Paperlauf ist noch nicht angeschlossen.",
} as const;
export type RecoveryReason = keyof typeof recoveryReasons;
export type RecoveryAsset = {
  account_id: string; symbol: string; cycle: number; revision: number; state_digest: string;
  liquidated_at: string; net_loss: string; leverage: string;
  available_capital: string; required_capital: string; reasons: RecoveryReason[]; allowed: boolean;
};
export type RecoveryStatus = {
  schema_version: "futures-recovery-status/1"; tenant_id: string; mode: "paper";
  live_enabled: false; observed_at: string; assets: RecoveryAsset[];
};
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const sha = /^[0-9a-f]{64}$/;
function object(x: unknown): x is Record<string, unknown> { return !!x && typeof x === "object" && !Array.isArray(x); }
function integer(x: unknown): x is number { return typeof x === "number" && Number.isSafeInteger(x) && x >= 0; }
function time(x: unknown): x is string { return typeof x === "string" && x.length <= 40 && /^\d{4}-\d\d-\d\dT.*(?:Z|\+00:00)$/.test(x) && Number.isFinite(Date.parse(x)); }
function amount(x: unknown): x is string {
  return typeof x === "string" && /^(?:0|[1-9]\d{0,20})(?:\.\d{1,24})?$/.test(x) && Number.isFinite(Number(x));
}
function reject(): never { throw new Error("FUTURES_RECOVERY_REJECTED"); }

export function parseRecoveryStatus(x: unknown, tenantId: string): RecoveryStatus {
  if (!object(x) || x.schema_version !== "futures-recovery-status/1" || x.tenant_id !== tenantId ||
      !uuid.test(tenantId) || x.mode !== "paper" || x.live_enabled !== false || !time(x.observed_at) ||
      !Array.isArray(x.assets) || x.assets.length > 140) return reject();
  const keys = new Set<string>();
  const assets = x.assets.map((a: unknown): RecoveryAsset => {
    if (!object(a) || typeof a.account_id !== "string" || !uuid.test(a.account_id) ||
        typeof a.symbol !== "string" || !/^[A-Z0-9]{2,20}USDT$/.test(a.symbol) ||
        !integer(a.cycle) || a.cycle < 1 || !integer(a.revision) ||
        typeof a.state_digest !== "string" || !sha.test(a.state_digest) ||
        !time(a.liquidated_at) || Date.parse(a.liquidated_at) > Date.parse(x.observed_at as string) ||
        !amount(a.net_loss) || !amount(a.available_capital) || !amount(a.required_capital) || Number(a.required_capital) <= 0 ||
        typeof a.leverage !== "string" || !/^(?:[2-9]|10)$/.test(a.leverage) ||
        !Array.isArray(a.reasons) || a.reasons.length > 9 || typeof a.allowed !== "boolean" ||
        a.reasons.some((r: unknown) => typeof r !== "string" || !Object.hasOwn(recoveryReasons, r)) ||
        new Set(a.reasons).size !== a.reasons.length ||
        a.allowed !== (a.reasons.length === 0) ||
        a.allowed && (a.reasons.length || Number(a.available_capital) < Number(a.required_capital)))
      return reject();
    const key = `${a.account_id}:${a.symbol}`;
    if (keys.has(key)) return reject();
    keys.add(key);
    return { account_id: a.account_id, symbol: a.symbol, cycle: a.cycle, revision: a.revision,
      state_digest: a.state_digest, liquidated_at: a.liquidated_at, net_loss: a.net_loss,
      leverage: a.leverage, available_capital: a.available_capital, required_capital: a.required_capital,
      reasons: a.reasons as RecoveryReason[], allowed: a.allowed };
  });
  return { schema_version: "futures-recovery-status/1", tenant_id: tenantId, mode: "paper",
    live_enabled: false, observed_at: x.observed_at, assets };
}

export function parseRecoveryRequest(x: unknown) {
  if (!object(x) || Object.keys(x).sort().join(",") !==
      "account_id,consent,cycle,event_id,revision,state_digest,symbol" ||
      typeof x.account_id !== "string" || !uuid.test(x.account_id) ||
      typeof x.symbol !== "string" || !/^[A-Z0-9]{2,20}USDT$/.test(x.symbol) ||
      !integer(x.cycle) || x.cycle < 1 || !integer(x.revision) ||
      typeof x.state_digest !== "string" || !sha.test(x.state_digest) ||
      typeof x.event_id !== "string" || !uuid.test(x.event_id) || x.consent !== true) return reject();
  return { account_id: x.account_id, symbol: x.symbol, cycle: x.cycle, revision: x.revision,
    state_digest: x.state_digest, event_id: x.event_id, consent: true };
}
