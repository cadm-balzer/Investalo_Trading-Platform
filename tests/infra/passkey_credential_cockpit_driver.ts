/**
 * Isolated stdin/RPC fixture. Synthetic secrets travel through bounded private
 * pipes only; stdout is a protocol, never a user-facing log or persisted file.
 */
import { createHash, createPrivateKey, randomBytes, randomUUID, sign } from "node:crypto";
import { request as httpsRequest, createServer, type Server } from "node:https";
import { createInterface } from "node:readline";
import {
  beginPasskeyCredentialFlow, executePasskeyCredentialFlow, finishPasskeyCredentialFlow,
  type PasskeyCredentialPorts,
} from "../../apps/cockpit/src/lib/passkey-credential-flow.ts";
import { internalToken } from "../../apps/cockpit/src/lib/internal-token.ts";
import { createPasskeyCredentialExecutor } from "../../apps/cockpit/src/lib/passkey-credential-executor.ts";
import type { ActionTarget, CredentialAction } from "../../apps/cockpit/src/lib/credential-action-contracts.ts";
import { actionProofBinding, type ProofSession } from "../../apps/cockpit/src/lib/passkey-action-proof-state.ts";
import { createPasskeyCredentialBrowserFlow } from "../../apps/cockpit/src/lib/passkey-credential-browser-flow.ts";
import { handlePasskeyCredentialHttp, type CredentialHttpPhase } from "../../apps/cockpit/src/lib/passkey-credential-http.ts";
import { CredentialBrowserController } from "../../apps/cockpit/src/lib/credential-browser-controller.ts";
import { parseActionTarget } from "../../apps/cockpit/src/lib/credential-action-contracts.ts";

const lines = createInterface({ input: process.stdin, crlfDelay: Infinity })[Symbol.asyncIterator]();
const MAX = 32_768;
let checks = 0, executions = 0, stage = "configuration";
let browserServer: Server | undefined;
function check(value: unknown): asserts value {
  if (!value) throw new Error("ISOLATED_CREDENTIAL_FLOW_CHECK_FAILED");
  checks++;
}
function output(value: unknown): void {
  const raw = JSON.stringify(value);
  if (Buffer.byteLength(raw) > MAX) throw new Error("ISOLATED_RPC_SIZE");
  process.stdout.write(raw + "\n");
}
async function input(): Promise<Record<string, any>> {
  const line = await lines.next();
  if (line.done || Buffer.byteLength(line.value) > MAX) throw new Error("ISOLATED_RPC_INPUT");
  const value = JSON.parse(line.value);
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("ISOLATED_RPC_INPUT");
  return value;
}
async function denied(callback: () => Promise<unknown>): Promise<void> {
  try { await callback(); } catch { checks++; return; }
  throw new Error("ISOLATED_DENIAL_MISSING");
}

async function main() {
  const initial = await input();
  check(initial.kind === "configuration");
  const config = initial.config, bound = config.bound as ProofSession;
  check(bound.origin === "https://cockpit.local.test:8443");
  check(config.api === "https://credential-flow-api:8000");
  check(config.disabledApi === "https://credential-flow-disabled-api:8000");
  const privateKey = createPrivateKey(config.privateKey);
  const signingKey = Buffer.from(config.signingKey, "base64url");
  check(signingKey.byteLength === 32 && config.internalKey !== config.signingKey);
  const token = () => randomBytes(32).toString("base64url");
  const now = () => Math.floor(Date.now() / 1000);

  async function api(path: string, method: string, body: string, disabled = false) {
    check(path.startsWith("/v1/") && !path.includes("?"));
    const jwt = await internalToken(config.internalKey, bound.session, method, path, body);
    const base = new URL(disabled ? config.disabledApi : config.api);
    return await new Promise<{ status: number; value: unknown }>((resolve, reject) => {
      const call = httpsRequest({
        hostname: base.hostname, port: base.port, path, method,
        // Existing fixture certificate has SAN api. Certificate verification
        // remains enabled; these are fixed isolated fixture aliases only.
        servername: "api", rejectUnauthorized: true,
        headers: { Authorization: `Bearer ${jwt}`, "Content-Type": "application/json",
          ...(body ? { "Content-Length": Buffer.byteLength(body) } : {}) },
      }, response => {
        const chunks: Buffer[] = [];
        let length = 0;
        response.on("data", (chunk: Buffer) => {
          length += chunk.byteLength;
          if (length > MAX) { call.destroy(); reject(new Error("ISOLATED_API_SIZE")); }
          else chunks.push(chunk);
        });
        response.on("end", () => {
          try { resolve({ status: response.statusCode ?? 0, value: JSON.parse(Buffer.concat(chunks).toString("utf8")) }); }
          catch { reject(new Error("ISOLATED_API_RESPONSE")); }
        });
      });
      call.setTimeout(8_000, () => call.destroy(new Error("ISOLATED_API_TIMEOUT")));
      call.on("error", () => reject(new Error("ISOLATED_API_UNAVAILABLE")));
      call.end(body || undefined);
    });
  }
  stage = "disabled";
  const disabled = await api("/v1/passkey-credential-authorizations/prepare", "POST", "{}", true);
  check(disabled.status === 404);
  let executorTarget: ActionTarget | undefined;
  const trusted = Object.freeze({
    tenantId: bound.session.tenantId, userId: config.userId, subject: bound.session.subject,
    authEpoch: bound.session.authEpoch, oidcAuthTime: bound.session.oidcAuthTime,
    sessionBinding: actionProofBinding(bound), sessionExpiresAt: bound.session.expiresAt,
  });
  function executor(origin = config.executor.origin, otherCertificate = false) {
    check(executorTarget !== undefined);
    return createPasskeyCredentialExecutor({
      origin, context: trusted, target: executorTarget,
      tls: {
        ca: Buffer.from(config.executor.ca),
        certificate: Buffer.from(otherCertificate ? config.executor.otherCertificate : config.executor.certificate),
        privateKey: Buffer.from(otherCertificate ? config.executor.otherPrivateKey : config.executor.privateKey),
      },
    });
  }

  const ports: PasskeyCredentialPorts = {
    current: async () => bound,
    context: async () => {
      const result = await api("/v1/passkeys/context", "GET", "");
      check(result.status === 200); return result.value;
    },
    metadata: async (_session, account) => {
      const result = await api(`/v1/credential-actions/${account}`, "GET", "");
      check(result.status === 200); return result.value;
    },
    request: async (_session, path, value) => {
      // Raw credentials must never reach the API.
      const body = JSON.stringify(value);
      check(!body.includes("synthetic-purpose-secret"));
      if (config.browser && path === "/v1/passkey-credential-authorizations/prepare") executorTarget = parseActionTarget(value.target);
      const result = await api(path, "POST", body);
      check(result.status === 200); return result.value;
    },
    now, randomToken: token, randomUuid: randomUUID,
    credentialKey: async () => new Uint8Array(signingKey),
    execute: async (jwt, body) => {
      let actual: unknown;
      if (config.executor) {
        if (executions === 0) {
          await denied(() => executor(config.executor.origin, true)(jwt, body));
          if (!config.executor.service) await denied(() => executor(config.executor.disabledOrigin)(jwt, body));
        }
        // Exact body bytes are authenticated before durable consumption.
        await denied(() => executor()(jwt, body + " "));
        actual = await executor()(jwt, body);
        // A second request cannot reuse durable consent or dispatch a probe.
        await denied(() => executor()(jwt, body));
      }
      executions++;
      output({ kind: "execute", token: jwt, body });
      const result = await input();
      check(result.kind === "executed" && result.body_sha256 === createHash("sha256").update(body).digest("hex"));
      if (config.executor) check(JSON.stringify(actual) === JSON.stringify(result.result));
      return config.executor ? actual : result.result;
    },
  };

  let browserPost: ((phase: CredentialHttpPhase, body: Record<string, unknown>, signal?: AbortSignal) => Promise<unknown>) | undefined;
  if (config.browser) {
    check(config.executor.service === true && !!config.browserHttp);
    const browserFlow = createPasskeyCredentialBrowserFlow({
      portsFor: () => ports, now, randomToken: token,
      acceptCredentials: (action, triple) => action === "revoke" ? triple === undefined
        : triple?.api_key === (action === "replace" ? "synthetic-purpose-replacement" : "synthetic-purpose-api")
          && triple?.secret === "synthetic-purpose-secret-päß-1e0" && triple?.passphrase === "synthetic-purpose-passphrase",
    });
    const cookie = `__Host-investalo-session=${bound.handle}`;
    browserServer = createServer({
      cert: config.browserHttp.certificate, key: config.browserHttp.privateKey,
      minVersion: "TLSv1.2", maxHeaderSize: 8192,
    }, async (incoming, outgoing) => {
      try {
        const phase = incoming.url?.match(/^\/api\/credentials\/passkey\/(start|finish|execute)$/)?.[1] as CredentialHttpPhase | undefined;
        if (!phase) throw new Error();
        const chunks: Buffer[] = []; let size = 0;
        for await (const chunk of incoming) {
          size += chunk.byteLength;
          if (size > 16_384) throw new Error();
          chunks.push(Buffer.from(chunk));
        }
        const headers = new Headers();
        for (let at = 0; at < incoming.rawHeaders.length; at += 2) headers.append(incoming.rawHeaders[at], incoming.rawHeaders[at + 1]);
        const request = new Request(bound.origin + incoming.url, {
          method: incoming.method, headers, body: Buffer.concat(chunks),
        });
        const response = await handlePasskeyCredentialHttp(request, phase, {
          enabled: () => true, origin: async () => bound.origin,
          session: async () => incoming.headers.cookie === cookie ? bound : null,
          now,
          execute: async (input, session) => {
            if (phase === "start") {
              const item = input as import("../../apps/cockpit/src/lib/passkey-credential-http.ts").CredentialHttpRequests["start"];
              return browserFlow.start(session, item.platform_account_id, item.action, item.credentials);
            }
            if (phase === "finish") {
              const item = input as import("../../apps/cockpit/src/lib/passkey-credential-http.ts").CredentialHttpRequests["finish"];
              return browserFlow.finish(session, item.flow_token, item.credential);
            }
            const item = input as import("../../apps/cockpit/src/lib/passkey-credential-http.ts").CredentialHttpRequests["execute"];
            return browserFlow.execute(session, item.flow_token, item.body, item.consent);
          },
        });
        outgoing.writeHead(response.status, { ...Object.fromEntries(response.headers), Connection: "close" });
        outgoing.end(Buffer.from(await response.arrayBuffer()));
      } catch {
        outgoing.writeHead(400, { "Content-Type": "application/json", "Connection": "close" });
        outgoing.end('{"error":"ISOLATED_BROWSER_REQUEST_REJECTED"}');
      }
    });
    browserServer.requestTimeout = 20_000;
    browserServer.headersTimeout = 10_000;
    browserServer.timeout = 20_000;
    browserServer.maxConnections = 8;
    browserServer.maxRequestsPerSocket = 1;
    browserServer.on("tlsClientError", () => {});
    browserServer.on("clientError", (_error, socket) => socket.destroy());
    await new Promise<void>((resolve, reject) => {
      browserServer!.once("error", reject);
      browserServer!.listen(9445, "0.0.0.0", resolve);
    });
    browserPost = async (phase, body, signal) => {
      const raw = JSON.stringify(body);
      check(Buffer.byteLength(raw) <= 16_384);
      return new Promise((resolve, reject) => {
        const call = httpsRequest({
          hostname: "credential-flow-node", port: 9445, servername: "credential-flow-node",
          ca: config.executor.ca, rejectUnauthorized: true, minVersion: "TLSv1.2",
          method: "POST", path: `/api/credentials/passkey/${phase}`, signal,
          headers: { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(raw),
            "Origin": bound.origin, "Sec-Fetch-Site": "same-origin", "X-CSRF-Token": bound.session.csrf,
            Cookie: cookie, Connection: "close" },
        }, response => {
          const chunks: Buffer[] = []; let size = 0;
          response.on("error", () => reject(new Error("ISOLATED_BROWSER_RESPONSE")));
          response.on("data", (chunk: Buffer) => {
            size += chunk.byteLength;
            if (size > 16_384) { call.destroy(); reject(new Error("ISOLATED_BROWSER_SIZE")); }
            else chunks.push(chunk);
          });
          response.on("end", () => {
            try {
              check(response.statusCode === 200 && response.headers["cache-control"] === "no-store");
              const wire = new TextDecoder("utf-8", { fatal: true }).decode(Buffer.concat(chunks));
              check(!wire.includes("synthetic-purpose-secret") && !wire.includes("synthetic-purpose-api")
                && !wire.includes("synthetic-purpose-passphrase") && !wire.includes(config.signingKey));
              resolve(JSON.parse(wire));
            } catch { reject(new Error("ISOLATED_BROWSER_RESPONSE")); }
          });
        });
        call.setTimeout(10_000, () => call.destroy());
        call.on("error", () => reject(new Error("ISOLATED_BROWSER_UNAVAILABLE")));
        call.end(raw);
      });
    };
  }

  let counter = 0, connection = "";
  for (const action of ["register", "replace", "revoke"] as const) {
    stage = action + ".prepare";
    let exactBody = "";
    const triple = action === "revoke" ? undefined : {
      api_key: action === "replace" ? "synthetic-purpose-replacement" : "synthetic-purpose-api",
      secret: "synthetic-purpose-secret-päß-1e0", passphrase: "synthetic-purpose-passphrase",
    };
    let controller: CredentialBrowserController | undefined;
    const authenticate = async (challenge: string) => {
      const client = Buffer.from(JSON.stringify({ type: "webauthn.get", challenge, origin: bound.origin, crossOrigin: false }));
      const count = Buffer.alloc(4); count.writeUInt32BE(++counter);
      const authenticator = Buffer.concat([
        createHash("sha256").update(config.rp).digest(), Buffer.from([0x05]), count,
      ]);
      const signature = sign("sha256", Buffer.concat([
        authenticator, createHash("sha256").update(client).digest(),
      ]), privateKey);
      return { id: config.credentialId, rawId: config.credentialId, type: "public-key",
        clientExtensionResults: {}, response: {
          clientDataJSON: client.toString("base64url"), authenticatorData: authenticator.toString("base64url"),
          signature: signature.toString("base64url"), userHandle: config.userHandle,
        } };
    };
    if (browserPost) {
      controller = new CredentialBrowserController({
        rpId: config.rp, now, post: browserPost,
        authenticate: options => authenticate(Buffer.from(options.challenge as ArrayBuffer).toString("base64url")),
      });
      await controller.prepare(config.account, action, triple);
      const snapshot = controller.snapshot();
      check(snapshot.phase === "prepared" && snapshot.preview?.target.action === action);
      check(!JSON.stringify(snapshot).includes("synthetic-purpose-secret"));
      if (action === "register") connection = snapshot.preview.target.connection_id;
      else check(snapshot.preview.target.connection_id === connection);
      stage = action + ".finish";
      await controller.assertPasskey();
      check(controller.snapshot().phase === "granted");
      const before = executions;
      await controller.execute(false);
      check(executions === before && controller.snapshot().phase === "granted");
      stage = action + ".execute";
      await controller.execute(true);
      const completed = controller.snapshot();
      check(completed.phase === "complete" && completed.result?.connection_id === connection);
      check(completed.result.credential_revision === (action === "register" ? 1 : 2));
      check(completed.result.storage_version === (action === "register" ? 1 : action === "replace" ? 2 : 3));
      check(completed.result.status === (action === "revoke" ? "revoked" : "active"));
      check(completed.preview === null && !JSON.stringify(completed).includes("synthetic-purpose-secret"));
      await controller.execute(true);
      check(executions === before + 1);
      controller.dispose();
      continue;
    }
    const prepared = await beginPasskeyCredentialFlow(ports, bound, config.account, action, (target: ActionTarget) => {
      executorTarget = target;
      const { action: _action, ...fields } = target;
      const body = { ...fields, ...(action === "revoke" ? {} : { credentials: {
        api_key: action === "replace" ? "synthetic-purpose-replacement" : "synthetic-purpose-api",
        secret: "synthetic-purpose-secret-päß-1e0", passphrase: "synthetic-purpose-passphrase",
      } }) };
      // Preserve lexical whitespace and UTF8, rather than reserialize later.
      exactBody = " \n" + JSON.stringify(body) + "\t";
      return exactBody;
    });
    check(prepared.preview.execution_enabled === false && prepared.preview.target.action === action);
    if (action === "register") connection = prepared.preview.target.connection_id;
    else check(prepared.preview.target.connection_id === connection);
    const response = await authenticate(prepared.options.challenge);
    stage = action + ".finish";
    const granted = await finishPasskeyCredentialFlow(ports, bound, prepared, response);
    check(granted.grant.execution_enabled === false && granted.grant.checkedAt >= bound.session.oidcAuthTime + 500);
    if (action === "register") {
      const before = executions;
      await denied(() => executePasskeyCredentialFlow(ports, bound, granted, exactBody + " ",
        { kind: "credential-write", confirmed: true }));
      check(executions === before);
    }
    stage = action + ".execute";
    const result = await executePasskeyCredentialFlow(ports, bound, granted, exactBody,
      { kind: "credential-write", confirmed: true });
    check(result.connection_id === connection);
    check(result.credential_revision === (action === "register" ? 1 : 2));
    check(result.storage_version === (action === "register" ? 1 : action === "replace" ? 2 : 3));
    check(result.status === (action === "revoke" ? "revoked" : "active"));
    check(Object.keys(result).sort().join(",") === "connection_id,credential_revision,status,storage_version");
    const before = executions;
    await denied(() => executePasskeyCredentialFlow(ports, bound, granted, exactBody,
      { kind: "credential-write", confirmed: true }));
    check(executions === before);
  }
  check(executions === 3 && counter === 3);
  output({ kind: "complete", checks });
  lines.return?.();
}
main().catch(() => {
  output({ kind: "failed", stage });
  process.exitCode = 1;
  lines.return?.();
}).finally(async () => {
  if (browserServer) {
    browserServer.closeAllConnections();
    await new Promise<void>(resolve => browserServer!.close(() => resolve()));
  }
});
