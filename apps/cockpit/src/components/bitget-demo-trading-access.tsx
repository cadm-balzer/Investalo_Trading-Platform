import Link from "next/link";

export function BitgetDemoTradingSetupStatus() {
  return <>
    <p role="status">Die Eingabe echter Demo-Handelsschlüssel ist noch nicht freigeschaltet. Der geschützte Zugang wird vor der Freischaltung vollständig geprüft.</p>
    <ol className="panel-intro">
      <li>Verwende einen im Bitget-Demo-Modus erstellten API-Key mit Futures- und Spot-Handelsrechten.</li>
      <li>Richte einen <Link href="/security/passkeys">Passkey im Cockpit</Link> ein.</li>
      <li>Nach der Freischaltung hinterlegst du API-Key, Secret und Passphrase für dein zugeordnetes Demo-Konto und bestätigst die Einrichtung mit dem Passkey.</li>
    </ol>
    <p className="form-hint">Die Einrichtung speichert den Zugang verschlüsselt. Sie startet noch keinen automatischen Handel.</p>
  </>;
}
