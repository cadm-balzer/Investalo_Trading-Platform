import type { Session } from "./auth.ts";
import {
  canonicalUuid, credentialInteger, deriveActionTarget, parseActionTarget, parseCredentialActionMetadata,
  type ActionTarget, type CredentialActionMetadata,
} from "./credential-action-contracts.ts";
import {
  canonicalBytes, exactObject, parsePasskeyContext, parsePasskeyRecord,
  type PasskeyContext, type PasskeyRecord,
} from "./passkey-enrollment-state.ts";
import { sameSecret, sha256 } from "./security.ts";
import type { PasskeyExpectedContext, VerifiedPasskeyAssertion } from "./passkey-verifier.ts";

export type ProofSession = Readonly<{ handle: string; session: Session; origin: string }>;
export type ActionProofAttempt = Readonly<{
  attempt_id: string; tenant_id: string; user_id: string; auth_epoch: number; rp_id: string;
  target: ActionTarget; metadata: CredentialActionMetadata; credential: PasskeyRecord;
  session_binding: string; challenge: string; confirmation_hash: string;
  prepared_at: number; expires_at: number; session_expires_at: number;
}>;
export type ActionProofGrant = Readonly<{
  grant_id: string; attempt_id: string; tenant_id: string; user_id: string; auth_epoch: number; rp_id: string;
  target: ActionTarget; metadata: CredentialActionMetadata; passkey_id: string; passkey_version: number;
  session_binding: string; confirmation_hash: string; checked_at: number;
  expires_at: number; session_expires_at: number;
}>;
export type PublicActionProofGrant = Readonly<{
  target: ActionTarget; accountName: string; checkedAt: number; expiresAt: number;
  confirmationToken: string; execution_enabled: false;
}>;
const rejected = () => new Error("PASSKEY_ACTION_PROOF_REJECTED");
const ATTEMPT_FIELDS = ["attempt_id", "tenant_id", "user_id", "auth_epoch", "rp_id", "target",
  "metadata", "credential", "session_binding", "challenge", "confirmation_hash",
  "prepared_at", "expires_at", "session_expires_at"] as const;
const GRANT_FIELDS = ["grant_id", "attempt_id", "tenant_id", "user_id", "auth_epoch", "rp_id", "target",
  "metadata", "passkey_id", "passkey_version", "session_binding", "confirmation_hash",
  "checked_at", "expires_at", "session_expires_at"] as const;

/** Snapshot trusted mutable inputs before any asynchronous operation. */
export function proofSession(value: ProofSession, now: number): ProofSession {
  canonicalBytes(value.handle, 32, 32);
  canonicalBytes(value.session.csrf, 32, 32);
  canonicalUuid(value.session.tenantId);
  credentialInteger(value.session.authEpoch);
  credentialInteger(now, 1);
  credentialInteger(value.session.oidcAuthTime, 1);
  credentialInteger(value.session.expiresAt, 1);
  if (value.session.expiresAt <= now || value.session.oidcAuthTime > now + 5 ||
    typeof value.session.issuer !== "string" || !value.session.issuer.startsWith("https://") ||
    typeof value.session.subject !== "string" || !value.session.subject ||
    value.session.subject.length > 255 || /[\u0000-\u001f\u007f]/.test(value.session.subject)) throw rejected();
  const origin = new URL(value.origin);
  if (origin.protocol !== "https:" || origin.origin !== value.origin || origin.username || origin.password ||
    !origin.hostname.includes(".") || /^[0-9.]+$/.test(origin.hostname)) throw rejected();
  return Object.freeze({ handle: value.handle, origin: value.origin, session: Object.freeze({ ...value.session }) });
}
export function actionProofBinding(value: ProofSession): string {
  return sha256(JSON.stringify(["passkey-action-proof-v1", value.handle, value.session.csrf,
    value.session.issuer, value.session.subject, value.session.tenantId, value.session.authEpoch,
    value.session.oidcAuthTime, value.origin, value.session.expiresAt]));
}
export function assertProofSession(expected: ProofSession, current: ProofSession, now: number): void {
  proofSession(expected, now); proofSession(current, now);
  if (!sameSecret(actionProofBinding(expected), actionProofBinding(current))) throw rejected();
}
function hex(value: unknown): string {
  if (typeof value !== "string" || !/^[a-f0-9]{64}$/.test(value)) throw rejected();
  return value;
}
export function confirmationHash(token: unknown): string {
  return sha256(canonicalBytes(token, 32, 32));
}
function activeContext(value: unknown, bound: ProofSession): PasskeyContext & { credential: PasskeyRecord } {
  const context = parsePasskeyContext(value, { tenantId: bound.session.tenantId,
    authEpoch: bound.session.authEpoch, rpId: new URL(bound.origin).hostname });
  if (!context.credential || context.credential.status !== "active" ||
    context.credential.enrollment_epoch !== context.auth_epoch) throw rejected();
  return context as PasskeyContext & { credential: PasskeyRecord };
}
export function parseActionProofContext(value: unknown, bound: ProofSession): PasskeyContext & { credential: PasskeyRecord } {
  return activeContext(value, bound);
}
function owner(item: Record<string, unknown>, bound: ProofSession) {
  const userId = canonicalUuid(item.user_id), rpId = new URL(bound.origin).hostname;
  if (item.tenant_id !== bound.session.tenantId || item.auth_epoch !== bound.session.authEpoch ||
    item.rp_id !== rpId || !sameSecret(hex(item.session_binding), actionProofBinding(bound)) ||
    credentialInteger(item.session_expires_at, 1) !== bound.session.expiresAt) throw rejected();
  return { tenantId: bound.session.tenantId, userId, rpId };
}
function targetAndMetadata(item: Record<string, unknown>, bound: ProofSession) {
  const target = parseActionTarget(item.target);
  const metadata = parseCredentialActionMetadata(item.metadata, {
    tenantId: bound.session.tenantId, accountId: target.platform_account_id, authEpoch: bound.session.authEpoch,
  });
  const derived = deriveActionTarget(metadata, target.action,
    target.action === "register" ? { newConnectionId: target.connection_id } : {});
  if (JSON.stringify(derived) !== JSON.stringify(target)) throw rejected();
  return { target, metadata };
}
function lifetime(started: number, expires: number, sessionExpires: number, now: number): void {
  for (const number of [started, expires, sessionExpires, now]) credentialInteger(number, 1);
  if (started > now || expires <= now || expires <= started || expires > started + 120 ||
    expires > sessionExpires || sessionExpires <= now) throw rejected();
}
export function parseActionProofAttempt(value: unknown, bound: ProofSession, now: number): ActionProofAttempt {
  const item = exactObject(value, ATTEMPT_FIELDS), owned = owner(item, bound);
  const credential = parsePasskeyRecord(item.credential, owned), frozen = targetAndMetadata(item, bound);
  if (credential.status !== "active" || credential.enrollment_epoch !== bound.session.authEpoch ||
    credential.storage_version === Number.MAX_SAFE_INTEGER) throw rejected();
  const prepared_at = credentialInteger(item.prepared_at, 1), expires_at = credentialInteger(item.expires_at, 1);
  const session_expires_at = credentialInteger(item.session_expires_at, 1);
  lifetime(prepared_at, expires_at, session_expires_at, now);
  return Object.freeze({ attempt_id: canonicalUuid(item.attempt_id), tenant_id: owned.tenantId,
    user_id: owned.userId, auth_epoch: bound.session.authEpoch, rp_id: owned.rpId, ...frozen, credential,
    session_binding: hex(item.session_binding), challenge: canonicalBytes(item.challenge, 32, 32),
    confirmation_hash: hex(item.confirmation_hash), prepared_at, expires_at, session_expires_at });
}
export function parseActionProofGrant(value: unknown, bound: ProofSession, now: number): ActionProofGrant {
  const item = exactObject(value, GRANT_FIELDS), owned = owner(item, bound), frozen = targetAndMetadata(item, bound);
  const checked_at = credentialInteger(item.checked_at, 1), expires_at = credentialInteger(item.expires_at, 1);
  const session_expires_at = credentialInteger(item.session_expires_at, 1);
  lifetime(checked_at, expires_at, session_expires_at, now);
  return Object.freeze({ grant_id: canonicalUuid(item.grant_id), attempt_id: canonicalUuid(item.attempt_id),
    tenant_id: owned.tenantId, user_id: owned.userId, auth_epoch: bound.session.authEpoch, rp_id: owned.rpId, ...frozen,
    passkey_id: canonicalUuid(item.passkey_id), passkey_version: credentialInteger(item.passkey_version, 2),
    session_binding: hex(item.session_binding), confirmation_hash: hex(item.confirmation_hash),
    checked_at, expires_at, session_expires_at });
}
export function assertAttemptLive(attempt: ActionProofAttempt, bound: ProofSession, context: unknown,
  metadataValue: unknown, now: number): void {
  parseActionProofAttempt(attempt, bound, now);
  const current = activeContext(context, bound);
  const metadata = parseCredentialActionMetadata(metadataValue, { tenantId: bound.session.tenantId,
    accountId: attempt.target.platform_account_id, authEpoch: bound.session.authEpoch });
  if (current.user_id !== attempt.user_id || JSON.stringify(current.credential) !== JSON.stringify(attempt.credential) ||
    JSON.stringify(metadata) !== JSON.stringify(attempt.metadata)) throw rejected();
}
export function assertGrantLive(grant: ActionProofGrant, bound: ProofSession, context: unknown,
  metadataValue: unknown, token: unknown, now: number): void {
  parseActionProofGrant(grant, bound, now);
  const current = activeContext(context, bound);
  const metadata = parseCredentialActionMetadata(metadataValue, { tenantId: bound.session.tenantId,
    accountId: grant.target.platform_account_id, authEpoch: bound.session.authEpoch });
  if (current.user_id !== grant.user_id || current.credential.passkey_id !== grant.passkey_id ||
    current.credential.storage_version !== grant.passkey_version ||
    JSON.stringify(metadata) !== JSON.stringify(grant.metadata) ||
    !sameSecret(grant.confirmation_hash, confirmationHash(token))) throw rejected();
}
export function assertionExpected(attempt: ActionProofAttempt, bound: ProofSession): PasskeyExpectedContext {
  const key = attempt.credential;
  return Object.freeze({ tenantId: attempt.tenant_id, userId: attempt.user_id,
    rpId: attempt.rp_id, origin: bound.origin, challenge: attempt.challenge,
    startedAt: attempt.prepared_at, expiresAt: attempt.expires_at,
    credential: Object.freeze({ tenantId: key.tenant_id, userId: key.user_id, id: key.credential_id,
      publicKey: new Uint8Array(Buffer.from(key.public_key, "base64url")), counter: key.sign_count,
      userHandle: key.user_handle }) });
}
export function assertVerifiedProof(verified: VerifiedPasskeyAssertion, attempt: ActionProofAttempt,
  now: number): void {
  credentialInteger(verified.checkedAt, 1); credentialInteger(verified.newCounter);
  if (verified.credentialId !== attempt.credential.credential_id ||
    verified.deviceType !== (attempt.credential.backup_eligible ? "multiDevice" : "singleDevice") ||
    typeof verified.backedUp !== "boolean" || verified.backedUp && !attempt.credential.backup_eligible ||
    verified.checkedAt < attempt.prepared_at || verified.checkedAt > now || verified.checkedAt >= attempt.expires_at ||
    verified.newCounter > 0xffff_ffff ||
    !(verified.newCounter > attempt.credential.sign_count ||
      verified.newCounter === 0 && attempt.credential.sign_count === 0)) throw rejected();
}
export function publicActionProofGrant(grant: ActionProofGrant, token: unknown): PublicActionProofGrant {
  if (!sameSecret(grant.confirmation_hash, confirmationHash(token))) throw rejected();
  return Object.freeze({ target: parseActionTarget(grant.target), accountName: grant.metadata.account.name,
    checkedAt: grant.checked_at, expiresAt: grant.expires_at,
    confirmationToken: token as string, execution_enabled: false });
}
