import { randomUUID } from "node:crypto";
import { SignJWT } from "jose";
import { sha256 } from "./security.ts";

export type Principal = {
  subject: string; issuer: string; oidcAuthTime: number; tenantId?: string; authEpoch?: number;
};

export async function internalToken(
  secret: string, principal: Principal, method: string, path: string, body = "", now = Math.floor(Date.now() / 1000),
): Promise<string> {
  if (Buffer.byteLength(secret) < 32 || !path.startsWith("/v1/") || path.includes("#") || path.includes("\\")) throw new Error("INTERNAL_CONTEXT_REJECTED");
  return new SignJWT({
    oidc_iss: principal.issuer,
    oidc_auth_time: principal.oidcAuthTime,
    ...(principal.tenantId ? { tenant_id: principal.tenantId } : {}),
    ...(principal.authEpoch !== undefined ? { auth_epoch: principal.authEpoch } : {}),
    htm: method.toUpperCase(),
    htu: path,
    body_sha256: sha256(body),
  }).setProtectedHeader({ alg: "HS256", typ: "JWT" })
    .setIssuer("investalo-bff").setAudience("investalo-api").setSubject(principal.subject)
    .setIssuedAt(now).setExpirationTime(now + 30).setJti(randomUUID())
    .sign(new TextEncoder().encode(secret));
}
