import assert from "node:assert/strict";
import test from "node:test";
import {
  parseDemoActionTarget, parseDemoCredentialActionMetadata, deriveDemoActionTarget,
} from "../src/lib/demo-credential-action-contracts.ts";
import { parseCredentialActionMetadata } from "../src/lib/credential-action-contracts.ts";
import { createPasskeyCredentialActionToken } from "../src/lib/passkey-credential-token.ts";
import { createDemoPasskeyCredentialActionToken } from "../src/lib/demo-passkey-credential-token.ts";
import { signing } from "./fixtures/demo-passkey-credential-fixture.ts";

const id = (n: number) => `00000000-0000-0000-0000-${n.toString().padStart(12, "0")}`;
const expected = { tenantId: id(1), accountId: id(3), authEpoch: 4 };
const metadata = () => ({ tenant_id: id(1), auth_epoch: 4, purpose: "demo_read_only",
  profile: "bitget-classic-demo-read-secret/1", environment: "demo", account: {
    id: id(3), name: "Demo", broker: "bitget", mode: "bitget_demo", currency: "USDT", status: "ready",
  }, connection: null });

test("own metadata cannot pass the Normal parser", () => {
  const own = parseDemoCredentialActionMetadata(metadata(), expected);
  assert.throws(() => parseCredentialActionMetadata(own, expected));
  const target = deriveDemoActionTarget(own, "register", { newConnectionId: id(4) });
  assert.equal(target.connection_id, id(4));
  assert(Object.isFrozen(own) && Object.isFrozen(own.account) && Object.isFrozen(target));
});
for (const field of ["purpose", "profile", "environment", "tenant_id", "auth_epoch"] as const) {
  test(`own metadata rejects changed ${field}`, () => {
    assert.throws(() => parseDemoCredentialActionMetadata({ ...metadata(), [field]: "wrong" }, expected));
  });
}
for (const patch of [{ mode: "read_only" }, { currency: "USD" }, { broker: "other" },
  { broker_uid: "synthetic-private-sentinel" }, { name: "\ud800" }]) {
  test(`own account rejects ${JSON.stringify(patch)}`, () => {
    assert.throws(() => parseDemoCredentialActionMetadata(
      { ...metadata(), account: { ...metadata().account, ...patch } }, expected));
  });
}
test("paused registration, replace and changed key revision are unavailable", () => {
  const paused = parseDemoCredentialActionMetadata(
    { ...metadata(), account: { ...metadata().account, status: "paused" } }, expected);
  assert.throws(() => deriveDemoActionTarget(paused, "register", { newConnectionId: id(4) }));
  assert.throws(() => deriveDemoActionTarget(paused, "replace" as never));
  for (const action of ["replace", "revoke"]) {
    assert.throws(() => parseDemoActionTarget({ action, platform_account_id: id(3), connection_id: id(4),
      expected_revision: 2, expected_storage: 1 }));
  }
});
test("paused revoke retains original keyrevision and current storage version", () => {
  const own = parseDemoCredentialActionMetadata({ ...metadata(), account: {
    ...metadata().account, status: "paused" }, connection: {
    connection_id: id(4), credential_revision: 1, storage_version: 3, status: "active",
  } }, expected);
  assert.deepEqual(deriveDemoActionTarget(own, "revoke"), {
    action: "revoke", platform_account_id: id(3), connection_id: id(4), expected_revision: 1, expected_storage: 3,
  });
});
test("Normal and Demo signers reject cross-domain receipts with the same key and body", async () => {
  const input = signing();
  await assert.rejects(createPasskeyCredentialActionToken(input as never));
  const normal = { ...input, authorization: {
    ...input.authorization as object, kind: "passkey-credential-authorization/1",
  } };
  await createPasskeyCredentialActionToken(normal as never);
  await assert.rejects(createDemoPasskeyCredentialActionToken(normal));
});
