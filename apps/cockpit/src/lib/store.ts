import { createCipheriv, createDecipheriv, createHash, randomBytes } from "node:crypto";
import { mkdir, readFile, readdir, rename, unlink, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { randomToken, sha256 } from "./security.ts";

type Stored = { expiresAt: number };

/** One runtime writer/instance. State is encrypted and authenticated at rest. */
export class EncryptedStore {
  private key: Buffer;
  private directory: string;
  constructor(directory: string, secret: string) {
    this.directory = directory;
    if (Buffer.byteLength(secret) < 32) throw new Error("STORE_KEY_REJECTED");
    this.key = createHash("sha256").update(`investalo-session-v1:${secret}`).digest();
  }
  private path(id: string): string {
    if (!/^[A-Za-z0-9_-]{43}$/.test(id)) throw new Error("STORE_ID_REJECTED");
    return join(this.directory, `${sha256(id)}.json.enc`);
  }
  private encrypt(data: Stored): string {
    const iv = randomBytes(12);
    const cipher = createCipheriv("aes-256-gcm", this.key, iv);
    const encrypted = Buffer.concat([cipher.update(JSON.stringify(data), "utf8"), cipher.final()]);
    return Buffer.concat([iv, cipher.getAuthTag(), encrypted]).toString("base64");
  }
  private decrypt<T extends Stored>(text: string): T {
    const bytes = Buffer.from(text, "base64");
    if (bytes.length < 29 || bytes.length > 65_536) throw new Error("STORE_DATA_REJECTED");
    const cipher = createDecipheriv("aes-256-gcm", this.key, bytes.subarray(0, 12));
    cipher.setAuthTag(bytes.subarray(12, 28));
    const data = JSON.parse(Buffer.concat([cipher.update(bytes.subarray(28)), cipher.final()]).toString("utf8")) as T;
    if (!Number.isSafeInteger(data.expiresAt) || data.expiresAt <= Math.floor(Date.now() / 1000)) throw new Error("STORE_EXPIRED");
    return data;
  }
  async put<T extends Stored>(id: string, data: T): Promise<void> {
    await mkdir(this.directory, { recursive: true, mode: 0o700 });
    const target = this.path(id);
    // Bounded expiry sweep prevents expired login attempts consuming disk forever.
    const entries = await readdir(this.directory);
    if (entries.length >= 500) {
      for (const file of entries.slice(0, 100)) {
        if (!/^[a-f0-9]{64}\.json\.enc$/.test(file)) continue;
        try { this.decrypt(await readFile(join(this.directory, file), "utf8")); }
        catch { await unlink(join(this.directory, file)).catch(() => {}); }
      }
      if ((await readdir(this.directory)).length >= 1000) throw new Error("STORE_CAPACITY");
    }
    const temp = `${target}.${randomToken()}.tmp`;
    await writeFile(temp, this.encrypt(data), { encoding: "utf8", mode: 0o600, flag: "wx" });
    await rename(temp, target);
  }
  async get<T extends Stored>(id: string): Promise<T | null> {
    try { return this.decrypt<T>(await readFile(this.path(id), "utf8")); }
    catch { return null; }
  }
  /** Atomic claim ensures one successful callback even across concurrent requests. */
  async consume<T extends Stored>(id: string): Promise<T | null> {
    let claimed: string | undefined;
    try {
      claimed = `${this.path(id)}.${randomToken()}.consumed`;
      await rename(this.path(id), claimed);
      return this.decrypt<T>(await readFile(claimed, "utf8"));
    } catch { return null; }
    finally { if (claimed) await unlink(claimed).catch(() => {}); }
  }
  async delete(id: string): Promise<void> {
    try { await unlink(this.path(id)); } catch { /* Invalid/stale browser handles must not prevent session rotation. */ }
  }
}
