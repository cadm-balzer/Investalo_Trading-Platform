# Demo-Profil für Futures-/Spot-Handelskeys

2026-11-17, IP-009/IP-015. Nutzer bestätigt einen im Bitget-Demo-Modus
erstellten Key mit Read-Write für Futures und Spot. Das bestimmt den vorgesehenen
Profilumfang; es ersetzt keine native Keyprüfung.

## Implementierter Umfang

Der eigene Classic-V2-Identitätsparser benötigt `coow` (Futuresorders),
`cpow` (Futurespositionen) und `stow` (Spot-Handel). Zusätzlich sind die neun
schon bekannten Lesecodes zulässig. Auszahlungs-/Transfer-/Margin-/Copy-/
Subaccount-/Loan-/Tax-/P2P-Schreibrechte, unbekannte/fehlende/duplizierte Codes,
UTA-Felder und fehlerhafte UID/Parent/IP oder Providerantworten werden abgewiesen.
Der alte reine Leseparser akzeptiert Schreibrechte weiterhin nicht.

`DemoTradingOriginApproval` verwendet eigenes Schema/MAC-Domain, gebunden
an das vollständige Triple und ursprüngliche Actor-/Konto-/UID-/Parent-/IP-/
Rechtemetadaten. Die private Dateiprüfung übernimmt Originalpfad-/UID-/0700-/
0400-/Inode-/Hash-/PID-Guards. Der getrennte native Provisioner prüft vor/nach
genau einem festen signierten `GET /api/v2/spot/account/info` mit `paptrading: 1`
und vor dem Ergebnis erneut Originalfreigabe/Frist/nativen Zeitstand.
Rechte und eine einzige Whitelist-IP müssen exakt zur Originalfreigabe passen.

Der gemeinsame GET-Transport bezeichnet eine reine HTTP-Lesefähigkeit,
keine Erklärung, dass der native Key ausschließlich Leserechte besitzt.
Geschützte Klassenhooks wählen das Profil serverseitig. Der alte Provisioner
verlangt seine exakte Freigabeklasse und seinen alten Parser/Resulttyp;
kein Requestflag erweitert Rechte oder konvertiert Profile.

`DemoTradingSecretSpec` trägt `bitget-classic-demo-trading-secret/1` und
Purpose `demo_futures_spot_trading`. Beide AES-GCM-Schichten authentifizieren
Originalbinding, Rechte, Provenienz und Revision mit eigenen Trading-Domains.
Seal/Open/Rewrap haben eigene exakte Typgrenzen. Alte Lese- und neue
Handelsciphertexts sind auch mit gleichem KEK und sonst gleichem Binding
nicht austauschbar. `order_execution_enabled` bleibt `false`.

## Abnahme und nächste Anbindung

50 neue/160 gesamte gezielte Fälle und38 Unterfälle im gepinnten
Python3.14.10-Container bestanden. Tatsächliche private Dateien/AES-GCM/
Signaturbytes, synthetische Keys/HTTP-Replies. Konto/IP/Rechte-/Fristabweichungen,
Originalmutation, falscher MAC-Key, fehlgeschlagener Send ohne Retry und
gegenseitige Profil-/Ciphertextablehnung geprüft. Keine echte Keyaufnahme
oder native Bitget-Anfrage.

Herkunft bleibt Betreiberattestation, kein zertifizierter Demo-Erstellungsnachweis.
Instance-lokale PID-/Mutex-/1s-Guards lösen keine gemeinsame UID-Quota.
Die bisherigen SQL-/Passkey-/BFF-/Browser- und TTY-Pfade bleiben beim
alten Lese-Purpose; ein Handelskey wird dort nicht als Lesekey registriert.
Als Nächstes eigenen dauerhaften Purpose mit atomarer gemeinsamer UID-/
Kontobindung, Passkey-/Metadaten-/BFF-/Browserpfad und operativer Einrichtung
anbinden und tatsächlich abnehmen.

Keine Migration/Dependency/Dienst-/Frontendänderung oder öffentliche
Freischaltung. Keine Spot-/Futuresorders, Hebel-/Strategie-/Live-/AI-Änderung.

Offizielle Grundlage, am17.11. erneut geprüft:
[Classic-Identität und Rechtecodes](https://www.bitget.com/legacy-docs/classic/spot/account/Get-Account-Info),
[Demo-Keyerstellung und Header](https://www.bitget.com/docs/classic/demo-trading/rest-api).
