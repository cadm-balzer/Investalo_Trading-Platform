import "server-only";
import { getBoundSession, type Session } from "./auth.ts";
import { getConfig } from "./config.ts";
import { apiRequest } from "./backend.ts";
import { parseOverview } from "./contracts.ts";
import {
  canonicalUuid, parseDemoCredentialActionMetadata, type DemoCredentialActionMetadata,
} from "./demo-credential-action-contracts.ts";
import {
  handleDemoPasskeyCredentialHttp, type DemoCredentialHttpPhase,
} from "./demo-passkey-credential-http.ts";

/** A private signing/TLS/provisioning identity has not been installed here. */
export function demoCredentialBrowserRuntimeAvailable(): boolean {
  return false;
}

export async function listDemoCredentialMetadata(session: Session): Promise<DemoCredentialActionMetadata[]> {
  const overview = parseOverview(await apiRequest<unknown>(session, "/v1/overview"), session.tenantId);
  if (overview.accounts.length > 50) throw new Error("DEMO_CREDENTIAL_METADATA_REJECTED");
  const accounts: DemoCredentialActionMetadata[] = [];
  const seen = new Set<string>();
  for (const account of overview.accounts) {
    if (account.mode !== "bitget_demo") continue;
    const id = canonicalUuid(account.id);
    if (seen.has(id)) throw new Error("DEMO_CREDENTIAL_METADATA_REJECTED");
    seen.add(id);
    try {
      const value = await apiRequest<unknown>(session, `/v1/bitget-demo/credential-actions/${id}`);
      accounts.push(parseDemoCredentialActionMetadata(value, { tenantId: session.tenantId,
        accountId: id, authEpoch: session.authEpoch }));
    } catch (error) {
      const status = (error as { status?: number }).status;
      if (status !== 403 && status !== 404) throw error;
    }
  }
  return accounts;
}

export function handleDemoCredentialBrowserRequest(request: Request, phase: DemoCredentialHttpPhase) {
  return handleDemoPasskeyCredentialHttp(request, phase, {
    enabled: demoCredentialBrowserRuntimeAvailable,
    origin: async () => (await getConfig()).origin,
    session: async () => {
      const bound = await getBoundSession();
      return bound ? { ...bound, origin: (await getConfig()).origin } : null;
    },
    execute: async () => { throw new Error("DEMO_CREDENTIAL_BROWSER_PROVIDER_UNAVAILABLE"); },
    now: () => Math.floor(Date.now() / 1000),
  });
}
