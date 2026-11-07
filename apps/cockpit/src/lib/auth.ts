import "server-only";
import { cookies } from "next/headers";
import { getConfig, type Config } from "./config.ts";
import { EncryptedStore } from "./store.ts";
import { LOGIN_COOKIE, SESSION_COOKIE, randomToken, sameSecret, signedState, validState } from "./security.ts";
import { authorizationUrl, exchangeIdentity } from "./oidc.ts";
import { apiRequest, type Membership } from "./backend.ts";
import type { Principal } from "./internal-token.ts";

type LoginState = { expiresAt: number; startedAt: number; binding: string; nonce: string; verifier: string };
export type Session = Principal & {
  tenantId: string; authEpoch: number; expiresAt: number; displayName: string; tenantName: string; csrf: string;
};

function sessionStore(config: Config): EncryptedStore { return new EncryptedStore(`${config.stateDir}/sessions`, config.sessionSecret); }
function loginStore(config: Config): EncryptedStore { return new EncryptedStore(`${config.stateDir}/logins`, config.sessionSecret); }

export async function beginLogin(): Promise<{ authorizationUrl: string; binding: string }> {
  const config = await getConfig();
  const id = randomToken(), binding = randomToken(), nonce = randomToken(), verifier = randomToken();
  const state = signedState(id, binding, config.sessionSecret);
  const startedAt = Math.floor(Date.now() / 1000);
  await loginStore(config).put<LoginState>(id, { binding, nonce, verifier, startedAt, expiresAt: startedAt + 300 });
  return { authorizationUrl: await authorizationUrl(config, { startedAt, nonce, verifier }, state, "/api/auth/callback"), binding };
}

export async function finishLogin(state: string, code: string, binding: string): Promise<{ id: string; expiresAt: number }> {
  const config = await getConfig();
  if (!validState(state, binding, config.sessionSecret) || code.length > 4096 || !code) throw new Error("CALLBACK_REJECTED");
  const attempt = await loginStore(config).consume<LoginState>(state.split(".")[0]);
  if (!attempt || !sameSecret(attempt.binding, binding)) throw new Error("CALLBACK_REPLAYED");
  const identity = await exchangeIdentity(config, attempt, code, "/api/auth/callback");
  const principal: Principal = { subject: identity.subject, issuer: config.issuer, oidcAuthTime: identity.authTime };
  const me = await apiRequest<{ user: { auth_epoch: number }; memberships: Membership[] }>(principal, "/v1/me", {}, config);
  const membership = me.memberships[0];
  if (!membership || !Number.isSafeInteger(me.user.auth_epoch)) throw new Error("MEMBERSHIP_REQUIRED");
  const previous = (await cookies()).get(SESSION_COOKIE)?.value;
  if (previous) await sessionStore(config).delete(previous);
  const id = randomToken();
  await sessionStore(config).put<Session>(id, {
    ...principal, tenantId: membership.tenant_id, tenantName: membership.tenant_name,
    authEpoch: me.user.auth_epoch, displayName: identity.name, expiresAt: identity.expiresAt, csrf: randomToken(),
  });
  return { id, expiresAt: identity.expiresAt };
}

export async function getSession(): Promise<Session | null> {
  return (await getBoundSession())?.session ?? null;
}

export async function getBoundSession(): Promise<{ handle: string; session: Session } | null> {
  const id = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!id) return null;
  try {
    const session = await sessionStore(await getConfig()).get<Session>(id);
    return session ? { handle: id, session } : null;
  } catch { return null; }
}

export async function destroySession(): Promise<void> {
  const id = (await cookies()).get(SESSION_COOKIE)?.value;
  if (id) await sessionStore(await getConfig()).delete(id);
}

export { LOGIN_COOKIE };
