"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { parseBasketSettings, type BasketSetting, type BasketSettings } from "@/lib/futures-paper-settings-contracts";

function AccountSettings({ initial, tenantId, csrf }: { initial: BasketSetting; tenantId: string; csrf: string }) {
  const router = useRouter();
  const [current, setCurrent] = useState(initial);
  const [limit, setLimit] = useState(initial.basket_limit);
  const [pending, setPending] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [message, setMessage] = useState("");
  async function save() {
    setPending(true); setMessage("");
    try {
      const response = await fetch("/api/futures/settings", { method: "POST", redirect: "error",
        headers: { "Content-Type": "application/json", "x-csrf-token": csrf },
        body: JSON.stringify({ account_id: current.account_id, expected_revision: current.revision, basket_limit: limit }) });
      if (!response.ok) throw new Error("NOT_CONFIRMED");
      const result = parseBasketSettings(await response.json(), tenantId);
      const accepted = result.accounts[0];
      if (result.accounts.length !== 1 || accepted.account_id !== current.account_id ||
        accepted.revision !== current.revision+1 || accepted.basket_limit !== limit) throw new Error("NOT_CONFIRMED");
      setCurrent(accepted);
      setMessage("Basket-Obergrenze gespeichert. Die Futures-Paper-Ausführung folgt im nächsten Schritt.");
      router.refresh();
    } catch {
      setUncertain(true);
      setMessage("Speichern nicht bestätigt. Bitte den aktuellen Stand neu laden; die Änderung wird nicht automatisch wiederholt.");
    } finally { setPending(false); }
  }
  return <article className="account-card">
    <div className="card-heading"><strong>{current.account_name}</strong><span className="badge paper">FUTURES · PAPER · 2×</span></div>
    <label htmlFor={`baskets-${current.account_id}`}>Maximal gleichzeitige Baskets</label>{" "}
    <select id={`baskets-${current.account_id}`} value={limit} disabled={!current.can_edit || pending || uncertain}
      onChange={e => setLimit(Number(e.target.value))}>
      {[3, 4, 5, 6, 7].map(n => <option key={n} value={n}>{n} Baskets</option>)}
    </select>
    <p>Anfangs drei bis fünf. Sechs und sieben werden erst durch die bestätigten Gewinnetappen finanziert.</p>
    <p>Kapitalempfehlung ausstehend: Der eigene Futures-Kontostand und aktuelle Mindestorderdaten sind noch nicht angebunden.</p>
    <p>Offene Baskets behalten ihre vollständige Kaufstaffel und manuelle Reserve. Eine niedrigere Obergrenze wartet auf Abschlüsse.</p>
    <button type="button" className="button secondary"
      disabled={!current.can_edit || pending || uncertain || (current.saved && limit === current.basket_limit)} onClick={save}>
      {pending ? "Wird gespeichert…" : "Basket-Obergrenze speichern"}
    </button>
    {uncertain && <p><a className="text-link" href="/portfolio">Aktuellen Stand neu laden</a></p>}
    {message && <p role="status">{message}</p>}
  </article>;
}

export function FuturesPaperSettingsPanel({ data, csrf }: { data: BasketSettings | null; csrf: string }) {
  return <section className="panel" aria-label="Futures-Paperplanung">
    <div className="section-heading"><h2>Futures-Baskets planen</h2><span className="badge neutral">VORBEREITUNG</span></div>
    <p>2× ist die Basis aus dem bisherigen Hebelvergleich. Mehr Coins teilen das verfügbare Kapital auf; die Kapitalempfehlung ist keine Gewinnprognose.</p>
    {!data ? <p>Kontoeinstellungen derzeit nicht verfügbar.</p> : !data.accounts.length ?
      <p>Noch kein geeignetes USDT-Paperkonto zugeordnet.</p> :
      data.accounts.map(a => <AccountSettings key={`${a.account_id}:${a.revision}`} initial={a} tenantId={data.tenant_id} csrf={csrf} />)}
  </section>;
}
