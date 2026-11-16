import assert from "node:assert/strict";
import { chmod, link, mkdir, rename, symlink, unlink, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { randomBytes } from "node:crypto";
import https from "node:https";
import test from "node:test";
import { createDemoCredentialPrivateIdentity } from "../src/lib/demo-credential-private-identity.ts";
import { createDemoCredentialPrivateProvider } from "../src/lib/demo-credential-private-provider.ts";
import type { ProofSession } from "../src/lib/demo-passkey-action-proof-state.ts";
import { demoTlsFixture, id, identityFixture, sha } from "./helpers/demo-private-identity-fixture.ts";
import { SYNTHETIC_DEMO_TLS } from "./helpers/demo-private-tls-material.ts";

const NOW = 1_800_000_000;
const bound = (): ProofSession => ({
  handle: randomBytes(32).toString("base64url"), origin: "https://cockpit.fixture.invalid:8443",
  session: { subject: "original-private-subject", issuer: "https://idp.fixture.invalid", oidcAuthTime: NOW - 3600,
    tenantId: id(1), authEpoch: 4, expiresAt: NOW + 1800, csrf: randomBytes(32).toString("base64url"),
    displayName: "Fixture", tenantName: "Fixture" },
});
const rejected = (error: unknown) => {
  assert.equal((error as Error).message, "DEMO_CREDENTIAL_PRIVATE_IDENTITY_REJECTED");
  assert.equal((error as Error).cause, undefined); return true;
};

test("protected actual files load own copied signing identity without exposing material on provider", async t => {
  const x = await identityFixture(t);
  const identity = await createDemoCredentialPrivateIdentity(x.spec, () => NOW);
  assert.equal(JSON.stringify(identity), "{}");
  const ports = identity.forSession(bound(), id(2)), first = await ports.credentialKey();
  assert.deepEqual(first, Uint8Array.from(x.signing));
  first.fill(0);
  assert.deepEqual(await ports.credentialKey(), Uint8Array.from(x.signing));
});

for (const mode of [0o600, 0o440, 0o444, 0o1400]) {
  test(`actual secret mode ${mode.toString(8)} is rejected`, async t => {
    const x = await identityFixture(t);
    await chmod(join(x.directory, "signing-key"), mode);
    await assert.rejects(createDemoCredentialPrivateIdentity(x.spec, () => NOW), rejected);
  });
}
for (const fault of ["root-mode", "root-link", "ancestor-link", "file-link", "hardlink", "directory", "empty", "oversize",
  "foreign-owner", "fingerprint", "shared-signing", "invalid-origin", "path-traversal", "extra-field"] as const) {
  test(`actual private identity rejects ${fault}`, async t => {
    const x = await identityFixture(t), path = join(x.directory, "signing-key");
    let spec = { ...x.spec };
    if (fault === "root-mode") await chmod(x.directory, 0o755);
    if (fault === "root-link" || fault === "ancestor-link") {
      await symlink(x.directory, join(x.directory, "alias"));
      spec.directory = fault === "root-link" ? join(x.directory, "alias") : join(x.directory, "alias", "child");
      if (fault === "ancestor-link") await mkdir(join(x.directory, "child"), { mode: 0o700 });
    }
    if (fault === "file-link") {
      await rename(path, join(x.directory, "original"));
      await symlink("original", path);
    }
    if (fault === "hardlink") await link(path, join(x.directory, "duplicate"));
    if (fault === "directory") { await unlink(path); await mkdir(path, { mode: 0o400 }); }
    if (fault === "empty" || fault === "oversize") {
      await unlink(path); await writeFile(path, Buffer.alloc(fault === "empty" ? 0 : 33), { flag: "wx", mode: 0o400 });
    }
    if (fault === "foreign-owner") spec.ownerUid++;
    if (fault === "fingerprint") spec.signingSha256 = "0".repeat(64);
    if (fault === "shared-signing") spec.excludedSigningSha256 = [spec.signingSha256];
    if (fault === "invalid-origin") spec.executorOrigin = "https://127.0.0.1:9443";
    if (fault === "path-traversal") spec.directory += "/../fixture";
    if (fault === "extra-field") Object.assign(spec, { key: x.signing });
    await assert.rejects(createDemoCredentialPrivateIdentity(spec, () => NOW), rejected);
  });
}
for (const fault of ["file-replacement", "root-replacement", "chmod", "mutated", "symlink", "expired-certificate"] as const) {
  test(`loaded identity rejects subsequent ${fault} and never adopts or rotates`, async t => {
    const x = await identityFixture(t); let now = NOW;
    const identity = await createDemoCredentialPrivateIdentity(x.spec, () => now);
    const ports = identity.forSession(bound(), id(2)), path = join(x.directory, "signing-key");
    if (fault === "file-replacement") {
      await rename(path, join(x.directory, "old"));
      await writeFile(path, x.signing, { flag: "wx", mode: 0o400 });
    }
    if (fault === "root-replacement") {
      const moved = x.directory + "-original";
      await rename(x.directory, moved);
      t.after(async () => { const { rm } = await import("node:fs/promises"); await rm(moved, { recursive: true, force: true }); });
      await mkdir(x.directory, { mode: 0o700 });
      for (const [name, bytes] of Object.entries(x.material)) {
        await writeFile(join(x.directory, name), bytes, { mode: 0o400, flag: "wx" });
      }
    }
    if (fault === "chmod") await chmod(path, 0o600);
    if (fault === "mutated") {
      await chmod(path, 0o600); await writeFile(path, randomBytes(32)); await chmod(path, 0o400);
    }
    if (fault === "symlink") {
      await rename(path, join(x.directory, "old")); await symlink("old", path);
    }
    if (fault === "expired-certificate") {
      now = Math.floor(Date.parse("2041-01-01T00:00:00Z") / 1000);
      await assert.rejects(createDemoCredentialPrivateIdentity(x.spec, () => now), rejected);
    }
    await assert.rejects(ports.credentialKey(), rejected);
  });
}

test("wrong TLS key and a server-only certificate reject even with their correctly pinned fingerprints", async t => {
  for (const kind of ["key", "eku"]) {
    const x = await identityFixture(t), spec = { ...x.spec };
    if (kind === "key") {
      const bytes = Buffer.from(SYNTHETIC_DEMO_TLS.serverPrivateKey);
      await unlink(join(x.directory, "client-private-key"));
      await writeFile(join(x.directory, "client-private-key"), bytes, { flag: "wx", mode: 0o400 });
      spec.privateKeySha256 = sha(bytes);
    } else {
      for (const [name, value] of [["client-certificate", SYNTHETIC_DEMO_TLS.serverCertificate],
        ["client-private-key", SYNTHETIC_DEMO_TLS.serverPrivateKey]] as const) {
        await unlink(join(x.directory, name));
        await writeFile(join(x.directory, name), value, { flag: "wx", mode: 0o400 });
      }
      spec.certificateSha256 = sha(SYNTHETIC_DEMO_TLS.serverCertificate);
      spec.privateKeySha256 = sha(SYNTHETIC_DEMO_TLS.serverPrivateKey);
    }
    await assert.rejects(createDemoCredentialPrivateIdentity(spec, () => NOW), rejected);
  }
});

test("foreign scope, origin, issuer, user and expired original session cannot bind private identity", async t => {
  const x = await identityFixture(t), identity = await createDemoCredentialPrivateIdentity(x.spec, () => NOW);
  const original = bound();
  for (const session of [
    { ...original, origin: "https://foreign.fixture.invalid" },
    { ...original, session: { ...original.session, tenantId: id(9) } },
    { ...original, session: { ...original.session, issuer: "https://foreign.fixture.invalid" } },
    { ...original, session: { ...original.session, expiresAt: NOW } },
  ]) assert.throws(() => identity.forSession(session, id(2)), rejected);
  assert.throws(() => identity.forSession(original, id(9)), rejected);
});

test("actual mTLS uses original independent context and own fixed register/revoke paths", async t => {
  const calls: { path: string; context: Record<string, unknown>; body: string }[] = [];
  const tls = await demoTlsFixture(t, (request, response) => {
    assert.equal((request.socket as import("node:tls").TLSSocket).authorized, true);
    const context = JSON.parse(Buffer.from(request.headers["x-investalo-credential-context"] as string, "base64url").toString());
    const chunks: Buffer[] = [];
    request.on("data", value => chunks.push(value));
    request.on("end", () => {
      calls.push({ path: request.url!, context, body: Buffer.concat(chunks).toString() });
      const revoke = request.url!.endsWith("revoke");
      const body = JSON.stringify({ connection_id: id(4), credential_revision: 1,
        storage_version: revoke ? 4 : 1, status: revoke ? "revoked" : "active" });
      response.writeHead(200, { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(body) });
      response.end(body);
    });
  });
  const x = await identityFixture(t, tls.origin), identity = await createDemoCredentialPrivateIdentity(x.spec, () => NOW);
  const original = bound(), ports = identity.forSession(original, id(2));
  for (const action of ["register", "revoke"]) {
    const body = " \n" + JSON.stringify({ platform_account_id: id(3), connection_id: id(4),
      ...(action === "revoke" ? { expected_revision: 1, expected_storage: 3 } :
        { credentials: { api_key: "synthetic", secret: "synthetic-ß", passphrase: "synthetic" } }) }) + "\t";
    const result = await ports.execute("opaque.synthetic.assertion", body);
    assert.equal((result as { status: string }).status, action === "register" ? "active" : "revoked");
    assert.equal(calls.at(-1)!.body, body);
    assert.equal(calls.at(-1)!.context.oidc_auth_time, original.session.oidcAuthTime);
    assert.equal(calls.at(-1)!.context.user_id, id(2));
  }
  assert.deepEqual(calls.map(value => value.path), [
    "/v1/credentials/bitget-demo/register", "/v1/credentials/bitget-demo/revoke",
  ]);
});

test("private executor rejects foreign accounts and replacement before any network dispatch", async t => {
  const x = await identityFixture(t), identity = await createDemoCredentialPrivateIdentity(x.spec, () => NOW);
  const ports = identity.forSession(bound(), id(2));
  let calls = 0;
  t.mock.method(https, "request", () => { calls++; throw new Error("NETWORK_MUST_NOT_RUN"); });
  for (const body of [
    { platform_account_id: id(9), connection_id: id(4), credentials: { api_key: "x", secret: "x", passphrase: "x" } },
    { platform_account_id: id(3), connection_id: id(4), expected_revision: 1, expected_storage: 3,
      credentials: { api_key: "x", secret: "x", passphrase: "x" } },
  ]) await assert.rejects(ports.execute("opaque.synthetic.assertion", JSON.stringify(body)), rejected);
  assert.equal(calls, 0);
});

test("original binding is snapshotted before an asynchronous private file load", async t => {
  const x = await identityFixture(t), identity = await createDemoCredentialPrivateIdentity(x.spec, () => NOW);
  const original = bound(), ports = identity.forSession(original, id(2));
  (original.session as { tenantId: string }).tenantId = id(9);
  assert.deepEqual(await ports.credentialKey(), Uint8Array.from(x.signing));
});

test("private provider obtains independent current API actor before binding identity", async () => {
  const original = bound(), calls: string[] = [];
  const credentialId = randomBytes(32).toString("base64url");
  const context = { tenant_id: id(1), user_id: id(2), auth_epoch: 4, rp_id: "cockpit.fixture.invalid",
    credential: { passkey_id: id(5), tenant_id: id(1), user_id: id(2), rp_id: "cockpit.fixture.invalid",
      credential_id: credentialId, user_handle: credentialId, public_key: credentialId,
      sign_count: 0, backup_eligible: false, backed_up: false, storage_version: 1,
      status: "active", enrollment_epoch: 4 } };
  const options = { authorized: original, current: async () => original,
    now: () => NOW, randomToken: () => credentialId, randomUuid: () => id(4),
    api: async (_session: unknown, path: string) => { calls.push(path); return context; },
    identity: { forSession: (value: ProofSession, userId: string) => {
      assert.equal(value.session.subject, original.session.subject);
      assert.equal(userId, id(2)); calls.push("identity");
      return { credentialKey: async () => new Uint8Array(32), execute: async () => { throw new Error(); } };
    } },
  };
  await createDemoCredentialPrivateProvider(options);
  assert.deepEqual(calls, ["/v1/passkeys/context", "identity"]);
  calls.length = 0;
  await assert.rejects(createDemoCredentialPrivateProvider({ ...options,
    current: async () => ({ ...original, session: { ...original.session, authEpoch: 5 } }) }),
  { message: "DEMO_CREDENTIAL_PRIVATE_PROVIDER_REJECTED" });
  assert.deepEqual(calls, []);
});
