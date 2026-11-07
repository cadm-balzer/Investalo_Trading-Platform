"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type { Dataset } from "@/lib/backtest-contracts";
import { isUuid } from "@/lib/backtest-contracts";

export function BacktestForm({ csrf, datasets }: { csrf: string; datasets: Dataset[] | null }) {
  const [symbol, setSymbol] = useState("BTC/USDT");
  const [datasetId, setDatasetId] = useState("");
  const [acknowledged, setAcknowledged] = useState(false);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const key = useRef<string | null>(null);
  const router = useRouter();
  const available = datasets?.filter(dataset => dataset.symbol === symbol) ?? [];
  const chosen = available.find(dataset => dataset.id === datasetId);
  const ready = !!chosen && (!chosen.synthetic || acknowledged);
  function resetChoice() { setDatasetId(""); setAcknowledged(false); key.current = null; setMessage(""); }
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (pending || !ready) return;
    key.current ??= crypto.randomUUID();
    setPending(true);
    setMessage("");
    try {
      const response = await fetch("/api/backtests", {
        method: "POST", credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf, "Idempotency-Key": key.current },
        body: JSON.stringify({ symbol, timeframe: "4h", dataset_id: datasetId }),
      });
      if (!response.ok) {
        const data = await response.json();
        throw new Error(typeof data.error === "string" ? data.error : "Auftrag nicht bestätigt.");
      }
      const job = await response.json();
      if (!isUuid(job.id)) throw new Error("Auftrag nicht bestätigt. Bitte den tatsächlichen Stand prüfen.");
      setMessage("Backtest angefordert. Der tatsächliche Bearbeitungsstand erscheint im Auftrag.");
      key.current = null;
      router.push(`/backtests/${job.id}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Verbindung unterbrochen. Auftrag nicht bestätigt.");
    } finally { setPending(false); }
  }
  return <form className="backtest-form" onSubmit={submit}>
    <div className="form-field"><label htmlFor="symbol">Asset</label><select id="symbol" value={symbol} disabled={pending} onChange={(e) => { setSymbol(e.target.value); resetChoice(); }}><option>BTC/USDT</option><option>ETH/USDT</option></select></div>
    <div className="form-field"><label htmlFor="timeframe">Zeitrahmen</label><select id="timeframe" disabled><option>H4 · geschlossene Kerzen</option></select></div>
    <div className="form-field dataset-field"><label htmlFor="dataset">Eingefrorener Datensatz</label><select id="dataset" value={datasetId} disabled={pending || !available.length} required onChange={e => { setDatasetId(e.target.value); setAcknowledged(false); key.current = null; setMessage(""); }}><option value="">Datensatz bewusst auswählen</option>{available.map(dataset => <option key={dataset.id} value={dataset.id}>{dataset.synthetic ? "SYNTHETISCH · Funktionstest" : dataset.source.venue === "csv" ? "CSV · Herkunft nicht verifiziert" : "Bitget · historische Kerzen"}{dataset.purpose === "test" && !dataset.synthetic ? " · Testzweck" : ""} · {dataset.bar_count} Kerzen · {dataset.start.slice(0, 10)} – {dataset.end.slice(0, 10)} · {dataset.data_digest.slice(0, 10)}</option>)}</select></div>
    {chosen && <div className="dataset-selection"><strong>{chosen.synthetic ? "Synthetische Testdaten – kein Marktnachweis" : chosen.source.venue === "csv" ? "CSV-Import – Herkunft nicht verifiziert" : "Historischer Bitget-Snapshot"}</strong><p>{chosen.bar_count} H4-Kerzen · Snapshot {chosen.data_digest.slice(0, 12)} · {chosen.coverage_complete === null ? "Zeitabdeckung nicht geprüft" : chosen.coverage_complete ? "Nur das angeforderte Zeitfenster ist vollständig" : "Unvollständige Abdeckung des angeforderten Zeitfensters"}. Vollständigkeit belegt weder drei Jahre Historie noch einen unabhängigen Holdout.</p>{chosen.synthetic && <label className="acknowledgement"><input type="checkbox" checked={acknowledged} disabled={pending} onChange={event => setAcknowledged(event.target.checked)} />Ich wähle synthetische Daten ausschließlich für einen Funktionstest.</label>}</div>}
    {!available.length && <p className="form-result" role="status">{datasets === null ? "Dataset-Metadaten aktuell nicht bestätigt. Bitte erneut laden." : "Für dieses Asset ist noch kein eingefrorener H4-Datensatz verfügbar. Ein Datenimport ist erforderlich."}</p>}
    <button type="submit" className="button primary" disabled={pending || !ready}>{pending ? "Wird angefordert …" : "Backtest anfordern"}</button>
    {message && <p className="form-result" role="status">{message}</p>}
    <p className="form-hint">Dieser Snapshot wird beim Auftrag unveränderlich gebunden. Ergebnisse erscheinen nach Verarbeitung; ein Lauf ist noch kein Leistungsnachweis.</p>
  </form>;
}
