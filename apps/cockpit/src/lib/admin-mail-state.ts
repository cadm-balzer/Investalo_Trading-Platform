/** One trusted platform administrator; SMTP secrets use a dedicated AEAD key. */
import { createCipheriv, createDecipheriv, createHmac, randomBytes, randomInt, randomUUID, timingSafeEqual } from "node:crypto";
import { constants } from "node:fs";
import { mkdir, open, rename, lstat } from "node:fs/promises";
import { join } from "node:path";
import { exactObject, parseEnrollmentJson } from "./passkey-enrollment-state.ts";

export const mailFailure = () => new Error("ADMIN_MAIL_UNAVAILABLE");
export function mailAddress(value: unknown): string {
  if (typeof value !== "string" || value.length > 254 ||
    !/^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?\.[a-zA-Z]{2,63}$/.test(value)) throw mailFailure();
  return value;
}
export function mailHost(value: unknown): string {
  if (typeof value !== "string" || value.length > 253 || !value.includes(".") ||
    value.split(".").some(v => !/^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(v)) ||
    /^[0-9]+$/.test(value.split(".").at(-1)!)) throw mailFailure();
  return value;
}
export type MailSettings = { host: string; port: 465; username: string; password: string; sender: string };
export type EmailProof = { reference: string; hash: string; epoch: number; expiresAt: number;
  attempts: number; state: "pending" | "sent" | "verified"; verifiedAt: number | null };
type State = { revision: number; settings: MailSettings | null; proof: EmailProof | null; lastSentAt: number };
export type MailSummary = { revision: number; configured: boolean; host: string; port: 465;
  username: string; sender: string; recipient: string; verification: "none" | EmailProof["state"];
  expiresAt: number | null; verifiedAt: number | null };

function settings(value: unknown): MailSettings {
  const v = exactObject(value, ["host", "port", "username", "password", "sender"]);
  if (v.port !== 465 || typeof v.username !== "string" || !v.username || Buffer.byteLength(v.username) > 256 ||
    /[\u0000-\u001f\u007f]/.test(v.username) || typeof v.password !== "string" || !v.password ||
    Buffer.byteLength(v.password) > 1024 || !v.password.isWellFormed() || /[\u0000\r\n]/.test(v.password)) throw mailFailure();
  return { host: mailHost(v.host), port: 465, username: v.username, password: v.password, sender: mailAddress(v.sender) };
}
function state(value: unknown): State {
  const v = exactObject(value, ["revision", "settings", "proof", "lastSentAt"]);
  if (!Number.isSafeInteger(v.revision) || (v.revision as number) < 1 ||
    !Number.isSafeInteger(v.lastSentAt) || (v.lastSentAt as number) < 0) throw mailFailure();
  let proof: EmailProof | null = null;
  if (v.proof !== null) {
    const p = exactObject(v.proof, ["reference", "hash", "epoch", "expiresAt", "attempts", "state", "verifiedAt"]);
    if (typeof p.reference !== "string" || !/^[a-f0-9-]{36}$/.test(p.reference) ||
      typeof p.hash !== "string" || !/^[a-f0-9]{64}$/.test(p.hash) ||
      !Number.isSafeInteger(p.epoch) || (p.epoch as number) < 0 ||
      !Number.isSafeInteger(p.expiresAt) || (p.expiresAt as number) < 1 ||
      !Number.isSafeInteger(p.attempts) || (p.attempts as number) < 0 || (p.attempts as number) > 5 ||
      !["pending", "sent", "verified"].includes(p.state as string) ||
      (p.state === "verified" ? !Number.isSafeInteger(p.verifiedAt) ||
        (p.verifiedAt as number) < 1 || (p.verifiedAt as number) >= (p.expiresAt as number) : p.verifiedAt !== null)) throw mailFailure();
    proof = p as EmailProof;
  }
  return { revision: v.revision as number, settings: v.settings === null ? null : settings(v.settings),
    proof, lastSentAt: v.lastSentAt as number };
}

/** Single running Cockpit writer, private filesystem, atomic acknowledged updates. */
export class AdminMailStore {
  #key: Buffer; #aad: Buffer; #directory: string; #recipient: string; #host: string; #busy = false;
  constructor(input: { key: Uint8Array; binding: string; directory: string; recipient: string; defaultHost: string }) {
    if (input.key.byteLength !== 32 || !input.directory.startsWith("/") || input.directory.includes("\0")) throw mailFailure();
    this.#key = Buffer.from(input.key);
    this.#aad = Buffer.from(`investalo-platform-smtp/1\0${input.binding}`);
    this.#directory = input.directory;
    this.#recipient = mailAddress(input.recipient);
    this.#host = mailHost(input.defaultHost);
  }
  async #root() {
    try { await lstat(this.#directory); }
    catch (error) {
      if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw mailFailure();
      await mkdir(this.#directory, { mode: 0o700, recursive: false }).catch(error => {
        if ((error as NodeJS.ErrnoException).code !== "EEXIST") throw mailFailure();
      });
    }
    const value = await lstat(this.#directory);
    if (!value.isDirectory() || (value.mode & 0o7777) !== 0o700 || value.uid !== process.getuid!()) throw mailFailure();
  }
  async #read(): Promise<State> {
    await this.#root();
    let file;
    try { file = await open(join(this.#directory, "settings.enc"), constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK); }
    catch (error) {
      if ((error as NodeJS.ErrnoException).code === "ENOENT") return { revision: 0, settings: null, proof: null, lastSentAt: 0 };
      throw mailFailure();
    }
    try {
      const before = await file.stat();
      if (!before.isFile() || (before.mode & 0o7777) !== 0o600 || before.uid !== process.getuid!() ||
        before.nlink !== 1 || before.size < 29 || before.size > 16_384) throw mailFailure();
      const bytes = Buffer.alloc(16_385);
      const size = (await file.read(bytes, 0, bytes.length, 0)).bytesRead;
      const after = await file.stat();
      if (size !== before.size || after.size !== before.size || after.mtimeMs !== before.mtimeMs || after.ctimeMs !== before.ctimeMs) throw mailFailure();
      const wire = bytes.subarray(0, size), decipher = createDecipheriv("aes-256-gcm", this.#key, wire.subarray(0, 12));
      decipher.setAAD(this.#aad); decipher.setAuthTag(wire.subarray(12, 28));
      return state(parseEnrollmentJson(Buffer.concat([decipher.update(wire.subarray(28)), decipher.final()]).toString("utf8")));
    } catch { throw mailFailure(); } finally { await file.close(); }
  }
  async #write(value: State) {
    const nonce = randomBytes(12), cipher = createCipheriv("aes-256-gcm", this.#key, nonce);
    cipher.setAAD(this.#aad);
    const ciphertext = Buffer.concat([cipher.update(JSON.stringify(value), "utf8"), cipher.final()]);
    const path = join(this.#directory, `.${randomUUID()}.tmp`);
    const file = await open(path, constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | constants.O_NOFOLLOW, 0o600);
    try { await file.writeFile(Buffer.concat([nonce, cipher.getAuthTag(), ciphertext])); await file.sync(); }
    finally { await file.close(); }
    await rename(path, join(this.#directory, "settings.enc"));
    const directory = await open(this.#directory, constants.O_RDONLY | constants.O_DIRECTORY | constants.O_NOFOLLOW);
    try { await directory.sync(); } finally { await directory.close(); }
    const acknowledged = await this.#read();
    if (JSON.stringify(acknowledged) !== JSON.stringify(value)) throw mailFailure();
  }
  #summary(s: State, now: number): MailSummary {
    return { revision: s.revision, configured: s.settings !== null, host: s.settings?.host ?? this.#host,
      port: 465, username: s.settings?.username ?? "", sender: s.settings?.sender ?? this.#recipient,
      recipient: this.#recipient,
      verification: s.proof && (s.proof.state === "verified" || s.proof.expiresAt > now) ? s.proof.state : "none",
      expiresAt: s.proof?.expiresAt ?? null, verifiedAt: s.proof?.verifiedAt ?? null };
  }
  async summary(now: number, epoch?: number) {
    const s = await this.#read();
    if (epoch !== undefined && s.proof?.epoch !== epoch) s.proof = null;
    return this.#summary(s, now);
  }
  async #change<T>(revision: number, work: (value: State) => Promise<T>) {
    if (this.#busy) throw mailFailure();
    this.#busy = true;
    try {
      const value = await this.#read();
      if (!Number.isSafeInteger(revision) || revision !== value.revision || revision > Number.MAX_SAFE_INTEGER - 2) throw mailFailure();
      return await work(value);
    } finally { this.#busy = false; }
  }
  #hash(reference: string, epoch: number, code: string) {
    return createHmac("sha256", this.#key).update(this.#aad).update(`\0${this.#recipient}\0${reference}\0${epoch}\0${code}`).digest("hex");
  }
  async save(revision: number, input: unknown, now: number, guard: () => Promise<void>) {
    const v = exactObject(input, ["host", "port", "username", "password", "sender"]);
    return this.#change(revision, async s => {
      const saved = settings({ ...v, password: v.password === "" ? s.settings?.password : v.password });
      if (saved.host !== this.#host) throw mailFailure();
      await guard();
      const next = { ...s, revision: s.revision + 1, settings: saved, proof: null };
      await this.#write(next);
      return this.#summary(next, now);
    });
  }
  async send(revision: number, epoch: number, now: number,
    deliver: (settings: MailSettings, recipient: string, code: string) => Promise<void>, guard: () => Promise<void>) {
    return this.#change(revision, async s => {
      if (!s.settings || !Number.isSafeInteger(epoch) || epoch < 0 || now - s.lastSentAt < 60) throw mailFailure();
      const code = randomInt(100_000_000).toString().padStart(8, "0"), reference = randomUUID();
      const pending: State = { ...s, revision: s.revision + 1, lastSentAt: now, proof: {
        reference, hash: this.#hash(reference, epoch, code), epoch, expiresAt: now + 600,
        attempts: 0, state: "pending", verifiedAt: null,
      } };
      await guard(); await this.#write(pending); // Durable uncertainty precedes the first SMTP byte.
      try {
        await deliver(s.settings, this.#recipient, code); await guard();
      } catch { return this.#summary(pending, now); } // Never resend an uncertain delivery.
      const sent: State = { ...pending, revision: pending.revision + 1, proof: { ...pending.proof!, state: "sent" } };
      await this.#write(sent);
      return this.#summary(sent, now);
    });
  }
  async verify(revision: number, epoch: number, code: unknown, now: number, guard: () => Promise<void>) {
    if (typeof code !== "string" || !/^[0-9]{8}$/.test(code)) throw mailFailure();
    return this.#change(revision, async s => {
      const p = s.proof;
      if (!p || p.state === "verified" || p.epoch !== epoch || p.expiresAt <= now || p.attempts >= 5) throw mailFailure();
      const valid = timingSafeEqual(Buffer.from(p.hash, "hex"), Buffer.from(this.#hash(p.reference, epoch, code), "hex"));
      await guard();
      const next: State = { ...s, revision: s.revision + 1, proof: { ...p, attempts: p.attempts + 1,
        state: valid ? "verified" : p.state, verifiedAt: valid ? now : null } };
      await this.#write(next);
      return this.#summary(next, now);
    });
  }
  /** Operator-only evidence, contains no password/code/ticket. Not a browser projection. */
  async confirmation(epoch: number, now: number) {
    const s = await this.#read(), p = s.proof;
    if (!p || p.state !== "verified" || p.epoch !== epoch || p.verifiedAt === null ||
      p.verifiedAt > now || now - p.verifiedAt > 86400) throw mailFailure();
    return { reference: p.reference, email: this.#recipient, epoch, verifiedAt: p.verifiedAt };
  }
  async deliverTicket(epoch: number, now: number, expectedReference: string, token: string,
    deliver: (settings: MailSettings, recipient: string, token: string) => Promise<void>) {
    const proof = await this.confirmation(epoch, now), s = await this.#read();
    if (proof.reference !== expectedReference || !s.settings || s.proof?.reference !== expectedReference) throw mailFailure();
    await deliver(s.settings, this.#recipient, token);
  }
}
