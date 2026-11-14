# Bestätigte Minuten-Open-Referenz für Paperfunding

IP-090/Q49,2026-11-14. PR62 (`0f70ff6`) ist in Main `4b837f1` gemerged;
GitHub/Fetched-Ancestry geprüft. Der Nutzer bestätigt den nativen Mark-Open
der Settlementminute als deklarierte Paper-Modellreferenz. Die tatsächliche
Broker-Fundingbewertung bleibt unbekannt. Kaufstaffel, eigene reservierte
Ranges, manuelle sechste Stufe und fester2×-Hebel bleiben erhalten.

## Eigenständiger Vertrag

`futures_paper_minute.py` führt `PaperMarkMinute` und `PaperMinuteSettlement`
ein, Version `isolated-usdt-futures-paper-minute-settlement/1`,
Policy `native-minute-mark-open/1`. Der eigene Journalbefehl
`minute_settlement` speichert die komplette kanonische OHLC-Kerze pro Kandidat,
exakte UTC-Minutenachse, signierte native Fundingraten/-IDs, Quellenhash,
Erfassungszeit und gegebenenfalls den gerade geschlossenen H1-Frame.
Der Bewertungsmark wird ausschließlich aus Open abgeleitet; Close, Low, High,
Forecast oder spätere Tickerpreise können ihn nicht ersetzen.

`SettlementEvidence.paper_minute_settlement` prüft die Verbindung mit dem
aktuellen Classic-H1/Quote/Fundingbeleg und dem bestätigten Vorgängerreceipt.
Beide Quellen müssen dieselben nativen Funding-IDs, Zeiten und Raten liefern.
Frühere offene Fundingtermine, fehlende erwartete Abrechnung, revidierte
H1-Historie oder falscher Vorgänger stoppen die Übergabe. Die reine
Quellenaufnahme behält ihre bisherigen Bytes und deaktivierten Archivflags:
sie startet selbst keinen Worker.

Der volle Modellbefehl hat eine eigene Receipt-ID und bindet auch OHLC,
Erfassungszeit und Policy. Der bisherige exakte `settlement`-Befehl bleibt
getrennt. Gemeinsame finanzielle Reduktion erhält seine ursprünglichen
Identitäten; Goldenreceipts prüfen sowohl die alten normalen Batches als
auch die alte exakte Fundingabrechnung.

## Zeit, Cash und Wiederaufnahme

Die native Minute muss bereits geschlossen und der Beleg beim Commit bekannt
sein. Die Grenze von höchstens1h zwischen Fundingtermin und Commit bleibt.
Die reale16:00Z-Probe aus PR62 ist über2h verspätet und wird nicht rückwirkend
als Paperabrechnung eingesetzt.

Funding wird als `−offene Menge × Minuten-Open × native Rate` im eigenen
isolierten Saldo gebucht; positive Rate belastet Longs, negative schreibt gut.
Am UTC-Tageswechsel kommt zuerst die Tagesbasis zum selben Open, dann Funding.
Die Abrechnung erzeugt keine Orders/Fills, Restoration oder Basketabschlüsse
und erneuert keine echte Handelsquoteuhr. Liquidationsbedarf bleibt verriegelt,
bis der getrennte Abgleich erfolgt; neuere erholte Quotes löschen ihn nicht.

Erst nach fsync-bestätigtem vollständigem Befehl und erneuter Prüfung der
nativen History darf die Quelle mit echten frischen Quotes fortfahren.
Das30s-H1-RSI-Einstiegsfenster bleibt bestehen. Die abgeschlossene Minute ist
frühestens nach60s bekannt: ein inzwischen abgelaufenes Fundingstunden-Signal
wird daher nicht nachträglich gehandelt. Weitere aktuelle H1-Signale gelten
nach den bestehenden Regeln.

CAS, exklusive Schreiberschaft, native ID-Deduplizierung und voller
Genesisrestore gelten auch für den neuen Befehl. Unknown-fsync beendet den
Writer; Readback stellt die einmalige Buchung fest, kein Wiederholungsversuch.
Der eingespeiste Worker prüft den Archivguard vor Abruf und vor Journalcommit.

## Prüfumfang und verbleibende Anbindung

Zwölf neue Fälle prüfen signierte Open-Abrechnung, native Quellenbindung,
Wissenszeit/abgelaufene RSI-Fenster, Policy-/OHLC-/Receiptmanipulation,
Mitternacht, native Duplikate, Liquidationsverriegelung, Trennung der beiden
Journalverträge, alte exakte Goldenidentität, Vollrestore/Fortsetzung,
Unknown-write-Readback und Worker-Archivguards.

Gezielte gepinnte Quellen-/Paper-/API-/Signalregression:115 Fälle/96 Subtests
grün; die zwölf neuen Fälle sind enthalten. Python3.14.10 aus dem bestehenden
Prüfcontainer, kein Image-/Dependencywechsel.

Dauerhafter Quellen-/Settlementcursor, Archiv/Launcher, State-Readerpublikation,
013 Settings/Kapitaladapter, Q36-Gewinnetappen und IP-088-Recovery bleiben
IP-090. Laufende Dienste und Dashboard-Opt-ins sind unverändert; keine
Migration, neue Dependency, Marktstudie, Public-/Live-/AI-Aktivierung.
