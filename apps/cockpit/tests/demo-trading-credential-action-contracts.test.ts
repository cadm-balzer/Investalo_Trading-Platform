import assert from "node:assert/strict";
import test from "node:test";
import {
  parseDemoTradingActionTarget, parseDemoTradingCredentialActionMetadata, deriveDemoTradingActionTarget,
} from "../src/lib/demo-trading-credential-action-contracts.ts";
import { parseCredentialActionMetadata } from "../src/lib/credential-action-contracts.ts";
import { createPasskeyCredentialActionToken } from "../src/lib/passkey-credential-token.ts";
import { createDemoTradingPasskeyCredentialActionToken } from "../src/lib/demo-trading-passkey-credential-token.ts";
import { signing } from "./fixtures/demo-trading-passkey-credential-fixture.ts";
import { parseDemoCredentialActionMetadata } from "../src/lib/demo-credential-action-contracts.ts";
import { createDemoPasskeyCredentialActionToken } from "../src/lib/demo-passkey-credential-token.ts";
import { signing as readSigning } from "./fixtures/demo-passkey-credential-fixture.ts";

const id = (n: number) => `00000000-0000-0000-0000-${n.toString().padStart(12, "0")}`;
const expected = { tenantId: id(1), accountId: id(3), authEpoch: 4 };
const metadata = () => ({ tenant_id: id(1), auth_epoch: 4, purpose: "demo_futures_spot_trading",
  profile: "bitget-classic-demo-trading-secret/1", environment: "demo", account: {
    id: id(3), name: "DemoTrading", broker: "bitget", mode: "bitget_demo", currency: "USDT", status: "ready",
  }, connection: null, key_authorities: null });

test("own metadata cannot pass the Normal parser", () => {
  const own = parseDemoTradingCredentialActionMetadata(metadata(), expected);
  assert.throws(() => parseCredentialActionMetadata(own, expected));
  const target = deriveDemoTradingActionTarget(own, "register", { newConnectionId: id(4) });
  assert.equal(target.connection_id, id(4));
  assert(Object.isFrozen(own) && Object.isFrozen(own.account) && Object.isFrozen(target));
});
test("Read and Trading metadata and signers reject both directions with the same authority bytes", async () => {
  const own = parseDemoTradingCredentialActionMetadata(metadata(), expected);
  assert.throws(() => parseDemoCredentialActionMetadata(own, expected));
  const read = { ...metadata(), purpose: "demo_read_only", profile: "bitget-classic-demo-read-secret/1" };
  delete (read as { key_authorities?: null }).key_authorities;
  assert.throws(() => parseDemoTradingCredentialActionMetadata(read, expected));
  await assert.rejects(createDemoPasskeyCredentialActionToken(signing() as never));
  await assert.rejects(createDemoTradingPasskeyCredentialActionToken(readSigning() as never));
});
for (const rights of [null, [], ["coor", "cpor", "stor"], ["coow", "cpow"],
  ["stow", "cpow", "coow"], ["coow", "coow", "cpow", "stow"],
  ["coow", "cpow", "stow", "wwow"], ["coow", "cpow", "stow", true],
  ["coow", "cpow", "stow", {}]]) {
  test(`connected Trading metadata rejects malformed rights ${JSON.stringify(rights)}`, () => {
    assert.throws(() => parseDemoTradingCredentialActionMetadata({ ...metadata(),
      connection: { connection_id: id(4), credential_revision: 1, storage_version: 1, status: "active" },
      key_authorities: rights }, expected));
  });
}
test("canonical native rights are snapshotted and frozen; accessors never run", () => {
  const rights = ["coow", "cpow", "stow"];
  const connected = { ...metadata(), connection: {
    connection_id: id(4), credential_revision: 1, storage_version: 1, status: "active" },
    key_authorities: rights };
  const own = parseDemoTradingCredentialActionMetadata(connected, expected);
  assert.ok(Object.isFrozen(own.key_authorities));
  rights.push("synthetic");
  assert.deepEqual(own.key_authorities, ["coow", "cpow", "stow"]);
  let calls = 0;
  const accessor = ["coow", "cpow", "stow"];
  Object.defineProperty(accessor, "0", { get() { calls++; return "coow"; } });
  assert.throws(() => parseDemoTradingCredentialActionMetadata({ ...connected, key_authorities: accessor }, expected));
  assert.equal(calls, 0);
  assert.throws(() => parseDemoTradingCredentialActionMetadata({ ...metadata(), key_authorities: ["coow", "cpow", "stow"] }, expected));
  const all = ["coow", "cpow", "stow", "stor", "coor", "cpor", "smor", "ttor", "wtor", "taxr", "chor", "p2pr"].sort();
  assert.deepEqual(parseDemoTradingCredentialActionMetadata({ ...connected, key_authorities: all }, expected).key_authorities, all);
});
for (const field of ["purpose", "profile", "environment", "tenant_id", "auth_epoch"] as const) {
  test(`own metadata rejects changed ${field}`, () => {
    assert.throws(() => parseDemoTradingCredentialActionMetadata({ ...metadata(), [field]: "wrong" }, expected));
  });
}
for (const patch of [{ mode: "read_only" }, { currency: "USD" }, { broker: "other" },
  { broker_uid: "synthetic-private-sentinel" }, { name: "\ud800" }]) {
  test(`own account rejects ${JSON.stringify(patch)}`, () => {
    assert.throws(() => parseDemoTradingCredentialActionMetadata(
      { ...metadata(), account: { ...metadata().account, ...patch } }, expected));
  });
}
test("paused registration, replace and changed key revision are unavailable", () => {
  const paused = parseDemoTradingCredentialActionMetadata(
    { ...metadata(), account: { ...metadata().account, status: "paused" } }, expected);
  assert.throws(() => deriveDemoTradingActionTarget(paused, "register", { newConnectionId: id(4) }));
  assert.throws(() => deriveDemoTradingActionTarget(paused, "replace" as never));
  for (const action of ["replace", "revoke"]) {
    assert.throws(() => parseDemoTradingActionTarget({ action, platform_account_id: id(3), connection_id: id(4),
      expected_revision: 2, expected_storage: 1 }));
  }
});
test("paused revoke retains original keyrevision and current storage version", () => {
  const own = parseDemoTradingCredentialActionMetadata({ ...metadata(), account: {
    ...metadata().account, status: "paused" }, connection: {
    connection_id: id(4), credential_revision: 1, storage_version: 3, status: "active",
  }, key_authorities: ["coow", "cpow", "stow"] }, expected);
  assert.deepEqual(deriveDemoTradingActionTarget(own, "revoke"), {
    action: "revoke", platform_account_id: id(3), connection_id: id(4), expected_revision: 1, expected_storage: 3,
  });
});
test("Normal and DemoTrading signers reject cross-domain receipts with the same key and body", async () => {
  const input = signing();
  await assert.rejects(createPasskeyCredentialActionToken(input as never));
  const normal = { ...input, authorization: {
    ...input.authorization as object, kind: "passkey-credential-authorization/1",
  } };
  await createPasskeyCredentialActionToken(normal as never);
  await assert.rejects(createDemoTradingPasskeyCredentialActionToken(normal));
});
