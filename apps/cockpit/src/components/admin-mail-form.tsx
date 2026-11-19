"use client";
import { useRef, useState } from "react";
import type { MailSummary } from "@/lib/admin-mail-state";

export function AdminMailForm({ csrf, initial }: { csrf: string; initial: MailSummary }) {
  const [summary, setSummary] = useState(initial);
  const [host] = useState(initial.host), [username, setUsername] = useState(initial.username);
  const [sender, setSender] = useState(initial.sender), [password, setPassword] = useState("");
  const [code, setCode] = useState(""), [message, setMessage] = useState(""), [busy, setBusy] = useState(false);
  const inFlight = useRef(false);
  async function action(action: "save" | "send" | "verify") {
    if (inFlight.current) return;
    inFlight.current = true; setBusy(true); setMessage("");
    const body = { action, revision: summary.revision, ...(action === "save" ? {
      settings: { host, port: 465, username, sender, password },
    } : action === "verify" ? { code } : {}) };
    setPassword(""); setCode("");
    try {
      const reply = await fetch("/api/admin/mail", { method: "POST", cache: "no-store",
        headers: { "Content-Type": "application/json", "x-csrf-token": csrf }, body: JSON.stringify(body) });
      const value = await reply.json();
      if (!reply.ok || !value.summary || typeof value.summary.revision !== "number") throw new Error();
      setSummary(value.summary);
      setMessage(action === "save" ? "Einstellungen gespeichert. Das Passwort bleibt verschlüsselt." :
        action === "send" ? value.summary.verification === "sent"
          ? "Bestätigungscode versendet. Prüfe auch den Spamordner." : "Versand nicht bestätigt. Falls die Mail angekommen ist, kannst du den Code prüfen." :
          value.summary.verification === "verified" ? "E-Mail bestätigt. Die Administration kann jetzt dein Passkey-Ticket ausstellen." : "Code nicht bestätigt. Prüfe die Eingabe.");
    } catch { setMessage("Ergebnis nicht bestätigt. Lade den Status neu; falls nötig melde dich erneut an."); }
    finally { inFlight.current = false; setBusy(false); }
  }
  return <div aria-busy={busy}>
    <form className="backtest-form" onSubmit={event => { event.preventDefault(); void action("save"); }}>
      <div className="form-field"><label htmlFor="smtp-host">Freigegebener SMTP-Host</label><input id="smtp-host" value={host} readOnly /></div>
      <div className="form-field"><label htmlFor="smtp-security">Verbindung</label><input id="smtp-security" value="SSL/TLS · Port 465" readOnly /></div>
      <div className="form-field"><label htmlFor="smtp-user">SMTP-Benutzername</label><input id="smtp-user" value={username} onChange={e => setUsername(e.target.value)} autoComplete="off" maxLength={256} required disabled={busy} /></div>
      <div className="form-field"><label htmlFor="smtp-password">SMTP-Passwort</label><input id="smtp-password" type="password" value={password} onChange={e => setPassword(e.target.value)} autoComplete="new-password" maxLength={1024} required={!summary.configured} disabled={busy} placeholder={summary.configured ? "Leer lassen, um das gespeicherte Passwort zu behalten" : ""} /></div>
      <div className="form-field"><label htmlFor="smtp-sender">Absenderadresse</label><input id="smtp-sender" type="email" value={sender} onChange={e => setSender(e.target.value)} maxLength={254} required disabled={busy} /></div>
      <button className="button primary" disabled={busy}>SMTP-Einstellungen speichern</button>
    </form>
    <p className="form-hint">Bestätigungsadresse: {summary.recipient}. Das gespeicherte Passwort wird nicht zurückgegeben. Änderungen benötigen eine kürzlich mit MFA bestätigte Anmeldung.</p>
    <button className="button secondary" disabled={busy || !summary.configured || summary.verification === "verified"} onClick={() => void action("send")}>Bestätigungscode per E-Mail senden</button>
    <form className="backtest-form" onSubmit={event => { event.preventDefault(); void action("verify"); }}>
      <div className="form-field"><label htmlFor="mail-code">Bestätigungscode</label><input id="mail-code" value={code} onChange={e => setCode(e.target.value)} inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{8}" maxLength={8} disabled={busy || summary.verification === "none" || summary.verification === "verified"} /></div>
      <button className="button primary" disabled={busy || !/^[0-9]{8}$/.test(code)}>E-Mail bestätigen</button>
    </form>
    {summary.verification === "verified" && <p role="status">E-Mail-Adresse bestätigt.</p>}
    {message && <p className="form-result" role="status">{message}</p>}
    <a className="button secondary" href="/admin/settings">Status neu laden</a>
  </div>;
}
