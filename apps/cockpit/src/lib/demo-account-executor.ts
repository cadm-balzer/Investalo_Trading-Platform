import { createHash, createHmac, randomUUID } from "node:crypto";
import https from "node:https";
import { parseDemoAccount, type DemoAccount, type DemoAccountTarget } from "./demo-account-contract.ts";
import type { ProofSession } from "./demo-trading-passkey-action-proof-state.ts";
import { actionProofBinding } from "./demo-trading-passkey-action-proof-state.ts";

export const DEMO_ACCOUNT_PATH = "/v1/bitget-demo-trading/account-read";
export async function readDemoAccount(input: {
  origin: string; oidcIssuer: string; authorized: ProofSession; userId: string;
  target: DemoAccountTarget; signingKey: Uint8Array;
  tls: { ca: Uint8Array; certificate: Uint8Array; privateKey: Uint8Array };
  now?: number;
}): Promise<DemoAccount> {
  const now = input.now ?? Math.floor(Date.now() / 1000), s = input.authorized.session;
  const uri = new URL(input.origin);
  if (uri.origin !== "https://demo-trading-executor.cockpit.internal:9443" ||
    input.signingKey.byteLength !== 32 || s.expiresAt <= now) throw new Error("DEMO_ACCOUNT_UNAVAILABLE");
  const context = { tenant_id: s.tenantId, user_id: input.userId, subject: s.subject,
    auth_epoch: s.authEpoch, oidc_auth_time: s.oidcAuthTime,
    session_binding: actionProofBinding(input.authorized), session_expires_at: s.expiresAt };
  const body = JSON.stringify(input.target);
  const claims = { ...context, kind: "investalo-demo-account-read/1", aud: "investalo-demo-account-read",
    oidc_issuer: input.oidcIssuer, origin: input.authorized.origin,
    iat: now, exp: Math.min(now + 15, s.expiresAt), jti: randomUUID(), htm: "POST",
    htu: DEMO_ACCOUNT_PATH, body_sha256: createHash("sha256").update(body).digest("hex") };
  const header = Buffer.from(JSON.stringify({ alg: "HS256", typ: "JWT" })).toString("base64url");
  const payload = Buffer.from(JSON.stringify(claims)).toString("base64url");
  const token = `${header}.${payload}.${createHmac("sha256", input.signingKey).update(`${header}.${payload}`).digest("base64url")}`;
  return new Promise((resolve, reject) => {
    let done = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const fail = () => { if (!done) { done = true; clearTimeout(timer); reject(new Error("DEMO_ACCOUNT_UNAVAILABLE")); } };
    const req = https.request(uri, { path: DEMO_ACCOUNT_PATH, method: "POST",
      ca: Buffer.from(input.tls.ca), cert: Buffer.from(input.tls.certificate),
      key: Buffer.from(input.tls.privateKey), minVersion: "TLSv1.2", rejectUnauthorized: true,
      agent: false, headers: { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(body),
        Connection: "close", Accept: "application/json", Authorization: `Bearer ${token}`,
        "X-Investalo-Credential-Context": Buffer.from(JSON.stringify(context)).toString("base64url") },
    }, response => {
      const counts = new Map<string, number>();
      for (let i = 0; i < response.rawHeaders.length; i += 2) {
        const name = response.rawHeaders[i].toLowerCase(); counts.set(name, (counts.get(name) ?? 0) + 1);
      }
      const length = response.headers["content-length"];
      if (response.statusCode !== 200 || counts.get("content-length") !== 1 || counts.get("content-type") !== 1 ||
        response.headers["content-type"] !== "application/json" || counts.has("transfer-encoding") ||
        counts.has("content-encoding") || typeof length !== "string" || !/^[1-9][0-9]{0,4}$/.test(length) ||
        Number(length) > 65536) { response.destroy(); fail(); return; }
      let size = 0;
      const chunks: Buffer[] = [];
      response.on("data", (chunk: Buffer) => {
        size += chunk.length;
        if (size > Number(length)) { response.destroy(); fail(); }
        else chunks.push(chunk);
      });
      response.on("error", fail);
      response.on("aborted", fail);
      response.on("end", () => {
        try {
          if (done || size !== Number(length)) throw new Error();
          const raw = new TextDecoder("utf-8", { fatal: true }).decode(Buffer.concat(chunks));
          const result = parseDemoAccount(JSON.parse(raw), s.tenantId, input.target.platform_account_id);
          const observed = Date.parse(result.observed_at) / 1000;
          if (observed > now + 15 || Math.floor(Date.now() / 1000) - observed > 15) throw new Error();
          done = true; clearTimeout(timer); resolve(result);
        } catch { fail(); }
      });
    });
    req.on("error", fail);
    timer = setTimeout(() => { req.destroy(); fail(); }, 7000);
    req.setTimeout(7000, () => { req.destroy(); fail(); });
    req.end(body);
  });
}
