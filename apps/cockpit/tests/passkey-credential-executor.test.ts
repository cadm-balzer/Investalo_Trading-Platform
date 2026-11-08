/**
 * Fault-injected transport tests verify bounds, immutable context and no retries.
 * Actual mutual TLS plus TS/Python/PG execution is covered by the isolated fixture.
 */
import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import https from "node:https";
import type { ClientRequest, IncomingMessage } from "node:http";
import test, { type TestContext } from "node:test";
import { createPasskeyCredentialExecutor,
  type CredentialExecutorConfig } from "../src/lib/passkey-credential-executor.ts";
import type { ActionTarget, CredentialAction } from "../src/lib/credential-action-contracts.ts";

const NOW = 1_800_000_000;
const id = (value: number) => `00000000-0000-0000-0000-${String(value).padStart(12, "0")}`;
const TOKEN = "opaque.synthetic.assertion";
const rejected = (error: unknown) => {
  assert.equal((error as Error).message, "PASSKEY_CREDENTIAL_EXECUTOR_REJECTED");
  assert.equal((error as Error).cause, undefined); return true;
};
function inputs(action: CredentialAction = "register") {
  const target: ActionTarget = action === "register"
    ? { action, platform_account_id: id(3), connection_id: id(4) }
    : { action, platform_account_id: id(3), connection_id: id(4), expected_revision: 2, expected_storage: 3 };
  const context = { tenantId: id(1), userId: id(2), subject: "opaque-original-subject",
    authEpoch: 4, oidcAuthTime: NOW - 600, sessionBinding: "a".repeat(64), sessionExpiresAt: NOW + 1800 };
  const tls = { ca: Buffer.from("synthetic-ca-not-real-material"),
    certificate: Buffer.from("synthetic-client-certificate"), privateKey: Buffer.from("synthetic-client-private-key") };
  const config: CredentialExecutorConfig = { origin: "https://credential.fixture.invalid:9443",
    target, context, tls, clock: () => NOW };
  const requestBody: Record<string, unknown> = { platform_account_id: id(3), connection_id: id(4) };
  if (action !== "register") Object.assign(requestBody, { expected_revision: 2, expected_storage: 3 });
  if (action !== "revoke") requestBody.credentials = {
    api_key: "synthetic-api-key", secret: "synthetic-secret", passphrase: "synthetic-über",
  };
  const body = " \n" + JSON.stringify(requestBody) + "\t ";
  const result = { connection_id: id(4), credential_revision: action === "register" ? 1 : action === "replace" ? 3 : 2,
    storage_version: action === "register" ? 1 : 4, status: action === "revoke" ? "revoked" : "active" };
  return { config, body, result, target, context, tls };
}
type Scenario = {
  raw?: Buffer; status?: number; headers?: Record<string, string | string[] | undefined>;
  rawHeaders?: readonly string[]; incomplete?: boolean; requestError?: boolean; responseError?: boolean;
  neverRespond?: boolean; drip?: boolean; beforeResponse?: () => void; synchronousError?: boolean;
};
function fixture(t: TestContext, action: CredentialAction = "register", scenario: Scenario = {}) {
  const input = inputs(action), responseBytes = scenario.raw ?? Buffer.from(JSON.stringify(input.result));
  const seen = { calls: 0, options: null as https.RequestOptions | null, body: null as Buffer | null,
    requestDestroyed: false, responseDestroyed: false };
  const timers: NodeJS.Timeout[] = [];
  t.after(() => timers.forEach(clearTimeout));
  t.mock.method(https, "request", (options: https.RequestOptions, callback: (value: IncomingMessage) => void) => {
    seen.calls++; seen.options = options;
    if (scenario.synchronousError) throw new Error("synthetic transport details must remain private");
    const request = new EventEmitter() as EventEmitter & { end(body: Buffer): void; destroy(): void };
    request.destroy = () => { seen.requestDestroyed = true; };
    request.end = body => {
      seen.body = Buffer.from(body);
      queueMicrotask(() => {
        if (scenario.requestError) { request.emit("error", new Error("private certificate/provider details")); return; }
        if (scenario.neverRespond) return;
        const response = new EventEmitter() as EventEmitter & {
          statusCode: number; headers: Record<string, string | string[] | undefined>;
          rawHeaders: string[]; complete: boolean; destroy(): void;
        };
        response.statusCode = scenario.status ?? 200;
        response.headers = scenario.headers ?? { "content-type": "application/json", "content-length": String(responseBytes.length) };
        response.rawHeaders = [...(scenario.rawHeaders ?? [
          "Content-Type", "application/json", "Content-Length", String(responseBytes.length),
        ])];
        response.complete = !scenario.incomplete;
        response.destroy = () => { seen.responseDestroyed = true; };
        scenario.beforeResponse?.();
        callback(response as unknown as IncomingMessage);
        if (seen.responseDestroyed) return;
        if (scenario.responseError) { response.emit("error", new Error("private response details")); return; }
        if (scenario.drip) {
          const send = (at: number) => {
            if (seen.responseDestroyed || at >= responseBytes.length) return;
            response.emit("data", responseBytes.subarray(at, at + 1));
            timers.push(setTimeout(() => send(at + 1), 5));
          };
          send(0); return;
        }
        response.emit("data", responseBytes);
        response.emit("end");
      });
    };
    return request as unknown as ClientRequest;
  });
  return { ...input, seen };
}
for (const action of ["register", "replace", "revoke"] as const) {
  test(`executor sends unchanged ${action} bytes and independent original context`, async t => {
    const f = fixture(t, action), execute = createPasskeyCredentialExecutor(f.config);
    const result = await execute(TOKEN, f.body);
    assert.deepEqual(result, f.result); assert(Object.isFrozen(result));
    assert.equal(f.seen.calls, 1); assert.equal(f.seen.body?.toString("utf8"), f.body);
    const options = f.seen.options!;
    assert.equal(options.path, `/v1/credentials/bitget/${action}`); assert.equal(options.method, "POST");
    assert.equal(options.hostname, "credential.fixture.invalid"); assert.equal(options.servername, options.hostname);
    assert.equal(options.minVersion, "TLSv1.2"); assert.equal(options.rejectUnauthorized, true);
    assert(options.agent instanceof https.Agent); assert.notEqual(options.agent, https.globalAgent);
    assert.equal(options.agent.options.keepAlive, false); assert.equal(options.maxHeaderSize, 8192);
    assert.equal((options.agent.options as Record<string, unknown>).proxyEnv, undefined);
    const headers = options.headers as Record<string, string | number>;
    assert.equal(headers.Authorization, `Bearer ${TOKEN}`); assert.equal(headers.Connection, "close");
    assert.equal(headers["Content-Length"], Buffer.byteLength(f.body)); assert.equal(headers["Content-Type"], "application/json");
    const encoded = headers["X-Investalo-Credential-Context"] as string;
    assert.equal(Buffer.from(encoded, "base64url").toString("base64url"), encoded);
    assert.deepEqual(JSON.parse(Buffer.from(encoded, "base64url").toString()), {
      tenant_id: id(1), user_id: id(2), subject: "opaque-original-subject", auth_epoch: 4,
      oidc_auth_time: NOW - 600, session_binding: "a".repeat(64), session_expires_at: NOW + 1800,
    });
    assert(f.seen.requestDestroyed && f.seen.responseDestroyed);
  });
}
test("constructor snapshots original context, fixed target and TLS material", async t => {
  const f = fixture(t, "replace"), execute = createPasskeyCredentialExecutor(f.config);
  f.context.subject = "mutated"; f.context.oidcAuthTime = NOW;
  (f.target as { connection_id: string }).connection_id = id(99);
  f.tls.ca.fill(0); f.tls.certificate.fill(0); f.tls.privateKey.fill(0);
  await execute(TOKEN, f.body);
  const options = f.seen.options!;
  assert.equal(Buffer.from(options.ca as Buffer).toString(), "synthetic-ca-not-real-material");
  assert.equal(Buffer.from(options.cert as Buffer).toString(), "synthetic-client-certificate");
  assert.equal(Buffer.from(options.key as Buffer).toString(), "synthetic-client-private-key");
  const context = JSON.parse(Buffer.from((options.headers as Record<string, string>)["X-Investalo-Credential-Context"], "base64url").toString());
  assert.equal(context.subject, "opaque-original-subject"); assert.equal(context.oidc_auth_time, NOW - 600);
});
for (const value of [
  "http://credential.fixture.invalid", "https://127.0.0.1:9443", "https://localhost:9443",
  "https://Credential.fixture.invalid:9443", "https://credential.fixture.invalid:443",
  "https://user@credential.fixture.invalid:9443", "https://credential.fixture.invalid:9443/",
  "https://credential.fixture.invalid:9443/path", "https://credential.fixture.invalid:9443?q=secret",
  "https://credential.fixture.invalid:9443#secret", "https://credential.123:9443",
]) {
  test(`executor rejects noncanonical origin ${value}`, () => {
    const f = inputs(); assert.throws(() => createPasskeyCredentialExecutor({ ...f.config, origin: value }), rejected);
  });
}
for (const [name, changed] of [
  ["context extra", (f: ReturnType<typeof inputs>) => ({ ...f.config, context: { ...f.context, actor_role: "admin" } })],
  ["subject control", (f: ReturnType<typeof inputs>) => ({ ...f.config, context: { ...f.context, subject: "a\nsecret" } })],
  ["subject byte bound", (f: ReturnType<typeof inputs>) => ({ ...f.config, context: { ...f.context, subject: "ü".repeat(128) } })],
  ["epoch float", (f: ReturnType<typeof inputs>) => ({ ...f.config, context: { ...f.context, authEpoch: 1.2 } })],
  ["binding invalid", (f: ReturnType<typeof inputs>) => ({ ...f.config, context: { ...f.context, sessionBinding: "A".repeat(64) } })],
  ["missing tls", (f: ReturnType<typeof inputs>) => ({ ...f.config, tls: null })],
  ["empty key", (f: ReturnType<typeof inputs>) => ({ ...f.config, tls: { ...f.tls, privateKey: new Uint8Array() } })],
  ["oversized ca", (f: ReturnType<typeof inputs>) => ({ ...f.config, tls: { ...f.tls, ca: new Uint8Array(32769) } })],
  ["timeout high", (f: ReturnType<typeof inputs>) => ({ ...f.config, timeoutMs: 15001 })],
  ["timeout float", (f: ReturnType<typeof inputs>) => ({ ...f.config, timeoutMs: 1.2 })],
  ["invalid clock", (f: ReturnType<typeof inputs>) => ({ ...f.config, clock: null })],
] as const) {
  test(`executor rejects ${name}`, () => {
    const f = inputs(); assert.throws(() => createPasskeyCredentialExecutor(changed(f) as CredentialExecutorConfig), rejected);
  });
}
for (const value of ["", "not-jwt", "a.b.c\nsecret", "a.b." + "x".repeat(8192)]) {
  test(`executor rejects malformed opaque token length ${value.length} before transport`, async t => {
    const f = fixture(t); await assert.rejects(createPasskeyCredentialExecutor(f.config)(value, f.body), rejected);
    assert.equal(f.seen.calls, 0);
  });
}
test("executor rejects body-target drift before transport", async t => {
  const f = fixture(t); await assert.rejects(createPasskeyCredentialExecutor(f.config)(TOKEN, f.body.replace(id(4), id(99))), rejected);
  assert.equal(f.seen.calls, 0);
});
test("executor rejects stale original session before transport", async t => {
  const f = fixture(t), execute = createPasskeyCredentialExecutor({ ...f.config, clock: () => NOW + 1800 });
  await assert.rejects(execute(TOKEN, f.body), rejected); assert.equal(f.seen.calls, 0);
});
test("executor rechecks original session before publishing response", async t => {
  let now = NOW;
  const f = fixture(t, "register", { beforeResponse: () => { now = NOW + 1800; } });
  await assert.rejects(createPasskeyCredentialExecutor({ ...f.config, clock: () => now })(TOKEN, f.body), rejected);
  assert.equal(f.seen.calls, 1);
});
for (const [name, scenario] of [
  ["redirect", { status: 307 }], ["unknown commit error response", { status: 503 }],
  ["request error", { requestError: true }], ["response error", { responseError: true }],
  ["synchronous transport error", { synchronousError: true }], ["incomplete response", { incomplete: true }],
  ["invalid UTF8", { raw: Buffer.from([0xff]) }],
  ["duplicate JSON field", { raw: Buffer.from('{"connection_id":"x","connection_id":"y"}') }],
  ["extra secret result", { raw: Buffer.from(JSON.stringify({ ...inputs().result, secret: "private" })) }],
  ["wrong connection", { raw: Buffer.from(JSON.stringify({ ...inputs().result, connection_id: id(99) })) }],
  ["wrong revision", { raw: Buffer.from(JSON.stringify({ ...inputs().result, credential_revision: 2 })) }],
  ["wrong storage", { raw: Buffer.from(JSON.stringify({ ...inputs().result, storage_version: 2 })) }],
  ["wrong status", { raw: Buffer.from(JSON.stringify({ ...inputs().result, status: "revoked" })) }],
  ["body exceeds bound", { raw: Buffer.alloc(4097, 32) }],
  ["missing length", { headers: { "content-type": "application/json" } }],
  ["chunked", { headers: { "content-type": "application/json", "content-length": "1", "transfer-encoding": "chunked" },
    rawHeaders: ["Content-Type", "application/json", "Content-Length", "1", "Transfer-Encoding", "chunked"] }],
  ["compressed", { headers: { "content-type": "application/json", "content-length": "1", "content-encoding": "gzip" },
    rawHeaders: ["Content-Type", "application/json", "Content-Length", "1", "Content-Encoding", "gzip"] }],
  ["duplicate length", { rawHeaders: ["Content-Type", "application/json", "Content-Length", "1", "Content-Length", "1"] }],
  ["wrong type", { headers: { "content-type": "text/html", "content-length": "1" } }],
  ["length short", { headers: { "content-type": "application/json", "content-length": "1" } }],
] as const) {
  test(`executor rejects ${name} without retry`, async t => {
    const f = fixture(t, "register", scenario);
    await assert.rejects(createPasskeyCredentialExecutor(f.config)(TOKEN, f.body), rejected);
    assert.equal(f.seen.calls, 1); assert(f.seen.requestDestroyed || scenario.synchronousError);
  });
}
for (const scenario of [{ neverRespond: true }, { drip: true }]) {
  test(`wallclock deadline covers ${scenario.drip ? "continually dripping response" : "missing response"}`, async t => {
    const f = fixture(t, "register", scenario);
    await assert.rejects(createPasskeyCredentialExecutor({ ...f.config, timeoutMs: 20 })(TOKEN, f.body), rejected);
    assert.equal(f.seen.calls, 1); assert(f.seen.requestDestroyed);
  });
}
