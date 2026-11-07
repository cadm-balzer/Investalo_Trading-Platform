"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import type { ActionTarget } from "@/lib/credential-action-contracts";
import { credentialActionLabels } from "./credential-action-form";

export type CredentialGrantView = {
  target: ActionTarget; accountName: string; expiresAt: number; confirmationToken: string;
};
const freshFactorProofAvailable = false;

export function CredentialConfirmationForm({ csrf, grant }: { csrf: string; grant: CredentialGrantView }) {
  const [acknowledged, setAcknowledged] = useState(false);
  const [expired, setExpired] = useState(false);
  const [pending, setPending] = useState(false);
  const [attempted, setAttempted] = useState(false);
  const [message, setMessage] = useState("");
  const inFlight = useRef(false);
  const validExpiry = Number.isSafeInteger(grant.expiresAt) && grant.expiresAt > 0 &&
    Number.isFinite(new Date(grant.expiresAt * 1000).getTime());
  useEffect(() => {
    const check = () => setExpired(!validExpiry || Math.floor(Date.now() / 1000) >= grant.expiresAt);
    check();
    const timer = window.setInterval(check, 1000);
    return () => window.clearInterval(timer);
  }, [grant.expiresAt, validExpiry]);
  const expires = validExpiry ? new Intl.DateTimeFormat("de-DE", {
    dateStyle: "medium", timeStyle: "medium", timeZone: "Europe/Berlin",
  }).format(new Date(grant.expiresAt * 1000)) : "Nicht verfügbar";

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!freshFactorProofAvailable || inFlight.current || attempted || !acknowledged || !validExpiry ||
        Math.floor(Date.now() / 1000) >= grant.expiresAt) {
      if (!validExpiry || Math.floor(Date.now() / 1000) >= grant.expiresAt) setExpired(true);
      return;
    }
    inFlight.current = true;
    setPending(true);
    setAttempted(true);
    setMessage("");
    try {
      const response = await fetch("/api/credentials/confirm", {
        method: "POST", credentials: "same-origin", cache: "no-store",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
        body: JSON.stringify({ confirmed: true, confirmation_token: grant.confirmationToken }),
      });
      if (!response.ok) throw new Error("CONFIRMATION_UNAVAILABLE");
      const result: unknown = await response.json();
      if (!result || typeof result !== "object" || Array.isArray(result) ||
          Object.keys(result).length !== 4 || !("status" in result) || result.status !== "verified" ||
          !("execution_enabled" in result) || result.execution_enabled !== false ||
          !("action" in result) || result.action !== grant.target.action ||
          !("platform_account_id" in result) || result.platform_account_id !== grant.target.platform_account_id) {
        throw new Error("CONFIRMATION_UNAVAILABLE");
      }
      setMessage("Der Prüfschritt ist abgeschlossen. Die Kontoänderung wurde nicht ausgeführt.");
    } catch {
      setMessage("Die Bestätigung konnte nicht geprüft werden. Die Kontoänderung wurde hier nicht ausgeführt.");
    } finally {
      setPending(false);
      // One attempt per grant. A missing response must not trigger an automatic
      // retry or imply that a consumed confirmation remains reusable.
    }
  }

  return <form className="backtest-form" onSubmit={submit} aria-busy={pending}>
    <dl className="security-list" style={{ width: "100%" }}>
      <div><dt>Konto</dt><dd>{grant.accountName}</dd></div>
      <div><dt>Festgelegte Aktion</dt><dd>{credentialActionLabels[grant.target.action]}</dd></div>
      <div><dt>Verbindung</dt><dd style={{ overflowWrap: "anywhere" }}>{grant.target.connection_id}</dd></div>
      {grant.target.action === "register" ? <div><dt>Aktueller Zugang</dt><dd>Neue Verbindung vorgesehen</dd></div> : <>
        <div><dt>Schlüsselrevision</dt><dd>{grant.target.expected_revision}</dd></div>
        <div><dt>Gespeicherter Stand</dt><dd>{grant.target.expected_storage}</dd></div>
      </>}
      <div><dt>Bestätigung gültig bis</dt><dd>{expires} · Europe/Berlin</dd></div>
    </dl>
    <p className="form-result" role="status">Die Bestätigung ist gesperrt: Der zusätzliche Nachweis eines frischen zweiten Faktors ist noch nicht verfügbar.</p>
    <p className="panel-intro">Die Kontoanbindung ist noch nicht verfügbar. Diese Prüfung führt die Änderung noch nicht aus. Gib hier keine API-Schlüssel ein.</p>
    <label className="acknowledgement">
      <input type="checkbox" checked={acknowledged} disabled={!freshFactorProofAvailable || pending || attempted || expired}
        onChange={event => setAcknowledged(event.target.checked)} />
      Ich habe das Konto und die festgelegte Aktion geprüft und bestätige diese Auswahl bewusst.
    </label>
    <button type="submit" className="button primary"
      disabled={!freshFactorProofAvailable || pending || attempted || expired || !validExpiry || !acknowledged}>
      {pending ? "Bestätigung wird geprüft …" : "Bestätigung derzeit gesperrt"}
    </button>
    {expired && !attempted && <p className="form-result" role="status">Die kurze Bestätigungsfrist ist abgelaufen.</p>}
    {message && <p className="form-result" role="status">{message}</p>}
    <Link href="/security/credentials" className="button secondary">Zurück zur Kontenauswahl</Link>
  </form>;
}
