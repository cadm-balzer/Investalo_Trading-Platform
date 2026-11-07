# Nutzergebundene Bitget-Anbindung

Stand 2026-11-07. Nutzerangabe: eigenes finanziertes Bitget-Konto mit Spot-
und Futuresbeständen; **Classic mit getrennten Wallets** ist bestätigt.
Jeder Plattformnutzer erstellt einen eigenen dedizierten API-Key in seinem
Bitget-Konto. Die Plattform verwaltet dessen freigegebene Kontoverbindung.
Ein gemeinsamer Betreiberkey ist kein Ersatz für diese Nutzerbindung.

Der bestätigte M1-Start bleibt BTC/USDT und ETH/USDT Spot ohne Hebel auf H4,
zunächst Paper mit lesender Realkontoanbindung. Futuresbestände können separat
beobachtet werden; Futureshandel und Echtgeldaktivierung haben spätere eigene
Strategie-/Konto-/Risikofreigaben. Finanziertes Guthaben ist keine Livefreigabe.

## Einrichtung im Cockpit

Vorgesehener Ablauf, noch keine fertige Eingabemaske:

1. Eingeloggter Nutzer wählt „Bitget verbinden“, Kontonamen und Classic-Profil.
2. Die Plattform zeigt die geprüften festen **ausgehenden Server-IP-Adressen**
   und die für diesen Modus benötigten Keyrechte. Der Nutzer erstellt den
   dedizierten Key selbst in Bitgets APIverwaltung.
3. API-Key, Secret und Passphrase werden einmalig im geschützten Cockpit
   eingegeben. Frische MFA, CSRF und serverseitige Rollenprüfung sind erforderlich.
   Keine Übermittlung über Chat, E-Mail, URL oder lokale Browserpersistenz.
   Gemeint ist die API-Passphrase, nicht das Bitget-Loginpasswort.
4. Der Server prüft signierten lesenden Zugang, tatsächliche Bitget-UID,
   Parent-UID, Rechte und IP-Bindung. Er bindet die Verbindung an Tenant,
   Plattformnutzer, Brokerkonto, API-Familie und Umgebung.
5. Die Übersicht zeigt Verbindungsstatus, Datenalter und maskierte Referenz.
   Rohschlüssel werden nicht erneut ausgeliefert. Schlüsselwechsel prüft dieselbe
   Kontobindung; Widerruf sperrt neue brokergebundene Aufträge und informiert
   den Nutzer.

Die IP-Freigabe gilt für den tatsächlichen Brokerzugang des Servers, nicht für
die Cockpitdomain, eine Docker-IP oder die IP des Nutzerbrowsers.
Ein gültiger HTTPS-Proxyeinstieg allein beweist diese ausgehende Identität nicht.

## Rechte und Ausführungsgrenzen

| Modus | Schlüsselrechte und Plattformfunktion |
|---|---|
| M1 lesendes Realkonto | Ausschließlich bekannte Leserechte; Kontoinfo und getrennte Walletdaten |
| Paper | Lokale simulierte Orders; Realkontokey erhält dadurch keine Handelsrechte |
| Später freigegebener Spot-Livebetrieb | Nur konkret benötigte Handelsrechte, freigegebene Assets/Budgets und unabhängige Risk Gates |
| Futures | Eigene Strategie-/Margin-/Hebel-/Kontolimits und Implementierungsabnahme erforderlich |

Auszahlungen, interne Transfers, Kreditaufnahme, Subaccountverwaltung und
automatischer Kontomodwechsel gehören nicht zum vorgesehenen Keyumfang.
Die Plattform beantragt keine solchen Rechte, verschiebt kein Kapital zwischen
Wallets und migriert kein Konto nach UTA. Unbekannte oder überschießende
Rechte werden bei der lesenden Ersteinrichtung abgewiesen.

Classic meldet Rechte als `authorities`, nicht als UTAs `permType/permissions`.
Der Readadapter akzeptiert ausschließlich ausdrücklich dokumentierte Lesecodes.
Die zugelassenen HTTP-Pfade bilden eine zweite Grenze unabhängig von der
Provider-Rechtegranularität. Ein UI-Häkchen „Trade“ wird nicht pauschal als
technische Beschränkung auf ausschließlich Spot gewertet.

## Classic-API und Datenmodell

Private Zugriffe verwenden festes `https://api.bitget.com`, überprüftes TLS,
signierte Requests und begrenzte Zeit-/Antwortgrößen. Keine nutzerdefinierten
Broker-URLs oder Credentialweitergabe bei Redirects.

| Lesepfad | Verwendung |
|---|---|
| `GET /api/v2/spot/account/info` | UID, Parent-UID, Rechte und IP-Whitelist |
| `GET /api/v2/spot/account/assets` | Spotbestand pro Coin, verfügbar/gefroren/gesperrt |
| `GET /api/v2/mix/account/accounts` | Futureskonten je ausdrücklich gewähltem Produkttyp |

Spot und Futures sind getrennte Walletbereiche derselben Brokeridentität.
Spotverfügbarkeit, reservierte Strategiequote, Futures-Equity, Margin und
unrealisierter PnL bleiben unterschiedliche Größen. Futures-PnL ist in
gemeldeter Equity gegebenenfalls bereits enthalten und wird nicht nochmals
addiert. Werte verschiedener Coins erhalten eine dokumentierte Bewertung,
bevor eine Gesamtportfoliosicht entsteht. Fehlende Daten bleiben unbekannt.
Kein Gesamtbestand wird automatisch zum Spot-Handelsbudget.

Mehrere API-Keys derselben Bitget-UID erzeugen kein weiteres Kapital und keinen
zweiten unabhängigen Writer. UID-/Parent-/Umgebungsmismatch oder unbekannter
Modus sperrt die betroffene Verbindung. Der Classic-Accountinfoendpoint liefert
keinen universellen Accountmodebeweis: erklärte API-Familie und geprüfte
Responseform sind zu dokumentieren; kein automatisches UTA-Fallback.

## Credentialschutz und Umsetzung

Vor echter Keyannahme: authentifizierte Übertragung, serverseitige AEAD-
Verschlüsselung mit Tenant-/Kontobindung, Schlüsselversion, begrenzte
Entschlüsselungsidentität und geprüfte Rotation/Restore. Ciphertext und
Schlüsselzugriff bleiben getrennte Sicherheitsgrenzen; Hostkompromittierung
wird durch eine Datei auf derselben VM nicht ausgeschlossen.

Research, AI, öffentliche Marktdatenprozesse und normale Cockpitantworten erhalten
keine Brokercredentials. BFF/API redigieren Eingaben, Header, Exceptions und
Traces; sensible Werte gehören nicht in Git oder Logs. Konto-/Credentialänderung
und spätere Handelsaktivierung werden ohne Rohwerte auditiert.

Ein isolierter Classic-Readadapter wird zuerst mit erfundenen Fixtures geprüft.
Geschützte Speicherung, Cockpiteingabe und tatsächliche Brokerprüfung folgen
IP-009/IP-015. Es wurde kein echter Nutzerkey entgegengenommen oder Konto
verbunden. Fach- und Betriebsgates:
[Security](security.md), [Trading](trading.md), [Ticketboard](tasks/board.md).

## Offizielle Grundlagen

Am 2026-11-07 geprüft:

- [Classic REST: Keybestandteile, Rechte, Signatur und IP-Bindung](https://www.bitget.com/docs/classic/rest-api)
- [Classic-Accountinfo und Rechtecodes](https://www.bitget.com/legacy-docs/classic/spot/account/Get-Account-Info)
- [Classic-Spotassets](https://www.bitget.com/legacy-docs/classic/spot/account/Get-Account-Assets)
- [Classic-Futureskonten](https://www.bitget.com/docs/catalog/classic-contract-account/classic-contract-account)
- [Classic/UTA-Endpointvergleich](https://www.bitget.com/docs/classic/uta-api-upgrade-guide)
- [Classic-Wartungsstand und UTA-Empfehlung](https://www.bitget.com/docs/classic/Introduction)

Die vollständigen Classic-Spotdetails sind aktuell teilweise nur in offiziellen
`legacy-docs` abrufbar. Redirects alter Dokumentationslinks können stattdessen
UTA beschreiben. Änderungen und tatsächliche Kontoantworten vor Integration
abgleichen; weder Modus noch produktspezifische Rechte allein aus einem alten
Link ableiten.
Bitget empfiehlt inzwischen UTA und nennt Classic einen Wartungsmodus.
Der bestätigte Classic-Start erhält daher gezielte Endpoint-/Changelogprüfungen;
eine Migration mit geänderten Marginpools benötigt eine eigene Entscheidung.
