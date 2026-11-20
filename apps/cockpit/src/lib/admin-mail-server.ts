import "server-only";
import { getBoundSession, type Session } from "./auth.ts";
import { getConfig } from "./config.ts";
import { apiRequest } from "./backend.ts";
import { assertAuthorizedSession, snapshotAuthorizedSession } from "./authorized-session.ts";
import { exactObject, parseEnrollmentJson } from "./passkey-enrollment-state.ts";
import { requireCsrf, requireSameOrigin } from "./security.ts";
import { loadMailAuthority, mailStore, type MailAuthority } from "./admin-mail-authority.ts";
import { mailFailure, type AdminMailStore } from "./admin-mail-state.ts";
import { sendEmailCode } from "./admin-smtp.ts";

const runtimeKey = Symbol.for("investalo.platform-admin-mail/1");
type Runtime = { digest: string; authority: MailAuthority; store: AdminMailStore };
type Global = typeof globalThis & { [runtimeKey]?: Runtime };
const now = () => Math.floor(Date.now() / 1000);

async function runtime() {
  if (process.env.COCKPIT_PLATFORM_ADMIN !== "1") throw mailFailure();
  const material = await loadMailAuthority(), config = await getConfig(), shared = globalThis as Global;
  if (config.origin !== material.authority.origin || config.issuer !== material.authority.issuer) throw mailFailure();
  if (shared[runtimeKey] && shared[runtimeKey].digest !== material.digest) throw mailFailure();
  shared[runtimeKey] ??= { digest: material.digest, authority: material.authority,
    store: mailStore(material, config.stateDir) };
  return shared[runtimeKey];
}
async function authorize(session: Session, a: MailAuthority, fresh: boolean) {
  const original = snapshotAuthorizedSession(session);
  if (original.subject !== a.subject || original.issuer !== a.issuer || original.tenantId !== a.tenantId ||
    fresh && (original.oidcAuthTime > now() || now() - original.oidcAuthTime > 900)) throw mailFailure();
  const me = await apiRequest<unknown>(original, "/v1/me");
  const root = exactObject(me, ["user", "memberships", "live_enabled"]);
  const user = exactObject(root.user, ["id", "subject", "auth_epoch"]);
  if (user.id !== a.userId || user.subject !== a.subject || user.auth_epoch !== original.authEpoch ||
    !Array.isArray(root.memberships) || !root.memberships.some(value => {
      const m = exactObject(value, ["tenant_id", "tenant_name", "role"]);
      return m.tenant_id === a.tenantId && m.role === "owner";
    })) throw mailFailure();
}
export async function adminMailAvailable(session: Session) {
  try { const r = await runtime(); await authorize(session, r.authority, false); return true; }
  catch { return false; }
}
export async function adminMailSummary(session: Session) {
  const r = await runtime();
  await authorize(session, r.authority, false);
  return r.store.summary(now(), session.authEpoch);
}

const headers = { "Cache-Control": "no-store", "Referrer-Policy": "no-referrer", "X-Content-Type-Options": "nosniff" };
async function privateInput(request: Request): Promise<string> {
  const length = request.headers.get("content-length");
  if (length !== null && (!/^[1-9][0-9]{0,3}$/.test(length) || Number(length) > 8192) || !request.body) throw mailFailure();
  const reader = request.body.getReader(), chunks: Uint8Array[] = [];
  let bytes = 0, expired = false;
  const timeout = setTimeout(() => { expired = true; void reader.cancel().catch(() => {}); }, 5000);
  try {
    while (true) {
      const value = await reader.read();
      if (expired) throw mailFailure();
      if (value.done) break;
      bytes += value.value.byteLength;
      if (bytes > 8192) throw mailFailure();
      chunks.push(value.value);
    }
    if (bytes < 1 || length !== null && bytes !== Number(length)) throw mailFailure();
    return new TextDecoder("utf-8", { fatal: true }).decode(Buffer.concat(chunks));
  } catch { void reader.cancel().catch(() => {}); throw mailFailure(); }
  finally { clearTimeout(timeout); reader.releaseLock(); }
}
export async function handleAdminMail(request: Request) {
  if (request.method !== "POST") return Response.json({ error: "Nicht verfügbar." }, { status: 405, headers });
  if (process.env.COCKPIT_PLATFORM_ADMIN !== "1") return Response.json({ error: "Nicht verfügbar." }, { status: 404, headers });
  try {
    const r = await runtime(), bound = await getBoundSession();
    if (!bound) return Response.json({ error: "Bitte anmelden." }, { status: 401, headers });
    const original = snapshotAuthorizedSession(bound.session);
    requireSameOrigin(request, r.authority.origin);
    if (request.headers.get("sec-fetch-site") !== "same-origin") throw mailFailure();
    requireCsrf(original.csrf, request.headers.get("x-csrf-token"));
    if (new URL(request.url).pathname !== "/api/admin/mail" || new URL(request.url).search ||
      request.headers.has("content-encoding") || !/^application\/json(?:;\s*charset=utf-8)?$/i.test(request.headers.get("content-type") ?? "")) throw mailFailure();
    await authorize(original, r.authority, true);
    const input = parseEnrollmentJson(await privateInput(request)) as Record<string, unknown>;
    if (!input || typeof input !== "object" || Array.isArray(input)) throw mailFailure();
    const { action } = input;
    const v = exactObject(input, action === "save" ? ["action", "revision", "settings"] :
      action === "verify" ? ["action", "revision", "code"] : ["action", "revision"]);
    if (!Number.isSafeInteger(v.revision) || (v.revision as number) < 0) throw mailFailure();
    async function guard() {
      const current = await getBoundSession();
      if (!current || current.handle !== bound!.handle) throw mailFailure();
      assertAuthorizedSession(original, current.session);
      const actual = await runtime();
      await authorize(original, actual.authority, true);
    }
    let summary;
    if (action === "save") summary = await r.store.save(v.revision as number, v.settings, now(), guard);
    else if (action === "send") summary = await r.store.send(v.revision as number, original.authEpoch, now(), sendEmailCode, guard);
    else if (action === "verify") summary = await r.store.verify(v.revision as number, original.authEpoch, v.code, now(), guard);
    else throw mailFailure();
    await guard();
    return Response.json({ summary }, { headers });
  } catch {
    return Response.json({ error: "Änderung nicht bestätigt. Status neu laden; falls nötig erneut anmelden." }, { status: 400, headers });
  }
}
