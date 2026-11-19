import "server-only";
import { randomUUID } from "node:crypto";
import { getBoundSession } from "./auth.ts";
import { apiRequest } from "./backend.ts";
import { getConfig } from "./config.ts";
import { randomToken } from "./security.ts";
import type { ProofSession } from "./demo-trading-passkey-action-proof-state.ts";
import {
  createDemoTradingPasskeyCredentialPorts, type DemoTradingCredentialIdentityPorts,
} from "./demo-trading-passkey-credential-provider.ts";
import { createDemoTradingCredentialPrivateProvider } from "./demo-trading-credential-private-provider.ts";
import type { DemoTradingCredentialPrivateIdentity } from "./demo-trading-credential-private-identity.ts";

/** Explicit own private identity; current API actor is read before binding TLS. */
export async function createDemoTradingPrivateCredentialServerPorts(
  authorized: ProofSession, identity: DemoTradingCredentialPrivateIdentity,
) {
  return createDemoTradingCredentialPrivateProvider({
    authorized, identity,
    async current() {
      const bound = await getBoundSession();
      if (!bound) throw new Error("DEMO_TRADING_CREDENTIAL_PRIVATE_PROVIDER_REJECTED");
      return { ...bound, origin: (await getConfig()).origin };
    },
    async api(session, path, options) {
      return apiRequest<unknown>(session, path, options, await getConfig());
    },
    now: () => Math.floor(Date.now() / 1000), randomToken, randomUuid: randomUUID,
  });
}

/** Explicit trusted identity supplied by server setup; no env flag creates one. */
export function createDemoTradingPasskeyCredentialServerPorts(
  authorized: ProofSession, identity: DemoTradingCredentialIdentityPorts,
) {
  return createDemoTradingPasskeyCredentialPorts({
    authorized, credentialKey: identity.credentialKey, execute: identity.execute,
    async current() {
      const bound = await getBoundSession();
      if (!bound) throw new Error("DEMO_TRADING_CREDENTIAL_PROVIDER_REJECTED");
      return { ...bound, origin: (await getConfig()).origin };
    },
    async api(session, path, options) {
      return apiRequest<unknown>(session, path, options, await getConfig());
    },
    now: () => Math.floor(Date.now() / 1000), randomToken, randomUuid: randomUUID,
  });
}
