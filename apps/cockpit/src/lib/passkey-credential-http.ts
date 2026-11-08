/** Injected credential HTTP boundary; runtime identities are provisioned separately. */
import {
  canonicalUuid, credentialAction, credentialInteger, parseActionTarget,
  type ActionTarget, type CredentialAction,
} from "./credential-action-contracts.ts";
import { parseBrowserCredentialTriple, type CredentialTriple } from "./credential-browser-body.ts";
import { snapshotAuthorizedSession } from "./authorized-session.ts";
import { canonicalBytes, exactObject, parseEnrollmentJson } from "./passkey-enrollment-state.ts";
import { assertProofSession, proofSession, type ProofSession } from "./passkey-action-proof-state.ts";
import { validatePasskeyCredentialBody } from "./passkey-credential-token.ts";
import { requireCsrf, requireSameOrigin } from "./security.ts";

export type CredentialHttpPhase = "start" | "finish" | "execute";
export type CredentialHttpRequests = {
  start: Readonly<{ platform_account_id: string; action: CredentialAction; credentials?: CredentialTriple }>;
  finish: Readonly<{ flow_token: string; credential: unknown }>;
  execute: Readonly<{ flow_token: string; body: string; consent: Readonly<{ kind: "credential-write"; confirmed: true }> }>;
};
export type CredentialHttpPorts<P extends CredentialHttpPhase> = Readonly<{
  enabled(): boolean;
  origin(): Promise<string>;
  session(): Promise<ProofSession | null>;
  execute(input: CredentialHttpRequests[P], authorized: ProofSession): Promise<unknown>;
  now(): number;
}>;
const HEADERS = {
  "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "no-referrer",
};
const unavailable = "Die Kontoanbindung ist in dieser Umgebung noch nicht freigeschaltet.";
const rejected = "Ergebnis nicht bestätigt. Lade den Kontostand neu.";
const failure = () => new Error("PASSKEY_CREDENTIAL_HTTP_REJECTED");
const token = (value: unknown) => canonicalBytes(value, 32, 32);

/** Fatal UTF8 preserves the private input; replacement decoding would change it. */
async function privateRequestBody(request: Request): Promise<string> {
  const announced = request.headers.get("content-length");
  if (announced !== null && (!/^[1-9][0-9]{0,4}$/.test(announced) || Number(announced) > 16_384)) throw failure();
  if (!request.body) throw failure();
  const reader = request.body.getReader(), chunks: Uint8Array[] = [];
  let size = 0, expired = false;
  const deadline = setTimeout(() => {
    expired = true;
    void reader.cancel().catch(() => {});
  }, 10_000);
  try {
    while (true) {
      const value = await reader.read();
      if (expired) throw failure();
      if (value.done) break;
      if (!(value.value instanceof Uint8Array)) throw failure();
      size += value.value.byteLength;
      if (size > 16_384) throw failure();
      chunks.push(value.value);
    }
    if (size < 1 || announced !== null && Number(announced) !== size) throw failure();
    return new TextDecoder("utf-8", { fatal: true }).decode(Buffer.concat(chunks));
  } catch {
    void reader.cancel().catch(() => {});
    throw failure();
  } finally {
    clearTimeout(deadline);
    reader.releaseLock();
  }
}
function executeTarget(body: unknown): ActionTarget {
  if (typeof body !== "string") throw failure();
  const item = parseEnrollmentJson(body);
  if (!item || typeof item !== "object" || Array.isArray(item)) throw failure();
  const wire = item as Record<string, unknown>;
  const action = !Object.hasOwn(wire, "expected_revision") ? "register"
    : Object.hasOwn(wire, "credentials") ? "replace" : "revoke";
  const target = parseActionTarget({
    action, platform_account_id: wire.platform_account_id, connection_id: wire.connection_id,
    ...(action === "register" ? {} : { expected_revision: wire.expected_revision, expected_storage: wire.expected_storage }),
  });
  validatePasskeyCredentialBody(body, target);
  return target;
}
function input<P extends CredentialHttpPhase>(phase: P, value: unknown): CredentialHttpRequests[P] {
  if (phase === "start") {
    if (!value || typeof value !== "object" || Array.isArray(value)) throw failure();
    const action = credentialAction((value as Record<string, unknown>).action);
    const item = exactObject(value, action === "revoke"
      ? ["platform_account_id", "action"] : ["platform_account_id", "action", "credentials"]);
    return Object.freeze({
      platform_account_id: canonicalUuid(item.platform_account_id), action,
      ...(action === "revoke" ? {} : { credentials: parseBrowserCredentialTriple(item.credentials) }),
    }) as CredentialHttpRequests[P];
  }
  if (phase === "finish") {
    const item = exactObject(value, ["flow_token", "credential"]);
    return Object.freeze({ flow_token: token(item.flow_token), credential: item.credential }) as CredentialHttpRequests[P];
  }
  const item = exactObject(value, ["flow_token", "body", "consent"]);
  const consent = exactObject(item.consent, ["kind", "confirmed"]);
  if (consent.kind !== "credential-write" || consent.confirmed !== true) throw failure();
  executeTarget(item.body);
  return Object.freeze({ flow_token: token(item.flow_token), body: item.body as string,
    consent: Object.freeze({ kind: "credential-write" as const, confirmed: true as const }),
  }) as CredentialHttpRequests[P];
}
function name(value: unknown): string {
  if (typeof value !== "string" || !value || value.length > 200 || !value.isWellFormed() ||
    /[\u0000-\u001f\u007f]/.test(value)) throw failure();
  return value;
}
function expires(value: unknown, bound: ProofSession, now: number): number {
  const expiry = credentialInteger(value, 1);
  if (expiry <= now || expiry > now + 120 || expiry > bound.session.expiresAt) throw failure();
  return expiry;
}
function options(value: unknown, origin: string) {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw failure();
  const fields = ["rpId", "challenge", "allowCredentials", "timeout", "userVerification"];
  const item = exactObject(value, Object.hasOwn(value, "extensions") ? [...fields, "extensions"] : fields);
  if (item.rpId !== new URL(origin).hostname || item.userVerification !== "required" ||
    !Array.isArray(item.allowCredentials) || item.allowCredentials.length !== 1 ||
    credentialInteger(item.timeout, 1) > 120_000) throw failure();
  if (item.extensions !== undefined) exactObject(item.extensions, []);
  const credential = exactObject(item.allowCredentials[0], ["id", "type"]);
  if (credential.type !== "public-key") throw failure();
  return Object.freeze({
    rpId: item.rpId, challenge: token(item.challenge), timeout: item.timeout,
    userVerification: "required" as const,
    allowCredentials: [Object.freeze({ id: canonicalBytes(credential.id, 1, 1023), type: "public-key" as const })],
  });
}
function projection<P extends CredentialHttpPhase>(
  phase: P, value: unknown, requested: CredentialHttpRequests[P], bound: ProofSession, now: number,
): unknown {
  if (phase === "start") {
    const expected = requested as CredentialHttpRequests["start"];
    const item = exactObject(value, ["flow_token", "options", "preview"]);
    const preview = exactObject(item.preview, ["target", "accountName", "expiresAt", "execution_enabled"]);
    const target = parseActionTarget(preview.target);
    if (preview.execution_enabled !== false || target.platform_account_id !== expected.platform_account_id ||
      target.action !== expected.action) throw failure();
    return Object.freeze({
      flow_token: token(item.flow_token), options: options(item.options, bound.origin),
      preview: Object.freeze({ target, accountName: name(preview.accountName),
        expiresAt: expires(preview.expiresAt, bound, now), execution_enabled: false as const }),
    });
  }
  if (phase === "finish") {
    const item = exactObject(value, ["flow_token", "grant"]);
    const grant = exactObject(item.grant, ["target", "accountName", "checkedAt", "expiresAt", "execution_enabled"]);
    const checkedAt = credentialInteger(grant.checkedAt, 1), expiresAt = expires(grant.expiresAt, bound, now);
    if (grant.execution_enabled !== false || checkedAt > now || expiresAt <= checkedAt ||
      expiresAt > checkedAt + 120 || token(item.flow_token) === (requested as CredentialHttpRequests["finish"]).flow_token) throw failure();
    return Object.freeze({ flow_token: token(item.flow_token), grant: Object.freeze({
      target: parseActionTarget(grant.target), accountName: name(grant.accountName),
      checkedAt, expiresAt, execution_enabled: false as const,
    }) });
  }
  const target = executeTarget((requested as CredentialHttpRequests["execute"]).body);
  const item = exactObject(value, ["connection_id", "credential_revision", "storage_version", "status"]);
  const revision = target.action === "register" ? 1 : target.expected_revision + (target.action === "replace" ? 1 : 0);
  const storage = target.action === "register" ? 1 : target.expected_storage + 1;
  const status = target.action === "revoke" ? "revoked" : "active";
  if (canonicalUuid(item.connection_id) !== target.connection_id ||
    credentialInteger(item.credential_revision, 1) !== revision ||
    credentialInteger(item.storage_version, 1) !== storage || item.status !== status) throw failure();
  return Object.freeze({ connection_id: target.connection_id, credential_revision: revision, storage_version: storage, status });
}

/** Default-off, original-session HTTP checks independent of the workflow core. */
export async function handlePasskeyCredentialHttp<P extends CredentialHttpPhase>(
  request: Request, phase: P, ports: CredentialHttpPorts<P>,
): Promise<Response> {
  if (request.method !== "POST") return Response.json({ error: rejected },
    { status: 405, headers: { ...HEADERS, Allow: "POST" } });
  try {
    if (!ports.enabled()) return Response.json({ error: unavailable }, { status: 503, headers: HEADERS });
    const origin = await ports.origin(), uri = new URL(origin);
    if (uri.protocol !== "https:" || uri.origin !== origin) throw failure();
    try {
      requireSameOrigin(request, origin);
      if (request.headers.get("sec-fetch-site") !== "same-origin") throw failure();
    } catch { return Response.json({ error: rejected }, { status: 403, headers: HEADERS }); }
    const initial = await ports.session();
    if (!initial) return Response.json({ error: "Bitte erneut anmelden." }, { status: 401, headers: HEADERS });
    const bound = proofSession({ ...initial, session: snapshotAuthorizedSession(initial.session, ports.now()) }, ports.now());
    if (bound.origin !== origin) throw failure();
    try { requireCsrf(bound.session.csrf, request.headers.get("x-csrf-token")); }
    catch { return Response.json({ error: rejected }, { status: 403, headers: HEADERS }); }
    if (!/^application\/json(?:\s*;\s*charset=utf-8)?$/i.test(request.headers.get("content-type") ?? "") ||
      request.headers.has("content-encoding")) throw failure();
    const requested = input(phase, parseEnrollmentJson(await privateRequestBody(request)));
    // Keep the final assertion in this continuation, immediately before dispatch.
    // An async assertion helper would introduce another stale-snapshot boundary.
    const dispatchOrigin = await ports.origin();
    const dispatchSession = await ports.session();
    if (!dispatchSession || !ports.enabled() || dispatchOrigin !== origin) throw failure();
    assertProofSession(bound, dispatchSession, ports.now());
    const result = await ports.execute(requested, bound);
    const receiptOrigin = await ports.origin();
    const receiptSession = await ports.session();
    if (!receiptSession || !ports.enabled() || receiptOrigin !== origin) throw failure();
    assertProofSession(bound, receiptSession, ports.now());
    return Response.json(projection(phase, result, requested, bound, ports.now()), { headers: HEADERS });
  } catch {
    // An absent response can follow a committed write. Never infer rollback or retry.
    return Response.json({ error: rejected }, { status: 400, headers: HEADERS });
  }
}
