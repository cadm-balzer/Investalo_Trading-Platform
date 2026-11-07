import "server-only";
import { getBoundSession, type Session } from "./auth.ts";
import { apiRequest } from "./backend.ts";
import { getConfig, type Config } from "./config.ts";
import { EncryptedStore } from "./store.ts";
import { randomToken } from "./security.ts";
import {
  assertEnrollment, canonicalBytes, enrollmentBinding, exactObject, parsePasskeyContext, parsePasskeyRecord,
  type EnrollmentAttempt, type PasskeyContext,
} from "./passkey-enrollment-state.ts";
import { canonicalUuid, credentialInteger } from "./credential-action-contracts.ts";
import { generatePasskeyRegistrationOptions, verifyPasskeyRegistration } from "./passkey-registration.ts";

function attempts(config: Config): EncryptedStore {
  return new EncryptedStore(`${config.stateDir}/passkey-enrollment`, config.sessionSecret);
}
export async function getPasskeyContext(session: Session, config = getConfig()): Promise<PasskeyContext> {
  const settings = await config;
  const value = await apiRequest<unknown>(session, "/v1/passkeys/context", {}, settings);
  return parsePasskeyContext(value, { tenantId: session.tenantId, authEpoch: session.authEpoch,
    rpId: new URL(settings.origin).hostname });
}
/** Invitation claim commits in the API before any browser or crypto work. */
export async function beginPasskeyEnrollment(ticket: unknown) {
  const token = canonicalBytes(ticket, 32, 32), config = await getConfig(), bound = await getBoundSession();
  if (!bound) throw new Error("PASSKEY_ENROLLMENT_REJECTED");
  const context = await getPasskeyContext(bound.session, Promise.resolve(config));
  if (context.credential !== null) throw new Error("PASSKEY_ENROLLMENT_REJECTED");
  const binding = enrollmentBinding(bound.handle, bound.session);
  const claim = exactObject(await apiRequest<unknown>(bound.session, "/v1/passkeys/enrollment/claim", {
    method: "POST", body: JSON.stringify({ token, session_binding: binding }),
  }, config), ["claim_id", "user_handle", "expires_at", "tenant_id", "user_id", "auth_epoch", "rp_id"]);
  if (claim.tenant_id !== context.tenant_id || claim.user_id !== context.user_id ||
    credentialInteger(claim.auth_epoch) !== context.auth_epoch || claim.rp_id !== context.rp_id ||
    typeof claim.expires_at !== "string") throw new Error("PASSKEY_ENROLLMENT_REJECTED");
  const startedAt = Math.floor(Date.now() / 1000);
  const expiresAt = Math.min(Math.floor(Date.parse(claim.expires_at) / 1000), startedAt + 120);
  if (!Number.isSafeInteger(expiresAt) || expiresAt <= startedAt) throw new Error("PASSKEY_ENROLLMENT_REJECTED");
  const attempt: EnrollmentAttempt = Object.freeze({
    tenantId: context.tenant_id, userId: context.user_id, authEpoch: context.auth_epoch,
    rpId: context.rp_id, origin: config.origin, claimId: canonicalUuid(claim.claim_id),
    userHandle: canonicalBytes(claim.user_handle, 32, 32), binding, challenge: randomToken(), startedAt, expiresAt,
  });
  const options = await generatePasskeyRegistrationOptions({
    tenantId: attempt.tenantId, userId: attempt.userId, rpId: attempt.rpId, origin: attempt.origin,
    userHandle: attempt.userHandle, challenge: attempt.challenge, startedAt, expiresAt,
  });
  const latest = await getBoundSession();
  if (!latest) throw new Error("PASSKEY_ENROLLMENT_REJECTED");
  assertEnrollment(attempt, latest.handle, latest.session, await getPasskeyContext(latest.session, Promise.resolve(config)));
  const id = randomToken();
  await attempts(config).put(id, attempt);
  return { attempt_id: id, options };
}
export async function finishPasskeyEnrollment(id: unknown, response: unknown): Promise<void> {
  const attemptId = canonicalBytes(id, 32, 32), config = await getConfig(), bound = await getBoundSession();
  if (!bound) throw new Error("PASSKEY_ENROLLMENT_REJECTED");
  const store = attempts(config), candidate = await store.get<EnrollmentAttempt>(attemptId);
  if (!candidate || candidate.origin !== config.origin) throw new Error("PASSKEY_ENROLLMENT_REJECTED");
  // A different session cannot burn an invitation. The matching session gets
  // exactly one verification attempt, including malformed responses and crashes.
  assertEnrollment(candidate, bound.handle, bound.session, await getPasskeyContext(bound.session, Promise.resolve(config)));
  const attempt = await store.consume<EnrollmentAttempt>(attemptId);
  if (!attempt || attempt.origin !== config.origin) throw new Error("PASSKEY_ENROLLMENT_REJECTED");
  assertEnrollment(attempt, bound.handle, bound.session, await getPasskeyContext(bound.session, Promise.resolve(config)));
  const key = await verifyPasskeyRegistration(response, {
    tenantId: attempt.tenantId, userId: attempt.userId, rpId: attempt.rpId, origin: attempt.origin,
    userHandle: attempt.userHandle, challenge: attempt.challenge, startedAt: attempt.startedAt, expiresAt: attempt.expiresAt,
  });
  const latest = await getBoundSession();
  if (!latest) throw new Error("PASSKEY_ENROLLMENT_REJECTED");
  assertEnrollment(attempt, latest.handle, latest.session, await getPasskeyContext(latest.session, Promise.resolve(config)));
  const saved = parsePasskeyRecord(await apiRequest<unknown>(latest.session, "/v1/passkeys/enrollment/finish", {
    method: "POST", body: JSON.stringify({ claim_id: attempt.claimId, session_binding: attempt.binding,
      credential_id: key.credentialId, public_key: Buffer.from(key.publicKey).toString("base64url"),
      sign_count: key.counter, backup_eligible: key.backupEligible, backed_up: key.backedUp }),
  }, config), { tenantId: attempt.tenantId, userId: attempt.userId, rpId: attempt.rpId });
  if (saved.status !== "active" || saved.storage_version !== 1 || saved.enrollment_epoch !== attempt.authEpoch ||
    saved.credential_id !== key.credentialId || saved.user_handle !== key.userHandle ||
    saved.public_key !== Buffer.from(key.publicKey).toString("base64url") || saved.sign_count !== key.counter ||
    saved.backup_eligible !== key.backupEligible || saved.backed_up !== key.backedUp) throw new Error("PASSKEY_ENROLLMENT_REJECTED");
}
