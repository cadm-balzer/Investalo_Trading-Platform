import "server-only";
import { cookies } from "next/headers";
import { randomUUID } from "node:crypto";
import { getBoundSession, type Session } from "./auth.ts";
import { apiRequest } from "./backend.ts";
import { getConfig, type Config } from "./config.ts";
import { parseOverview } from "./contracts.ts";
import { canonicalUuid, parseCredentialActionMetadata, deriveActionTarget, type CredentialAction, type CredentialActionMetadata } from "./credential-action-contracts.ts";
import { EncryptedStore } from "./store.ts";
import { randomToken, sameSecret, signedState, validState } from "./security.ts";
import { authorizationUrl, exchangeIdentity } from "./oidc.ts";
import { bindSession, assertSession, makeCredentialGrant, assertCredentialGrant, assertCredentialConfirmation,
  publicCredentialGrant, requireCredentialStepUp, CREDENTIAL_STEP_UP_AVAILABLE,
  type CredentialGrant, type StepUpAttempt, type PublicCredentialGrant } from "./credential-step-up-state.ts";
import type { Principal } from "./internal-token.ts";

export const STEP_UP_COOKIE = "__Host-investalo-step-up";
export const CREDENTIAL_GRANT_COOKIE = "__Host-investalo-credential-grant";
const CALLBACK = "/api/credentials/callback";
function attempts(config: Config) { return new EncryptedStore(`${config.stateDir}/credential-logins`, config.sessionSecret); }
function grants(config: Config) { return new EncryptedStore(`${config.stateDir}/credential-grants`, config.sessionSecret); }

export async function getCredentialMetadata(session: Principal & { tenantId: string; authEpoch: number }, accountId: string) {
  canonicalUuid(accountId);
  const candidate = await apiRequest<unknown>(session, `/v1/credential-actions/${accountId}`);
  return parseCredentialActionMetadata(candidate, { tenantId: session.tenantId, accountId, authEpoch: session.authEpoch });
}

export async function listCredentialMetadata(session: Session): Promise<CredentialActionMetadata[]> {
  const overview = parseOverview(await apiRequest<unknown>(session, "/v1/overview"), session.tenantId);
  if (overview.accounts.length > 50) throw new Error("STEP_UP_REJECTED");
  const accounts: CredentialActionMetadata[] = [];
  for (const account of overview.accounts) {
    if (account.mode !== "read_only") continue;
    // Only the authenticated context endpoint may publish connection state.
    // A denied/non-Bitget account remains absent, not a fabricated empty state.
    try { accounts.push(await getCredentialMetadata(session, account.id)); }
    catch (error) {
      const status = (error as { status?: number }).status;
      if (status !== 403 && status !== 404) throw error;
    }
  }
  return accounts;
}

async function current() {
  const bound = await getBoundSession();
  if (!bound) throw new Error("SESSION_REQUIRED");
  return { ...bound, binding: bindSession(bound.handle, bound.session) };
}

export async function beginCredentialStepUp(accountId: string, action: CredentialAction) {
  requireCredentialStepUp();
  const config = await getConfig();
  const original = await current();
  const metadata = await getCredentialMetadata(original.session, accountId);
  const target = deriveActionTarget(metadata, action, action === "register" ? { newConnectionId: randomUUID() } : {});
  const id = randomToken(), binding = randomToken(), startedAt = Math.floor(Date.now() / 1000);
  const attempt: StepUpAttempt = { session: original.binding, target, accountName: metadata.account.name,
    binding, nonce: randomToken(), verifier: randomToken(), startedAt, expiresAt: Math.min(startedAt + 300, original.session.expiresAt) };
  const store = attempts(config);
  await store.put(id, attempt);
  const oldGrant = (await cookies()).get(CREDENTIAL_GRANT_COOKIE)?.value;
  if (oldGrant) await grants(config).delete(oldGrant);
  const state = signedState(id, binding, config.sessionSecret);
  try {
    const url = await authorizationUrl(config, attempt, state, CALLBACK);
    assertSession(original.binding, (await current()).binding, Math.floor(Date.now() / 1000));
    return { authorizationUrl: url, binding };
  } catch {
    await store.delete(id);
    throw new Error("STEP_UP_REJECTED");
  }
}

export async function finishCredentialStepUp(state: string, code: string, binding: string) {
  requireCredentialStepUp();
  const config = await getConfig();
  if (!validState(state, binding, config.sessionSecret) || !code || code.length > 4096) throw new Error("CALLBACK_REJECTED");
  // Claim before OIDC exchange. Invalid or failed attempts never become replayable.
  const attempt = await attempts(config).consume<StepUpAttempt>(state.split(".")[0]);
  if (!attempt || !sameSecret(attempt.binding, binding)) throw new Error("CALLBACK_REJECTED");
  const original = await current();
  assertSession(attempt.session, original.binding, Math.floor(Date.now() / 1000));
  const identity = { ...await exchangeIdentity(config, attempt, code, CALLBACK), issuer: config.issuer };
  const after = await current();
  assertSession(attempt.session, after.binding, Math.floor(Date.now() / 1000));
  const principal = { ...after.session, oidcAuthTime: identity.authTime };
  const metadata = await getCredentialMetadata(principal, attempt.target.platform_account_id);
  const grant = makeCredentialGrant(attempt, after.binding, identity, metadata, Math.floor(Date.now() / 1000), randomToken());
  const id = randomToken();
  await grants(config).put(id, grant);
  return { id, expiresAt: grant.expiresAt };
}

export async function getCredentialGrant(): Promise<PublicCredentialGrant | null> {
  if (!CREDENTIAL_STEP_UP_AVAILABLE) return null;
  try {
    const config = await getConfig();
    const id = (await cookies()).get(CREDENTIAL_GRANT_COOKIE)?.value;
    if (!id) return null;
    const grant = await grants(config).get<CredentialGrant>(id);
    if (!grant) return null;
    const bound = await current();
    const metadata = await getCredentialMetadata({ ...bound.session, oidcAuthTime: grant.identity.authTime }, grant.target.platform_account_id);
    assertCredentialGrant(grant, bound.binding, metadata);
    return publicCredentialGrant(grant);
  } catch { return null; }
}

export async function confirmCredentialStepUp(confirmationToken: string) {
  requireCredentialStepUp();
  const config = await getConfig();
  const id = (await cookies()).get(CREDENTIAL_GRANT_COOKIE)?.value;
  if (!id) throw new Error("STEP_UP_REQUIRED");
  const bound = await current();
  const store = grants(config);
  const candidate = await store.get<CredentialGrant>(id);
  if (!candidate) throw new Error("STEP_UP_REQUIRED");
  assertSession(candidate.session, bound.binding, Math.floor(Date.now() / 1000));
  // The preview's nonce must match before consuming the latest cookie grant.
  // A different tab's preview cannot confirm a subsequently prepared action.
  assertCredentialConfirmation(candidate, confirmationToken);
  const grant = await store.consume<CredentialGrant>(id);
  if (!grant) throw new Error("STEP_UP_REQUIRED");
  assertCredentialConfirmation(grant, confirmationToken);
  const metadata = await getCredentialMetadata({ ...bound.session, oidcAuthTime: grant.identity.authTime }, grant.target.platform_account_id);
  assertCredentialGrant(grant, (await current()).binding, metadata);
  // Verification only. No HTTP credential endpoint, triple intake, token
  // response, broker call or database credential mutation is enabled here.
  return { status: "verified" as const, execution_enabled: false as const,
    action: grant.target.action, platform_account_id: grant.target.platform_account_id };
}
