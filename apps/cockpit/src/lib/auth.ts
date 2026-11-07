import "server-only";
import { cookies } from "next/headers";
import { createRemoteJWKSet } from "jose";
import { getConfig, type Config } from "./config.ts";
import { EncryptedStore } from "./store.ts";
import { LOGIN_COOKIE, SESSION_COOKIE, pkceChallenge, randomToken, sameSecret, signedState, validState } from "./security.ts";
import { verifyIdentityToken } from "./id-token.ts";
import { apiRequest, type Membership } from "./backend.ts";
import type { Principal } from "./internal-token.ts";

type Discovery = { issuer: string; authorization_endpoint: string; token_endpoint: string; jwks_uri: string };
type LoginState = { expiresAt: number; startedAt: number; binding: string; nonce: string; verifier: string };
export type Session = Principal & {
  tenantId: string; authEpoch: number; expiresAt: number; displayName: string; tenantName: string; csrf: string;
};

function sessionStore(config: Config): EncryptedStore { return new EncryptedStore(`${config.stateDir}/sessions`, config.sessionSecret); }
function loginStore(config: Config): EncryptedStore { return new EncryptedStore(`${config.stateDir}/logins`, config.sessionSecret); }

async function discovery(config: Config): Promise<Discovery> {
  const response = await fetch(`${config.issuer}/.well-known/openid-configuration`, { cache: "no-store", redirect: "error", signal: AbortSignal.timeout(5000) });
  if (!response.ok) throw new Error("IDENTITY_UNAVAILABLE");
  const data = await response.json() as Discovery;
  if (data.issuer !== config.issuer) throw new Error("ISSUER_REJECTED");
  for (const value of [data.authorization_endpoint, data.token_endpoint, data.jwks_uri]) {
    const url = new URL(value);
    if (url.origin !== config.issuer || url.protocol !== "https:" || url.username || url.password || url.hash) throw new Error("OIDC_ENDPOINT_REJECTED");
  }
  return data;
}

export async function beginLogin(): Promise<{ authorizationUrl: string; binding: string }> {
  const config = await getConfig();
  const metadata = await discovery(config);
  const id = randomToken(), binding = randomToken(), nonce = randomToken(), verifier = randomToken();
  const state = signedState(id, binding, config.sessionSecret);
  const startedAt = Math.floor(Date.now() / 1000);
  await loginStore(config).put<LoginState>(id, { binding, nonce, verifier, startedAt, expiresAt: startedAt + 300 });
  const url = new URL(metadata.authorization_endpoint);
  url.search = new URLSearchParams({
    client_id: config.clientId, redirect_uri: `${config.origin}/api/auth/callback`,
    response_type: "code", scope: "openid profile email", state, nonce,
    code_challenge: pkceChallenge(verifier), code_challenge_method: "S256",
    // OIDC Core treats prompt=login and max_age=0 as equivalent. Authelia
    // 4.39.28 keeps max_age=0 in its consent form and requires login forever.
    prompt: "login",
    claims: JSON.stringify({ id_token: { amr: { essential: true }, auth_time: { essential: true }, name: null } }),
  }).toString();
  return { authorizationUrl: url.toString(), binding };
}

export async function finishLogin(state: string, code: string, binding: string): Promise<{ id: string; expiresAt: number }> {
  const config = await getConfig();
  if (!validState(state, binding, config.sessionSecret) || code.length > 4096 || !code) throw new Error("CALLBACK_REJECTED");
  const attempt = await loginStore(config).consume<LoginState>(state.split(".")[0]);
  if (!attempt || !sameSecret(attempt.binding, binding)) throw new Error("CALLBACK_REPLAYED");
  const metadata = await discovery(config);
  const response = await fetch(metadata.token_endpoint, {
    method: "POST", cache: "no-store", redirect: "error", signal: AbortSignal.timeout(5000),
    headers: { "Content-Type": "application/x-www-form-urlencoded", Authorization: `Basic ${Buffer.from(`${encodeURIComponent(config.clientId)}:${encodeURIComponent(config.clientSecret)}`).toString("base64")}` },
    body: new URLSearchParams({ grant_type: "authorization_code", code, redirect_uri: `${config.origin}/api/auth/callback`, code_verifier: attempt.verifier }),
  });
  if (!response.ok) throw new Error("CODE_REJECTED");
  const token = await response.json() as { id_token?: string };
  if (!token.id_token || token.id_token.length > 32_768) throw new Error("TOKEN_REJECTED");
  const keys = createRemoteJWKSet(new URL(metadata.jwks_uri), { timeoutDuration: 5000 });
  const identity = await verifyIdentityToken(token.id_token, keys, config.issuer, config.clientId, attempt.nonce, attempt.startedAt);
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
  const id = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!id) return null;
  try { return await sessionStore(await getConfig()).get<Session>(id); } catch { return null; }
}

export async function destroySession(): Promise<void> {
  const id = (await cookies()).get(SESSION_COOKIE)?.value;
  if (id) await sessionStore(await getConfig()).delete(id);
}

export { LOGIN_COOKIE };
