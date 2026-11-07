"use client";

import { useRef, useState } from "react";
import {
  allowedCredentialActions,
  type CredentialAction,
  type CredentialActionMetadata,
} from "@/lib/credential-action-contracts";

export const credentialActionLabels: Record<CredentialAction, string> = {
  register: "API-Schlüssel einrichten",
  replace: "API-Schlüssel wechseln",
  revoke: "Gespeicherten Zugang widerrufen",
};
const statusLabels = { disconnected: "Noch nicht verbunden", ready: "Bereit", paused: "Pausiert" };
// Reopening this flow requires a reviewed fresh-factor proof, also enforced
// independently by the server. Normal OIDC MFA claims do not provide that proof.
const freshFactorProofAvailable = false;

export function CredentialActionForm({ csrf, accounts }: {
  csrf: string; accounts: CredentialActionMetadata[];
}) {
  const [accountId, setAccountId] = useState("");
  const [action, setAction] = useState<CredentialAction | "">("");
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const inFlight = useRef(false);
  const chosen = accounts.find(item => item.account.id === accountId);
  const actions = chosen ? allowedCredentialActions(chosen) : [];
  const ready = !!chosen && action !== "" && actions.includes(action);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (inFlight.current || !ready || !freshFactorProofAvailable) return;
    inFlight.current = true;
    setPending(true);
    setMessage("");
    let departing = false;
    try {
      const response = await fetch("/api/credentials/step-up", {
        method: "POST", credentials: "same-origin", cache: "no-store",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
        body: JSON.stringify({ platform_account_id: accountId, action }),
      });
      if (!response.ok) throw new Error("STEP_UP_UNAVAILABLE");
      const result: unknown = await response.json();
      if (!result || typeof result !== "object" || Array.isArray(result) ||
          Object.keys(result).length !== 1 || !("authorization_url" in result) ||
          typeof result.authorization_url !== "string" || result.authorization_url.length > 8192) {
        throw new Error("STEP_UP_UNAVAILABLE");
      }
      // The server fixes the trusted issuer. Reject unsafe URL schemes and
      // embedded credentials even when a response violates its contract.
      const destination = new URL(result.authorization_url);
      if (destination.protocol !== "https:" || destination.username || destination.password || destination.hash) {
        throw new Error("STEP_UP_UNAVAILABLE");
      }
      departing = true;
      window.location.assign(destination.toString());
    } catch {
      setMessage("Die erneute Anmeldung konnte nicht gestartet werden. Lade den Kontostand neu und wähle die Aktion erneut.");
    } finally {
      if (!departing) { inFlight.current = false; setPending(false); }
    }
  }

  return <form className="backtest-form" onSubmit={submit} aria-busy={pending}>
    <div className="form-field dataset-field">
      <label htmlFor="credential-account">Administrativ zugeordnetes Bitget-Konto</label>
      <select id="credential-account" value={accountId} disabled={pending || !accounts.length} required
        onChange={event => { setAccountId(event.target.value); setAction(""); setMessage(""); }}>
        <option value="">Konto bewusst auswählen</option>
        {accounts.map(item => <option key={item.account.id} value={item.account.id}>
          {item.account.name} · {statusLabels[item.account.status]}
        </option>)}
      </select>
    </div>
    <div className="form-field dataset-field">
      <label htmlFor="credential-action">Gewünschte Aktion</label>
      <select id="credential-action" value={action} required disabled={pending || !actions.length}
        onChange={event => { setAction(event.target.value as CredentialAction | ""); setMessage(""); }}>
        <option value="">Aktion bewusst auswählen</option>
        {actions.map(value => <option key={value} value={value}>{credentialActionLabels[value]}</option>)}
      </select>
    </div>
    {chosen && <div className="dataset-selection">
      <strong>{chosen.account.name} · Bitget · Lesezugriff</strong>
      <p>{chosen.account.status === "paused"
        ? "Das Konto ist pausiert. Ein vorhandener gespeicherter Zugang kann weiterhin widerrufen werden."
        : "Konto und mögliche Aktion sind sichtbar. Der Bestätigungsschritt ist derzeit gesperrt."}</p>
      {!actions.length && <p>Für dieses Konto ist derzeit keine neue Aktion verfügbar.</p>}
    </div>}
    {!accounts.length && <p className="form-result" role="status">
      Noch kein geeignetes Bitget-Konto zugeordnet. Die administrative Einrichtung ist erforderlich.
    </p>}
    <button type="submit" className="button primary" disabled={pending || !ready || !freshFactorProofAvailable}>
      {pending ? "Anmeldung wird vorbereitet …" : "Zusätzliche Bestätigung noch nicht verfügbar"}
    </button>
    <p className="form-result" role="status">Der zusätzliche Nachweis eines frischen zweiten Faktors ist noch nicht verfügbar. Die Aktion kann deshalb nicht begonnen werden.</p>
    {message && <p className="form-result" role="status">{message}</p>}
    <p className="form-hint">Hier werden keine API-Schlüssel abgefragt. Die Kontoanbindung ist noch nicht verfügbar; diese Prüfung führt die Änderung noch nicht aus.</p>
  </form>;
}
