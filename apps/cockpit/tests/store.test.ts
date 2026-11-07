import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { EncryptedStore } from "../src/lib/store.ts";
import { randomToken } from "../src/lib/security.ts";

test("state is encrypted, authenticated and atomically consumable only once", async () => {
  const directory = await mkdtemp(join(tmpdir(), "investalo-store-test-"));
  try {
    const store = new EncryptedStore(directory, randomToken()), id = randomToken();
    await store.put(id, { expiresAt: Math.floor(Date.now() / 1000) + 60, subject: "synthetic-test-user", nonce: "test-nonce" });
    const [file] = await readdir(directory);
    const bytes = await readFile(join(directory, file), "utf8");
    assert.equal(bytes.includes("synthetic-test-user"), false);
    assert.equal(bytes.includes("test-nonce"), false);
    const results = await Promise.all([store.consume(id), store.consume(id), store.consume(id)]);
    assert.equal(results.filter(Boolean).length, 1);
    assert.equal(await store.get(id), null);
  } finally { await rm(directory, { recursive: true, force: true }); }
});
test("expired, tampered and wrong-key state is rejected", async () => {
  const directory = await mkdtemp(join(tmpdir(), "investalo-store-test-"));
  try {
    const store = new EncryptedStore(directory, randomToken()), id = randomToken();
    await store.put(id, { expiresAt: Math.floor(Date.now() / 1000) - 1 });
    assert.equal(await store.get(id), null);
    await store.put(id, { expiresAt: Math.floor(Date.now() / 1000) + 60 });
    assert.equal(await new EncryptedStore(directory, randomToken()).get(id), null);
    const [file] = await readdir(directory);
    const encoded = Buffer.from(await readFile(join(directory, file), "utf8"), "base64");
    encoded[28] ^= 1;
    await writeFile(join(directory, file), encoded.toString("base64"));
    assert.equal(await store.get(id), null);
    await assert.rejects(store.put("../escape", { expiresAt: 123 }));
  } finally { await rm(directory, { recursive: true, force: true }); }
});
