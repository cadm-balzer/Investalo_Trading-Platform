import { createHash, createHmac, randomBytes, timingSafeEqual } from "node:crypto";

export const SESSION_COOKIE = "__Host-investalo-session";
export const LOGIN_COOKIE = "__Host-investalo-login";
export const COOKIE_OPTIONS = { httpOnly: true, secure: true, sameSite: "lax" as const, path: "/" };

export function randomToken(): string {
  return randomBytes(32).toString("base64url");
}

export function sha256(value: string): string {
  return createHash("sha256").update(value, "utf8").digest("hex");
}

export function sameSecret(a: string, b: string): boolean {
  const left = Buffer.from(a);
  const right = Buffer.from(b);
  return left.length === right.length && timingSafeEqual(left, right);
}

export function signedState(id: string, binding: string, secret: string): string {
  const signature = createHmac("sha256", secret).update(`oidc-state:${id}:${binding}`).digest("base64url");
  return `${id}.${signature}`;
}

export function validState(state: string, binding: string, secret: string): boolean {
  if (!/^[A-Za-z0-9_-]{43}\.[A-Za-z0-9_-]{43}$/.test(state)) return false;
  return sameSecret(state, signedState(state.split(".")[0], binding, secret));
}

export function pkceChallenge(verifier: string): string {
  return createHash("sha256").update(verifier).digest("base64url");
}

export function requireSameOrigin(request: Request, origin: string): void {
  if (request.headers.get("origin") !== origin) throw new Error("ORIGIN_REJECTED");
  const site = request.headers.get("sec-fetch-site");
  if (site && site !== "same-origin") throw new Error("ORIGIN_REJECTED");
}

export function requireCsrf(expected: string, actual: string | null): void {
  if (!actual || !sameSecret(expected, actual)) throw new Error("CSRF_REJECTED");
}

/** Authelia uses RFC8176 `mfa` for an authentication with multiple factors. */
export function verifiedIdentity(
  claims: Record<string, unknown>,
  expectedNonce: string,
  clientId: string,
  startedAt: number,
  now = Math.floor(Date.now() / 1000),
): { subject: string; authTime: number; expiresAt: number; name: string } {
  if (typeof claims.sub !== "string" || !claims.sub || claims.sub.length > 512) throw new Error("SUBJECT_REJECTED");
  if (typeof claims.nonce !== "string" || !sameSecret(claims.nonce, expectedNonce)) throw new Error("NONCE_REJECTED");
  if (claims.azp !== undefined && claims.azp !== clientId) throw new Error("AUTHORIZED_PARTY_REJECTED");
  if (Array.isArray(claims.aud) && claims.aud.length > 1 && claims.azp !== clientId) throw new Error("AUTHORIZED_PARTY_REJECTED");
  if (!Array.isArray(claims.amr) || !claims.amr.includes("mfa")) throw new Error("MFA_REQUIRED");
  // auth_time has whole-second precision. Persist the start with the same
  // precision and never accept an earlier authentication. The local BFF and
  // IdP share the host clock; five seconds of tolerance applies only to future
  // timestamps, not to authentication predating this browser-bound flow.
  if (!Number.isSafeInteger(startedAt) || startedAt <= 0 || startedAt > now + 5 || startedAt < now - 300 ||
      !Number.isSafeInteger(claims.auth_time) || (claims.auth_time as number) > now + 5 || (claims.auth_time as number) < startedAt) {
    throw new Error("AUTH_TIME_REJECTED");
  }
  if (!Number.isSafeInteger(claims.exp) || (claims.exp as number) <= now) throw new Error("TOKEN_EXPIRED");
  if (!Number.isSafeInteger(claims.iat) || (claims.iat as number) > now + 5 || (claims.iat as number) < now - 300) throw new Error("ISSUED_AT_REJECTED");
  return {
    subject: claims.sub,
    authTime: claims.auth_time as number,
    expiresAt: Math.min(claims.exp as number, now + 1800),
    name: typeof claims.name === "string" ? claims.name.slice(0, 100) : "Pilotnutzer",
  };
}

export async function limitedBody(request: Request, maxBytes = 1024): Promise<string> {
  const announced = request.headers.get("content-length");
  if (announced && (!/^\d+$/.test(announced) || Number(announced) > maxBytes)) throw new Error("BODY_TOO_LARGE");
  if (!request.body) return "";
  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let length = 0;
  try {
    while (true) {
      const chunk = await reader.read();
      if (chunk.done) break;
      length += chunk.value.byteLength;
      if (length > maxBytes) { await reader.cancel(); throw new Error("BODY_TOO_LARGE"); }
      chunks.push(chunk.value);
    }
  } finally { reader.releaseLock(); }
  return Buffer.concat(chunks).toString("utf8");
}
