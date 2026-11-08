import assert from "node:assert/strict";
import test from "node:test";
import {
  parseBrowserCredentialStart, parseBrowserCredentialGrant, parseBrowserCredentialResult,
} from "../src/lib/passkey-credential-browser.ts";
import type { ActionTarget } from "../src/lib/credential-action-contracts.ts";

const account = "10000000-0000-0000-0000-000000000001", connection = "20000000-0000-0000-0000-000000000002";
const now = 1_800_000_000, rp = "cockpit.local.test";
function fixture(action: "register" | "replace" | "revoke" = "register") {
  const target: ActionTarget = action === "register" ? { action, platform_account_id: account, connection_id: connection }
    : { action, platform_account_id: account, connection_id: connection, expected_revision: 4, expected_storage: 8 };
  const start = { flow_token: Buffer.alloc(32, 1).toString("base64url"), preview: {
    target, accountName: "Synthetic account", expiresAt: now + 110, execution_enabled: false,
  }, options: { rpId: rp, challenge: Buffer.alloc(32, 2).toString("base64url"), timeout: 110_000,
    allowCredentials: [{ id: Buffer.alloc(32, 3).toString("base64url"), type: "public-key" }],
    userVerification: "required" } };
  const finish = { flow_token: Buffer.alloc(32, 4).toString("base64url"),
    grant: { target, accountName: start.preview.accountName, checkedAt: now, expiresAt: now + 110, execution_enabled: false } };
  return { start, finish, target };
}
for (const action of ["register", "replace", "revoke"] as const) {
  test(`browser ${action} projections accept only the matching safe completion`, () => {
    const f = fixture(action), start = parseBrowserCredentialStart(f.start, account, action, rp, now);
    const grant = parseBrowserCredentialGrant(f.finish, start, now);
    assert.equal(grant.grant.execution_enabled, false);
    const result = { connection_id: connection, credential_revision: action === "register" ? 1 : action === "replace" ? 5 : 4,
      storage_version: action === "register" ? 1 : 9, status: action === "revoke" ? "revoked" : "active" };
    assert.deepEqual(parseBrowserCredentialResult(result, f.target), result);
    for (const wrong of [
      { ...result, storage_version: result.storage_version + 1 }, { ...result, credential_revision: result.credential_revision + 1 },
      { ...result, connection_id: account }, { ...result, status: "unknown" }, { ...result, secret: "sentinel" },
    ]) assert.throws(() => parseBrowserCredentialResult(wrong, f.target));
  });
}
for (const [label, change] of [
  ["private response field", (f: ReturnType<typeof fixture>) => Object.assign(f.start, { credentials: "sentinel" })],
  ["wrong account", (f: ReturnType<typeof fixture>) => { f.start.preview.target = { ...f.target, platform_account_id: connection }; }],
  ["unreviewed execution", (f: ReturnType<typeof fixture>) => { f.start.preview.execution_enabled = true; }],
  ["expired", (f: ReturnType<typeof fixture>) => { f.start.preview.expiresAt = now; }],
  ["extended deadline", (f: ReturnType<typeof fixture>) => { f.start.preview.expiresAt = now + 121; }],
  ["wrong RP", (f: ReturnType<typeof fixture>) => { f.start.options.rpId = "other.invalid"; }],
  ["optional UV", (f: ReturnType<typeof fixture>) => { f.start.options.userVerification = "preferred"; }],
  ["extra credential", (f: ReturnType<typeof fixture>) => { f.start.options.allowCredentials.push(f.start.options.allowCredentials[0]); }],
  ["noncanonical token", (f: ReturnType<typeof fixture>) => { f.start.flow_token += "="; }],
  ["request extensions", (f: ReturnType<typeof fixture>) => { Object.assign(f.start.options, { extensions: { private: true } }); }],
] as const) {
  test(`browser credential preparation rejects ${label}`, () => {
    const f = fixture(); change(f);
    assert.throws(() => parseBrowserCredentialStart(f.start, account, "register", rp, now));
  });
}
for (const [label, change] of [
  ["reused start token", (f: ReturnType<typeof fixture>) => { f.finish.flow_token = f.start.flow_token; }],
  ["different target", (f: ReturnType<typeof fixture>) => { f.finish.grant.target = { ...f.target, connection_id: account }; }],
  ["different account label", (f: ReturnType<typeof fixture>) => { f.finish.grant.accountName = "Other"; }],
  ["future check", (f: ReturnType<typeof fixture>) => { f.finish.grant.checkedAt = now + 1; }],
  ["extended wrapper deadline", (f: ReturnType<typeof fixture>) => { f.finish.grant.expiresAt = now + 111; }],
  ["execution flag", (f: ReturnType<typeof fixture>) => { f.finish.grant.execution_enabled = true; }],
  ["private grant field", (f: ReturnType<typeof fixture>) => { Object.assign(f.finish.grant, { body: "sentinel" }); }],
] as const) {
  test(`browser credential grant rejects ${label}`, () => {
    const f = fixture(), start = parseBrowserCredentialStart(f.start, account, "register", rp, now);
    change(f);
    assert.throws(() => parseBrowserCredentialGrant(f.finish, start, now));
  });
}
