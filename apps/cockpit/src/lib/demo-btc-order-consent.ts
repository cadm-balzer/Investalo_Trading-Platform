/** Server-side BTC test signing after actual HTTP confirmation; no route/transport. */
import { createHash, createHmac, randomUUID } from "node:crypto";
import { canonicalUuid, credentialInteger } from "./credential-action-contracts.ts";
import { exactObject, parseEnrollmentJson } from "./passkey-enrollment-state.ts";
import { assertAuthorizedSession, snapshotAuthorizedSession } from "./authorized-session.ts";
import { actionProofBinding, type ProofSession } from "./demo-trading-passkey-action-proof-state.ts";
import { parseDemoTradingCredentialActionMetadata } from "./demo-trading-credential-action-contracts.ts";
import { sameSecret } from "./security.ts";

export const BTC_ORDER_CONFIRMATION = "btc-demo-long-isolated-2x-notional-at-most-20-usdt";
export const BTC_ORDER_PATH = "/v1/bitget-demo-trading/order-submit";
export const BTC_MARKET_CONFIRMATION = "btc-demo-market-long-isolated-2x-estimate-20-usdt";
const LIMIT_PROFILE = Object.freeze({ confirmation: BTC_ORDER_CONFIRMATION, path: BTC_ORDER_PATH,
  browserPath: "/api/bitget-demo/orders/btc-test/submit",
  kind: "investalo-demo-btc-test-order-consent/1", audience: "investalo-demo-btc-test-order" });
const MARKET_PROFILE = Object.freeze({ confirmation: BTC_MARKET_CONFIRMATION,
  path: "/v1/bitget-demo-trading/market-order-submit",
  browserPath: "/api/bitget-demo/orders/btc-market/submit",
  kind: "investalo-demo-btc-market-order-consent/1", audience: "investalo-demo-btc-market-order" });
const ORIGIN = "https://cockpit.investalo.de";
const MAX_BODY = 16384;
let inFlight = 0;
const rejected = () => new Error("BTC_ORDER_CONSENT_NOT_CONFIRMED");
type Bound = Readonly<{ handle: string; session: ProofSession["session"] }>;
export type BTCOrderConsentDependencies = Readonly<{
  accountId: string; signingKey: Uint8Array;
  getSession(): Promise<Bound | null>;
  getActor(authorized: ProofSession): Promise<unknown>;
  checkInstallation(): Promise<void>;
  now?: () => number;
}>;

function hash(value: unknown): string {
  if (typeof value !== "string" || !/^[a-f0-9]{64}$/.test(value)) throw rejected();
  return value;
}
function bodyTarget(value: unknown, accountId: string, confirmation: string) {
  const item = exactObject(value, ["platform_account_id", "connection_id", "credential_revision",
    "storage_version", "command_id", "intent_sha256", "outbox_receipt", "confirmation"]);
  const receipt = exactObject(item.outbox_receipt, ["schema", "outbox_id", "binding_digest",
    "revision", "head", "state_digest"]);
  if (item.platform_account_id !== accountId || item.credential_revision !== 1 ||
    item.confirmation !== confirmation || receipt.schema !== "bitget-classic-demo-outbox/1")
    throw rejected();
  return { platform_account_id: accountId, connection_id: canonicalUuid(item.connection_id),
    credential_revision: 1, storage_version: credentialInteger(item.storage_version, 1),
    command_id: canonicalUuid(item.command_id), intent_sha256: hash(item.intent_sha256),
    outbox_receipt: { schema: receipt.schema, outbox_id: canonicalUuid(receipt.outbox_id),
      binding_digest: hash(receipt.binding_digest), revision: credentialInteger(receipt.revision, 1),
      head: hash(receipt.head), state_digest: hash(receipt.state_digest) },
    confirmation };
}
export async function readOrderBody(request: Request): Promise<unknown> {
  const announced = request.headers.get("content-length");
  if (announced !== null && (!/^[1-9][0-9]{0,4}$/.test(announced) || Number(announced) > MAX_BODY))
    throw rejected();
  if (!request.body) throw rejected();
  const reader = request.body.getReader(), chunks: Uint8Array[] = [];
  let size = 0, expired = false;
  const deadline = setTimeout(() => { expired = true; void reader.cancel().catch(() => {}); }, 10000);
  try {
    for (;;) {
      const next = await reader.read();
      if (expired) throw rejected();
      if (next.done) break;
      size += next.value.byteLength;
      if (size > MAX_BODY) { await reader.cancel(); throw rejected(); }
      chunks.push(next.value);
    }
    if (size < 1 || announced !== null && Number(announced) !== size) throw rejected();
    const raw = new TextDecoder("utf-8", { fatal: true }).decode(Buffer.concat(chunks));
    // Canonical body publication is independent of client whitespace/key order.
    return parseEnrollmentJson(raw);
  } catch { void reader.cancel().catch(() => {}); throw rejected(); }
  finally { clearTimeout(deadline); reader.releaseLock(); }
}

/** Returns a private executor packet. Caller must never return it to a browser.
 * getActor must independently query current owner/trader membership and metadata.
 * A native account guard and durable consumer are still required before POST.
 */
export async function prepareDemoBTCTestConsent(request: Request, deps: BTCOrderConsentDependencies) {
  return prepareConsent(request, deps, LIMIT_PROFILE);
}
export async function prepareDemoBTCMarketConsent(request: Request, deps: BTCOrderConsentDependencies) {
  return prepareConsent(request, deps, MARKET_PROFILE);
}
async function prepareConsent(request: Request, deps: BTCOrderConsentDependencies,
  profile: typeof LIMIT_PROFILE | typeof MARKET_PROFILE) {
  if (inFlight >= 8) throw rejected();
  inFlight++;
  try {
    const uri = new URL(request.url);
    if (request.method !== "POST" || uri.origin !== ORIGIN ||
      uri.pathname !== profile.browserPath || uri.search ||
      request.headers.get("origin") !== ORIGIN || request.headers.get("sec-fetch-site") !== "same-origin" ||
      request.headers.get("content-type") !== "application/json" ||
      !(deps.signingKey instanceof Uint8Array) || deps.signingKey.byteLength !== 32)
      throw rejected();
    const accountId = canonicalUuid(deps.accountId), now = deps.now ?? (() => Math.floor(Date.now() / 1000));
    const current = await deps.getSession();
    if (!current) throw rejected();
    const original = snapshotAuthorizedSession(current.session, now());
    if (original.issuer !== "https://auth.cockpit.investalo.de") throw rejected();
    if (!sameSecret(original.csrf, request.headers.get("x-csrf-token") ?? "")) throw rejected();
    const authorized: ProofSession = Object.freeze({ handle: current.handle, session: original, origin: ORIGIN });
    async function guard() {
      await deps.checkInstallation();
      const live = await deps.getSession();
      if (!live || !sameSecret(live.handle, current!.handle)) throw rejected();
      assertAuthorizedSession(original, live.session, now());
    }
    async function actor() {
      await guard();
      const data = exactObject(await deps.getActor(authorized), ["userId", "role", "metadata"]);
      if (!["owner", "trader"].includes(data.role as string)) throw rejected();
      const userId = canonicalUuid(data.userId), metadata = parseDemoTradingCredentialActionMetadata(data.metadata,
        { tenantId: original.tenantId, accountId, authEpoch: original.authEpoch });
      if (metadata.account.status !== "ready" || metadata.connection?.status !== "active") throw rejected();
      await guard();
      return { userId, metadata };
    }
    const before = await actor();
    const target = bodyTarget(await readOrderBody(request), accountId, profile.confirmation);
    if (target.connection_id !== before.metadata.connection!.connection_id ||
      target.storage_version !== before.metadata.connection!.storage_version) throw rejected();
    const after = await actor();
    if (JSON.stringify(before) !== JSON.stringify(after)) throw rejected();
    await guard();
    const at = credentialInteger(now(), 1), expires = Math.min(at + 15, original.expiresAt);
    if (expires <= at) throw rejected();
    const body = JSON.stringify(target);
    const context = Object.freeze({ tenant_id: original.tenantId, user_id: before.userId, subject: original.subject,
      auth_epoch: original.authEpoch, oidc_auth_time: original.oidcAuthTime,
      session_binding: actionProofBinding(authorized), session_expires_at: original.expiresAt });
    const claims = { ...context, kind: profile.kind,
      aud: profile.audience, oidc_issuer: original.issuer, origin: ORIGIN,
      iat: at, exp: expires, jti: randomUUID(), htm: "POST", htu: profile.path,
      body_sha256: createHash("sha256").update(body).digest("hex") };
    const header = Buffer.from(JSON.stringify({ alg: "HS256", typ: "JWT" })).toString("base64url");
    const payload = Buffer.from(JSON.stringify(claims)).toString("base64url");
    const token = `${header}.${payload}.${createHmac("sha256", Buffer.from(deps.signingKey)).update(`${header}.${payload}`).digest("base64url")}`;
    return Object.freeze({ context, body, token });
  } catch { throw rejected(); }
  finally { inFlight--; }
}
