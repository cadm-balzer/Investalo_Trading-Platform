/** Own explicit provider composition; no global installation or browser activation. */
import type { Session } from "./auth.ts";
import {
  canonicalUuid,
} from "./demo-trading-credential-action-contracts.ts";
import {
  parseActionProofContext, proofSession, type ProofSession,
} from "./demo-trading-passkey-action-proof-state.ts";
import {
  createDemoTradingPasskeyCredentialPorts,
} from "./demo-trading-passkey-credential-provider.ts";
import type { DemoTradingCredentialPrivateIdentity } from "./demo-trading-credential-private-identity.ts";

export type DemoTradingCredentialPrivateProviderOptions = Readonly<{
  authorized: ProofSession; identity: DemoTradingCredentialPrivateIdentity;
  current(): Promise<ProofSession>;
  api(session: Session, path: string, options: Readonly<{ method: "GET" | "POST"; body?: string }>): Promise<unknown>;
  now(): number; randomToken(): string; randomUuid(): string;
}>;

/**
 * User ID comes from current authenticated API context, independently of JWT.
 * Existing provider checks the original session before/after every API await.
 */
export async function createDemoTradingCredentialPrivateProvider(input: DemoTradingCredentialPrivateProviderOptions) {
  try {
    const { current, api, now, randomToken, randomUuid, identity } = input;
    const bound = proofSession(input.authorized, now());
    const scoped = createDemoTradingPasskeyCredentialPorts({
      authorized: bound, current, api, now, randomToken, randomUuid,
      credentialKey: async () => { throw new Error(); },
      execute: async () => { throw new Error(); },
    });
    const actor = parseActionProofContext(await scoped.context(bound.session), bound);
    const ports = identity.forSession(bound, canonicalUuid(actor.user_id));
    return createDemoTradingPasskeyCredentialPorts({
      authorized: bound, current, api, now, randomToken, randomUuid, ...ports,
    });
  } catch { throw new Error("DEMO_TRADING_CREDENTIAL_PRIVATE_PROVIDER_REJECTED"); }
}
