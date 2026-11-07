/** Safe metadata only. These contracts contain no broker UID or ciphertext. */
export type CredentialAction = "register" | "replace" | "revoke";
export type ActionTarget =
  | Readonly<{ action: "register"; platform_account_id: string; connection_id: string }>
  | Readonly<{ action: "replace" | "revoke"; platform_account_id: string; connection_id: string;
      expected_revision: number; expected_storage: number }>;
export type CredentialActionMetadata = Readonly<{
  tenant_id: string; auth_epoch: number;
  account: Readonly<{ id: string; name: string; broker: "bitget"; mode: "read_only";
    status: "disconnected" | "ready" | "paused" }>;
  connection: Readonly<{ connection_id: string; credential_revision: number; storage_version: number;
    status: "active" | "revoked" }> | null;
}>;

function rejected(): Error { return new Error("CREDENTIAL_ACTION_REJECTED"); }
export function canonicalUuid(value: unknown): string {
  // Match Python str(UUID(value)), without inventing a UUID-version constraint.
  if (typeof value !== "string" || !/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(value)) throw rejected();
  return value;
}
function object(value: unknown, fields: readonly string[]): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value) ||
    (Object.getPrototypeOf(value) !== Object.prototype && Object.getPrototypeOf(value) !== null)) throw rejected();
  const keys = Reflect.ownKeys(value);
  if (keys.length !== fields.length || keys.some(key => typeof key !== "string" || !fields.includes(key)) ||
    fields.some(key => !Object.hasOwn(value, key))) throw rejected();
  // JSON metadata has data properties, never user-supplied getters.
  if (keys.some(key => !Object.hasOwn(Object.getOwnPropertyDescriptor(value, key)!, "value"))) throw rejected();
  return value as Record<string, unknown>;
}
export function credentialInteger(value: unknown, minimum = 0): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < minimum) throw rejected();
  return value;
}
export function credentialAction(value: unknown): CredentialAction {
  if (value !== "register" && value !== "replace" && value !== "revoke") throw rejected();
  return value;
}
export function parseAccountRequest(value: unknown): Readonly<{ platform_account_id: string }> {
  const item = object(value, ["platform_account_id"]);
  return Object.freeze({ platform_account_id: canonicalUuid(item.platform_account_id) });
}
export function parseActionTarget(value: unknown): ActionTarget {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw rejected();
  const descriptor = Object.getOwnPropertyDescriptor(value, "action");
  if (!descriptor || !Object.hasOwn(descriptor, "value")) throw rejected();
  const action = credentialAction(descriptor.value);
  const fields = ["action", "platform_account_id", "connection_id"];
  const item = object(value, action === "register" ? fields : [...fields, "expected_revision", "expected_storage"]);
  const base = { platform_account_id: canonicalUuid(item.platform_account_id), connection_id: canonicalUuid(item.connection_id) };
  if (action === "register") return Object.freeze({ action, ...base });
  const expected_revision = credentialInteger(item.expected_revision, 1);
  const expected_storage = credentialInteger(item.expected_storage, 1);
  // The resulting versions must also remain exactly representable in JS.
  if (expected_storage === Number.MAX_SAFE_INTEGER ||
    (action === "replace" && expected_revision === Number.MAX_SAFE_INTEGER)) throw rejected();
  return Object.freeze({ action, ...base, expected_revision, expected_storage });
}
export function parseCredentialActionMetadata(
  value: unknown, expected: { tenantId: string; accountId: string; authEpoch: number },
): CredentialActionMetadata {
  const tenantId = canonicalUuid(expected.tenantId), accountId = canonicalUuid(expected.accountId);
  const authEpoch = credentialInteger(expected.authEpoch);
  const item = object(value, ["tenant_id", "auth_epoch", "account", "connection"]);
  if (canonicalUuid(item.tenant_id) !== tenantId || credentialInteger(item.auth_epoch) !== authEpoch) throw rejected();
  const account = object(item.account, ["id", "name", "broker", "mode", "status"]);
  if (canonicalUuid(account.id) !== accountId || account.broker !== "bitget" || account.mode !== "read_only" ||
    !["disconnected", "ready", "paused"].includes(account.status as string) ||
    typeof account.name !== "string" || !account.name || account.name.length > 200 ||
    !account.name.isWellFormed() || /[\u0000-\u001f\u007f]/.test(account.name)) throw rejected();
  let connection: CredentialActionMetadata["connection"] = null;
  if (item.connection !== null) {
    const current = object(item.connection, ["connection_id", "credential_revision", "storage_version", "status"]);
    if (current.status !== "active" && current.status !== "revoked") throw rejected();
    connection = Object.freeze({
      connection_id: canonicalUuid(current.connection_id),
      credential_revision: credentialInteger(current.credential_revision, 1),
      storage_version: credentialInteger(current.storage_version, 1), status: current.status,
    });
  }
  return Object.freeze({ tenant_id: tenantId, auth_epoch: authEpoch, account: Object.freeze({
    id: accountId, name: account.name, broker: "bitget", mode: "read_only",
    status: account.status as CredentialActionMetadata["account"]["status"],
  }), connection });
}
export function allowedCredentialActions(metadata: CredentialActionMetadata): readonly CredentialAction[] {
  // Revalidate typed input at the runtime boundary; TS types are not authority.
  const current = parseCredentialActionMetadata(metadata, {
    tenantId: metadata.tenant_id, accountId: metadata.account.id, authEpoch: metadata.auth_epoch,
  });
  if (current.connection === null) return Object.freeze(current.account.status === "paused" ? [] : ["register"]);
  if (current.connection.status !== "active") return Object.freeze([]);
  const result: CredentialAction[] = [];
  if (current.account.status !== "paused" && current.connection.credential_revision < Number.MAX_SAFE_INTEGER &&
    current.connection.storage_version < Number.MAX_SAFE_INTEGER) result.push("replace");
  if (current.connection.storage_version < Number.MAX_SAFE_INTEGER) result.push("revoke");
  return Object.freeze(result);
}
export function deriveActionTarget(
  metadata: CredentialActionMetadata, action: CredentialAction, options: { newConnectionId?: string } = {},
): ActionTarget {
  credentialAction(action);
  if (!allowedCredentialActions(metadata).includes(action)) throw rejected();
  if (action === "register") {
    return parseActionTarget({ action, platform_account_id: metadata.account.id,
      connection_id: canonicalUuid(options.newConnectionId) });
  }
  if (options.newConnectionId !== undefined || !metadata.connection) throw rejected();
  return parseActionTarget({ action, platform_account_id: metadata.account.id,
    connection_id: metadata.connection.connection_id, expected_revision: metadata.connection.credential_revision,
    expected_storage: metadata.connection.storage_version });
}
