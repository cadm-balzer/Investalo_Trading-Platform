import "server-only";
import { randomUUID } from "node:crypto";
import { getBoundSession } from "./auth.ts";
import { apiRequest } from "./backend.ts";
import { getConfig } from "./config.ts";
import { randomToken } from "./security.ts";
import type { ProofSession } from "./demo-passkey-action-proof-state.ts";
import {
  createDemoPasskeyCredentialPorts, type DemoCredentialIdentityPorts,
} from "./demo-passkey-credential-provider.ts";
import { createDemoCredentialPrivateProvider } from "./demo-credential-private-provider.ts";
import type { DemoCredentialPrivateIdentity } from "./demo-credential-private-identity.ts";

/** Explicit own private identity; current API actor is read before binding TLS. */
export async function createDemoPrivateCredentialServerPorts(
  authorized: ProofSession, identity: DemoCredentialPrivateIdentity,
) {
  return createDemoCredentialPrivateProvider({
    authorized, identity,
    async current() {
      const bound = await getBoundSession();
      if (!bound) throw new Error("DEMO_CREDENTIAL_PRIVATE_PROVIDER_REJECTED");
      return { ...bound, origin: (await getConfig()).origin };
    },
    async api(session, path, options) {
      return apiRequest<unknown>(session, path, options, await getConfig());
    },
    now: () => Math.floor(Date.now() / 1000), randomToken, randomUuid: randomUUID,
  });
}

/** Explicit trusted identity supplied by server setup; no env flag creates one. */
export function createDemoPasskeyCredentialServerPorts(
  authorized: ProofSession, identity: DemoCredentialIdentityPorts,
) {
  return createDemoPasskeyCredentialPorts({
    authorized, credentialKey: identity.credentialKey, execute: identity.execute,
    async current() {
      const bound = await getBoundSession();
      if (!bound) throw new Error("DEMO_CREDENTIAL_PROVIDER_REJECTED");
      return { ...bound, origin: (await getConfig()).origin };
    },
    async api(session, path, options) {
      return apiRequest<unknown>(session, path, options, await getConfig());
    },
    now: () => Math.floor(Date.now() / 1000), randomToken, randomUuid: randomUUID,
  });
}
