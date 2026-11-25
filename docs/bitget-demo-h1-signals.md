# H1-RSI-Anzeige und tatsächlicher Startstatus

## Antwortkorrektur am 25.11.2026

PR130/main`7121439` ist gemergt. Der automatische H1-Handelsworker ist
[operativ aktiv](bitget-demo-h1-worker.md) und verarbeitet die abgeschlossenen
Stunden unabhängig vom separaten Dashboard-RSI-Abruf. Tatsächlicher
Workerstatus25.11.2026 20:39UTC: `running / waiting_for_h1_signal`,
Ausführung freigegeben, Journalrevision44.

Der ursprüngliche `account_read`-Ergebnisrouter erkannte Wallet-, Startup-
und BTC-Testformate, aber keinen `investalo-demo-signals/1`-Bericht.
Der gültige Signalbericht fiel dadurch in die Walletprüfung und wurde
zu503. Eine tatsächliche öffentliche Probe im laufenden Executor lieferte
alle sieben Coins bestätigt; die neue lokale ASGI/mTLS-Regression reproduziert
vor dem Fix genau503. Bisherige Quell-, BFF- und Launcher-Tests hatten diese
abschließende Antwortgrenze nicht abgedeckt.

`demo_signal_view.py` prüft ausschließlich den vorhandenen öffentlichen
Signalvertrag: exakte Felder und sieben geordnete Symbole, kanonische
Kontobindung, UTC-/H1-Zeitbezug, unbekannte Werte als null und vollständige
abgeschlossene Kerzen. RSI-Grenzen und Bestätigungszählung verwenden die
unveränderten Decimalwerte. Wilder liefert36-stellige Präzision; die strengere
Skalengrenze für native Kontobeträge darf diesen berechneten RSI nicht
ablehnen. Read-/Order-/Walletverträge und Browsercode bleiben unverändert.

121 gepinnte Pythonfälle inklusive neuer echter lokaler ASGI/mTLS-Abdeckung
für beide installierbaren Read-/Market-Anwendungen,30 bestehende Nodefälle
und der finale Executorbuild sind grün. Eine tatsächliche schlüssellose
Bitget-Probe aus dem finalen Image liefert sieben bestätigte Berichte,
die sowohl die neue Pythonprüfung als auch den unveränderten gepinnten
TypeScript-Parser passieren. Ausschließlich die Kontobindung dieser reinen
öffentlichen Interopprobe ist synthetisch; keine Kontositzung wird erfunden.

Notwendiger Executor-only-Rollout abgeschlossen. Die sieben anderen
Dienste/Images einschließlich laufendem Handelsworker und Cockpit bleiben
gleich; ursprüngliche private Dateien, Freigabe, Key active1/1 und technisches
Journal8 erhalten. Der laufende Strategie-Journalpräfix bleibt erhalten;
normale neue Workerbuchungen laufen weiter. TLS200, Signals/Account anonym401
und tatsächliches privates mTLS405 bestätigt.
Private Image-/Before-/Aktivbelege liegen unter
`infra/local/demo-h1-signals/response-fix-*`.
Der originale Dashboard-RSI-Abruf nach dem Fix bleibt als Browserabnahme offen.
Ein RSI-Bericht selbst erteilt weiterhin keine Orderfreigabe.

## Ursprüngliche Implementierung und Abnahme

Stand: 24.11.2026. PR120/main `97241f9` verifiziert. Der Nutzer möchte
automatischen Demohandel mit Startfreigabe im Dashboard und aktuelle
RSI-Werte. Die ursprüngliche operative Basketfreigabe bleibt noch in Arbeit;
der bisherige kleine BTC-Roundtrip ist abgeschlossen.

Die eigene Anzeige unter „Bitget Futures-Konto“ zeigt die sieben bisherigen
Kandidaten AVAX, BNB, BTC, ETH, LINK, SOL und XRP. Werte stammen aus dem
[öffentlichen Classic-Futures-Kerzenabruf](https://www.bitget.com/docs/catalog/classic-contract-market/classic-contract-market)
mit `paptrading: 1`, USDT-FUTURES und H1. Es werden keine Brokercredentials
für die Kerzenabfrage entschlüsselt oder an einen Marktdatenanbieter gegeben.

300 lückenlose abgeschlossene H1-Kerzen wärmen dieselbe Decimal-/Wilder-
Berechnung `advance`/`IndicatorParameters` wie im Strategiekern auf. Die
laufende Kerze wird ausgeschlossen; Duplikate, Preisfehler, fehlende letzte
Stunde oder Lücken bleiben unbestätigt. Die Anzeige verwendet einen
rollierenden 300-Kerzen-Start, keinen vermeintlichen bestätigten
Basketjournalzustand. Ein späterer operativer Worker muss seine eigene
persistente Indikatorhistorie wiederherstellen.

Die Tabelle zeigt RSI, Vorwert, Abstand zu 30 in RSI-Punkten, H1-Schlusskurs,
Kerzenschlusszeit, tatsächlichen Abrufzeitpunkt und Erstkaufzählung 0–2.
Die Grenze `<30` wird vor der Anzeigerundung verglichen, auch im
Browserparser. Ein RSI nahe 30 ist keine Kaufzeitprognose. Bei bestehenden
Positionen werden keine Nachkaufstufe oder 95-%-Grenze aus dem
Durchschnittseinstand erfunden; der letzte tatsächliche Einzelkauf und
RSI-Rearm benötigen das eigene Basketjournal.

## Operativer Leseweg

`GET /api/bitget-demo/signals` führt über die bestehende originale
Session-/Actor-/Tradingmetadaten-/mTLS-Lesedomäne mit exakt signierter
`inspection=signals`. Sessionhandle, Tenant, aktuelle Rolle/Epoch und
aktives Credential werden vor und nach dem Abruf geprüft. Hinter Caddy
wird der Browser-Origin gegen die öffentliche Domain geprüft; der
interne Next-Listenerorigin wird nicht fälschlich gleichgesetzt.

Die private Quelle prüft aktuelle Trading-Snapshots ebenfalls vor und nach
dem öffentlichen Abruf. Der ursprüngliche Read-Token bleibt nur eine
Leseerlaubnis. Kein Signalbericht oder Read-Token erteilt eine Orderfreigabe.
Der tatsächliche Launcher verwendet unverändert seinen vorhandenen
`account_read`-Zweig; es entsteht kein neuer Handelsaktionspfad.

Der Monitor hält öffentliche Daten getrennt von Sitzung und Kontoprüfung.
Pro abgeschlossener Stunde wird jedes bestätigte Asset einmal geladen;
der originale Marktabrufzeitpunkt bleibt beim Cacheabruf erhalten.
Fehlgeschlagene Assets bleiben einzeln unbekannt und werden frühestens
nach 30 Sekunden erneut abgefragt. Drei parallele GETs, mindestens 110ms
Startabstand, begrenzte Antwortgröße und 4,5s Sammlung; Restlaufzeit
begrenzt jeden einzelnen nativen Request. Feste URLs, TLS-Prüfung,
keine Redirects/Proxies/automatischen Transportwiederholungen.

Die sichtbare Seite aktualisiert den Bericht alle 30 Sekunden nur im
aktiven Tab. Stundenwechsel oder Abruffehler markieren erhaltene Werte als
alten Stand. Ein manueller Abruf verwirft den letzten empfangenen Stand
nicht bei Fehlern. Der neue Leseweg konkurriert nicht um den Account-/
Ordermutex und ändert dessen Quoten nicht.

## Startfreigabe

Der Startbereich wird durch die
[gespeicherte Dashboard-Steuerung](bitget-demo-dashboard-control.md) ergänzt:
Coin-Auswahl, Basketobergrenze und Start-/Pause-Wunsch. Bei aktiviertem
eigenem Opt-in zeigt er „Start angefordert“ nach dem bestätigten Speichern.
Der operative Worker ist weiterhin nicht installiert; der Status behauptet
keinen aktiven Demohandel. Native Orderfreigabe und Worker folgen separat.

Weiterhin offen: native Basketzulassung einschließlich bekannter
Marketgrenzen, aktuell ausgewähltes Coinprofil, bestätigte Stufenmargin,
dauerhafte Start-/Pause-Zustimmung, Wiederanlauf und operativer Worker für
Käufe/Nachkäufe/Ausstiege sowie echte Fundingbuchungen. Die für den
20-USDT-Test genehmigte technische Ausnahme wird nicht auf Baskets
ausgedehnt. Eigenkapitalmargin×2 und manuelle sechste Stufe bleiben erhalten.

## Prüfung und Rollout

13 neue Pythonfälle prüfen Wilder, Null-/Grenzwerte, unfertige Kerzen,
Lücken, Stundenwechselcache, partielle Quellfehler, parallele Sammlung,
PID/Single-flight und aktuelle originale Read-Autorisierung einschließlich
Widerruf und tatsächlicher Launcherweiterleitung. 11 neue Nodefälle prüfen
Decimalgrenzen, Tenant-/Account-/Schema-Bindung, Stale/UI, Startstatus und
BFF-Origin-/Session-/Credentialprüfungen. Broker-/Actorports dieser
Tests sind synthetisch; Dateien/HTTP-mTLS der bestehenden Regressionen real.

87 verschiedene betroffene gepinnte Pythonfälle und 40 Nodefälle grün.
Der initiale Nodevergleich benutzte zwei verschieden zeitgestempelte
Testfixtures; auf einen Originalbeleg korrigiert und vollständig grün.
Erster schlüsselloser tatsächlicher BTC-H1-Abruf: 24.11.2026 13:00 UTC
Schlusskurs 60.403,5, RSI 44,9084789229005868326486570935569389,
Vorwert 45,2464900279309912923872658746447030, null Schlüsse unter 30.
Dies belegt ausschließlich den öffentlichen Marktleseweg.

Vollständige gepinnte Typprüfung und beide finalen Produktionsbuilds grün.
Der erste Typprüfcontainer brach ohne Diagnose mit Exit139 ab; mit begrenztem
512MiB-Heap/896MiB-Container erfolgreich. Der finale Cockpitbuild verwendet
768MiB-Heap/einen Worker, optimiert in3,3min, Typprüfung22,7s.
Öffentlicher Collector aus dem finalen Executorimage ohne Quellmounts oder
Schlüssel liefert alle sieben Assets bestätigt. Der tatsächliche Output
passt unverändert in den TypeScript-Vertrag; nur Tenant/Account für diesen
Interoptest synthetisch, keine native Kontoautorisierung behauptet.
Der Signalszweig wurde zusätzlich im realen Node-mTLS-Transport getestet;
gewöhnliche Walletantwort kann keinen Signalbericht ersetzen.

Autorisierter Rollout von `2db8a86` abgeschlossen: ausschließlich Cockpit und
Demo-Executor mit den finalen unveränderlichen Image-IDs erneuert, fünf
andere laufende Dienste unverändert. Alle sechs ursprünglichen Overlays und
Flags bleiben erhalten. Private Before-/Aktiv-/kompatible Rollbackbelege
unter `infra/local/demo-h1-signals/rollout-*`.

Öffentliches TLS200, neue Signalsroute/Account und alle fünf technischen
Order-POSTs anonym401; tatsächliches privates mTLS405. Cockpit gesund,
Executor UID10003/read-only/keine Hostports/Logdriver none/Restarts0.
Credential active1/1, originales technisches Journal Revision8 mit genau
zwei Versänden und sämtliche ursprünglichen privaten Datei-Hashes gleich.
Keine neue Migration/Dependency oder Deploymentorder. Automatischer
Demohandel weiterhin nicht gestartet. Originale Dashboard-Signalabnahme
angefordert und noch offen; kein Operator-OIDC/Sessionkontext erfunden.
