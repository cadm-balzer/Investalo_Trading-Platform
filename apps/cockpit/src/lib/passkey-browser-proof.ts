/** Browser-safe wire projections. Never import server crypto or registry records. */
import {
  canonicalUuid, credentialAction, credentialInteger, parseActionTarget,
  type ActionTarget, type CredentialAction,
} from "./credential-action-contracts.ts";

export type ProofPreview = Readonly<{
  target: ActionTarget; accountName: string; expiresAt: number; execution_enabled: false;
}>;
export type BrowserProofStart = Readonly<{
  attempt_id: string; confirmation_token: string; preview: ProofPreview;
  options: PublicKeyCredentialRequestOptions;
}>;
export type BrowserProofGrant = Readonly<{
  grant_id: string; target: ActionTarget; accountName: string;
  checkedAt: number; expiresAt: number; confirmationToken: string; execution_enabled: false;
}>;
const rejected = () => new Error("PASSKEY_BROWSER_PROOF_REJECTED");
function record(value: unknown, required: readonly string[], optional: readonly string[] = []): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value) ||
    ![Object.prototype, null].includes(Object.getPrototypeOf(value))) throw rejected();
  const keys = Reflect.ownKeys(value);
  if (required.some(key => !Object.hasOwn(value, key)) ||
    keys.some(key => typeof key !== "string" || ![...required, ...optional].includes(key) ||
      !Object.hasOwn(Object.getOwnPropertyDescriptor(value, key)!, "value"))) throw rejected();
  return value as Record<string, unknown>;
}
export function browserEncoded(bytes: ArrayBuffer, minimum: number, maximum: number): string {
  if (!(bytes instanceof ArrayBuffer) || bytes.byteLength < minimum || bytes.byteLength > maximum) throw rejected();
  return btoa(String.fromCharCode(...new Uint8Array(bytes)))
    .replaceAll("+", "-").replaceAll("/", "_").replace(/=+$/, "");
}
export function browserBytes(value: unknown, minimum: number, maximum: number): ArrayBuffer {
  if (typeof value !== "string" || value.length > Math.ceil(maximum * 4 / 3) ||
    !/^[A-Za-z0-9_-]+$/.test(value)) throw rejected();
  const bytes = Uint8Array.from(atob(value.replaceAll("-", "+").replaceAll("_", "/")), char => char.charCodeAt(0)).buffer;
  if (browserEncoded(bytes, minimum, maximum) !== value) throw rejected();
  return bytes;
}
function token(value: unknown): string { browserBytes(value, 32, 32); return value as string; }
function name(value: unknown): string {
  if (typeof value !== "string" || !value || value.length > 200 ||
    !value.isWellFormed() || /[\u0000-\u001f\u007f]/.test(value)) throw rejected();
  return value;
}
function deadline(value: unknown, now: number): number {
  const expires = credentialInteger(value, 1);
  credentialInteger(now, 1);
  if (expires <= now || expires > now + 120) throw rejected();
  return expires;
}
export function parseBrowserProofStart(
  value: unknown, accountId: string, action: CredentialAction, rpId: string,
  now = Math.floor(Date.now() / 1000),
): BrowserProofStart {
  canonicalUuid(accountId); credentialAction(action);
  const item = record(value, ["attempt_id", "confirmation_token", "preview", "options"]);
  const preview = record(item.preview, ["target", "accountName", "expiresAt", "execution_enabled"]);
  const target = parseActionTarget(preview.target);
  if (target.platform_account_id !== accountId || target.action !== action ||
    preview.execution_enabled !== false) throw rejected();
  const expiresAt = deadline(preview.expiresAt, now);
  const options = record(item.options, ["challenge", "rpId", "timeout", "allowCredentials", "userVerification"]);
  if (options.rpId !== rpId || !rpId || options.userVerification !== "required" ||
    !Array.isArray(options.allowCredentials) || options.allowCredentials.length !== 1) throw rejected();
  const timeout = credentialInteger(options.timeout, 1);
  if (timeout > 120_000) throw rejected();
  const credential = record(options.allowCredentials[0], ["id", "type"]);
  if (credential.type !== "public-key") throw rejected();
  return Object.freeze({
    attempt_id: canonicalUuid(item.attempt_id), confirmation_token: token(item.confirmation_token),
    preview: Object.freeze({ target, accountName: name(preview.accountName), expiresAt, execution_enabled: false }),
    options: { challenge: browserBytes(options.challenge, 32, 32), rpId, timeout,
      userVerification: "required" as const, allowCredentials: [{ type: "public-key" as const, id: browserBytes(credential.id, 1, 1023) }] },
  });
}
/** Copy only the authenticator assertion fields; no extensions were requested. */
export function serializeBrowserProofAssertion(value: Credential | null) {
  if (!value || value.type !== "public-key") throw rejected();
  const credential = value as PublicKeyCredential;
  const response = credential.response as AuthenticatorAssertionResponse;
  const id = browserEncoded(credential.rawId, 1, 1023);
  if (id !== credential.id) throw rejected();
  record(credential.getClientExtensionResults(), []);
  const userHandle = response.userHandle === null ? undefined : browserEncoded(response.userHandle, 1, 64);
  if (credential.authenticatorAttachment && !["platform", "cross-platform"].includes(credential.authenticatorAttachment)) throw rejected();
  return {
    id, rawId: id, type: "public-key", clientExtensionResults: {},
    response: {
      clientDataJSON: browserEncoded(response.clientDataJSON, 1, 4096),
      authenticatorData: browserEncoded(response.authenticatorData, 37, 1024),
      signature: browserEncoded(response.signature, 1, 1024),
      ...(userHandle === undefined ? {} : { userHandle }),
    },
    ...(credential.authenticatorAttachment ? { authenticatorAttachment: credential.authenticatorAttachment } : {}),
  };
}
export function parseBrowserProofGrant(
  value: unknown, start: BrowserProofStart, now = Math.floor(Date.now() / 1000),
): BrowserProofGrant {
  const receipt = record(value, ["grant_id", "grant"]);
  const grant = record(receipt.grant, ["target", "accountName", "checkedAt", "expiresAt", "confirmationToken", "execution_enabled"]);
  const target = parseActionTarget(grant.target), checkedAt = credentialInteger(grant.checkedAt, 1);
  if (JSON.stringify(target) !== JSON.stringify(start.preview.target) ||
    grant.accountName !== start.preview.accountName || token(grant.confirmationToken) !== start.confirmation_token ||
    grant.execution_enabled !== false || checkedAt > now || checkedAt >= start.preview.expiresAt ||
    checkedAt < start.preview.expiresAt - 120) throw rejected();
  const expiresAt = deadline(grant.expiresAt, now);
  if (expiresAt <= checkedAt || expiresAt > checkedAt + 120) throw rejected();
  return Object.freeze({ grant_id: canonicalUuid(receipt.grant_id), target, accountName: name(grant.accountName),
    checkedAt, expiresAt, confirmationToken: start.confirmation_token, execution_enabled: false });
}
export function parseBrowserProofConfirmation(value: unknown, grant: BrowserProofGrant): void {
  const receipt = record(value, ["status", "execution_enabled", "action", "platform_account_id"]);
  if (receipt.status !== "verified" || receipt.execution_enabled !== false ||
    receipt.action !== grant.target.action || receipt.platform_account_id !== grant.target.platform_account_id) throw rejected();
}
