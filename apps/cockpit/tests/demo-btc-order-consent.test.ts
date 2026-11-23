import test from "node:test";
import assert from "node:assert/strict";
import { createHash, createHmac } from "node:crypto";
import { BTC_ORDER_CONFIRMATION, BTC_ORDER_PATH, prepareDemoBTCTestConsent,
  BTC_MARKET_CONFIRMATION, prepareDemoBTCMarketConsent,
  type BTCOrderConsentDependencies } from "../src/lib/demo-btc-order-consent.ts";

const id = (n: number) => `00000000-0000-0000-0000-${String(n).padStart(12, "0")}`;
const ORIGIN = "https://cockpit.investalo.de", at = 1700000000;
type RequestChanges = { headers?: Record<string, string>; body?: string; method?: string; path?: string };
function fixture() {
  const session = { issuer: "https://auth.cockpit.investalo.de", subject: "synthetic-order-owner",
    oidcAuthTime: at - 30, tenantId: id(1), authEpoch: 3, expiresAt: at + 3600,
    displayName: "Synthetic", tenantName: "Synthetic", csrf: Buffer.alloc(32, 2).toString("base64url") };
  const original = { handle: Buffer.alloc(32, 1).toString("base64url"), session };
  const f = { current: original, role: "owner", calls: 0, mutate: () => {} };
  const metadata = () => ({ tenant_id: id(1), auth_epoch: 3, purpose: "demo_futures_spot_trading",
    profile: "bitget-classic-demo-trading-secret/1", environment: "demo",
    account: { id: id(4), name: "Demo", broker: "bitget", mode: "bitget_demo", currency: "USDT", status: "ready" },
    connection: { connection_id: id(5), credential_revision: 1, storage_version: 1, status: "active" },
    key_authorities: ["coow", "cpow", "stow"] });
  const deps: BTCOrderConsentDependencies = { accountId: id(4), signingKey: new Uint8Array(32).fill(83),
    getSession: async () => f.current, getActor: async () => {
      f.calls++; if (f.calls === 2) f.mutate();
      return { userId: id(2), role: f.role, metadata: metadata() };
    }, checkInstallation: async () => {}, now: () => at };
  const target = { platform_account_id: id(4), connection_id: id(5), credential_revision: 1,
    storage_version: 1, command_id: id(6), intent_sha256: "a".repeat(64),
    outbox_receipt: { schema: "bitget-classic-demo-outbox/1", outbox_id: id(92),
      binding_digest: "b".repeat(64), revision: 1, head: "c".repeat(64), state_digest: "d".repeat(64) },
    confirmation: BTC_ORDER_CONFIRMATION };
  function request(changes: RequestChanges = {}) {
    return new Request(ORIGIN + (changes.path ?? "/api/bitget-demo/orders/btc-test/submit"), {
      method: changes.method ?? "POST", headers: { origin: ORIGIN, "sec-fetch-site": "same-origin",
        "content-type": "application/json", "x-csrf-token": session.csrf, ...changes.headers },
      ...(changes.method === "GET" ? {} : { body: changes.body ?? JSON.stringify(target) }) });
  }
  return { f, deps, target, request, original };
}

test("original HTTP confirmation signs an exact private 15s executor packet", async () => {
  const f = fixture(), packet = await prepareDemoBTCTestConsent(f.request(), f.deps);
  const [header, payload, signature] = packet.token.split(".");
  assert.deepEqual(JSON.parse(Buffer.from(header, "base64url").toString()), { alg: "HS256", typ: "JWT" });
  assert.equal(signature, createHmac("sha256", f.deps.signingKey).update(header+"."+payload).digest("base64url"));
  const claims = JSON.parse(Buffer.from(payload, "base64url").toString());
  assert.equal(claims.kind, "investalo-demo-btc-test-order-consent/1");
  assert.equal(claims.aud, "investalo-demo-btc-test-order");
  assert.equal(claims.htu, BTC_ORDER_PATH);
  assert.equal(claims.exp, at+15);
  assert.equal(claims.body_sha256, createHash("sha256").update(packet.body).digest("hex"));
  assert.deepEqual(JSON.parse(packet.body), f.target);
  assert.equal(packet.context.user_id, id(2));
  assert.equal(f.f.calls, 2);
});

test("wrong origin site CSRF method path and content type deny", async () => {
  const cases: RequestChanges[] = [{ headers: { origin: "https://foreign.invalid" } },
    { headers: { "sec-fetch-site": "cross-site" } }, { headers: { "x-csrf-token": "foreign" } },
    { method: "GET" }, { path: "/api/bitget-demo/account" }, { headers: { "content-type": "text/plain" } }];
  for (const changes of cases) {
    const f = fixture();
    await assert.rejects(prepareDemoBTCTestConsent(f.request(changes), f.deps));
    assert.equal(f.f.calls, 0);
  }
});

test("missing original session issuer and trading membership deny", async () => {
  const f = fixture();
  await assert.rejects(prepareDemoBTCTestConsent(f.request(), { ...f.deps, getSession: async () => null }));
  f.f.current = { ...f.original, session: { ...f.original.session, issuer: "https://foreign.invalid" } };
  await assert.rejects(prepareDemoBTCTestConsent(f.request(), f.deps));
  f.f.current = f.original; f.f.role = "viewer";
  await assert.rejects(prepareDemoBTCTestConsent(f.request(), f.deps));
});

test("original session and actor rights remain bound across body and metadata awaits", async () => {
  for (const field of ["handle", "authEpoch", "csrf", "role"]) {
    const f = fixture();
    f.f.mutate = () => {
      if (field === "role") f.f.role = "viewer";
      else if (field === "handle") f.f.current = { ...f.original, handle: Buffer.alloc(32, 3).toString("base64url") };
      else f.f.current = { ...f.original, session: { ...f.original.session,
        ...(field === "authEpoch" ? { authEpoch: 4 } : { csrf: Buffer.alloc(32, 3).toString("base64url") }) } };
    };
    await assert.rejects(prepareDemoBTCTestConsent(f.request(), f.deps));
  }
});

test("foreign targets unknown fields bool revisions and wrong confirmation deny", async () => {
  for (const changes of [{ platform_account_id: id(9) }, { connection_id: id(9) },
    { storage_version: 2 }, { storage_version: true }, { credential_revision: true },
    { confirmation: "yes" }, { native_order_id: "not-allowed" },
    { outbox_receipt: { ...fixture().target.outbox_receipt, revision: true } }]) {
    const f = fixture();
    await assert.rejects(prepareDemoBTCTestConsent(f.request({
      body: JSON.stringify({ ...f.target, ...changes }) }), f.deps));
  }
});

test("duplicate JSON properties oversized and invalid UTF8 bodies deny", async () => {
  const f = fixture();
  const raw = JSON.stringify(f.target).replace('"storage_version":1', '"storage_version":1,"storage_version":1');
  await assert.rejects(prepareDemoBTCTestConsent(f.request({ body: raw }), f.deps));
  await assert.rejects(prepareDemoBTCTestConsent(f.request({ body: " ".repeat(16385) }), f.deps));
  await assert.rejects(prepareDemoBTCTestConsent(f.request({
    headers: { "content-length": "2" } }), f.deps));
  const invalid = new Request(f.request(), { body: new Uint8Array([0xff]) });
  await assert.rejects(prepareDemoBTCTestConsent(invalid, f.deps));
});

test("lease clips at original session expiry and revoked installation rejects", async () => {
  const f = fixture();
  f.f.current = { ...f.original, session: { ...f.original.session, expiresAt: at+5 } };
  const packet = await prepareDemoBTCTestConsent(f.request(), f.deps);
  assert.equal(JSON.parse(Buffer.from(packet.token.split(".")[1], "base64url").toString()).exp, at+5);
  await assert.rejects(prepareDemoBTCTestConsent(f.request(), { ...f.deps, checkInstallation: async () => {
    throw new Error("synthetic revoked installation");
  } }));
});

test("Market HTTP confirmation signs its own domain and rejects old Limit confirmation", async () => {
  const f = fixture();
  const request = () => f.request({ path: "/api/bitget-demo/orders/btc-market/submit",
    body: JSON.stringify({ ...f.target, confirmation: BTC_MARKET_CONFIRMATION }) });
  const packet = await prepareDemoBTCMarketConsent(request(), f.deps);
  const claims = JSON.parse(Buffer.from(packet.token.split(".")[1], "base64url").toString());
  assert.equal(claims.kind, "investalo-demo-btc-market-order-consent/1");
  assert.equal(claims.aud, "investalo-demo-btc-market-order");
  assert.equal(claims.htu, "/v1/bitget-demo-trading/market-order-submit");
  assert.equal(JSON.parse(packet.body).confirmation, BTC_MARKET_CONFIRMATION);
  await assert.rejects(prepareDemoBTCTestConsent(request(), f.deps));
  await assert.rejects(prepareDemoBTCMarketConsent(f.request({
    path: "/api/bitget-demo/orders/btc-market/submit" }), f.deps));
  await assert.rejects(prepareDemoBTCMarketConsent(f.request(), f.deps));
});
