import https from "node:https";
import { createHash, createHmac, randomUUID } from "node:crypto";
import { actionProofBinding, type ProofSession } from "./demo-trading-passkey-action-proof-state.ts";
import type { DemoAccountTarget } from "./demo-account-contract.ts";
import { parseEnrollmentJson } from "./passkey-enrollment-state.ts";
import { parseMarketPrepared, parseMarketClosePrepared, parseMarketOutcome, type MarketPreparation, type MarketOutcome } from "./demo-market-order-contract.ts";
export type MarketPhase = "prepare" | "submit" | "observe" | "close-prepare" | "close-submit";
export type MarketTLS = { ca: Uint8Array; certificate: Uint8Array; privateKey: Uint8Array };
export type MarketPacket = { context: { tenant_id: string; user_id: string; subject: string; auth_epoch: number;
  oidc_auth_time: number; session_binding: string; session_expires_at: number }; body: string; token: string };
const paths = { prepare: "/v1/bitget-demo-trading/market-order-prepare",
  submit: "/v1/bitget-demo-trading/market-order-submit", observe: "/v1/bitget-demo-trading/market-order-observe",
  "close-prepare": "/v1/bitget-demo-trading/market-close-prepare", "close-submit": "/v1/bitget-demo-trading/market-close-submit" };
const fail = () => new Error("DEMO_MARKET_UNCONFIRMED");
export function marketReadPacket(input: { phase: "prepare" | "observe" | "close-prepare"; authorized: ProofSession; userId: string;
  target: DemoAccountTarget & { command_id?: string }; signingKey: Uint8Array; now: number }): MarketPacket {
  const { session: s, origin } = input.authorized, now = input.now;
  if (input.signingKey.byteLength !== 32 || origin !== "https://cockpit.investalo.de" ||
    s.issuer !== "https://auth.cockpit.investalo.de" || s.expiresAt <= now) throw fail();
  const context = { tenant_id: s.tenantId, user_id: input.userId, subject: s.subject,
    auth_epoch: s.authEpoch, oidc_auth_time: s.oidcAuthTime,
    session_binding: actionProofBinding(input.authorized), session_expires_at: s.expiresAt };
  const body = JSON.stringify(input.target);
  const suffix = input.phase;
  const claims = { ...context, kind: `investalo-demo-btc-market-${suffix}/1`,
    aud: `investalo-demo-btc-market-${suffix}`, oidc_issuer: s.issuer, origin,
    iat: now, exp: Math.min(now+15, s.expiresAt), jti: randomUUID(), htm: "POST",
    htu: paths[input.phase], body_sha256: createHash("sha256").update(body).digest("hex") };
  const header = Buffer.from('{"alg":"HS256","typ":"JWT"}').toString("base64url"),
    payload = Buffer.from(JSON.stringify(claims)).toString("base64url");
  return { context, body, token: `${header}.${payload}.${createHmac("sha256", input.signingKey)
    .update(`${header}.${payload}`).digest("base64url")}` };
}
export function sendMarketPacket(origin: string, tls: MarketTLS, phase: MarketPhase, packet: MarketPacket):
  Promise<MarketPreparation | MarketOutcome> {
  if (origin !== "https://demo-trading-executor.cockpit.internal:9443" || !Object.hasOwn(paths, phase)) throw fail();
  const input = parseEnrollmentJson(packet.body) as { platform_account_id: string; command_id?: string };
  const maximum = phase === "prepare" ? 65536 : 4096, timeout = phase.endsWith("submit") ? 18000 : 10000;
  return new Promise((resolve, reject) => {
    let done = false, timer: ReturnType<typeof setTimeout> | undefined;
    const denied = () => { if (!done) { done = true; clearTimeout(timer); reject(fail()); } };
    const request = https.request(new URL(origin), { path: paths[phase], method: "POST", agent: false,
      ca: Buffer.from(tls.ca), cert: Buffer.from(tls.certificate), key: Buffer.from(tls.privateKey),
      minVersion: "TLSv1.2", rejectUnauthorized: true, headers: { "Content-Type": "application/json",
        "Content-Length": Buffer.byteLength(packet.body), Accept: "application/json", Connection: "close",
        Authorization: `Bearer ${packet.token}`,
        "X-Investalo-Credential-Context": Buffer.from(JSON.stringify(packet.context)).toString("base64url") },
    }, response => {
      const counts = new Map<string, number>();
      for (let i=0; i<response.rawHeaders.length; i+=2) {
        const key = response.rawHeaders[i].toLowerCase(); counts.set(key, (counts.get(key) ?? 0)+1);
      }
      const length = response.headers["content-length"];
      if (response.statusCode !== 200 || response.headers["content-type"] !== "application/json" ||
        counts.get("content-length") !== 1 || counts.get("content-type") !== 1 ||
        counts.has("transfer-encoding") || counts.has("content-encoding") || typeof length !== "string" ||
        !/^[1-9][0-9]{0,4}$/.test(length) || Number(length) > maximum) { response.destroy(); denied(); return; }
      const chunks: Buffer[] = []; let size = 0;
      response.on("data", (chunk: Buffer) => { size += chunk.length;
        if (size > Number(length)) { response.destroy(); denied(); } else chunks.push(chunk); });
      response.on("error", denied); response.on("aborted", denied);
      response.on("end", () => {
        if (done) return;
        try {
          if (size !== Number(length)) throw fail();
          const body = parseEnrollmentJson(new TextDecoder("utf-8", { fatal: true }).decode(Buffer.concat(chunks)));
          const result = phase === "prepare" ? parseMarketPrepared(body, packet.context.tenant_id, input.platform_account_id)
            : phase === "close-prepare" ? parseMarketClosePrepared(body,packet.context.tenant_id,input.platform_account_id)
            : parseMarketOutcome(body, input.command_id === "latest" ? undefined : input.command_id);
          done = true; clearTimeout(timer); resolve(result);
        } catch { denied(); }
      });
    });
    request.on("error", denied);
    timer = setTimeout(() => { request.destroy(); denied(); }, timeout);
    request.setTimeout(timeout, () => { request.destroy(); denied(); });
    request.end(packet.body);
  });
}
