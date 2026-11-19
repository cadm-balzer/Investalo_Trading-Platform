# Interne API für Demo-Handelskeys

Stand 2026-11-19, IP-009/IP-015, D-133. PR93/cb696f6 ist als3cb3fdc in
main gemerged; GitHub/Fetch/Ancestry geprüft. Die eigene API verbindet den
vertrauenswürdigen BFF mit dem Handelsledger019 und dessen sicherer
Metadatengrundlage018. Sie nimmt keine Broker-Keytriple an.

## Vertrag

| Route | Ergebnis |
|---|---|
| `GET /v1/bitget-demo-trading/credential-actions/{account_id}` | Eigene aktuelle Kontometadaten und gespeicherte Handelsrechte |
| `POST /v1/bitget-demo-trading/passkey-authorizations/prepare` | Eigene Authorization-ID, Challenge und eingefrorener Metadatenhash |
| `POST …/claim` | Einmaliger bestätigter Claim vor dem BFF-Verifikationsurteil |
| `POST …/finish` | Grant nach aktuellem Factor-CAS |
| `POST …/grant` | Erneut geprüfter, noch nicht bestätigter Grant |
| `POST …/authorize` | Dauerhafte Receipt nach ausdrücklichem Consent |

Zwei getrennte, standardmäßig falsche Einstellungen registrieren die
Routefamilien ausschließlich bei exakt aktivem Boolean:
`API_DEMO_TRADING_CREDENTIAL_METADATA=1` und
`API_DEMO_TRADING_PASSKEY_AUTHORIZATIONS=1`. Normal-/Demo-Leseflags
aktivieren keine Handelsroute. Ohne den eigenen Schalter antwortet die
jeweilige Route404 auch bei ungültigem Bearer oder Requestbody.
Diese Variablen wurden nicht in normale Compose-/Servicekonfigurationen
aufgenommen.

Requests verwenden die bestehende kurzlebige BFF-Assertion mit ursprünglicher
OIDC-Zeit und exakten Methoden-/Pfad-/Bodyhashbindungen. Die tatsächliche
Runtime-LOGIN-Transaktion prüft aktuellen Actor, Membership, Epoch, Reauth und
persistente Requestnonce. Passkeyzeit ersetzt die OIDC-Zeit nicht.
SQL019 prüft außerdem Proofsitzung, Konto, Faktorversion, Metadaten und Ablauf.
Freigaben gehören ausschließlich zu `demo_futures_spot_trading`,
`bitget-classic-demo-trading-secret/1` und
`passkey-demo-trading-credential-authorization/1`.

Die eigene Projektion enthält exakt acht Metadatenfelder:
Tenant, Epoch, Purpose, Profil, Environment, Account, Connection und
`key_authorities`. Ein fehlender Connectiondatensatz erfordert null-Rechte.
Ein vorhandener Datensatz erfordert die kanonisch sortierten, verschiedenen
coow/cpow/stow-Rechte mit optionalen neun bekannten Lesecodes gemäß018.
Andere Rechte, unbekannte/private Felder und Lese-/Normalprofile werden
verworfen. Widerrufene und pausierte Verbindungen behalten ihren tatsächlichen
Status, die Storageversion und Rechte. Gleiche Tenant-Peers erhalten keine
falsche freie Slotanzeige für fremde Verbindungen.
UID, Parent, Egress-IP, Provenienz, Envelope und Credentials werden nie
projiziert. Die Projektion bestätigt keine native Schlüsselherkunft.

Consent hält den aktuellen Grant und autorisiert ihn atomar in derselben
Transaktion. Fehlerhafte Projektion rollt Änderungen zurück. Ergebnisse
werden erst nach bestätigtem Commit und erneuter Prüfung von Ablauf und
ursprünglicher Transportassertion veröffentlicht. Ein unbekannter
Claim-/Consent-Commitack liefert statisches503 ohne Commandretry.
Tatsächlich committed Zustände bleiben einmalig verbraucht.
Register/Revoke sind die einzigen Aktionen; Keyrevision bleibt1.

Das Resultat enthält `execution_enabled=false`: Diese API signiert keinen
privaten Credential-Executortoken, schreibt keine Credentials und schickt
keinen Brokerrequest. Der eigene [Executor019](bitget-demo-trading-passkey.md)
übernimmt später die Speicherung. Alte Normal-/Demo-Lesecontroller,
Ledger und Metadatenprojektionen bleiben unverändert; geteilt werden
passive strikte Codecs und der ursprüngliche Faktor-/Sessionkern.

## Abnahme

107 neue gezielte Fälle bestanden: sichere Rechte-/Metadatenprojektion,
separate Defaults/Flags, Consent, aktuelle Rollen-/Epoch-/Reauth-/Faktor-/
Kontodrift, parallele Claims, ursprüngliche Requestbindung/Nonce,
Read/Trading-Crossdomain, Post-Commit-Ablauf und tatsächlich committed
Claim/Consent mit fehlender Bestätigung. Fehlerhafte öffentliche
Projektion wurde mit tatsächlichem Transaktionsrollback geprüft.
320 vorhandene Normal-/Demo-Lesefälle ebenfalls grün:
427 verschiedene gepinnte Fälle insgesamt.

Python3.14.10 mit unveränderten gehashten Dependencies. API-/Check-/
Migrationsimages gebaut; das echte Runtimeimage ohne Netzwerk, Secrets,
DB- oder Quelldateimounts importiert und seine Handelsrouten als
standardmäßig deaktiviert geprüft. Bestehende Starlette/httpx-Warnung
erfordert für diesen Checkpoint keine Dependencyänderung.

Die HTTP-Prüfungen verwenden den tatsächlichen ASGI/TestClient-Adapter und
Restricted-Runtime-PostgreSQL in `investalo_credentials_checks`.
Identitäten, strukturelle Ciphertexts, Brokerkeys und WebAuthn-Urteile
bleiben synthetisch; keine physische Browser-/native Bitget-Abnahme.
Keine neue Migration oder Schemaänderung; Fixture001–019 und tatsächliches
Entwicklungsset vor/nach unverändert geprüft. Normale laufende Dienste und
Frontend wurden nicht neu erstellt.

## Nächster Schritt

Die [eigene Handels-BFF-/Signing-/Browser-/private HTTP-Anbindung](bitget-demo-trading-dashboard.md)
ist inzwischen separat geprüft. Gemeinsame isolierte laufende Tradingabnahme
und operative private Identitäten vorbereiten. Anschließend Key-/UID-/Parent-/
IP-/Rechteprovenienz und native Account-/Order-/Kosten-/Latenz-/Quotaabnahme
prüfen. Öffentlicher Rollout benötigt seine eigene Freigabe.
Keine echten Keys, Brokerrequests, Orders, Backtests, Dependencies oder
Public-/Live-/AI-Freischaltungen.
