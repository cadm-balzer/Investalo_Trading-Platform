/** Durable user intent only. No broker approval, OIDC token or order sender. */
import { createHmac, randomUUID, timingSafeEqual } from "node:crypto";
import { constants } from "node:fs";
import { open, mkdir, lstat, rename, unlink } from "node:fs/promises";
import { canonicalUuid } from "./credential-action-contracts.ts";
import { exactObject, parseEnrollmentJson } from "./passkey-enrollment-state.ts";
import { DEMO_SIGNAL_SYMBOLS as SYMBOLS } from "./demo-signals-contract.ts";
import { controlSettings, parseDemoControl, type DemoControl, type DemoControlInput } from "./demo-control-contract.ts";

export type DemoControlBinding = {
  tenant_id: string; account_id: string; user_id: string; subject: string;
  auth_epoch: number; connection_id: string; credential_revision: 1; storage_version: number;
};
type Saved = { schema: "investalo-demo-h1-intent/1"; binding: DemoControlBinding;
  revision: number; action: "start" | "pause"; basket_limit: number; assets: string[]; requested_at: string };
const fail = () => new Error("DEMO_CONTROL_UNCONFIRMED");
const directories = constants.O_RDONLY | constants.O_DIRECTORY | constants.O_NOFOLLOW;
function binding(value: unknown): DemoControlBinding {
  const v = exactObject(value, ["tenant_id", "account_id", "user_id", "subject", "auth_epoch",
    "connection_id", "credential_revision", "storage_version"]);
  for (const key of ["tenant_id", "account_id", "user_id", "connection_id"]) canonicalUuid(v[key]);
  if (typeof v.subject !== "string" || !v.subject || v.subject.length > 255 ||
    !Number.isSafeInteger(v.auth_epoch) || (v.auth_epoch as number) < 0 || v.credential_revision !== 1 ||
    !Number.isSafeInteger(v.storage_version) || (v.storage_version as number) < 1) throw fail();
  return v as DemoControlBinding;
}
const sameBinding = (a: DemoControlBinding, b: DemoControlBinding) =>
  Object.keys(a).every(k => a[k as keyof DemoControlBinding] === b[k as keyof DemoControlBinding]);

/** One Cockpit process writes this separate private directory. */
export class DemoControlStore {
  #directory: string; #key: Buffer; #busy = false; #pid = process.pid;
  constructor(directory: string, secret: string) {
    if (!directory.startsWith("/") || directory.split("/").slice(1).some(p => !p || p === "." || p === "..") ||
      directory.includes("\0") || Buffer.byteLength(secret) < 32) throw fail();
    this.#directory = directory;
    this.#key = createHmac("sha256", secret).update("investalo-demo-h1-intent-signing/1").digest();
  }
  #shared() { return process.env.COCKPIT_DEMO_H1_WORKER === "1"; }
  async #root() {
    if (this.#pid !== process.pid) throw fail();
    const parent = this.#directory.slice(0, this.#directory.lastIndexOf("/"));
    const s = await lstat(parent);
    if (!s.isDirectory() || s.uid !== process.getuid!() || (s.mode & 0o022) !== 0) throw fail();
    await mkdir(this.#directory, { mode: this.#shared() ? 0o2750 : 0o700 }).catch(e => {
      if (e.code !== "EEXIST") throw fail();
    });
    const held = await open(this.#directory, directories), current = await held.stat();
    if (!current.isDirectory() || current.uid !== process.getuid!() ||
      (current.mode & 0o7777) !== (this.#shared() ? 0o2750 : 0o700) ||
      this.#shared() && current.gid !== 10003) {
      await held.close(); throw fail();
    }
    return held;
  }
  #name(b: DemoControlBinding) { return `${b.tenant_id}.${b.account_id}.json`; }
  #mac(payload: string) { return createHmac("sha256", this.#key).update(payload).digest("hex"); }
  async #read(root: number, b: DemoControlBinding): Promise<Saved | null> {
    let file;
    try { file = await open(`/proc/self/fd/${root}/${this.#name(b)}`,
      constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK); }
    catch (e) { if ((e as NodeJS.ErrnoException).code === "ENOENT") return null; throw fail(); }
    try {
      const before = await file.stat({ bigint: true });
      if (!before.isFile() || before.uid !== BigInt(process.getuid!()) ||
        (before.mode & 0o7777n) !== (this.#shared() ? 0o640n : 0o600n) ||
        this.#shared() && before.gid !== 10003n ||
        before.nlink !== 1n || before.size < 1n || before.size > 8192n) throw fail();
      const bytes = Buffer.alloc(8193), count = (await file.read(bytes, 0, bytes.length, 0)).bytesRead;
      const after = await file.stat({ bigint: true });
      if (BigInt(count) !== before.size || before.size !== after.size ||
        before.mtimeNs !== after.mtimeNs || before.ctimeNs !== after.ctimeNs) throw fail();
      const wire = exactObject(parseEnrollmentJson(new TextDecoder("utf-8", { fatal: true })
        .decode(bytes.subarray(0, count))), ["payload", "mac"]);
      if (typeof wire.payload !== "string" || typeof wire.mac !== "string" || !/^[a-f0-9]{64}$/.test(wire.mac) ||
        !timingSafeEqual(Buffer.from(wire.mac, "hex"), Buffer.from(this.#mac(wire.payload), "hex"))) throw fail();
      const v = exactObject(parseEnrollmentJson(wire.payload),
        ["schema", "binding", "revision", "action", "basket_limit", "assets", "requested_at"]);
      const owner = binding(v.binding);
      if (v.schema !== "investalo-demo-h1-intent/1" || owner.tenant_id !== b.tenant_id || owner.account_id !== b.account_id ||
        !Number.isSafeInteger(v.revision) || (v.revision as number) < 1 || !["start", "pause"].includes(v.action as string) ||
        typeof v.requested_at !== "string" || !Number.isFinite(Date.parse(v.requested_at)) ||
        new Date(v.requested_at).toISOString() !== v.requested_at) throw fail();
      const settings = controlSettings(v.basket_limit, v.assets);
      if (JSON.stringify(settings.assets) !== JSON.stringify(v.assets)) throw fail();
      return { ...v, binding: owner } as Saved;
    } finally { await file.close(); }
  }
  #summary(s: Saved | null, b: DemoControlBinding): DemoControl {
    return parseDemoControl({ schema: "investalo-demo-h1-control/1", tenant_id: b.tenant_id, account_id: b.account_id,
      revision: s?.revision ?? 0, basket_limit: s?.basket_limit ?? 3, assets: s?.assets ?? [...SYMBOLS],
      status: !s ? "not_started" : !sameBinding(s.binding, b) ? "authorization_changed" :
        s.action === "start" ? "start_requested" : "paused", requested_at: s?.requested_at ?? null,
      worker_state: "not_installed", execution_enabled: false }, b.tenant_id, b.account_id);
  }
  async #worker(summary: DemoControl, b: DemoControlBinding): Promise<DemoControl> {
    if (!this.#shared()) return summary;
    const path = this.#directory.slice(0, this.#directory.lastIndexOf("/"))+"/demo-h1-worker-status/status.json";
    let file;
    try {
      file = await open(path, constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK);
      const stat = await file.stat({ bigint: true });
      if (!stat.isFile() || stat.uid !== 10003n || stat.gid !== 10002n ||
        (stat.mode & 0o7777n) !== 0o640n || stat.nlink !== 1n || stat.size > 8192n) throw fail();
      const raw = Buffer.alloc(8193), count = (await file.read(raw, 0, raw.length, 0)).bytesRead;
      const after = await file.stat({ bigint: true });
      if (BigInt(count) !== stat.size || after.mtimeNs !== stat.mtimeNs || after.ctimeNs !== stat.ctimeNs) throw fail();
      const wire = exactObject(parseEnrollmentJson(new TextDecoder("utf-8", { fatal: true }).decode(raw.subarray(0, count))),
        ["payload", "mac"]);
      if (typeof wire.payload !== "string" || typeof wire.mac !== "string" || !/^[a-f0-9]{64}$/.test(wire.mac)) throw fail();
      const purpose = "investalo-demo-h1-worker-status/1";
      const mac = createHmac("sha256", this.#key).update(purpose+"\0"+wire.payload).digest("hex");
      if (!timingSafeEqual(Buffer.from(mac, "hex"), Buffer.from(wire.mac, "hex"))) throw fail();
      const w = exactObject(parseEnrollmentJson(wire.payload), ["schema", "tenant_id", "account_id", "connection_id",
        "storage_version", "auth_epoch", "control_revision", "state", "detail", "execution_enabled", "observed_at", "journal_revision"]);
      if (w.schema !== purpose || w.tenant_id !== b.tenant_id || w.account_id !== b.account_id ||
        w.connection_id !== b.connection_id || w.storage_version !== b.storage_version || w.auth_epoch !== b.auth_epoch ||
        w.control_revision !== summary.revision || typeof w.observed_at !== "string" ||
        !["waiting", "running", "paused", "blocked"].includes(w.state as string) ||
        typeof w.execution_enabled !== "boolean" || typeof w.detail !== "string" || w.detail.length > 128) throw fail();
      const age = Date.now()-Date.parse(w.observed_at);
      if (!Number.isFinite(age) || age < 0 || age > 30000) throw fail();
      return parseDemoControl({ ...summary, worker_state: w.state,
        execution_enabled: w.execution_enabled && summary.status === "start_requested",
        worker_detail: w.detail, worker_seen_at: w.observed_at }, b.tenant_id, b.account_id);
    } catch {
      return parseDemoControl({ ...summary, worker_state: "offline", execution_enabled: false,
        worker_detail: "worker_status_unconfirmed", worker_seen_at: null }, b.tenant_id, b.account_id);
    } finally { await file?.close(); }
  }
  async summary(input: DemoControlBinding) {
    const b = binding(input), root = await this.#root();
    try { return await this.#worker(this.#summary(await this.#read(root.fd, b), b), b); } finally { await root.close(); }
  }
  async change(input: DemoControlBinding, request: DemoControlInput, now: number, guard: () => Promise<void>) {
    if (this.#busy) throw fail();
    this.#busy = true;
    let root, temporary: string | undefined;
    try {
      const b = binding(input);
      const settings = controlSettings(request.basket_limit, request.assets);
      if (!["start", "pause"].includes(request.action) || !Number.isSafeInteger(now) || now < 1 ||
        !Number.isSafeInteger(request.expected_revision) || request.expected_revision < 0 ||
        request.expected_revision >= Number.MAX_SAFE_INTEGER) throw fail();
      root = await this.#root();
      const previous = await this.#read(root.fd, b);
      if ((previous?.revision ?? 0) !== request.expected_revision) throw fail();
      const next: Saved = { schema: "investalo-demo-h1-intent/1", binding: b,
        revision: request.expected_revision + 1, action: request.action, ...settings,
        requested_at: new Date(now * 1000).toISOString() };
      const payload = JSON.stringify(next), wire = JSON.stringify({ payload, mac: this.#mac(payload) });
      temporary = `/proc/self/fd/${root.fd}/.${randomUUID()}.tmp`;
      const file = await open(temporary, constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | constants.O_NOFOLLOW,
        this.#shared() ? 0o640 : 0o600);
      try { await file.writeFile(wire); await file.sync(); } finally { await file.close(); }
      await guard(); // Recheck current actor/key immediately before publishing user intent.
      await rename(temporary, `/proc/self/fd/${root.fd}/${this.#name(b)}`); temporary = undefined;
      await root.sync();
      const acknowledged = await this.#read(root.fd, b);
      if (JSON.stringify(acknowledged) !== JSON.stringify(next)) throw fail();
      return this.#summary(acknowledged, b);
    } finally {
      if (temporary) await unlink(temporary).catch(() => {});
      await root?.close(); this.#busy = false;
    }
  }
}
