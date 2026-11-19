import "server-only";
import { randomUUID } from "node:crypto";
import { getBoundSession, type Session } from "./auth.ts";
import { getConfig } from "./config.ts";
import { apiRequest } from "./backend.ts";
import { parseOverview } from "./contracts.ts";
import {
  canonicalUuid, parseDemoTradingCredentialActionMetadata, type DemoTradingCredentialActionMetadata,
} from "./demo-trading-credential-action-contracts.ts";
import {
  handleDemoTradingPasskeyCredentialHttp, type DemoTradingCredentialHttpPhase, type DemoTradingCredentialHttpRequests,
} from "./demo-trading-passkey-credential-http.ts";
import { loadDemoTradingCredentialRuntime, DEMO_TRADING_IDENTITY_DIRECTORY,
  type DemoTradingRuntime } from "./demo-trading-credential-runtime.ts";
import { createDemoTradingPrivateCredentialServerPorts } from "./demo-trading-passkey-credential-server.ts";
import { randomToken } from "./security.ts";

// Next route bundles share one continuation store. Restart loses only ephemeral
// handles; committed019 remains authoritative. Failed installation never retries.
const runtimeKey = Symbol.for("investalo.demo-trading.browser-runtime/1");
type RuntimeGlobal = typeof globalThis & { [runtimeKey]?: Promise<DemoTradingRuntime | null> };
async function runtime(): Promise<DemoTradingRuntime | null> {
  if (process.env.COCKPIT_DEMO_TRADING_CREDENTIALS !== "1") return null;
  const shared = globalThis as RuntimeGlobal;
  shared[runtimeKey] ??= (async () => {
    try {
      const config = await getConfig();
      return await loadDemoTradingCredentialRuntime({
        directory: DEMO_TRADING_IDENTITY_DIRECTORY, ownerUid: 10002,
        origin: config.origin, oidcIssuer: config.issuer,
        portsFor: createDemoTradingPrivateCredentialServerPorts,
        now: () => Math.floor(Date.now() / 1000), randomToken, randomUuid: randomUUID,
      });
    } catch { return null; }
  })();
  const installed = await shared[runtimeKey];
  try { await installed?.check(); return installed; } catch { return null; }
}

export async function demoTradingCredentialBrowserRuntimeAvailable(): Promise<boolean> {
  return await runtime() !== null;
}

export async function listDemoTradingCredentialMetadata(session: Session): Promise<DemoTradingCredentialActionMetadata[]> {
  const overview = parseOverview(await apiRequest<unknown>(session, "/v1/overview"), session.tenantId);
  if (overview.accounts.length > 50) throw new Error("DEMO_TRADING_CREDENTIAL_METADATA_REJECTED");
  const accounts: DemoTradingCredentialActionMetadata[] = [];
  const seen = new Set<string>();
  for (const account of overview.accounts) {
    if (account.mode !== "bitget_demo") continue;
    const id = canonicalUuid(account.id);
    if (seen.has(id)) throw new Error("DEMO_TRADING_CREDENTIAL_METADATA_REJECTED");
    seen.add(id);
    try {
      const value = await apiRequest<unknown>(session, `/v1/bitget-demo-trading/credential-actions/${id}`);
      accounts.push(parseDemoTradingCredentialActionMetadata(value, { tenantId: session.tenantId,
        accountId: id, authEpoch: session.authEpoch }));
    } catch (error) {
      const status = (error as { status?: number }).status;
      if (status !== 403 && status !== 404) throw error;
    }
  }
  return accounts;
}

export async function handleDemoTradingCredentialBrowserRequest(request: Request, phase: DemoTradingCredentialHttpPhase) {
  const installed = await runtime();
  return handleDemoTradingPasskeyCredentialHttp(request, phase, {
    enabled: () => installed !== null && process.env.COCKPIT_DEMO_TRADING_CREDENTIALS === "1",
    origin: async () => (await getConfig()).origin,
    session: async () => {
      const bound = await getBoundSession();
      return bound ? { ...bound, origin: (await getConfig()).origin } : null;
    },
    execute: async (input, bound) => {
      if (!installed) throw new Error("DEMO_TRADING_CREDENTIAL_BROWSER_PROVIDER_UNAVAILABLE");
      await installed.check();
      if (phase === "start") {
        const start = input as DemoTradingCredentialHttpRequests["start"];
        if (start.platform_account_id !== installed.accountId) throw new Error("DEMO_TRADING_CREDENTIAL_BROWSER_PROVIDER_UNAVAILABLE");
        return installed.flow.start(bound, start.platform_account_id, start.action, start.credentials);
      }
      if (phase === "finish") {
        const finish = input as DemoTradingCredentialHttpRequests["finish"];
        return installed.flow.finish(bound, finish.flow_token, finish.credential);
      }
      const execute = input as DemoTradingCredentialHttpRequests["execute"];
      return installed.flow.execute(bound, execute.flow_token, execute.body, execute.consent);
    },
    now: () => Math.floor(Date.now() / 1000),
  });
}
