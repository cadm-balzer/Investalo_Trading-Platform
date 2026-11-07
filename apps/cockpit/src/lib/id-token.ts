import { jwtVerify, type JWTVerifyGetKey } from "jose";
import { verifiedIdentity } from "./security.ts";

export async function verifyIdentityToken(token: string, key: CryptoKey | JWTVerifyGetKey, issuer: string, clientId: string, nonce: string, startedAt: number) {
  const options = { issuer, audience: clientId, algorithms: ["RS256"], clockTolerance: 5 };
  const result = typeof key === "function" ? await jwtVerify(token, key, options) : await jwtVerify(token, key, options);
  return verifiedIdentity(result.payload, nonce, clientId, startedAt);
}
