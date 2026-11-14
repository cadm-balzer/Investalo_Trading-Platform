# Dauerhafte Futures-Paperstatus-Übergabe

IP-090,2026-11-14. PR63 (`7aeec8d`) ist in Main `da3c467` gemerged;
GH/Fetched-Ancestry bestätigt. Dieser Zwischenstand verbindet den bereits
geprüften eingespeisten Paperworker mit einem privaten dateibasierten
Dashboardreader. Ein automatischer aktueller Quellenworker wird noch nicht
gestartet.

## Journal und Lesestand

`futures_paper_view.asset_state` extrahiert einen eigenen unveränderlichen
`FuturesAssetState`: Mandant/Konto, Revision, echte Quote-/H1-/Wissenszeiten,
Kapazität/Sperren sowie höchstens sieben RSI-/Positions-/Nachkaufzeilen.
Kein Journal, Event-/Funding-ID-Verlauf, Keys oder ausführbarer Handelszustand
werden kopiert. Derselbe `asset_snapshot`-Projektor liest nun entweder diesen
Lesestand oder den bisherigen `FuturesPaperState`; der HTTP/TS-Vertrag bleibt.

`FuturesPaperJournal.checkpoint()` liefert unter einem Lock den bestätigten
Zustand mit seinem Receipt. Unknown-write/geschlossenes Journal verweigern
bereits diesen Zugriff. Ein optionaler `FuturesAssetPublisher` am eingespeisten
Worker veröffentlicht erst nach warmup/batch/settlement/minute_settlement-
Commit und erneuter Guardprüfung. Ohne Publisher bleiben die alten Workerpfade
unverändert.

`futures_paper_status.py` schreibt Version
`isolated-usdt-futures-paper-status/1`: kompakter Lesestand, vollständiger
Journalreceipt, Publikationszeit und Contenthash, `execution_enabled=false`.
SHA256 bindet den kanonischen Inhalt; die Vertrauensgrenze sind die privaten
Dateisystemrechte und der bestätigte Journalschreiber, kein externer
signierter Brokerbeleg.

Der bestehende absolute Root muss owned0700 sein, Dateien owned0600/
regulär/einzelner Hardlink, höchstens64KiB. Mandant/Konto werden auf einen
festen Dateinamen gehasht; HTTP übernimmt keinen Pfad. Symlinks, falsche
Rechte, fremde IDs, Extra-/Duplikatfelder, beschädigte oder zukünftige
Publikation werden abgewiesen.
Ein separater Accountlock bleibt für die ganze Publisherlebenszeit gehalten.
Create-only-Temporärdatei, File-fsync, atomarer Replace, Directory-fsync und
voller Readback sichern die Veröffentlichung. Reader erhalten den alten
oder neuen vollständigen Stand; sie sperren nicht das Journal.

## Neustart und Fehlergrenzen

Journal und Statusdatei sind zwei getrennte Commits. Der Status darf hinter
dem Journal liegen; er behauptet dann ausdrücklich nur die zuletzt publizierte
Revision. Quotealter, geschlossene Stunde,30s-RSI-Fenster, nächste H1-Prüfung
und aktueller Kontostatus werden bei jeder HTTP-Abfrage neu berechnet.
Publikations-/Lesedatum erneuern nie die Quoteuhr. Veraltete offene Positionen
bleiben sichtbar und sind als veraltet markiert; fehlende Publikation bleibt
`snapshot=null`.

Unknown-fsync/Replace/Readback stoppt den Publisher und weitere Workerabrufe.
Teildateien bleiben erhalten; kein Retry und keine rückwirkende Order.
Nach Prozessende wird der vorhandene publizierte Receipt gelesen und als
`minimum_receipt` an den vollständigen `FuturesPaperJournal.restore` übergeben.
Damit werden Trunkierung, fremde Genesis oder ein anderer Journalzweig am
bestätigten Stand abgewiesen. Der neue Publisher akzeptiert nur den aktuellen
Receipt oder genau den bei diesem Vollrestore belegten Vorfahren. Danach kann
der bereits bestätigte neuere Journalstand erneut publiziert werden.

## API-Konfiguration und Prüfung

`API_FUTURES_PAPER_STATUS_ROOT=/absolute/private/root` konfiguriert den
`FuturesAssetReader` beim normalen `create_app` ausschließlich zusammen mit
dem bestehenden `API_FUTURES_PAPER_ASSETS_PREVIEW=1`. Der explizit injizierte
Testreader behält Vorrang. Authentifizierung/aktuelle Membership/DB-Accountscope
kommen vor Dateizugriff; Lesefehler bleiben generische503 ohne interne Details.
Die API braucht nur einen readonly Mount und denselben dedizierten UID wie der
Writer. Compose, Mounts, Rollen und laufende Dienste sind noch unverändert.

Zehn neue Domain-/echte Dateisystemfälle und drei tatsächliche
restricted-LOGIN/HTTP/PG-Fälle.128 gezielte gepinnte Paper-/Quellen-/Signal-/
API-Fälle und105 Subtests grün unter Python3.14.10. Alte exakte/gewöhnliche
Journalgoldenreceipts und bisherige Anzeigeverträge weiterhin geprüft.
Nach der Abschlussprüfung von Dateirechteänderungen und der möglichen
Null-Tick-Kaufgrenze26 betroffene Publikations-/Anzeige-/API-Fälle mit14
Subtests erneut gepinnt grün.
Keine neuen Abhängigkeiten, Migrationen, historischen Performancejobs oder
Public-/Live-/AI-Aktivierung.

Weiter: dauerhafter Quellen-/Settlementcursor, Archiv-/Launcheranbindung,
013 Settings-/Kapitaladapter, Q36-Gewinnetappen und IP-088-Recovery;
danach laufende lokale Cockpitabnahme. IP-090 bleibt in Arbeit.
