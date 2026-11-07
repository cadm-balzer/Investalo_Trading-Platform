import Link from "next/link";
import { getSession, type Session } from "@/lib/auth";
import { apiRequest, BackendError, type Overview, type Job } from "@/lib/backend";
import { Icon, Brand } from "./icons";
import { Login } from "./login";
import { BacktestForm } from "./backtest-form";
import { parseOverview } from "@/lib/contracts";
import { parseDatasets, type Dataset } from "@/lib/backtest-contracts";
import { ResultMetrics } from "./backtest-result";

type Section = "overview" | "portfolio" | "journal" | "backtest" | "shield";
const navigation: { label: string; href: string; section: Section }[] = [
  { label: "Übersicht", href: "/", section: "overview" },
  { label: "Portfolio", href: "/portfolio", section: "portfolio" },
  { label: "Tradingjournal", href: "/journal", section: "journal" },
  { label: "Backtests", href: "/backtests", section: "backtest" },
  { label: "Sicherheit", href: "/security", section: "shield" },
];
const titles: Record<Section, [string, string]> = {
  overview: ["Alles im Blick.", "Dein Portfolio, deine Entscheidungen und der aktuelle Forschungsstand."],
  portfolio: ["Kapital mit Überblick.", "Konten und Positionen bleiben nach Währung und Handelsmodus getrennt."],
  journal: ["Jede Entscheidung zählt.", "Dein nachvollziehbares Protokoll aus tatsächlichen Paperereignissen."],
  backtest: ["Erst prüfen. Dann handeln.", "Strategien mit Daten und Nettokosten bewerten, bevor echtes Kapital ins Spiel kommt."],
  shield: ["Kontrolle beginnt mit Sicherheit.", "Geschützte Anmeldung und klare Grenzen für dein Cockpit."],
};
function money(value: string | undefined, currency: string): string {
  if (value === undefined || !Number.isFinite(Number(value))) return "—";
  return `${new Intl.NumberFormat("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(value))} ${currency}`;
}
function date(value: string | undefined | null): string {
  if (!value || Number.isNaN(Date.parse(value))) return "Zeitpunkt nicht verfügbar";
  return new Intl.DateTimeFormat("de-DE", { dateStyle: "medium", timeStyle: "short", timeZone: "Europe/Berlin" }).format(new Date(value));
}
export function jobLabel(status: string) {
  const labels: Record<string, string> = { QUEUED: "Angefordert", RUNNING: "Wird geprüft", SUCCEEDED: "Abgeschlossen", FAILED: "Fehlgeschlagen", COMPLETED: "Abgeschlossen", PENDING: "Wartet", BLOCKED: "Voraussetzungen fehlen" };
  return labels[status.toUpperCase()] ?? status;
}
function Empty({ title, children, icon = "portfolio" }: { title: string; children: React.ReactNode; icon?: "portfolio" | "journal" | "backtest" }) {
  return <div className="empty-state"><span className="empty-icon"><Icon name={icon} size={26} /></span><h3>{title}</h3><p>{children}</p></div>;
}
function Jobs({ jobs }: { jobs: Job[] }) {
  if (!jobs.length) return <Empty title="Noch kein Backtest angefordert" icon="backtest">Fordere einen Lauf an. Nur tatsächlich verarbeitete Daten und Ergebnisse werden angezeigt.</Empty>;
  return <div className="job-list">{jobs.map((job) => <Link className="job-entry" href={`/backtests/${job.id}`} key={job.id}><div className="job-row"><div className="asset-symbol"><Icon name="backtest" /></div><div><strong>{job.payload.symbol} · H4</strong><small>{date(job.created_at)}</small></div><span className="badge neutral">{jobLabel(job.status)}</span><Icon name="arrow" size={16} /></div>{job.result_summary && <div className="job-summary"><span className={`badge ${job.result_summary.synthetic ? "warning" : "neutral"}`}>{job.result_summary.synthetic ? "SYNTHETISCH · NUR TEST" : "NICHT VALIDIERT"}</span><ResultMetrics result={job.result_summary} compact /></div>}</Link>)}</div>;
}
function Journal({ data }: { data: Overview }) {
  if (!data.journal.length) return <Empty title="Ein Journal beginnt mit einer Entscheidung" icon="journal">Noch keine Ereignisse vorhanden. Simulierte Fills und Riskentscheidungen werden hier nachvollziehbar protokolliert.</Empty>;
  return <div className="journal-list">{data.journal.map((entry) => <article className="journal-row" key={entry.id}><div className="timeline-dot" /><div><span className="eyebrow">{entry.event_type}</span><p>{entry.message ?? "Paperereignis protokolliert."}</p><small>{date(entry.created_at)}{entry.symbol ? ` · ${entry.symbol}` : ""}</small></div></article>)}</div>;
}
function Accounts({ data }: { data: Overview }) {
  if (!data.accounts.length) return <Empty title="Noch kein Paperkonto eingerichtet">Sobald ein virtuelles Konto zugeordnet ist, erscheinen hier Kapital, Kontowährung und Datenalter.</Empty>;
  return <div className="account-grid">{data.accounts.map((account) => <article key={account.id} className="account-card"><div className="card-heading"><span>{account.name}</span><span className="badge">{account.mode}</span></div><span className="metric-label">Equity · {account.currency}</span><strong className="account-equity">{money(account.equity, account.currency)}</strong>{account.cash !== undefined && <p>Verfügbar <b>{money(account.cash, account.currency)}</b></p>}<small>Aktualisiert: {date(account.updated_at)}</small></article>)}</div>;
}
function Positions({ data }: { data: Overview }) {
  if (!data.positions.length) return <Empty title="Keine offenen Positionen">Aktuell hat dieses Paperportfolio keine offenen Positionen. Die manuelle Reserve wird erst nach fünf regulären Einstiegen angeboten.</Empty>;
  return <div className="table-scroll"><table><thead><tr><th>Asset</th><th>Menge</th><th>Ø Einstieg</th><th>Stufe</th></tr></thead><tbody>{data.positions.map((p) => <tr key={`${p.account_id}:${p.symbol}`}><td><strong>{p.symbol}</strong></td><td>{p.quantity}</td><td>{p.average_price}</td><td>{p.stage ?? "—"}</td></tr>)}</tbody></table></div>;
}
export function Shell({ session, section, children, connected }: { session: Session; section: Section; children: React.ReactNode; connected: boolean }) {
  return <div className="app-shell">
    <aside className="sidebar"><Link href="/" className="brand-link" aria-label="Investalo Übersicht"><Brand /></Link><span className="sidebar-subtitle">TRADING COCKPIT</span><nav aria-label="Hauptnavigation">{navigation.map((n) => <Link key={n.href} href={n.href} className={`nav-link ${n.section === section ? "active" : ""}`} aria-current={n.section === section ? "page" : undefined}><Icon name={n.section} /><span>{n.label}</span>{n.section === section && <span className="nav-active-dot" />}</Link>)}</nav><div className="sidebar-bottom"><div className="pilot-card"><Icon name="shield" /><strong>Lokale Entwicklung</strong><p>Paper Trading.<br />Echtgeld gesperrt.</p></div><div className="user-block"><span className="avatar">{session.displayName.slice(0, 1).toUpperCase()}</span><div><strong>{session.displayName}</strong><small>{session.tenantName}</small></div><form action="/api/auth/logout" method="post"><input name="csrf" type="hidden" value={session.csrf} /><button title="Cockpitsitzung beenden" aria-label="Abmelden" className="icon-button"><Icon name="exit" /></button></form></div></div></aside>
    <div className="main-column"><header className="topbar"><div className="breadcrumb">Cockpit <span>/</span> <strong>{navigation.find(n => n.section === section)?.label}</strong></div><div className="topbar-status"><span className={`connection ${connected ? "" : "disconnected"}`}><span className="status-dot" />{connected ? "API verbunden" : "API nicht verfügbar"}</span><span className="badge paper">PAPER MODUS</span><form className="mobile-logout" action="/api/auth/logout" method="post"><input name="csrf" type="hidden" value={session.csrf} /><button aria-label="Abmelden" className="icon-button"><Icon name="exit" /></button></form></div></header><main className="content"><div className="page-heading"><span className="eyebrow">DEIN INVESTALO COCKPIT</span><h1>{titles[section][0]}</h1><p>{titles[section][1]}</p></div>{children}<footer className="dashboard-footer"><span>Virtuelles Kapital · Echtgeldhandel gesperrt</span><span>Zeiten: Europe/Berlin</span></footer></main></div>
  </div>;
}
export async function DashboardPage({ section }: { section: Section }) {
  const session = await getSession();
  if (!session) return <Login />;
  let data: Overview | null = null;
  let datasets: Dataset[] | null = null;
  try {
    const candidate = await apiRequest<unknown>(session, "/v1/overview");
    data = parseOverview(candidate, session.tenantId);
  } catch (error) {
    data = null;
    if (error instanceof BackendError && [401, 403].includes(error.status)) return <Login expired />;
  }
  if (section === "backtest" && data) {
    try { datasets = parseDatasets(await apiRequest<unknown>(session, "/v1/datasets"), session.tenantId); }
    catch (error) {
      datasets = null;
      if (error instanceof BackendError && [401, 403].includes(error.status)) return <Login expired />;
    }
  }
  return <Shell session={session} section={section} connected={!!data}>
    {!data ? <section className="panel connection-error" role="status"><Icon name="shield" size={28} /><h2>Verbindung noch nicht bestätigt</h2><p>Die geschützte API ist aktuell nicht erreichbar. Konten und Ergebnisse werden erst nach einer bestätigten Antwort angezeigt.</p><Link href={navigation.find(n => n.section === section)!.href} className="button secondary">Erneut laden</Link></section> : <>
      {section === "overview" && <>
        <div className="overview-banner"><div><span className="eyebrow">DEIN ERSTER SCHRITT</span><h2>Nachweise statt Versprechen.</h2><p>BTC und ETH auf H4. Gold auf H1/M15. Erst Daten prüfen, dann mit virtuellem Kapital lernen.</p><Link href="/backtests" className="text-link">Zur Strategieforschung <Icon name="arrow" size={17} /></Link></div><div className="banner-icon" aria-hidden="true"><Icon name="globe" size={82} /></div></div>
        <div className="metric-grid"><article className="metric-card"><span className="metric-label">Zugeordnete Konten</span><strong>{data.accounts.length}</strong><small>Getrennt nach Konto & Währung</small></article><article className="metric-card"><span className="metric-label">Offene Positionen</span><strong>{data.positions.length}</strong><small>Simulierte Paperpositionen</small></article><article className="metric-card"><span className="metric-label">Forschungsaufträge</span><strong>{data.jobs.length}</strong><small>Tatsächlich gespeicherte Aufträge</small></article></div>
        <section className="panel"><div className="section-heading"><h2>Dein Portfolio</h2><Link href="/portfolio">Alle Konten <Icon name="arrow" size={16} /></Link></div><Accounts data={data} /></section>
        <div className="two-column"><section className="panel"><div className="section-heading"><h2>Letzte Entscheidungen</h2><Link href="/journal">Journal <Icon name="arrow" size={16} /></Link></div><Journal data={{ ...data, journal: data.journal.slice(0, 4) }} /></section><section className="panel"><div className="section-heading"><h2>Forschungsstand</h2><Link href="/backtests">Backtests <Icon name="arrow" size={16} /></Link></div><Jobs jobs={data.jobs.slice(0, 4)} /></section></div>
      </>}
      {section === "portfolio" && <><section className="panel"><div className="section-heading"><h2>Konten & virtuelles Kapital</h2><span className="badge paper">PAPER</span></div><Accounts data={data} /></section><section className="panel"><div className="section-heading"><h2>Offene Positionen</h2><span className="count">{data.positions.length}</span></div><Positions data={data} /></section><section className="panel"><div className="section-heading"><h2>Portfolioentwicklung</h2></div><Empty title="Noch keine bestätigte Equityzeitreihe" icon="backtest">Die grafische Entwicklung wird aus tatsächlichen protokollierten Kontoständen aufgebaut. Es werden keine Kurven erfunden.</Empty></section></>}
      {section === "journal" && <section className="panel"><div className="section-heading"><h2>Dein Tradingjournal</h2><span className="count">{data.journal.length} Ereignisse</span></div><Journal data={data} /></section>}
      {section === "backtest" && <><section className="panel"><div className="section-heading"><h2>Crypto Basket prüfen</h2><span className="badge neutral">BTC / ETH · SPOT · H4</span></div><p className="panel-intro">Fünf reguläre Stufen; die manuelle Reserve bleibt im Referenzbacktest als Cash. Nachträglich ausgewählte Käufe werden nicht als automatische Leistung gerechnet.</p><BacktestForm csrf={session.csrf} datasets={datasets} /></section><section className="panel"><div className="section-heading"><h2>Angeforderte Läufe</h2><Link href="/backtests">Stand aktualisieren <Icon name="arrow" size={16} /></Link></div><Jobs jobs={data.jobs} /></section><div className="research-note"><Icon name="shield" /><p><strong>Freigabe braucht unabhängige Nachweise.</strong> Positiver Nettoertrag, Profitfaktor ≥ 1,2 und mindestens 30 geschlossene Baskets je Cryptoasset im unabhängigen Holdout. Gold wird gesondert nach Kosten- und Kausalitätsprüfung freigegeben.</p></div></>}
      {section === "shield" && <><section className="panel"><div className="section-heading"><h2>Deine Cockpitsitzung</h2><span className="badge">MFA BESTÄTIGT</span></div><dl className="security-list"><div><dt>Nutzerkreis</dt><dd>Administrativ eingerichteter Privatpilot</dd></div><div><dt>Sitzung gültig bis</dt><dd>{date(new Date(session.expiresAt * 1000).toISOString())}</dd></div><div><dt>Echtgeldhandel</dt><dd>Gesperrt</dd></div><div><dt>Abmeldung</dt><dd>Beendet diese Cockpitsitzung. Die separate Authelia-Sitzung bleibt bestehen.</dd></div></dl></section><section className="panel"><div className="section-heading"><h2>Bestätigte Risikoprofile</h2></div><div className="risk-grid"><article><span className="eyebrow">CRYPTO PAPER</span><strong>6 % täglich / 8 % initial</strong><p>BTC/ETH Spot ohne Hebel. 500 USDT Kaufprincipal plus 5 USDT Kostenreserve je Basket.</p></article><article><span className="eyebrow">MT5 DEMO · FREIGABE AUSSTEHEND</span><strong>1 % täglich / 5 % initial</strong><p>0,25 % modelliertes Risiko je Idee. Maximal eine offene Idee auf getrenntem Brokerdemo.</p></article></div></section></>}
    </>}
  </Shell>;
}
