"use client";

import { useEffect, useRef, useState } from "react";
import {
  allowedDemoTradingCredentialActions, type DemoTradingCredentialAction, type DemoTradingCredentialActionMetadata,
} from "@/lib/demo-trading-credential-action-contracts";
import { parseBrowserCredentialTriple, type CredentialTriple } from "@/lib/credential-browser-body";
import {
  DemoTradingCredentialBrowserController, type DemoTradingCredentialBrowserSnapshot,
} from "@/lib/demo-trading-credential-browser-controller";
import { serializeBrowserProofAssertion } from "@/lib/passkey-browser-proof";
const demoTradingCredentialActionLabels = { register: "Demo-Handelszugang einrichten", revoke: "Demo-Handelszugang widerrufen" } as const;

const empty: DemoTradingCredentialBrowserSnapshot = {
  phase: "input", busy: false, message: "", preview: null, result: null,
};
export function DemoTradingPasskeyCredentialForm({ csrf, accounts, reloadHref = "/security/credentials/demo-trading" }: {
  csrf: string; accounts: DemoTradingCredentialActionMetadata[]; reloadHref?: string;
}) {
  const [accountId, setAccountId] = useState(""), [action, setAction] = useState<DemoTradingCredentialAction | "">("");
  const [state, setState] = useState(empty), [acknowledged, setAcknowledged] = useState(false);
  const [boundIdentity, setBoundIdentity] = useState("");
  const apiKey = useRef<HTMLInputElement>(null), secret = useRef<HTMLInputElement>(null);
  const passphrase = useRef<HTMLInputElement>(null), controller = useRef<DemoTradingCredentialBrowserController | null>(null);
  const identity = JSON.stringify([csrf, accounts]);
  const clearInputs = () => {
    for (const input of [apiKey.current, secret.current, passphrase.current]) if (input) input.value = "";
  };
  useEffect(() => {
    clearInputs(); setAccountId(""); setAction(""); setAcknowledged(false); setState(empty);
    const current = new DemoTradingCredentialBrowserController({
      rpId: window.location.hostname, now: () => Math.floor(Date.now() / 1000),
      async post(phase, body, signal) {
        if (!window.isSecureContext) throw new Error();
        const response = await fetch(`/api/credentials/bitget-demo-trading/passkey/${phase}`, {
          method: "POST", credentials: "same-origin", cache: "no-store", redirect: "error",
          headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
          body: JSON.stringify(body), signal: AbortSignal.any([signal, AbortSignal.timeout(30_000)]),
        });
        if (!response.ok) throw new Error();
        // The server projects a bounded response. Bound unexpected responses
        // too, without logging or displaying their private content.
        if (!response.body) throw new Error();
        const reader = response.body.getReader(), parts: Uint8Array[] = [];
        let size = 0;
        try {
          while (true) {
            const next = await reader.read();
            if (next.done) break;
            size += next.value.byteLength;
            if (size > 16_384) { await reader.cancel(); throw new Error(); }
            parts.push(next.value);
          }
        } finally { reader.releaseLock(); }
        const bytes = new Uint8Array(size);
        let offset = 0;
        for (const part of parts) { bytes.set(part, offset); offset += part.byteLength; }
        return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
      },
      async authenticate(options, signal) {
        if (!window.isSecureContext || !navigator.credentials) throw new Error();
        return serializeBrowserProofAssertion(await navigator.credentials.get({ publicKey: options, signal }));
      },
    });
    const unsubscribe = current.subscribe(setState);
    controller.current = current; setBoundIdentity(identity);
    const timer = window.setInterval(() => current.expire(), 1000);
    const leaving = () => { clearInputs(); current.dispose(); };
    const restored = (event: PageTransitionEvent) => { if (event.persisted) window.location.reload(); };
    window.addEventListener("pagehide", leaving);
    window.addEventListener("pageshow", restored);
    return () => {
      clearInputs(); unsubscribe(); current.dispose(); window.clearInterval(timer);
      window.removeEventListener("pagehide", leaving);
      window.removeEventListener("pageshow", restored);
      if (controller.current === current) controller.current = null;
    };
    // Only safe prop snapshots are included; no private data enters effect state.
  }, [csrf, identity]);
  useEffect(() => { setAcknowledged(false); clearInputs(); }, [state.phase]);
  const chosen = accounts.find(account => account.account.id === accountId);
  const actions = chosen ? allowedDemoTradingCredentialActions(chosen) : [];
  const bound = boundIdentity === identity;
  const ready = bound && !!chosen && action !== "" && actions.includes(action);
  function currentController() {
    if (!bound) { clearInputs(); controller.current?.abandon(); return null; }
    return controller.current;
  }
  async function prepare() {
    const current = currentController();
    if (!current || !ready || state.busy) return;
    let triple: CredentialTriple | undefined;
    try {
      if (action !== "revoke") {
        if ([apiKey.current, secret.current, passphrase.current].some(input => !input?.reportValidity())) return;
        triple = parseBrowserCredentialTriple({ api_key: apiKey.current!.value,
          secret: secret.current!.value, passphrase: passphrase.current!.value });
      }
      const pending = current.prepare(accountId, action, triple);
      triple = undefined; clearInputs();
      await pending;
    } catch {
      clearInputs(); current.abandon();
      setState({ ...empty, phase: "failed", message: "Eingaben nicht bestätigt. Lade den aktuellen Status neu." });
    } finally { triple = undefined; clearInputs(); }
  }
  return <div className="backtest-form" aria-busy={state.busy}>
    <p className="form-hint">Verwende einen ausdrücklich im Bitget-Demo-Modus erstellten Key mit Futures- und Spot-Handelsrechten.</p>
    {state.phase === "input" ? <>
      <div className="form-field dataset-field">
        <label htmlFor="demo-trading-passkey-credential-account">Zugeordnetes Bitget-Demo-Konto</label>
        <select id="demo-trading-passkey-credential-account" value={accountId} disabled={!bound || state.busy || !accounts.length}
          onChange={event => { clearInputs(); setAccountId(event.target.value); setAction(""); setAcknowledged(false); }}>
          <option value="">Konto auswählen</option>
          {accounts.map(account => <option key={account.account.id} value={account.account.id}>{account.account.name}</option>)}
        </select>
      </div>
      <div className="form-field dataset-field">
        <label htmlFor="demo-trading-passkey-credential-action">Gewünschte Änderung</label>
        <select id="demo-trading-passkey-credential-action" value={action} disabled={!bound || state.busy || !actions.length}
          onChange={event => { clearInputs(); setAction(event.target.value as DemoTradingCredentialAction | ""); setAcknowledged(false); }}>
          <option value="">Aktion auswählen</option>
          {actions.map(value => <option key={value} value={value}>{demoTradingCredentialActionLabels[value]}</option>)}
        </select>
      </div>
      {chosen && <p className="form-hint">Futures- und Spot-Handelsrechte
        {chosen.connection && <> · {chosen.connection.status === "active" ? "Zugang aktiv" : "Zugang widerrufen"} · Stand {chosen.connection.storage_version}</>}
      </p>}
      {ready && action !== "revoke" && <>
        <div className="form-field">
          <label htmlFor="demo-trading-passkey-credential-key">API-Key</label>
          <input id="demo-trading-passkey-credential-key" ref={apiKey} type="password" autoComplete="off" required
            disabled={state.busy} maxLength={256} spellCheck={false} />
        </div>
        <div className="form-field">
          <label htmlFor="demo-trading-passkey-credential-secret">Secret</label>
          <input id="demo-trading-passkey-credential-secret" ref={secret} type="password" autoComplete="off" required
            disabled={state.busy} maxLength={1024} spellCheck={false} />
        </div>
        <div className="form-field">
          <label htmlFor="demo-trading-passkey-credential-passphrase">Passphrase</label>
          <input id="demo-trading-passkey-credential-passphrase" ref={passphrase} type="password" autoComplete="off" required
            disabled={state.busy} maxLength={256} spellCheck={false} />
        </div>
      </>}
      {!accounts.length && <p role="status">Noch kein geeignetes Demo-Konto zugeordnet.</p>}
      <button type="button" className="button primary" disabled={!ready || state.busy}
        onClick={() => void prepare()}>Änderung vorbereiten</button>
      {state.busy && <button type="button" className="button secondary"
        onClick={() => { clearInputs(); currentController()?.abandon(); }}>Prüfung verlassen</button>}
    </> : state.preview && <div className="dataset-selection">
      <strong>{state.preview.accountName} · Bitget Demo · Futures/Spot-Handelsrechte</strong>
      <p>{demoTradingCredentialActionLabels[state.preview.target.action]}</p>
      <dl className="security-list">
        <div><dt>Verbindung</dt><dd style={{ overflowWrap: "anywhere" }}>{state.preview.target.connection_id}</dd></div>
        {state.preview.target.action !== "register" && <>
          <div><dt>Schlüsselrevision</dt><dd>{state.preview.target.expected_revision}</dd></div>
          <div><dt>Gespeicherter Stand</dt><dd>{state.preview.target.expected_storage}</dd></div>
        </>}
        <div><dt>Gültig bis</dt><dd>{new Date(state.preview.expiresAt * 1000).toLocaleTimeString("de-DE")}</dd></div>
      </dl>
      {state.phase === "prepared" ? <button type="button" className="button primary" disabled={!bound || state.busy}
        onClick={() => void currentController()?.assertPasskey()}>Mit Passkey bestätigen</button> : <>
        <p>Dein Gerät hat den Passkey bestätigt. Prüfe Konto und Aktion vor der Ausführung.</p>
        <label className="acknowledgement">
          <input type="checkbox" checked={acknowledged} disabled={!bound || state.busy}
            onChange={event => setAcknowledged(event.target.checked)} />
          Ich bestätige die angezeigte Aktion am Demo-Handelszugang ausdrücklich.
        </label>
        <button type="button" className="button primary" disabled={!bound || state.busy || !acknowledged}
          onClick={() => void currentController()?.execute(acknowledged)}>Änderung ausführen</button>
      </>}
      <button type="button" className="button secondary"
        onClick={() => { clearInputs(); currentController()?.abandon(); setAcknowledged(false); }}>Prüfung verlassen</button>
    </div>}
    {state.message && <p className="form-result" role="status">{state.message}</p>}
    {state.result && <p className="form-result" role="status">
      {state.result.status === "active" ? "Demo-Handelszugang aktiv" : "Demo-Handelszugang widerrufen"}
      {" · "}Revision {state.result.credential_revision} · Stand {state.result.storage_version}
    </p>}
    <a href={reloadHref} className="button secondary">Kontostand neu laden</a>
  </div>;
}
