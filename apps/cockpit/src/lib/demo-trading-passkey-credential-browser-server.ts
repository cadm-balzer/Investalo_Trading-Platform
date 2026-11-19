import "server-only";
import { getBoundSession, type Session } from "./auth.ts";
import { getConfig } from "./config.ts";
import { apiRequest } from "./backend.ts";
import { parseOverview } from "./contracts.ts";
import {
  canonicalUuid, parseDemoTradingCredentialActionMetadata, type DemoTradingCredentialActionMetadata,
} from "./demo-trading-credential-action-contracts.ts";
import {
  handleDemoTradingPasskeyCredentialHttp, type DemoTradingCredentialHttpPhase,
} from "./demo-trading-passkey-credential-http.ts";

/** A private signing/TLS/provisioning identity has not been installed here. */
export function demoTradingCredentialBrowserRuntimeAvailable(): boolean {
  return false;
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

export function handleDemoTradingCredentialBrowserRequest(request: Request, phase: DemoTradingCredentialHttpPhase) {
  return handleDemoTradingPasskeyCredentialHttp(request, phase, {
    enabled: demoTradingCredentialBrowserRuntimeAvailable,
    origin: async () => (await getConfig()).origin,
    session: async () => {
      const bound = await getBoundSession();
      return bound ? { ...bound, origin: (await getConfig()).origin } : null;
    },
    execute: async () => { throw new Error("DEMO_TRADING_CREDENTIAL_BROWSER_PROVIDER_UNAVAILABLE"); },
    now: () => Math.floor(Date.now() / 1000),
  });
}
