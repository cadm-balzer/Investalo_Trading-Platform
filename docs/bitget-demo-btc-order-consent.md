# Konkrete Zustimmung zur kleinen BTC-Demo-Testorder

PR112 ist auf main `dc879b3` verifiziert. Der vorhandene
[dauerhafte Consumer](bitget-demo-order-consumer.md) erhält einen eigenen
BFF-/Python-Zustimmungsbaustein für den ersten technischen BTC-Test.
Dieser Baustein ist noch nicht in eine operative Next-/Executorroute eingebaut.

## Eigener Request und aktueller Actor

Die BFF-Funktion prüft den tatsächlichen POST auf den festen Submitpfad:
gleiche Origin, Same-site, JSON, Original-CSRF und Originalanmeldung.
Aktuelle Owner-/Traderrolle und aktive Demo-Keymetadaten müssen über einen
unabhängigen API-Adapter vor/nach den Asynchronstellen gelesen werden.
Sitzungs-Handle, Tenant, Subject, Epoch, OIDC-Anmeldezeit, Ablauf und CSRF
bleiben an die ursprüngliche Bestätigung gebunden. Bodies sind auf16KiB/
10s begrenzt, doppelte JSON-Felder abgelehnt, höchstens acht Vorgänge
werden vor dem ersten Await zugelassen.

Das private HMAC-Paket nutzt den eigenen Kind
`investalo-demo-btc-test-order-consent/1`, eigene Audience und festen
Executorpfad `/v1/bitget-demo-trading/order-submit`. Maximal15s Gültigkeit,
innerhalb der ursprünglichen Session. Der Body bindet Konto, Verbindung,
Key-/Speicherversion, Command, vollständigen Intentdigest, Outboxbeleg und
die ausdrückliche20-USDT-/2×-/isolierte-Long-Testbestätigung.
Paket/Context/Token sind ausschließlich für den privaten Executor bestimmt,
nicht für Browserantworten oder dauerhafte Speicherung.

Der Python-Verifier authentifiziert gegen den unabhängig gelieferten
Originalkontext. Er akzeptiert ausschließlich einen tatsächlichen
`DemoIntent`: BTCUSDT, initiale Menge null, neuer Long, feste Demo-/Classic-/
One-way-/2×-Bindung und exakter Positionswert höchstens20 USDT.
Menge, Preis und Raster bleiben im Intent fest gebunden.
Lese- und Key-Write-Tokens werden abgelehnt; der alte Reader lehnt auch
einen frischen neuen Ordertoken vor nativer IO ab.

Der Issuer prüft anschließend aktuelle Actor-/Installationsguards und zwei
unabhängige originale018-Trading-Snapshots. Bindung, Revision, Storage und
verschlüsselter Datensatz müssen unverändert zur Zustimmung passen.
Er öffnet keine Credentials. Der dauerhafte Consumer verbraucht die
bestätigte JTI mit fsync/readback vor AEAD und tatsächlichem Versand.

Dies ist eine eigene manuelle Bestätigung über die bestehende
MFA-geschützte Originalanmeldung. Kein neuer WebAuthn- oder ausgeführter
Passkeynachweis wird behauptet; die bisherigen verpflichtenden Passkey-
Abläufe zur Keyverwaltung bleiben unverändert.

## Validierung und verbleibende Installation

197 unterschiedliche gepinnte Pythonfälle und23 gepinnte Nodefälle grün.
Zwölf neue Python- und sieben neue Nodefälle decken eigene Domains,
Manipulation von Actor/Session/Body/Preis/Scope, Rollen-/Keywechsel, Ablauf
und tatsächlichen Consumer-/AEAD-/Outboxpfad ab. Vollständige Cockpit-
Typprüfung und gepinnter Executorbuild/paketierter Offlineimport grün.

Ein unverändertes tatsächliches Node-HMAC-Paket wurde vom Python-Issuer
geprüft, dauerhaft verbraucht und über echte AEAD/Outbox bis zum simulierten
Broker-ACK geführt. Sitzungen, Zustimmung, API-Actor und Brokerantworten
sind synthetisch: keine physische Browser-/MFA-/native Orderabnahme.

Kein Frontendneubau, operative Route, Dienstrestart, SQL-/Key-/Dependency-
Änderung oder Brokerauftrag. Originaler nativer Accountguard, registrierte
operative Outboxbasis und Handler-/Transportinstallation bleiben erforderlich.
Grant/native Maximalmenge fehlen weiterhin; Kosten und ältere Auftragsabdeckung
sind nicht bestätigt. Die neue Zustimmung hebt diese Prüfungen nicht auf.
Eine separat vorgeschlagene, begrenzte
[technische Testregel](bitget-demo-small-test-policy.md) steht zur Nutzerentscheidung.
