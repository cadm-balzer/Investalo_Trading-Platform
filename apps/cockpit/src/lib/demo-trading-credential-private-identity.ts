/**
 * Explicit Linux private identity, supplied by trusted local server setup.
 * No environment lookup, provisioning, browser activation or key rotation.
 */
import { constants, type BigIntStats } from "node:fs";
import { open, lstat, type FileHandle } from "node:fs/promises";
import { createHash, createPrivateKey, X509Certificate } from "node:crypto";
import { isIP } from "node:net";
import {
  canonicalUuid, credentialInteger, parseDemoTradingActionTarget,
} from "./demo-trading-credential-action-contracts.ts";
import {
  actionProofBinding, proofSession, type ProofSession,
} from "./demo-trading-passkey-action-proof-state.ts";
import { exactObject, parseEnrollmentJson } from "./passkey-enrollment-state.ts";
import { validateDemoTradingPasskeyCredentialBody } from "./demo-trading-passkey-credential-token.ts";
import { createDemoTradingPasskeyCredentialExecutor } from "./demo-trading-passkey-credential-executor.ts";
import type { DemoTradingCredentialIdentityPorts } from "./demo-trading-passkey-credential-provider.ts";
import { readDemoAccount } from "./demo-account-executor.ts";
import type { DemoAccount, DemoAccountTarget } from "./demo-account-contract.ts";
import type { DemoStartup } from "./demo-startup-contract.ts";
import type { DemoBTCTest, DemoBTCMarketTest } from "./demo-btc-test-contract.ts";
import type { DemoSignals } from "./demo-signals-contract.ts";
import { prepareDemoBTCMarketConsent, prepareDemoBTCMarketCloseConsent, type BTCOrderConsentDependencies } from "./demo-btc-order-consent.ts";
import { marketReadPacket, sendMarketPacket } from "./demo-market-order-executor.ts";
import type { MarketPreparation, MarketOutcome } from "./demo-market-order-contract.ts";

export type DemoTradingCredentialPrivateIdentitySpec = Readonly<{
  schema: "investalo-demo-trading-credential-private-identity/1";
  directory: string; ownerUid: number;
  tenantId: string; userId: string; accountId: string; origin: string; oidcIssuer: string;
  executorOrigin: string;
  signingSha256: string; caSha256: string; certificateSha256: string; privateKeySha256: string;
  /** Trusted setup supplies fingerprints of Read/Normal/API/session/KEK authorities. */
  excludedSigningSha256: readonly string[];
}>;
export type DemoTradingCredentialPrivateIdentity = Readonly<{
  forSession(bound: ProofSession, currentUserId: string): DemoTradingCredentialIdentityPorts;
  readAccount?(bound: ProofSession, currentUserId: string, target: DemoAccountTarget): Promise<DemoAccount | DemoStartup | DemoBTCTest | DemoBTCMarketTest | DemoSignals>;
  marketRead?(phase: "prepare" | "observe" | "close-prepare", bound: ProofSession, currentUserId: string,
    target: DemoAccountTarget & { command_id?: string }): Promise<MarketPreparation | MarketOutcome>;
  marketSubmit?(request: Request, deps: Omit<BTCOrderConsentDependencies, "accountId" | "signingKey">,
    phase?: "submit" | "close-submit"): Promise<MarketOutcome>;
}>;
const rejection = () => new Error("DEMO_TRADING_CREDENTIAL_PRIVATE_IDENTITY_REJECTED");
const sha = (value: Uint8Array) => createHash("sha256").update(value).digest("hex");
const FILES = [
  ["signing-key", "signingSha256", 32],
  ["executor-ca", "caSha256", 32768],
  ["client-certificate", "certificateSha256", 16384],
  ["client-private-key", "privateKeySha256", 16384],
] as const;
type Metadata = BigIntStats;
type Pin = Readonly<{ dev: bigint; ino: bigint }>;
const pin = (value: Metadata): Pin => Object.freeze({ dev: value.dev, ino: value.ino });
const samePin = (expected: Pin, actual: Metadata) => expected.dev === actual.dev && expected.ino === actual.ino;
const DIRECTORY_FLAGS = constants.O_RDONLY | constants.O_DIRECTORY | constants.O_NOFOLLOW;
const FILE_FLAGS = constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK;

function origin(value: unknown): string {
  if (typeof value !== "string" || value.length > 255) throw rejection();
  const uri = new URL(value), host = uri.hostname;
  if (uri.protocol !== "https:" || uri.origin !== value || uri.username || uri.password ||
    isIP(host) || !host.includes(".") || host.length > 253 ||
    /^[0-9]+$/.test(host.split(".").at(-1)!) ||
    host.split(".").some(label => !/^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(label))) throw rejection();
  return value;
}
function digest(value: unknown): string {
  if (typeof value !== "string" || !/^[a-f0-9]{64}$/.test(value)) throw rejection();
  return value;
}
function specSnapshot(value: DemoTradingCredentialPrivateIdentitySpec): DemoTradingCredentialPrivateIdentitySpec {
  const item = exactObject(value, ["schema", "directory", "ownerUid", "tenantId", "userId", "accountId",
    "origin", "oidcIssuer", "executorOrigin", "signingSha256", "caSha256", "certificateSha256",
    "privateKeySha256", "excludedSigningSha256"]);
  if (process.platform !== "linux" || item.schema !== "investalo-demo-trading-credential-private-identity/1" ||
    credentialInteger(item.ownerUid) > 4_294_967_295 ||
    typeof item.directory !== "string" || item.directory.length > 4096 || !item.directory.startsWith("/") ||
    item.directory.includes("\0") || item.directory.split("/").slice(1).some(part => !part || part === "." || part === "..") ||
    !Array.isArray(item.excludedSigningSha256) || item.excludedSigningSha256.length < 1 ||
    item.excludedSigningSha256.length > 16) throw rejection();
  const excluded = Object.freeze(item.excludedSigningSha256.map(digest)), signing = digest(item.signingSha256);
  if (new Set(excluded).size !== excluded.length || excluded.includes(signing)) throw rejection();
  return Object.freeze({
    schema: "investalo-demo-trading-credential-private-identity/1", directory: item.directory,
    ownerUid: credentialInteger(item.ownerUid), tenantId: canonicalUuid(item.tenantId),
    userId: canonicalUuid(item.userId), accountId: canonicalUuid(item.accountId),
    origin: origin(item.origin), oidcIssuer: origin(item.oidcIssuer), executorOrigin: origin(item.executorOrigin),
    signingSha256: signing, caSha256: digest(item.caSha256), certificateSha256: digest(item.certificateSha256),
    privateKeySha256: digest(item.privateKeySha256), excludedSigningSha256: excluded,
  });
}
function directoryMetadata(value: Metadata, spec: DemoTradingCredentialPrivateIdentitySpec) {
  if (!value.isDirectory() || (value.mode & 0o7777n) !== 0o700n || value.uid !== BigInt(spec.ownerUid)) throw rejection();
}
function fileMetadata(value: Metadata, spec: DemoTradingCredentialPrivateIdentitySpec, maximum: number, exact: boolean) {
  if (!value.isFile() || (value.mode & 0o7777n) !== 0o400n || value.uid !== BigInt(spec.ownerUid) ||
    value.nlink !== 1n || value.size < 1n || value.size > BigInt(maximum) || exact && value.size !== BigInt(maximum)) throw rejection();
}
function unchanged(before: Metadata, after: Metadata) {
  if (!samePin(pin(before), after) || before.mode !== after.mode || before.uid !== after.uid ||
    before.gid !== after.gid || before.nlink !== after.nlink || before.size !== after.size ||
    before.mtimeNs !== after.mtimeNs || before.ctimeNs !== after.ctimeNs) throw rejection();
}
async function linked(parent: FileHandle, name: string, held: FileHandle) {
  const current = await lstat(`/proc/self/fd/${parent.fd}/${name}`, { bigint: true });
  unchanged(await held.stat({ bigint: true }), current);
}
function certificate(bytes: Buffer): X509Certificate {
  const wire = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  if (!/^-----BEGIN CERTIFICATE-----\n[A-Za-z0-9+/=\r\n]+-----END CERTIFICATE-----\n?$/.test(wire)) throw rejection();
  return new X509Certificate(bytes);
}
function validateMaterial(values: readonly Buffer[], now: number) {
  const [signing, caBytes, certBytes, privateBytes] = values;
  if (sha(signing) === sha(privateBytes)) throw rejection();
  const ca = certificate(caBytes), cert = certificate(certBytes);
  const privateWire = new TextDecoder("utf-8", { fatal: true }).decode(privateBytes);
  if (!/^-----BEGIN PRIVATE KEY-----\n[A-Za-z0-9+/=\r\n]+-----END PRIVATE KEY-----\n?$/.test(privateWire)) throw rejection();
  const key = createPrivateKey(privateBytes);
  if (!ca.ca || !ca.checkIssued(ca) || !ca.verify(ca.publicKey) || cert.ca ||
    !cert.checkIssued(ca) || !cert.verify(ca.publicKey) || !cert.checkPrivateKey(key) ||
    !cert.keyUsage?.includes("1.3.6.1.5.5.7.3.2")) throw rejection();
  for (const value of [ca, cert]) {
    if (Date.parse(value.validFrom) > now * 1000 || Date.parse(value.validTo) <= now * 1000) throw rejection();
  }
}

/** Initial and every subsequent read revalidate original inode, pins and TLS identity. */
export async function createDemoTradingCredentialPrivateIdentity(
  input: DemoTradingCredentialPrivateIdentitySpec, clock: () => number = () => Math.floor(Date.now() / 1000),
): Promise<DemoTradingCredentialPrivateIdentity> {
  try {
    const spec = specSnapshot(input);
    if (typeof clock !== "function") throw rejection();
    let rootPin: Pin | undefined;
    const filePins = new Map<string, Pin>();
    async function load() {
      const now = credentialInteger(clock(), 1), directories: FileHandle[] = [], files: FileHandle[] = [];
      const values: Buffer[] = [];
      try {
        let directory = await open("/", DIRECTORY_FLAGS);
        directories.push(directory);
        for (const component of spec.directory.split("/").slice(1)) {
          const next = await open(`/proc/self/fd/${directory.fd}/${component}`, DIRECTORY_FLAGS);
          directories.push(next);
          directory = next;
        }
        const metadata = await directory.stat({ bigint: true });
        directoryMetadata(metadata, spec);
        if (rootPin && !samePin(rootPin, metadata)) throw rejection();
        const observedPins = new Map<string, Pin>(), observedMetadata: Metadata[] = [];
        for (const [name, fingerprint, maximum] of FILES) {
          const file = await open(`/proc/self/fd/${directory.fd}/${name}`, FILE_FLAGS);
          files.push(file);
          const before = await file.stat({ bigint: true });
          fileMetadata(before, spec, maximum, name === "signing-key");
          const expected = filePins.get(name);
          if (expected && !samePin(expected, before)) throw rejection();
          // Bounded read including one overflow byte; no readFile allocation by st_size.
          const bytes = Buffer.alloc(maximum + 1);
          let size = 0;
          while (size < bytes.length) {
            const read = await file.read(bytes, size, bytes.length - size, null);
            if (read.bytesRead === 0) break;
            size += read.bytesRead;
          }
          const after = await file.stat({ bigint: true });
          fileMetadata(after, spec, maximum, name === "signing-key");
          unchanged(before, after);
          await linked(directory, name, file);
          if (BigInt(size) !== before.size || sha(bytes.subarray(0, size)) !== spec[fingerprint]) throw rejection();
          values.push(Buffer.from(bytes.subarray(0, size)));
          bytes.fill(0);
          observedPins.set(name, pin(before));
          observedMetadata.push(before);
        }
        for (let at = 0; at < FILES.length; at++) {
          const [name, , maximum] = FILES[at];
          const current = await files[at].stat({ bigint: true });
          fileMetadata(current, spec, maximum, name === "signing-key");
          unchanged(observedMetadata[at], current);
          if (!samePin(observedPins.get(name)!, current)) throw rejection();
          await linked(directory, name, files[at]);
        }
        // Recheck every path component after all reads, including original root.
        const components = spec.directory.split("/").slice(1);
        for (let at = 0; at < components.length; at++) {
          await linked(directories[at], components[at], directories[at + 1]);
        }
        directoryMetadata(await directory.stat({ bigint: true }), spec);
        validateMaterial(values, now);
        rootPin ??= pin(metadata);
        for (const [name, value] of observedPins) filePins.set(name, value);
        return values;
      } catch {
        values.forEach(value => value.fill(0));
        throw rejection();
      } finally {
        for (const file of [...files, ...directories].reverse()) await file.close();
      }
    }
    const initial = await load();
    initial.forEach(value => value.fill(0));
    return Object.freeze({
      async marketRead(phase: "prepare" | "observe" | "close-prepare", session: ProofSession, currentUserId: string,
        target: DemoAccountTarget & { command_id?: string }) {
        const bound = proofSession(session, clock());
        if (bound.session.tenantId !== spec.tenantId || canonicalUuid(currentUserId) !== spec.userId ||
          bound.origin !== spec.origin || bound.session.issuer !== spec.oidcIssuer ||
          target.platform_account_id !== spec.accountId || Object.hasOwn(target, "inspection") ||
          phase !== "observe" && Object.hasOwn(target, "command_id") ||
          phase === "observe" && !target.command_id) throw rejection();
        let values: Buffer[] = [];
        try {
          values = await load(); proofSession(bound, clock());
          const packet = marketReadPacket({ phase, authorized: bound, userId: spec.userId, target,
            signingKey: values[0], now: clock() });
          const result = await sendMarketPacket(spec.executorOrigin,
            { ca: values[1], certificate: values[2], privateKey: values[3] }, phase, packet);
          proofSession(bound, clock()); await load().then(v => v.forEach(b => b.fill(0)));
          return result;
        } finally { values.forEach(v => v.fill(0)); }
      },
      async marketSubmit(request: Request, deps: Omit<BTCOrderConsentDependencies, "accountId" | "signingKey">,
        phase: "submit" | "close-submit" = "submit") {
        let values: Buffer[] = [];
        try {
          values = await load();
          const sign = phase === "close-submit" ? prepareDemoBTCMarketCloseConsent : prepareDemoBTCMarketConsent;
          const packet = await sign(request, { ...deps, accountId: spec.accountId, signingKey: values[0] });
          if (packet.context.tenant_id !== spec.tenantId || packet.context.user_id !== spec.userId) throw rejection();
          await load().then(v => v.forEach(b => b.fill(0)));
          await deps.checkInstallation();
          const result = await sendMarketPacket(spec.executorOrigin,
            { ca: values[1], certificate: values[2], privateKey: values[3] }, phase, packet);
          await deps.checkInstallation();
          await load().then(v => v.forEach(b => b.fill(0)));
          if (result.schema !== "investalo-demo-market-status/1" &&
              result.schema !== "investalo-demo-market-close-status/1") throw rejection();
          return result;
        } finally { values.forEach(v => v.fill(0)); }
      },
      async readAccount(session: ProofSession, currentUserId: string, target: DemoAccountTarget) {
        const bound = proofSession(session, clock());
        if (bound.session.tenantId !== spec.tenantId || canonicalUuid(currentUserId) !== spec.userId ||
          bound.origin !== spec.origin || bound.session.issuer !== spec.oidcIssuer ||
          canonicalUuid(target.platform_account_id) !== spec.accountId) throw rejection();
        let values: Buffer[] = [];
        try {
          values = await load(); proofSession(bound, clock());
          const result = await readDemoAccount({ origin: spec.executorOrigin, oidcIssuer: spec.oidcIssuer,
            authorized: bound, userId: spec.userId, target, signingKey: values[0],
            tls: { ca: values[1], certificate: values[2], privateKey: values[3] }, now: clock() });
          proofSession(bound, clock()); await load().then(material => material.forEach(v => v.fill(0)));
          return result;
        } catch { throw rejection(); }
        finally { values.forEach(value => value.fill(0)); }
      },
      forSession(session: ProofSession, currentUserId: string): DemoTradingCredentialIdentityPorts {
        try {
          const bound = proofSession(session, clock());
          if (bound.session.tenantId !== spec.tenantId || canonicalUuid(currentUserId) !== spec.userId ||
            bound.origin !== spec.origin || bound.session.issuer !== spec.oidcIssuer) throw rejection();
          const live = () => proofSession(bound, clock());
          return Object.freeze({
            async credentialKey() {
              let values: Buffer[] = [];
              try {
                live(); values = await load(); live();
                return Uint8Array.from(values[0]);
              } catch { throw rejection(); }
              finally { values.forEach(value => value.fill(0)); }
            },
            async execute(token: string, body: string) {
              let values: Buffer[] = [];
              try {
                live();
                const wire = parseEnrollmentJson(body);
                if (!wire || typeof wire !== "object" || Array.isArray(wire)) throw rejection();
                const target = parseDemoTradingActionTarget({
                  action: Object.hasOwn(wire, "expected_revision") ? "revoke" : "register",
                  platform_account_id: wire.platform_account_id, connection_id: wire.connection_id,
                  ...(Object.hasOwn(wire, "expected_revision") ? {
                    expected_revision: wire.expected_revision, expected_storage: wire.expected_storage,
                  } : {}),
                });
                if (target.platform_account_id !== spec.accountId) throw rejection();
                validateDemoTradingPasskeyCredentialBody(body, target);
                values = await load(); live();
                const dispatch = createDemoTradingPasskeyCredentialExecutor({
                  origin: spec.executorOrigin, target, clock,
                  context: { tenantId: spec.tenantId, userId: spec.userId, subject: bound.session.subject,
                    authEpoch: bound.session.authEpoch, oidcAuthTime: bound.session.oidcAuthTime,
                    sessionBinding: actionProofBinding(bound), sessionExpiresAt: bound.session.expiresAt },
                  tls: { ca: values[1], certificate: values[2], privateKey: values[3] },
                });
                const result = await dispatch(token, body);
                live();
                return result;
              } catch { throw rejection(); }
              finally { values.forEach(value => value.fill(0)); }
            },
          });
        } catch { throw rejection(); }
      },
    });
  } catch { throw rejection(); }
}
