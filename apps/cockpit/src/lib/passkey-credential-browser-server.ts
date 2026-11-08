import "server-only";
import { getBoundSession } from "./auth.ts";
import { getConfig } from "./config.ts";
import { handlePasskeyCredentialHttp, type CredentialHttpPhase } from "./passkey-credential-http.ts";

/**
 * Browser contracts are exercised by an injected isolated provider. A real BFF
 * signing/mTLS identity is not provisioned yet; flags cannot create that authority.
 * Installing that provider and activating routes is a separate reviewed step.
 */
export function credentialBrowserRuntimeAvailable(): boolean {
  return false;
}

export function handleCredentialBrowserRequest(request: Request, phase: CredentialHttpPhase) {
  return handlePasskeyCredentialHttp(request, phase, {
    enabled: credentialBrowserRuntimeAvailable,
    origin: async () => (await getConfig()).origin,
    session: async () => {
      const bound = await getBoundSession();
      return bound ? { ...bound, origin: (await getConfig()).origin } : null;
    },
    execute: async () => { throw new Error("CREDENTIAL_BROWSER_PROVIDER_UNAVAILABLE"); },
    now: () => Math.floor(Date.now() / 1000),
  });
}
