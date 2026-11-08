import type { Session } from "./auth.ts";
import { assertAuthorizedSession, snapshotAuthorizedSession } from "./authorized-session.ts";
import {
  canonicalUuid, credentialAction, credentialInteger, parseActionTarget,
  type CredentialAction,
} from "./credential-action-contracts.ts";
import { canonicalBytes, exactObject, parseEnrollmentJson } from "./passkey-enrollment-state.ts";
import { limitedBody, requireCsrf, requireSameOrigin, sameSecret } from "./security.ts";

export type ProofHttpPhase = "start" | "finish" | "grant" | "confirm";
export type ProofHttpRequests = {
  start: Readonly<{ platform_account_id: string; action: CredentialAction }>;
  finish: Readonly<{ attempt_id: string; credential: unknown; confirmation_token: string }>;
  grant: Readonly<{ grant_id: string; confirmation_token: string }>;
  confirm: Readonly<{ grant_id: string; confirmation_token: string }>;
};
export type ProofHttpPorts<P extends ProofHttpPhase> = Readonly<{
  enabled(): boolean;
  origin(): Promise<string>;
  session(): Promise<Session | null>;
  execute(input: ProofHttpRequests[P], authorizedSession: Session): Promise<unknown>;
  now(): number;
}>;

const HEADERS = { "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff" };
const unavailable = "Die zusätzliche Passkey-Prüfung ist derzeit nicht freigeschaltet.";
const rejected = "Passkey-Prüfung nicht bestätigt. Lade den Status neu und starte eine neue Vorschau.";
const failure = () => new Error("PASSKEY_PROOF_HTTP_REJECTED");

function requestInput<P extends ProofHttpPhase>(phase: P, value: unknown): ProofHttpRequests[P] {
  if (phase === "start") {
    const item = exactObject(value, ["platform_account_id", "action"]);
    return Object.freeze({ platform_account_id: canonicalUuid(item.platform_account_id),
      action: credentialAction(item.action) }) as ProofHttpRequests[P];
  }
  if (phase === "finish") {
    const item = exactObject(value, ["attempt_id", "credential", "confirmation_token"]);
    // The committed one-use claim precedes assertion parsing in the proof core.
    // Retain this distinction: malformed assertions must consume a matching attempt.
    return Object.freeze({ attempt_id: canonicalUuid(item.attempt_id), credential: item.credential,
      confirmation_token: canonicalBytes(item.confirmation_token, 32, 32) }) as ProofHttpRequests[P];
  }
  const item = exactObject(value, ["grant_id", "confirmation_token"]);
  return Object.freeze({ grant_id: canonicalUuid(item.grant_id),
    confirmation_token: canonicalBytes(item.confirmation_token, 32, 32) }) as ProofHttpRequests[P];
}
function name(value: unknown): string {
  if (typeof value !== "string" || !value || value.length > 200 || !value.isWellFormed() ||
    /[\u0000-\u001f\u007f]/.test(value)) throw failure();
  return value;
}
function expires(value: unknown, now: number): number {
  const expiry = credentialInteger(value, 1);
  if (expiry <= now || expiry > now + 120) throw failure();
  return expiry;
}
function requestOptions(value: unknown, origin: string) {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw failure();
  const item = value as Record<string, unknown>;
  const fields = ["rpId", "challenge", "allowCredentials", "timeout", "userVerification"];
  exactObject(item, Object.hasOwn(item, "extensions") ? [...fields, "extensions"] : fields);
  if (item.rpId !== new URL(origin).hostname || item.userVerification !== "required" ||
    !Array.isArray(item.allowCredentials) || item.allowCredentials.length !== 1 ||
    credentialInteger(item.timeout, 1) > 120_000) throw failure();
  if (item.extensions !== undefined) exactObject(item.extensions, []);
  const key = exactObject(item.allowCredentials[0], ["id", "type"]);
  if (key.type !== "public-key") throw failure();
  return Object.freeze({ rpId: item.rpId, challenge: canonicalBytes(item.challenge, 32, 32),
    allowCredentials: [Object.freeze({ id: canonicalBytes(key.id, 1, 1023), type: "public-key" as const })],
    timeout: item.timeout as number, userVerification: "required" as const });
}
function grantProjection(value: unknown, token: string, now: number) {
  const item = exactObject(value, ["target", "accountName", "checkedAt", "expiresAt", "confirmationToken", "execution_enabled"]);
  if (item.execution_enabled !== false || !sameSecret(canonicalBytes(item.confirmationToken, 32, 32), token)) throw failure();
  const checkedAt = credentialInteger(item.checkedAt, 1), expiresAt = expires(item.expiresAt, now);
  if (checkedAt > now || expiresAt <= checkedAt || expiresAt > checkedAt + 120) throw failure();
  return Object.freeze({ target: parseActionTarget(item.target), accountName: name(item.accountName),
    checkedAt, expiresAt, confirmationToken: token, execution_enabled: false as const });
}
function responseProjection<P extends ProofHttpPhase>(
  phase: P, value: unknown, input: ProofHttpRequests[P], origin: string, now: number,
): unknown {
  if (phase === "start") {
    const expected = input as ProofHttpRequests["start"];
    const item = exactObject(value, ["attempt_id", "options", "confirmation_token", "preview"]);
    const preview = exactObject(item.preview, ["target", "accountName", "expiresAt", "execution_enabled"]);
    const target = parseActionTarget(preview.target);
    if (preview.execution_enabled !== false || target.platform_account_id !== expected.platform_account_id ||
      target.action !== expected.action) throw failure();
    return Object.freeze({ attempt_id: canonicalUuid(item.attempt_id),
      options: requestOptions(item.options, origin), confirmation_token: canonicalBytes(item.confirmation_token, 32, 32),
      preview: Object.freeze({ target, accountName: name(preview.accountName),
        expiresAt: expires(preview.expiresAt, now), execution_enabled: false as const }) });
  }
  if (phase === "finish") {
    const item = exactObject(value, ["grant_id", "grant"]);
    return Object.freeze({ grant_id: canonicalUuid(item.grant_id),
      grant: grantProjection(item.grant, (input as ProofHttpRequests["finish"]).confirmation_token, now) });
  }
  if (phase === "grant") {
    return grantProjection(value, (input as ProofHttpRequests["grant"]).confirmation_token, now);
  }
  const item = exactObject(value, ["status", "execution_enabled", "action", "platform_account_id"]);
  if (item.status !== "verified" || item.execution_enabled !== false) throw failure();
  return Object.freeze({ status: "verified" as const, execution_enabled: false as const,
    action: credentialAction(item.action), platform_account_id: canonicalUuid(item.platform_account_id) });
}

/** Proof-only HTTP boundary; no credential executor or browser identity is accepted. */
export async function handlePasskeyProofHttp<P extends ProofHttpPhase>(
  request: Request, phase: P, ports: ProofHttpPorts<P>,
): Promise<Response> {
  if (request.method !== "POST") {
    return Response.json({ error: rejected }, { status: 405, headers: { ...HEADERS, Allow: "POST" } });
  }
  try {
    if (!ports.enabled()) return Response.json({ error: unavailable }, { status: 503, headers: HEADERS });
    const origin = await ports.origin();
    const parsedOrigin = new URL(origin);
    if (parsedOrigin.protocol !== "https:" || parsedOrigin.origin !== origin) throw failure();
    try {
      requireSameOrigin(request, origin);
      if (request.headers.get("sec-fetch-site") !== "same-origin") throw failure();
    } catch { return Response.json({ error: rejected }, { status: 403, headers: HEADERS }); }
    const initial = await ports.session();
    if (!initial) return Response.json({ error: "Bitte erneut anmelden." }, { status: 401, headers: HEADERS });
    const session = snapshotAuthorizedSession(initial, ports.now());
    try { requireCsrf(session.csrf, request.headers.get("x-csrf-token")); }
    catch { return Response.json({ error: rejected }, { status: 403, headers: HEADERS }); }
    if (request.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") throw failure();
    const input = requestInput(phase, parseEnrollmentJson(await limitedBody(request, phase === "finish" ? 16_384 : 1024)));
    // Slow/streamed bodies cannot preserve expired, rotated or disabled authority.
    const latest = await ports.session();
    if (!latest) throw failure();
    assertAuthorizedSession(session, latest, ports.now());
    if (!ports.enabled() || await ports.origin() !== origin) throw failure();
    const result = await ports.execute(input, session);
    const finished = await ports.session();
    if (!finished) throw failure();
    assertAuthorizedSession(session, finished, ports.now());
    if (!ports.enabled() || await ports.origin() !== origin) throw failure();
    return Response.json(responseProjection(phase, result, input, origin, ports.now()), { headers: HEADERS });
  } catch {
    // Do not echo library/API errors, challenge, key IDs, grant IDs or tokens.
    return Response.json({ error: rejected }, { status: 400, headers: HEADERS });
  }
}
