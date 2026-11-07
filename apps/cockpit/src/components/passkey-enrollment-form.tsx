"use client";

import { useRef, useState } from "react";
import type { PublicKeyCredentialCreationOptionsJSON } from "@simplewebauthn/server";

function bytes(value: string): ArrayBuffer {
  const raw = atob(value.replaceAll("-", "+").replaceAll("_", "/"));
  return Uint8Array.from(raw, char => char.charCodeAt(0)).buffer;
}
function encoded(value: ArrayBuffer): string {
  return btoa(String.fromCharCode(...new Uint8Array(value))).replaceAll("+", "-").replaceAll("/", "_").replace(/=+$/, "");
}
export function PasskeyEnrollmentForm({ csrf }: { csrf: string }) {
  const [ticket, setTicket] = useState(""), [busy, setBusy] = useState(false), [message, setMessage] = useState("");
  const inFlight = useRef(false);
  async function register(event: React.FormEvent) {
    event.preventDefault();
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(true); setMessage("");
    const token = ticket.trim(); setTicket("");
    try {
      if (!window.isSecureContext || !navigator.credentials) throw new Error();
      const response = await fetch("/api/passkeys/enrollment/start", { method: "POST",
        headers: { "Content-Type": "application/json", "x-csrf-token": csrf }, body: JSON.stringify({ token }) });
      if (!response.ok) throw new Error();
      const start = await response.json() as { attempt_id: string; options: PublicKeyCredentialCreationOptionsJSON };
      const options = start.options;
      const credential = await navigator.credentials.create({ publicKey: {
        ...options, challenge: bytes(options.challenge), user: { ...options.user, id: bytes(options.user.id) },
        extensions: { credProps: true },
        excludeCredentials: options.excludeCredentials?.map(item => ({ ...item, type: "public-key", id: bytes(item.id),
          transports: item.transports as AuthenticatorTransport[] | undefined })),
      } }) as PublicKeyCredential | null;
      if (!credential || credential.type !== "public-key" ||
        !(credential.response instanceof AuthenticatorAttestationResponse)) throw new Error();
      const registration = { id: credential.id, rawId: encoded(credential.rawId), type: credential.type,
        response: { clientDataJSON: encoded(credential.response.clientDataJSON),
          attestationObject: encoded(credential.response.attestationObject) },
        clientExtensionResults: credential.getClientExtensionResults(),
        ...(credential.authenticatorAttachment ? { authenticatorAttachment: credential.authenticatorAttachment } : {}) };
      const finish = await fetch("/api/passkeys/enrollment/finish", { method: "POST",
        headers: { "Content-Type": "application/json", "x-csrf-token": csrf },
        body: JSON.stringify({ attempt_id: start.attempt_id, credential: registration }) });
      if (!finish.ok) throw new Error();
      const receipt = await finish.json() as Record<string, unknown>;
      if (!receipt || receipt.registered !== true || Object.keys(receipt).length !== 1) throw new Error();
      setMessage("Passkey registriert. Lade den Status neu, um die gespeicherte Registrierung zu prüfen.");
    } catch {
      setMessage("Registrierung nicht bestätigt. Lade den Status neu. Bei einem verbrauchten Ticket hilft die Administration weiter.");
    } finally { inFlight.current = false; setBusy(false); }
  }
  return <form onSubmit={register} className="backtest-form" aria-busy={busy}>
    <div className="form-field">
      <label htmlFor="passkey-ticket">Einmaliges Registrierungsticket</label>
      <input id="passkey-ticket" type="password" autoComplete="off" spellCheck={false}
        value={ticket} onChange={event => setTicket(event.target.value)} maxLength={43} required disabled={busy} />
    </div>
    <button className="button primary" type="submit" disabled={busy || ticket.trim().length !== 43}>
      {busy ? "Registrierung läuft …" : "Passkey registrieren"}
    </button>
    {message && <p className="form-result" role="status">{message}</p>}
    <a href="/security/passkeys" className="button secondary">Status neu laden</a>
    <p className="form-hint">Die Administration gibt das Ticket nach deiner E-Mail-Bestätigung aus. Dein Gerät muss den Passkey durch PIN oder Biometrie bestätigen.</p>
  </form>;
}
