import test from "node:test";
import assert from "node:assert/strict";
import { randomBytes } from "node:crypto";
import { mkdtemp, readFile, writeFile, rm, chmod } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { AdminMailStore } from "../src/lib/admin-mail-state.ts";

const NOW = 1_800_000_000;
const settings = { host: "mail.fixture.invalid", port: 465, username: "synthetic-user",
  password: "synthetic-mail-secret", sender: "sender@fixture.invalid" };
async function fixture(t: test.TestContext) {
  const root = await mkdtemp(join(tmpdir(), "investalo-admin-mail-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  const options = { key: randomBytes(32), binding: "synthetic-tenant-and-admin", directory: join(root, "mail"),
    recipient: "owner@fixture.invalid", defaultHost: "mail.fixture.invalid" };
  const store = new AdminMailStore(options);
  return { store, options, file: join(options.directory, "settings.enc") };
}

test("SMTP password stays encrypted and never appears in browser summary; blank preserves it", async t => {
  const x = await fixture(t);
  const first = await x.store.save(0, settings, NOW, async () => {});
  assert.equal(first.configured, true);
  assert.doesNotMatch(JSON.stringify(first), /password|synthetic-mail-secret/);
  assert.equal((await readFile(x.file)).includes(Buffer.from(settings.password)), false);
  const next = await x.store.save(1, { ...settings, password: "" }, NOW, async () => {});
  await x.store.send(next.revision, 1, NOW, async saved => assert.equal(saved.password, settings.password), async () => {});
});

test("AEAD rejects modified ciphertext and another administrator binding", async t => {
  const x = await fixture(t);
  await x.store.save(0, settings, NOW, async () => {});
  await assert.rejects(new AdminMailStore({ ...x.options, binding: "foreign-admin" }).summary(NOW));
  const bytes = await readFile(x.file); bytes[28] ^= 1;
  await writeFile(x.file, bytes);
  await assert.rejects(x.store.summary(NOW));
  await assert.rejects(x.store.save(1, settings, NOW, async () => {}));
});

test("private state mode is enforced", async t => {
  const x = await fixture(t);
  await x.store.save(0, settings, NOW, async () => {});
  await chmod(x.file, 0o644);
  await assert.rejects(x.store.summary(NOW));
});

test("durable pending precedes SMTP; actual code verifies once under the original epoch", async t => {
  const x = await fixture(t);
  let code = "";
  await x.store.save(0, settings, NOW, async () => {});
  const sent = await x.store.send(1, 4, NOW, async (_, to, value) => {
    assert.equal(to, x.options.recipient); code = value;
    assert.equal((await x.store.summary(NOW)).verification, "pending");
  }, async () => {});
  assert.equal(sent.verification, "sent");
  await assert.rejects(x.store.verify(sent.revision, 5, code, NOW + 1, async () => {}));
  const verified = await x.store.verify(sent.revision, 4, code, NOW + 1, async () => {});
  assert.equal(verified.verification, "verified");
  await assert.rejects(x.store.verify(verified.revision, 4, code, NOW + 2, async () => {}));
  const proof = await x.store.confirmation(4, NOW + 10);
  assert.equal(proof.email, x.options.recipient);
  assert.doesNotMatch(JSON.stringify(proof), /password|synthetic-mail-secret|hash/);
  assert.equal((await x.store.summary(NOW + 10, 5)).verification, "none");
});

test("uncertain SMTP acknowledgement never resends; received code remains verifiable", async t => {
  const x = await fixture(t);
  let count = 0, code = "";
  await x.store.save(0, settings, NOW, async () => {});
  const pending = await x.store.send(1, 1, NOW, async (_, __, value) => {
    count++; code = value; throw new Error("private SMTP reply");
  }, async () => {});
  assert.equal(pending.verification, "pending");
  await assert.rejects(x.store.send(pending.revision, 1, NOW + 1, async () => { count++; }, async () => {}));
  assert.equal(count, 1);
  assert.equal((await x.store.verify(pending.revision, 1, code, NOW + 1, async () => {})).verification, "verified");
});

test("five incorrect codes, expiration and stale revisions deny without verifying", async t => {
  const x = await fixture(t);
  let code = "";
  await x.store.save(0, settings, NOW, async () => {});
  let value = await x.store.send(1, 1, NOW, async (_, __, c) => { code = c; }, async () => {});
  const wrong = code === "00000000" ? "11111111" : "00000000";
  for (let i = 0; i < 5; i++) value = await x.store.verify(value.revision, 1, wrong, NOW + 1, async () => {});
  await assert.rejects(x.store.verify(value.revision, 1, code, NOW + 1, async () => {}));
  await assert.rejects(x.store.save(0, settings, NOW, async () => {}));
  const resent = await x.store.send(value.revision, 1, NOW + 61, async (_, __, c) => { code = c; }, async () => {});
  await assert.rejects(x.store.verify(resent.revision, 1, code, NOW + 661, async () => {}));
});

test("guard revocation after SMTP retains pending rather than claiming verification or retrying", async t => {
  const x = await fixture(t);
  await x.store.save(0, settings, NOW, async () => {});
  let checks = 0, sends = 0;
  const pending = await x.store.send(1, 1, NOW, async () => { sends++; }, async () => {
    if (++checks === 2) throw new Error("revoked");
  });
  assert.equal(pending.verification, "pending");
  assert.equal(sends, 1);
});

test("concurrent writer cannot overwrite an in-flight mail or accept stale configuration", async t => {
  const x = await fixture(t);
  await x.store.save(0, settings, NOW, async () => {});
  let release!: () => void, entered!: () => void;
  const wait = new Promise<void>(r => { release = r; });
  const reached = new Promise<void>(r => { entered = r; });
  const sending = x.store.send(1, 1, NOW, async () => { entered(); await wait; }, async () => {});
  await reached;
  await assert.rejects(x.store.save(2, { ...settings, password: "other-secret" }, NOW, async () => {}));
  release(); await sending;
});

test("verification uses only the operator-approved mail provider and actual verified reference", async t => {
  const x = await fixture(t);
  await assert.rejects(x.store.save(0, { ...settings, host: "mail.foreign.invalid" }, NOW, async () => {}));
  await x.store.save(0, settings, NOW, async () => {});
  await assert.rejects(x.store.confirmation(1, NOW));
  let code = "", delivered = 0;
  const sent = await x.store.send(1, 1, NOW, async (_, __, c) => { code = c; }, async () => {});
  await x.store.verify(sent.revision, 1, code, NOW + 1, async () => {});
  const proof = await x.store.confirmation(1, NOW + 2);
  await assert.rejects(x.store.deliverTicket(1, NOW + 2, "foreign-reference", "token", async () => { delivered++; }));
  await x.store.deliverTicket(1, NOW + 2, proof.reference, "token", async (_, to) => {
    assert.equal(to, x.options.recipient); delivered++;
  });
  assert.equal(delivered, 1);
});
