/** Shared browser/BFF body construction. No signing, persistence or authority. */
import { parseActionTarget, type ActionTarget } from "./credential-action-contracts.ts";

export type CredentialTriple = Readonly<{ api_key: string; secret: string; passphrase: string }>;
const rejected = () => new Error("CREDENTIAL_BROWSER_BODY_REJECTED");
function text(value: unknown, maximum: number): string {
  if (typeof value !== "string" || !value || !value.isWellFormed() ||
    new TextEncoder().encode(value).byteLength > maximum || /[\p{Cc}\p{Cf}\p{Cs}]/u.test(value)) throw rejected();
  return value;
}
export function parseBrowserCredentialTriple(value: unknown): CredentialTriple {
  if (!value || typeof value !== "object" || Array.isArray(value) ||
    ![Object.prototype, null].includes(Object.getPrototypeOf(value))) throw rejected();
  const fields = ["api_key", "secret", "passphrase"], keys = Reflect.ownKeys(value);
  if (keys.length !== fields.length || keys.some(key => typeof key !== "string" || !fields.includes(key) ||
    !Object.hasOwn(Object.getOwnPropertyDescriptor(value, key)!, "value"))) throw rejected();
  const item = value as Record<string, unknown>;
  return Object.freeze({ api_key: text(item.api_key, 256), secret: text(item.secret, 1024),
    passphrase: text(item.passphrase, 256) });
}
export function buildBrowserCredentialBody(target: ActionTarget, triple?: CredentialTriple): string {
  const current = parseActionTarget(target);
  if (current.action === "revoke" && triple !== undefined) throw rejected();
  const credentials = current.action === "revoke" ? undefined : parseBrowserCredentialTriple(triple);
  const body = JSON.stringify({
    platform_account_id: current.platform_account_id, connection_id: current.connection_id,
    ...(current.action === "register" ? {} : {
      expected_revision: current.expected_revision, expected_storage: current.expected_storage,
    }),
    ...(credentials === undefined ? {} : { credentials }),
  });
  if (new TextEncoder().encode(body).byteLength > 4096) throw rejected();
  return body;
}
