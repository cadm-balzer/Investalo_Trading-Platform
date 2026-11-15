/**
 * Private injected orchestration. Only durable015 preparation/consent and the
 * private executor confer authority; the opaque handles merely correlate this
 * trusted caller's preview. No HTTP route, credential intake or runtime key.
 * Raw bodies, signing keys and signed assertions never enter handle storage.
 */
import { createHash } from "node:crypto";
import {
  canonicalUuid, credentialInteger, deriveDemoActionTarget, parseDemoCredentialActionMetadata,
  type DemoActionTarget, type DemoCredentialAction,
} from "./demo-credential-action-contracts.ts";
import type { PasskeyActionPorts } from "./passkey-action-proof.ts";
import {
  actionProofBinding, assertAttemptLive, assertGrantLive, assertProofSession, assertVerifiedProof,
  assertionExpected, confirmationHash, parseDemoActionProofAttempt, parseActionProofContext,
  parseDemoActionProofGrant, proofSession, publicDemoActionProofGrant,
  type DemoActionProofAttempt, type DemoActionProofGrant, type ProofSession,
} from "./demo-passkey-action-proof-state.ts";
import {
  createDemoPasskeyCredentialActionToken, parseDemoPasskeyCredentialAuthorization,
  validateDemoPasskeyCredentialBody, type DemoPasskeyCredentialContext,
} from "./demo-passkey-credential-token.ts";
import { canonicalBytes, exactObject, type PasskeyRecord } from "./passkey-enrollment-state.ts";
import { generatePasskeyAuthenticationOptions, verifyPasskeyAssertion } from "./passkey-verifier.ts";
import { sameSecret } from "./security.ts";

export type DemoPasskeyCredentialPorts = PasskeyActionPorts & Readonly<{
  /** Dedicated credential assertion identity, separate from API/session keys. */
  credentialKey(): Promise<Uint8Array>;
  /** Trusted private executor; it verifies/consumes before reading or probing. */
  execute(token: string, unchangedBody: string): Promise<unknown>;
}>;
export type DemoPasskeyCredentialConsent = Readonly<{ kind: "demo-credential-write"; confirmed: true }>;
export type DemoSafeOnboardingResult = Readonly<{
  connection_id: string; credential_revision: 1; storage_version: number;
  status: "active" | "revoked";
}>;
export type PreparedDemoPasskeyCredential = Readonly<{
  authorization_id: string; attempt_id: string;
  options: Awaited<ReturnType<typeof generatePasskeyAuthenticationOptions>>;
  confirmation_token: string;
  preview: Readonly<{ target: DemoActionTarget; accountName: string; expiresAt: number; execution_enabled: false }>;
}>;
export type GrantedDemoPasskeyCredential = Readonly<{
  authorization_id: string; grant_id: string;
  grant: ReturnType<typeof publicDemoActionProofGrant>;
}>;
type PreparedState = Readonly<{
  ports: DemoPasskeyCredentialPorts; bound: ProofSession; attempt: DemoActionProofAttempt;
  authorizationId: string; metadataHash: string; bodyHash: string; confirmationToken: string;
}>;
type GrantedState = PreparedState & Readonly<{ grant: DemoActionProofGrant; factor: PasskeyRecord }>;
const preparedStates = new WeakMap<PreparedDemoPasskeyCredential, PreparedState>();
const grantedStates = new WeakMap<GrantedDemoPasskeyCredential, GrantedState>();
const PURPOSE = "/v1/bitget-demo/passkey-authorizations", PROOF = "/v1/bitget-demo/passkey-authorizations";
const rejected = () => new Error("DEMO_PASSKEY_CREDENTIAL_FLOW_REJECTED");
const equal = (left: unknown, right: unknown) => JSON.stringify(left) === JSON.stringify(right);
function digest(value: unknown): string {
  if (typeof value !== "string" || !/^[a-f0-9]{64}$/.test(value)) throw rejected();
  return value;
}
function bodyHash(body: string, target: DemoActionTarget): string {
  return createHash("sha256").update(validateDemoPasskeyCredentialBody(body, target)).digest("hex");
}
async function current(ports: DemoPasskeyCredentialPorts, expected: ProofSession): Promise<void> {
  const value = proofSession(await ports.current(), ports.now());
  assertProofSession(expected, value, ports.now());
}
async function live(ports: DemoPasskeyCredentialPorts, bound: ProofSession, accountId: string) {
  const [context, metadata] = await Promise.all([
    ports.context(bound.session), ports.metadata(bound.session, accountId),
  ]);
  await current(ports, bound);
  return { context, metadata };
}
async function request(ports: DemoPasskeyCredentialPorts, bound: ProofSession, path: string,
  body: Readonly<Record<string, unknown>>): Promise<unknown> {
  await current(ports, bound);
  const result = await ports.request(bound.session, path, body);
  await current(ports, bound);
  return result;
}
function contextFor(state: PreparedState): DemoPasskeyCredentialContext {
  const session = state.bound.session;
  return Object.freeze({ tenantId: session.tenantId, userId: state.attempt.user_id,
    subject: session.subject, authEpoch: session.authEpoch, oidcIssuer: session.issuer,
    oidcAuthTime: session.oidcAuthTime, origin: state.bound.origin,
    sessionBinding: actionProofBinding(state.bound), sessionExpiresAt: session.expiresAt });
}
async function liveGrant(state: GrantedState): Promise<void> {
  const values = await live(state.ports, state.bound, state.grant.target.platform_account_id);
  assertGrantLive(state.grant, state.bound, values.context, values.metadata,
    state.confirmationToken, state.ports.now());
  const context = parseActionProofContext(values.context, state.bound);
  if (!equal(context.credential, state.factor)) throw rejected();
}
function safeResult(value: unknown, target: DemoActionTarget): DemoSafeOnboardingResult {
  const item = exactObject(value, ["connection_id", "credential_revision", "storage_version", "status"]);
  const revision = 1;
  const storage = target.action === "register" ? 1 : target.expected_storage + 1;
  const status = target.action === "revoke" ? "revoked" : "active";
  if (canonicalUuid(item.connection_id) !== target.connection_id ||
    credentialInteger(item.credential_revision, 1) !== revision ||
    credentialInteger(item.storage_version, 1) !== storage || item.status !== status) throw rejected();
  return Object.freeze({ connection_id: target.connection_id,
    credential_revision: revision, storage_version: storage, status });
}

/**
 * The synchronous trusted factory can capture the generated target in caller
 * memory. It must preserve that exact body until explicit credential consent.
 */
export async function beginDemoPasskeyCredentialFlow(
  ports: DemoPasskeyCredentialPorts, expectedSession: ProofSession, accountId: string,
  action: DemoCredentialAction, bodyForTarget: (target: DemoActionTarget) => string,
): Promise<PreparedDemoPasskeyCredential> {
  try {
    const bound = proofSession(expectedSession, ports.now());
    canonicalUuid(accountId);
    if (typeof bodyForTarget !== "function") throw rejected();
    await current(ports, bound);
    const values = await live(ports, bound, accountId);
    const context = parseActionProofContext(values.context, bound);
    const metadata = parseDemoCredentialActionMetadata(values.metadata, {
      tenantId: bound.session.tenantId, accountId, authEpoch: bound.session.authEpoch,
    });
    const target = deriveDemoActionTarget(metadata, action,
      action === "register" ? { newConnectionId: canonicalUuid(ports.randomUuid()) } : {});
    const frozenBodyHash = bodyHash(bodyForTarget(target), target);
    const challenge = canonicalBytes(ports.randomToken(), 32, 32);
    const token = canonicalBytes(ports.randomToken(), 32, 32), hash = confirmationHash(token);
    // No raw body or credential triple is passed to the API.
    const wire = exactObject(await request(ports, bound, `${PURPOSE}/prepare`, Object.freeze({
      target, session_binding: actionProofBinding(bound), challenge, confirmation_hash: hash,
      session_expires_at: bound.session.expiresAt, body_sha256: frozenBodyHash,
    })), ["authorization_id", "metadata_sha256", "attempt"]);
    const authorizationId = canonicalUuid(wire.authorization_id), metadataHash = digest(wire.metadata_sha256);
    const attempt = parseDemoActionProofAttempt(wire.attempt, bound, ports.now());
    if (authorizationId === attempt.attempt_id || attempt.user_id !== context.user_id ||
      attempt.challenge !== challenge || !sameSecret(attempt.confirmation_hash, hash) ||
      !equal(attempt.target, target) || !equal(attempt.metadata, metadata) ||
      !equal(attempt.credential, context.credential)) throw rejected();
    const after = await live(ports, bound, accountId);
    assertAttemptLive(attempt, bound, after.context, after.metadata, ports.now());
    const options = await generatePasskeyAuthenticationOptions(assertionExpected(attempt, bound), ports.now());
    await current(ports, bound);
    const completed = await live(ports, bound, accountId);
    assertAttemptLive(attempt, bound, completed.context, completed.metadata, ports.now());
    const result: PreparedDemoPasskeyCredential = Object.freeze({
      authorization_id: authorizationId, attempt_id: attempt.attempt_id, options,
      confirmation_token: token, preview: Object.freeze({ target: attempt.target,
        accountName: attempt.metadata.account.name, expiresAt: attempt.expires_at, execution_enabled: false }),
    });
    preparedStates.set(result, Object.freeze({ ports, bound, attempt, authorizationId,
      metadataHash, bodyHash: frozenBodyHash, confirmationToken: token }));
    return result;
  } catch { throw rejected(); }
}

export async function finishDemoPasskeyCredentialFlow(
  ports: DemoPasskeyCredentialPorts, expectedSession: ProofSession,
  prepared: PreparedDemoPasskeyCredential, response: unknown,
): Promise<GrantedDemoPasskeyCredential> {
  try {
    const bound = proofSession(expectedSession, ports.now()), state = preparedStates.get(prepared);
    if (!state || state.ports !== ports) throw rejected();
    assertProofSession(state.bound, bound, ports.now());
    // A local retry cannot replay an uncertain API commit; durable claim is the
    // authority even across separate processes.
    preparedStates.delete(prepared);
    await current(ports, bound);
    const wire = await request(ports, bound, `${PROOF}/claim`, Object.freeze({
      attempt_id: state.attempt.attempt_id, session_binding: actionProofBinding(bound),
    }));
    const attempt = parseDemoActionProofAttempt(wire, bound, ports.now());
    if (!equal(attempt, state.attempt)) throw rejected();
    const values = await live(ports, bound, attempt.target.platform_account_id);
    assertAttemptLive(attempt, bound, values.context, values.metadata, ports.now());
    const verified = await verifyPasskeyAssertion(response, assertionExpected(attempt, bound));
    await current(ports, bound);
    assertVerifiedProof(verified, attempt, ports.now());
    const latest = await live(ports, bound, attempt.target.platform_account_id);
    assertAttemptLive(attempt, bound, latest.context, latest.metadata, ports.now());
    const finished = await request(ports, bound, `${PROOF}/finish`, Object.freeze({
      attempt_id: attempt.attempt_id, session_binding: actionProofBinding(bound),
      new_counter: verified.newCounter, backup_eligible: attempt.credential.backup_eligible,
      backed_up: verified.backedUp, checked_at: verified.checkedAt,
    }));
    const grant = parseDemoActionProofGrant(finished, bound, ports.now());
    if (grant.grant_id === state.authorizationId || grant.grant_id === attempt.attempt_id ||
      grant.attempt_id !== attempt.attempt_id || grant.user_id !== attempt.user_id ||
      grant.passkey_id !== attempt.credential.passkey_id ||
      grant.passkey_version !== attempt.credential.storage_version + 1 ||
      grant.checked_at !== verified.checkedAt || !equal(grant.target, attempt.target) ||
      !equal(grant.metadata, attempt.metadata) ||
      !sameSecret(grant.confirmation_hash, attempt.confirmation_hash)) throw rejected();
    const after = await live(ports, bound, grant.target.platform_account_id);
    assertGrantLive(grant, bound, after.context, after.metadata, state.confirmationToken, ports.now());
    const factor = parseActionProofContext(after.context, bound).credential;
    const expectedFactor = Object.freeze({ ...attempt.credential, sign_count: verified.newCounter,
      backed_up: verified.backedUp, storage_version: attempt.credential.storage_version + 1 });
    if (!equal(factor, expectedFactor)) throw rejected();
    const result: GrantedDemoPasskeyCredential = Object.freeze({ authorization_id: state.authorizationId,
      grant_id: grant.grant_id, grant: publicDemoActionProofGrant(grant, state.confirmationToken) });
    grantedStates.set(result, Object.freeze({ ...state, grant, factor }));
    return result;
  } catch { throw rejected(); }
}

export async function executeDemoPasskeyCredentialFlow(
  ports: DemoPasskeyCredentialPorts, expectedSession: ProofSession, granted: GrantedDemoPasskeyCredential,
  unchangedBody: string, consent: DemoPasskeyCredentialConsent,
): Promise<DemoSafeOnboardingResult> {
  try {
    const bound = proofSession(expectedSession, ports.now()), state = grantedStates.get(granted);
    const purpose = exactObject(consent, ["kind", "confirmed"]);
    if (!state || state.ports !== ports || purpose.kind !== "demo-credential-write" || purpose.confirmed !== true ||
      !sameSecret(bodyHash(unchangedBody, state.grant.target), state.bodyHash)) throw rejected();
    assertProofSession(state.bound, bound, ports.now());
    grantedStates.delete(granted);
    await current(ports, bound);
    await liveGrant(state);
    const grant = parseDemoActionProofGrant(await request(ports, bound, `${PROOF}/grant`, Object.freeze({
      grant_id: state.grant.grant_id, session_binding: actionProofBinding(bound),
    })), bound, ports.now());
    if (!equal(grant, state.grant)) throw rejected();
    await liveGrant(state);
    const wire = exactObject(await request(ports, bound, `${PURPOSE}/authorize`, Object.freeze({
      authorization_id: state.authorizationId, grant_id: grant.grant_id,
      session_binding: actionProofBinding(bound), confirmation_hash: confirmationHash(state.confirmationToken),
    })), ["status", "execution_enabled", "authorization"]);
    if (wire.status !== "authorized" || wire.execution_enabled !== false) throw rejected();
    const context = contextFor(state);
    const receipt = parseDemoPasskeyCredentialAuthorization(wire.authorization, context, unchangedBody, ports.now());
    if (receipt.authorization_id !== state.authorizationId || receipt.proof_id !== state.attempt.attempt_id ||
      receipt.grant_id !== grant.grant_id || receipt.passkey_id !== grant.passkey_id ||
      receipt.passkey_version !== grant.passkey_version || receipt.prepared_at !== state.attempt.prepared_at ||
      receipt.checked_at !== grant.checked_at || receipt.expires_at !== grant.expires_at ||
      !equal(receipt.target, grant.target) || !sameSecret(receipt.metadata_sha256, state.metadataHash) ||
      !sameSecret(receipt.body_sha256, state.bodyHash)) throw rejected();
    //008 consent consumed007 grant. Compare saved proof with current identity/
    // factor/metadata, never call007 grant/confirm again.
    await liveGrant(state);
    const receivedKey = await ports.credentialKey();
    if (!(receivedKey instanceof Uint8Array)) throw rejected();
    const key = new Uint8Array(receivedKey);
    await current(ports, bound);
    await liveGrant(state);
    const token = await createDemoPasskeyCredentialActionToken({
      key, context, authorization: receipt, body: unchangedBody, clock: () => ports.now(),
    });
    await current(ports, bound);
    await liveGrant(state);
    parseDemoPasskeyCredentialAuthorization(receipt, context, unchangedBody, ports.now());
    const executed = await ports.execute(token, unchangedBody);
    await current(ports, bound);
    const result = safeResult(executed, grant.target);
    const after = await live(ports, bound, grant.target.platform_account_id);
    const actor = parseActionProofContext(after.context, bound);
    const metadata = parseDemoCredentialActionMetadata(after.metadata, {
      tenantId: bound.session.tenantId, accountId: grant.target.platform_account_id,
      authEpoch: bound.session.authEpoch,
    });
    // The expected credential mutation changes connection metadata. Verify its
    // exact resulting state without comparing it to the old prewrite snapshot.
    if (actor.user_id !== state.attempt.user_id || !equal(actor.credential, state.factor) ||
      !equal(metadata.account, grant.metadata.account) ||
      !equal(metadata.connection, result)) throw rejected();
    return result;
  } catch { throw rejected(); }
}
