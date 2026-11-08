/**
 * Trusted BFF enrollment orchestration. API ticket claims and the attempt
 * store supply single-use authority; fmt=none registration is only a candidate.
 */
import type { Session } from "./auth.ts";
import { canonicalUuid, credentialInteger } from "./credential-action-contracts.ts";
import {
  assertEnrollment, canonicalBytes, enrollmentBinding, exactObject,
  parsePasskeyContext, parsePasskeyRecord, type EnrollmentAttempt, type PasskeyContext,
} from "./passkey-enrollment-state.ts";
import {
  generatePasskeyRegistrationOptions, verifyPasskeyRegistration, type RegistrationExpectedContext,
} from "./passkey-registration.ts";
import { sameSecret } from "./security.ts";

export type EnrollmentSession = Readonly<{ handle: string; session: Session; origin: string }>;
export type StoredEnrollmentAttempt = EnrollmentAttempt & Readonly<{ sessionExpiresAt: number }>;
export type EnrollmentFlowPorts = Readonly<{
  current(): Promise<EnrollmentSession | null>;
  context(session: Session): Promise<unknown>;
  request(session: Session, path: string, body: Readonly<Record<string, unknown>>): Promise<unknown>;
  attempts: Readonly<{
    put(id: string, attempt: StoredEnrollmentAttempt): Promise<void>;
    get(id: string): Promise<unknown>;
    consume(id: string): Promise<unknown>;
  }>;
  now(): number;
  randomToken(): string;
}>;
const rejected = () => new Error("PASSKEY_ENROLLMENT_REJECTED");
const FIELDS = ["tenantId", "userId", "authEpoch", "rpId", "origin", "claimId",
  "userHandle", "binding", "challenge", "startedAt", "expiresAt", "sessionExpiresAt"] as const;

function snapshot(value: EnrollmentSession | null, now: number): EnrollmentSession {
  if (!value) throw rejected();
  canonicalBytes(value.handle, 32, 32); canonicalBytes(value.session.csrf, 32, 32);
  canonicalUuid(value.session.tenantId); credentialInteger(value.session.authEpoch);
  credentialInteger(now, 1); credentialInteger(value.session.oidcAuthTime, 1);
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
async function current(ports: EnrollmentFlowPorts, expected?: EnrollmentSession): Promise<EnrollmentSession> {
  const bound = snapshot(await ports.current(), ports.now());
  if (expected && (bound.origin !== expected.origin || bound.session.expiresAt !== expected.session.expiresAt ||
    !sameSecret(enrollmentBinding(bound.handle, bound.session), enrollmentBinding(expected.handle, expected.session)))) {
    throw rejected();
  }
  return bound;
}
async function context(ports: EnrollmentFlowPorts, bound: EnrollmentSession): Promise<PasskeyContext> {
  const wire = await ports.context(bound.session);
  await current(ports, bound);
  return parsePasskeyContext(wire, { tenantId: bound.session.tenantId,
    authEpoch: bound.session.authEpoch, rpId: new URL(bound.origin).hostname });
}
function attempt(value: unknown): StoredEnrollmentAttempt {
  const item = exactObject(value, FIELDS);
  if (typeof item.origin !== "string" || typeof item.rpId !== "string" ||
    typeof item.binding !== "string" || !/^[a-f0-9]{64}$/.test(item.binding)) throw rejected();
  const origin = new URL(item.origin);
  if (origin.protocol !== "https:" || origin.origin !== item.origin || origin.hostname !== item.rpId ||
    origin.username || origin.password) throw rejected();
  return Object.freeze({ tenantId: canonicalUuid(item.tenantId), userId: canonicalUuid(item.userId),
    authEpoch: credentialInteger(item.authEpoch), rpId: item.rpId, origin: item.origin,
    claimId: canonicalUuid(item.claimId), userHandle: canonicalBytes(item.userHandle, 32, 32),
    binding: item.binding, challenge: canonicalBytes(item.challenge, 32, 32),
    startedAt: credentialInteger(item.startedAt, 1), expiresAt: credentialInteger(item.expiresAt, 1),
    sessionExpiresAt: credentialInteger(item.sessionExpiresAt, 1) });
}
function live(value: StoredEnrollmentAttempt, bound: EnrollmentSession, state: PasskeyContext, now: number): void {
  if (value.origin !== bound.origin || value.sessionExpiresAt !== bound.session.expiresAt ||
    value.expiresAt > value.sessionExpiresAt) throw rejected();
  assertEnrollment(value, bound.handle, bound.session, state, now);
}
function registrationContext(value: StoredEnrollmentAttempt): RegistrationExpectedContext {
  return Object.freeze({ tenantId: value.tenantId, userId: value.userId, rpId: value.rpId, origin: value.origin,
    challenge: value.challenge, userHandle: value.userHandle, startedAt: value.startedAt, expiresAt: value.expiresAt });
}

export async function beginEnrollmentFlow(ports: EnrollmentFlowPorts, ticket: unknown) {
  try {
    const token = canonicalBytes(ticket, 32, 32), bound = await current(ports);
    const initial = await context(ports, bound);
    if (initial.credential !== null) throw rejected();
    const binding = enrollmentBinding(bound.handle, bound.session);
    // A successful request receipt follows an API transaction committing the claim.
    const claim = exactObject(await ports.request(bound.session, "/v1/passkeys/enrollment/claim",
      Object.freeze({ token, session_binding: binding })),
    ["claim_id", "user_handle", "expires_at", "tenant_id", "user_id", "auth_epoch", "rp_id"]);
    await current(ports, bound);
    if (claim.tenant_id !== initial.tenant_id || claim.user_id !== initial.user_id ||
      credentialInteger(claim.auth_epoch) !== initial.auth_epoch || claim.rp_id !== initial.rp_id ||
      typeof claim.expires_at !== "string" || claim.expires_at.length > 64) throw rejected();
    const startedAt = ports.now();
    const expiresAt = Math.min(Math.floor(Date.parse(claim.expires_at) / 1000), startedAt + 120,
      bound.session.expiresAt);
    if (!Number.isSafeInteger(expiresAt) || expiresAt <= startedAt) throw rejected();
    const saved = attempt({ tenantId: initial.tenant_id, userId: initial.user_id, authEpoch: initial.auth_epoch,
      rpId: initial.rp_id, origin: bound.origin, claimId: claim.claim_id, userHandle: claim.user_handle,
      binding, challenge: canonicalBytes(ports.randomToken(), 32, 32), startedAt, expiresAt,
      sessionExpiresAt: bound.session.expiresAt });
    const options = await generatePasskeyRegistrationOptions(registrationContext(saved), ports.now());
    live(saved, bound, await context(ports, bound), ports.now());
    const id = canonicalBytes(ports.randomToken(), 32, 32);
    await ports.attempts.put(id, saved);
    live(saved, bound, await context(ports, bound), ports.now());
    return Object.freeze({ attempt_id: id, options });
  } catch { throw rejected(); }
}

export async function finishEnrollmentFlow(ports: EnrollmentFlowPorts, id: unknown, response: unknown): Promise<void> {
  try {
    const attemptId = canonicalBytes(id, 32, 32), bound = await current(ports);
    const candidate = attempt(await ports.attempts.get(attemptId));
    await current(ports, bound);
    // A different session cannot burn an invitation. Its owner gets one attempt.
    live(candidate, bound, await context(ports, bound), ports.now());
    const consumed = attempt(await ports.attempts.consume(attemptId));
    await current(ports, bound);
    if (JSON.stringify(candidate) !== JSON.stringify(consumed)) throw rejected();
    live(consumed, bound, await context(ports, bound), ports.now());
    const key = await verifyPasskeyRegistration(response, registrationContext(consumed), ports.now());
    live(consumed, bound, await context(ports, bound), ports.now());
    const wire = await ports.request(bound.session, "/v1/passkeys/enrollment/finish", Object.freeze({
      claim_id: consumed.claimId, session_binding: consumed.binding,
      credential_id: key.credentialId, public_key: Buffer.from(key.publicKey).toString("base64url"),
      sign_count: key.counter, backup_eligible: key.backupEligible, backed_up: key.backedUp,
    }));
    await current(ports, bound);
    const saved = parsePasskeyRecord(wire, { tenantId: consumed.tenantId, userId: consumed.userId, rpId: consumed.rpId });
    if (saved.status !== "active" || saved.storage_version !== 1 || saved.enrollment_epoch !== consumed.authEpoch ||
      saved.credential_id !== key.credentialId || saved.user_handle !== key.userHandle ||
      saved.public_key !== Buffer.from(key.publicKey).toString("base64url") || saved.sign_count !== key.counter ||
      saved.backup_eligible !== key.backupEligible || saved.backed_up !== key.backedUp) throw rejected();
    // The write may already be committed. Publish success only after current
    // actor/session/epoch/origin and the authoritative saved factor still agree.
    const latest = await context(ports, bound);
    if (latest.user_id !== consumed.userId || JSON.stringify(latest.credential) !== JSON.stringify(saved) ||
      ports.now() >= consumed.expiresAt || ports.now() >= consumed.sessionExpiresAt) throw rejected();
  } catch { throw rejected(); }
}
