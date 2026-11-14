import { buyReasons, buyStates, type FuturesAssets } from "../lib/futures-paper-assets-contracts";
import { FuturesAssetRefresh } from "./futures-asset-refresh";

function date(value: string | null) {
  return value ? new Intl.DateTimeFormat("de-DE", {
    dateStyle: "short", timeStyle: "medium", timeZone: "Europe/Berlin",
  }).format(new Date(value)) : "Noch kein Kerzenschluss";
}

export function FuturesAssetsPanel({ data }: { data: FuturesAssets | null }) {
  return <section className="panel" aria-label="Futures-Assets und Kaufbedingungen">
    <div className="section-heading"><h2>Handelsassets & nächste Käufe</h2><span className="badge paper">FUTURES · PAPER</span></div>
    <FuturesAssetRefresh />
    <p className="panel-intro">RSI14 aus abgeschlossenen H1-Kerzen. Der nächste Kauf hängt von RSI, Kurs und den
      Kapitalprüfungen ab. Ein zukünftiger Kaufzeitpunkt lässt sich nicht vorhersagen.</p>
    {!data ? <p role="status">Der aktuelle Futures-Paperstand ist derzeit nicht verfügbar.</p> :
      !data.accounts.length ? <p>Noch kein Futures-Paperkonto zugeordnet.</p> :
      data.accounts.map(account => <div key={account.account_id} className="futures-asset-account">
        <h3>{account.account_name}{account.snapshot && <span className="count">
          {account.snapshot.assets.filter(a => a.position !== null).length} offene Futuresbaskets</span>}</h3>
        {!account.snapshot ? <p>Der Futures-Paperzustand ist noch nicht angeschlossen.
          RSI und offene Positionen sind noch nicht verfügbar.</p> : <>
          <div className="futures-asset-times"><span>RSI-Kerzenschluss: {date(account.snapshot.indicator_at)}</span>
            <span>Quotes: {date(account.snapshot.observed_at)}</span>
            <span>Nächster H1-Signalcheck: {date(account.snapshot.next_signal_check)}</span></div>
          {!account.snapshot.data_fresh && <p className="notice" role="status">Datenstand veraltet oder noch im Aufbau.
            Die gespeicherten Werte gelten nicht als aktuelle Kaufprüfung.</p>}
          <div className="table-scroll"><table className="futures-asset-table">
            <caption className="sr-only">Ausgewählte Handelsassets, RSI, offene Baskets und Kaufgrenzen</caption>
            <thead><tr><th>Asset / letzter Bid</th><th>RSI14 · H1</th><th>Offener Basket</th><th>Nächster Kauf</th></tr></thead>
            <tbody>{account.snapshot.assets.map(asset => <tr key={asset.symbol}>
              <td><strong>{asset.symbol}</strong><small>{asset.reference_bid} USDT</small></td>
              <td><strong title={asset.rsi === null ? undefined : `Ungerundeter RSI: ${asset.rsi}`}>
                {asset.rsi === null ? "—" : Number(asset.rsi).toFixed(2)}</strong>
                {asset.rsi !== null && <div className="rsi-track" aria-hidden="true"><span
                  style={{ width: `${Number(asset.rsi)}%` }} /><i /></div>}
                <small>{asset.rsi_confirmations}/2 Schlüsse unter 30</small></td>
              <td>{asset.position ? <><strong>{asset.position.quantity} · {asset.position.leverage}×</strong>
                <small>Ø Einstieg {asset.position.average_entry} USDT</small>
                <small>{asset.position.regular_entries}/5 reguläre Käufe</small>
                <small>Letzter Kauf {asset.position.last_entry_price} USDT</small></> :
                <span>Kein offener Basket</span>}</td>
              <td><strong>{asset.next_buy.stage === 6 ? "Manuelle Stufe 6" : `Kaufstufe ${asset.next_buy.stage}`}</strong>
                <small>{asset.next_buy.maximum_fill_price === null ? "Erstkauf ohne feste Kursgrenze" :
                  `Ausführung höchstens ${asset.next_buy.maximum_fill_price} USDT`}</small>
                <small>{buyStates[asset.next_buy.status]}</small>
                {asset.position && asset.next_buy.stage < 6 &&
                  <small>RSI-Rearm über 30: {asset.rearmed ? "erfüllt" : "noch offen"}</small>}
                {asset.next_buy.reasons.map(reason => <small key={reason}>{buyReasons[reason]}</small>)}</td>
            </tr>)}</tbody>
          </table></div>
        </>}
      </div>)}
    <p className="panel-intro">Nachkaufgrenze: 95 % des letzten tatsächlichen Kaufpreises, am Preisraster
      abgerundet. Ask, Slippage, Funding und verfügbare Margin werden bei der Ausführung geprüft.
      Die sechste Stufe bleibt manuell.</p>
  </section>;
}
