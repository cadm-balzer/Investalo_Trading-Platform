"use client";
import { useEffect, useRef, useState } from "react";
import { MARKET_CONFIRMATION, parseMarketPrepared, parseMarketStatus,
  type MarketPrepared, type MarketStatus } from "../lib/demo-market-order-contract";
const labels: Record<MarketStatus["state"], string> = { prepared: "Vorbereitet", submission_unknown: "Ausgang unbestätigt",
  acknowledged: "Von Bitget angenommen · Ausführung noch prüfen", live: "Offen", partially_filled: "Teilweise ausgeführt",
  filled: "Vollständig ausgeführt", canceled: "Restauftrag storniert" };
export function DemoMarketOrder({ tenantId, accountId, csrf }: { tenantId: string; accountId: string; csrf: string }) {
  const [prepared, setPrepared] = useState<MarketPrepared | null>(null), [status, setStatus] = useState<MarketStatus | null>(null);
  const [busy, setBusy] = useState(false), [message, setMessage] = useState(""), [spent, setSpent] = useState(false);
  const [now, setNow] = useState(Date.now());
  const running = useRef(false), attempted = useRef(false);
  useEffect(() => {
    if (!prepared || spent) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [prepared, spent]);
  async function action(phase: "prepare" | "submit" | "observe") {
    if (running.current || phase === "submit" && (attempted.current || !prepared || prepared.expires_ms <= Date.now())) return;
    running.current = true; setBusy(true); setMessage("");
    if (phase === "prepare") setPrepared(null);
    // The browser never offers another POST once a send was initiated, even
    // on timeout/unknown. Server journal enforces this across tabs/restarts.
    if (phase === "submit") { attempted.current = true; setSpent(true); }
    try {
      const body = phase === "prepare" ? { confirmation: MARKET_CONFIRMATION } : phase === "submit" ?
        prepared!.consent_request : { command_id: prepared?.consent_request.command_id ?? status?.command_id ?? "latest" };
      const response = await fetch(`/api/bitget-demo/orders/btc-market/${phase}`, {
        method: "POST", cache: "no-store", credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
        body: JSON.stringify(body), signal: AbortSignal.timeout(22000) });
      if (!response.ok) throw new Error();
      const data = await response.json();
      if (phase === "prepare") setPrepared(parseMarketPrepared(data, tenantId, accountId));
      else {
        const value = parseMarketStatus(data, prepared?.consent_request.command_id ?? status?.command_id);
        setStatus(value);
        if (value.state !== "prepared") { attempted.current = true; setSpent(true); }
      }
    } catch {
      setMessage(phase === "submit" ? "Ergebnis nicht bestätigt. Bitte nur den Teststatus prüfen."
        : "Demotest derzeit nicht bestätigt. Bitte später erneut prüfen.");
    } finally { running.current = false; setBusy(false); }
  }
  const p = prepared?.report.preview;
  const number = (v: string | null) => v === null ? "Noch nicht bestätigt" :
    new Intl.NumberFormat("de-DE", { maximumFractionDigits: 8 }).format(Number(v));
  return <div className="demo-btc-test-report">
    <h3>BTC-Market-Demotest</h3>
    <p>Ein kleiner Long-Test mit 2× Hebel und isolierter Margin im Bitget-Demokonto.
      Zielgröße etwa 20 USDT. Der Ausführungskurs kann von der Vorschau abweichen.</p>
    {!spent && <button type="button" className="button secondary" disabled={busy}
      onClick={() => void action("prepare")}>{busy ? "Wird geprüft …" : "Demotest vorbereiten"}</button>}
    {p && <dl><dt>Menge</dt><dd>{p.quantity_btc} BTC</dd>
      <dt>Geschätzter Positionswert</dt><dd>{number(p.estimated_notional_usdt)} USDT</dd>
      <dt>Geschätzte Eigenkapital-Margin vor Gebühren</dt><dd>{number(p.estimated_margin_usdt)} USDT</dd></dl>}
    {prepared && !spent && <><p>{prepared.expires_ms <= now ?
      "Vorschau abgelaufen. Bitte erneut vorbereiten." : "Diese Vorbereitung gilt 30 Sekunden. Bei Ablauf erneut vorbereiten."}</p>
      <button type="button" className="button primary" disabled={busy || prepared.expires_ms <= now}
        onClick={() => void action("submit")}>BTC-Demo-Marketorder einmal senden</button></>}
    <button type="button" className="button secondary" disabled={busy}
      onClick={() => void action("observe")}>Teststatus prüfen</button>
    {message && <p role="status">{message}</p>}
    {status && <><p role="status">{labels[status.state]}</p><dl>
      <dt>Bestätigte ausgeführte Menge</dt><dd>{status.filled_quantity_btc === null ? "Noch nicht bestätigt" : `${status.filled_quantity_btc} BTC`}</dd>
      <dt>Ø Ausführungskurs</dt><dd>{number(status.average_price_usdt)}{status.average_price_usdt !== null ? " USDT" : ""}</dd>
      <dt>Gemeldete Ordergebühr</dt><dd>{number(status.reported_fee_usdt)}{status.reported_fee_usdt !== null ? " USDT" : ""}</dd>
      <dt>Positionsabgleich</dt><dd>{status.position_matched ? "Bestätigt" : "Noch nicht bestätigt"}</dd>
    </dl></>}
  </div>;
}
