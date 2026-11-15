/**
 * Injected single-process browser continuation adapter. These bounded handles
 * correlate own Demo core objects; durable015/016 consumption remains the
 * authority. Nothing is written to session storage, and a restart fails closed.
 */
import {
  canonicalUuid, demoCredentialAction, credentialInteger, type DemoCredentialAction,
} from "./demo-credential-action-contracts.ts";
import {
  buildBrowserCredentialBody, parseBrowserCredentialTriple, type CredentialTriple,
} from "./credential-browser-body.ts";
import {
  actionProofBinding, proofSession, type ProofSession,
} from "./passkey-action-proof-state.ts";
import { canonicalBytes, exactObject } from "./passkey-enrollment-state.ts";
import {
  beginDemoPasskeyCredentialFlow, executeDemoPasskeyCredentialFlow, finishDemoPasskeyCredentialFlow,
  type GrantedDemoPasskeyCredential, type DemoPasskeyCredentialConsent, type DemoPasskeyCredentialPorts,
  type PreparedDemoPasskeyCredential, type DemoSafeOnboardingResult,
} from "./demo-passkey-credential-flow.ts";
import { sameSecret } from "./security.ts";

export type DemoPasskeyCredentialBrowserOptions = Readonly<{
  portsFor(bound: ProofSession): DemoPasskeyCredentialPorts;
  now(): number;
  randomToken(): string;
  /** Mandatory trusted policy; flags alone never permit arbitrary key intake. */
  acceptCredentials(action: DemoCredentialAction, triple: CredentialTriple | undefined): boolean;
  capacity?: number;
  perSession?: number;
}>;
export type BrowserDemoCredentialPrepared = Readonly<{
  flow_token: string; options: PreparedDemoPasskeyCredential["options"];
  preview: PreparedDemoPasskeyCredential["preview"];
}>;
export type BrowserDemoCredentialGranted = Readonly<{
  flow_token: string;
  grant: Readonly<{
    target: GrantedDemoPasskeyCredential["grant"]["target"]; accountName: string;
    checkedAt: number; expiresAt: number; execution_enabled: false;
  }>;
}>;
export type DemoPasskeyCredentialBrowserFlow = Readonly<{
  start(bound: ProofSession, accountId: string, action: DemoCredentialAction,
    credentials?: unknown): Promise<BrowserDemoCredentialPrepared>;
  finish(bound: ProofSession, flowToken: string, response: unknown): Promise<BrowserDemoCredentialGranted>;
  execute(bound: ProofSession, flowToken: string, body: string,
    consent: DemoPasskeyCredentialConsent): Promise<DemoSafeOnboardingResult>;
  cancel(bound: ProofSession, flowToken: string): void;
}>;

type Lease = {
  binding: string; expiresAt: number; inFlight: boolean; token: string | undefined;
};
type Continuation = Readonly<{ lease: Lease; ports: DemoPasskeyCredentialPorts }> & (
  Readonly<{ phase: "prepared"; value: PreparedDemoPasskeyCredential }> |
  Readonly<{ phase: "granted"; value: GrantedDemoPasskeyCredential }>
);
const fail = () => new Error("DEMO_PASSKEY_CREDENTIAL_BROWSER_FLOW_REJECTED");
const PORT_FIELDS = ["current", "context", "metadata", "request", "now", "randomToken",
  "randomUuid", "credentialKey", "execute"] as const;

/** Copy callbacks only; trusted ports must never capture a request's raw triple. */
function portsSnapshot(value: DemoPasskeyCredentialPorts, assertLive: () => void): DemoPasskeyCredentialPorts {
  const item = exactObject(value, PORT_FIELDS);
  if (PORT_FIELDS.some(name => typeof item[name] !== "function")) throw fail();
  const current = item.current as DemoPasskeyCredentialPorts["current"];
  const wrapped: DemoPasskeyCredentialPorts = {
    context: value.context, metadata: value.metadata, request: value.request,
    now: value.now, randomToken: value.randomToken, randomUuid: value.randomUuid,
    credentialKey: value.credentialKey, execute: value.execute,
    async current() {
      assertLive();
      const value = await current();
      assertLive();
      return value;
    },
  };
  return Object.freeze(wrapped);
}

export function createDemoPasskeyCredentialBrowserFlow(
  options: DemoPasskeyCredentialBrowserOptions,
): DemoPasskeyCredentialBrowserFlow {
  if (!options || typeof options !== "object" || Array.isArray(options)) throw fail();
  try {
    exactObject(options, ["portsFor", "now", "randomToken", "acceptCredentials",
      ...(Object.hasOwn(options, "capacity") ? ["capacity"] : []),
      ...(Object.hasOwn(options, "perSession") ? ["perSession"] : [])]);
  } catch { throw fail(); }
  const { portsFor, now: clock, randomToken, acceptCredentials,
    capacity: providedCapacity, perSession: providedPerSession } = options;
  const capacity = providedCapacity ?? 32, perSession = providedPerSession ?? Math.min(2, capacity);
  if (typeof portsFor !== "function" || typeof clock !== "function" ||
    typeof randomToken !== "function" || typeof acceptCredentials !== "function" ||
    !Number.isSafeInteger(capacity) || capacity < 1 || capacity > 128 ||
    !Number.isSafeInteger(perSession) || perSession < 1 || perSession > 8 ||
    perSession > capacity) throw fail();
  // This store is deliberately distinct from the encrypted enrollment/session
  // store. Entries contain only correlation, safe core objects and callbacks.
  const continuations = new Map<string, Continuation>(), leases = new Set<Lease>();
  const now = () => credentialInteger(clock(), 1);
  function release(lease: Lease): void {
    if (lease.token !== undefined && continuations.get(lease.token)?.lease === lease) {
      continuations.delete(lease.token);
    }
    lease.token = undefined;
    leases.delete(lease);
  }
  function sweep(time: number): void {
    for (const lease of leases) {
      // Expiry does not release a still-running prepare, crypto or executor
      // promise. Otherwise repeated slow requests bypass admission limits.
      if (!lease.inFlight && lease.expiresAt <= time) release(lease);
    }
  }
  function fresh(excluded?: string): string {
    const value = canonicalBytes(randomToken(), 32, 32);
    if (value === excluded || continuations.has(value)) throw fail();
    return value;
  }
  function reserve(bound: ProofSession, time: number): Lease {
    sweep(time);
    const binding = actionProofBinding(bound);
    if (leases.size >= capacity ||
      [...leases].filter(lease => sameSecret(lease.binding, binding)).length >= perSession) throw fail();
    const lease = { binding, expiresAt: Math.min(time + 120, bound.session.expiresAt),
      inFlight: true, token: undefined };
    leases.add(lease);
    return lease;
  }
  function store(token: string, state: Continuation): void {
    if (continuations.has(token) || state.lease.expiresAt <= now()) throw fail();
    continuations.set(token, state);
    state.lease.token = token;
    state.lease.inFlight = false;
  }
  function take(bound: ProofSession, token: string, phase?: Continuation["phase"]): Continuation {
    const time = now(), expected = proofSession(bound, time);
    canonicalBytes(token, 32, 32); sweep(time);
    const state = continuations.get(token);
    if (!state || (phase !== undefined && state.phase !== phase) ||
      !sameSecret(state.lease.binding, actionProofBinding(expected))) throw fail();
    // A foreign session cannot burn a live handle. Matching owner consumes it
    // synchronously before the first subsequent await or crypto operation.
    continuations.delete(token);
    state.lease.token = undefined;
    state.lease.inFlight = true;
    return state;
  }
  return Object.freeze({
    async start(bound, accountId, action, credentials) {
      let lease: Lease | undefined;
      try {
        const time = now(), expected = proofSession(bound, time);
        canonicalUuid(accountId); demoCredentialAction(action);
        const triple = action === "revoke" ? undefined : parseBrowserCredentialTriple(credentials);
        if (action === "revoke" && credentials !== undefined ||
          acceptCredentials(action, triple) !== true) throw fail();
        // Admission precedes every provider/API await. Raw triple is confined
        // to this call and its synchronous body factory, never the continuation.
        lease = reserve(expected, time);
        const reserved = lease;
        const ports = portsSnapshot(portsFor(expected), () => {
          if (reserved.expiresAt <= now()) throw fail();
        });
        const prepared = await beginDemoPasskeyCredentialFlow(ports, expected, accountId, action,
          target => buildBrowserCredentialBody(target, triple));
        lease.expiresAt = Math.min(lease.expiresAt, prepared.preview.expiresAt);
        const token = fresh();
        store(token, Object.freeze({ lease, ports, phase: "prepared", value: prepared }));
        return Object.freeze({ flow_token: token, options: prepared.options,
          preview: Object.freeze({ ...prepared.preview, expiresAt: lease.expiresAt }) });
      } catch {
        if (lease) release(lease);
        throw fail();
      }
    },
    async finish(bound, flowToken, response) {
      let state: Continuation | undefined;
      try {
        state = take(bound, flowToken, "prepared");
        if (state.phase !== "prepared") throw fail();
        const granted = await finishDemoPasskeyCredentialFlow(state.ports,
          proofSession(bound, now()), state.value, response);
        state.lease.expiresAt = Math.min(state.lease.expiresAt, granted.grant.expiresAt);
        const token = fresh(flowToken);
        store(token, Object.freeze({ lease: state.lease, ports: state.ports,
          phase: "granted", value: granted }));
        return Object.freeze({ flow_token: token, grant: Object.freeze({
          target: granted.grant.target, accountName: granted.grant.accountName,
          checkedAt: granted.grant.checkedAt, expiresAt: state.lease.expiresAt,
          execution_enabled: false as const,
        }) });
      } catch {
        if (state) release(state.lease);
        throw fail();
      }
    },
    async execute(bound, flowToken, body, consent) {
      let state: Continuation | undefined;
      try {
        state = take(bound, flowToken, "granted");
        if (state.phase !== "granted") throw fail();
        return await executeDemoPasskeyCredentialFlow(state.ports,
          proofSession(bound, now()), state.value, body, consent);
      } catch { throw fail(); }
      finally { if (state) release(state.lease); }
    },
    cancel(bound, flowToken) {
      try { release(take(bound, flowToken).lease); }
      catch { throw fail(); }
    },
  });
}
