import { Brand, Icon } from "./icons";

export function Login({ expired = false }: { expired?: boolean }) {
  return <main className="login-page">
    <header className="login-header"><Brand /><span className="pilot-label">COCKPIT / LOKALE ENTWICKLUNG</span></header>
    <div className="login-grid">
      <section className="login-story">
        <div className="eyebrow"><span className="status-dot" /> YOUR MONEY. YOUR RESPONSIBILITY.</div>
        <h1>Dein Kapital.<br />Deine Richtung.<br /><span>Dein Cockpit.</span></h1>
        <p className="login-lead">Ein klarer Blick auf dein Portfolio. Nachvollziehbare Entscheidungen. Strategien, die sich zuerst beweisen.</p>
        <div className="login-features">
          <div><Icon name="portfolio" /><span>Portfolio & Journal</span></div>
          <div><Icon name="backtest" /><span>Backtests & Paper Trading</span></div>
          <div><Icon name="shield" /><span>Unabhängige Risikogrenzen</span></div>
        </div>
        <div className="orbit" aria-hidden="true"><span /><span /><span /><div className="orbit-core"><Icon name="globe" size={50} /></div><b className="orbit-point" /></div>
      </section>
      <section className="login-panel" aria-labelledby="login-title">
        <div className="lock-symbol"><Icon name="shield" size={30} /></div>
        <span className="eyebrow">DEIN GESCHÜTZTER BEREICH</span>
        <h2 id="login-title">{expired ? "Sitzung erneut bestätigen" : "Willkommen im Cockpit"}</h2>
        <p>{expired ? "Deine Sitzung oder Mitgliedschaft ist nicht mehr bestätigt. Melde dich erneut mit MFA an." : "Melde dich mit deinem administrativ eingerichteten Konto und einem zweiten Faktor an."}</p>
        <a href="/api/auth/login" className="button primary login-button">Mit MFA anmelden <Icon name="arrow" /></a>
        <div className="login-note"><span className="status-dot" /><span>Nur für eingeladene Nutzer. Keine öffentliche Registrierung.</span></div>
        <div className="paper-callout"><strong>Paper zuerst.</strong><p>Virtuelles Kapital und simulierte Ausführung. Echtgeldhandel bleibt gesperrt.</p></div>
      </section>
    </div>
    <footer className="login-footer"><span>Investalo · Klarheit. Kontrolle. Verantwortung.</span><span>MFA geschützt · Privater Nutzerkreis</span></footer>
  </main>;
}
