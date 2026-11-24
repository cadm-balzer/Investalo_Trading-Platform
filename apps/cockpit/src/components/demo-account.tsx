"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { parseDemoAccount, type DemoAccount } from "../lib/demo-account-contract";
import { parseDemoStartup, type DemoStartup } from "../lib/demo-startup-contract";
import { DemoStartupReport } from "./demo-startup";
import { parseDemoBTCMarketTest, type DemoBTCMarketTest } from "../lib/demo-btc-test-contract";
import { DemoBTCTestReport } from "./demo-btc-test";
import { DemoMarketOrder } from "./demo-market-order";
import { DemoSignalsPanel } from "./demo-signals";

const money = (v: string | null) => v === null ? "—" :
  `${new Intl.NumberFormat("de-DE", { maximumFractionDigits: 2 }).format(Number(v))} USDT`;
export function DemoAccountPanel({ tenantId, csrf, marketTest = false }: { tenantId: string; csrf?: string; marketTest?: boolean }) {
  const [snapshot, setData] = useState<DemoAccount | null>(null), [error, setError] = useState(""),
    [busy, setBusy] = useState(false), [tick, setTick] = useState(0), [now, setNow] = useState(Date.now());
  const [startup, setStartup] = useState<DemoStartup | null>(null), [checking, setChecking] = useState(false),
    [startupError, setStartupError] = useState("");
  const [btcTest, setBTCTest] = useState<DemoBTCMarketTest | null>(null);
  const inspecting = useRef(false), startupRequest = useRef<AbortController | null>(null);
  const data = snapshot?.tenant_id === tenantId ? snapshot : null;
  const report = startup?.account.tenant_id === tenantId && startup.account.account_id === data?.account_id ? startup : null;
  const proposal = btcTest?.readiness.account.tenant_id === tenantId &&
    btcTest.readiness.account.account_id === data?.account_id ? btcTest : null;
  useEffect(() => {
    setStartup(null); setStartupError(""); setBTCTest(null);
    return () => { startupRequest.current?.abort(); };
  }, [tenantId]);
  async function inspect(kind: "startup" | "btc-market") {
    if (busy || inspecting.current) return;
    const controller = new AbortController();
    startupRequest.current = controller; inspecting.current = true; setChecking(true); setStartupError("");
    if (kind === "btc-market") setBTCTest(null); else setStartup(null);
    try {
      const response = await fetch(`/api/bitget-demo/account?inspection=${kind}`,
        { cache: "no-store", credentials: "same-origin",
          signal: AbortSignal.any([controller.signal, AbortSignal.timeout(12000)]) });
      if (!response.ok) throw new Error();
      const body = await response.json();
      if (kind === "btc-market") {
        const value = parseDemoBTCMarketTest(body, tenantId, data?.account_id);
        if (!controller.signal.aborted) { setBTCTest(value); setData(value.readiness.account); setNow(Date.now()); }
      } else {
        const value = parseDemoStartup(body, tenantId, data?.account_id);
        if (!controller.signal.aborted) { setStartup(value); setData(value.account); setNow(Date.now()); }
      }
    } catch {
      if (!controller.signal.aborted) setStartupError(kind === "btc-market" ?
        "BTC-Testvorschau derzeit nicht bestätigt. Bitte später erneut prüfen." :
        "Startprüfung derzeit nicht bestätigt. Bitte später erneut prüfen.");
    } finally { inspecting.current = false; setChecking(false); }
  }
  useEffect(() => {
    let disposed = false, pending = false;
    const controller = new AbortController();
    async function refresh() {
      if (pending || inspecting.current || document.visibilityState === "hidden") return;
      pending = true; setBusy(true);
      try {
        const response = await fetch("/api/bitget-demo/account", { cache: "no-store", credentials: "same-origin",
          signal: AbortSignal.any([controller.signal, AbortSignal.timeout(12000)]) });
        if (!response.ok) throw new Error();
        const value = parseDemoAccount(await response.json(), tenantId);
        if (!disposed) { setData(value); setError(""); setNow(Date.now()); }
      } catch {
        if (!disposed) setError("Kontodaten derzeit nicht bestätigt. Der zuletzt empfangene Stand bleibt sichtbar.");
      } finally { pending = false; if (!disposed) setBusy(false); }
    }
    void refresh();
    const interval = setInterval(() => { setNow(Date.now()); void refresh(); }, 30000);
    const visible = () => { if (document.visibilityState === "visible") void refresh(); };
    document.addEventListener("visibilitychange", visible);
    return () => { disposed = true; controller.abort(); clearInterval(interval); document.removeEventListener("visibilitychange", visible); };
  }, [tenantId, tick]);
  const stale = !!data && now - Date.parse(data.observed_at) > 60000;
  return <section className="panel">
    <div className="section-heading"><h2>Bitget Futures-Konto</h2><span className="badge neutral">DEMO · USDT</span></div>
    <div className="card-heading"><p className="panel-intro">Kontowert, verfügbare Margin und offene Positionen aus deinem Demo-Konto.</p>
      <button type="button" className="button secondary" disabled={busy || checking} onClick={() => setTick(v => v + 1)}>
        {busy ? "Wird aktualisiert …" : "Aktualisieren"}</button></div>
    {error && <p role="status">{error} <Link href="/security/credentials/demo-trading">Zugang prüfen</Link></p>}
    {!data && !error && <p role="status">Demo-Kontodaten werden geladen …</p>}
    {data && <>
      <p><span className={`badge ${stale || error ? "warning" : "neutral"}`}>{stale || error ? "LETZTER STAND" : "AKTUALISIERT"}</span>
        {" "}Stand: {new Date(data.observed_at).toLocaleString("de-DE", { timeZone: "Europe/Berlin" })}</p>
      <div className="metric-grid">
        {[["Kontowert (Equity)", data.wallet.equity], ["Freie Margin", data.wallet.available],
          ["Unrealisierter Gewinn / Verlust", data.wallet.unrealized_pnl], ["Gesperrter Betrag", data.wallet.locked]]
          .map(([label, value]) => <article className="metric-card" key={label}><span className="metric-label">{label}</span>
            <strong>{money(value)}</strong><small>Bitget Demo · USDT</small></article>)}
      </div>
      <div className="section-heading"><h3>Offene Demo-Positionen</h3><span className="count">{data.positions.length}</span></div>
      {!data.positions.length ? <p>Zum angezeigten Zeitpunkt waren keine offenen Futures-Positionen vorhanden.</p> :
        <div className="table-scroll"><table><thead><tr><th>Asset</th><th>Richtung</th><th>Menge</th>
          <th>Ø Einstieg</th><th>Markpreis</th><th>Unrealisiert</th><th>Hebel</th><th>Margin</th><th>Liquidationspreis</th></tr></thead>
          <tbody>{data.positions.map(p => <tr key={`${p.symbol}:${p.side}`}><td><strong>{p.symbol}</strong></td>
            <td>{p.side === "long" ? "Long" : "Short"}</td><td>{p.quantity}</td><td>{money(p.entry_price)}</td>
            <td>{money(p.mark_price)}</td><td>{money(p.unrealized_pnl)}</td>
            <td>{p.leverage === null ? "—" : `${Number(p.leverage)}×`}</td>
            <td>{p.margin_mode === "isolated" ? "Isoliert" : "Cross"}</td><td>{money(p.liquidation_price)}</td></tr>)}</tbody></table></div>}
    </>}
    {data && <DemoSignalsPanel key={`${tenantId}:${data.account_id}`} tenantId={tenantId}
      accountId={data.account_id} positions={data.positions} />}
    <div className="card-heading"><div><h3>Demo-Handelsstart vorbereiten</h3>
      <p>Prüfe Kontoeinstellungen und offene Aufträge für den ersten Test mit 2× Hebel und isolierter Margin.</p></div>
      <button type="button" className="button secondary" disabled={busy || checking || !data} onClick={() => void inspect("startup")}>
        {checking ? "Wird geprüft …" : "Startprüfung"}</button></div>
    {startupError && <p role="status">{startupError}</p>}
    {report && <DemoStartupReport data={report} />}
    <div className="card-heading"><div><h3>Ersten BTC-Test vorbereiten</h3>
      <p>Prüfe BTC und das gesamte Konto und berechne eine kleine Ordervorschau.</p></div>
      <button type="button" className="button secondary" disabled={busy || checking || !data}
        onClick={() => void inspect("btc-market")}>{checking ? "Wird geprüft …" : "BTC-Testvorschau"}</button></div>
    {proposal && <DemoBTCTestReport data={proposal} />}
    {marketTest && csrf && data && <DemoMarketOrder key={`${tenantId}:${data.account_id}:${csrf}`}
      tenantId={tenantId} accountId={data.account_id} csrf={csrf} />}
  </section>;
}
