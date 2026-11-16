/** Own explicit provider composition; no global installation or browser activation. */
import type { Session } from "./auth.ts";
import {
  canonicalUuid,
} from "./demo-credential-action-contracts.ts";
import {
  parseActionProofContext, proofSession, type ProofSession,
} from "./demo-passkey-action-proof-state.ts";
import {
  createDemoPasskeyCredentialPorts,
} from "./demo-passkey-credential-provider.ts";
import type { DemoCredentialPrivateIdentity } from "./demo-credential-private-identity.ts";

export type DemoCredentialPrivateProviderOptions = Readonly<{
  authorized: ProofSession; identity: DemoCredentialPrivateIdentity;
  current(): Promise<ProofSession>;
  api(session: Session, path: string, options: Readonly<{ method: "GET" | "POST"; body?: string }>): Promise<unknown>;
  now(): number; randomToken(): string; randomUuid(): string;
}>;

/**
 * User ID comes from current authenticated API context, independently of JWT.
 * Existing provider checks the original session before/after every API await.
 */
export async function createDemoCredentialPrivateProvider(input: DemoCredentialPrivateProviderOptions) {
  try {
    const { current, api, now, randomToken, randomUuid, identity } = input;
    const bound = proofSession(input.authorized, now());
    const scoped = createDemoPasskeyCredentialPorts({
      authorized: bound, current, api, now, randomToken, randomUuid,
      credentialKey: async () => { throw new Error(); },
      execute: async () => { throw new Error(); },
    });
    const actor = parseActionProofContext(await scoped.context(bound.session), bound);
    const ports = identity.forSession(bound, canonicalUuid(actor.user_id));
    return createDemoPasskeyCredentialPorts({
      authorized: bound, current, api, now, randomToken, randomUuid, ...ports,
    });
  } catch { throw new Error("DEMO_CREDENTIAL_PRIVATE_PROVIDER_REJECTED"); }
}
