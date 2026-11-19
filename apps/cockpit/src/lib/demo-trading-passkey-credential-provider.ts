/** Own server-port adapter. Identity provisioning and browser activation are separate. */
import type { Session } from "./auth.ts";
import { assertAuthorizedSession } from "./authorized-session.ts";
import {
  canonicalUuid, parseDemoTradingCredentialActionMetadata,
} from "./demo-trading-credential-action-contracts.ts";
import {
  assertProofSession, parseActionProofContext, proofSession, type ProofSession,
} from "./demo-trading-passkey-action-proof-state.ts";
import type { DemoTradingPasskeyCredentialPorts } from "./demo-trading-passkey-credential-flow.ts";

export type DemoTradingCredentialIdentityPorts = Readonly<Pick<
  DemoTradingPasskeyCredentialPorts, "credentialKey" | "execute">>;
export type DemoTradingCredentialProviderOptions = DemoTradingCredentialIdentityPorts & Readonly<{
  authorized: ProofSession;
  current(): Promise<ProofSession>;
  api(session: Session, path: string, options: Readonly<{ method: "GET" | "POST"; body?: string }>): Promise<unknown>;
  now(): number;
  randomToken(): string;
  randomUuid(): string;
}>;
const paths = new Set(["prepare", "claim", "finish", "grant", "authorize"].map(
  action => `/v1/bitget-demo-trading/passkey-authorizations/${action}`));
const rejected = () => new Error("DEMO_TRADING_CREDENTIAL_PROVIDER_REJECTED");

export function createDemoTradingPasskeyCredentialPorts(options: DemoTradingCredentialProviderOptions): DemoTradingPasskeyCredentialPorts {
  // Snapshot callbacks as well as the original authorized session before awaits.
  const { current, api, now, randomToken, randomUuid, credentialKey, execute } = options;
  const bound = proofSession(options.authorized, now());
  async function live(): Promise<ProofSession> {
    const actual = proofSession(await current(), now());
    assertProofSession(bound, actual, now());
    return actual;
  }
  async function request(session: Session, path: string,
    input: Readonly<{ method: "GET" | "POST"; body?: string }>): Promise<unknown> {
    assertAuthorizedSession(bound.session, session, now());
    await live();
    // Use the original immutable principal, never a caller-selected subject/time.
    const result = await api(bound.session, path, input);
    await live();
    return result;
  }
  return Object.freeze({
    current: live, now, randomToken, randomUuid,
    async metadata(session: Session, accountId: string) {
      const id = canonicalUuid(accountId);
      const result = await request(session, `/v1/bitget-demo-trading/credential-actions/${id}`, { method: "GET" });
      return parseDemoTradingCredentialActionMetadata(result, { tenantId: bound.session.tenantId,
        accountId: id, authEpoch: bound.session.authEpoch });
    },
    async context(session: Session) {
      return parseActionProofContext(await request(session, "/v1/passkeys/context", { method: "GET" }), bound);
    },
    async request(session: Session, path: string, body: Readonly<Record<string, unknown>>) {
      if (!paths.has(path)) throw rejected();
      return request(session, path, { method: "POST", body: JSON.stringify(body) });
    },
    async credentialKey() {
      await live();
      const key = await credentialKey();
      if (!(key instanceof Uint8Array) || key.byteLength < 32 || key.byteLength > 4096) throw rejected();
      const snapshot = Uint8Array.from(key);
      await live();
      return snapshot;
    },
    async execute(token: string, body: string) {
      await live();
      const result = await execute(token, body);
      await live();
      return result;
    },
  });
}
