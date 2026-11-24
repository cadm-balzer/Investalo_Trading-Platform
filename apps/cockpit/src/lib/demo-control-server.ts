import "server-only";
import { createHash } from "node:crypto";
import { join } from "node:path";
import { getBoundSession } from "./auth.ts";
import { getConfig } from "./config.ts";
import { apiRequest } from "./backend.ts";
import { runtime } from "./demo-trading-passkey-credential-browser-server.ts";
import { assertAuthorizedSession, snapshotAuthorizedSession } from "./authorized-session.ts";
import { canonicalUuid } from "./credential-action-contracts.ts";
import { exactObject } from "./passkey-enrollment-state.ts";
import { parseDemoTradingCredentialActionMetadata } from "./demo-trading-credential-action-contracts.ts";
import { readOrderBody } from "./demo-btc-order-consent.ts";
import { sameSecret } from "./security.ts";
import { parseControlInput } from "./demo-control-contract.ts";
import { DemoControlStore, type DemoControlBinding } from "./demo-control-state.ts";

const headers = { "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer" };
const storeKey = Symbol.for("investalo.demo-h1-control-store/1");
type Shared = typeof globalThis & { [storeKey]?: { fingerprint: string; store: DemoControlStore } };
let inFlight = 0;
export async function handleDemoControl(request: Request) {
  if (process.env.COCKPIT_DEMO_H1_CONTROL !== "1")
    return Response.json({ error: "Nicht verfügbar." }, { status: 404, headers });
  if (!["GET", "POST"].includes(request.method))
    return Response.json({ error: "Nicht verfügbar." }, { status: 405, headers });
  if (inFlight >= 8) return Response.json({ error: "Bitte später erneut prüfen." }, { status: 503, headers });
  inFlight++;
  try {
    const current = await getBoundSession();
    if (!current) return Response.json({ error: "Bitte anmelden." }, { status: 401, headers });
    const original = snapshotAuthorizedSession(current.session), originalHandle = current.handle,
      config = await getConfig(), url = new URL(request.url);
    if (config.origin !== "https://cockpit.investalo.de" ||
      url.pathname !== "/api/bitget-demo/control" || url.search || url.hash ||
      request.headers.get("sec-fetch-site") !== "same-origin" ||
      (request.method === "POST" ? request.headers.get("origin") !== config.origin ||
        request.headers.get("content-type") !== "application/json" ||
        !sameSecret(original.csrf, request.headers.get("x-csrf-token") ?? "") :
        request.headers.has("origin") && request.headers.get("origin") !== config.origin)) throw new Error();
    const installed = await runtime();
    if (!installed?.identity) throw new Error();
    async function guard() {
      if (process.env.COCKPIT_DEMO_H1_CONTROL !== "1") throw new Error();
      const live = await getBoundSession();
      if (!live || !sameSecret(live.handle, originalHandle)) throw new Error();
      assertAuthorizedSession(original, live.session); await installed!.check();
    }
    async function actor(): Promise<DemoControlBinding> {
      await guard();
      const me = exactObject(await apiRequest<unknown>(original, "/v1/me"), ["user", "memberships", "live_enabled"]);
      const user = exactObject(me.user, ["id", "subject", "auth_epoch"]), userId = canonicalUuid(user.id);
      if (user.subject !== original.subject || user.auth_epoch !== original.authEpoch ||
        !Array.isArray(me.memberships) || !me.memberships.some(value => {
          const m = exactObject(value, ["tenant_id", "tenant_name", "role"]);
          return m.tenant_id === original.tenantId && ["owner", "trader"].includes(m.role as string);
        })) throw new Error();
      // Existing private identity restricts the pilot account/actor. No port is invoked.
      installed!.identity!.forSession({ handle: originalHandle, session: original, origin: config.origin }, userId);
      const m = parseDemoTradingCredentialActionMetadata(await apiRequest<unknown>(original,
        `/v1/bitget-demo-trading/credential-actions/${installed!.accountId}`),
        { tenantId: original.tenantId, accountId: installed!.accountId, authEpoch: original.authEpoch });
      if (m.account.status !== "ready" || m.connection?.status !== "active") throw new Error();
      await guard();
      return { tenant_id: original.tenantId, account_id: installed!.accountId, user_id: userId,
        subject: original.subject, auth_epoch: original.authEpoch, connection_id: m.connection.connection_id,
        credential_revision: 1, storage_version: m.connection.storage_version };
    }
    const before = await actor(), directory = join(config.stateDir, "demo-h1-control");
    const fingerprint = createHash("sha256").update(directory).update("\0").update(config.sessionSecret).digest("hex");
    const shared = globalThis as Shared;
    if (shared[storeKey] && shared[storeKey].fingerprint !== fingerprint) throw new Error();
    shared[storeKey] ??= { fingerprint, store: new DemoControlStore(directory, config.sessionSecret) };
    async function unchanged() {
      if (JSON.stringify(await actor()) !== JSON.stringify(before)) throw new Error();
    }
    const store = shared[storeKey].store;
    const result = request.method === "GET" ? await store.summary(before) :
      await store.change(before, parseControlInput(await readOrderBody(request)), Math.floor(Date.now()/1000), unchanged);
    await unchanged(); await guard();
    return Response.json(result, { headers });
  } catch {
    return Response.json({ error: "Steuerung nicht bestätigt. Lade den Status neu, bevor du eine weitere Änderung sendest." },
      { status: 503, headers });
  } finally { inFlight--; }
}
