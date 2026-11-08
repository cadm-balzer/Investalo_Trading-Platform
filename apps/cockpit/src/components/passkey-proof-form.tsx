"use client";

import { useRef, useState } from "react";
import {
  allowedCredentialActions, type CredentialAction, type CredentialActionMetadata,
} from "@/lib/credential-action-contracts";
import {
  parseBrowserProofStart, parseBrowserProofGrant, parseBrowserProofConfirmation, serializeBrowserProofAssertion,
  type BrowserProofStart, type BrowserProofGrant,
} from "@/lib/passkey-browser-proof";

const labels: Record<CredentialAction, string> = {
  register: "Zugang einrichten", replace: "Zugang wechseln", revoke: "Zugang widerrufen",
};
export function PasskeyProofForm({ csrf, accounts }: { csrf: string; accounts: CredentialActionMetadata[] }) {
  const [accountId, setAccountId] = useState(""), [action, setAction] = useState<CredentialAction | "">("");
  const [start, setStart] = useState<BrowserProofStart | null>(null), [grant, setGrant] = useState<BrowserProofGrant | null>(null);
  const [busy, setBusy] = useState(false), [message, setMessage] = useState("");
  const active = useRef(false);
  const chosen = accounts.find(account => account.account.id === accountId);
  const actions = chosen ? allowedCredentialActions(chosen) : [];
  const ready = !!chosen && action !== "" && actions.includes(action);
  async function post(path: string, body: Record<string, unknown>): Promise<unknown> {
    const response = await fetch(`/api/passkeys/actions/${path}`, { method: "POST",
      credentials: "same-origin", cache: "no-store",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf }, body: JSON.stringify(body) });
    if (!response.ok) throw new Error();
    return response.json();
  }
  async function run(step: "start" | "assert" | "confirm") {
    if (active.current) return;
    active.current = true; setBusy(true); setMessage("");
    try {
      if (!window.isSecureContext || !navigator.credentials) throw new Error();
      if (step === "start") {
        if (!ready) throw new Error();
        const prepared = parseBrowserProofStart(await post("start", { platform_account_id: accountId, action }),
          accountId, action, window.location.hostname);
        setStart(prepared); setGrant(null);
      } else if (step === "assert") {
        if (!start || start.preview.expiresAt <= Math.floor(Date.now() / 1000)) throw new Error();
        const credential = serializeBrowserProofAssertion(await navigator.credentials.get({ publicKey: start.options }));
        const verified = parseBrowserProofGrant(await post("finish", {
          attempt_id: start.attempt_id, credential, confirmation_token: start.confirmation_token,
        }), start);
        setGrant(verified);
      } else {
        if (!grant || grant.expiresAt <= Math.floor(Date.now() / 1000)) throw new Error();
        parseBrowserProofConfirmation(await post("confirm", {
          grant_id: grant.grant_id, confirmation_token: grant.confirmationToken,
        }), grant);
        setStart(null); setGrant(null);
        setMessage("Passkey-Bestätigung erfolgreich geprüft. Die Kontoaktion wurde nicht ausgeführt.");
      }
    } catch {
      // A cancelled authenticator, failed claim or unknown commit is never retried.
      setStart(null); setGrant(null);
      setMessage("Prüfung nicht bestätigt. Lade den aktuellen Status neu, bevor du eine neue Prüfung beginnst.");
    } finally { active.current = false; setBusy(false); }
  }
  return <form className="backtest-form" aria-busy={busy}
    onSubmit={event => { event.preventDefault(); void run("start"); }}>
    {!start ? <>
      <div className="form-field dataset-field">
        <label htmlFor="proof-account">Dein zugeordnetes Bitget-Konto</label>
        <select id="proof-account" value={accountId} required disabled={busy || !accounts.length}
          onChange={event => { setAccountId(event.target.value); setAction(""); setMessage(""); }}>
          <option value="">Konto auswählen</option>
          {accounts.map(account => <option key={account.account.id} value={account.account.id}>{account.account.name}</option>)}
        </select>
      </div>
      <div className="form-field dataset-field">
        <label htmlFor="proof-action">Aktion für die Bestätigungsprüfung</label>
        <select id="proof-action" value={action} required disabled={busy || !actions.length}
          onChange={event => { setAction(event.target.value as CredentialAction | ""); setMessage(""); }}>
          <option value="">Aktion auswählen</option>
          {actions.map(value => <option key={value} value={value}>{labels[value]}</option>)}
        </select>
      </div>
      {!accounts.length && <p role="status">Noch kein geeignetes Konto zugeordnet. Die Administration muss es zuerst zuordnen.</p>}
      <button type="submit" className="button primary" disabled={busy || !ready}>Prüfvorschau vorbereiten</button>
    </> : <div className="dataset-selection">
      <strong>{start.preview.accountName} · Bitget · Lesezugriff</strong>
      <p>{labels[start.preview.target.action]}</p>
      <p>Diese Prüfung bestätigt deinen Passkey für die angezeigte Aktion. Sie richtet keinen Zugang ein, verändert kein Konto und startet keinen Handel.</p>
      <p>Gültig bis {new Date((grant?.expiresAt ?? start.preview.expiresAt) * 1000).toLocaleTimeString("de-DE")}.</p>
      {grant ? <>
        <p>Dein Gerät hat den Passkey bestätigt. Prüfe Konto und Aktion noch einmal.</p>
        <button type="button" className="button primary" disabled={busy} onClick={() => void run("confirm")}>Prüfung abschließen</button>
      </> : <button type="button" className="button primary" disabled={busy}
        onClick={() => void run("assert")}>Mit Passkey bestätigen</button>}
      <button type="button" className="button secondary" disabled={busy}
        onClick={() => { setStart(null); setGrant(null); setMessage(""); }}>Prüfung verlassen</button>
    </div>}
    {message && <p className="form-result" role="status">{message}</p>}
    <a href="/security/passkeys/verify" className="button secondary">Status neu laden</a>
  </form>;
}
