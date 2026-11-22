import assert from "node:assert/strict";
import { chmod, rename, symlink, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { randomBytes, randomUUID } from "node:crypto";
import test from "node:test";
import { loadDemoTradingCredentialRuntime } from "../src/lib/demo-trading-credential-runtime.ts";
import type { ProofSession } from "../src/lib/demo-trading-passkey-action-proof-state.ts";
import type { DemoTradingPasskeyCredentialPorts } from "../src/lib/demo-trading-passkey-credential-flow.ts";
import { identityFixture, id } from "./helpers/demo-trading-private-identity-fixture.ts";

const NOW = 1_800_000_000;
const token = () => randomBytes(32).toString("base64url");
const triple = { api_key: "synthetic-runtime-api", secret: "synthetic-runtime-secret",
  passphrase: "synthetic-runtime-passphrase" };
const bound = (): ProofSession => ({
  handle: token(), origin: "https://cockpit.fixture.invalid:8443",
  session: { subject: "synthetic-runtime-subject", issuer: "https://idp.fixture.invalid",
    oidcAuthTime: NOW - 3600, tenantId: id(1), authEpoch: 4, expiresAt: NOW + 1800,
    csrf: token(), displayName: "Fixture", tenantName: "Fixture" },
});
async function fixture(t: Parameters<typeof identityFixture>[0]) {
  const identity = await identityFixture(t);
  await writeFile(join(identity.directory, "config"), JSON.stringify(identity.spec), { flag: "wx", mode: 0o400 });
  const actor = bound(), calls: string[] = [];
  let contextReady!: () => void;
  const contextObserved = new Promise<void>(resolve => { contextReady = resolve; });
  const options = {
    directory: identity.directory, ownerUid: process.getuid!(),
    origin: identity.spec.origin, oidcIssuer: identity.spec.oidcIssuer,
    now: () => NOW, randomToken: token, randomUuid: randomUUID,
    async portsFor(b: ProofSession): Promise<DemoTradingPasskeyCredentialPorts> {
      calls.push("provider");
      return {
        current: async () => b, now: () => NOW, randomToken: token, randomUuid: randomUUID,
        context: async () => { calls.push("context"); contextReady(); return {}; },
        metadata: async () => { calls.push("metadata"); await contextObserved; throw new Error("synthetic API stop"); },
        request: async () => { throw new Error("unexpected write"); },
        credentialKey: async () => { throw new Error("unexpected signing"); },
        execute: async () => { throw new Error("unexpected execution"); },
      };
    },
  };
  return { ...identity, options, actor, calls };
}

test("operative installation loads actual private identity and keeps key material out of public runtime", async t => {
  const x = await fixture(t), runtime = await loadDemoTradingCredentialRuntime(x.options);
  await runtime.check();
  assert.equal(runtime.accountId, id(3));
  assert.doesNotMatch(JSON.stringify(runtime), /signing|passphrase|synthetic-runtime-secret/);
  await assert.rejects(runtime.flow.start(x.actor, id(3), "register", triple));
  assert.equal(x.calls.filter(v => v === "provider").length, 1);
  assert.ok(x.calls.includes("context"));
  assert.ok(x.calls.includes("metadata"));
});

test("replaced or mutated private manifest disables the installed continuation", async t => {
  const x = await fixture(t), runtime = await loadDemoTradingCredentialRuntime(x.options);
  await rename(join(x.directory, "config"), join(x.directory, "original"));
  await writeFile(join(x.directory, "config"), JSON.stringify(x.spec), { mode: 0o400 });
  await assert.rejects(runtime.check(), /DEMO_TRADING_RUNTIME_UNAVAILABLE/);
  await assert.rejects(runtime.flow.start(x.actor, id(3), "register", triple));
  assert.deepEqual(x.calls, []);
});

for (const mode of [0o600, 0o444]) {
  test(`operative manifest rejects mode ${mode.toString(8)} before provider use`, async t => {
    const x = await fixture(t);
    await chmod(join(x.directory, "config"), mode);
    await assert.rejects(loadDemoTradingCredentialRuntime(x.options), /DEMO_TRADING_RUNTIME_UNAVAILABLE/);
    assert.deepEqual(x.calls, []);
  });
}

test("symlink manifest never reads a substitute", async t => {
  const x = await fixture(t);
  await rename(join(x.directory, "config"), join(x.directory, "original"));
  await symlink(join(x.directory, "original"), join(x.directory, "config"));
  await assert.rejects(loadDemoTradingCredentialRuntime(x.options), /DEMO_TRADING_RUNTIME_UNAVAILABLE/);
});

test("installation cannot override current server origin or file owner", async t => {
  const x = await fixture(t);
  for (const field of [{ origin: "https://other.fixture.invalid" }, { ownerUid: process.getuid!() + 1 }]) {
    await assert.rejects(loadDemoTradingCredentialRuntime({ ...x.options, ...field }));
  }
  assert.deepEqual(x.calls, []);
});

test("foreign original tenant or issuer is rejected before provider creation", async t => {
  const x = await fixture(t), runtime = await loadDemoTradingCredentialRuntime(x.options);
  for (const field of [{ tenantId: id(9) }, { issuer: "https://other.fixture.invalid" }]) {
    await assert.rejects(runtime.flow.start({ ...x.actor, session: { ...x.actor.session, ...field } },
      id(3), "register", triple));
  }
  assert.deepEqual(x.calls, []);
});
