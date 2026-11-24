"use client";
import { useEffect, useState } from "react";
import { parseDemoSignals, rsiRelation, type DemoSignals, type DemoSignalAsset } from "../lib/demo-signals-contract";
import type { DemoPosition } from "../lib/demo-account-contract";

const format = (value: string) => new Intl.NumberFormat("de-DE", { maximumFractionDigits: 2,
  minimumFractionDigits: 2 }).format(Number(value));
const date = (value: string) => new Date(value).toLocaleString("de-DE", { timeZone: "Europe/Berlin" });

export function DemoSignalRows({ data, stale, positions }: {
  data: DemoSignals; stale: boolean; positions: DemoPosition[];
}) {
  const labels: Record<DemoSignalAsset["entry_condition"], string> = {
    confirmed: "RSI-Erstkaufbedingung erfüllt", waiting_confirmation: "Ein Schluss unter 30 · zweiter fehlt",
    waiting_rsi: "Wartet auf RSI unter 30", unavailable: "H1-Daten nicht bestätigt",
  };
  return <div className="table-scroll"><table className="demo-signal-table">
    <caption className="sr-only">Bitget-Demo-Kandidaten und RSI aus abgeschlossenen H1-Kerzen</caption>
    <thead><tr><th>Asset / H1-Schlusskurs</th><th>RSI14 · H1</th><th>Abstand zur 30</th><th>Einstiegsbedingung</th></tr></thead>
    <tbody>{data.assets.map(asset => {
      const existing = positions.filter(p => p.symbol === asset.symbol);
      const difference = asset.rsi === null ? null : Number(asset.rsi) - 30;
      const relation = asset.rsi === null ? null : rsiRelation(asset.rsi);
      return <tr key={asset.symbol}>
        <td><strong>{asset.symbol}</strong>
          <small>{asset.close_price === null ? "Schlusskurs nicht bestätigt" : `${format(asset.close_price)} USDT`}</small></td>
        <td><strong title={asset.rsi ?? undefined}>{asset.rsi === null ? "—" : format(asset.rsi)}</strong>
          {asset.rsi !== null && <div className="rsi-track" aria-hidden="true">
            <span style={{ width: `${Number(asset.rsi)}%` }} /><i /></div>}
          <small>{asset.previous_rsi === null ? "Vorwert nicht bestätigt" :
            `Vorige H1: ${format(asset.previous_rsi)}`}</small></td>
        <td>{difference === null ? "—" : <><strong>{format(String(Math.abs(difference)))} RSI-Punkte</strong>
          <small>{relation === 1 ? "oberhalb der Einstiegsschwelle" : relation === -1 ?
            "unterhalb der Einstiegsschwelle" : "an der Schwelle"}</small></>}</td>
        <td><strong>{stale ? "Datenstand veraltet" : existing.length > 0 ?
          "Nachkaufprüfung noch nicht bestätigt" : labels[asset.entry_condition]}</strong>
          {asset.below_count !== null && existing.length === 0 &&
            <small>{asset.below_count}/2 aufeinanderfolgende Schlüsse unter 30</small>}
          {existing.length > 0 && <small>Position vorhanden · Nachkaufstaffel noch nicht zugeordnet</small>}
          {asset.candle_closed_at && <small>Kerzenschluss: {date(asset.candle_closed_at)}</small>}
          {asset.fetched_at && <small>Marktabruf: {date(asset.fetched_at)}</small>}
        </td>
      </tr>;
    })}</tbody>
  </table></div>;
}

export function DemoSignalsPanel({ tenantId, accountId, positions }: {
  tenantId: string; accountId: string; positions: DemoPosition[];
}) {
  const [data, setData] = useState<DemoSignals | null>(null), [error, setError] = useState(""),
    [busy, setBusy] = useState(false), [tick, setTick] = useState(0), [now, setNow] = useState(Date.now());
  useEffect(() => { setData(null); setError(""); }, [tenantId, accountId]);
  useEffect(() => {
    let disposed = false, pending = false;
    const controller = new AbortController();
    async function refresh() {
      if (pending || document.visibilityState === "hidden") return;
      pending = true; setBusy(true);
      try {
        const response = await fetch("/api/bitget-demo/signals", { cache: "no-store", credentials: "same-origin",
          signal: AbortSignal.any([controller.signal, AbortSignal.timeout(12000)]) });
        if (!response.ok) throw new Error();
        const value = parseDemoSignals(await response.json(), tenantId, accountId);
        if (!disposed) { setData(value); setError(""); setNow(Date.now()); }
      } catch {
        if (!disposed) setError("H1-Marktdaten derzeit nicht bestätigt. Der letzte Stand bleibt sichtbar.");
      } finally { pending = false; if (!disposed) setBusy(false); }
    }
    void refresh();
    const interval = setInterval(() => { setNow(Date.now()); void refresh(); }, 30000);
    const visible = () => { if (document.visibilityState === "visible") void refresh(); };
    document.addEventListener("visibilitychange", visible);
    return () => { disposed = true; controller.abort(); clearInterval(interval);
      document.removeEventListener("visibilitychange", visible); };
  }, [tenantId, accountId, tick]);
  const current = data?.tenant_id === tenantId && data.account_id === accountId ? data : null;
  const stale = !!current && (now >= Date.parse(current.next_candle_close) ||
    now - Date.parse(current.observed_at) > 60000 || !!error);
  return <div className="demo-signals">
    <div className="card-heading"><div><h3>RSI & H1-Einstiegssignale</h3>
      <p>Bitget-Futures, RSI14 nach Wilder. Nur abgeschlossene H1-Kerzen zählen.</p></div>
      <button type="button" className="button secondary" disabled={busy} onClick={() => setTick(t => t + 1)}>
        {busy ? "Wird geladen …" : "RSI aktualisieren"}</button></div>
    {error && <p role="status">{error}</p>}
    {!current && !error && <p role="status">H1-Einstiegssignale werden geladen …</p>}
    {current && <>
      <p><span className={`badge ${stale ? "warning" : "neutral"}`}>{stale ? "LETZTER STAND" : "H1-SIGNALBEOBACHTUNG"}</span>
        {" "}Nächster H1-Schluss: {date(current.next_candle_close)}</p>
      <DemoSignalRows data={current} stale={stale} positions={positions} />
    </>}
    <p className="panel-intro">Erstkauf: zwei aufeinanderfolgende H1-Schlüsse mit RSI unter 30.
      Nachkauf: RSI zwischenzeitlich über 30, danach wieder unter 30 und mindestens 5 % unter dem
      letzten tatsächlichen Kaufpreis. Der RSI-Abstand ist keine Zeit- oder Kaufprognose.</p>
    <div className="demo-start-gate" role="status">
      <div className="card-heading"><h3>Startfreigabe für automatischen Demohandel</h3>
        <span className="badge neutral">NOCH NICHT GESTARTET</span></div>
      <p>Der automatische Handel wird eingerichtet. Käufe, Ausstiege, Gebühren und Funding müssen
        noch vollständig mit den tatsächlichen Demo-Ausführungen und Kontobuchungen verbunden werden.</p>
      <button type="button" className="button secondary" disabled aria-describedby="demo-start-unavailable">
        Automatischen Demohandel starten</button>
      <p id="demo-start-unavailable" className="panel-intro">Die Startfreigabe wird hier verfügbar,
        sobald diese Anbindung und die Prüfung deiner ausgewählten Coin-Einstellungen abgeschlossen sind.
        Profil: Long · 2× · isolierte Margin · fünf Käufe, sechste Stufe manuell.</p>
    </div>
  </div>;
}
