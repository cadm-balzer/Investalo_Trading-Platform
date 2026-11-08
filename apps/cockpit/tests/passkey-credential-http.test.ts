import test from "node:test";
import assert from "node:assert/strict";
import type { Session } from "../src/lib/auth.ts";
import type { ProofSession } from "../src/lib/passkey-action-proof-state.ts";
import { handlePasskeyCredentialHttp } from "../src/lib/passkey-credential-http.ts";

// Synthetic browser HTTP fixtures only; no broker credentials or issued proof.
const NOW = 1_800_000_000, ORIGIN = "https://cockpit.local.test:8443";
const accountId = "11111111-1111-1111-1111-111111111111";
const connectionId = "22222222-2222-2222-2222-222222222222";
const tenantId = "55555555-5555-5555-5555-555555555555";
const token = Buffer.alloc(32, 6).toString("base64url");
const grantToken = Buffer.alloc(32, 11).toString("base64url");
const csrf = Buffer.alloc(32, 7).toString("base64url");
const handle = Buffer.alloc(32, 10).toString("base64url");
const challenge = Buffer.alloc(32, 8).toString("base64url");
const credentialId = Buffer.alloc(16, 9).toString("base64url");
const PRIVATE = "SYNTHETIC_PRIVATE_VALUE_NOT_FOR_RESPONSE";
const credentials = { api_key: `${PRIVATE}-key`, secret: `${PRIVATE}-secret`, passphrase: `${PRIVATE}-phrase` };
const session: Session = {
  issuer: "https://auth.local.test:8443", subject: "opaque-subject", oidcAuthTime: NOW - 600,
  tenantId, authEpoch: 2, expiresAt: NOW + 1800, displayName: "Test", tenantName: "Test", csrf,
};
const bound: ProofSession = { handle, origin: ORIGIN, session };
const target = { action: "register", platform_account_id: accountId, connection_id: connectionId };
const consent = { kind: "credential-write", confirmed: true };
const body = JSON.stringify({ platform_account_id: accountId, connection_id: connectionId, credentials });
type Phase = "start" | "finish" | "execute";
type Ports = {
  enabled(): boolean;
  origin(): Promise<string>;
  session(): Promise<ProofSession | null>;
  execute(input: unknown, authorized: ProofSession): Promise<unknown>;
  now(): number;
};
function copyBound(patch: Partial<Session> = {}, extra: Partial<ProofSession> = {}): ProofSession {
  return { ...bound, ...extra, session: { ...session, ...patch } };
}
function startResult() {
  return { flow_token: token,
    options: { rpId: "cockpit.local.test", challenge, allowCredentials: [{ id: credentialId, type: "public-key" }],
      timeout: 120_000, userVerification: "required" },
    preview: { target: { ...target }, accountName: "Testkonto", expiresAt: NOW + 120, execution_enabled: false } };
}
function finishResult() {
  return { flow_token: grantToken, grant: { target: { ...target }, accountName: "Testkonto",
    checkedAt: NOW, expiresAt: NOW + 120, execution_enabled: false } };
}
function validInput(phase: Phase): Record<string, unknown> {
  return phase === "start" ? { platform_account_id: accountId, action: "register", credentials: { ...credentials } }
    : phase === "finish" ? { flow_token: token, credential: { synthetic: true } }
      : { flow_token: token, body, consent: { ...consent } };
}
function result(phase: Phase): unknown {
  return phase === "start" ? startResult() : phase === "finish" ? finishResult()
    : { connection_id: connectionId, credential_revision: 1, storage_version: 1, status: "active" };
}
function fixture(phase: Phase) {
  const calls: unknown[] = [];
  const reads = { session: 0, origin: 0, enabled: 0 };
  const ports: Ports = {
    enabled: () => { reads.enabled++; return true; },
    origin: async () => { reads.origin++; return ORIGIN; },
    session: async () => { reads.session++; return copyBound(); },
    execute: async (input, authorized) => {
      assert.deepEqual(authorized, bound);
      assert(Object.isFrozen(authorized));
      assert(Object.isFrozen(authorized.session));
      calls.push(input);
      return result(phase);
    },
    now: () => NOW,
  };
  return { ports, calls, reads };
}
function request(phase: Phase, options: {
  method?: string; wire?: string | Uint8Array<ArrayBuffer>; headers?: Record<string, string | null>;
} = {}): Request {
  const headers = new Headers({ Origin: ORIGIN, "Sec-Fetch-Site": "same-origin",
    "X-CSRF-Token": csrf, "Content-Type": "application/json" });
  for (const [name, value] of Object.entries(options.headers ?? {})) {
    if (value === null) headers.delete(name); else headers.set(name, value);
  }
  const method = options.method ?? "POST";
  return new Request(`${ORIGIN}/api/credentials/passkey/${phase}`, {
    method, headers, ...(method !== "GET" ? { body: options.wire ?? JSON.stringify(validInput(phase)) } : {}),
  });
}
function watchBody(req: Request) {
  const original = req.body;
  const reads = { body: 0 };
  Object.defineProperty(req, "body", { get() { reads.body++; return original; } });
  return reads;
}
async function rejected(phase: Phase, req: Request, ports?: Ports, status = 400) {
  const f = fixture(phase);
  const response = await handlePasskeyCredentialHttp(req, phase, ports ?? f.ports);
  assert.equal(response.status, status);
  assert.equal(response.headers.get("cache-control"), "no-store");
  assert.equal(response.headers.get("x-content-type-options"), "nosniff");
  const wire = await response.text();
  assert.deepEqual(Object.keys(JSON.parse(wire)), ["error"]);
  assert(!wire.includes(PRIVATE)); assert(!wire.includes(token)); assert(!wire.includes(body));
  assert.equal(f.calls.length, 0);
  return { response, wire };
}

for (const phase of ["start", "finish", "execute"] as const) {
  test(`${phase}: credential HTTP POST preserves original authority and returns only safe fields`, async () => {
    const f = fixture(phase);
    const response = await handlePasskeyCredentialHttp(request(phase), phase, f.ports);
    assert.equal(response.status, 200);
    assert.equal(response.headers.get("cache-control"), "no-store");
    assert.equal(response.headers.get("x-content-type-options"), "nosniff");
    assert.deepEqual(f.calls, [validInput(phase)]);
    const wire = await response.text();
    assert.deepEqual(JSON.parse(wire), result(phase));
    assert(!wire.includes(PRIVATE));
    assert(!wire.includes(session.subject)); assert(!wire.includes(session.issuer));
    assert(f.reads.session >= 3); assert(f.reads.origin >= 3);
  });
  test(`${phase}: disabled capability never reads private input, identity or provider`, async () => {
    const f = fixture(phase), req = request(phase), watched = watchBody(req);
    const response = await handlePasskeyCredentialHttp(req, phase, { ...f.ports, enabled: () => false });
    assert.equal(response.status, 503);
    assert.equal(watched.body, 0); assert.equal(f.calls.length, 0);
    assert.equal(f.reads.session, 0); assert.equal(f.reads.origin, 0);
  });
  test(`${phase}: native GET fallback cannot disclose or operate on credentials`, async () => {
    const f = fixture(phase), req = request(phase, { method: "GET" }), watched = watchBody(req);
    const response = await handlePasskeyCredentialHttp(req, phase, f.ports);
    assert.equal(response.status, 405); assert.equal(response.headers.get("allow"), "POST");
    assert.equal(response.headers.get("cache-control"), "no-store");
    assert.equal(watched.body, 0); assert.equal(f.calls.length, 0);
    assert.equal(f.reads.session, 0); assert.equal(f.reads.origin, 0);
  });
  test(`${phase}: Origin and Fetch Metadata reject before session or secret-body reads`, async () => {
    const cases: Record<string, string | null>[] = [{ Origin: null }, { Origin: `${ORIGIN}/` }, { Origin: "https://attacker.test" },
      { Origin: "null" }, { "Sec-Fetch-Site": null }, { "Sec-Fetch-Site": "cross-site" },
      { "Sec-Fetch-Site": "same-site" }, { "Sec-Fetch-Site": "none" }];
    for (const headers of cases) {
      const f = fixture(phase), req = request(phase, { headers }), watched = watchBody(req);
      const response = await handlePasskeyCredentialHttp(req, phase, f.ports);
      assert.equal(response.status, 403);
      assert.equal(f.reads.session, 0); assert.equal(watched.body, 0); assert.equal(f.calls.length, 0);
    }
  });
  test(`${phase}: missing session or CSRF cannot parse input or claim a continuation`, async () => {
    const f = fixture(phase), req = request(phase), watched = watchBody(req);
    assert.equal((await handlePasskeyCredentialHttp(req, phase, { ...f.ports, session: async () => null })).status, 401);
    assert.equal(watched.body, 0); assert.equal(f.calls.length, 0);
    for (const value of [null, "", "invalid", token]) {
      const x = fixture(phase), other = request(phase, { headers: { "X-CSRF-Token": value } }), read = watchBody(other);
      assert.equal((await handlePasskeyCredentialHttp(other, phase, x.ports)).status, 403);
      assert.equal(read.body, 0); assert.equal(x.calls.length, 0);
    }
  });
  test(`${phase}: input type, duplicate keys and added identity fields fail before dispatch`, async () => {
    for (const media of [null, "text/plain", "application/x-www-form-urlencoded",
      "application/json; charset=iso-8859-1", "application/json; charset=utf-8; other=1"]) {
      await rejected(phase, request(phase, { headers: { "Content-Type": media } }));
    }
    const good = JSON.stringify(validInput(phase));
    const field = phase === "start" ? "action" : "flow_token";
    const escaped = phase === "start" ? "\\u0061ction" : "\\u0066low_token";
    const value = phase === "start" ? "register" : token;
    for (const wire of ["", "{", "null", "[]", `${good.slice(0, -1)},"tenant_id":"${tenantId}"}`,
      `${good.slice(0, -1)},"${field}":"${value}"}`, `${good.slice(0, -1)},"${escaped}":"${value}"}`]) {
      await rejected(phase, request(phase, { wire }));
    }
  });
  test(`${phase}: fatal UTF8, compressed input and bounded bodies reject without secret replacement`, async () => {
    const slot = phase === "finish" ? "SYNTHETIC_UTF8_SLOT" : PRIVATE;
    const good = JSON.stringify({ ...validInput(phase), ...(phase === "finish" ? { credential: slot } : {}) });
    const at = good.indexOf(slot);
    assert(at >= 0);
    // Replacement decoding would leave an otherwise valid request. Rejection
    // therefore proves malformed original UTF8 is not silently repaired.
    const malformed = new Uint8Array(Buffer.concat([Buffer.from(good.slice(0, at)),
      Buffer.from([0xc0, 0xaf]), Buffer.from(good.slice(at + slot.length))]));
    await rejected(phase, request(phase, { wire: malformed }));
    for (const coding of ["gzip", "br", "identity"]) {
      await rejected(phase, request(phase, { headers: { "Content-Encoding": coding } }));
    }
    await rejected(phase, request(phase, { wire: " ".repeat(16_385) }));
    for (const length of ["16385", "-1", "NaN", "1", "4096"]) {
      await rejected(phase, request(phase, { headers: { "Content-Length": length } }));
    }
  });
  test(`${phase}: expired or rotated authority after body reading cannot dispatch`, async () => {
    for (const mutation of [
      { session: { csrf: token } }, { session: { issuer: "https://other.test" } },
      { session: { subject: "other-subject" } }, { session: { tenantId: accountId } },
      { session: { authEpoch: 3 } }, { session: { oidcAuthTime: NOW - 599 } },
      { session: { expiresAt: NOW + 1200 } }, { extra: { handle: token } },
      { extra: { origin: "https://other.test" } },
    ]) {
      const f = fixture(phase);
      let reads = 0;
      const response = await handlePasskeyCredentialHttp(request(phase), phase, { ...f.ports,
        session: async () => reads++ > 0 ? copyBound(mutation.session, mutation.extra) : copyBound() });
      assert.equal(response.status, 400); assert.equal(f.calls.length, 0);
    }
    for (const mutation of ["expired", "disabled", "origin", "logout"] as const) {
      const f = fixture(phase);
      let reads = 0, origins = 0, gates = 0;
      const response = await handlePasskeyCredentialHttp(request(phase), phase, { ...f.ports,
        session: async () => { reads++; return mutation === "logout" && reads > 1 ? null : copyBound(); },
        now: () => mutation === "expired" && reads > 1 ? session.expiresAt : NOW,
        origin: async () => mutation === "origin" && origins++ > 0 ? "https://other.test" : ORIGIN,
        enabled: () => !(mutation === "disabled" && gates++ > 0) });
      assert.equal(response.status, 400); assert.equal(f.calls.length, 0);
    }
  });
  test(`${phase}: authority lost during execution never publishes a successful receipt`, async () => {
    for (const mutation of ["handle", "csrf", "oidc", "expired", "origin", "disabled", "logout"] as const) {
      const f = fixture(phase);
      let completed = false, executions = 0;
      const response = await handlePasskeyCredentialHttp(request(phase), phase, { ...f.ports,
        execute: async () => { executions++; completed = true; return result(phase); },
        session: async () => completed && mutation === "logout" ? null
          : copyBound(completed && mutation === "csrf" ? { csrf: token }
            : completed && mutation === "oidc" ? { oidcAuthTime: NOW - 599 } : {},
          completed && mutation === "handle" ? { handle: token } : {}),
        origin: async () => completed && mutation === "origin" ? "https://other.test" : ORIGIN,
        enabled: () => !(completed && mutation === "disabled"),
        now: () => completed && mutation === "expired" ? session.expiresAt : NOW });
      assert.equal(response.status, 400); assert.equal(executions, 1);
      const wire = await response.text();
      assert(!wire.includes(token)); assert(!wire.includes(PRIVATE));
    }
  });
  test(`${phase}: provider errors and accidental secret-bearing results stay static with no retry`, async () => {
    for (const value of ["throw", "extra"] as const) {
      const f = fixture(phase);
      let executions = 0;
      const response = await handlePasskeyCredentialHttp(request(phase), phase, { ...f.ports,
        execute: async () => {
          executions++;
          if (value === "throw") throw new Error(`${PRIVATE}:${token}:${challenge}`);
          return { ...(result(phase) as Record<string, unknown>), private_key: PRIVATE };
        } });
      assert.equal(response.status, 400); assert.equal(executions, 1);
      const wire = await response.text();
      for (const forbidden of [PRIVATE, token, challenge, connectionId, session.subject]) assert(!wire.includes(forbidden));
      assert.deepEqual(Object.keys(JSON.parse(wire)), ["error"]);
    }
  });
}

test("a session rotation during the final Origin await cannot authorize credential dispatch", async () => {
  for (const phase of ["start", "finish", "execute"] as const) {
    for (const rotated of [copyBound({}, { handle: token }), copyBound({ authEpoch: 3 }),
      copyBound({ oidcAuthTime: NOW - 599 })]) {
      const f = fixture(phase);
      let live = copyBound(), origins = 0;
      let enterOrigin!: () => void, releaseOrigin!: () => void;
      const entered = new Promise<void>(resolve => { enterOrigin = resolve; });
      const released = new Promise<void>(resolve => { releaseOrigin = resolve; });
      const pending = handlePasskeyCredentialHttp(request(phase), phase, { ...f.ports,
        session: async () => live,
        origin: async () => {
          if (++origins === 2) { enterOrigin(); await released; }
          return ORIGIN;
        } });
      await entered;
      assert.equal(f.calls.length, 0, "The operation has not started while Origin resolution is pending.");
      live = rotated;
      releaseOrigin();
      const response = await pending;
      assert.equal(response.status, 400);
      assert.equal(origins, 2);
      assert.equal(f.calls.length, 0, "Origin completion must be followed by a current-session check.");
      assert.deepEqual(Object.keys(await response.json()), ["error"]);
    }
  }
});

test("a session rotation during the final response Origin await withholds the successful receipt", async () => {
  for (const phase of ["start", "finish", "execute"] as const) {
    for (const rotated of [copyBound({}, { handle: token }), copyBound({ authEpoch: 3 }),
      copyBound({ oidcAuthTime: NOW - 599 })]) {
      const f = fixture(phase);
      let live = copyBound(), origins = 0;
      let enterOrigin!: () => void, releaseOrigin!: () => void;
      const entered = new Promise<void>(resolve => { enterOrigin = resolve; });
      const released = new Promise<void>(resolve => { releaseOrigin = resolve; });
      const pending = handlePasskeyCredentialHttp(request(phase), phase, { ...f.ports,
        session: async () => live,
        origin: async () => {
          if (++origins === 3) { enterOrigin(); await released; }
          return ORIGIN;
        } });
      await entered;
      assert.equal(f.calls.length, 1, "The operation completed before the response authority check.");
      live = rotated;
      releaseOrigin();
      const response = await pending;
      assert.equal(response.status, 400);
      assert.equal(origins, 3);
      assert.equal(f.calls.length, 1, "Withholding an uncertain receipt must not retry the operation.");
      const wire = await response.text();
      assert.deepEqual(Object.keys(JSON.parse(wire)), ["error"]);
      for (const forbidden of [PRIVATE, token, grantToken, connectionId]) assert(!wire.includes(forbidden));
    }
  }
});

test("a concurrently delivered session invalidation cannot fall between the guard and dispatch", async () => {
  for (const phase of ["start", "finish", "execute"] as const) {
    const f = fixture(phase);
    let live = copyBound(), reads = 0, dispatchAfterInvalidation = false;
    const response = await handlePasskeyCredentialHttp(request(phase), phase, { ...f.ports,
      execute: async (input, authorized) => {
        dispatchAfterInvalidation = live.handle === token;
        return f.ports.execute(input, authorized);
      },
      session: async () => {
        const snapshot = live;
        if (++reads === 2) {
          // Simulate another pending request delivering its session invalidation
          // after this lookup resolves, before this request resumes dispatch.
          queueMicrotask(() => queueMicrotask(() => { live = copyBound({}, { handle: token }); }));
        }
        return snapshot;
      } });
    assert.equal(live.handle, token);
    assert.equal(response.status, 400);
    assert.equal(dispatchAfterInvalidation, false,
      "Dispatch may precede invalidation, but must never follow an already rotated session.");
    assert(f.calls.length <= 1);
    assert.deepEqual(Object.keys(await response.json()), ["error"]);
  }
});

test("a concurrently delivered session invalidation cannot fall between the guard and receipt", async () => {
  for (const phase of ["start", "finish", "execute"] as const) {
    const f = fixture(phase);
    let live = copyBound(), reads = 0, resultProjectionAfterInvalidation = false;
    const response = await handlePasskeyCredentialHttp(request(phase), phase, { ...f.ports,
      now: () => {
        if (live.session.authEpoch === 3) resultProjectionAfterInvalidation = true;
        return NOW;
      },
      session: async () => {
        const snapshot = live;
        if (++reads === 3) {
          queueMicrotask(() => queueMicrotask(() => { live = copyBound({ authEpoch: 3 }); }));
        }
        return snapshot;
      } });
    assert.equal(live.session.authEpoch, 3);
    assert(!(response.status === 200 && resultProjectionAfterInvalidation),
      "A receipt may precede invalidation, but cannot be projected after the live session rotated.");
    assert.equal(f.calls.length, 1);
    if (response.status === 400) {
      const wire = await response.text();
      assert.deepEqual(Object.keys(JSON.parse(wire)), ["error"]);
      for (const forbidden of [PRIVATE, token, grantToken, connectionId]) assert(!wire.includes(forbidden));
    }
  }
});

test("start: register/replace require an exact bounded triple while revoke forbids all credential input", async () => {
  const invalid: unknown[] = [
    { platform_account_id: accountId, action: "register" },
    { platform_account_id: accountId, action: "replace" },
    { platform_account_id: accountId, action: "register", credentials: null },
    { platform_account_id: accountId, action: "revoke", credentials },
    { platform_account_id: accountId, action: "register", credentials: { ...credentials, uid: PRIVATE } },
    { platform_account_id: accountId, action: "register", credentials: { api_key: "", secret: "fixture", passphrase: "fixture" } },
    { platform_account_id: accountId, action: "register", credentials: { ...credentials, api_key: "\ud800" } },
    { platform_account_id: accountId, action: "register", credentials: { ...credentials, secret: "x".repeat(1025) } },
    { platform_account_id: accountId, action: "register", credentials: { ...credentials, passphrase: "line\nbreak" } },
    { platform_account_id: accountId, action: "register", connection_id: connectionId, credentials },
    { platform_account_id: "INVALID", action: "register", credentials },
    { platform_account_id: accountId, action: "transfer", credentials },
  ];
  for (const input of invalid) await rejected("start", request("start", { wire: JSON.stringify(input) }));
});

test("start: closed response projection rejects forged account, action, expiry and passkey options", async () => {
  const cases = [
    { ...startResult(), flow_token: "bad" },
    { ...startResult(), preview: { ...startResult().preview, target: { ...target, platform_account_id: tenantId } } },
    { ...startResult(), preview: { ...startResult().preview, execution_enabled: true } },
    { ...startResult(), preview: { ...startResult().preview, expiresAt: NOW } },
    { ...startResult(), preview: { ...startResult().preview, expiresAt: NOW + 121 } },
    { ...startResult(), options: { ...startResult().options, rpId: "other.test" } },
    { ...startResult(), options: { ...startResult().options, userVerification: "preferred" } },
    { ...startResult(), options: { ...startResult().options, challenge: "bad" } },
    { ...startResult(), options: { ...startResult().options, allowCredentials: [] } },
    { ...startResult(), options: { ...startResult().options, timeout: 120_001 } },
    { ...startResult(), options: { ...startResult().options, private_key: PRIVATE } },
  ];
  for (const value of cases) {
    const f = fixture("start");
    const response = await handlePasskeyCredentialHttp(request("start"), "start", { ...f.ports, execute: async () => value });
    assert.equal(response.status, 400); assert(!(await response.text()).includes(PRIVATE));
  }
});

test("finish: assertion content is claimed by orchestration, not prevalidated as proof by HTTP", async () => {
  for (const credential of [null, "malformed", {}, { secret: PRIVATE }]) {
    const f = fixture("finish");
    const response = await handlePasskeyCredentialHttp(
      request("finish", { wire: JSON.stringify({ flow_token: token, credential }) }), "finish", f.ports);
    assert.equal(response.status, 200);
    assert.deepEqual(f.calls, [{ flow_token: token, credential }]);
    assert(!(await response.text()).includes(PRIVATE));
  }
});

test("finish: malformed handles and forged grant time or execution fields fail closed", async () => {
  for (const bad of ["", "bad", `${token}=`, Buffer.alloc(31).toString("base64url")]) {
    await rejected("finish", request("finish", { wire: JSON.stringify({ flow_token: bad, credential: {} }) }));
  }
  for (const value of [
    { ...finishResult(), flow_token: "bad" },
    { ...finishResult(), flow_token: token },
    { ...finishResult(), grant: { ...finishResult().grant, checkedAt: NOW + 1 } },
    { ...finishResult(), grant: { ...finishResult().grant, checkedAt: NOW - 121 } },
    { ...finishResult(), grant: { ...finishResult().grant, expiresAt: NOW } },
    { ...finishResult(), grant: { ...finishResult().grant, execution_enabled: true } },
    { ...finishResult(), grant: { ...finishResult().grant, confirmationToken: PRIVATE } },
  ]) {
    const f = fixture("finish");
    const response = await handlePasskeyCredentialHttp(request("finish"), "finish", { ...f.ports, execute: async () => value });
    assert.equal(response.status, 400); assert(!(await response.text()).includes(PRIVATE));
  }
});

test("execute: explicit credential-write consent and exact target/CAS body are required", async () => {
  for (const invalid of [
    { ...validInput("execute"), consent: null }, { ...validInput("execute"), consent: { kind: "credential-write", confirmed: false } },
    { ...validInput("execute"), consent: { kind: "proof-only", confirmed: true } },
    { ...validInput("execute"), consent: { ...consent, silent: true } },
    { ...validInput("execute"), body: { credentials } }, { ...validInput("execute"), body: "{}" },
    { ...validInput("execute"), body: '{"platform_account_id":"invalid"}' },
    { ...validInput("execute"), body: JSON.stringify({ platform_account_id: accountId, connection_id: connectionId,
      expected_revision: 1, expected_storage: 1, credentials, action: "replace" }) },
  ]) await rejected("execute", request("execute", { wire: JSON.stringify(invalid) }));
  const original = ` \n${body}\t `;
  const f = fixture("execute");
  const response = await handlePasskeyCredentialHttp(
    request("execute", { wire: JSON.stringify({ ...validInput("execute"), body: original }) }), "execute", f.ports);
  assert.equal(response.status, 200);
  assert.equal((f.calls[0] as { body: string }).body, original);
});

test("execute: result connection, revision, storage and status must match the intended mutation", async () => {
  for (const value of [
    { ...(result("execute") as Record<string, unknown>), connection_id: tenantId },
    { ...(result("execute") as Record<string, unknown>), credential_revision: 2 },
    { ...(result("execute") as Record<string, unknown>), storage_version: 2 },
    { ...(result("execute") as Record<string, unknown>), status: "revoked" },
  ]) {
    const f = fixture("execute");
    const response = await handlePasskeyCredentialHttp(request("execute"), "execute", { ...f.ports, execute: async () => value });
    assert.equal(response.status, 400);
  }
  for (const action of ["replace", "revoke"] as const) {
    const unchangedBody = JSON.stringify({ platform_account_id: accountId, connection_id: connectionId,
      expected_revision: 2, expected_storage: 3, ...(action === "replace" ? { credentials } : {}) });
    const expected = { connection_id: connectionId, credential_revision: action === "replace" ? 3 : 2,
      storage_version: 4, status: action === "replace" ? "active" : "revoked" };
    const f = fixture("execute");
    const response = await handlePasskeyCredentialHttp(
      request("execute", { wire: JSON.stringify({ flow_token: token, body: unchangedBody, consent }) }),
      "execute", { ...f.ports, execute: async () => expected });
    assert.equal(response.status, 200); assert.deepEqual(await response.json(), expected);
  }
});

test("streamed private input that outlives its original session cannot authorize an operation", async () => {
  const f = fixture("start");
  let now = NOW;
  const stream = new ReadableStream<Uint8Array>({
    pull(controller) {
      controller.enqueue(new TextEncoder().encode(JSON.stringify(validInput("start"))));
      now = session.expiresAt;
      controller.close();
    },
  }, { highWaterMark: 0 });
  const req = new Request(`${ORIGIN}/api/credentials/passkey/start`, { method: "POST",
    headers: { Origin: ORIGIN, "Sec-Fetch-Site": "same-origin", "X-CSRF-Token": csrf,
      "Content-Type": "application/json; charset=UTF-8" }, body: stream, duplex: "half" } as RequestInit);
  const response = await handlePasskeyCredentialHttp(req, "start", { ...f.ports, now: () => now });
  assert.equal(now, session.expiresAt, "The streamed body was actually read after the original authority snapshot.");
  assert.equal(response.status, 400); assert.equal(f.calls.length, 0);
});

test("trusted origin configuration must remain canonical HTTPS before identity or body access", async () => {
  for (const phase of ["start", "finish", "execute"] as const) {
    for (const origin of ["http://cockpit.local.test", `${ORIGIN}/`, "invalid",
      "https://user:password@cockpit.local.test"]) {
      const f = fixture(phase), req = request(phase), watched = watchBody(req);
      const response = await handlePasskeyCredentialHttp(req, phase, { ...f.ports, origin: async () => origin });
      assert.equal(response.status, 400);
      assert.equal(f.reads.session, 0); assert.equal(watched.body, 0); assert.equal(f.calls.length, 0);
    }
  }
});

test("explicit UTF8 JSON media type preserves private bytes without normalization", async () => {
  const f = fixture("start");
  const original = { ...validInput("start"), credentials: { ...credentials, passphrase: "synthetic-é-e\u0301" } };
  const response = await handlePasskeyCredentialHttp(
    request("start", { wire: JSON.stringify(original), headers: { "Content-Type": "application/json; charset=UTF-8" } }),
    "start", f.ports);
  assert.equal(response.status, 200);
  assert.deepEqual(f.calls, [original]);
});
