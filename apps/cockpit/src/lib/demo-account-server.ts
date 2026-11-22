import "server-only";
import { getBoundSession } from "./auth.ts";
import { getConfig } from "./config.ts";
import { apiRequest } from "./backend.ts";
import { runtime } from "./demo-trading-passkey-credential-browser-server.ts";
import { parseDemoTradingCredentialActionMetadata } from "./demo-trading-credential-action-contracts.ts";
import { assertAuthorizedSession, snapshotAuthorizedSession } from "./authorized-session.ts";
import { exactObject } from "./passkey-enrollment-state.ts";
import { canonicalUuid } from "./credential-action-contracts.ts";
import { parseDemoAccount, type DemoAccount } from "./demo-account-contract.ts";
import { parseDemoStartup, type DemoStartup } from "./demo-startup-contract.ts";

type Cache = { key: string; data: DemoAccount; at: number };
const symbol = Symbol.for("investalo.demo-account-cache/1");
type Shared = typeof globalThis & { [symbol]?: Cache };
const headers = { "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer" };

export async function handleDemoAccount(request: Request) {
  if (request.method !== "GET") return Response.json({ error: "Nicht verfügbar." }, { status: 405, headers });
  if (process.env.COCKPIT_DEMO_ACCOUNT_SYNC !== "1") return Response.json({ error: "Nicht verfügbar." }, { status: 404, headers });
  try {
    const current = await getBoundSession();
    if (!current) return Response.json({ error: "Bitte anmelden." }, { status: 401, headers });
    const original = snapshotAuthorizedSession(current.session), config = await getConfig();
    const url = new URL(request.url);
    const startup = url.search === "?inspection=startup";
    if (url.pathname !== "/api/bitget-demo/account" || url.search && !startup ||
      request.headers.get("sec-fetch-site") !== "same-origin" ||
      request.headers.has("origin") && request.headers.get("origin") !== config.origin) throw new Error();
    const installed = await runtime();
    if (!installed?.identity?.readAccount) throw new Error();
    async function guard() {
      if (process.env.COCKPIT_DEMO_ACCOUNT_SYNC !== "1") throw new Error();
      const live = await getBoundSession();
      if (!live || live.handle !== current!.handle) throw new Error();
      assertAuthorizedSession(original, live.session); await installed!.check();
    }
    async function metadata() {
      await guard();
      const me = exactObject(await apiRequest<unknown>(original, "/v1/me"), ["user", "memberships", "live_enabled"]);
      const user = exactObject(me.user, ["id", "subject", "auth_epoch"]);
      const userId = canonicalUuid(user.id);
      if (user.subject !== original.subject || user.auth_epoch !== original.authEpoch || !Array.isArray(me.memberships) ||
        !me.memberships.some(value => {
          const m = exactObject(value, ["tenant_id", "tenant_name", "role"]);
          return m.tenant_id === original.tenantId && ["owner", "trader"].includes(m.role as string);
        })) throw new Error();
      const m = parseDemoTradingCredentialActionMetadata(await apiRequest<unknown>(original,
        `/v1/bitget-demo-trading/credential-actions/${installed!.accountId}`),
        { tenantId: original.tenantId, accountId: installed!.accountId, authEpoch: original.authEpoch });
      if (m.account.status !== "ready" || m.connection?.status !== "active") throw new Error();
      await guard();
      return { userId, metadata: m };
    }
    const before = await metadata(), connection = before.metadata.connection!;
    const key = JSON.stringify([original.tenantId, before.userId, original.authEpoch,
      installed.accountId, connection.connection_id, connection.credential_revision, connection.storage_version]);
    const shared = globalThis as Shared;
    let data: DemoAccount | DemoStartup;
    if (!startup && shared[symbol]?.key === key && Date.now() - shared[symbol]!.at < 25000) {
      data = parseDemoAccount(shared[symbol]!.data, original.tenantId, installed.accountId);
    } else {
      data = await installed.identity.readAccount({ ...current, session: original, origin: config.origin },
        before.userId, { platform_account_id: installed.accountId, connection_id: connection.connection_id,
          credential_revision: 1, storage_version: connection.storage_version,
          ...(startup ? { inspection: "startup" as const } : {}) });
    }
    const after = await metadata();
    if (after.userId !== before.userId || JSON.stringify(after.metadata) !== JSON.stringify(before.metadata)) throw new Error();
    await guard();
    if (startup) return Response.json(parseDemoStartup(data, original.tenantId, installed.accountId), { headers });
    data = parseDemoAccount(data, original.tenantId, installed.accountId);
    shared[symbol] = { key, data, at: Math.min(Date.now(), Date.parse(data.observed_at)) };
    return Response.json(data, { headers });
  } catch {
    return Response.json({ error: "Demo-Kontodaten derzeit nicht bestätigt. Bitte erneut aktualisieren." },
      { status: 503, headers });
  }
}
