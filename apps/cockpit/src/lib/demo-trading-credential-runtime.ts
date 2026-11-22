/** Private server installation; no broker triple is read from a file or env. */
import { constants, type BigIntStats } from "node:fs";
import { open, lstat } from "node:fs/promises";
import { createHash } from "node:crypto";
import { exactObject, parseEnrollmentJson } from "./passkey-enrollment-state.ts";
import {
  createDemoTradingCredentialPrivateIdentity, type DemoTradingCredentialPrivateIdentity,
  type DemoTradingCredentialPrivateIdentitySpec,
} from "./demo-trading-credential-private-identity.ts";
import {
  createDemoTradingPasskeyCredentialBrowserFlow, type DemoTradingPasskeyCredentialBrowserFlow,
} from "./demo-trading-passkey-credential-browser-flow.ts";
import type { ProofSession } from "./demo-trading-passkey-action-proof-state.ts";
import type { DemoTradingPasskeyCredentialPorts } from "./demo-trading-passkey-credential-flow.ts";

export const DEMO_TRADING_IDENTITY_DIRECTORY = "/run/demo-trading-identity";
const failure = () => new Error("DEMO_TRADING_RUNTIME_UNAVAILABLE");
const stamp = (value: BigIntStats) => [value.dev, value.ino, value.mode, value.uid,
  value.gid, value.nlink, value.size, value.mtimeNs, value.ctimeNs].join(":");

async function privateManifest(directory: string, ownerUid: number): Promise<{ body: string; stamp: string }> {
  const held = [];
  try {
    if (!directory.startsWith("/") || directory.split("/").slice(1).some(v => !v || v === "." || v === "..")) throw failure();
    let root = await open("/", constants.O_RDONLY | constants.O_DIRECTORY | constants.O_NOFOLLOW);
    held.push(root);
    for (const part of directory.split("/").slice(1)) {
      root = await open(`/proc/self/fd/${root.fd}/${part}`, constants.O_RDONLY | constants.O_DIRECTORY | constants.O_NOFOLLOW);
      held.push(root);
    }
    const parent = await root.stat({ bigint: true });
    if (!parent.isDirectory() || (parent.mode & 0o7777n) !== 0o700n || parent.uid !== BigInt(ownerUid)) throw failure();
    const file = await open(`/proc/self/fd/${root.fd}/config`, constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK);
    held.push(file);
    const before = await file.stat({ bigint: true });
    if (!before.isFile() || (before.mode & 0o7777n) !== 0o400n || before.uid !== BigInt(ownerUid) ||
      before.nlink !== 1n || before.size < 1n || before.size > 8192n) throw failure();
    const bytes = Buffer.alloc(8193), count = (await file.read(bytes, 0, bytes.length, 0)).bytesRead;
    if (BigInt(count) !== before.size || stamp(before) !== stamp(await file.stat({ bigint: true })) ||
      stamp(before) !== stamp(await lstat(`${directory}/config`, { bigint: true })) ||
      parent.dev !== (await lstat(directory, { bigint: true })).dev ||
      parent.ino !== (await lstat(directory, { bigint: true })).ino) throw failure();
    return { body: new TextDecoder("utf-8", { fatal: true }).decode(bytes.subarray(0, count)),
      stamp: `${parent.dev}:${parent.ino}:${stamp(before)}` };
  } catch { throw failure(); }
  finally { for (const file of held.reverse()) await file.close(); }
}

export type DemoTradingRuntime = Readonly<{
  flow: DemoTradingPasskeyCredentialBrowserFlow;
  check(): Promise<void>;
  accountId: string;
  identity?: DemoTradingCredentialPrivateIdentity;
}>;

export async function loadDemoTradingCredentialRuntime(input: Readonly<{
  directory: string; ownerUid: number; origin: string; oidcIssuer: string;
  portsFor(bound: ProofSession, identity: DemoTradingCredentialPrivateIdentity): Promise<DemoTradingPasskeyCredentialPorts>;
  now(): number; randomToken(): string; randomUuid(): string;
}>): Promise<DemoTradingRuntime> {
  const original = await privateManifest(input.directory, input.ownerUid);
  const fields = ["schema", "directory", "ownerUid", "tenantId", "userId", "accountId", "origin",
    "oidcIssuer", "executorOrigin", "signingSha256", "caSha256", "certificateSha256",
    "privateKeySha256", "excludedSigningSha256"];
  const manifest = exactObject(parseEnrollmentJson(original.body), fields) as unknown as DemoTradingCredentialPrivateIdentitySpec;
  if (manifest.directory !== input.directory || manifest.ownerUid !== input.ownerUid ||
    manifest.origin !== input.origin || manifest.oidcIssuer !== input.oidcIssuer) throw failure();
  const identity = await createDemoTradingCredentialPrivateIdentity(manifest, input.now);
  const hash = createHash("sha256").update(original.body).digest("hex");
  async function check() {
    const current = await privateManifest(input.directory, input.ownerUid);
    if (current.stamp !== original.stamp || createHash("sha256").update(current.body).digest("hex") !== hash) throw failure();
  }
  const flow = createDemoTradingPasskeyCredentialBrowserFlow({
    now: input.now, randomToken: input.randomToken,
    // Installation attests the user's Demo-mode key. Native UID/rights/IP are
    // independently checked by the executor before encrypted registration.
    acceptCredentials: (action, triple) => action === "revoke" ? triple === undefined : triple !== undefined,
    portsFor(bound) {
      if (bound.origin !== manifest.origin || bound.session.issuer !== manifest.oidcIssuer ||
        bound.session.tenantId !== manifest.tenantId) throw failure();
      let pending: Promise<DemoTradingPasskeyCredentialPorts> | undefined;
      async function ports() {
        await check();
        pending ??= input.portsFor(bound, identity);
        return pending;
      }
      return {
        now: input.now, randomToken: input.randomToken,
        randomUuid: input.randomUuid,
        current: async () => {
          const value = await (await ports()).current(); await check(); return value;
        },
        context: async (...args) => {
          const value = await (await ports()).context(...args); await check(); return value;
        },
        metadata: async (...args) => {
          if (args[1] !== manifest.accountId) throw failure();
          const value = await (await ports()).metadata(...args); await check(); return value;
        },
        request: async (...args) => {
          const value = await (await ports()).request(...args); await check(); return value;
        },
        credentialKey: async () => {
          const value = await (await ports()).credentialKey(); await check(); return value;
        },
        execute: async (...args) => {
          const value = await (await ports()).execute(...args); await check(); return value;
        },
      };
    },
  });
  return Object.freeze({ flow, check, accountId: manifest.accountId, identity });
}
