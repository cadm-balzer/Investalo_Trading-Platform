import test from "node:test";
import assert from "node:assert/strict";
import { COOKIE_OPTIONS, SESSION_COOKIE, limitedBody, pkceChallenge, randomToken, requireCsrf, requireSameOrigin, signedState, validState, verifiedIdentity } from "../src/lib/security.ts";

test("PKCE S256 uses the RFC7636 test vector", () => {
  assert.equal(pkceChallenge("dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"), "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM");
});
test("OIDC state cannot be transplanted to another browser or altered", () => {
  const secret = randomToken(), id = randomToken(), browser = randomToken();
  const state = signedState(id, browser, secret);
  assert.equal(validState(state, browser, secret), true);
  assert.equal(validState(state, randomToken(), secret), false);
  assert.equal(validState(state, browser, randomToken()), false);
  assert.equal(validState(`${state.slice(0, -1)}!`, browser, secret), false);
});
test("unsafe origins, absent CSRF and cross-site mutations fail closed", () => {
  const origin = "https://cockpit.local.test:8443";
  requireSameOrigin(new Request(origin, { headers: { origin } }), origin);
  assert.throws(() => requireSameOrigin(new Request(origin), origin));
  assert.throws(() => requireSameOrigin(new Request(origin, { headers: { origin: "https://attacker.test" } }), origin));
  assert.throws(() => requireSameOrigin(new Request(origin, { headers: { origin, "sec-fetch-site": "cross-site" } }), origin));
  requireCsrf("expected", "expected");
  assert.throws(() => requireCsrf("expected", null));
  assert.throws(() => requireCsrf("expected", "forged"));
});
test("only nonce-bound MFA with fresh authenticated ID claims creates identity", () => {
  const now = Math.floor(Date.now() / 1000);
  const claims = { sub: "opaque-user", nonce: "nonce", amr: ["pwd", "otp", "mfa"], auth_time: now, exp: now + 300, iat: now, aud: "cockpit" };
  assert.equal(verifiedIdentity(claims, "nonce", "cockpit", now, now).subject, "opaque-user");
  for (const patch of [{ amr: ["pwd"] }, { nonce: "forged" }, { auth_time: now + 20 }, { auth_time: now - 4000 }, { iat: now + 20 }, { exp: now - 1 }, { sub: "" }, { aud: ["cockpit", "another"] }, { azp: "another" }]) {
    assert.throws(() => verifiedIdentity({ ...claims, ...patch }, "nonce", "cockpit", now, now));
  }
});
test("fresh login rejects earlier authentication even within the clock tolerance", () => {
  const now = 1_800_000_000, startedAt = now - 20;
  const claims = { sub: "opaque-user", nonce: "nonce", amr: ["pwd", "otp", "mfa"], auth_time: startedAt, exp: now + 300, iat: now, aud: "cockpit" };
  assert.equal(verifiedIdentity(claims, "nonce", "cockpit", startedAt, now).authTime, startedAt);
  assert.equal(verifiedIdentity({ ...claims, auth_time: now + 5 }, "nonce", "cockpit", startedAt, now).authTime, now + 5);
  for (const auth_time of [startedAt - 1, startedAt - 5, now + 6, undefined, startedAt + 0.5]) {
    assert.throws(() => verifiedIdentity({ ...claims, auth_time }, "nonce", "cockpit", startedAt, now));
  }
  for (const invalidStart of [NaN, 0, now - 301, now + 6, startedAt + 0.5]) {
    assert.throws(() => verifiedIdentity(claims, "nonce", "cockpit", invalidStart, now));
  }
});
test("session cookie is host-only, Secure, HttpOnly and SameSite Lax", () => {
  assert.ok(SESSION_COOKIE.startsWith("__Host-"));
  assert.deepEqual(COOKIE_OPTIONS, { httpOnly: true, secure: true, sameSite: "lax", path: "/" });
});
test("request bodies are bounded even without a Content-Length", async () => {
  assert.equal(await limitedBody(new Request("https://test.invalid", { method: "POST", body: "small" })), "small");
  await assert.rejects(limitedBody(new Request("https://test.invalid", { method: "POST", body: "x".repeat(1025) })));
  await assert.rejects(limitedBody(new Request("https://test.invalid", { method: "POST", headers: { "content-length": "2000" }, body: "small" })));
});
