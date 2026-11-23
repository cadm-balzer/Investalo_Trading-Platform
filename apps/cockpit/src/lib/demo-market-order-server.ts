import "server-only";
import { getBoundSession } from "./auth.ts";
import { apiRequest } from "./backend.ts";
import { runtime } from "./demo-trading-passkey-credential-browser-server.ts";
import { snapshotAuthorizedSession, assertAuthorizedSession } from "./authorized-session.ts";
import { canonicalUuid } from "./credential-action-contracts.ts";
import { exactObject } from "./demo-account-contract.ts";
import { parseDemoTradingCredentialActionMetadata } from "./demo-trading-credential-action-contracts.ts";
import { readOrderBody } from "./demo-btc-order-consent.ts";
import { MARKET_CONFIRMATION, parseMarketPrepared, parseMarketStatus } from "./demo-market-order-contract.ts";
import { sameSecret } from "./security.ts";
import type { MarketPhase } from "./demo-market-order-executor.ts";
import type { ProofSession } from "./demo-trading-passkey-action-proof-state.ts";
const ORIGIN = "https://cockpit.investalo.de";
const headers = { "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer" };
let inFlight = 0;
export async function handleDemoMarketOrder(request: Request, phase: MarketPhase) {
  if (process.env.COCKPIT_DEMO_BTC_MARKET_TEST !== "1")
    return Response.json({ error: "Nicht verfügbar." }, { status: 404, headers });
  if (inFlight >= 8) return Response.json({ error: "Bitte später erneut prüfen." }, { status: 503, headers });
  inFlight++;
  try {
    if (!["prepare", "submit", "observe"].includes(phase)) throw new Error();
    const current = await getBoundSession();
    if (!current) return Response.json({ error: "Bitte anmelden." }, { status: 401, headers });
    const original = snapshotAuthorizedSession(current.session), url = new URL(request.url);
    // Next derives request.url from its internal listener behind the proxy.
    // Browser origin is checked independently against the fixed public origin.
    if (request.method !== "POST" ||
      url.pathname !== `/api/bitget-demo/orders/btc-market/${phase}` || url.search || url.hash ||
      request.headers.get("origin") !== ORIGIN || request.headers.get("sec-fetch-site") !== "same-origin" ||
      request.headers.get("content-type") !== "application/json" ||
      !sameSecret(original.csrf, request.headers.get("x-csrf-token") ?? "")) throw new Error();
    const installed = await runtime();
    if (!installed?.identity?.marketRead || !installed.identity.marketSubmit) throw new Error();
    async function guard() {
      if (process.env.COCKPIT_DEMO_BTC_MARKET_TEST !== "1") throw new Error();
      const live = await getBoundSession();
      if (!live || !sameSecret(live.handle, current!.handle)) throw new Error();
      assertAuthorizedSession(original, live.session); await installed!.check();
    }
    async function actor(_authorized?: ProofSession) {
      await guard();
      const me = exactObject(await apiRequest<unknown>(original, "/v1/me"), ["user", "memberships", "live_enabled"]);
      const user = exactObject(me.user, ["id", "subject", "auth_epoch"]);
      if (user.subject !== original.subject || user.auth_epoch !== original.authEpoch || !Array.isArray(me.memberships))
        throw new Error();
      const userId = canonicalUuid(user.id);
      let role: "owner" | "trader" | undefined;
      for (const membership of me.memberships) {
        const m = exactObject(membership, ["tenant_id", "tenant_name", "role"]);
        if (m.tenant_id === original.tenantId && (m.role === "owner" || m.role === "trader")) role = m.role;
      }
      if (!role) throw new Error();
      const metadata = parseDemoTradingCredentialActionMetadata(await apiRequest<unknown>(original,
        `/v1/bitget-demo-trading/credential-actions/${installed!.accountId}`),
        { tenantId: original.tenantId, accountId: installed!.accountId, authEpoch: original.authEpoch });
      if (metadata.account.status !== "ready" || metadata.connection?.status !== "active") throw new Error();
      await guard();
      return { userId, role, metadata };
    }
    const before = await actor(), connection = before.metadata.connection!;
    let result: unknown;
    if (phase === "submit") {
      result = await installed.identity.marketSubmit(request, {
        getSession: getBoundSession, getActor: actor, checkInstallation: guard });
    } else {
      const input = exactObject(await readOrderBody(request), phase === "prepare" ? ["confirmation"] : ["command_id"]);
      if (phase === "prepare" && input.confirmation !== MARKET_CONFIRMATION) throw new Error();
      const command = phase === "observe" ? (input.command_id === "latest" ? "latest" : canonicalUuid(input.command_id)) : undefined;
      await guard();
      result = await installed.identity.marketRead(phase, { ...current, session: original, origin: ORIGIN }, before.userId,
        { platform_account_id: installed.accountId, connection_id: connection.connection_id,
          credential_revision: 1, storage_version: connection.storage_version,
          ...(command ? { command_id: command } : {}) });
    }
    const after = await actor();
    if (JSON.stringify(before) !== JSON.stringify(after)) throw new Error();
    await guard();
    return Response.json(phase === "prepare" ?
      parseMarketPrepared(result, original.tenantId, installed.accountId) : parseMarketStatus(result), { headers });
  } catch {
    return Response.json({ error: phase === "submit" ?
      "Ergebnis nicht bestätigt. Bitte den Teststatus prüfen; keinen zweiten Auftrag senden." :
      "Demotest derzeit nicht bestätigt. Bitte später erneut prüfen." }, { status: 503, headers });
  } finally { inFlight--; }
}
