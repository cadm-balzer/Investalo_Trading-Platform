/**
 * Trusted-server orchestration only. Injected ports allow real crypto testing;
 * durable API claims/grants supply authority, never process memory or a TTL cache.
 * No browser route, broker credential input, order or execution is enabled here.
 */
import type { Session } from "./auth.ts";
import { deriveActionTarget, parseCredentialActionMetadata, type CredentialAction } from "./credential-action-contracts.ts";
import { canonicalUuid } from "./credential-action-contracts.ts";
import { canonicalBytes, exactObject } from "./passkey-enrollment-state.ts";
import { generatePasskeyAuthenticationOptions, verifyPasskeyAssertion } from "./passkey-verifier.ts";
import {
  actionProofBinding, assertAttemptLive, assertGrantLive, assertProofSession, assertVerifiedProof,
  assertionExpected, confirmationHash, parseActionProofAttempt, parseActionProofContext, parseActionProofGrant,
  proofSession, publicActionProofGrant, type ActionProofGrant, type ProofSession,
} from "./passkey-action-proof-state.ts";
import { sameSecret } from "./security.ts";

export type PasskeyActionPorts = Readonly<{
  current(): Promise<ProofSession>;
  context(session: Session): Promise<unknown>;
  metadata(session: Session, accountId: string): Promise<unknown>;
  request(session: Session, path: string, body: Readonly<Record<string, unknown>>): Promise<unknown>;
  now(): number;
  randomToken(): string;
  randomUuid(): string;
}>;
const PREFIX = "/v1/passkey-action-proofs";
const rejected = () => new Error("PASSKEY_ACTION_PROOF_REJECTED");

async function current(ports: PasskeyActionPorts, expected?: ProofSession): Promise<ProofSession> {
  const bound = proofSession(await ports.current(), ports.now());
  if (expected) assertProofSession(expected, bound, ports.now());
  return bound;
}
async function live(ports: PasskeyActionPorts, bound: ProofSession, accountId: string) {
  const [context, metadata] = await Promise.all([
    ports.context(bound.session), ports.metadata(bound.session, accountId),
  ]);
  await current(ports, bound);
  return { context, metadata };
}

export async function beginPasskeyActionProof(ports: PasskeyActionPorts, accountId: string, action: CredentialAction) {
  try {
    canonicalUuid(accountId);
    const bound = await current(ports), values = await live(ports, bound, accountId);
    const context = parseActionProofContext(values.context, bound);
    const metadata = parseCredentialActionMetadata(values.metadata, {
      tenantId: bound.session.tenantId, accountId, authEpoch: bound.session.authEpoch,
    });
    const target = deriveActionTarget(metadata, action,
      action === "register" ? { newConnectionId: canonicalUuid(ports.randomUuid()) } : {});
    const challenge = canonicalBytes(ports.randomToken(), 32, 32);
    const token = canonicalBytes(ports.randomToken(), 32, 32), hash = confirmationHash(token);
    const wire = await ports.request(bound.session, `${PREFIX}/prepare`, Object.freeze({
      target, session_binding: actionProofBinding(bound), challenge, confirmation_hash: hash,
      session_expires_at: bound.session.expiresAt,
    }));
    await current(ports, bound);
    const attempt = parseActionProofAttempt(wire, bound, ports.now());
    if (attempt.user_id !== context.user_id || attempt.challenge !== challenge ||
      !sameSecret(attempt.confirmation_hash, hash) || JSON.stringify(attempt.target) !== JSON.stringify(target) ||
      JSON.stringify(attempt.metadata) !== JSON.stringify(metadata) ||
      JSON.stringify(attempt.credential) !== JSON.stringify(context.credential)) throw rejected();
    const after = await live(ports, bound, accountId);
    assertAttemptLive(attempt, bound, after.context, after.metadata, ports.now());
    const options = await generatePasskeyAuthenticationOptions(assertionExpected(attempt, bound), ports.now());
    const completed = await live(ports, bound, accountId);
    assertAttemptLive(attempt, bound, completed.context, completed.metadata, ports.now());
    // Raw token belongs to this trusted caller's specific preview, not a bearer grant.
    return Object.freeze({ attempt_id: attempt.attempt_id, options, confirmation_token: token,
      preview: Object.freeze({ target: attempt.target, accountName: attempt.metadata.account.name,
        expiresAt: attempt.expires_at, execution_enabled: false as const }) });
  } catch { throw rejected(); }
}
export async function finishPasskeyActionProof(
  ports: PasskeyActionPorts, attemptId: string, response: unknown, confirmationToken: string,
) {
  try {
    canonicalUuid(attemptId);
    const bound = await current(ports);
    // API transaction commits the one-use claim before response parsing and crypto.
    const wire = await ports.request(bound.session, `${PREFIX}/claim`,
      Object.freeze({ attempt_id: attemptId, session_binding: actionProofBinding(bound) }));
    await current(ports, bound);
    const attempt = parseActionProofAttempt(wire, bound, ports.now());
    if (attempt.attempt_id !== attemptId || !sameSecret(attempt.confirmation_hash, confirmationHash(confirmationToken))) throw rejected();
    const values = await live(ports, bound, attempt.target.platform_account_id);
    assertAttemptLive(attempt, bound, values.context, values.metadata, ports.now());
    const verified = await verifyPasskeyAssertion(response, assertionExpected(attempt, bound));
    await current(ports, bound);
    assertVerifiedProof(verified, attempt, ports.now());
    const latest = await live(ports, bound, attempt.target.platform_account_id);
    assertAttemptLive(attempt, bound, latest.context, latest.metadata, ports.now());
    const finished = await ports.request(bound.session, `${PREFIX}/finish`, Object.freeze({
      attempt_id: attemptId, session_binding: actionProofBinding(bound),
      new_counter: verified.newCounter, backup_eligible: attempt.credential.backup_eligible,
      backed_up: verified.backedUp, checked_at: verified.checkedAt,
    }));
    await current(ports, bound);
    const grant = parseActionProofGrant(finished, bound, ports.now());
    if (grant.attempt_id !== attemptId || grant.user_id !== attempt.user_id ||
      grant.passkey_id !== attempt.credential.passkey_id ||
      grant.passkey_version !== attempt.credential.storage_version + 1 ||
      grant.checked_at !== verified.checkedAt || grant.expires_at > attempt.session_expires_at ||
      JSON.stringify(grant.target) !== JSON.stringify(attempt.target) ||
      JSON.stringify(grant.metadata) !== JSON.stringify(attempt.metadata) ||
      !sameSecret(grant.confirmation_hash, attempt.confirmation_hash)) throw rejected();
    const after = await live(ports, bound, grant.target.platform_account_id);
    assertGrantLive(grant, bound, after.context, after.metadata, confirmationToken, ports.now());
    return Object.freeze({ grant_id: grant.grant_id, grant: publicActionProofGrant(grant, confirmationToken) });
  } catch { throw rejected(); }
}
async function readGrant(ports: PasskeyActionPorts, bound: ProofSession, grantId: string, token: string): Promise<ActionProofGrant> {
  canonicalUuid(grantId);
  const wire = await ports.request(bound.session, `${PREFIX}/grant`,
    Object.freeze({ grant_id: grantId, session_binding: actionProofBinding(bound) }));
  await current(ports, bound);
  const grant = parseActionProofGrant(wire, bound, ports.now());
  if (grant.grant_id !== grantId || !sameSecret(grant.confirmation_hash, confirmationHash(token))) throw rejected();
  const after = await live(ports, bound, grant.target.platform_account_id);
  assertGrantLive(grant, bound, after.context, after.metadata, token, ports.now());
  return grant;
}
export async function readPasskeyActionGrant(ports: PasskeyActionPorts, grantId: string, confirmationToken: string) {
  try {
    const bound = await current(ports), grant = await readGrant(ports, bound, grantId, confirmationToken);
    return publicActionProofGrant(grant, confirmationToken);
  } catch { throw rejected(); }
}
export async function confirmPasskeyActionProof(ports: PasskeyActionPorts, grantId: string, confirmationToken: string) {
  try {
    const bound = await current(ports), grant = await readGrant(ports, bound, grantId, confirmationToken);
    // Compare this displayed preview before consume; a stale tab cannot burn the latest grant.
    const wire = await ports.request(bound.session, `${PREFIX}/confirm`, Object.freeze({
      grant_id: grantId, session_binding: actionProofBinding(bound), confirmation_hash: confirmationHash(confirmationToken),
    }));
    await current(ports, bound);
    const confirmation = exactObject(wire, ["status", "execution_enabled", "proof"]);
    if (confirmation.status !== "verified" || confirmation.execution_enabled !== false) throw rejected();
    const receipt = parseActionProofGrant(confirmation.proof, bound, ports.now());
    if (JSON.stringify(receipt) !== JSON.stringify(grant)) throw rejected();
    const after = await live(ports, bound, grant.target.platform_account_id);
    assertGrantLive(grant, bound, after.context, after.metadata, confirmationToken, ports.now());
    return Object.freeze({ status: "verified" as const, execution_enabled: false as const,
      action: grant.target.action, platform_account_id: grant.target.platform_account_id });
  } catch { throw rejected(); }
}
