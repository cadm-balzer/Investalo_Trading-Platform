import type { BacktestResult, ResultSummary } from "@/lib/backtest-contracts";
import { decimal } from "@/lib/backtest-contracts";
import { equityGeometry } from "@/lib/equity-curve";
import { Icon } from "./icons";

const number = (value: number, decimals = 2) => new Intl.NumberFormat("de-DE", { maximumFractionDigits: decimals, minimumFractionDigits: decimals }).format(value);
const time = (value: string) => new Intl.DateTimeFormat("de-DE", { dateStyle: "medium", timeZone: "Europe/Berlin" }).format(new Date(value));
const timestamp = (value: string) => new Intl.DateTimeFormat("de-DE", { dateStyle: "medium", timeStyle: "short", timeZone: "Europe/Berlin" }).format(new Date(value));
export function ResultMetrics({ result, compact = false }: { result: ResultSummary; compact?: boolean }) {
  return <div className={`result-metrics ${compact ? "compact" : ""}`}>
    <div><span>Netto-PnL</span><strong>{number(decimal(result.net_pnl))} <small>USDT</small></strong></div>
    <div><span>Max. Drawdown</span><strong>{number(decimal(result.maximum_drawdown_fraction, 0, 1) * 100)} <small>%</small></strong></div>
    <div><span>Profitfaktor</span><strong>{result.profit_factor === null ? "Nicht bestimmbar" : number(decimal(result.profit_factor, 0, 1e9))}</strong></div>
    <div><span>Geschlossene Baskets</span><strong>{result.closed_basket_count}</strong></div>
  </div>;
}
export function ValidationNotice({ result }: { result: ResultSummary }) {
  return <div className={`research-note ${result.synthetic ? "synthetic-notice" : ""}`} role="note"><Icon name="shield" /><div><strong>{result.synthetic ? "SYNTHETISCHE DATEN · NUR FUNKTIONSTEST" : "NICHT VALIDIERT · KEINE HANDELSFREIGABE"}</strong><p>{result.synthetic ? "Die Kerzen wurden künstlich erzeugt. PnL, Profitfaktor und Kurve sind kein Beleg für Handelsleistung." : result.source.venue === "csv" ? "CSV-Herkunft nicht unabhängig verifiziert. Dieses Ergebnis ist ein Forschungsstand und keine geprüfte Marktleistung." : "Historische Simulation nach modellierten Kosten. Dieses Ergebnis ist ein Forschungsstand und keine geprüfte Marktleistung."} Unabhängiger Holdout und Freigabe stehen aus. Vergangene Ergebnisse garantieren keine künftigen Gewinne.</p></div></div>;
}
export function EquityCurve({ result }: { result: BacktestResult }) {
  const geometry = equityGeometry(result.equity_curve);
  return <figure className="equity-figure">
    <svg className="equity-chart" viewBox="0 0 760 310" role="img" aria-label={`Equityverlauf aus ${result.equity_curve.length} tatsächlichen Simulationspunkten. Start ${number(geometry.first)} USDT, Ende ${number(geometry.last)} USDT.`}>
      <title>Simulierte Equity · {result.symbol} · USDT</title>
      <desc>Netto nach modellierten Gebühren, Spread und Slippage. Keine unabhängige Holdout-Validierung.</desc>
      {[40, 150, 260].map((y, index) => <g key={y}><line x1="70" y1={y} x2="720" y2={y} className="chart-grid" /><text x="62" y={y + 4} textAnchor="end" className="chart-axis">{number(geometry.maximum - index / 2 * (geometry.maximum - geometry.minimum), 0)}</text></g>)}
      <polyline points={geometry.points} className={`chart-line ${geometry.last < geometry.first ? "loss" : ""}`} />
      {result.equity_curve.length === 1 && <circle cx={geometry.points.split(",")[0]} cy={geometry.points.split(",")[1]} r="4" fill="currentColor" />}
      <text x="70" y="290" className="chart-axis">{time(result.equity_curve[0].at)}</text>
      <text x="720" y="290" textAnchor="end" className="chart-axis">{time(result.equity_curve[result.equity_curve.length - 1].at)}</text>
    </svg>
    <figcaption>{result.equity_curve.length} angezeigte Punkte{result.equity_curve_sampled ? " · Kurve für die Anzeige ausgedünnt; Kennzahlen aus der vollständigen Zeitreihe" : " · vollständige Simulationskurve"}. Y-Achse: USDT; Skala passt sich den tatsächlichen Werten an.</figcaption>
  </figure>;
}
export function Provenance({ result }: { result: BacktestResult }) {
  const costs = result.cost_assumptions;
  const coverage = result.coverage;
  return <>
    <section className="panel"><div className="section-heading"><h2>Zeitfenster & Datenabdeckung</h2><span className={`badge ${coverage.complete === false ? "warning" : "neutral"}`}>{coverage.complete === null ? "UNGEPRÜFT" : coverage.complete ? "ANGEFORDERTES FENSTER VOLLSTÄNDIG" : "HISTORIE UNVOLLSTÄNDIG"}</span></div><dl className="provenance-list">
      <div><dt>Angefordert</dt><dd>{coverage.requested_start && coverage.requested_end ? `${timestamp(coverage.requested_start)} – ${timestamp(coverage.requested_end)}` : "Kein angefordertes Zeitfenster dokumentiert; Vollständigkeit nicht geprüft."}</dd></div>
      <div><dt>Tatsächlich verfügbar</dt><dd>{timestamp(coverage.actual_start)} – {timestamp(coverage.actual_end)} · {result.bar_count} H4-Kerzen</dd></div>
      <div><dt>Fehlende H4-Kerzen</dt><dd>{coverage.missing_leading_bars === null ? "Nicht geprüft" : `Am Anfang: ${coverage.missing_leading_bars} · Am Ende: ${coverage.missing_trailing_bars}`}</dd></div>
    </dl><p className="form-hint">„Vollständig“ gilt ausschließlich für das angeforderte Zeitfenster. Ein 90-Tage-Probelauf erfüllt weder das Drei-Jahres-Rechercheziel noch den unabhängigen Holdout-Nachweis.</p></section>
    <section className="panel"><div className="section-heading"><h2>Datenherkunft & reproduzierbare Versionen</h2><span className="badge neutral">{result.synthetic ? "SYNTHETISCH" : result.source.venue === "csv" ? "CSV · UNVERIFIZIERT" : "BITGET SNAPSHOT"}</span></div><dl className="provenance-list">
      <div><dt>Quelle</dt><dd>{result.source.venue === "bitget" ? "Bitget · öffentliche historische Kerzen" : result.synthetic ? "Künstlich erzeugte Fixture" : "CSV-Import · unverifizierte Herkunft"} · API {result.source.api_version}{result.source.url && <span className="source-endpoint">{result.source.url}</span>}</dd></div>
      <div><dt>Abgerufen</dt><dd>{timestamp(result.source.retrieved_at)}</dd></div>
      <div><dt>Zeitraum</dt><dd>{timestamp(result.start)} – {timestamp(result.end)} · {result.bar_count} geschlossene H4-Kerzen</dd></div>
      <div><dt>Strategieversion</dt><dd><code>{result.strategy_version}</code></dd></div>
      <div><dt>Snapshot · SHA256</dt><dd><code>{result.data_digest}</code></dd></div>
      <div><dt>Simulationsdaten · SHA256</dt><dd><code>{result.simulation_data_digest}</code></dd></div>
      <div><dt>Konfiguration · SHA256</dt><dd><code>{result.configuration_digest}</code></dd></div>
      <div><dt>Kostenmodell · SHA256</dt><dd><code>{result.cost_digest}</code></dd></div>
    </dl></section>
    <section className="panel"><div className="section-heading"><h2>Eingefrorene Kosten- und Kapitalannahmen</h2></div><dl className="provenance-list">
      <div><dt>Gebührenrate</dt><dd>{number(decimal(costs.fee_rate, 0, 1) * 100, 4)} %</dd></div>
      <div><dt>Spread / Slippage</dt><dd>{number(decimal(costs.spread_fraction, 0, 1) * 100, 4)} % / {number(decimal(costs.slippage_fraction, 0, 1) * 100, 4)} %</dd></div>
      <div><dt>Virtuelles Startkapital</dt><dd>{number(decimal(costs.initial_equity, 0))} USDT</dd></div>
      <div><dt>Basket-Principal / Kostenreserve</dt><dd>{number(decimal(costs.basket_principal, 0))} / {number(decimal(costs.basket_cost_reserve, 0))} USDT</dd></div>
    </dl><p className="form-hint">Kennzahlen gelten für diese modellierten Annahmen. Offene Positionen werden zum letzten modellierten verkaufbaren Bid bewertet; kein erzwungener Verkauf am Datenende. Der Profitfaktor basiert auf geschlossenen Baskets. Die manuelle Reserve bleibt Cash; kein rückwirkend gewählter Reservekauf wird als automatische Leistung gerechnet.</p></section>
  </>;
}
