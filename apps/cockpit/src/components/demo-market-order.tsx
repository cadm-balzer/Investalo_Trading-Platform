"use client";
import { useEffect, useRef, useState } from "react";
import { MARKET_CONFIRMATION, MARKET_CLOSE_CONFIRMATION, parseMarketPrepared, parseMarketClosePrepared, parseMarketOutcome,
  type MarketPreparation, type MarketOutcome, type MarketStatus } from "../lib/demo-market-order-contract";
const labels: Record<MarketStatus["state"], string> = { prepared: "Vorbereitet", submission_unknown: "Ausgang unbestätigt",
  acknowledged: "Von Bitget angenommen · Ausführung noch prüfen", live: "Offen", partially_filled: "Teilweise ausgeführt",
  filled: "Vollständig ausgeführt", canceled: "Restauftrag storniert" };
export function DemoMarketOrder({ tenantId, accountId, csrf }: { tenantId: string; accountId: string; csrf: string }) {
  const [prepared, setPrepared] = useState<MarketPreparation | null>(null), [outcome, setOutcome] = useState<MarketOutcome | null>(null);
  const [busy, setBusy] = useState(false), [message, setMessage] = useState("");
  const [openSpent,setOpenSpent]=useState(false),[closeSpent,setCloseSpent]=useState(false),[closing,setClosing]=useState(false);
  const status=outcome?.schema==="investalo-demo-market-close-status/1" ? outcome.order : outcome;
  const settlement=outcome?.schema==="investalo-demo-market-close-status/1" ? outcome.settlement : null;
  const spent=closing ? closeSpent : openSpent;
  const [now, setNow] = useState(Date.now());
  const running = useRef(false), attempted = useRef(new Set<"open" | "close">());
  useEffect(() => {
    if (!prepared || spent) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [prepared, spent]);
  async function action(phase: "prepare" | "submit" | "observe" | "close-prepare" | "close-submit") {
    const send=phase==="submit" || phase==="close-submit",prepare=phase==="prepare" || phase==="close-prepare";
    const mode=phase.startsWith("close") ? "close" : "open";
    if (running.current || send && (attempted.current.has(mode) || !prepared || prepared.expires_ms <= Date.now())) return;
    running.current = true; setBusy(true); setMessage("");
    if (prepare) {setPrepared(null);setOutcome(null);setClosing(mode==="close");}
    // The browser never offers another POST once a send was initiated, even
    // on timeout/unknown. Server journal enforces this across tabs/restarts.
    if (send) { attempted.current.add(mode); mode==="close" ? setCloseSpent(true) : setOpenSpent(true); }
    try {
      const body = prepare ? { confirmation: mode==="close" ? MARKET_CLOSE_CONFIRMATION : MARKET_CONFIRMATION } : send ?
        prepared!.consent_request : { command_id: prepared?.consent_request.command_id ?? status?.command_id ?? "latest" };
      const response = await fetch(`/api/bitget-demo/orders/btc-market/${phase}`, {
        method: "POST", cache: "no-store", credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
        body: JSON.stringify(body), signal: AbortSignal.timeout(22000) });
      if (!response.ok) throw new Error();
      const data = await response.json();
      if (prepare) setPrepared(mode==="close" ? parseMarketClosePrepared(data,tenantId,accountId) : parseMarketPrepared(data, tenantId, accountId));
      else {
        const value = parseMarketOutcome(data, prepared?.consent_request.command_id ?? status?.command_id);
        setOutcome(value);
        const closed=value.schema==="investalo-demo-market-close-status/1";
        const order=closed ? value.order : value;
        if (closed) {setClosing(true);setOpenSpent(true);attempted.current.add("open");}
        if (order.state!=="prepared") {
          const actualMode=closed || prepared?.schema==="investalo-demo-market-close-prepared/1" ? "close" : "open";
          attempted.current.add(actualMode);actualMode==="close" ? setCloseSpent(true) : setOpenSpent(true);
        }
      }
    } catch {
      setMessage(send ? "Ergebnis nicht bestätigt. Bitte nur den Teststatus prüfen."
        : "Demotest derzeit nicht bestätigt. Bitte später erneut prüfen.");
    } finally { running.current = false; setBusy(false); }
  }
  const p = prepared?.schema==="investalo-demo-market-prepared/1" ? prepared.report.preview : prepared;
  const number = (v: string | null) => v === null ? "Noch nicht bestätigt" :
    new Intl.NumberFormat("de-DE", { maximumFractionDigits: 8 }).format(Number(v));
  return <div className="demo-btc-test-report">
    <h3>BTC-Market-Demotest</h3>
    <p>Ein kleiner Long-Test mit 2× Hebel und isolierter Margin im Bitget-Demokonto.
      Zielgröße etwa 20 USDT. Der Ausführungskurs kann von der Vorschau abweichen.</p>
    {!openSpent && <button type="button" className="button secondary" disabled={busy}
      onClick={() => void action("prepare")}>{busy ? "Wird geprüft …" : "Demotest vorbereiten"}</button>}
    {!closeSpent && <button type="button" className="button secondary" disabled={busy}
      onClick={()=>void action("close-prepare")}>Abschluss der Testposition vorbereiten</button>}
    {p && <dl><dt>Menge</dt><dd>{p.quantity_btc} BTC</dd>
      <dt>Geschätzter Positionswert</dt><dd>{number(p.estimated_notional_usdt)} USDT</dd>
      {"estimated_margin_usdt" in p && <><dt>Geschätzte Eigenkapital-Margin vor Gebühren</dt><dd>{number(p.estimated_margin_usdt)} USDT</dd></>}
      {closing && <><dt>Abschluss</dt><dd>Market · ausschließlich bestehende Testposition</dd></>}</dl>}
    {prepared && !spent && <><p>{prepared.expires_ms <= now ?
      "Vorschau abgelaufen. Bitte erneut vorbereiten." : "Diese Vorbereitung gilt 30 Sekunden. Bei Ablauf erneut vorbereiten."}</p>
      <button type="button" className="button primary" disabled={busy || prepared.expires_ms <= now}
        onClick={() => void action(closing ? "close-submit" : "submit")}>
          {closing ? "BTC-Testposition einmal schließen" : "BTC-Demo-Marketorder einmal senden"}</button></>}
    <button type="button" className="button secondary" disabled={busy}
      onClick={() => void action("observe")}>Teststatus prüfen</button>
    {message && <p role="status">{message}</p>}
    {status && <><p role="status">{closing ? "Abschluss: " : ""}{labels[status.state]}</p><dl>
      <dt>Bestätigte ausgeführte Menge</dt><dd>{status.filled_quantity_btc === null ? "Noch nicht bestätigt" : `${status.filled_quantity_btc} BTC`}</dd>
      <dt>Ø Ausführungskurs</dt><dd>{number(status.average_price_usdt)}{status.average_price_usdt !== null ? " USDT" : ""}</dd>
      <dt>Gemeldete Ordergebühr</dt><dd>{number(status.reported_fee_usdt)}{status.reported_fee_usdt !== null ? " USDT" : ""}</dd>
      <dt>Positionsabgleich</dt><dd>{status.position_matched ? "Bestätigt" : "Noch nicht bestätigt"}</dd>
    </dl></>}
    {settlement && <><p role="status">{settlement.position_closed ? "Testposition geschlossen · Nullposition bestätigt" :
      "Nullposition noch nicht bestätigt"}</p><dl>
      <dt>Gebühr der Eröffnung</dt><dd>{number(settlement.opening_reported_fee_usdt)} USDT</dd>
      <dt>Gebühr des Abschlusses</dt><dd>{number(status?.reported_fee_usdt ?? null)} USDT</dd>
      <dt>Kontowert nach Abgleich</dt><dd>{number(settlement.wallet.equity)} USDT</dd>
      <dt>Freie Margin</dt><dd>{number(settlement.wallet.available)} USDT</dd>
      <dt>Offene Positionen</dt><dd>{settlement.open_position_count}</dd>
      <dt>Kontostand geprüft</dt><dd>{new Date(settlement.observed_at).toLocaleString("de-DE")}</dd>
    </dl></>}
  </div>;
}
