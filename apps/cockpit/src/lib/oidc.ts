import "server-only";
import { createRemoteJWKSet } from "jose";
import type { Config } from "./config.ts";
import { limitedBody, pkceChallenge } from "./security.ts";
import { verifyIdentityToken } from "./id-token.ts";

type Discovery = { issuer: string; authorization_endpoint: string; token_endpoint: string; jwks_uri: string };
export type OidcAttempt = { startedAt: number; nonce: string; verifier: string };

async function readJson(response: Response): Promise<Record<string, unknown>> {
  if (!response.ok) throw new Error("IDENTITY_UNAVAILABLE");
  const raw = await limitedBody(new Request("https://response.invalid", {
    method: "POST", body: response.body, duplex: "half",
  } as RequestInit), 65_536);
  return JSON.parse(raw) as Record<string, unknown>;
}

async function discovery(config: Config): Promise<Discovery> {
  const response = await fetch(`${config.issuer}/.well-known/openid-configuration`, {
    cache: "no-store", redirect: "error", signal: AbortSignal.timeout(5000),
  });
  const data = await readJson(response) as Discovery;
  if (data.issuer !== config.issuer) throw new Error("ISSUER_REJECTED");
  for (const value of [data.authorization_endpoint, data.token_endpoint, data.jwks_uri]) {
    const url = new URL(value);
    if (url.origin !== config.issuer || url.protocol !== "https:" || url.username || url.password || url.hash) {
      throw new Error("OIDC_ENDPOINT_REJECTED");
    }
  }
  return data;
}

function callback(config: Config, path: string): string {
  if (!["/api/auth/callback", "/api/credentials/callback"].includes(path)) throw new Error("CALLBACK_REJECTED");
  return `${config.origin}${path}`;
}

export async function authorizationUrl(config: Config, attempt: OidcAttempt, state: string, path: string): Promise<string> {
  const metadata = await discovery(config);
  const url = new URL(metadata.authorization_endpoint);
  url.search = new URLSearchParams({
    client_id: config.clientId, redirect_uri: callback(config, path),
    response_type: "code", scope: "openid profile email", state, nonce: attempt.nonce,
    code_challenge: pkceChallenge(attempt.verifier), code_challenge_method: "S256",
    // max_age=0 loops in Authelia 4.39.28. Verify the signed auth_time against
    // the stored flow start in addition to requesting interactive authentication.
    prompt: "login",
    claims: JSON.stringify({ id_token: { amr: { essential: true }, auth_time: { essential: true }, name: null } }),
  }).toString();
  return url.toString();
}

export async function exchangeIdentity(config: Config, attempt: OidcAttempt, code: string, path: string) {
  if (!code || code.length > 4096) throw new Error("CALLBACK_REJECTED");
  const metadata = await discovery(config);
  const response = await fetch(metadata.token_endpoint, {
    method: "POST", cache: "no-store", redirect: "error", signal: AbortSignal.timeout(5000),
    headers: { "Content-Type": "application/x-www-form-urlencoded",
      Authorization: `Basic ${Buffer.from(`${encodeURIComponent(config.clientId)}:${encodeURIComponent(config.clientSecret)}`).toString("base64")}` },
    body: new URLSearchParams({ grant_type: "authorization_code", code, redirect_uri: callback(config, path), code_verifier: attempt.verifier }),
  });
  const token = await readJson(response);
  if (typeof token.id_token !== "string" || !token.id_token || token.id_token.length > 32_768) throw new Error("TOKEN_REJECTED");
  const keys = createRemoteJWKSet(new URL(metadata.jwks_uri), { timeoutDuration: 5000 });
  return verifyIdentityToken(token.id_token, keys, config.issuer, config.clientId, attempt.nonce, attempt.startedAt);
}
