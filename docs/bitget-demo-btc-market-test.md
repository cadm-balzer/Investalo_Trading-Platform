# Kleiner BTC-Demotest mit Market

PR113/mainac1246b ist verifiziert. Der Nutzer genehmigt den begrenzten
technischen Demotest mit den bekannten fehlenden Brokerangaben und wählt
Market statt Limit-IOC. Die bisherige Limit-Ausführung darf weder den
Marketversand noch dessen tatsächliche Fills als Limit behandeln.

Der eigene `BTCMarketIntent` verwendet BTCUSDT, isoliert, One-way und2×.
Menge und Referenzpreis sind gebunden; ein1%-Preispuffer und Abrunden auf
das native Mengenraster halten den geplanten Wert unter20 USDT.
Der Referenzpreis wird nicht an Bitget gesendet. Das exakte Market-POST
enthält `orderType=market`, ohne `price` und `force`. Die native Market-
Höchstmenge wird aus `maxMarketOrderQty` gelesen und bleibt bei fehlenden
Angaben unbekannt; weder die Limit-Höchstmenge noch ein erfundener Maximalwert
ersetzen sie. Nicht passende native Mindestmengen werden nicht aufgerundet.
Der angezeigte Vorschlag kann30s bestätigt werden; die signierte
Zustimmung bleibt15s gültig. Ein angezeigter Referenzpreis gilt niemals
als aktuelle native Quelle. Vor POST verlangt der separate Accountguard
weiterhin Quellen höchstens5s alt und prüft die feste Menge am frischen Ask.

Die neue signierte BFF-/Python-Consentdomain bindet dieselbe Original-
HTTPbestätigung, CSRF, Sitzung, aktuelle Rolle, Metadaten, exakten Intent
und Outboxbeleg wie der bestehende Vertrag. Limit-, Read- und Key-Tokens
berechtigen nicht zum Markettest. Native aktuelle Konto-/Credentialguards
und der dauerhafte Consumer bleiben erforderlich. Die eigene reine
Admissionprüfung verlangt die bestätigte10k/flat-Basis, alle fünf
vollständigen leeren Pendingfamilien, passende BTC-Einstellungen und
Quellen höchstens5s alt; sie ersetzt weder die Quelle noch eine Freigabe.
Nur die ausdrücklich genehmigten fehlenden Angaben werden akzeptiert.

Die dauerhaft geprüfte Outbox kodiert die neue Intentversion getrennt und
erhält fehlende Market-Maximalmengen beim Restore. Vor POST wird der Ausgang
dauerhaft `submission_unknown`. Ohne bestätigten Ausgang wird nie erneut
gesendet. ACK ist kein Fill. Tatsächliche Ausführung kann über dem
Referenzpreis und20-USDT-Schätzwert liegen; dieses Ergebnis wird erhalten.
Teilfills, Reststorno, unbekannte Gebühren und Positionsabgleich verwenden
die tatsächlich bestätigte Menge. Alte Limit-Verträge bleiben unverändert.
Reduce-only-Marketpayloads sind unterstützt; der neue Consentissuer
erteilt ausschließlich den Long-Test aus einer leeren Position.

Dashboard/Portfolio fordert nun die eigene `btc-market`-Vorschau über
Originalsitzung/Metadaten/mTLS/Trading-AEAD an. Die11 festen GETs, maximal3
Worker,110ms-Startabstände und5s-Kohorte bleiben erhalten. Parser und UI
zeigen Referenzpreis, geschätzten Positionswert/Margin und Marketpreis-
Unsicherheit. Alter Limit-Lesepfad und seine Tests bleiben erhalten.
Vorschau, readiness report und Admissionrückgabe geben keine Orderautorität.

Abnahme2026-11-23:

- 215 gepinnte Pythonfälle grün: neue Marketcontracts, tatsächliches
  Journal/Registry/Restore und Consumer→AEAD→Versand mit synthetischen
  Native-Replies, getrennte Domains, echte mTLS-Fixtures und alte Regressionen.
- 27 gepinnte Nodefälle und volle Cockpit-Typprüfung grün. Marketlesen
  verwendet tatsächliches lokales mTLS; Sitzung/CSRF/Metadaten und
  Market-/Limittrennung sind geprüft. Actor und Broker sind synthetisch.
- Gepinnte Executor- und Cockpitbuilds erfolgreich. Der einzelne
  Frontendbuild verwendet512MiB Node-Heap und einen Next-Worker; keine
  zusätzliche Buildparallelität. Öffentliche native Demo-Marktprobe:
  0,0003 BTC, Referenz61.287,1 USDT, Schätzwert18,38613 USDT,
  Initialmargin9,193065 USDT, Planungswert18,5699913 USDT;
  native Market-Höchstmenge weiter unbekannt. Genau zwei öffentliche
  GETs ohne Keys, keine private Brokerabnahme daraus abgeleitet.
- Unverändertes tatsächliches gepinntes Node-Market-Paket wird vom
  Pythonissuer angenommen und durch dauerhaften Consumer, tatsächliches
  AEAD/Outboxjournal und synthetischen Broker-ACK verarbeitet.

Operativer Issuer-/Accountquellenadapter, ursprüngliche private Registry/
Consumerinstallation und tatsächliche Send-/Statusroute bleiben der nächste
Schritt. Dieser Checkpoint installiert keine Orderroute, ändert keine
laufenden Dienste, Credentials, Migrationen oder Abhängigkeiten und
sendet keinen Auftrag. Er aktiviert keine Baskets oder Echtgeld.

Primärquellen, geprüft2026-11-23:

- [Bitget Classic Order API](https://www.bitget.com/docs/catalog/classic-contract-trade/classic-contract-trade):
  Market/Limit, Preis und Gültigkeit nur bei Limit, One-way und Reduce-only.
- [Bitget Classic Market API](https://www.bitget.com/docs/catalog/classic-contract-market/classic-contract-market):
  `maxMarketOrderQty` und `maxOrderQty` sind getrennte native Größen.
- [Bitget Demo REST](https://www.bitget.com/docs/classic/demo-trading/rest-api):
  virtuelle Mittel, Demo-Key und `paptrading:1`.
