import type { DemoBTCTest, DemoBTCMarketTest } from "../lib/demo-btc-test-contract";
import { DemoStartupReport } from "./demo-startup";

const labels: Record<DemoBTCTest["unknown_wallet_fields"][number], string> = {
  account_equity: "Kontowert", available: "Freie Margin", locked: "Gesperrter Betrag",
  isolated_margin: "Isolierte Margin", crossed_margin: "Cross-Margin",
  unrealized_pnl: "Unrealisierter Gewinn / Verlust", coupon: "Coupons",
  grant: "Bonusguthaben", asset_mode: "Sicherheitenmodus",
};
export function DemoBTCTestReport({ data }: { data: DemoBTCTest | DemoBTCMarketTest }) {
  const p = data.preview;
  const money = (v: string) => `${new Intl.NumberFormat("de-DE",
    { maximumFractionDigits: 8 }).format(Number(v))} USDT`;
  return <div className="demo-btc-test-report">
    <h3>BTC-Demo-Testvorschau</h3>
    <p>Kleine technische Long-Testorder mit 2× Hebel und isolierter Margin.
      {p.order_type === "market" ? " Zielgröße etwa 20 USDT, mit 1 % Preispuffer bei der Mengenberechnung."
        : " Der Positionswert ist auf 20 USDT begrenzt."}</p>
    <p>Marktstand: {new Date(p.observed_ms).toLocaleString("de-DE", { timeZone: "Europe/Berlin" })}.
      {" "}Preise und Menge werden bei jeder neuen Vorschau erneut berechnet.</p>
    <dl>
      <dt>Menge</dt><dd>{p.quantity_btc} BTC</dd>
      <dt>{p.order_type === "market" ? "Aktueller Referenzpreis" : "Limitpreis"}</dt>
      <dd>{money(p.order_type === "market" ? p.reference_price_usdt : p.limit_price_usdt)}</dd>
      <dt>{p.order_type === "market" ? "Geschätzter Positionswert" : "Maximaler Positionswert"}</dt>
      <dd>{money(p.order_type === "market" ? p.estimated_notional_usdt : p.maximum_notional_usdt)}</dd>
      <dt>Geschätzte Eigenkapital-Margin vor Gebühren</dt>
      <dd>{money(p.order_type === "market" ? p.estimated_margin_usdt : p.initial_margin_estimate_usdt)}</dd>
    </dl>
    <p>{p.order_type === "market" ? "Market-Ausführung zum verfügbaren Marktpreis. Der tatsächliche Kurs und Positionswert können von der Schätzung abweichen."
      : "Ausführung: sofort vollständig oder teilweise zum Limitpreis oder günstiger; ein verbleibender Rest wird verworfen."}</p>
    <DemoStartupReport data={data.readiness} />
    {data.unknown_wallet_fields.length > 0 && <p>Von Bitget nicht bestätigte Kontofelder:
      {" "}{data.unknown_wallet_fields.map(f => labels[f]).join(", ")}.</p>}
    {(p.order_type === "market" ? p.native_max_market_quantity_btc === null : !p.maximum_quantity_verified)
      && <p>Die maximale Ordermenge wurde von Bitget nicht bestätigt.</p>}
    <p>Diese Vorschau sendet keinen Auftrag. {p.order_type === "market" ?
      "Für den einzelnen technischen Demotest wurden fehlendes Bonusguthaben, native Maximalmenge, tatsächliche Gebühren und ältere Auftragsabdeckung ausdrücklich akzeptiert. Der Testversand wird separat angeschlossen."
      : "Die tatsächlichen Gebühren und die vollständige Auftragsabdeckung müssen vor der gesonderten Orderfreigabe geklärt sein."}</p>
  </div>;
}
