import test from "node:test";
import assert from "node:assert/strict";
import { generateKeyPair, jwtVerify, SignJWT } from "jose";
import { internalToken } from "../src/lib/internal-token.ts";
import { verifyIdentityToken } from "../src/lib/id-token.ts";
import { parseOverview } from "../src/lib/contracts.ts";
import { randomToken, sha256 } from "../src/lib/security.ts";

test("internal JWT binds identity, tenant, MFA age, auth epoch, request bytes and a short lifetime", async () => {
  const secret = randomToken(), now = Math.floor(Date.now() / 1000), body = '{"symbol":"BTC/USDT"}';
  const principal = { subject: "opaque-subject", issuer: "https://auth.test", oidcAuthTime: now, tenantId: "tenant-1", authEpoch: 4 };
  const token = await internalToken(secret, principal, "POST", "/v1/backtests", body, now);
  const { payload } = await jwtVerify(token, new TextEncoder().encode(secret), { issuer: "investalo-bff", audience: "investalo-api", algorithms: ["HS256"] });
  assert.equal(payload.sub, principal.subject);
  assert.equal(payload.tenant_id, principal.tenantId);
  assert.equal(payload.auth_epoch, 4);
  assert.equal(payload.oidc_auth_time, now);
  assert.equal(payload.htm, "POST");
  assert.equal(payload.htu, "/v1/backtests");
  assert.equal(payload.body_sha256, sha256(body));
  assert.equal(payload.exp! - payload.iat!, 30);
  assert.equal("roles" in payload, false);
  await assert.rejects(jwtVerify(token, new TextEncoder().encode(randomToken()), { algorithms: ["HS256"] }));
  await assert.rejects(jwtVerify(token, new TextEncoder().encode(secret), { audience: "another" }));
  const second = await internalToken(secret, principal, "GET", "/v1/jobs?limit=20", "", now);
  const { payload: other } = await jwtVerify(second, new TextEncoder().encode(secret));
  assert.notEqual(payload.jti, other.jti);
  assert.equal(other.htu, "/v1/jobs?limit=20");
  await assert.rejects(internalToken("short", principal, "GET", "/v1/me"));
});
test("ID token validates real RSA signature, audience, issuer, nonce and MFA", async () => {
  const { publicKey, privateKey } = await generateKeyPair("RS256");
  const now = Math.floor(Date.now() / 1000);
  const token = await new SignJWT({ nonce: "bound-nonce", auth_time: now, amr: ["pwd", "otp", "mfa"] })
    .setProtectedHeader({ alg: "RS256" }).setIssuer("https://auth.test").setAudience("cockpit").setSubject("opaque-subject")
    .setIssuedAt(now).setExpirationTime(now + 60).sign(privateKey);
  assert.equal((await verifyIdentityToken(token, publicKey, "https://auth.test", "cockpit", "bound-nonce", now)).subject, "opaque-subject");
  await assert.rejects(verifyIdentityToken(token, publicKey, "https://wrong.test", "cockpit", "bound-nonce", now));
  await assert.rejects(verifyIdentityToken(token, publicKey, "https://auth.test", "wrong", "bound-nonce", now));
  await assert.rejects(verifyIdentityToken(token, publicKey, "https://auth.test", "cockpit", "wrong", now));
  const other = await generateKeyPair("RS256");
  await assert.rejects(verifyIdentityToken(token, other.publicKey, "https://auth.test", "cockpit", "bound-nonce", now));
  const earlierAuthentication = await new SignJWT({ nonce: "bound-nonce", auth_time: now - 1, amr: ["pwd", "otp", "mfa"] })
    .setProtectedHeader({ alg: "RS256" }).setIssuer("https://auth.test").setAudience("cockpit").setSubject("opaque-subject")
    .setIssuedAt(now).setExpirationTime(now + 60).sign(privateKey);
  await assert.rejects(verifyIdentityToken(earlierAuthentication, publicKey, "https://auth.test", "cockpit", "bound-nonce", now), /AUTH_TIME_REJECTED/);
});
test("overview cannot publish another tenant, malformed arrays or real-money mode", () => {
  const safe = { mode: "paper", live_enabled: false, tenant_id: "own", accounts: [], positions: [], journal: [], jobs: [] };
  assert.equal(parseOverview(safe, "own").tenant_id, "own");
  for (const patch of [{ tenant_id: "other" }, { live_enabled: true }, { mode: "live" }, { accounts: null }, { positions: "bad" }, { journal: {} }]) {
    assert.throws(() => parseOverview({ ...safe, ...patch }, "own"));
  }
});
