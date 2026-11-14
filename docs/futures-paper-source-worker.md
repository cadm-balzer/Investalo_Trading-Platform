# Archivierter Futures-Paperquellenworker

IP-090,2026-11-14. PR64 (`5469400`) ist in Main `4a50081` gemerged,
GH/Fetched-Ancestry bestätigt. Dieser Zwischenstand verbindet die unsigned
Classic-Quellen, den bestätigten Q49-Minutenvertrag, das eigene Paperjournal
und die private Dashboardpublikation. Ein expliziter begrenzter Launcher
ist implementiert; laufende Dienste und Dashboardopt-ins bleiben unverändert.

## Quellenarchiv und Journalfortschritt

`FuturesPaperArchive` schreibt jede native Antwort vor ihrer Verwendung
create-only/owned0600 mit fsync und Readback in eine neue owned0700-Kohorte.
Der bestehende absolute Archivroot muss owned0700 sein. Ein Marktbeleg
enthält25 GET-Antworten, ein Minutenbeleg zehn. Die typisierte Beobachtung
und ein eigener `bitget-classic-futures-paper-archive/1`-Receipt binden
Originalantworten, URLs, SHA256 und tatsächliche Erfassungsuhren.
Vor Erfolg und bei jedem Laden werden die Originalantworten mit den
bisherigen Collectors vollständig offline erneut geparst. Eine manipulierte
Beobachtung mit neu berechneten eigenen Hashes reicht damit nicht aus.
Private Dateirechte bleiben die Vertrauensgrenze; kein signierter Brokerbeleg.

Symlinks, fremde UID/Rechte, Hardlinks und übergroße Dateien werden abgewiesen.
Höchstens2000 Kohorten; kein Löschen oder Verdrängen von Belegen. Bei15s-Zyklen
ist das ein begrenzter lokaler Prüflauf, kein unbegrenzt betreibbarer Dienst.
Unvollständige Kohorten bleiben ohne Erfolgsreceipt erhalten. Unbekannter
Schreib-/fsync-/Readbackausgang sperrt weitere Abrufe derselben Archivinstanz.

`PaperSourceRef` bindet Art, privaten Kohortenschlüssel, Daten-/Receipthash und
Erfassungszeit. Drei additive Befehle im bestehenden eigenen Paperjournal
speichern diese Referenzen zusammen mit dem jeweiligen finanziellen Commit:
`source_warmup`, `source_batch`, `source_minute_settlement`.
Der bestätigte Vorgänger ist verbindlich. `source_checkpoint()` liefert
Zustand, Receipt und Quellenfortschritt unter demselben Lock. Der Cursor
wird ausschließlich durch vollständiges Journalreplay rekonstruiert;
keine separate mutable Cursordatei und kein Fortschritt vor fsync.
Alte ungebundene Journale und ihre Goldenidentitäten bleiben unverändert.
Ein nichtleeres ungebundenes Journal wird vom neuen Worker vor HTTP gestoppt;
eine Migration oder Rücksetzung erfolgt nicht automatisch.

## Kausaler Zyklus und Neustart

Der kalte Worker archiviert die16–72 geschlossenen H1-Warmupstunden der
bereits erklärten Genesis und publiziert erst nach dem Journalcommit.
Spätere Zyklen prüfen den archivierten Warmup- und letzten Quellenbeleg,
erfassen getrennte native H1-Trade-/Markachsen, echte Bid/Ask-/Markquoteuhren,
Fundinghistorie und Forecast. Offene Positionen mit mehr als einer
fehlenden geschlossenen H1-Stunde erfordern Reconciliation vor weiteren GETs.

Vor erwartetem Funding wartet der Worker auf die tatsächlich geschlossene
Settlementminute. Er archiviert die Minute und die aktuelle Marktbeobachtung,
gleicht beide nativen Fundingkohorten gegen den bestätigten Vorgänger ab und
committet den eigenen Q49-Minuten-Open-Modellbefehl. Keine exakte
Broker-Settlementbewertung wird behauptet. Native IDs/Raten, volle OHLC,
Wissenszeit und höchstens1h Publicationlag bleiben verbindlich.
Das30s-RSI-Fenster wird nicht verlängert; die Abrechnung erneuert keine Quotes.

Zwischen Fundingcommit und Quotecommit bleibt ein vollständiger Fundingcursor
im Journal. Nach einem Abbruch werden beide archivierten Quellen nochmals
geprüft und frische Quotes erfasst. Bereits gebuchte IDs werden nicht erneut
belastet. Erst der bestätigte nachfolgende Quotecommit setzt den Cursor weiter.
Liquidationsbedarf stoppt vor neuen Quotes und verlangt manuellen Abgleich.
Fills, Käufe, Nachkäufe und Schließungen bleiben ausschließlich die bisherigen
kausalen Paperreducer mit2× und vollständiger eigener Kaufstaffel.

Jeder bestätigte Commit wird mit dem vorhandenen Publisher veröffentlicht.
Ein unbekannter Statuscommit stoppt weitere Abrufe. Neustart liest den
veröffentlichten Mindestreceipt, stellt das vollständige Journal wieder her
und repariert erst dann einen zurückliegenden Lesestand. Auch ein unbekannter,
aber bei Vollrestore tatsächlich vorhandener Quotecommit wird berücksichtigt.
Kein automatischer Retry, keine rückwirkenden Fills und keine Genesiserneuerung.

## Begrenzter lokaler Launcher

`python -m investalo_workers.futures_paper_main` verlangt
`FUTURES_PAPER_WORKER_ENABLED=1` sowie:

- `--journal`: vorhandenes privates eigenes Paperjournal.
- `--config-digest`: dessen separat vertrauenswürdig festgelegter Konfigurationshash.
- `--tenant-id`, `--account-id`: eigene UUIDs, exakt gleich dem Journalplan.
- `--archive-root`, `--status-root`: bereits vorhandene absolute private Roots.
- Optional `--cycles`1–100 (Default1), `--interval`5–300 Sekunden (Default15).

`PYTHONPATH` umfasst `packages/trading/src`, `packages/marketdata/src` und
`services/workers/src`. Der Launcher erzeugt kein Konto und kein Startkapital.
Er braucht keine Börsenkeys, DB-Zugangsdaten oder private Brokerendpunkte.
SIGTERM/SIGINT werden vor Abrufen, Commit und Veröffentlichung erneut geprüft.
Fehler beenden den Lauf ohne automatische Wiederholung; Logs enthalten nur
Ergebnis, Revision und Paper-Kauf-/Abschlussanzahlen bzw. einen generischen
Fehlertyp. Kein systemd-/Compose-Dienst und keine Health-/Betriebszusage.

## Prüfbeleg und nächste Schritte

Zwölf neue Fälle verwenden tatsächliche lokale Archiv-/Journal-/Statusdateien
mit synthetischen nativen HTTP-Antworten: Warmup/erste Käufe, Minutenwartezeit,
einmalige Fundingbuchung, Abbruch zwischen Funding und Quotes, unbekannter
Journal-/Status-/Archivcommit, native Replaymanipulation, Quellenvorgänger,
zukünftiges Wissen, Lücken, Abbruchguard und zwei begrenzte Launcherinvokationen
mit vollständigem Restore und publiziertem Mindestreceipt.
140 gezielte gepinnte Paper-/Quellen-/Signal-/API-Fälle und109 Subtests unter
Python3.14.10 grün, einschließlich alter gewöhnlicher und exakter
Journalgoldenidentitäten. Kein neuer historischer Performancejob.

Als Nächstes: tatsächliche eigene Konto-/Kapital-/Genesisbereitstellung und
013-Settingsbindung, dann eine laufende lokale Cockpitabnahme. Q36-Gewinnetappen,
IP-088-Reconciliation/Recovery und Bitget-Demoausführung bleiben weitere Schritte.
Keine Migrationen, neuen Abhängigkeiten oder Public-/Live-/AI-Aktivierung.
