import test from "node:test";
import assert from "node:assert/strict";
import type { Session } from "../src/lib/auth.ts";
import {
  handlePasskeyProofHttp, type ProofHttpPhase, type ProofHttpPorts, type ProofHttpRequests,
} from "../src/lib/passkey-action-proof-http.ts";

const NOW = 1_800_000_000, ORIGIN = "https://cockpit.local.test:8443";
const accountId = "11111111-1111-1111-1111-111111111111";
const connectionId = "22222222-2222-2222-2222-222222222222";
const attemptId = "33333333-3333-3333-3333-333333333333";
const grantId = "44444444-4444-4444-4444-444444444444";
const tenantId = "55555555-5555-5555-5555-555555555555";
const token = Buffer.alloc(32, 6).toString("base64url"), csrf = Buffer.alloc(32, 7).toString("base64url");
const challenge = Buffer.alloc(32, 8).toString("base64url");
const credentialId = Buffer.alloc(16, 9).toString("base64url");
const PRIVATE = "PRIVATE_VALUE_NOT_FOR_BROWSER";
const session: Session = {
  issuer: "https://auth.local.test:8443", subject: "opaque-subject", oidcAuthTime: NOW - 600,
  tenantId, authEpoch: 2, expiresAt: NOW + 1800, displayName: "Test", tenantName: "Test", csrf,
};
const target = { action: "register", platform_account_id: accountId, connection_id: connectionId };
function startResult() {
  return { attempt_id: attemptId, confirmation_token: token,
    options: { rpId: "cockpit.local.test", challenge, allowCredentials: [{ id: credentialId, type: "public-key" }],
      timeout: 120_000, userVerification: "required", extensions: undefined },
    preview: { target: { ...target }, accountName: "Testkonto", expiresAt: NOW + 120, execution_enabled: false } };
}
function grantResult() {
  return { target: { ...target }, accountName: "Testkonto", checkedAt: NOW,
    expiresAt: NOW + 120, confirmationToken: token, execution_enabled: false };
}
function validInput<P extends ProofHttpPhase>(phase: P): ProofHttpRequests[P] {
  return (phase === "start" ? { platform_account_id: accountId, action: "register" }
    : phase === "finish" ? { attempt_id: attemptId, credential: { synthetic: true }, confirmation_token: token }
      : { grant_id: grantId, confirmation_token: token }) as ProofHttpRequests[P];
}
function result(phase: ProofHttpPhase): unknown {
  return phase === "start" ? startResult()
    : phase === "finish" ? { grant_id: grantId, grant: grantResult() }
      : phase === "grant" ? grantResult()
        : { status: "verified", execution_enabled: false, action: "register", platform_account_id: accountId };
}
function fixture<P extends ProofHttpPhase>(phase: P) {
  const calls: ProofHttpRequests[P][] = [];
  const reads = { session: 0, origin: 0, enabled: 0 };
  const ports: ProofHttpPorts<P> = {
    enabled: () => { reads.enabled++; return true; },
    origin: async () => { reads.origin++; return ORIGIN; },
    session: async () => { reads.session++; return { ...session }; },
    execute: async (value, authorized) => {
      assert.deepEqual(authorized, session);
      assert(Object.isFrozen(authorized), "CSRF authority is an immutable snapshot supplied to the proof core");
      calls.push(value); return result(phase);
    },
    now: () => NOW,
  };
  return { ports, calls, reads };
}
function request(phase: ProofHttpPhase, options: {
  method?: string; wire?: string; headers?: Record<string, string | null>;
} = {}): Request {
  const headers = new Headers({ Origin: ORIGIN, "Sec-Fetch-Site": "same-origin",
    "X-CSRF-Token": csrf, "Content-Type": "application/json" });
  for (const [name, value] of Object.entries(options.headers ?? {})) {
    if (value === null) headers.delete(name); else headers.set(name, value);
  }
  return new Request(`${ORIGIN}/api/passkeys/actions/${phase}`, {
    method: options.method ?? "POST", headers,
    ...((options.method ?? "POST") !== "GET" ? { body: options.wire ?? JSON.stringify(validInput(phase)) } : {}),
  });
}
async function denied<P extends ProofHttpPhase>(
  phase: P, req: Request, ports?: ProofHttpPorts<P>, status = 400,
) {
  const f = fixture(phase), response = await handlePasskeyProofHttp(req, phase, ports ?? f.ports);
  assert.equal(response.status, status);
  assert.equal(response.headers.get("cache-control"), "no-store");
  assert.deepEqual(Object.keys(await response.json()), ["error"]);
  assert.equal(f.calls.length, 0);
  return f;
}

for (const phase of ["start", "finish", "grant", "confirm"] as const) {
  test(`${phase}: valid browser POST projects only the proof-only response`, async () => {
    const f = fixture(phase), response = await handlePasskeyProofHttp(request(phase), phase, f.ports);
    assert.equal(response.status, 200);
    assert.equal(response.headers.get("cache-control"), "no-store");
    assert.equal(response.headers.get("x-content-type-options"), "nosniff");
    assert.equal(f.calls.length, 1);
    assert.deepEqual(f.calls[0], validInput(phase));
    const expected: unknown = JSON.parse(JSON.stringify(result(phase)));
    assert.deepEqual(await response.json(), expected);
    assert.equal(f.reads.session, 3);
    assert.equal(f.reads.origin, 3);
  });
  test(`${phase}: disabled preview performs no origin, session or proof operation`, async () => {
    const f = fixture(phase);
    const response = await handlePasskeyProofHttp(request(phase), phase, { ...f.ports, enabled: () => false });
    assert.equal(response.status, 503);
    assert.equal(response.headers.get("cache-control"), "no-store");
    assert.equal(f.calls.length, 0);
    assert.deepEqual(f.reads, { enabled: 0, origin: 0, session: 0 });
  });
  test(`${phase}: browser GET cannot use a proof operation or cache its tokens`, async () => {
    const f = fixture(phase), response = await handlePasskeyProofHttp(request(phase, { method: "GET" }), phase, f.ports);
    assert.equal(response.status, 405);
    assert.equal(response.headers.get("allow"), "POST");
    assert.equal(response.headers.get("cache-control"), "no-store");
    assert.equal(f.calls.length, 0);
    assert.deepEqual(f.reads, { enabled: 0, origin: 0, session: 0 });
  });
  test(`${phase}: origin and Fetch Metadata checks precede cookie or proof reads`, async () => {
    const cases: Record<string, string | null>[] = [{ Origin: null }, { Origin: "https://attacker.test" },
      { Origin: `${ORIGIN}/` }, { Origin: "null" }, { "Sec-Fetch-Site": null },
      { "Sec-Fetch-Site": "cross-site" }, { "Sec-Fetch-Site": "same-site" }, { "Sec-Fetch-Site": "none" }];
    for (const headers of cases) {
      const f = fixture(phase);
      const response = await handlePasskeyProofHttp(request(phase, { headers }), phase, f.ports);
      assert.equal(response.status, 403);
      assert.equal(f.calls.length, 0);
      assert.equal(f.reads.session, 0);
    }
  });
  test(`${phase}: an absent session does not dispatch or parse a proof`, async () => {
    const f = fixture(phase);
    const response = await handlePasskeyProofHttp(request(phase), phase, { ...f.ports, session: async () => null });
    assert.equal(response.status, 401);
    assert.equal(f.calls.length, 0);
  });
  test(`${phase}: absent or foreign CSRF cannot claim a prepared attempt`, async () => {
    for (const value of [null, token, "", "invalid"]) {
      const f = fixture(phase);
      const response = await handlePasskeyProofHttp(request(phase, { headers: { "X-CSRF-Token": value } }), phase, f.ports);
      assert.equal(response.status, 403);
      assert.equal(f.calls.length, 0);
      assert.equal(f.reads.session, 1);
    }
  });
  test(`${phase}: input media type, duplicate keys and added identities fail before side effects`, async () => {
    for (const header of [null, "text/plain", "application/x-www-form-urlencoded"]) {
      await denied(phase, request(phase, { headers: { "Content-Type": header } }));
    }
    const good = JSON.stringify(validInput(phase));
    const key = phase === "start" ? "action" : "confirmation_token";
    const escaped = phase === "start" ? "\\u0061ction" : "\\u0063onfirmation_token";
    const value = phase === "start" ? "register" : token;
    for (const wire of ["[]", "null", "", "{", `${good.slice(0, -1)},"tenant_id":"${tenantId}"}`,
      `${good.slice(0, -1)},"${key}":"${value}"}`, `${good.slice(0, -1)},"${escaped}":"${value}"}`]) {
      await denied(phase, request(phase, { wire }));
    }
  });
  test(`${phase}: declared and actual oversize bodies cannot reach a proof`, async () => {
    const f = fixture(phase), size = phase === "finish" ? 16_384 : 1024;
    const oversized = request(phase, { wire: " ".repeat(size + 1) });
    assert.equal((await handlePasskeyProofHttp(oversized, phase, f.ports)).status, 400);
    assert.equal(f.calls.length, 0);
    for (const length of [String(size + 1), "-1", "NaN"]) {
      await denied(phase, request(phase, { headers: { "Content-Length": length } }));
    }
  });
  test(`${phase}: a session change during body reading cannot reach a proof`, async () => {
    for (const patch of [{ csrf: token }, { issuer: "https://other.test" }, { subject: "other-subject" },
      { tenantId: accountId }, { authEpoch: 3 }, { oidcAuthTime: NOW - 599 }, { expiresAt: NOW + 1200 }]) {
      const f = fixture(phase);
      let reads = 0;
      const response = await handlePasskeyProofHttp(request(phase), phase, { ...f.ports,
        session: async () => ({ ...session, ...(reads++ > 0 ? patch : {}) }) });
      assert.equal(response.status, 400);
      assert.equal(f.calls.length, 0);
    }
  });
  test(`${phase}: expiration, gate closure or origin change after body reading cannot dispatch`, async () => {
    for (const mutation of ["expired", "disabled", "origin", "logout"] as const) {
      const f = fixture(phase);
      let sessionReads = 0, originReads = 0, gateReads = 0;
      const response = await handlePasskeyProofHttp(request(phase), phase, { ...f.ports,
        session: async () => { sessionReads++; return mutation === "logout" && sessionReads > 1 ? null : { ...session }; },
        now: () => mutation === "expired" && sessionReads > 1 ? session.expiresAt : NOW,
        origin: async () => mutation === "origin" && originReads++ > 0 ? "https://other.test" : ORIGIN,
        enabled: () => !(mutation === "disabled" && gateReads++ > 0),
      });
      assert.equal(response.status, 400);
      assert.equal(f.calls.length, 0);
    }
  });
  test(`${phase}: thrown internal errors never expose private values or credentials`, async () => {
    const f = fixture(phase);
    const response = await handlePasskeyProofHttp(request(phase), phase, { ...f.ports,
      execute: async () => { throw new Error(`${PRIVATE}:${token}:${challenge}`); } });
    assert.equal(response.status, 400);
    const wire = await response.text();
    for (const value of [PRIVATE, token, challenge, attemptId, grantId]) assert.ok(!wire.includes(value));
  });
  test(`${phase}: session, origin or feature changes during execute never publish a receipt`, async () => {
    for (const mutation of ["session", "expired", "origin", "disabled", "logout"] as const) {
      const f = fixture(phase);
      let finished = false;
      const response = await handlePasskeyProofHttp(request(phase), phase, { ...f.ports,
        execute: async () => { finished = true; return result(phase); },
        session: async () => finished && mutation === "logout" ? null
          : { ...session, ...(finished && mutation === "session" ? { csrf: token } : {}) },
        origin: async () => finished && mutation === "origin" ? "https://other.test" : ORIGIN,
        enabled: () => !(finished && mutation === "disabled"),
        now: () => finished && mutation === "expired" ? session.expiresAt : NOW,
      });
      assert.equal(response.status, 400);
      assert(finished);
      const wire = await response.text();
      assert.ok(!wire.includes(token)); assert.ok(!wire.includes(grantId));
    }
  });
  test(`${phase}: public projection refuses accidental internal response fields`, async () => {
    const f = fixture(phase);
    const response = await handlePasskeyProofHttp(request(phase), phase, { ...f.ports,
      execute: async () => ({ ...(result(phase) as Record<string, unknown>), public_key: PRIVATE }) });
    assert.equal(response.status, 400);
    assert.ok(!(await response.text()).includes(PRIVATE));
  });
}

test("start: action and account are canonical, with no free connection or tenant choice", async () => {
  for (const body of [{ platform_account_id: "AAAA1111-1111-1111-1111-111111111111", action: "register" },
    { platform_account_id: "invalid", action: "register" }, { platform_account_id: accountId, action: "transfer" },
    { platform_account_id: accountId, action: "register", connection_id: connectionId },
    { platform_account_id: accountId }, { action: "register" }]) {
    await denied("start", request("start", { wire: JSON.stringify(body) }));
  }
});
test("finish: structurally malformed credential still reaches committed-claim orchestration", async () => {
  const f = fixture("finish");
  let received: unknown;
  const response = await handlePasskeyProofHttp(request("finish", { wire: JSON.stringify({
    attempt_id: attemptId, confirmation_token: token, credential: null,
  }) }), "finish", { ...f.ports, execute: async input => { received = input.credential; throw new Error("CRYPTO_REJECTED"); } });
  assert.equal(response.status, 400);
  assert.equal(received, null);
});
test("finish: nested duplicate keys and excessive depth cannot reach committed claim", async () => {
  await denied("finish", request("finish", { wire: `{"attempt_id":"${attemptId}","confirmation_token":"${token}","credential":{"response":{"signature":"a","\\u0073ignature":"b"}}}` }));
  await denied("finish", request("finish", { wire: JSON.stringify({ attempt_id: attemptId,
    confirmation_token: token, credential: { a: { b: { c: { d: { e: {} } } } } } }) }));
});
for (const phase of ["finish", "grant", "confirm"] as const) {
  test(`${phase}: proof IDs and preview tokens reject noncanonical spellings before dispatch`, async () => {
    for (const value of [token + "=", token.slice(0, -1), "x".repeat(43), 1, null]) {
      await denied(phase, request(phase, { wire: JSON.stringify({ ...validInput(phase), confirmation_token: value }) }));
    }
    await denied(phase, request(phase, { wire: JSON.stringify({ ...validInput(phase),
      [phase === "finish" ? "attempt_id" : "grant_id"]: "unknown" }) }));
  });
}
test("start: frozen preview target must match requested account and action", async () => {
  for (const patch of [{ platform_account_id: tenantId }, { action: "revoke", expected_revision: 1, expected_storage: 1 }]) {
    const f = fixture("start"), responseValue = startResult();
    Object.assign(responseValue.preview.target, patch);
    const response = await handlePasskeyProofHttp(request("start"), "start", {
      ...f.ports, execute: async () => responseValue,
    });
    assert.equal(response.status, 400);
  }
});
test("start: options must bind HTTPS RP, UV, one credential and bounded challenge", async () => {
  for (const patch of [{ rpId: "attacker.test" }, { userVerification: "preferred" },
    { timeout: 120_001 }, { timeout: 0 }, { challenge: "short" },
    { allowCredentials: [] }, { extensions: { secret: PRIVATE } },
    { allowCredentials: [{ id: credentialId, type: "public-key", public_key: PRIVATE }] }]) {
    const f = fixture("start"), responseValue = startResult();
    Object.assign(responseValue.options, patch);
    const response = await handlePasskeyProofHttp(request("start"), "start", {
      ...f.ports, execute: async () => responseValue,
    });
    assert.equal(response.status, 400);
    assert.ok(!(await response.text()).includes(PRIVATE));
  }
});
test("start: expired or execution-enabled preview cannot be published", async () => {
  for (const patch of [{ expiresAt: NOW }, { expiresAt: NOW + 121 }, { execution_enabled: true }]) {
    const f = fixture("start"), responseValue = startResult();
    Object.assign(responseValue.preview, patch);
    assert.equal((await handlePasskeyProofHttp(request("start"), "start", {
      ...f.ports, execute: async () => responseValue,
    })).status, 400);
  }
});
for (const phase of ["finish", "grant"] as const) {
  test(`${phase}: wrong preview token, time, execution flag or private grant cannot publish`, async () => {
    for (const patch of [{ confirmationToken: csrf }, { checkedAt: NOW + 1 },
      { expiresAt: NOW }, { expiresAt: NOW + 121 }, { execution_enabled: true }, { confirmation_hash: PRIVATE }]) {
      const f = fixture(phase), badGrant = Object.assign(grantResult(), patch);
      const response = await handlePasskeyProofHttp(request(phase), phase, {
        ...f.ports, execute: async () => phase === "finish" ? { grant_id: grantId, grant: badGrant } : badGrant,
      });
      assert.equal(response.status, 400);
      assert.ok(!(await response.text()).includes(PRIVATE));
    }
  });
}
test("confirm: no executed, execution-enabled or private receipt reaches the browser", async () => {
  for (const patch of [{ status: "executed" }, { execution_enabled: true }, { credential_id: PRIVATE },
    { action: "transfer" }, { platform_account_id: "other" }]) {
    const f = fixture("confirm");
    assert.equal((await handlePasskeyProofHttp(request("confirm"), "confirm", {
      ...f.ports, execute: async () => ({ ...(result("confirm") as Record<string, unknown>), ...patch }),
    })).status, 400);
  }
});
