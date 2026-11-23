import type { DemoStartup, DemoBTCReadiness } from "../lib/demo-startup-contract";

const reasons: Record<DemoStartup["blockers"][number], string> = {
  initial_balance_changed: "Kontowert oder freie Margin weichen vom bestätigten Startguthaben von 10.000 USDT ab.",
  wallet_unknown: "Ein benötigter Kontobetrag wurde von Bitget nicht bestätigt.",
  wallet_collateral: "Es gibt belegte Margin, offene Gewinne/Verluste oder abweichende Sicherheiten.",
  positions_present: "Es bestehen bereits Futures-Positionen. Diese müssen vor dem ersten Test zugeordnet werden.",
  orders_present: "Es wurden offene Aufträge gefunden. Diese müssen vor dem Test zugeordnet werden.",
  order_pages_incomplete: "Die Auftragsabfrage konnte nicht vollständig paginiert werden.",
  configuration_mismatch: "Mindestens ein Asset benötigt eine andere Einstellung für das geplante Profil.",
};
const categories: Record<DemoStartup["orders"][number]["category"], string> = {
  live: "Offene Limitaufträge", partially_filled: "Teilweise ausgeführte Aufträge",
  normal_plan: "Triggeraufträge", track_plan: "Trailing-Aufträge", profit_loss: "Take-Profit / Stop-Loss",
};
export function DemoStartupReport({ data }: { data: DemoStartup | DemoBTCReadiness }) {
  return <div className="demo-startup-report">
    <p>Prüfstand: {new Date(data.observed_at).toLocaleString("de-DE", { timeZone: "Europe/Berlin" })}.
      {" "}Vergleich für den ersten Demo-Test mit 10.000 USDT Startguthaben.</p>
    <p><strong>{data.blockers.length ? "Vorbereitung benötigt Anpassungen" : "Abgefragte Einstellungen passen"}</strong></p>
    {!!data.blockers.length && <ul>{data.blockers.map(reason => <li key={reason}>{reasons[reason]}</li>)}</ul>}
    <div className="table-scroll"><table><thead><tr><th>Asset</th><th>Margin</th><th>Positionen</th>
      <th>Long-Hebel</th><th>Profil</th></tr></thead><tbody>{data.configurations.map(c => <tr key={c.symbol}>
        <td><strong>{c.symbol}</strong></td><td>{c.margin_mode === "isolated" ? "Isoliert" :
          c.margin_mode === "crossed" ? "Cross" : "Unbestätigt"}</td>
        <td>{c.position_mode === "one_way_mode" ? "Einseitig" : c.position_mode === "hedge_mode" ? "Hedge" : "Unbestätigt"}</td>
        <td>{c.long_leverage === null ? "Unbestätigt" : `${Number(c.long_leverage)}×`}</td>
        <td>{c.matches ? "Passt · 2× isoliert" : "Prüfen"}</td></tr>)}</tbody></table></div>
    <ul>{data.orders.map(o => <li key={o.category}>{categories[o.category]}: {o.count}
      {!o.complete && " · Abfrage unvollständig"}</li>)}</ul>
    <p>Die Prüfung ändert keine Bitget-Einstellungen. Ältere offene Aufträge außerhalb des
      API-Zeitfensters und tatsächliche Handelskosten sind noch nicht abschließend geprüft.
      Der erste Testauftrag wird separat vorbereitet und freigegeben.</p>
    <p><span className="badge neutral">ORDERVERSAND NOCH AUS</span></p>
  </div>;
}
