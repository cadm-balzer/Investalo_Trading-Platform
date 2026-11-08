/**
 * Injected private development transport. No environment configuration, browser
 * route, signing identity or production launcher is installed by this module.
 * Mutual TLS authenticates the BFF independently of the opaque action assertion;
 * trusted original context is never reconstructed from that assertion.
 */
import https from "node:https";
import { isIP } from "node:net";
import type { ClientRequest, IncomingMessage } from "node:http";
import {
  canonicalUuid, credentialInteger, parseActionTarget, type ActionTarget,
} from "./credential-action-contracts.ts";
import { CREDENTIAL_ACTION_TARGETS } from "./credential-action-token.ts";
import { exactObject, parseEnrollmentJson } from "./passkey-enrollment-state.ts";
import { validatePasskeyCredentialBody } from "./passkey-credential-token.ts";
import type { SafeOnboardingResult } from "./passkey-credential-flow.ts";

export type CredentialExecutorContext = Readonly<{
  tenantId: string; userId: string; subject: string; authEpoch: number;
  oidcAuthTime: number; sessionBinding: string; sessionExpiresAt: number;
}>;
export type CredentialExecutorConfig = Readonly<{
  origin: string; target: ActionTarget; context: CredentialExecutorContext;
  tls: Readonly<{ ca: Uint8Array; certificate: Uint8Array; privateKey: Uint8Array }>;
  timeoutMs?: number; clock?: () => number;
}>;
const MAX_RESPONSE = 4096;
const failure = () => new Error("PASSKEY_CREDENTIAL_EXECUTOR_REJECTED");
function text(value: unknown, maximum: number): string {
  if (typeof value !== "string" || !value || !value.isWellFormed() ||
    Buffer.byteLength(value, "utf8") > maximum || /[\p{Cc}\p{Cf}\p{Cs}]/u.test(value)) throw failure();
  return value;
}
function origin(value: unknown): URL {
  const wire = text(value, 255), uri = new URL(wire), host = uri.hostname;
  if (uri.protocol !== "https:" || uri.origin !== wire || uri.username || uri.password ||
    isIP(host) || !host.includes(".") || host.length > 253 || /^[0-9]+$/.test(host.split(".").at(-1)!) ||
    host.split(".").some(label => !/^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(label)) ||
    (uri.port !== "" && (Number(uri.port) < 1 || Number(uri.port) > 65535))) throw failure();
  return uri;
}
function material(value: unknown, maximum: number): Buffer {
  if (!(value instanceof Uint8Array) || value.byteLength < 1 || value.byteLength > maximum) throw failure();
  return Buffer.from(value);
}
function contextSnapshot(value: CredentialExecutorContext): CredentialExecutorContext {
  const item = exactObject(value, ["tenantId", "userId", "subject", "authEpoch",
    "oidcAuthTime", "sessionBinding", "sessionExpiresAt"]);
  if (typeof item.sessionBinding !== "string" || !/^[a-f0-9]{64}$/.test(item.sessionBinding)) throw failure();
  return Object.freeze({
    tenantId: canonicalUuid(item.tenantId), userId: canonicalUuid(item.userId),
    subject: text(item.subject, 255), authEpoch: credentialInteger(item.authEpoch),
    oidcAuthTime: credentialInteger(item.oidcAuthTime, 1), sessionBinding: item.sessionBinding,
    sessionExpiresAt: credentialInteger(item.sessionExpiresAt, 1),
  });
}
function safeResult(value: unknown, target: ActionTarget): SafeOnboardingResult {
  const item = exactObject(value, ["connection_id", "credential_revision", "storage_version", "status"]);
  const revision = target.action === "register" ? 1
    : target.expected_revision + (target.action === "replace" ? 1 : 0);
  const storage = target.action === "register" ? 1 : target.expected_storage + 1;
  const status = target.action === "revoke" ? "revoked" : "active";
  if (canonicalUuid(item.connection_id) !== target.connection_id ||
    credentialInteger(item.credential_revision, 1) !== revision ||
    credentialInteger(item.storage_version, 1) !== storage || item.status !== status) throw failure();
  return Object.freeze({ connection_id: target.connection_id, credential_revision: revision,
    storage_version: storage, status });
}
function responseLength(response: IncomingMessage): number {
  const counts = new Map<string, number>();
  for (let at = 0; at < response.rawHeaders.length; at += 2) {
    const name = response.rawHeaders[at].toLowerCase();
    counts.set(name, (counts.get(name) ?? 0) + 1);
  }
  const length = response.headers["content-length"];
  if (response.statusCode !== 200 || counts.get("content-type") !== 1 ||
    counts.get("content-length") !== 1 || response.headers["content-type"] !== "application/json" ||
    counts.has("transfer-encoding") || counts.has("content-encoding") ||
    typeof length !== "string" || !/^[1-9][0-9]{0,3}$/.test(length) ||
    Number(length) > MAX_RESPONSE) throw failure();
  return Number(length);
}

/** Construct solely from trusted server state; request input selects no endpoint or actor. */
export function createPasskeyCredentialExecutor(config: CredentialExecutorConfig):
  (token: string, unchangedBody: string) => Promise<SafeOnboardingResult> {
  try {
    const endpoint = origin(config.origin), target = parseActionTarget(config.target);
    const context = contextSnapshot(config.context), tls = exactObject(config.tls, ["ca", "certificate", "privateKey"]);
    const ca = material(tls.ca, 32768), cert = material(tls.certificate, 16384), key = material(tls.privateKey, 16384);
    const clock = config.clock === undefined ? (() => Math.floor(Date.now() / 1000)) : config.clock;
    const timeoutMs = config.timeoutMs === undefined ? 10000 : config.timeoutMs;
    if (typeof clock !== "function" || !Number.isSafeInteger(timeoutMs) ||
      timeoutMs < 1 || timeoutMs > 15000) throw failure();
    const contextHeader = Buffer.from(JSON.stringify({
      tenant_id: context.tenantId, user_id: context.userId, subject: context.subject,
      auth_epoch: context.authEpoch, oidc_auth_time: context.oidcAuthTime,
      session_binding: context.sessionBinding, session_expires_at: context.sessionExpiresAt,
    }), "utf8").toString("base64url");
    if (Buffer.byteLength(contextHeader) > 2048) throw failure();
    const live = () => {
      const now = credentialInteger(clock(), 1);
      if (context.oidcAuthTime > now + 5 || context.sessionExpiresAt <= now) throw failure();
    };
    return async (token, unchangedBody) => {
      try {
        live();
        if (typeof token !== "string" || token.length > 8192 ||
          !/^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$/.test(token)) throw failure();
        // Keep whitespace/Unicode bytes unchanged; do not reserialize private input.
        const body = Buffer.from(validatePasskeyCredentialBody(unchangedBody, target));
        return await new Promise<SafeOnboardingResult>((resolve, reject) => {
          let request: ClientRequest | undefined, response: IncomingMessage | undefined;
          let agent: https.Agent | undefined, done = false;
          const finish = (result?: SafeOnboardingResult) => {
            if (done) return;
            done = true; clearTimeout(deadline);
            response?.destroy(); request?.destroy(); agent?.destroy();
            if (result) resolve(result); else reject(failure());
          };
          // This covers DNS, connection/TLS and a continually dripping response.
          const deadline = setTimeout(() => finish(), timeoutMs);
          try {
            agent = new https.Agent({ keepAlive: false, maxSockets: 1,
              ca, cert, key, minVersion: "TLSv1.2", rejectUnauthorized: true });
            request = https.request({
              protocol: "https:", hostname: endpoint.hostname, port: endpoint.port || 443,
              servername: endpoint.hostname, path: CREDENTIAL_ACTION_TARGETS[target.action], method: "POST",
              agent, ca, cert, key, minVersion: "TLSv1.2", rejectUnauthorized: true,
              maxHeaderSize: 8192,
              headers: {
                Authorization: `Bearer ${token}`, "X-Investalo-Credential-Context": contextHeader,
                "Content-Type": "application/json", "Content-Length": body.length, Connection: "close",
              },
            }, received => {
              response = received;
              if (done) { received.destroy(); return; }
              received.on("error", () => finish());
              received.on("aborted", () => finish());
              let length: number;
              try { length = responseLength(received); } catch { finish(); return; }
              const chunks: Buffer[] = []; let size = 0;
              received.on("data", (chunk: Buffer) => {
                if (done) return;
                size += chunk.length;
                if (size > length || size > MAX_RESPONSE) { finish(); return; }
                chunks.push(Buffer.from(chunk));
              });
              received.on("end", () => {
                if (done) return;
                try {
                  if (!received.complete || size !== length) throw failure();
                  live();
                  const wire = new TextDecoder("utf-8", { fatal: true }).decode(Buffer.concat(chunks));
                  finish(safeResult(parseEnrollmentJson(wire), target));
                } catch { finish(); }
              });
            });
            request.on("error", () => finish());
            request.end(body);
          } catch { finish(); }
        });
      } catch { throw failure(); }
    };
  } catch { throw failure(); }
}
