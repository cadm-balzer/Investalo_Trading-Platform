/** State invariants only; DB ticket consumption, browser ceremonies and role fencing have separate tests. */
import assert from "node:assert/strict";
import { randomBytes } from "node:crypto";
import test from "node:test";
import {
  assertEnrollment, canonicalBytes, enrollmentBinding, exactObject, parseEnrollmentJson,
  parsePasskeyContext, parsePasskeyRecord,
  type EnrollmentAttempt, type PasskeyContext,
} from "../src/lib/passkey-enrollment-state.ts";
import type { Session } from "../src/lib/auth.ts";

const NOW = 1_794_080_000;
const TENANT = "10000000-0000-0000-0000-000000000001";
const USER = "20000000-0000-0000-0000-000000000002";
const OTHER = "30000000-0000-0000-0000-000000000003";
const RP = "cockpit.local.test";
const encoded = (size: number) => randomBytes(size).toString("base64url");
const staticError = (error: unknown) => {
  assert.equal((error as Error).message, "PASSKEY_ENROLLMENT_REJECTED");
  assert.equal((error as Error).cause, undefined);
  return true;
};
function fixture() {
  const handle = encoded(32);
  const session: Session = { subject: "opaque-idp-user", issuer: "https://idp.fixture.invalid",
    oidcAuthTime: NOW - 300, tenantId: TENANT, authEpoch: 4, expiresAt: NOW + 600,
    csrf: encoded(32), displayName: "Fixture", tenantName: "Fixture tenant" };
  const current: PasskeyContext = { tenant_id: TENANT, user_id: USER, auth_epoch: 4, rp_id: RP, credential: null };
  const attempt: EnrollmentAttempt = { tenantId: TENANT, userId: USER, authEpoch: 4,
    rpId: RP, origin: `https://${RP}:8443`, claimId: OTHER, userHandle: encoded(32),
    challenge: encoded(32), startedAt: NOW, expiresAt: NOW + 120, binding: enrollmentBinding(handle, session) };
  return { handle, session, current, attempt };
}
function record() {
  return { passkey_id: OTHER, tenant_id: TENANT, user_id: USER, rp_id: RP,
    credential_id: encoded(32), user_handle: encoded(32), public_key: encoded(77),
    sign_count: 0, backup_eligible: true, backed_up: true, storage_version: 1,
    status: "active", enrollment_epoch: 4 };
}
const owner = { tenantId: TENANT, userId: USER, rpId: RP };
const expected = { tenantId: TENANT, authEpoch: 4, rpId: RP };

test("enrollment binding retains no raw session handle/CSRF and a valid null-registry attempt passes", () => {
  const f = fixture();
  assert.match(f.attempt.binding, /^[a-f0-9]{64}$/);
  assert.equal(f.attempt.binding.includes(f.handle), false);
  assert.equal(f.attempt.binding.includes(f.session.csrf), false);
  assert.doesNotThrow(() => assertEnrollment(f.attempt, f.handle, f.session, f.current, NOW));
  assert.doesNotThrow(() => assertEnrollment(f.attempt, f.handle,
    { ...f.session, displayName: "New display name", tenantName: "New tenant label" }, f.current, NOW));
});

for (const [field, replacement] of [
  ["csrf", encoded(32)], ["subject", "different-idp-user"], ["issuer", "https://other-idp.fixture.invalid"],
  ["tenantId", OTHER], ["authEpoch", 5], ["oidcAuthTime", NOW - 299],
] as const) {
  test(`enrollment cannot transplant the attempt after session ${field} changes`, () => {
    const f = fixture();
    const changed = { ...f.session, [field]: replacement };
    assert.notEqual(enrollmentBinding(f.handle, changed), f.attempt.binding);
    assert.throws(() => assertEnrollment(f.attempt, f.handle, changed, f.current, NOW), staticError);
  });
}

test("another browser session, malformed handle/CSRF or a changed attempt binding is rejected", () => {
  const f = fixture();
  assert.throws(() => assertEnrollment(f.attempt, encoded(32), f.session, f.current, NOW), staticError);
  assert.throws(() => assertEnrollment({ ...f.attempt, binding: "0".repeat(64) }, f.handle, f.session, f.current, NOW), staticError);
  for (const invalid of ["", encoded(31), encoded(33), "Zh", f.handle + "="]) {
    assert.throws(() => enrollmentBinding(invalid, f.session), staticError);
    assert.throws(() => enrollmentBinding(f.handle, { ...f.session, csrf: invalid }), staticError);
  }
});

test("current authoritative user/tenant/RP/recovery epoch must remain exactly the attempt owner", () => {
  const f = fixture();
  for (const change of [{ user_id: OTHER }, { tenant_id: OTHER }, { rp_id: "other.local.test" }, { auth_epoch: 5 }]) {
    assert.throws(() => assertEnrollment(f.attempt, f.handle, f.session, { ...f.current, ...change }, NOW), staticError);
  }
  // A mutually changed typed attempt/context must still agree with the bound session tenant.
  assert.throws(() => assertEnrollment({ ...f.attempt, tenantId: OTHER }, f.handle, f.session,
    { ...f.current, tenant_id: OTHER }, NOW), staticError);
});

test("appearance of any existing active or revoked passkey blocks completing another enrollment", () => {
  const f = fixture();
  for (const status of ["active", "revoked"] as const) {
    const credential = parsePasskeyRecord({ ...record(), status }, owner);
    assert.throws(() => assertEnrollment(f.attempt, f.handle, f.session, { ...f.current, credential }, NOW), staticError);
  }
});

test("120-second lifetime and whole-second expiry boundaries exclude stale and future attempts", () => {
  const f = fixture();
  assert.doesNotThrow(() => assertEnrollment(f.attempt, f.handle, f.session, f.current, NOW + 119));
  assert.throws(() => assertEnrollment(f.attempt, f.handle, f.session, f.current, NOW + 120), staticError);
  for (const change of [
    { startedAt: NOW + 1 }, { startedAt: NOW - 121 }, { expiresAt: NOW },
    { expiresAt: NOW + 121 }, { startedAt: NaN }, { expiresAt: Infinity },
    { startedAt: NOW + 0.5 }, { expiresAt: NOW + 0.5 },
  ]) assert.throws(() => assertEnrollment({ ...f.attempt, ...change }, f.handle, f.session, f.current, NOW), staticError);
});

test("expired sessions and invalid verification clocks cannot authorize the post-await finish dispatch", () => {
  const f = fixture();
  for (const expiresAt of [NOW - 1, NOW, NaN, Infinity, NOW + 0.5]) {
    assert.throws(() => assertEnrollment(f.attempt, f.handle, { ...f.session, expiresAt }, f.current, NOW), staticError);
  }
  for (const now of [NaN, Infinity, -Infinity, 0, -1, NOW + 0.5]) {
    assert.throws(() => assertEnrollment(f.attempt, f.handle, f.session, f.current, now), staticError);
  }
});

test("context parser isolates authenticated tenant/epoch/RP and authoritative internal user UUID", () => {
  const f = fixture(), value = parsePasskeyContext(f.current, expected);
  assert.deepEqual(value, f.current);
  assert(Object.isFrozen(value));
  assert.equal(value.user_id, USER);
  for (const change of [
    { tenant_id: OTHER }, { auth_epoch: 3 }, { rp_id: "other.local.test" },
    { user_id: "opaque-idp-subject" }, { auth_epoch: true }, { auth_epoch: 1.5 },
    { public_key: "private-extra-field" },
  ]) assert.throws(() => parsePasskeyContext({ ...f.current, ...change }, expected));
});

test("credential row parser binds independent tenant/user/RP and rejects extra private transport fields", () => {
  const row = record(), parsed = parsePasskeyRecord(row, owner);
  assert.deepEqual(parsed, row);
  assert(Object.isFrozen(parsed));
  for (const change of [
    { tenant_id: OTHER }, { user_id: OTHER }, { rp_id: "other.local.test" },
    { passkey_id: "not-a-uuid" }, { unknown: "private-sentinel" },
  ]) assert.throws(() => parsePasskeyRecord({ ...row, ...change }, owner));
  const f = fixture();
  assert.throws(() => parsePasskeyContext({ ...f.current, credential: { ...row, user_id: OTHER } }, expected));
});

test("registry fields distinguish zero counters, safe versions, epoch, backup flags and terminal status", () => {
  const row = record();
  assert.equal(parsePasskeyRecord(row, owner).sign_count, 0);
  assert.equal(parsePasskeyRecord({ ...row, sign_count: 0xffff_ffff }, owner).sign_count, 0xffff_ffff);
  assert.equal(parsePasskeyRecord({ ...row, status: "revoked", storage_version: 2 }, owner).status, "revoked");
  for (const change of [
    { sign_count: -1 }, { sign_count: 0x1_0000_0000 }, { sign_count: 1.5 }, { sign_count: true },
    { storage_version: 0 }, { storage_version: Number.MAX_SAFE_INTEGER + 1 }, { storage_version: "1" },
    { enrollment_epoch: -1 }, { enrollment_epoch: NaN }, { status: "pending" },
    { backup_eligible: false, backed_up: true }, { backup_eligible: "true" }, { backed_up: 1 },
  ]) assert.throws(() => parsePasskeyRecord({ ...row, ...change }, owner));
});

test("canonical byte fields preserve W3C credential-ID limit 1023 and exact opaque handle size", () => {
  const row = record(), maximum = encoded(1023);
  assert.equal(parsePasskeyRecord({ ...row, credential_id: maximum }, owner).credential_id, maximum);
  for (const change of [
    { credential_id: encoded(1024) }, { credential_id: "Zh" }, { credential_id: row.credential_id + "=" },
    { user_handle: encoded(31) }, { user_handle: encoded(33) },
    { public_key: "" }, { public_key: encoded(2049) },
  ]) assert.throws(() => parsePasskeyRecord({ ...row, ...change }, owner), staticError);
  assert.equal(canonicalBytes(row.user_handle, 32, 32), row.user_handle);
});

test("exact objects reject authority extras, arrays, prototypes and accessors without running getters", () => {
  for (const value of [null, [], Object.create({ token: "inherited" }), { token: "x", tenant_id: OTHER }]) {
    assert.throws(() => exactObject(value, ["token"]), staticError);
  }
  let touched = false;
  const accessor = Object.defineProperty({}, "token", { enumerable: true,
    get: () => { touched = true; throw new Error("ticket-secret"); } });
  assert.throws(() => exactObject(accessor, ["token"]), staticError);
  assert.equal(touched, false);
  assert.deepEqual(exactObject({ token: "x" }, ["token"]), { token: "x" });
});

test("wire parsing rejects duplicate and escaped keys at outer, nested credential and extension levels", () => {
  for (const wire of [
    '{"token":"first","token":"second"}',
    '{"token":"first","to\\u006ben":"second"}',
    '{"attempt_id":"x","credential":{"id":"first","id":"second"}}',
    '{"credential":{"clientExtensionResults":{"credProps":{"rk":true,"r\\u006b":false}}}}',
  ]) assert.throws(() => parseEnrollmentJson(wire), staticError);
  assert.deepEqual(parseEnrollmentJson('{"token":"opaque-ticket"}'), { token: "opaque-ticket" });
  assert.deepEqual(parseEnrollmentJson('{"credential":{"response":{"transports":["internal","hybrid"]}}}'),
    { credential: { response: { transports: ["internal", "hybrid"] } } });
});

test("malformed, oversized, over-depth and over-node wire fails statically without ticket disclosure", () => {
  for (const wire of [
    '{"token":"private-ticket"', '{"token": private-ticket}', "private-ticket",
    "null", "[]", " ".repeat(16_385), '{"a":{"b":{"c":{"d":{"e":{"f":{"g":{}}}}}}}}',
    JSON.stringify({ a: Array.from({ length: 161 }, () => 0) }),
    '{"token":"\ud800"}',
  ]) assert.throws(() => parseEnrollmentJson(wire), staticError);
});
