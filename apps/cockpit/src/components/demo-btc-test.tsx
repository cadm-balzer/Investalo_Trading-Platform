import type { DemoBTCTest } from "../lib/demo-btc-test-contract";
import { DemoStartupReport } from "./demo-startup";

const labels: Record<DemoBTCTest["unknown_wallet_fields"][number], string> = {
  account_equity: "Kontowert", available: "Freie Margin", locked: "Gesperrter Betrag",
  isolated_margin: "Isolierte Margin", crossed_margin: "Cross-Margin",
  unrealized_pnl: "Unrealisierter Gewinn / Verlust", coupon: "Coupons",
  grant: "Bonusguthaben", asset_mode: "Sicherheitenmodus",
};
export function DemoBTCTestReport({ data }: { data: DemoBTCTest }) {
  const p = data.preview;
  const money = (v: string) => `${new Intl.NumberFormat("de-DE",
    { maximumFractionDigits: 8 }).format(Number(v))} USDT`;
  return <div className="demo-btc-test-report">
    <h3>BTC-Demo-Testvorschau</h3>
    <p>Kleine technische Long-Testorder mit 2× Hebel und isolierter Margin.
      Der Positionswert ist auf 20 USDT begrenzt.</p>
    <p>Marktstand: {new Date(p.observed_ms).toLocaleString("de-DE", { timeZone: "Europe/Berlin" })}.
      {" "}Preise und Menge werden bei jeder neuen Vorschau erneut berechnet.</p>
    <dl>
      <dt>Menge</dt><dd>{p.quantity_btc} BTC</dd>
      <dt>Limitpreis</dt><dd>{money(p.limit_price_usdt)}</dd>
      <dt>Maximaler Positionswert</dt><dd>{money(p.maximum_notional_usdt)}</dd>
      <dt>Geschätzte Eigenkapital-Margin vor Gebühren</dt><dd>{money(p.initial_margin_estimate_usdt)}</dd>
    </dl>
    <p>Ausführung: sofort vollständig oder teilweise zum Limitpreis oder günstiger;
      ein verbleibender Rest wird verworfen.</p>
    <DemoStartupReport data={data.readiness} />
    {data.unknown_wallet_fields.length > 0 && <p>Von Bitget nicht bestätigte Kontofelder:
      {" "}{data.unknown_wallet_fields.map(f => labels[f]).join(", ")}.</p>}
    {!p.maximum_quantity_verified && <p>Die maximale Ordermenge wurde von Bitget nicht bestätigt.</p>}
    <p>Diese Vorschau sendet keinen Auftrag. Die tatsächlichen Gebühren und die vollständige
      Auftragsabdeckung müssen vor der gesonderten Orderfreigabe geklärt sein.</p>
  </div>;
}
