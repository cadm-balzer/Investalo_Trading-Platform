import Link from "next/link";

/** Public setup information; never grants access to the private intake. */
export function BitgetDemoSetupStatus() {
  return <>
    <p role="status">Die Eingabe echter Demo-Schlüssel ist noch nicht freigeschaltet. Die geschützte Kontoanbindung muss zuerst eingerichtet werden.</p>
    <ol className="panel-intro">
      <li>Erstelle den API-Key ausdrücklich im Bitget-Demo-Modus.</li>
      <li>Richte einen <Link href="/security/passkeys">Passkey im Cockpit</Link> ein. Er bestätigt später die Einrichtung des Zugangs.</li>
      <li>Nach der Freischaltung hinterlegst du hier API-Key, Secret und Passphrase für dein zugeordnetes Demo-Konto.</li>
    </ol>
    <p className="form-hint">Der erste Verbindungstest unterstützt Demo-Keys mit reinen Leserechten. Die Anbindung für Demo-Handelsrechte folgt separat. Schlüssel werden erst über die freigeschaltete Eingabe entgegengenommen.</p>
  </>;
}

export function BitgetDemoAccessPanel() {
  return <section className="panel">
    <div className="section-heading"><h2>Bitget-Demo-Zugang</h2><span className="badge neutral">EINRICHTUNG AUSSTEHEND</span></div>
    <p className="panel-intro">Hier erhält dein Bitget-Demo-Konto einen eigenen Zugang. Die Demo-Einrichtung hat einen separaten Bereich mit ihrem aktuellen Freischaltungsstatus.</p>
    <Link href="/security/credentials/demo-trading" className="button primary">Demo-Handelskey für Futures/Spot einrichten</Link>
    <Link href="/security/credentials/demo" className="button primary">Demo-Zugang einrichten</Link>
  </section>;
}
