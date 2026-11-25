"use client";
import { useEffect, useRef, useState } from "react";
import { DEMO_SIGNAL_SYMBOLS } from "../lib/demo-signals-contract";
import { DEMO_START_CONFIRMATION, parseDemoControl, type DemoControl } from "../lib/demo-control-contract";

export function DemoControlPanel({ tenantId, accountId, csrf }: {
  tenantId: string; accountId: string; csrf?: string;
}) {
  const [state, setState] = useState<DemoControl | null>(null), [error, setError] = useState(""),
    [busy, setBusy] = useState(false), [available, setAvailable] = useState(true),
    [limit, setLimit] = useState(3), [assets, setAssets] = useState<string[]>([...DEMO_SIGNAL_SYMBOLS]);
  const pending = useRef(false), uncertain = useRef(false);
  async function call(action?: "start" | "pause") {
    if (pending.current || action && (!state || !csrf || uncertain.current)) return;
    pending.current = true; setBusy(true); setError("");
    try {
      const response = await fetch("/api/bitget-demo/control", { method: action ? "POST" : "GET",
        credentials: "same-origin", cache: "no-store", signal: AbortSignal.timeout(12000),
        ...(action ? { headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf! },
          body: JSON.stringify({ expected_revision: state!.revision, action,
            basket_limit: action === "pause" ? state!.basket_limit : limit,
            assets: action === "pause" ? state!.assets : assets,
            confirmation: action === "start" ? DEMO_START_CONFIRMATION : "pause" }) } : {}) });
      if (response.status === 404) { setAvailable(false); return; }
      if (!response.ok) throw new Error();
      const value = parseDemoControl(await response.json(), tenantId, accountId);
      setState(value); setLimit(value.basket_limit); setAssets(value.assets); uncertain.current = false;
    } catch {
      if (action) uncertain.current = true;
      setError("Steuerung derzeit nicht bestätigt. Bitte den Status neu laden.");
    } finally { pending.current = false; setBusy(false); }
  }
  useEffect(() => {
    void call();
    const timer = setInterval(() => { if (document.visibilityState === "visible") void call(); }, 10000);
    return () => clearInterval(timer);
  }, []); // Parent keys this panel by tenant/account/session.
  const labels: Record<DemoControl["status"], string> = { not_started: "NOCH NICHT GESTARTET",
    start_requested: "START ANGEFORDERT", paused: "PAUSIERT", authorization_changed: "ERNEUTE STARTFREIGABE NÖTIG" };
  return <div className="demo-start-gate">
    <div className="card-heading"><h3>Automatischer Demohandel</h3>
      <span className="badge neutral">{state?.execution_enabled ? "DEMOHANDEL AKTIV" :
        state?.worker_state === "blocked" ? "PRÜFUNG NÖTIG" : state ? labels[state.status] : "NOCH NICHT GESTARTET"}</span></div>
    <p>Long · H1 · 2× · isolierte Margin. Fünf Käufe, sechste Stufe manuell.
      Jeder Kauf verwendet die geplante Eigenkapital-Margin; der Hebel verdoppelt das Marktvolumen.</p>
    {available ? <>
      <label>Maximal gleichzeitige Baskets{" "}
        <select value={limit} disabled={busy || !state} onChange={e => setLimit(Number(e.target.value))}>
          {[3, 4, 5, 6, 7].map(n => <option value={n} key={n}>{n}</option>)}
        </select></label>
      <fieldset disabled={busy || !state}><legend>Coin-Kandidaten</legend>
        {DEMO_SIGNAL_SYMBOLS.map(symbol => <label key={symbol} style={{ display: "inline-block", margin: "0.5rem" }}>
          <input type="checkbox" checked={assets.includes(symbol)} onChange={e => setAssets(current =>
            e.target.checked ? [...current, symbol] : current.filter(v => v !== symbol))} /> {symbol.replace("USDT", "")}
        </label>)}
      </fieldset>
      <p className="panel-intro">Empfehlung für den ersten Demo-Lauf: 3 Baskets.
        Mehr Coin-Kandidaten schaffen mehr Signalchancen; sie erhöhen die Basketzahl nicht.</p>
      <div className="card-heading" style={{ flexWrap: "wrap" }}>
        <button className="button primary" type="button" disabled={busy || !state || !csrf || !assets.length ||
          uncertain.current || state.status === "start_requested" && limit === state.basket_limit &&
          JSON.stringify([...assets].sort()) === JSON.stringify(state.assets)} onClick={() => void call("start")}>Demo-Start anfordern</button>
        <button className="button secondary" type="button" disabled={busy || !state || !csrf || uncertain.current}
          onClick={() => void call("pause")}>Pausieren</button>
        <button className="button secondary" type="button" disabled={busy} onClick={() => void call()}>Status neu laden</button>
      </div>
    </> : <p>Die Dashboard-Steuerung wird mit dem nächsten Deployment verfügbar.</p>}
    <p role="status">{state?.execution_enabled ?
      "Demohandel aktiv. Der Worker prüft geschlossene H1-RSI-Signale und verwaltet eigene Positionen." :
      state?.worker_state === "waiting" && state.worker_detail?.includes("reconciliation") ?
        "Die Orderausführung wird mit Bitget abgeglichen. Es erfolgt kein erneuter Versand." :
      state?.worker_state === "waiting" ? "Der Worker bereitet die nativen Kontoeinstellungen und H1-Indikatoren vor." :
      state?.worker_state === "blocked" ? "Der native Konto- oder Orderabgleich ist noch nicht bestätigt. Neue Käufe bleiben gesperrt; der Worker prüft erneut." :
      state?.worker_state === "offline" ? "Der Workerstatus ist derzeit nicht bestätigt. Neue Käufe sind nicht freigegeben." :
      state?.status === "start_requested" ?
      "Dein Startwunsch ist gespeichert. Der Handelsworker wird noch angebunden; es werden noch keine Strategieorders gesendet." :
      state?.status === "paused" ? "Der Startwunsch ist pausiert. Bestehende Positionen werden dadurch nicht geschlossen." :
      state?.status === "authorization_changed" ? "Kontozugang oder Anmeldung haben sich geändert. Der frühere Startwunsch gilt nicht mehr." :
      "Der Handelsworker wird noch angebunden. Automatischer Demohandel ist noch nicht aktiv."}</p>
    {error && <p role="alert">{error}</p>}
    {state?.requested_at && <small>Gespeichert: {new Date(state.requested_at).toLocaleString("de-DE")} · Stand {state.revision}</small>}
  </div>;
}
