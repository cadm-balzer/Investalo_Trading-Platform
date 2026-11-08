/**
 * Isolated stdin/RPC fixture. Synthetic secrets travel through bounded private
 * pipes only; stdout is a protocol, never a user-facing log or persisted file.
 */
import { createHash, createPrivateKey, randomBytes, randomUUID, sign } from "node:crypto";
import { request as httpsRequest } from "node:https";
import { createInterface } from "node:readline";
import {
  beginPasskeyCredentialFlow, executePasskeyCredentialFlow, finishPasskeyCredentialFlow,
  type PasskeyCredentialPorts,
} from "../../apps/cockpit/src/lib/passkey-credential-flow.ts";
import { internalToken } from "../../apps/cockpit/src/lib/internal-token.ts";
import type { ActionTarget, CredentialAction } from "../../apps/cockpit/src/lib/credential-action-contracts.ts";
import type { ProofSession } from "../../apps/cockpit/src/lib/passkey-action-proof-state.ts";

const lines = createInterface({ input: process.stdin, crlfDelay: Infinity })[Symbol.asyncIterator]();
const MAX = 32_768;
let checks = 0, executions = 0, stage = "configuration";
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
      const result = await api(path, "POST", body);
      check(result.status === 200); return result.value;
    },
    now, randomToken: token, randomUuid: randomUUID,
    credentialKey: async () => new Uint8Array(signingKey),
    execute: async (jwt, body) => {
      executions++;
      output({ kind: "execute", token: jwt, body });
      const result = await input();
      check(result.kind === "executed" && result.body_sha256 === createHash("sha256").update(body).digest("hex"));
      return result.result;
    },
  };

  let counter = 0, connection = "";
  for (const action of ["register", "replace", "revoke"] as const) {
    stage = action + ".prepare";
    let exactBody = "";
    const prepared = await beginPasskeyCredentialFlow(ports, bound, config.account, action, (target: ActionTarget) => {
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
    const client = Buffer.from(JSON.stringify({ type: "webauthn.get",
      challenge: prepared.options.challenge, origin: bound.origin, crossOrigin: false }));
    const count = Buffer.alloc(4); count.writeUInt32BE(++counter);
    const authenticator = Buffer.concat([
      createHash("sha256").update(config.rp).digest(), Buffer.from([0x05]), count,
    ]);
    const signature = sign("sha256", Buffer.concat([
      authenticator, createHash("sha256").update(client).digest(),
    ]), privateKey);
    const response = { id: config.credentialId, rawId: config.credentialId, type: "public-key",
      clientExtensionResults: {}, response: {
        clientDataJSON: client.toString("base64url"), authenticatorData: authenticator.toString("base64url"),
        signature: signature.toString("base64url"), userHandle: config.userHandle,
      } };
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
});
