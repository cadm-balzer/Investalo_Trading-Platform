import { mkdtemp, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createHash, randomBytes } from "node:crypto";
import dns from "node:dns";
import https from "node:https";
import type { IncomingMessage, ServerResponse } from "node:http";
import type { TestContext } from "node:test";
import type { DemoCredentialPrivateIdentitySpec } from "../../src/lib/demo-credential-private-identity.ts";
import { SYNTHETIC_DEMO_TLS } from "./demo-private-tls-material.ts";

export const id = (n: number) => `00000000-0000-0000-0000-${n.toString().padStart(12, "0")}`;
export const sha = (value: string | Uint8Array) => createHash("sha256").update(value).digest("hex");
export async function identityFixture(t: TestContext, executorOrigin = "https://executor.fixture.invalid:9443") {
  const directory = await mkdtemp(join(tmpdir(), "investalo-demo-identity-"));
  t.after(() => rm(directory, { recursive: true, force: true }));
  const signing = randomBytes(32);
  const material = {
    "signing-key": signing, "executor-ca": Buffer.from(SYNTHETIC_DEMO_TLS.ca),
    "client-certificate": Buffer.from(SYNTHETIC_DEMO_TLS.clientCertificate),
    "client-private-key": Buffer.from(SYNTHETIC_DEMO_TLS.clientPrivateKey),
  };
  for (const [name, bytes] of Object.entries(material)) {
    await writeFile(join(directory, name), bytes, { flag: "wx", mode: 0o400 });
  }
  const spec: DemoCredentialPrivateIdentitySpec = {
    schema: "investalo-demo-credential-private-identity/1", directory, ownerUid: process.getuid!(),
    tenantId: id(1), userId: id(2), accountId: id(3),
    origin: "https://cockpit.fixture.invalid:8443", oidcIssuer: "https://idp.fixture.invalid", executorOrigin,
    signingSha256: sha(signing), caSha256: sha(material["executor-ca"]),
    certificateSha256: sha(material["client-certificate"]), privateKeySha256: sha(material["client-private-key"]),
    excludedSigningSha256: [sha(randomBytes(32))],
  };
  return { directory, signing, material, spec };
}

/** Actual TCP/mTLS; only this fixture's DNS name is mapped to loopback. */
export async function demoTlsFixture(t: TestContext,
  handler: (request: IncomingMessage, response: ServerResponse) => void) {
  const server = https.createServer({
    ca: SYNTHETIC_DEMO_TLS.ca, cert: SYNTHETIC_DEMO_TLS.serverCertificate,
    key: SYNTHETIC_DEMO_TLS.serverPrivateKey, requestCert: true, rejectUnauthorized: true,
    minVersion: "TLSv1.2",
  }, handler);
  server.on("tlsClientError", () => {});
  await new Promise<void>((resolve, reject) => {
    server.once("error", reject); server.listen(0, "127.0.0.1", resolve);
  });
  t.after(() => new Promise<void>((resolve, reject) => server.close(error => error ? reject(error) : resolve())));
  const original = dns.lookup;
  t.mock.method(dns, "lookup", (...args: unknown[]) => {
    const [host, options, callback] = args;
    if (host !== "executor.fixture.invalid") return Reflect.apply(original, dns, args);
    const done = typeof options === "function" ? options : callback;
    queueMicrotask(() => {
      if ((options as { all?: boolean })?.all) (done as Function)(null, [{ address: "127.0.0.1", family: 4 }]);
      else (done as Function)(null, "127.0.0.1", 4);
    });
  });
  const address = server.address();
  if (!address || typeof address === "string") throw new Error("SYNTHETIC_TLS_FIXTURE_REJECTED");
  return { server, origin: `https://executor.fixture.invalid:${address.port}` };
}
