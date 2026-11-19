/** Exact browser-safe credential projections; no private server imports. */
import {
  canonicalUuid, demoTradingCredentialAction, credentialInteger, parseDemoTradingActionTarget,
  type DemoTradingActionTarget, type DemoTradingCredentialAction,
} from "./demo-trading-credential-action-contracts.ts";
import { browserBytes } from "./passkey-browser-proof.ts";

export type DemoTradingProofPreview = Readonly<{
  target: DemoTradingActionTarget; accountName: string; expiresAt: number; execution_enabled: false;
}>;

export type BrowserDemoTradingCredentialStart = Readonly<{
  flow_token: string; options: PublicKeyCredentialRequestOptions; preview: DemoTradingProofPreview;
}>;
export type BrowserDemoTradingCredentialGrant = Readonly<{
  flow_token: string; grant: Readonly<{ target: DemoTradingActionTarget; accountName: string;
    checkedAt: number; expiresAt: number; execution_enabled: false }>;
}>;
export type BrowserDemoTradingCredentialResult = Readonly<{
  connection_id: string; credential_revision: 1; storage_version: number; status: "active" | "revoked";
}>;
const rejected = () => new Error("DEMO_TRADING_PASSKEY_CREDENTIAL_BROWSER_REJECTED");
function record(value: unknown, fields: readonly string[]): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value) ||
    ![Object.prototype, null].includes(Object.getPrototypeOf(value))) throw rejected();
  const keys = Reflect.ownKeys(value);
  if (keys.length !== fields.length || keys.some(key => typeof key !== "string" || !fields.includes(key) ||
    !Object.hasOwn(Object.getOwnPropertyDescriptor(value, key)!, "value"))) throw rejected();
  return value as Record<string, unknown>;
}
function token(value: unknown): string {
  browserBytes(value, 32, 32);
  return value as string;
}
function name(value: unknown): string {
  if (typeof value !== "string" || !value || value.length > 200 || !value.isWellFormed() ||
    /[\u0000-\u001f\u007f]/.test(value)) throw rejected();
  return value;
}
function expiry(value: unknown, now: number): number {
  const expires = credentialInteger(value, 1);
  credentialInteger(now, 1);
  if (expires <= now || expires > now + 120) throw rejected();
  return expires;
}
export function parseBrowserDemoTradingCredentialStart(
  value: unknown, accountId: string, action: DemoTradingCredentialAction, rpId: string,
  now = Math.floor(Date.now() / 1000),
): BrowserDemoTradingCredentialStart {
  canonicalUuid(accountId); demoTradingCredentialAction(action);
  const item = record(value, ["flow_token", "options", "preview"]);
  const preview = record(item.preview, ["target", "accountName", "expiresAt", "execution_enabled"]);
  const target = parseDemoTradingActionTarget(preview.target);
  if (target.platform_account_id !== accountId || target.action !== action ||
    preview.execution_enabled !== false) throw rejected();
  const options = record(item.options, ["challenge", "rpId", "timeout", "allowCredentials", "userVerification"]);
  if (options.rpId !== rpId || !rpId || options.userVerification !== "required" ||
    !Array.isArray(options.allowCredentials) || options.allowCredentials.length !== 1) throw rejected();
  const timeout = credentialInteger(options.timeout, 1);
  if (timeout > 120_000) throw rejected();
  const credential = record(options.allowCredentials[0], ["id", "type"]);
  if (credential.type !== "public-key") throw rejected();
  return Object.freeze({
    flow_token: token(item.flow_token),
    preview: Object.freeze({ target, accountName: name(preview.accountName),
      expiresAt: expiry(preview.expiresAt, now), execution_enabled: false }),
    options: { challenge: browserBytes(options.challenge, 32, 32), rpId, timeout,
      userVerification: "required" as const,
      allowCredentials: [{ type: "public-key" as const, id: browserBytes(credential.id, 1, 1023) }] },
  });
}
export function parseBrowserDemoTradingCredentialGrant(
  value: unknown, start: BrowserDemoTradingCredentialStart, now = Math.floor(Date.now() / 1000),
): BrowserDemoTradingCredentialGrant {
  const item = record(value, ["flow_token", "grant"]);
  const grant = record(item.grant, ["target", "accountName", "checkedAt", "expiresAt", "execution_enabled"]);
  const target = parseDemoTradingActionTarget(grant.target), checkedAt = credentialInteger(grant.checkedAt, 1);
  const expiresAt = expiry(grant.expiresAt, now), nextToken = token(item.flow_token);
  if (nextToken === start.flow_token || JSON.stringify(target) !== JSON.stringify(start.preview.target) ||
    grant.accountName !== start.preview.accountName || grant.execution_enabled !== false ||
    checkedAt > now || checkedAt < start.preview.expiresAt - 120 || checkedAt >= start.preview.expiresAt ||
    expiresAt <= checkedAt || expiresAt > checkedAt + 120 || expiresAt > start.preview.expiresAt) throw rejected();
  return Object.freeze({ flow_token: nextToken,
    grant: Object.freeze({ target, accountName: name(grant.accountName), checkedAt, expiresAt, execution_enabled: false }) });
}
export function parseBrowserDemoTradingCredentialResult(value: unknown, target: DemoTradingActionTarget): BrowserDemoTradingCredentialResult {
  const expected = parseDemoTradingActionTarget(target);
  const item = record(value, ["connection_id", "credential_revision", "storage_version", "status"]);
  const revision = 1;
  const storage = expected.action === "register" ? 1 : expected.expected_storage + 1;
  const status = expected.action === "revoke" ? "revoked" : "active";
  if (canonicalUuid(item.connection_id) !== expected.connection_id ||
    credentialInteger(item.credential_revision, 1) !== revision ||
    credentialInteger(item.storage_version, 1) !== storage || item.status !== status) throw rejected();
  return Object.freeze({ connection_id: expected.connection_id, credential_revision: revision, storage_version: storage, status });
}
