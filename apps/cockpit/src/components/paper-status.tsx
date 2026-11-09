import type { PaperStatus } from "@/lib/paper-status-contracts";

function money(value: string | null) {
  return value === null ? "Nicht bewertbar" : `${new Intl.NumberFormat("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(value))} USDT`;
}
function time(value: string) {
  return new Intl.DateTimeFormat("de-DE", { dateStyle: "medium", timeStyle: "short", timeZone: "Europe/Berlin" }).format(new Date(value));
}
export function PaperStatusPanel({ data }: { data: PaperStatus | null }) {
  return <section className="panel">
    <div className="section-heading"><h2>Paperlauf & Handelsjournal</h2><span className="badge paper">SIMULIERT</span></div>
    {!data ? <p className="panel-intro">Der gespeicherte Paperstand ist momentan nicht verfügbar.</p> :
      !data.accounts.length ? <p className="panel-intro">Noch kein eigenes Crypto-Paperkonto eingerichtet.</p> :
      data.accounts.map((account) => <article className="account-card" key={account.id}>
        <div className="card-heading"><strong>{account.name}</strong><span className="badge">{account.status === "paused" ? "PAUSIERT" : account.status === "ready" ? "EINGERICHTET" : "NICHT VERBUNDEN"}</span></div>
        {!account.snapshot ? <p>Noch kein bestätigter Paperstand gespeichert.</p> : <>
          <div className="metric-grid">
            <div><span className="metric-label">Gespeicherte Equity</span><strong>{money(account.snapshot.equity)}</strong><small>{account.snapshot.valuation_fresh ? "Bewertung zum gespeicherten Kursstand" : "Historische Bewertung · Kurse veraltet"}</small></div>
            <div><span className="metric-label">Virtuelles Cash</span><strong>{money(account.snapshot.cash)}</strong></div>
            <div><span className="metric-label">Tagesbasis · {account.snapshot.trading_day}</span><strong>{money(account.snapshot.day_start_equity)}</strong><small>6 % Tageslimit / 8 % Startkapitallimit</small></div>
          </div>
          <p>Letzter gespeicherter Input: {time(account.snapshot.observed_at)} · Revision {account.snapshot.revision}</p>
          <p>{account.snapshot.halted ? "Risikostopp aktiv. Neue Käufe gesperrt." : !account.snapshot.daily_baseline_ready ? "Tagesbasis fehlt. Neue Käufe gesperrt." : "Tagesbasis vorhanden. Weitere Daten- und Risikoprüfungen gelten vor jedem Kauf."}</p>
          <div className="table-scroll"><table><thead><tr><th>Asset</th><th>Menge</th><th>Ø Einstieg</th><th>Schutz</th></tr></thead><tbody>{account.snapshot.positions.map((p) => <tr key={p.symbol}><td>{p.symbol}</td><td>{p.quantity}</td><td>{p.average_price ?? "—"}</td><td>{p.risk_stopped ? "Risikostopp" : p.protected ? "Gewinnschutz" : "—"}</td></tr>)}</tbody></table></div>
          <details><summary>Letzte {account.journal.length} bestätigte Inputs</summary><ol>{account.journal.map((j) => <li key={j.revision}><strong>{time(j.at)} · {j.input_kind === "bar" ? "H4-Kerze" : "Kurs"} · Revision {j.revision}</strong><p>{j.fill_count ? `${j.fill_count} simulierter Fill${j.fill_count === 1 ? "" : "s"}. ` : ""}{j.messages.join(" ") || "Input ohne zusätzliches Handelsereignis."}</p></li>)}</ol></details>
        </>}
      </article>)}
  </section>;
}
