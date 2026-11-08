/**
 * Real SimpleWebAuthn P256 verification and Jose assertions through the closed
 * injected protocol. Durable SQL transactions have separate actual PG tests.
 */
import assert from "node:assert/strict";
import { createHash, generateKeyPairSync, randomBytes, sign } from "node:crypto";
import test from "node:test";
import { isoCBOR } from "@simplewebauthn/server/helpers";
import { jwtVerify } from "jose";
import {
  beginPasskeyCredentialFlow, executePasskeyCredentialFlow, finishPasskeyCredentialFlow,
  type PasskeyCredentialPorts, type SafeOnboardingResult,
} from "../src/lib/passkey-credential-flow.ts";
import { actionProofBinding, type ActionProofAttempt, type ActionProofGrant,
  type ProofSession } from "../src/lib/passkey-action-proof-state.ts";
import type { CredentialAction, CredentialActionMetadata } from "../src/lib/credential-action-contracts.ts";
import type { PasskeyContext } from "../src/lib/passkey-enrollment-state.ts";
import { PASSKEY_CREDENTIAL_KIND, PASSKEY_CREDENTIAL_AUDIENCE,
  type PasskeyCredentialAuthorization } from "../src/lib/passkey-credential-token.ts";

const id = (n: number) => `00000000-0000-0000-0000-${n.toString().padStart(12, "0")}`;
const TENANT = id(1), USER = id(2), ACCOUNT = id(3), CONNECTION = id(4);
const FACTOR = id(5), ATTEMPT = id(6), GRANT = id(7), AUTHORIZATION = id(8);
const RP = "cockpit.fixture.invalid", ORIGIN = `https://${RP}:8443`;
const encoded = (value: Uint8Array) => Buffer.from(value).toString("base64url");
const token = () => encoded(randomBytes(32));
const sha = (value: string | Uint8Array) => createHash("sha256").update(value).digest("hex");
const clone = <T>(value: T): T => structuredClone(value);
const consent = Object.freeze({ kind: "credential-write" as const, confirmed: true as const });
const reject = (error: unknown) => {
  assert.equal((error as Error).message, "PASSKEY_CREDENTIAL_FLOW_REJECTED");
  assert.equal((error as Error).cause, undefined);
  return true;
};

function fixture(action: CredentialAction = "register", paused = false) {
  const started = Math.floor(Date.now() / 1000);
  const { publicKey, privateKey } = generateKeyPairSync("ec", { namedCurve: "prime256v1" });
  const jwk = publicKey.export({ format: "jwk" });
  const cose = isoCBOR.encode(new Map<number, number | Uint8Array>([
    [1, 2], [3, -7], [-1, 1], [-2, Buffer.from(jwk.x!, "base64url")], [-3, Buffer.from(jwk.y!, "base64url")],
  ]));
  const f = {
    bound: { handle: token(), origin: ORIGIN, session: { subject: "opaque-fixture-subject",
      issuer: "https://idp.fixture.invalid", oidcAuthTime: started - 3600, tenantId: TENANT,
      authEpoch: 4, expiresAt: started + 1800, csrf: token(), displayName: "Fixture", tenantName: "Fixture" } } as ProofSession,
    context: { tenant_id: TENANT, user_id: USER, auth_epoch: 4, rp_id: RP,
      credential: { passkey_id: FACTOR, tenant_id: TENANT, user_id: USER, rp_id: RP,
        credential_id: token(), user_handle: token(), public_key: encoded(cose),
        sign_count: 0, backup_eligible: false, backed_up: false, storage_version: 1,
        status: "active", enrollment_epoch: 4 } } as PasskeyContext,
    metadata: { tenant_id: TENANT, auth_epoch: 4, account: {
      id: ACCOUNT, name: "Synthetic read-only account", broker: "bitget", mode: "read_only",
      status: paused ? "paused" : action === "register" ? "disconnected" : "ready",
    }, connection: action === "register" ? null : {
      connection_id: CONNECTION, credential_revision: 2, storage_version: 3, status: "active",
    } } as CredentialActionMetadata,
    attempt: null as ActionProofAttempt | null, grant: null as ActionProofGrant | null,
    body: "", bodyHash: "", metadataHash: "c".repeat(64), claimed: false, authorized: false,
    executed: false, offset: 0, events: [] as string[], bodySent: "" as string,
    requests: [] as Record<string, unknown>[], jwt: null as Awaited<ReturnType<typeof jwtVerify>> | null,
    key: new Uint8Array(32).fill(87), executorKey: new Uint8Array(32).fill(87),
    hooks: new Map<string, () => void | Promise<void>>(),
    tamper: (event: string, value: unknown): unknown => value,
    executeInput: (signed: string, body: string) => ({ signed, body }),
  };
  const now = () => Math.floor(Date.now() / 1000) + f.offset;
  const ports: PasskeyCredentialPorts = {
    now, randomToken: token, randomUuid: () => CONNECTION,
    current: async () => { await f.hooks.get("current")?.(); return clone(f.bound); },
    context: async () => { await f.hooks.get("context")?.(); return clone(f.context); },
    metadata: async (_session, account) => {
      assert.equal(account, ACCOUNT); await f.hooks.get("metadata")?.(); return clone(f.metadata);
    },
    request: async (session, path, body) => {
      const event = path.split("/").at(-1)!;
      f.events.push(event); f.requests.push(clone(body));
      assert.equal(body.session_binding, actionProofBinding(f.bound));
      let value: unknown;
      if (event === "prepare") {
        assert.equal(path, "/v1/passkey-credential-authorizations/prepare");
        f.bodyHash = body.body_sha256 as string;
        f.attempt = { attempt_id: ATTEMPT, tenant_id: TENANT, user_id: USER, auth_epoch: 4, rp_id: RP,
          target: body.target as ActionProofAttempt["target"], metadata: clone(f.metadata),
          credential: clone(f.context.credential!), session_binding: body.session_binding as string,
          challenge: body.challenge as string, confirmation_hash: body.confirmation_hash as string,
          prepared_at: now(), expires_at: now() + 120, session_expires_at: session.expiresAt };
        value = { authorization_id: AUTHORIZATION, metadata_sha256: f.metadataHash, attempt: clone(f.attempt) };
      } else if (event === "claim") {
        assert(f.attempt); assert.equal(body.attempt_id, ATTEMPT);
        if (f.claimed) throw new Error("private synthetic transport error");
        f.claimed = true; value = clone(f.attempt);
      } else if (event === "finish") {
        assert(f.claimed && f.attempt);
        f.context = { ...f.context, credential: { ...f.context.credential!,
          sign_count: body.new_counter as number, backed_up: body.backed_up as boolean, storage_version: 2 } };
        f.grant = { grant_id: GRANT, attempt_id: ATTEMPT, tenant_id: TENANT, user_id: USER,
          auth_epoch: 4, rp_id: RP, target: f.attempt.target, metadata: f.attempt.metadata,
          passkey_id: FACTOR, passkey_version: 2, session_binding: f.attempt.session_binding,
          confirmation_hash: f.attempt.confirmation_hash, checked_at: body.checked_at as number,
          expires_at: (body.checked_at as number) + 120, session_expires_at: session.expiresAt };
        value = clone(f.grant);
      } else if (event === "grant") {
        assert(f.grant); assert.equal(body.grant_id, GRANT);
        if (f.authorized) throw new Error("grant consumed");
        value = clone(f.grant);
      } else if (event === "authorize") {
        assert.equal(path, "/v1/passkey-credential-authorizations/authorize");
        assert(f.grant && f.attempt); assert.equal(body.authorization_id, AUTHORIZATION);
        assert.equal(body.grant_id, GRANT); assert.equal(body.confirmation_hash, f.grant.confirmation_hash);
        if (f.authorized) throw new Error("authorization consumed");
        f.authorized = true;
        const receipt: PasskeyCredentialAuthorization = {
          kind: PASSKEY_CREDENTIAL_KIND, authorization_id: AUTHORIZATION, proof_id: ATTEMPT, grant_id: GRANT,
          tenant_id: TENANT, user_id: USER, subject: session.subject, auth_epoch: session.authEpoch,
          oidc_issuer: session.issuer, oidc_auth_time: session.oidcAuthTime, rp_id: RP, origin: ORIGIN,
          session_binding: f.grant.session_binding, session_expires_at: session.expiresAt,
          passkey_id: FACTOR, passkey_version: 2, target: f.grant.target,
          prepared_at: f.attempt.prepared_at, checked_at: f.grant.checked_at,
          authorized_at: now(), expires_at: f.grant.expires_at,
          metadata_sha256: f.metadataHash, body_sha256: f.bodyHash,
        };
        value = { status: "authorized", execution_enabled: false, authorization: receipt };
      } else throw new Error("Unexpected path");
      await f.hooks.get(event)?.();
      return f.tamper(event, value);
    },
    credentialKey: async () => {
      f.events.push("key");
      await f.hooks.get("key")?.();
      return f.key;
    },
    execute: async (signed, body) => {
      f.events.push("execute");
      const input = f.executeInput(signed, body);
      // Model the private executor's exact-body/audience/key boundary using real Jose.
      f.jwt = await jwtVerify(input.signed, f.executorKey, { audience: PASSKEY_CREDENTIAL_AUDIENCE,
        issuer: "investalo-bff", algorithms: ["HS256"] });
      assert.equal(f.jwt.payload.body_sha256, sha(input.body));
      assert.equal(input.body, f.body);
      f.bodySent = body; f.executed = true;
      const target = f.grant!.target;
      const result: SafeOnboardingResult = { connection_id: target.connection_id,
        credential_revision: target.action === "register" ? 1 :
          target.expected_revision + (target.action === "replace" ? 1 : 0),
        storage_version: target.action === "register" ? 1 : target.expected_storage + 1,
        status: target.action === "revoke" ? "revoked" : "active" };
      f.metadata = { ...f.metadata, connection: clone(result) };
      await f.hooks.get("execute")?.();
      return f.tamper("execute", result);
    },
  };
  async function begin(factory?: Parameters<typeof beginPasskeyCredentialFlow>[4]) {
    return beginPasskeyCredentialFlow(ports, f.bound, ACCOUNT, action, factory ?? (target => {
      const { action: _action, ...fields } = target;
      f.body = JSON.stringify({ ...fields, ...(action === "revoke" ? {} : {
        credentials: { api_key: "SYNTHETIC-KEY", secret: "synthetic-ß-key", passphrase: "synthetic-passphrase" },
      }) }, null, 2) + "\n";
      return f.body;
    }));
  }
  function assertion(challenge: string, changes: {
    privateKey?: typeof privateKey; challenge?: string; flags?: number;
  } = {}) {
    const client = Buffer.from(JSON.stringify({ type: "webauthn.get", challenge: changes.challenge ?? challenge,
      origin: ORIGIN, crossOrigin: false }));
    const count = Buffer.alloc(4); count.writeUInt32BE(1);
    const data = Buffer.concat([Buffer.from(sha(RP), "hex"), Buffer.from([changes.flags ?? 0x05]), count]);
    return { id: f.context.credential!.credential_id, rawId: f.context.credential!.credential_id,
      type: "public-key", clientExtensionResults: {}, response: {
        clientDataJSON: encoded(client), authenticatorData: encoded(data),
        signature: encoded(sign("sha256", Buffer.concat([data, Buffer.from(sha(client), "hex")]),
          changes.privateKey ?? privateKey)), userHandle: f.context.credential!.user_handle,
      } };
  }
  async function proved() {
    const prepared = await begin();
    const granted = await finishPasskeyCredentialFlow(ports, f.bound, prepared, assertion(prepared.options.challenge));
    return { prepared, granted };
  }
  async function execute(granted: Awaited<ReturnType<typeof finishPasskeyCredentialFlow>>, body = f.body) {
    return executePasskeyCredentialFlow(ports, f.bound, granted, body, consent);
  }
  return { f, ports, begin, assertion, proved, execute };
}

for (const action of ["register", "replace", "revoke"] as const) {
  test(`${action}: fresh realP256 proof, explicit008 consent, signed exactbody and safeCAS result`, async () => {
    const x = fixture(action), original = clone(x.f.bound), { prepared, granted } = await x.proved();
    assert.equal(x.f.authorized, false);
    assert.equal(prepared.options.userVerification, "required");
    const result = await x.execute(granted);
    assert.deepEqual(x.f.events, ["prepare", "claim", "finish", "grant", "authorize", "key", "execute"]);
    assert.deepEqual(Object.keys(result).sort(), ["connection_id", "credential_revision", "status", "storage_version"]);
    assert.equal(result.credential_revision, action === "register" ? 1 : action === "replace" ? 3 : 2);
    assert.equal(result.storage_version, action === "register" ? 1 : 4);
    assert.equal(result.status, action === "revoke" ? "revoked" : "active");
    assert.equal(x.f.bodySent, x.f.body);
    assert.deepEqual(x.f.bound, original);
    assert.equal(x.f.jwt!.payload.oidc_auth_time, original.session.oidcAuthTime);
    assert.equal(x.f.jwt!.payload.authorization_kind, PASSKEY_CREDENTIAL_KIND);
    assert.equal(x.f.jwt!.payload.passkey_version, 2);
    assert.deepEqual(Object.keys(granted).sort(), ["authorization_id", "grant", "grant_id"]);
    for (const request of x.f.requests) {
      assert.equal(JSON.stringify(request).includes("SYNTHETIC-KEY"), false);
      assert.equal(JSON.stringify(request).includes("synthetic-passphrase"), false);
    }
    await assert.rejects(x.execute(granted), reject);
    assert.equal(x.f.events.filter(event => event === "execute").length, 1);
  });
}

test("revoke works on a paused account and has no private triple", async () => {
  const x = fixture("revoke", true), { granted } = await x.proved();
  assert.equal(x.f.body.includes("credentials"), false);
  assert.equal((await x.execute(granted)).status, "revoked");
});

for (const failure of ["wrong-key", "wrong-challenge", "no-uv", "malformed"] as const) {
  test(`${failure} consumes claim but cannot authorize or execute`, async () => {
    const x = fixture(), prepared = await x.begin();
    const response = failure === "malformed" ? {} : x.assertion(prepared.options.challenge, {
      ...(failure === "wrong-key" ? { privateKey: generateKeyPairSync("ec", { namedCurve: "prime256v1" }).privateKey } : {}),
      ...(failure === "wrong-challenge" ? { challenge: token() } : {}),
      ...(failure === "no-uv" ? { flags: 0x01 } : {}),
    });
    await assert.rejects(finishPasskeyCredentialFlow(x.ports, x.f.bound, prepared, response), reject);
    assert.equal(x.f.claimed, true); assert.equal(x.f.authorized, false);
    await assert.rejects(finishPasskeyCredentialFlow(x.ports, x.f.bound, prepared,
      x.assertion(prepared.options.challenge)), reject);
    assert.equal(x.f.events.filter(event => event === "claim").length, 1);
  });
}

for (const bad of ["duplicate", "target", "surrogate", "float", "unknown", "oversize"] as const) {
  test(`body ${bad} rejects before durable preparation`, async () => {
    const x = fixture("replace");
    await assert.rejects(x.begin(target => {
      const { action: _action, ...fields } = target;
      let body = JSON.stringify({ ...fields,
        credentials: { api_key: "SYNTHETIC", secret: "synthetic", passphrase: "synthetic" } });
      if (bad === "duplicate") body = body.replace("{", `{"connection_id":"${CONNECTION}",`);
      if (bad === "target") body = body.replace(CONNECTION, id(50));
      if (bad === "surrogate") body += "\ud800";
      if (bad === "float") body = body.replace('"expected_revision":2', '"expected_revision":2.0');
      if (bad === "unknown") body = body.replace("{", '{"unknown":true,');
      if (bad === "oversize") body += " ".repeat(4097);
      return body;
    }), reject);
    assert.equal(x.f.events.length, 0);
  });
}

test("changed exactbody, purpose or false consent cannot convert proof into credential authority", async () => {
  const x = fixture(), { granted } = await x.proved();
  await assert.rejects(x.execute(granted, x.f.body + " "), reject);
  for (const consentValue of [{ kind: "proof-only", confirmed: true },
    { kind: "credential-write", confirmed: false }, { kind: "credential-write", confirmed: true, extra: true }]) {
    await assert.rejects(executePasskeyCredentialFlow(x.ports, x.f.bound, granted,
      x.f.body, consentValue as never), reject);
  }
  assert.equal(x.f.events.includes("authorize"), false);
  assert.equal((await x.execute(granted)).status, "active");
});

for (const field of ["authorization_id", "proof_id", "grant_id", "user_id", "metadata_sha256",
  "body_sha256", "passkey_version", "prepared_at", "oidc_auth_time", "target"] as const) {
  test(`wrong008 receipt ${field} rejects after consent without key or executor dispatch`, async () => {
    const x = fixture(), { granted } = await x.proved();
    x.f.tamper = (event, wire) => {
      if (event !== "authorize") return wire;
      const wrapper = clone(wire) as { authorization: Record<string, unknown> };
      const receipt = wrapper.authorization;
      receipt[field] = field === "target" ? { ...receipt.target as object, action: "revoke",
        expected_revision: 2, expected_storage: 3 } :
        field.endsWith("_sha256") ? "f".repeat(64) :
        ["passkey_version", "prepared_at", "oidc_auth_time"].includes(field) ? (receipt[field] as number) + 1 : id(99);
      return wrapper;
    };
    await assert.rejects(x.execute(granted), reject);
    assert.equal(x.f.authorized, true);
    assert.equal(x.f.events.includes("key"), false);
    assert.equal(x.f.events.includes("execute"), false);
  });
}

for (const event of ["prepare", "claim", "finish", "grant", "authorize", "key"] as const) {
  test(`session drift after ${event} await prevents next sensitive dispatch`, async () => {
    const x = fixture();
    x.f.hooks.set(event, () => { x.f.bound = { ...x.f.bound,
      session: { ...x.f.bound.session, csrf: token() } }; });
    await assert.rejects((async () => {
      const { granted } = await x.proved();
      return x.execute(granted);
    })(), reject);
    assert.equal(x.f.events.includes("execute"), false);
  });
}

for (const change of ["metadata", "factor-version", "factor-revoked", "factor-material", "owner", "expired"] as const) {
  test(`live ${change} change after consent prevents signing or execution`, async () => {
    const x = fixture(), { granted } = await x.proved();
    x.f.hooks.set("authorize", () => {
      if (change === "metadata") x.f.metadata = { ...x.f.metadata,
        account: { ...x.f.metadata.account, name: "Changed account" } };
      if (change === "factor-version") x.f.context = { ...x.f.context,
        credential: { ...x.f.context.credential!, storage_version: 3 } };
      if (change === "factor-revoked") x.f.context = { ...x.f.context,
        credential: { ...x.f.context.credential!, status: "revoked" } };
      if (change === "factor-material") x.f.context = { ...x.f.context,
        credential: { ...x.f.context.credential!, public_key: token() } };
      if (change === "owner") x.f.context = { ...x.f.context, user_id: id(90),
        credential: { ...x.f.context.credential!, user_id: id(90) } };
      if (change === "expired") x.f.offset = 120;
    });
    await assert.rejects(x.execute(granted), reject);
    assert.equal(x.f.events.includes("execute"), false);
  });
}

test("a changed dedicated signing key is rejected by private executor without retry", async () => {
  const x = fixture(), { granted } = await x.proved();
  x.f.key = new Uint8Array(32).fill(3);
  await assert.rejects(x.execute(granted), reject);
  assert.equal(x.f.events.filter(event => event === "execute").length, 1);
  assert.equal(x.f.executed, false);
  await assert.rejects(x.execute(granted), reject);
  assert.equal(x.f.events.filter(event => event === "execute").length, 1);
});

test("signing snapshots the dedicated key before subsequent awaits mutate its source", async () => {
  const x = fixture(), { granted } = await x.proved();
  x.f.hooks.set("current", () => {
    if (x.f.events.at(-1) === "key") x.f.key.fill(3);
  });
  assert.equal((await x.execute(granted)).status, "active");
  assert.equal(x.f.key[0], 3);
  assert.equal(x.f.executorKey[0], 87);
});

test("session change at the post-signing await prevents private token dispatch", async () => {
  const x = fixture(), { granted } = await x.proved();
  let afterKey = 0;
  x.f.hooks.set("current", () => {
    if (x.f.events.at(-1) === "key" && ++afterKey === 3) {
      x.f.bound = { ...x.f.bound, session: { ...x.f.bound.session, csrf: token() } };
    }
  });
  await assert.rejects(x.execute(granted), reject);
  assert.equal(afterKey, 3);
  assert.equal(x.f.events.includes("execute"), false);
});

for (const change of ["signed-token", "body-bytes"] as const) {
  test(`private executor rejects ${change} tampering after signing without replay`, async () => {
    const x = fixture(), { granted } = await x.proved();
    x.f.executeInput = (signed, body) => ({
      signed: change === "signed-token" ? `${signed}.tampered` : signed,
      body: change === "body-bytes" ? `${body} ` : body,
    });
    await assert.rejects(x.execute(granted), reject);
    assert.equal(x.f.authorized, true); assert.equal(x.f.executed, false);
    await assert.rejects(x.execute(granted), reject);
    assert.equal(x.f.events.filter(event => event === "execute").length, 1);
  });
}

for (const event of ["claim", "authorize", "execute"] as const) {
  test(`unknown ${event} commit never retries or publishes private transport text`, async () => {
    const x = fixture();
    x.f.hooks.set(event, () => { throw new Error("synthetic-secret-transport-sentinel"); });
    if (event === "claim") {
      const prepared = await x.begin();
      await assert.rejects(finishPasskeyCredentialFlow(x.ports, x.f.bound, prepared,
        x.assertion(prepared.options.challenge)), reject);
      await assert.rejects(finishPasskeyCredentialFlow(x.ports, x.f.bound, prepared,
        x.assertion(prepared.options.challenge)), reject);
      assert.equal(x.f.claimed, true);
    } else {
      const { granted } = await x.proved();
      await assert.rejects(x.execute(granted), reject);
      await assert.rejects(x.execute(granted), reject);
      assert.equal(x.f.authorized, true);
      assert.equal(x.f.executed, event === "execute");
    }
    assert.equal(x.f.events.filter(value => value === event).length, 1);
  });
}

for (const wrong of ["private-extra", "revision", "storage", "connection", "status", "post-metadata"] as const) {
  test(`executor ${wrong} result cannot escape the exact safe projection`, async () => {
    const x = fixture("replace"), { granted } = await x.proved();
    if (wrong === "post-metadata") x.f.hooks.set("execute", () => {
      x.f.metadata = { ...x.f.metadata, connection: { ...x.f.metadata.connection!, storage_version: 99 } };
    });
    else x.f.tamper = (event, value) => event !== "execute" ? value : {
      ...value as object, ...(wrong === "private-extra" ? { secret: "synthetic-private-sentinel" } : {}),
      ...(wrong === "revision" ? { credential_revision: 99 } : {}),
      ...(wrong === "storage" ? { storage_version: 99 } : {}),
      ...(wrong === "connection" ? { connection_id: id(99) } : {}),
      ...(wrong === "status" ? { status: "revoked" } : {}),
    };
    await assert.rejects(x.execute(granted), reject);
    assert.equal(x.f.executed, true);
    await assert.rejects(x.execute(granted), reject);
    assert.equal(x.f.events.filter(event => event === "execute").length, 1);
  });
}

test("forged/copied opaque handles and a different caller snapshot cannot cross flows", async () => {
  const x = fixture(), y = fixture(), prepared = await x.begin();
  await assert.rejects(finishPasskeyCredentialFlow(x.ports, x.f.bound, { ...prepared },
    x.assertion(prepared.options.challenge)), reject);
  await assert.rejects(finishPasskeyCredentialFlow(y.ports, y.f.bound, prepared,
    x.assertion(prepared.options.challenge)), reject);
  const expected = { ...x.f.bound, session: { ...x.f.bound.session, oidcAuthTime: x.f.bound.session.oidcAuthTime + 1 } };
  await assert.rejects(finishPasskeyCredentialFlow(x.ports, expected, prepared,
    x.assertion(prepared.options.challenge)), reject);
  assert.equal(x.f.events.includes("claim"), false);
});
