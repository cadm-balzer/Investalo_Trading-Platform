/** Isolated actual HTTPS/P256/API/PG/executor acceptance; synthetic session only. */
import assert from "node:assert/strict";
import { createHash, createPrivateKey, randomBytes, randomUUID, sign } from "node:crypto";
import { readFileSync } from "node:fs";
import { createServer, request } from "node:https";
import { Readable } from "node:stream";
import { createInterface } from "node:readline";
import { createDemoTradingCredentialPrivateIdentity,
  type DemoTradingCredentialPrivateIdentitySpec } from "../../apps/cockpit/src/lib/demo-trading-credential-private-identity.ts";
import { createDemoTradingCredentialPrivateProvider } from "../../apps/cockpit/src/lib/demo-trading-credential-private-provider.ts";
import { createDemoTradingPasskeyCredentialBrowserFlow } from "../../apps/cockpit/src/lib/demo-trading-passkey-credential-browser-flow.ts";
import { handleDemoTradingPasskeyCredentialHttp,
  type DemoTradingCredentialHttpPhase } from "../../apps/cockpit/src/lib/demo-trading-passkey-credential-http.ts";
import { buildBrowserCredentialBody } from "../../apps/cockpit/src/lib/credential-browser-body.ts";
import { internalToken } from "../../apps/cockpit/src/lib/internal-token.ts";
import type { ProofSession } from "../../apps/cockpit/src/lib/passkey-action-proof-state.ts";
import type { Session } from "../../apps/cockpit/src/lib/auth.ts";
import type { DemoTradingActionTarget } from "../../apps/cockpit/src/lib/demo-trading-credential-action-contracts.ts";

type Configuration = {
  bound: ProofSession; spec: DemoTradingCredentialPrivateIdentitySpec;
  account: string; uncertainAccount: string; foreignAccount: string;
  internalKey: string; credentialId: string; userHandle: string;
  privateKey: string; api: string; disabledApi: string;
};
const ORIGIN = "https://cockpit.local.test:8443", RP = "cockpit.local.test";
const TRIPLE = Object.freeze({ api_key: "synthetic-demo-trading-acceptance-api",
  secret: "synthetic-demo-trading-acceptance-secret-ß", passphrase: "synthetic-demo-trading-acceptance-passphrase" });
const CONSENT = Object.freeze({ kind: "demo-trading-credential-write" as const, confirmed: true as const });
const now = () => Math.floor(Date.now() / 1000);
const token = () => randomBytes(32).toString("base64url");
const hash = (value: string | Uint8Array) => createHash("sha256").update(value).digest();
let checks = 0, stage = "configuration", lastApiStatus = 0, lastBrowserStatus = 0, networkCode = "none";
function check(value: unknown): void { assert.ok(value); checks++; }
function emit(value: unknown) { process.stdout.write(JSON.stringify(value) + "\n"); }
const lines = createInterface({ input: process.stdin, crlfDelay: Infinity })[Symbol.asyncIterator]();
async function incoming() {
  const next = await lines.next();
  check(!next.done && Buffer.byteLength(next.value) <= 32_768);
  return JSON.parse(next.value!) as Record<string, unknown>;
}
type Result = { status: number; body: Record<string, any> };
function httpsJson(url: string, servername: string, ca: Buffer | undefined,
  method: string, headers: Record<string, string>, body = ""): Promise<Result> {
  return new Promise((resolve, reject) => {
    function failed(error: unknown) {
      const code = (error as { code?: string }).code ?? (error as Error).message;
      const allowed = ["ENOTFOUND", "EAI_AGAIN", "ECONNREFUSED", "ECONNRESET", "ETIMEDOUT",
        "ERR_TLS_CERT_ALTNAME_INVALID", "UNABLE_TO_VERIFY_LEAF_SIGNATURE", "CERT_HAS_EXPIRED",
        "BOUNDED_TIMEOUT", "INVALID_RESPONSE", "BOUNDED_RESPONSE"];
      networkCode = allowed.includes(code ?? "") ? code! : "other";
      reject(new Error("ISOLATED_NETWORK_FAILURE"));
    }
    const wire = Buffer.from(body);
    const call = request(url, { method, servername, ca, rejectUnauthorized: true, agent: false,
      headers: { ...headers, "content-length": String(wire.length) } }, response => {
      const chunks: Buffer[] = []; let size = 0;
      response.on("data", chunk => {
        size += chunk.length;
        if (size > 32_768) call.destroy(new Error("BOUNDED_RESPONSE"));
        else chunks.push(chunk);
      });
      response.on("error", failed);
      response.on("end", () => {
        try { resolve({ status: response.statusCode!, body: JSON.parse(
          new TextDecoder("utf-8", { fatal: true }).decode(Buffer.concat(chunks))) }); }
        catch { failed(new Error("INVALID_RESPONSE")); }
      });
    });
    call.setTimeout(12_000, () => call.destroy(new Error("BOUNDED_TIMEOUT")));
    call.on("error", failed);
    call.end(body ? wire : undefined);
  });
}
async function run() {
  const initial = await incoming();
  check(initial.kind === "configuration" && process.getuid?.() === 10003);
  const config = initial.config as Configuration, bound = config.bound;
  check(bound.origin === ORIGIN && config.spec.origin === ORIGIN);
  const privateKey = createPrivateKey(config.privateKey);
  let counter = 0;
  const apiCalls: string[] = [];
  async function rawApi(session: Session, path: string, options: { method: "GET" | "POST"; body?: string },
    origin = config.api) {
    check([config.api, config.disabledApi].includes(origin) && path.startsWith("/v1/"));
    const body = options.body ?? "";
    const authorization = await internalToken(config.internalKey, session, options.method, path, body);
    apiCalls.push(path);
    const result = await httpsJson(origin + path, "api", undefined, options.method,
      { authorization: `Bearer ${authorization}`, "content-type": "application/json" }, body);
    lastApiStatus = result.status;
    return result;
  }
  const api = async (session: Session, path: string, options: { method: "GET" | "POST"; body?: string }) => {
    const result = await rawApi(session, path, options);
    check(result.status === 200);
    return result.body;
  };
  // Read-only startup probe. Credential commands are never retried.
  stage = "api-readiness";
  const deadline = Date.now() + 45_000;
  for (const origin of [config.api, config.disabledApi]) {
    stage = origin === config.api ? "api-readiness-enabled" : "api-readiness-disabled";
    while (true) {
      try {
        const result = await rawApi(bound.session, "/v1/passkeys/context", { method: "GET" }, origin);
        check(result.status === 200); break;
      } catch {
        if (Date.now() >= deadline) throw new Error("READINESS");
        await new Promise(resolve => setTimeout(resolve, 200));
      }
    }
  }
  stage = "api-isolation";
  check((await rawApi(bound.session, "/v1/bitget-demo-trading/passkey-authorizations/prepare",
    { method: "POST", body: "{}" }, config.disabledApi)).status === 404);
  check((await rawApi(bound.session, `/v1/bitget-demo-trading/credential-actions/${config.account}`,
    { method: "GET" }, config.disabledApi)).status === 404);
  check((await rawApi(bound.session, "/v1/passkey-credential-authorizations/prepare",
    { method: "POST", body: "{}" })).status === 404);
  check((await rawApi(bound.session, "/v1/bitget-demo/passkey-authorizations/prepare",
    { method: "POST", body: "{}" })).status === 404);
  const witnesses: { token: string; body: string }[] = [];
  async function flowFor(accountId: string) {
    const identity = await createDemoTradingCredentialPrivateIdentity({ ...config.spec, accountId });
    const ports = await createDemoTradingCredentialPrivateProvider({
      authorized: bound, identity, current: async () => bound, api, now,
      randomToken: token, randomUuid: randomUUID,
    });
    const wrapped = Object.freeze({ ...ports, async execute(signed: string, body: string) {
      witnesses.push({ token: signed, body });
      return ports.execute(signed, body);
    } });
    return createDemoTradingPasskeyCredentialBrowserFlow({ portsFor: () => wrapped, now, randomToken: token,
      acceptCredentials: (action, triple) => action === "revoke" ? triple === undefined :
        triple?.api_key === TRIPLE.api_key && triple.secret === TRIPLE.secret && triple.passphrase === TRIPLE.passphrase });
  }
  let flow = await flowFor(config.account);
  stage = "https-bff";
  const ca = readFileSync("/run/demo-trading-browser-tls/ca");
  const server = createServer({ cert: readFileSync("/run/demo-trading-browser-tls/certificate"),
    key: readFileSync("/run/demo-trading-browser-tls/private-key"), minVersion: "TLSv1.2" }, async (req, res) => {
    try {
      const pathname = new URL(req.url!, ORIGIN).pathname;
      const phase = pathname.split("/").at(-1) as DemoTradingCredentialHttpPhase;
      const incomingHeaders = new Headers();
      for (const [name, value] of Object.entries(req.headers))
        if (value !== undefined) incomingHeaders.set(name, Array.isArray(value) ? value.join(",") : value);
      const web = new Request(ORIGIN + req.url, { method: req.method, headers: incomingHeaders,
        body: Readable.toWeb(req) as ReadableStream, duplex: "half" } as RequestInit);
      const result = await handleDemoTradingPasskeyCredentialHttp(web, phase, {
        enabled: () => true, origin: async () => ORIGIN, session: async () => bound, now,
        execute: async input => phase === "start" ? flow.start(bound,
          (input as any).platform_account_id, (input as any).action, (input as any).credentials) :
          phase === "finish" ? flow.finish(bound, (input as any).flow_token, (input as any).credential) :
          flow.execute(bound, (input as any).flow_token, (input as any).body, (input as any).consent),
      });
      res.writeHead(result.status, Object.fromEntries(result.headers));
      res.end(Buffer.from(await result.arrayBuffer()));
    } catch { res.writeHead(500); res.end('{"error":"isolated acceptance rejected"}'); }
  });
  await new Promise<void>(resolve => server.listen(8443, "127.0.0.1", resolve));
  async function browser(phase: string, body: unknown, extra: Record<string, string> = {},
    path = `/api/credentials/bitget-demo-trading/passkey/${phase}`) {
    const result = await httpsJson(`https://127.0.0.1:8443${path}`, RP, ca, "POST",
      { origin: ORIGIN, "x-csrf-token": bound.session.csrf, "sec-fetch-site": "same-origin",
        "content-type": "application/json", ...extra }, JSON.stringify(body));
    lastBrowserStatus = result.status;
    check(!JSON.stringify(result.body).includes("Bearer ") && !JSON.stringify(result.body).includes(config.internalKey));
    return result;
  }
  function assertion(challenge: string) {
    const client = Buffer.from(JSON.stringify({ type: "webauthn.get", challenge, origin: ORIGIN, crossOrigin: false }));
    const count = Buffer.alloc(4); count.writeUInt32BE(++counter);
    const data = Buffer.concat([hash(RP), Buffer.from([0x05]), count]);
    return { id: config.credentialId, rawId: config.credentialId, type: "public-key",
      clientExtensionResults: {}, response: { clientDataJSON: client.toString("base64url"),
        authenticatorData: data.toString("base64url"),
        signature: sign("sha256", Buffer.concat([data, hash(client)]), privateKey).toString("base64url"),
        userHandle: config.userHandle } };
  }
  async function proved(accountId: string, action: "register" | "revoke") {
    stage = action + "-prepare";
    const started = await browser("start", { platform_account_id: accountId, action,
      ...(action === "register" ? { credentials: TRIPLE } : {}) });
    check(started.status === 200 && started.body.preview.execution_enabled === false);
    stage = action + "-proof";
    const finished = await browser("finish", { flow_token: started.body.flow_token,
      credential: assertion(started.body.options.challenge) });
    check(finished.status === 200 && finished.body.grant.execution_enabled === false);
    const target = finished.body.grant.target as DemoTradingActionTarget;
    stage = action + "-write";
    return { flow_token: finished.body.flow_token,
      body: buildBrowserCredentialBody(target, action === "register" ? TRIPLE : undefined), consent: CONSENT };
  }
  async function audit(action: string, uncertain = false) {
    check(witnesses.length === 1);
    const witness = witnesses.pop()!;
    emit({ kind: "audit", action, uncertain, ...witness });
    check((await incoming()).kind === "audited");
  }
  try {
    stage = "bff-isolation";
    const start = { platform_account_id: config.account, action: "register", credentials: TRIPLE };
    let calls = apiCalls.length;
    check((await browser("start", start, { "x-csrf-token": token() })).status === 403);
    check((await browser("start", start, {}, "/api/credentials/passkey/start")).status === 400);
    check((await browser("start", start, {}, "/api/credentials/bitget-demo/passkey/start")).status === 400);
    check((await browser("start", { ...start, credentials: { ...TRIPLE, api_key: "not-the-canary" } })).status === 400);
    check(apiCalls.length === calls);
    check((await browser("start", { ...start, platform_account_id: config.foreignAccount })).status === 400);
    check(witnesses.length === 0);
    stage = "register";
    const registration = await proved(config.account, "register");
    const parallel = await Promise.all([browser("execute", registration), browser("execute", registration)]);
    check(parallel.filter(result => result.status === 200).length === 1 &&
      parallel.filter(result => result.status === 400).length === 1);
    check(parallel.find(result => result.status === 200)!.body.status === "active");
    await audit("register");
    calls = apiCalls.length;
    check((await browser("execute", registration)).status === 400 && apiCalls.length === calls);
    stage = "executor-restart";
    emit({ kind: "restart" }); check((await incoming()).kind === "restarted");
    stage = "revoke";
    const revocation = await proved(config.account, "revoke");
    check((await browser("execute", revocation)).status === 200);
    await audit("revoke");
    calls = apiCalls.length;
    check((await browser("execute", revocation)).status === 400 && apiCalls.length === calls);
    stage = "post-commit-unknown";
    flow = await flowFor(config.uncertainAccount);
    const uncertain = await proved(config.uncertainAccount, "register");
    check((await browser("execute", uncertain)).status === 400);
    calls = apiCalls.length;
    check((await browser("execute", uncertain)).status === 400 && apiCalls.length === calls);
    check(witnesses.length === 1);
    await audit("register", true);
    const metadata = await api(bound.session,
      `/v1/bitget-demo-trading/credential-actions/${config.uncertainAccount}`, { method: "GET" });
    check(metadata.connection.status === "active" && metadata.connection.credential_revision === 1 &&
      metadata.connection.storage_version === 1);
    check(metadata.purpose === "demo_futures_spot_trading" &&
      metadata.profile === "bitget-classic-demo-trading-secret/1" &&
      JSON.stringify(metadata.key_authorities) === JSON.stringify(["coow", "cpow", "stow"]));
    emit({ kind: "complete", checks });
  } finally {
    await new Promise<void>((resolve, reject) => server.close(error => error ? reject(error) : resolve()));
  }
}
try { await run(); process.stdin.destroy(); }
catch { emit({ kind: "failed", stage, api_status: lastApiStatus, bff_status: lastBrowserStatus, network_code: networkCode });
  process.stdin.destroy(); process.exitCode = 1; }
