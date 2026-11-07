import type { Principal } from "./internal-token.ts";
import { deriveActionTarget, parseActionTarget, type ActionTarget, type CredentialActionMetadata } from "./credential-action-contracts.ts";
import { sameSecret, sha256 } from "./security.ts";

// Preparatory primitives only. OIDC auth_time + amr=mfa cannot prove a newly
// used second factor in Authelia 4.39.28. The server adapter stays disabled.
export const CREDENTIAL_STEP_UP_AVAILABLE = false;
export function requireCredentialStepUp(): void {
  throw new Error("FRESH_FACTOR_UNAVAILABLE");
}

export type BoundSession = {
  sessionHash: string; csrfHash: string; issuer: string; subject: string;
  tenantId: string; authEpoch: number; expiresAt: number;
};
export type StepUpAttempt = {
  session: BoundSession; target: ActionTarget; accountName: string; binding: string;
  nonce: string; verifier: string; startedAt: number; expiresAt: number;
};
export type FreshIdentity = { subject: string; issuer: string; authTime: number; amr: string[]; expiresAt: number };
export type CredentialGrant = {
  session: BoundSession; target: ActionTarget; accountName: string; startedAt: number;
  identity: FreshIdentity; expiresAt: number; confirmationToken: string;
};
export type PublicCredentialGrant = Pick<CredentialGrant, "target" | "accountName" | "expiresAt" | "confirmationToken">;

export function bindSession(handle: string, session: Principal & { csrf: string; expiresAt: number }): BoundSession {
  if (!/^[A-Za-z0-9_-]{43}$/.test(handle) || !session.tenantId || session.authEpoch === undefined) {
    throw new Error("STEP_UP_REJECTED");
  }
  return { sessionHash: sha256(handle), csrfHash: sha256(session.csrf), issuer: session.issuer,
    subject: session.subject, tenantId: session.tenantId, authEpoch: session.authEpoch, expiresAt: session.expiresAt };
}

export function assertSession(record: BoundSession, current: BoundSession, now: number): void {
  if (!Number.isSafeInteger(now) || !Number.isSafeInteger(record.expiresAt) || !Number.isSafeInteger(current.expiresAt) ||
    record.expiresAt <= now || current.expiresAt <= now ||
    ["sessionHash", "csrfHash", "issuer", "subject", "tenantId", "authEpoch"].some(
      field => record[field as keyof BoundSession] !== current[field as keyof BoundSession])) {
    throw new Error("STEP_UP_REJECTED");
  }
}

function assertTarget(target: ActionTarget, metadata: CredentialActionMetadata, accountName: string): void {
  const candidate = deriveActionTarget(metadata, target.action,
    target.action === "register" ? { newConnectionId: target.connection_id } : {});
  if (JSON.stringify(parseActionTarget(target)) !== JSON.stringify(candidate) || accountName !== metadata.account.name) {
    throw new Error("STEP_UP_CHANGED");
  }
}

function assertFresh(identity: FreshIdentity, startedAt: number, session: BoundSession, now: number): void {
  if (identity.subject !== session.subject || identity.issuer !== session.issuer ||
    !Number.isSafeInteger(startedAt) || startedAt < now - 300 || startedAt > now + 5 ||
    !Number.isSafeInteger(identity.authTime) || identity.authTime < startedAt ||
    identity.authTime < now - 120 || identity.authTime > now + 5 ||
    !Number.isSafeInteger(identity.expiresAt) || identity.expiresAt <= now ||
    !Array.isArray(identity.amr) || identity.amr.length < 1 || identity.amr.length > 8 ||
    identity.amr.some(value => typeof value !== "string" || !/^[a-z0-9_-]{1,32}$/.test(value)) ||
    new Set(identity.amr).size !== identity.amr.length || !identity.amr.includes("mfa")) {
    throw new Error("STEP_UP_REJECTED");
  }
}

export function makeCredentialGrant(attempt: StepUpAttempt, current: BoundSession,
  identity: FreshIdentity, metadata: CredentialActionMetadata, now: number, confirmationToken: string): CredentialGrant {
  if (!/^[A-Za-z0-9_-]{43}$/.test(confirmationToken)) throw new Error("STEP_UP_REJECTED");
  assertSession(attempt.session, current, now);
  if (attempt.expiresAt <= now) throw new Error("STEP_UP_REJECTED");
  assertFresh(identity, attempt.startedAt, current, now);
  assertTarget(attempt.target, metadata, attempt.accountName);
  if (metadata.auth_epoch !== current.authEpoch || metadata.tenant_id !== current.tenantId) throw new Error("STEP_UP_REJECTED");
  const expiresAt = Math.min(now + 120, identity.authTime + 120, identity.expiresAt, current.expiresAt, attempt.session.expiresAt);
  if (expiresAt <= now) throw new Error("STEP_UP_REJECTED");
  return { session: { ...current }, target: parseActionTarget(attempt.target), accountName: metadata.account.name,
    startedAt: attempt.startedAt, identity: { ...identity, amr: [...identity.amr] }, expiresAt, confirmationToken };
}

export function assertCredentialConfirmation(grant: CredentialGrant, confirmationToken: string): void {
  if (!/^[A-Za-z0-9_-]{43}$/.test(confirmationToken) ||
    !sameSecret(grant.confirmationToken, confirmationToken)) throw new Error("STEP_UP_REJECTED");
}

export function assertCredentialGrant(grant: CredentialGrant, current: BoundSession,
  metadata: CredentialActionMetadata, now = Math.floor(Date.now() / 1000)): void {
  assertSession(grant.session, current, now);
  assertFresh(grant.identity, grant.startedAt, current, now);
  if (!Number.isSafeInteger(grant.expiresAt) || grant.expiresAt <= now ||
    grant.expiresAt > grant.identity.authTime + 120 || grant.expiresAt > grant.identity.expiresAt ||
    grant.expiresAt > grant.session.expiresAt || metadata.tenant_id !== current.tenantId ||
    metadata.auth_epoch !== current.authEpoch) throw new Error("STEP_UP_REJECTED");
  assertTarget(grant.target, metadata, grant.accountName);
}

export function publicCredentialGrant(grant: CredentialGrant): PublicCredentialGrant {
  return { target: parseActionTarget(grant.target), accountName: grant.accountName,
    expiresAt: grant.expiresAt, confirmationToken: grant.confirmationToken };
}
