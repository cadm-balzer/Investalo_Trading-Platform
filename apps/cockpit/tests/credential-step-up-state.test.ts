/** Preparatory state primitives; these tests do not establish fresh second-factor authentication. */
import test from "node:test";
import assert from "node:assert/strict";
import {
  assertCredentialConfirmation, assertCredentialGrant, assertSession, bindSession,
  CREDENTIAL_STEP_UP_AVAILABLE, makeCredentialGrant, publicCredentialGrant, requireCredentialStepUp,
} from "../src/lib/credential-step-up-state.ts";
import type {
  CredentialGrant, FreshIdentity, StepUpAttempt,
} from "../src/lib/credential-step-up-state.ts";
import {
  deriveActionTarget, parseActionTarget,
} from "../src/lib/credential-action-contracts.ts";
import type {
  CredentialAction, CredentialActionMetadata,
} from "../src/lib/credential-action-contracts.ts";
import { sha256 } from "../src/lib/security.ts";

const now = 1_700_000_000;
const tenant = "00000000-0000-0000-0000-000000000031";
const account = "00000000-0000-0000-0000-000000000032";
const connection = "00000000-0000-0000-0000-000000000033";
const other = "00000000-0000-0000-0000-000000000034";
const handle = "A".repeat(43);
const csrf = "B".repeat(43);
const confirmationToken = "C".repeat(43);
const issuer = "https://identity.fixture.invalid";
const rejected = /STEP_UP_REJECTED|STEP_UP_CHANGED|CREDENTIAL_ACTION_REJECTED/;

function fixture(action: CredentialAction = "register") {
  const principal = {
    subject: "opaque-fixture-user", issuer, oidcAuthTime: now - 600,
    tenantId: tenant, authEpoch: 3, csrf, expiresAt: now + 600,
  };
  const session = bindSession(handle, principal);
  const metadata: CredentialActionMetadata = {
    tenant_id: tenant, auth_epoch: 3,
    account: { id: account, name: "Fixture Classic", broker: "bitget", mode: "read_only", status: "ready" },
    connection: action === "register" ? null : {
      connection_id: connection, credential_revision: 4, storage_version: 7, status: "active",
    },
  };
  const target = deriveActionTarget(metadata, action, action === "register" ? { newConnectionId: connection } : {});
  const attempt: StepUpAttempt = {
    session: { ...session }, target, accountName: metadata.account.name,
    binding: "D".repeat(43), nonce: "E".repeat(43), verifier: "F".repeat(43),
    startedAt: now, expiresAt: now + 300,
  };
  const identity: FreshIdentity = {
    subject: principal.subject, issuer, authTime: now, amr: ["pwd", "otp", "mfa"], expiresAt: now + 600,
  };
  return { principal, session, metadata, attempt, identity };
}
function grantFor(value: ReturnType<typeof fixture>, at = now): CredentialGrant {
  return makeCredentialGrant(value.attempt, value.session, value.identity, value.metadata, at, confirmationToken);
}

test("fresh-factor availability stays disabled despite admissible preparatory auth_time and amr", () => {
  assert.equal(CREDENTIAL_STEP_UP_AVAILABLE, false);
  assert.throws(() => requireCredentialStepUp(), /FRESH_FACTOR_UNAVAILABLE/);
  // Pure construction is deliberately not a server-side authorization receipt.
  assert.equal(grantFor(fixture()).identity.authTime, now);
  assert.throws(() => requireCredentialStepUp(), /FRESH_FACTOR_UNAVAILABLE/);
});

test("session preparation hashes both opaque handle and CSRF instead of retaining raw tokens", () => {
  const { principal, session } = fixture();
  assert.equal(session.sessionHash, sha256(handle));
  assert.equal(session.csrfHash, sha256(csrf));
  assert.notEqual(session.sessionHash, session.csrfHash);
  assert.equal(JSON.stringify(session).includes(handle), false);
  assert.equal(JSON.stringify(session).includes(csrf), false);
  for (const invalid of ["", handle.slice(1), handle + "A", "!".repeat(43)]) {
    assert.throws(() => bindSession(invalid, principal), /STEP_UP_REJECTED/);
  }
  assert.throws(() => bindSession(handle, { ...principal, tenantId: undefined }), /STEP_UP_REJECTED/);
  assert.throws(() => bindSession(handle, { ...principal, authEpoch: undefined }), /STEP_UP_REJECTED/);
});

for (const [field, replacement] of [
  ["sessionHash", sha256("G".repeat(43))], ["csrfHash", sha256("H".repeat(43))],
  ["subject", "another-opaque-user"], ["issuer", "https://other.fixture.invalid"],
  ["tenantId", other], ["authEpoch", 4],
] as const) {
  test(`preparatory state rejects changed ${field} at construction and subsequent validation`, () => {
    const f = fixture(), grant = grantFor(f);
    const changed = { ...f.session, [field]: replacement };
    assert.throws(() => assertSession(f.attempt.session, changed, now), /STEP_UP_REJECTED/);
    assert.throws(() => makeCredentialGrant(f.attempt, changed, f.identity, f.metadata, now, confirmationToken), rejected);
    assert.throws(() => assertCredentialGrant(grant, changed, f.metadata, now), rejected);
  });
}

test("expired original/current sessions reject preparatory use and cannot be revived by a later expiry", () => {
  const f = fixture(), grant = grantFor(f);
  assert.doesNotThrow(() => assertSession(f.session, { ...f.session }, now));
  for (const expiry of [now - 1, now]) {
    assert.throws(() => assertSession({ ...f.session, expiresAt: expiry }, f.session, now), rejected);
    assert.throws(() => assertSession(f.session, { ...f.session, expiresAt: expiry }, now), rejected);
    assert.throws(() => assertCredentialGrant(grant, { ...f.session, expiresAt: expiry }, f.metadata, now), rejected);
  }
  // Actual logout also removes the server session; this pure test covers its
  // expired-state representation, not the server store lifecycle.
  const expiredGrant = { ...grant, session: { ...grant.session, expiresAt: now } };
  assert.throws(() => assertCredentialGrant(expiredGrant, { ...f.session, expiresAt: now + 900 }, f.metadata, now), rejected);
});

for (const action of ["register", "replace", "revoke"] as const) {
  test(`preparatory ${action} preserves its frozen account/connection and exact CAS target`, () => {
    const f = fixture(action), grant = grantFor(f);
    assert.deepEqual(grant.target, f.attempt.target);
    assert.equal(Object.isFrozen(grant.target), true);
    assert.notEqual(grant.target, f.attempt.target);
    assert.doesNotThrow(() => assertCredentialGrant(grant, f.session, f.metadata, now));
    assert.throws(() => {
      (grant.target as unknown as { connection_id: string }).connection_id = other;
    }, TypeError);
    if (grant.target.action !== "register") {
      assert.equal(grant.target.expected_revision, 4);
      assert.equal(grant.target.expected_storage, 7);
    } else {
      assert.equal("expected_revision" in grant.target, false);
      assert.equal("expected_storage" in grant.target, false);
    }
  });
}

test("preparatory actions reject changed account, display name, tenant and recovery epoch", () => {
  for (const action of ["register", "replace", "revoke"] as const) {
    const f = fixture(action), grant = grantFor(f);
    const mutations: CredentialActionMetadata[] = [
      { ...f.metadata, account: { ...f.metadata.account, id: other } },
      { ...f.metadata, account: { ...f.metadata.account, name: "Changed name" } },
      { ...f.metadata, tenant_id: other }, { ...f.metadata, auth_epoch: 4 },
    ];
    for (const changed of mutations) {
      assert.throws(() => makeCredentialGrant(f.attempt, f.session, f.identity, changed, now, confirmationToken), rejected);
      assert.throws(() => assertCredentialGrant(grant, f.session, changed, now), rejected);
    }
  }
});

test("registration cannot convert to replacement when another connection appeared", () => {
  const f = fixture(), grant = grantFor(f), active = fixture("replace").metadata;
  assert.throws(() => makeCredentialGrant(f.attempt, f.session, f.identity, active, now, confirmationToken), rejected);
  assert.throws(() => assertCredentialGrant(grant, f.session, active, now), rejected);
});

test("replacement and revoke reject changes of either independent CAS cursor or connection identity", () => {
  for (const action of ["replace", "revoke"] as const) {
    const f = fixture(action), grant = grantFor(f);
    for (const patch of [{ credential_revision: 5 }, { storage_version: 8 }, { connection_id: other }]) {
      const changed = { ...f.metadata, connection: { ...f.metadata.connection!, ...patch } };
      assert.throws(() => makeCredentialGrant(f.attempt, f.session, f.identity, changed, now, confirmationToken), rejected);
      assert.throws(() => assertCredentialGrant(grant, f.session, changed, now), rejected);
    }
    const absent = { ...f.metadata, connection: null };
    assert.throws(() => assertCredentialGrant(grant, f.session, absent, now), rejected);
  }
});

test("paused accounts retain only protective revoke preparation and revoked state remains terminal", () => {
  for (const action of ["register", "replace", "revoke"] as const) {
    const f = fixture(action), grant = grantFor(f);
    const paused = { ...f.metadata, account: { ...f.metadata.account, status: "paused" as const } };
    if (action === "revoke") {
      const prepared = makeCredentialGrant(f.attempt, f.session, f.identity, paused, now, confirmationToken);
      assert.doesNotThrow(() => assertCredentialGrant(prepared, f.session, paused, now));
      assert.doesNotThrow(() => assertCredentialGrant(grant, f.session, paused, now));
    } else {
      assert.throws(() => makeCredentialGrant(f.attempt, f.session, f.identity, paused, now, confirmationToken), rejected);
      assert.throws(() => assertCredentialGrant(grant, f.session, paused, now), rejected);
    }
    const revoked: CredentialActionMetadata = {
      ...f.metadata, connection: { connection_id: connection, credential_revision: 4, storage_version: 7, status: "revoked" },
    };
    assert.throws(() => makeCredentialGrant(f.attempt, f.session, f.identity, revoked, now, confirmationToken), rejected);
    assert.throws(() => assertCredentialGrant(grant, f.session, revoked, now), rejected);
  }
});

test("typed but tampered action targets cannot add authority or silently change operation", () => {
  const f = fixture("replace");
  for (const target of [
    { ...f.attempt.target, platform_account_id: other },
    { ...f.attempt.target, connection_id: other },
    { ...f.attempt.target, expected_revision: 3 },
    { ...f.attempt.target, expected_storage: 6 },
    { ...f.attempt.target, broker_uid: "private-marker" },
    { ...f.attempt.target, action: "register" },
  ]) {
    const attempt = { ...f.attempt, target: target as StepUpAttempt["target"] };
    assert.throws(() => makeCredentialGrant(attempt, f.session, f.identity, f.metadata, now, confirmationToken), rejected);
  }
  const revokedTarget = parseActionTarget({ ...f.attempt.target, action: "revoke" });
  // A structurally different target can prepare its own action, never mutate
  // a previously issued frozen target.
  assert.notDeepEqual(revokedTarget, grantFor(f).target);
});

test("preparatory claims must match issuer/subject and structurally contain distinct mfa methods", () => {
  const f = fixture();
  for (const patch of [
    { subject: "another-user" }, { issuer: "https://other.fixture.invalid" },
    { amr: [] }, { amr: ["pwd", "otp"] }, { amr: ["mfa", "mfa"] },
    { amr: ["MFA"] }, { amr: ["mfa", "bad\nmethod"] },
    { amr: ["mfa", true] }, { amr: "mfa" },
    { amr: ["mfa", ...Array.from({ length: 8 }, (_, index) => `factor${index}`)] },
  ]) {
    const identity = { ...f.identity, ...patch } as FreshIdentity;
    assert.throws(() => makeCredentialGrant(f.attempt, f.session, identity, f.metadata, now, confirmationToken), rejected);
  }
});

test("preparatory freshness never permits authentication before the stored attempt start", () => {
  const f = fixture();
  assert.throws(() => makeCredentialGrant(f.attempt, f.session,
    { ...f.identity, authTime: now - 1 }, f.metadata, now, confirmationToken), rejected);
  assert.doesNotThrow(() => grantFor(f));
  const future = { ...f.identity, authTime: now + 5 };
  assert.doesNotThrow(() => makeCredentialGrant({ ...f.attempt, startedAt: now + 5 },
    f.session, future, f.metadata, now, confirmationToken));
  assert.throws(() => makeCredentialGrant(f.attempt, f.session,
    { ...f.identity, authTime: now + 6 }, f.metadata, now, confirmationToken), rejected);
  assert.throws(() => makeCredentialGrant({ ...f.attempt, startedAt: now + 6 },
    f.session, future, f.metadata, now, confirmationToken), rejected);
});

test("whole-second preparation lifetime excludes its expiry and exhausted 120-second auth window", () => {
  const f = fixture();
  const attempt = { ...f.attempt, startedAt: now - 300 };
  const nearExpiry = { ...f.identity, authTime: now - 119 };
  const grant = makeCredentialGrant(attempt, f.session, nearExpiry, f.metadata, now, confirmationToken);
  assert.equal(grant.expiresAt, now + 1);
  assert.doesNotThrow(() => assertCredentialGrant(grant, f.session, f.metadata, now));
  assert.throws(() => assertCredentialGrant(grant, f.session, f.metadata, now + 1), rejected);
  assert.throws(() => makeCredentialGrant(attempt, f.session,
    { ...nearExpiry, authTime: now - 120 }, f.metadata, now, confirmationToken), rejected);
  assert.throws(() => makeCredentialGrant(attempt, f.session,
    { ...nearExpiry, authTime: now - 121 }, f.metadata, now, confirmationToken), rejected);
  assert.throws(() => makeCredentialGrant({ ...attempt, startedAt: now - 301 },
    f.session, nearExpiry, f.metadata, now, confirmationToken), rejected);
  assert.throws(() => makeCredentialGrant({ ...attempt, expiresAt: now },
    f.session, f.identity, f.metadata, now, confirmationToken), rejected);
  assert.throws(() => makeCredentialGrant(f.attempt, f.session,
    { ...f.identity, expiresAt: now }, f.metadata, now, confirmationToken), rejected);
});

test("preparatory expiry is capped independently by original/current session and ID-token expiration", () => {
  for (const source of ["original", "current", "identity"] as const) {
    const f = fixture();
    if (source === "original") f.attempt.session.expiresAt = now + 10;
    if (source === "current") f.session.expiresAt = now + 10;
    if (source === "identity") f.identity.expiresAt = now + 10;
    assert.equal(grantFor(f).expiresAt, now + 10);
  }
  const f = fixture();
  assert.equal(grantFor(f).expiresAt, now + 120);
  const grant = grantFor(f);
  assert.doesNotThrow(() => assertCredentialGrant(grant, f.session, f.metadata, now + 119));
  assert.throws(() => assertCredentialGrant(grant, f.session, f.metadata, now + 120), rejected);
  for (const expiry of [now, now - 1, now + 121, NaN, Infinity, 1.5]) {
    assert.throws(() => assertCredentialGrant({ ...grant, expiresAt: expiry }, f.session, f.metadata, now), rejected);
  }
});

test("invalid numeric preparation clocks and identity expiries reject instead of coercing", () => {
  for (const value of [NaN, Infinity, -Infinity, 1.5, true, "1700000000"]) {
    const f = fixture(), malformed = value as number;
    assert.throws(() => makeCredentialGrant(f.attempt, f.session, f.identity, f.metadata, malformed, confirmationToken), rejected);
    assert.throws(() => makeCredentialGrant({ ...f.attempt, startedAt: malformed },
      f.session, f.identity, f.metadata, now, confirmationToken), rejected);
    assert.throws(() => makeCredentialGrant(f.attempt, f.session,
      { ...f.identity, authTime: malformed }, f.metadata, now, confirmationToken), rejected);
    assert.throws(() => makeCredentialGrant(f.attempt, f.session,
      { ...f.identity, expiresAt: malformed }, f.metadata, now, confirmationToken), rejected);
  }
});

test("opaque confirmation is required for preparation and mismatch leaves the grant untouched", () => {
  const f = fixture(), grant = grantFor(f), original = structuredClone(grant);
  assert.doesNotThrow(() => assertCredentialConfirmation(grant, confirmationToken));
  for (const token of ["", confirmationToken.slice(1), confirmationToken + "C",
    "!".repeat(43), "X".repeat(43)]) {
    assert.throws(() => assertCredentialConfirmation(grant, token), /STEP_UP_REJECTED/);
    assert.deepEqual(grant, original);
  }
  for (const token of ["", confirmationToken.slice(1), confirmationToken + "C", "!".repeat(43)]) {
    assert.throws(() => makeCredentialGrant(f.attempt, f.session, f.identity, f.metadata, now, token), rejected);
  }
  // Consumption belongs to the server store; a pure failed comparison never
  // consumes or changes the prepared state.
  assert.doesNotThrow(() => assertCredentialConfirmation(grant, confirmationToken));
});

test("public preparation projection contains only target/name/expiry and opaque confirmation", () => {
  const f = fixture("replace"), grant = grantFor(f), result = publicCredentialGrant(grant);
  assert.deepEqual(Object.keys(result).sort(), ["accountName", "confirmationToken", "expiresAt", "target"]);
  assert.deepEqual(result, {
    target: grant.target, accountName: "Fixture Classic", expiresAt: now + 120, confirmationToken,
  });
  const wire = JSON.stringify(result);
  for (const privateField of ["sessionHash", "csrfHash", "subject", "issuer", "authEpoch",
    "tenantId", "identity", "authTime", "amr", "startedAt", "nonce", "verifier",
    "broker_uid", "parent_uid", "ciphertext", "kek_id"]) {
    assert.equal(wire.includes(`"${privateField}"`), false);
  }
  assert.notEqual(result.target, grant.target);
  assert.equal(Object.isFrozen(result.target), true);
});

test("preparation copies session/identity/amr and public projection cannot mutate the original", () => {
  const f = fixture(), grant = grantFor(f), projection = publicCredentialGrant(grant);
  assert.notEqual(grant.session, f.session);
  assert.notEqual(grant.identity, f.identity);
  assert.notEqual(grant.identity.amr, f.identity.amr);
  f.session.subject = "changed-after-copy";
  f.attempt.session.tenantId = other;
  f.identity.authTime = now - 600;
  f.identity.amr.push("changed");
  assert.equal(grant.session.subject, "opaque-fixture-user");
  assert.equal(grant.session.tenantId, tenant);
  assert.equal(grant.identity.authTime, now);
  assert.deepEqual(grant.identity.amr, ["pwd", "otp", "mfa"]);
  projection.accountName = "projection-only";
  projection.confirmationToken = "Z".repeat(43);
  assert.equal(grant.accountName, "Fixture Classic");
  assert.equal(grant.confirmationToken, confirmationToken);
});
