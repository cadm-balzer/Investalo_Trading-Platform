/** Own015 Demo metadata and targets. Normal metadata is never relabelled. */
import { canonicalUuid, credentialInteger, parseActionTarget } from "./credential-action-contracts.ts";
import { exactObject } from "./passkey-enrollment-state.ts";
export { canonicalUuid, credentialInteger };

export const DEMO_CREDENTIAL_ACTION_TARGETS = Object.freeze({
  register: "/v1/credentials/bitget-demo/register",
  revoke: "/v1/credentials/bitget-demo/revoke",
});
export type DemoCredentialAction = "register" | "revoke";
export type DemoActionTarget =
  | Readonly<{ action: "register"; platform_account_id: string; connection_id: string }>
  | Readonly<{ action: "revoke"; platform_account_id: string; connection_id: string;
      expected_revision: 1; expected_storage: number }>;
export type DemoCredentialActionMetadata = Readonly<{
  tenant_id: string; auth_epoch: number; purpose: "demo_read_only";
  profile: "bitget-classic-demo-read-secret/1"; environment: "demo";
  account: Readonly<{ id: string; name: string; broker: "bitget"; mode: "bitget_demo";
    currency: "USDT"; status: "disconnected" | "ready" | "paused" }>;
  connection: Readonly<{ connection_id: string; credential_revision: 1; storage_version: number;
    status: "active" | "revoked" }> | null;
}>;
const rejected = () => new Error("DEMO_CREDENTIAL_ACTION_REJECTED");

export function parseDemoActionTarget(value: unknown): DemoActionTarget {
  const target = parseActionTarget(value);
  if (target.action === "register") return target;
  if (target.action !== "revoke" || target.expected_revision !== 1) throw rejected();
  return Object.freeze({ action: "revoke", platform_account_id: target.platform_account_id,
    connection_id: target.connection_id, expected_revision: 1, expected_storage: target.expected_storage });
}
export function parseDemoCredentialActionMetadata(value: unknown,
  expected: { tenantId: string; accountId: string; authEpoch: number }): DemoCredentialActionMetadata {
  const tenant = canonicalUuid(expected.tenantId), accountId = canonicalUuid(expected.accountId);
  const epoch = credentialInteger(expected.authEpoch);
  const item = exactObject(value, ["tenant_id", "auth_epoch", "purpose", "profile", "environment", "account", "connection"]);
  if (item.tenant_id !== tenant || credentialInteger(item.auth_epoch) !== epoch ||
    item.purpose !== "demo_read_only" || item.profile !== "bitget-classic-demo-read-secret/1" ||
    item.environment !== "demo") throw rejected();
  const account = exactObject(item.account, ["id", "name", "broker", "mode", "currency", "status"]);
  if (account.id !== accountId || account.broker !== "bitget" || account.mode !== "bitget_demo" ||
    account.currency !== "USDT" || !["disconnected", "ready", "paused"].includes(account.status as string) ||
    typeof account.name !== "string" || !account.name || !account.name.isWellFormed() ||
    Array.from(account.name).length > 120 || /[\u0000-\u001f\u007f]/.test(account.name)) throw rejected();
  let connection: DemoCredentialActionMetadata["connection"] = null;
  if (item.connection !== null) {
    const current = exactObject(item.connection, ["connection_id", "credential_revision", "storage_version", "status"]);
    if (credentialInteger(current.credential_revision, 1) !== 1 ||
      (current.status !== "active" && current.status !== "revoked")) throw rejected();
    connection = Object.freeze({ connection_id: canonicalUuid(current.connection_id),
      credential_revision: 1, storage_version: credentialInteger(current.storage_version, 1), status: current.status });
  }
  return Object.freeze({ tenant_id: tenant, auth_epoch: epoch, purpose: "demo_read_only",
    profile: "bitget-classic-demo-read-secret/1", environment: "demo",
    account: Object.freeze({ id: accountId, name: account.name, broker: "bitget", mode: "bitget_demo",
      currency: "USDT", status: account.status as DemoCredentialActionMetadata["account"]["status"] }), connection });
}
export function deriveDemoActionTarget(metadata: DemoCredentialActionMetadata, action: DemoCredentialAction,
  options: { newConnectionId?: string } = {}): DemoActionTarget {
  const current = parseDemoCredentialActionMetadata(metadata, { tenantId: metadata.tenant_id,
    accountId: metadata.account.id, authEpoch: metadata.auth_epoch });
  if (action === "register") {
    if (current.connection !== null || current.account.status !== "ready") throw rejected();
    return parseDemoActionTarget({ action, platform_account_id: current.account.id,
      connection_id: canonicalUuid(options.newConnectionId) });
  }
  if (action !== "revoke" || options.newConnectionId !== undefined || !current.connection ||
    current.connection.status !== "active") throw rejected();
  return parseDemoActionTarget({ action, platform_account_id: current.account.id,
    connection_id: current.connection.connection_id, expected_revision: 1,
    expected_storage: current.connection.storage_version });
}
