"use client";
import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { parseRecoveryStatus, recoveryReasons, type RecoveryAsset, type RecoveryStatus } from "@/lib/futures-recovery-contracts";

function money(value: string) {
  return `${new Intl.NumberFormat("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(value))} USDT`;
}
function RecoveryCard({ asset, tenantId, csrf }: { asset: RecoveryAsset; tenantId: string; csrf: string }) {
  const router = useRouter();
  const [consent, setConsent] = useState(false);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  async function recover() {
    if (!consent || !asset.allowed || pending || confirmed) return;
    setPending(true); setMessage("");
    try {
      const response = await fetch("/api/futures/recovery", {
        method: "POST", cache: "no-store", redirect: "error", signal: AbortSignal.timeout(10000),
        headers: { "Content-Type": "application/json", "x-csrf-token": csrf },
        body: JSON.stringify({ account_id: asset.account_id, symbol: asset.symbol, cycle: asset.cycle,
          revision: asset.revision, state_digest: asset.state_digest, event_id: crypto.randomUUID(), consent: true }),
      });
      if (!response.ok) throw new Error("unconfirmed");
      const status = parseRecoveryStatus(await response.json(), tenantId);
      if (status.assets.some(a => a.account_id === asset.account_id && a.symbol === asset.symbol)) throw new Error("still-blocked");
      setConfirmed(true);
      setMessage("Freigabe bestätigt. Der neue Basket wartet auf ein neues RSI-Einstiegssignal.");
      router.refresh();
    } catch {
      setMessage("Freigabe nicht bestätigt. Status neu laden und Position, Aufträge sowie Kapital erneut prüfen.");
      // An unknown commit must never result in an automatic retry.
      setConsent(false);
    } finally { setPending(false); }
  }
  return <article className="account-card">
    <div className="card-heading"><strong>{asset.symbol} · Konto {asset.account_id.slice(0, 8)}</strong><span className="badge warning">NACH LIQUIDATION GESPERRT</span></div>
    <p>Zyklus {asset.cycle} · Hebel {asset.leverage}× · {new Intl.DateTimeFormat("de-DE", {
      dateStyle: "medium", timeStyle: "short", timeZone: "Europe/Berlin",
    }).format(new Date(asset.liquidated_at))}</p>
    <p>Gebuchter Nettoverlust: <strong>−{money(asset.net_loss)}</strong>. Dieser bleibt in der Kontohistorie erhalten.</p>
    <p>Kapital für neuen Basket: {money(asset.available_capital)} verfügbar / {money(asset.required_capital)} benötigt.</p>
    {asset.reasons.length > 0 && <ul>{asset.reasons.map(reason => <li key={reason}>{recoveryReasons[reason]}</li>)}</ul>}
    <p>Die Freigabe eröffnet einen neuen Zyklus. Neue Einstiege folgen erst nach einem neuen RSI-Signal und einer neuen Hebelentscheidung.</p>
    <label><input type="checkbox" checked={consent} disabled={!asset.allowed || pending || confirmed}
      onChange={e => setConsent(e.target.checked)} /> Ich möchte dieses Asset manuell wieder für neue Baskets freigeben.</label>
    <p><button type="button" className="button secondary" disabled={!asset.allowed || !consent || pending || confirmed}
      onClick={recover}>{pending ? "Wird geprüft…" : confirmed ? "Freigegeben" : "Wiederbeleben"}</button></p>
    {message && <p role="status">{message}</p>}
  </article>;
}
export function FuturesRecoveryPanel({ data, csrf, summary = false }: { data: RecoveryStatus | null; csrf: string; summary?: boolean }) {
  if (data && !data.assets.length) return null;
  return <section className="panel" role="region" aria-label="Futures-Handelssperren">
    <div className="section-heading"><h2>{summary ? "Handelsblocker: Liquidation" : "Gesperrte Futures-Assets"}</h2><span className="badge warning">MANUELLE FREIGABE</span></div>
    {!data ? <p>Der aktuelle Futures-Paperstatus ist nicht verfügbar. Eine Wiederbelebung kann derzeit nicht bestätigt werden.</p> :
      summary ? <><p>{data.assets.map(a => a.symbol).join(", ")}: {data.assets.length} Asset-Sperre(n) nach Liquidation.
        Neue Baskets bleiben bis zur manuellen Freigabe gesperrt.</p><Link className="button secondary" href="/portfolio#futures-recovery">Sperren und Wiederbelebung prüfen</Link></> :
        <div id="futures-recovery">{data.assets.map(asset => <RecoveryCard
          key={`${asset.account_id}:${asset.symbol}:${asset.cycle}:${asset.revision}:${asset.state_digest}`}
          asset={asset} tenantId={data.tenant_id} csrf={csrf} />)}</div>}
  </section>;
}
