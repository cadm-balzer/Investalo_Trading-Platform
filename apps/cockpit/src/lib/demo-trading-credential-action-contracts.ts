/** Own018/019 Trading metadata and targets. Normal metadata is never relabelled. */
import { canonicalUuid, credentialInteger, parseActionTarget } from "./credential-action-contracts.ts";
export { canonicalUuid, credentialInteger };

export const DEMO_TRADING_CREDENTIAL_ACTION_TARGETS = Object.freeze({
  register: "/v1/credentials/bitget-demo-trading/register",
  revoke: "/v1/credentials/bitget-demo-trading/revoke",
});
export type DemoTradingCredentialAction = "register" | "revoke";
export type DemoTradingActionTarget =
  | Readonly<{ action: "register"; platform_account_id: string; connection_id: string }>
  | Readonly<{ action: "revoke"; platform_account_id: string; connection_id: string;
      expected_revision: 1; expected_storage: number }>;
export type DemoTradingCredentialActionMetadata = Readonly<{
  tenant_id: string; auth_epoch: number; purpose: "demo_futures_spot_trading";
  profile: "bitget-classic-demo-trading-secret/1"; environment: "demo";
  account: Readonly<{ id: string; name: string; broker: "bitget"; mode: "bitget_demo";
    currency: "USDT"; status: "disconnected" | "ready" | "paused" }>;
  connection: Readonly<{ connection_id: string; credential_revision: 1; storage_version: number;
    status: "active" | "revoked" }> | null;
  key_authorities: readonly string[] | null;
}>;
const rejected = () => new Error("DEMO_TRADING_CREDENTIAL_ACTION_REJECTED");
const requiredRights = ["coow", "cpow", "stow"] as const;
const allowedRights = new Set<string>([...requiredRights,
  "stor", "coor", "cpor", "smor", "ttor", "wtor", "taxr", "chor", "p2pr"]);
function authorities(value: unknown, connection: DemoTradingCredentialActionMetadata["connection"]): readonly string[] | null {
  if (connection === null) {
    if (value !== null) throw rejected();
    return null;
  }
  if (!Array.isArray(value) || Object.getPrototypeOf(value) !== Array.prototype ||
    value.length < 3 || value.length > allowedRights.size ||
    Reflect.ownKeys(value).length !== value.length + 1) throw rejected();
  const result: string[] = [];
  for (let i = 0; i < value.length; i++) {
    const descriptor = Object.getOwnPropertyDescriptor(value, String(i));
    if (!descriptor || !Object.hasOwn(descriptor, "value") ||
      typeof descriptor.value !== "string" || !allowedRights.has(descriptor.value)) throw rejected();
    result.push(descriptor.value);
  }
  const sorted = [...result].sort();
  if (new Set(result).size !== result.length || requiredRights.some(right => !result.includes(right)) ||
    result.some((right, i) => right !== sorted[i])) throw rejected();
  return Object.freeze(result);
}
// Browser-safe exact projection; no Node crypto/session registry dependency.
function exactObject(value: unknown, fields: readonly string[]): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value) ||
    ![Object.prototype, null].includes(Object.getPrototypeOf(value))) throw rejected();
  const keys = Reflect.ownKeys(value);
  if (keys.length !== fields.length || fields.some(field => !Object.hasOwn(value, field)) ||
    keys.some(key => typeof key !== "string" || !fields.includes(key) ||
      !Object.hasOwn(Object.getOwnPropertyDescriptor(value, key)!, "value"))) throw rejected();
  return value as Record<string, unknown>;
}
export function demoTradingCredentialAction(value: unknown): DemoTradingCredentialAction {
  if (value !== "register" && value !== "revoke") throw rejected();
  return value;
}
export function allowedDemoTradingCredentialActions(metadata: DemoTradingCredentialActionMetadata): readonly DemoTradingCredentialAction[] {
  const current = parseDemoTradingCredentialActionMetadata(metadata, { tenantId: metadata.tenant_id,
    accountId: metadata.account.id, authEpoch: metadata.auth_epoch });
  if (current.connection === null) return Object.freeze(current.account.status === "ready" ? ["register"] : []);
  return Object.freeze(current.connection.status === "active" &&
    current.connection.storage_version < Number.MAX_SAFE_INTEGER ? ["revoke"] : []);
}

export function parseDemoTradingActionTarget(value: unknown): DemoTradingActionTarget {
  const target = parseActionTarget(value);
  if (target.action === "register") return target;
  if (target.action !== "revoke" || target.expected_revision !== 1) throw rejected();
  return Object.freeze({ action: "revoke", platform_account_id: target.platform_account_id,
    connection_id: target.connection_id, expected_revision: 1, expected_storage: target.expected_storage });
}
export function parseDemoTradingCredentialActionMetadata(value: unknown,
  expected: { tenantId: string; accountId: string; authEpoch: number }): DemoTradingCredentialActionMetadata {
  const tenant = canonicalUuid(expected.tenantId), accountId = canonicalUuid(expected.accountId);
  const epoch = credentialInteger(expected.authEpoch);
  const item = exactObject(value, ["tenant_id", "auth_epoch", "purpose", "profile", "environment", "account", "connection", "key_authorities"]);
  if (item.tenant_id !== tenant || credentialInteger(item.auth_epoch) !== epoch ||
    item.purpose !== "demo_futures_spot_trading" || item.profile !== "bitget-classic-demo-trading-secret/1" ||
    item.environment !== "demo") throw rejected();
  const account = exactObject(item.account, ["id", "name", "broker", "mode", "currency", "status"]);
  if (account.id !== accountId || account.broker !== "bitget" || account.mode !== "bitget_demo" ||
    account.currency !== "USDT" || !["disconnected", "ready", "paused"].includes(account.status as string) ||
    typeof account.name !== "string" || !account.name || !account.name.isWellFormed() ||
    Array.from(account.name).length > 120 || /[\u0000-\u001f\u007f]/.test(account.name)) throw rejected();
  let connection: DemoTradingCredentialActionMetadata["connection"] = null;
  if (item.connection !== null) {
    const current = exactObject(item.connection, ["connection_id", "credential_revision", "storage_version", "status"]);
    if (credentialInteger(current.credential_revision, 1) !== 1 ||
      (current.status !== "active" && current.status !== "revoked")) throw rejected();
    connection = Object.freeze({ connection_id: canonicalUuid(current.connection_id),
      credential_revision: 1, storage_version: credentialInteger(current.storage_version, 1), status: current.status });
  }
  return Object.freeze({ tenant_id: tenant, auth_epoch: epoch, purpose: "demo_futures_spot_trading",
    profile: "bitget-classic-demo-trading-secret/1", environment: "demo",
    account: Object.freeze({ id: accountId, name: account.name, broker: "bitget", mode: "bitget_demo",
      currency: "USDT", status: account.status as DemoTradingCredentialActionMetadata["account"]["status"] }), connection,
    key_authorities: authorities(item.key_authorities, connection) });
}
export function deriveDemoTradingActionTarget(metadata: DemoTradingCredentialActionMetadata, action: DemoTradingCredentialAction,
  options: { newConnectionId?: string } = {}): DemoTradingActionTarget {
  const current = parseDemoTradingCredentialActionMetadata(metadata, { tenantId: metadata.tenant_id,
    accountId: metadata.account.id, authEpoch: metadata.auth_epoch });
  if (action === "register") {
    if (current.connection !== null || current.account.status !== "ready") throw rejected();
    return parseDemoTradingActionTarget({ action, platform_account_id: current.account.id,
      connection_id: canonicalUuid(options.newConnectionId) });
  }
  if (action !== "revoke" || options.newConnectionId !== undefined || !current.connection ||
    current.connection.status !== "active") throw rejected();
  return parseDemoTradingActionTarget({ action, platform_account_id: current.account.id,
    connection_id: current.connection.connection_id, expected_revision: 1,
    expected_storage: current.connection.storage_version });
}
