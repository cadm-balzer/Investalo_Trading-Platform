import { constants } from "node:fs";
import { open, lstat } from "node:fs/promises";
import { createHash } from "node:crypto";
import { exactObject, parseEnrollmentJson } from "./passkey-enrollment-state.ts";
import { canonicalUuid } from "./credential-action-contracts.ts";
import { AdminMailStore, mailAddress, mailHost, mailFailure } from "./admin-mail-state.ts";

export const ADMIN_DIRECTORY = "/run/platform-admin";
export type MailAuthority = { tenantId: string; userId: string; subject: string; issuer: string;
  origin: string; recipient: string; defaultHost: string; keySha256: string };
const hash = (v: Uint8Array) => createHash("sha256").update(v).digest("hex");

async function material(directory: string, name: "config" | "smtp-key", size: number) {
  const parent = await lstat(directory);
  if (!parent.isDirectory() || parent.uid !== process.getuid!() || (parent.mode & 0o7777) !== 0o700) throw mailFailure();
  const file = await open(`${directory}/${name}`, constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK);
  try {
    const before = await file.stat();
    if (!before.isFile() || before.uid !== process.getuid!() || (before.mode & 0o7777) !== 0o400 ||
      before.nlink !== 1 || before.size < 1 || before.size > size || name === "smtp-key" && before.size !== 32) throw mailFailure();
    const bytes = Buffer.alloc(size + 1), length = (await file.read(bytes, 0, bytes.length, 0)).bytesRead;
    const after = await file.stat();
    if (length !== before.size || after.mtimeMs !== before.mtimeMs || after.ctimeMs !== before.ctimeMs ||
      after.size !== before.size) throw mailFailure();
    return bytes.subarray(0, length);
  } finally { await file.close(); }
}

export async function loadMailAuthority(directory = ADMIN_DIRECTORY) {
  const raw = await material(directory, "config", 4096);
  const v = exactObject(parseEnrollmentJson(raw.toString("utf8")),
    ["schema", "tenantId", "userId", "subject", "issuer", "origin", "recipient", "defaultHost", "keySha256"]);
  if (v.schema !== "investalo-platform-admin/1" || typeof v.subject !== "string" ||
    !v.subject || v.subject.length > 255 || /[\u0000-\u001f\u007f]/.test(v.subject) ||
    v.issuer !== "https://auth.cockpit.investalo.de" || v.origin !== "https://cockpit.investalo.de" ||
    typeof v.keySha256 !== "string" || !/^[a-f0-9]{64}$/.test(v.keySha256)) throw mailFailure();
  const authority: MailAuthority = { tenantId: canonicalUuid(v.tenantId), userId: canonicalUuid(v.userId),
    subject: v.subject, issuer: v.issuer, origin: v.origin, recipient: mailAddress(v.recipient),
    defaultHost: mailHost(v.defaultHost), keySha256: v.keySha256 };
  const key = await material(directory, "smtp-key", 32);
  if (hash(key) !== authority.keySha256) throw mailFailure();
  return { authority, key, digest: hash(raw) };
}
export function mailStore(input: Awaited<ReturnType<typeof loadMailAuthority>>, stateDirectory: string) {
  const a = input.authority;
  return new AdminMailStore({ directory: `${stateDirectory}/admin-mail`, key: input.key,
    binding: JSON.stringify([a.tenantId, a.userId, a.issuer, a.origin, a.recipient]),
    recipient: a.recipient, defaultHost: a.defaultHost });
}
