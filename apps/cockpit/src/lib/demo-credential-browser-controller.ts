/** Ephemeral page controller; private bodies never enter public snapshots. */
import { demoCredentialAction, type DemoCredentialAction } from "./demo-credential-action-contracts.ts";
import { buildBrowserCredentialBody, parseBrowserCredentialTriple, type CredentialTriple } from "./credential-browser-body.ts";
import {
  parseBrowserDemoCredentialStart, parseBrowserDemoCredentialGrant, parseBrowserDemoCredentialResult,
  type BrowserDemoCredentialStart, type BrowserDemoCredentialGrant, type BrowserDemoCredentialResult,
} from "./demo-passkey-credential-browser.ts";
import type { DemoProofPreview } from "./demo-passkey-credential-browser.ts";

export type DemoCredentialBrowserPhase = "input" | "prepared" | "granted" | "complete" | "failed";
export type DemoCredentialBrowserSnapshot = Readonly<{
  phase: DemoCredentialBrowserPhase; busy: boolean; message: string;
  preview: DemoProofPreview | null; result: BrowserDemoCredentialResult | null;
}>;
export type DemoCredentialBrowserPorts = Readonly<{
  rpId: string; now(): number;
  post(phase: "start" | "finish" | "execute", body: Record<string, unknown>, signal: AbortSignal): Promise<unknown>;
  authenticate(options: PublicKeyCredentialRequestOptions, signal: AbortSignal): Promise<unknown>;
}>;
const uncertain = "Ergebnis nicht bestätigt. Lade den Kontostand neu, bevor du eine neue Aktion beginnst.";
const rejected = "Aktion nicht bestätigt. Lade den aktuellen Status neu.";
export class DemoCredentialBrowserController {
  #ports: DemoCredentialBrowserPorts;
  #body: string | null = null;
  #start: BrowserDemoCredentialStart | null = null;
  #grant: BrowserDemoCredentialGrant | null = null;
  #abort: AbortController | null = null;
  #generation = 0;
  #attempted = false;
  #disposed = false;
  #listener: ((value: DemoCredentialBrowserSnapshot) => void) | null = null;
  #state: DemoCredentialBrowserSnapshot = Object.freeze({ phase: "input", busy: false, message: "", preview: null, result: null });
  constructor(ports: DemoCredentialBrowserPorts) { this.#ports = ports; }
  snapshot(): DemoCredentialBrowserSnapshot { return this.#state; }
  subscribe(listener: (value: DemoCredentialBrowserSnapshot) => void): () => void {
    this.#listener = listener;
    return () => { if (this.#listener === listener) this.#listener = null; };
  }
  #publish(value: DemoCredentialBrowserSnapshot) {
    this.#state = Object.freeze(value);
    this.#listener?.(this.#state);
  }
  #clear() {
    this.#generation++;
    this.#abort?.abort(); this.#abort = null;
    this.#body = null; this.#start = null; this.#grant = null;
  }
  #live(generation: number): boolean { return !this.#disposed && generation === this.#generation; }
  #failure(generation: number) {
    if (!this.#live(generation)) return;
    this.#clear();
    this.#publish({ phase: "failed", busy: false, message: this.#attempted ? uncertain : rejected, preview: null, result: null });
  }
  #begin(): { generation: number; signal: AbortSignal } {
    this.#abort = new AbortController();
    this.#publish({ ...this.#state, busy: true, message: "" });
    return { generation: this.#generation, signal: this.#abort.signal };
  }
  async prepare(accountId: string, action: DemoCredentialAction, triple?: CredentialTriple): Promise<void> {
    if (this.#disposed || this.#state.busy || this.#state.phase !== "input") return;
    const { generation, signal } = this.#begin();
    let frozen: CredentialTriple | undefined;
    try {
      demoCredentialAction(action);
      if (action === "revoke") {
        if (triple !== undefined) throw new Error();
      } else frozen = parseBrowserCredentialTriple(triple);
      const result = await this.#ports.post("start", { platform_account_id: accountId, action,
        ...(frozen === undefined ? {} : { credentials: frozen }) }, signal);
      if (!this.#live(generation)) return;
      const start = parseBrowserDemoCredentialStart(result, accountId, action, this.#ports.rpId, this.#ports.now());
      this.#body = buildBrowserCredentialBody(start.preview.target, frozen);
      frozen = undefined;
      this.#start = start;
      this.#publish({ phase: "prepared", busy: false, message: "", preview: start.preview, result: null });
    } catch { this.#failure(generation); }
    finally { frozen = undefined; }
  }
  async assertPasskey(): Promise<void> {
    if (this.#disposed || this.#state.busy || this.#state.phase !== "prepared" || !this.#start || !this.#body) return;
    const start = this.#start, { generation, signal } = this.#begin();
    try {
      if (start.preview.expiresAt <= this.#ports.now()) throw new Error();
      const credential = await this.#ports.authenticate(start.options, signal);
      if (!this.#live(generation) || start.preview.expiresAt <= this.#ports.now()) throw new Error();
      const result = await this.#ports.post("finish", { flow_token: start.flow_token, credential }, signal);
      if (!this.#live(generation)) return;
      const grant = parseBrowserDemoCredentialGrant(result, start, this.#ports.now());
      this.#grant = grant;
      this.#publish({ phase: "granted", busy: false, message: "",
        preview: Object.freeze({ ...start.preview, expiresAt: grant.grant.expiresAt }), result: null });
    } catch { this.#failure(generation); }
  }
  async execute(consent: boolean): Promise<void> {
    if (this.#disposed || this.#state.busy || this.#state.phase !== "granted" ||
      !this.#grant || !this.#body || consent !== true || this.#attempted) return;
    const grant = this.#grant;
    const { generation, signal } = this.#begin();
    this.#attempted = true;
    let body: string | null = this.#body;
    this.#body = null;
    try {
      if (grant.grant.expiresAt <= this.#ports.now()) throw new Error();
      const result = await this.#ports.post("execute", { flow_token: grant.flow_token, body,
        consent: { kind: "demo-credential-write", confirmed: true } }, signal);
      if (!this.#live(generation)) return;
      const parsed = parseBrowserDemoCredentialResult(result, grant.grant.target);
      this.#clear();
      this.#publish({ phase: "complete", busy: false, message: "Die ausgewählte Kontoänderung wurde bestätigt.",
        preview: null, result: parsed });
    } catch { this.#failure(generation); }
    finally { body = null; }
  }
  abandon() {
    if (this.#disposed) return;
    this.#clear();
    this.#publish({ phase: this.#attempted ? "failed" : "input", busy: false,
      message: this.#attempted ? uncertain : "", preview: null, result: null });
  }
  expire() {
    if (this.#state.preview && this.#state.preview.expiresAt <= this.#ports.now()) {
      this.#failure(this.#generation);
    }
  }
  dispose() { this.#disposed = true; this.#listener = null; this.#clear(); }
}
