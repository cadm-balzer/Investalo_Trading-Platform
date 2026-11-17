import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import ts from "typescript";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import * as contracts from "../src/lib/demo-credential-action-contracts.ts";
import * as overview from "../src/lib/contracts.ts";
import * as controller from "../src/lib/demo-credential-browser-controller.ts";
import * as body from "../src/lib/credential-browser-body.ts";
import * as proof from "../src/lib/passkey-browser-proof.ts";
import * as http from "../src/lib/demo-passkey-credential-http.ts";

const require = createRequire(import.meta.url);
function load(path: string, inject: Record<string, unknown>) {
  const compiled = ts.transpileModule(readFileSync(new URL(path, import.meta.url), "utf8"), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const module = { exports: {} as any };
  new Function("require", "module", "exports", compiled)(
    (name: string) => Object.hasOwn(inject, name) ? inject[name] : require(name), module, module.exports);
  return module.exports;
}
const id = (n: number) => `00000000-0000-0000-0000-${String(n).padStart(12, "0")}`;
const session = { tenantId: id(1), subject: "fixture", issuer: "https://idp.fixture.invalid",
  authEpoch: 0, oidcAuthTime: 1, csrf: Buffer.alloc(32, 7).toString("base64url"), expiresAt: 1_900_000_000 };
const metadata: contracts.DemoCredentialActionMetadata = { tenant_id: id(1), auth_epoch: 0,
  purpose: "demo_read_only", profile: "bitget-classic-demo-read-secret/1", environment: "demo",
  account: { id: id(2), name: "<script>private-name</script>", broker: "bitget",
    mode: "bitget_demo", currency: "USDT", status: "ready" }, connection: null };
const form = load("../src/components/demo-passkey-credential-form.tsx", {
  "@/lib/demo-credential-action-contracts": contracts,
  "@/lib/demo-credential-browser-controller": controller, "@/lib/credential-browser-body": body,
  "@/lib/passkey-browser-proof": proof,
});
const demoAccess = load("../src/components/bitget-demo-access.tsx", {
  "next/link": { default: ({ href, children }: any) => React.createElement("a", { href }, children) },
});

test("actual Demo form SSR escapes account names and exposes no secret value or execute control initially", () => {
  const rendered = renderToStaticMarkup(React.createElement(form.DemoPasskeyCredentialForm, {
    csrf: session.csrf, accounts: [metadata],
  }));
  assert.match(rendered, /Bitget-Demo-Testkonto/);
  assert.match(rendered, /&lt;script&gt;private-name&lt;\/script&gt;/);
  assert.doesNotMatch(rendered, /<script>|type="password"|demo-credential-write|Testaktion ausführen/);
  assert.match(rendered, /disabled/);
  assert.doesNotMatch(rendered, /localStorage|sessionStorage/);
});

test("own action availability preserves ready registration, paused revoke and terminal state", () => {
  assert.deepEqual(contracts.allowedDemoCredentialActions(metadata), ["register"]);
  for (const status of ["paused", "disconnected"] as const)
    assert.deepEqual(contracts.allowedDemoCredentialActions({ ...metadata,
      account: { ...metadata.account, status } }), []);
  const active = { ...metadata, account: { ...metadata.account, status: "paused" as const },
    connection: { connection_id: id(3), credential_revision: 1 as const, storage_version: 3, status: "active" as const } };
  assert.deepEqual(contracts.allowedDemoCredentialActions(active), ["revoke"]);
  assert.deepEqual(contracts.allowedDemoCredentialActions({ ...active,
    connection: { ...active.connection, status: "revoked" } }), []);
  assert.deepEqual(contracts.allowedDemoCredentialActions({ ...active,
    connection: { ...active.connection, storage_version: Number.MAX_SAFE_INTEGER } }), []);
});

function serverFixture() {
  const f = { calls: [] as string[], accounts: [{ id: id(2), mode: "bitget_demo" }, { id: id(3), mode: "read_only" }],
    fault: 0, privateMetadata: false };
  const server = load("../src/lib/demo-passkey-credential-browser-server.ts", {
    "server-only": {}, "./auth.ts": { getBoundSession: async () => { throw new Error("Unexpected session access"); } },
    "./config.ts": { getConfig: async () => { throw new Error("Unexpected config access"); } },
    "./contracts.ts": overview, "./demo-credential-action-contracts.ts": contracts,
    "./demo-passkey-credential-http.ts": http,
    "./backend.ts": { apiRequest: async (_session: unknown, path: string) => {
      f.calls.push(path);
      if (path === "/v1/overview") return { tenant_id: id(1), mode: "paper", live_enabled: false,
        accounts: f.accounts, positions: [], jobs: [], journal: [] };
      if (f.fault) throw Object.assign(new Error("private driver details"), { status: f.fault });
      return { ...metadata, ...(f.privateMetadata ? { envelope: "private" } : {}) };
    } },
  });
  return { f, server };
}

test("actual server wrapper stays unavailable and skips config/session/private body access", async () => {
  const { f, server } = serverFixture();
  assert.equal(server.demoCredentialBrowserRuntimeAvailable(), false);
  for (const phase of ["start", "finish", "execute"]) {
    const request = new Request(`https://cockpit.fixture.invalid/api/credentials/bitget-demo/passkey/${phase}`,
      { method: "POST", body: "synthetic-private" });
    const response = await server.handleDemoCredentialBrowserRequest(request, phase);
    assert.equal(response.status, 503);
    assert.equal(request.bodyUsed, false);
    assert.match(response.headers.get("cache-control")!, /no-store/);
  }
  assert.deepEqual(f.calls, []);
});

test("own scoped metadata list never substitutes Normal data or fabricates a denied free slot", async () => {
  const { f, server } = serverFixture();
  assert.deepEqual(await server.listDemoCredentialMetadata(session), [metadata]);
  assert.deepEqual(f.calls, ["/v1/overview", `/v1/bitget-demo/credential-actions/${id(2)}`]);
  for (const fault of [403, 404]) {
    f.fault = fault;
    assert.deepEqual(await server.listDemoCredentialMetadata(session), []);
  }
  f.fault = 503;
  await assert.rejects(server.listDemoCredentialMetadata(session));
  f.fault = 0; f.privateMetadata = true;
  await assert.rejects(server.listDemoCredentialMetadata(session));
  f.privateMetadata = false;
  f.accounts = [{ id: "../credentials/private", mode: "bitget_demo" }];
  const before = f.calls.length;
  await assert.rejects(server.listDemoCredentialMetadata(session));
  assert.equal(f.calls.length, before + 1); // only the overview read
  f.accounts = [{ id: id(2), mode: "bitget_demo" }, { id: id(2), mode: "bitget_demo" }];
  await assert.rejects(server.listDemoCredentialMetadata(session));
});

test("actual Demo page keeps disabled/login/active-passkey states distinct before rendering the form", async () => {
  let activeSession: unknown = session, enabled = false, factor = false, reads = 0;
  const page = load("../src/app/security/credentials/demo/page.tsx", {
    "next/link": { default: ({ href, children }: any) => React.createElement("a", { href }, children) },
    "@/lib/auth": { getSession: async () => activeSession },
    "@/lib/backend": { BackendError: class extends Error {} },
    "@/lib/passkey-enrollment": { getPasskeyContext: async () => {
      reads++; return { credential: factor ? { status: "active", enrollment_epoch: 0 } : null };
    } },
    "@/lib/demo-passkey-credential-browser-server": {
      demoCredentialBrowserRuntimeAvailable: () => enabled,
      listDemoCredentialMetadata: async () => [metadata],
    },
    "@/components/dashboard": { Shell: ({ children }: any) => React.createElement("main", {}, children) },
    "@/components/login": { Login: () => React.createElement("p", {}, "Fixture login") },
    "@/components/demo-passkey-credential-form": form,
    "@/components/bitget-demo-access": demoAccess,
  });
  let rendered = renderToStaticMarkup(await page.default());
  assert.match(rendered, /noch nicht freigeschaltet/);
  assert.match(rendered, /Bitget-Demo-Modus/);
  assert.match(rendered, /API-Key, Secret und Passphrase/);
  assert.match(rendered, /reinen Leserechten/);
  assert.match(rendered, /href="\/security\/passkeys"/);
  assert.doesNotMatch(rendered, /Testvorschau vorbereiten|type="password"/);
  assert.equal(reads, 0);
  enabled = true;
  rendered = renderToStaticMarkup(await page.default());
  assert.match(rendered, /aktiven Passkey/);
  factor = true;
  rendered = renderToStaticMarkup(await page.default());
  assert.match(rendered, /Testvorschau vorbereiten/);
  activeSession = null;
  assert.match(renderToStaticMarkup(await page.default()), /Fixture login/);
});

for (const phase of ["start", "finish", "execute"]) {
  test(`actual Next Demo ${phase} route forwards exclusively to own server handler`, async () => {
    const calls: unknown[] = [];
    const route = load(`../src/app/api/credentials/bitget-demo/passkey/${phase}/route.ts`, {
      "@/lib/demo-passkey-credential-browser-server": {
        handleDemoCredentialBrowserRequest: async (...args: unknown[]) => {
          calls.push(args); return Response.json({ error: "disabled" }, { status: 503 });
        },
      },
    });
    const request = new Request(`https://cockpit.fixture.invalid/api/credentials/bitget-demo/passkey/${phase}`,
      { method: "POST" });
    assert.equal((await route.POST(request)).status, 503);
    assert.deepEqual(calls, [[request, phase]]);
  });
}
