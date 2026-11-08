# Nutzergebundene Bitget-Anbindung

Stand 2026-11-08. Nutzerangabe: eigenes finanziertes Bitget-Konto mit Spot-
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

Lokaler Zwischenstand: `/security/credentials` zeigt nur zugeordnete
Kontometadaten und vorgesehene Aktionen. Die Schritte sind gesperrt, keine
Keyeingabe. Authelia-Reauth kann den alten zweiten Faktor erhalten; zusätzliche
Cockpit-Passkeys sind ausdrücklich bestätigt und befinden sich in Umsetzung.
[Schutzbefund und Integrationsgates](passkey-step-up.md).
IP-038 ergänzt einen isolierten [Credentialassertionvertrag](passkey-credential-assertions.md)
für eine spätere zweckgebundene Freigabe. Die vorhandene007-Nachweisbestätigung
erteilt diese nicht. IP-039 ergänzt008 mit eingefrorenem Zweck, ausdrücklicher
Autorisierung aus einem noch erteilten007-Grant, globalem Einmalverbrauch und
getrenntem finalen Lock. Geprüfte008 ist nur in der Fixture-DB angewendet;
die tatsächliche PostgreSQL-Lifecycleprüfung bestand. Geschützte Keyeingabe und
Browser-/Credentialexecutorintegration bleiben offen;004 und öffentliche Vorschau
unverändert. [Autorisierungsgrenze](passkey-credential-authorizations.md).
IP-040 ergänzt den privaten `PasskeyBitgetOnboarding` mit Consume vor Probe und
008-Lock/003-AEAD-Änderung/009-Abschlussaudit in derselben finalen Transaktion.
356 Credentialtests (221 tatsächliche PostgreSQL-Fälle),009-Preflight und
gepinnte Prüfbuilds bestanden;009 ist nur in der Fixture-DB angewendet.
Kein echter Nutzerkey oder Brokertransport angeschlossen.
[Privater Ausführungsablauf](passkey-credential-execution.md).

IP-041 ergänzt die private injizierte Cockpit-Orchestrierung mit eingefrorenem
Bodyhash und ausdrücklicher008-Zustimmung vor Signatur/privatem Executor.
Die interne008-Prepare-/Authorize-API bleibt ohne
`API_PASSKEY_CREDENTIAL_AUTHORIZATIONS=1` ausgeschaltet und verlangt einen
konfigurierten kanonischen HTTPS-Origin/RP. Kein Raw-Credentialbody geht an
diese API; die ursprüngliche OIDC-Zeit bleibt unverändert. Browser-Keyeingabe,
Executor-HTTP-Service, Betriebsidentität/-schlüssel und tatsächliche
Brokeranbindung sind weiterhin gesondert abzunehmen.
[Private Cockpit-Anbindung und Gates](passkey-credential-cockpit.md).

IP-042 ergänzt den injizierten lokalen HTTPS-Übergang zum Executor mit
gegenseitigem TLS, gepinntem BFF-Zertifikat und separat gebundenem
ursprünglichem Sitzungskontext. Nur synthetische Fixtureprüfungen;
ein Produktionslauncher oder echter Keyeingang wird nicht installiert.
[Transportgrenze](passkey-credential-https.md).

IP-043 prüft diesen Ablauf in einem eigenen synthetischen Credentialcontainer.
Startprüfung und Mountkontrolle trennen die gebundene Credentialrolle samt
eigenen Schlüsseldateien vom administrativen Fixturechecker. Echte Keytriples
werden vor008-Verbrauch abgewiesen; der Broker bleibt synthetisch.
[Dienst und Betriebsgrenzen](credential-development-service.md).

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

Der isolierte [Classic-Readadapter](../integrations/bitget/README.md) ist mit
24 Offline-Tests und unabhängigem Review geprüft. Eine reine Kontoinfoprobe
ermittelt die UID; Walletabfragen benötigen danach eine feste Nutzer-/Kontobindung
und erneute Rechte-/IP-Prüfung. Der Adapter prüft die erwartete ausgehende IP
in der gemeldeten Whitelist; die tatsächliche Server-IP und eine ausschließlich
auf Plattformadressen begrenzte Whitelist sind damit noch nicht nachgewiesen.
Cockpiteingabe, geschützter Schlüsselbetrieb und tatsächliche
Brokerprüfung folgen IP-009/IP-015. Es wurde kein echter Nutzerkey entgegengenommen
oder Konto verbunden. Fach- und Betriebsgates:
[Security](security.md), [Trading](trading.md), [Ticketboard](tasks/board.md).

Der getrennte [Credential-Envelopekern](../packages/credentials/README.md)
ist mit 20 echten AES-GCM-Tests geprüft. Er bindet verschlüsselte Daten an
Tenant, Nutzer, Plattformkonto, Verbindung, Broker-UID/Parent, Classic-Leseprofil
und Credentialrevision. KEK-Wechsel und lokale Wiederherstellung sind geprüft.
Der [Credentialstore](../services/credentials/README.md) ergänzt persistente
DB-Bindung und Autorisierung mit aktuellen Revisionen, CAS, Rotation und
terminalem Widerruf. Der private Einrichtungsablauf verbindet dies mit
Classic-Probe, genau einer konfigurierten Whitelist-IP und einmalig konsumierten,
body-/aktionsgebundenen Freigaben. Keywechsel darf UID/Parent nicht ändern.
Identität/Epoch, Konto, Zeit und Versionen werden nach der Probe erneut geprüft.
Verschlüsselte Speicherung und Abschlussaudit erfolgen in einer Transaktion.
Die Prüfungen verwenden erfundene Assertions/Keys/Brokerantworten gegen echte DB.
Eine Broker-UID ist global je Broker eindeutig, auch nach Widerruf; automatische
Übertragung oder Neueinrichtung derselben UID ist ausgeschlossen.
Physische BFF-MFA-Abnahme, Browseranbindung der zweckgebundenen Credentialfreigabe
und geschützte Cockpiteingabe, Betriebsschlüsselprovider,
tatsächliche Egress-/Brokerprüfung und gemeinsame UID-Quota müssen vor echter
Keyannahme integriert und abgenommen werden. Der Dateiprovider ist ausschließlich
für Entwicklung; es gibt keine freigeschaltete HTTP-Keyroute.

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
