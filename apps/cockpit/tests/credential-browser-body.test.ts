import assert from "node:assert/strict";
import test from "node:test";
import { buildBrowserCredentialBody, parseBrowserCredentialTriple } from "../src/lib/credential-browser-body.ts";
import { validatePasskeyCredentialBody } from "../src/lib/passkey-credential-token.ts";
import type { ActionTarget } from "../src/lib/credential-action-contracts.ts";

const account = "10000000-0000-0000-0000-000000000001", connection = "20000000-0000-0000-0000-000000000002";
const triple = { api_key: "synthetic-é", secret: "Synthetisch-密碼-é-e\u0301", passphrase: ' synthetic "\\test ' };
for (const action of ["register", "replace", "revoke"] as const) {
  test(`shared browser ${action} body preserves exact UTF8 and satisfies private server validation`, () => {
    const target: ActionTarget = action === "register"
      ? { action, platform_account_id: account, connection_id: connection }
      : { action, platform_account_id: account, connection_id: connection, expected_revision: 4, expected_storage: 7 };
    const body = buildBrowserCredentialBody(target, action === "revoke" ? undefined : triple);
    assert.deepEqual(new TextEncoder().encode(body), new Uint8Array(validatePasskeyCredentialBody(body, target)));
    const parsed = JSON.parse(body);
    assert.deepEqual(Object.keys(parsed), action === "register"
      ? ["platform_account_id", "connection_id", "credentials"]
      : ["platform_account_id", "connection_id", "expected_revision", "expected_storage",
        ...(action === "revoke" ? [] : ["credentials"])]);
    if (action !== "revoke") assert.deepEqual(parsed.credentials, triple);
    else assert.equal(Object.hasOwn(parsed, "credentials"), false);
  });
}
test("credential triple snapshots do not normalize or retain mutable caller objects", () => {
  const mutable = { ...triple };
  const parsed = parseBrowserCredentialTriple(mutable);
  mutable.api_key = "changed";
  assert.equal(parsed.api_key, triple.api_key);
  assert.equal(parsed.secret, triple.secret);
  assert.equal(parsed.passphrase, triple.passphrase);
  assert.equal(Object.isFrozen(parsed), true);
});
test("credential limits measure UTF8 bytes and reject malformed or invisible data", () => {
  assert.equal(parseBrowserCredentialTriple({ ...triple, api_key: "é".repeat(128) }).api_key.length, 128);
  for (const candidate of [
    { ...triple, api_key: "é".repeat(129) }, { ...triple, secret: "密".repeat(342) },
    { ...triple, passphrase: "" }, { ...triple, api_key: "\u0000key" },
    { ...triple, passphrase: "hidden\u200b" }, { ...triple, secret: "\ud800" },
    { ...triple, secret: 123 }, { ...triple, extra: "private" },
    Object.assign(Object.create({}), triple), { ...triple, [Symbol("private")]: "private" },
  ]) assert.throws(() => parseBrowserCredentialTriple(candidate));
});
test("credential parsing rejects accessors without evaluating them", () => {
  let touched = false;
  const candidate = { ...triple };
  Object.defineProperty(candidate, "secret", { get() { touched = true; return "sentinel"; } });
  assert.throws(() => parseBrowserCredentialTriple(candidate));
  assert.equal(touched, false);
});
test("revoke cannot carry a triple and register cannot omit it", () => {
  const revoke = { action: "revoke", platform_account_id: account, connection_id: connection,
    expected_revision: 1, expected_storage: 1 } as const;
  assert.throws(() => buildBrowserCredentialBody(revoke, triple));
  assert.throws(() => buildBrowserCredentialBody({ action: "register", platform_account_id: account, connection_id: connection }));
});
