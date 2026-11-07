"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";

export function BacktestForm({ csrf }: { csrf: string }) {
  const [symbol, setSymbol] = useState("BTC/USDT");
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const key = useRef<string | null>(null);
  const router = useRouter();
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (pending) return;
    key.current ??= crypto.randomUUID();
    setPending(true);
    setMessage("");
    try {
      const response = await fetch("/api/backtests", {
        method: "POST", credentials: "same-origin",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf, "Idempotency-Key": key.current },
        body: JSON.stringify({ symbol, timeframe: "4h" }),
      });
      if (!response.ok) {
        const data = await response.json();
        throw new Error(typeof data.error === "string" ? data.error : "Auftrag nicht bestätigt.");
      }
      setMessage("Backtest angefordert. Der tatsächliche Bearbeitungsstand erscheint in der Liste.");
      key.current = null;
      router.refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Verbindung unterbrochen. Auftrag nicht bestätigt.");
    } finally { setPending(false); }
  }
  return <form className="backtest-form" onSubmit={submit}>
    <div className="form-field"><label htmlFor="symbol">Asset</label><select id="symbol" value={symbol} disabled={pending} onChange={(e) => { setSymbol(e.target.value); key.current = null; }}><option>BTC/USDT</option><option>ETH/USDT</option></select></div>
    <div className="form-field"><label htmlFor="timeframe">Zeitrahmen</label><select id="timeframe" disabled><option>H4 · geschlossene Kerzen</option></select></div>
    <button type="submit" className="button primary" disabled={pending}>{pending ? "Wird angefordert …" : "Backtest anfordern"}</button>
    {message && <p className="form-result" role="status">{message}</p>}
    <p className="form-hint">Ergebnisse werden erst nach Verarbeitung und Prüfung angezeigt. Ein angeforderter Lauf ist noch kein Leistungsnachweis.</p>
  </form>;
}
