# Öffentliche Fundinghistorie und Abdeckungsprüfung

Erster IP-069-Checkpoint; IP-068`91a1547` ist in Main`56877b0` verifiziert.
Branch `feat/m1-futures-funding-history`. Neues reines Modul
`futures_funding.py`; bestehende Funding-/Futures-/Spotformate und Tradingkerne
bleiben unverändert.

## Tatsächlicher Quellenbefund

Die aktuelle offizielle [Classic-V2-Dokumentation](https://www.bitget.com/docs/catalog/classic-contract-market/classic-contract-market)
beschreibt Fundinghistorie mit `pageNo` und maximal100 Einträgen je Page.
Sie bietet hier keinen Start-/Endzeitparameter. Die aktuelle
[V3-Dokumentation](https://www.bitget.com/docs/catalog/market/derivatives)
nennt ausdrücklich die letzten90 Tage. Die ältere Legacy-V3-Seite lässt
diese Beschränkung im Text aus; zusätzliche Cursorpages beweisen deshalb
keine ältere Abdeckung.

Der native Classic-V2-Import am2026-11-11 bestätigt für **BTCUSDT und ETHUSDT
je270 Abrechnungen**,2026-08-13T16:00Z bis2026-11-11T08:00Z. In diesen
tatsächlich beobachteten Reihen beträgt der Abstand jeweils8 Stunden.
Je Symbol drei nichtleere Pages und eine leere Abschlussseite:
insgesamt8 öffentliche GETs und540 echte signed Fundingereignisse.

Für das bereits festgelegte Forschungsfenster
2022-08-01..2025-08-01 liefert diese Quelle **null Ereignisse**.
Gegen einen ausdrücklich deklarierten8h-Kalender fehlen je3288 erwartete
Abrechnungen. Dieser Kalender ist eine Forschungsannahme; aktuelle Intervalle
beweisen keinen vollständigen historischen Settlementkalender.
Die Datenlücke wird nicht als Fundingrate0 umgedeutet.

Der offizielle [Downloadcenter](https://www.bitget.com/legacy-docs/uta/data-download-center)
listet öffentliche Candles/Trades/Depth und getrennte persönliche
Finanzabrechnungen. Damit ist noch kein vollständiges öffentliches
Bitget-Fundingarchiv für2022–2025 belegt. Zusätzlich gefundene fremde
CSV-/Scriptangebote wurden mangels belegter passender Venue-/Zeitraumprovenienz
nicht als native Bitgetdaten übernommen. Es wurden keine Dienste gebucht.

## Importvertrag

`BitgetFundingHistoryAdapter` ruft ausschließlich den festen unsignierten
Classic-V2-Fundingpfad für bestehende erlaubte Futures-Symbole ab.
Der Transport akzeptiert exakt seine kanonischen URLs: keine zusätzlichen
Parameter, Origin-/Pfadänderungen, API-Keys, Cookies oder Redirects.
10 Sekunden Timeout,256KiB Antwortlimit,100 Zeilen je Page,
höchstens100 Pages/10.000 Beobachtungen,0,1 Sekunden Pageabstand.
Es gibt keinen automatischen Retry.

Provider muss Erfolg bestätigen; jedes Ereignis bindet eigenes Symbol,
streng signed Decimalrate und begrenzten Unix-Millisekundenzeitpunkt vor
dem eingefrorenen Retrievalcutoff. Pages müssen absteigend sortiert sein.
Gleiche Pagegrenzen werden einmal übernommen; widersprechende Revisionen,
doppelte Zeilen innerhalb einer Page, Futureevents und nicht fortschreitende
Pagination brechen ab. Ein erschöpftes Pagelimit ist kein Erfolgsabschluss.
Eine kurze Page beendet den Import nicht: die nächste leere Seite oder das
Erreichen des gewünschten Starts beendet den begrenzten Beobachtungslauf.

Ergebnis sind zwei **getrennte** bestehende `funding/1`-Snapshots:
die tatsächlich im gewünschten Fenster gefundenen Ereignisse und die
tatsächlich beobachtete neuere Historie. Neuere Raten werden niemals in ein
altes Fenster verschoben. Leere Beobachtung bleibt leer.

`FundingExpectation` bindet Symbol, exaktes Fenster, nichtleeren
kanonischen Settlementkalender und expliziten Annahmendigest. Kalender können
ausdrücklich wechselnde Intervalle enthalten; der Prüfer leitet diese nicht
aus zufällig vorhandenen Ereignissen ab. `audit_funding_coverage` weist
fehlende **und unerwartete** Zeitpunkte aus, einschließlich innerer Lücken.
Ein tatsächlich beobachtetes Ereignis mit Rate0 zählt als vorhanden.
Passende Endpunkte allein beweisen keine Vollständigkeit.

`complete_against_declared_calendar` bezeichnet nur Mengen-/Zeitdeckung
gegen diesen deklarierten Kalender. `historical_schedule_verified=false`,
`performance_evaluated=false` und `execution_enabled=false` bleiben fest.
Der Prüfer ist keine wirtschaftliche Profil- oder Brokerfreigabe.

## Artefakte und Abnahme

```bash
python3 infra/scripts/import-futures-funding.py OUTPUT_DIRECTORY
```

Das CLI prüft vor Netzwerk-/Dateischreibzugriff den fest gepinnten
[Protokollhash](research-protocols/futures-funding-20261111.json).
Ausgabeverzeichnisse und Dateien sind create-only. Fehler oder eine
unvollständige zweite Symbolabfrage veröffentlichen keine abschließende
Receipt. Fehlende Marktabdeckung darf dagegen eine erfolgreiche
**Beobachtungsreceipt mit ausdrücklich unvollständigem Fenster** erzeugen.
`net_backtest_ready=false` bleibt auch bei passendem Annahmenkalender.

Echte Snapshots liegen ignoriert unter
`infra/local/futures-funding-data/20261111-native-network`.
[Commitbare Receipt](research-protocols/futures-funding-receipt-20261111.json)
bindet Protokollhash, acht dekodierte Pagehashes, vier Datei-/Datendigests und
die beiden Kalenderdiagnosen. Alle vier Snapshots wurden tatsächlich
eingelesen und gegen ihre Hashes sowie die jüngste8h-Achse geprüft.
Ein vorheriger sandboxgesperrter DNS-Lauf bleibt ohne Erfolgsreceipt erhalten;
der separat freigegebene Netzwerklauf nutzt ein neues Verzeichnis.

25 neue synthetische Fälle,24 erste Hostchecks plus25 finale Modulchecks;
25 unterschiedliche Hostfälle. Gepinnte Marktdataregression101 Fälle und
187 Subtests, danach finale25 Modulchecks:102 unterschiedliche gepinnte Fälle.
Kalender-/Zeitgrenzen, signed/Nullraten, innere Lücken, Cadencewechsel,
URL-/Body-/Pageressourcen, Revisionen, Retryverbot, Protokolländerung und
create-only/Teilfehler belegt. Eigenprüfung, keine Agentdelegation,
Trading-/Credential-/DB-Suiten ohne Änderungen nicht wiederholt.
Nur zwei readonly Fixturemounts für CLI/Protokoll ergänzt; keine Dependencies,
Migrationen, Holdoutjobs, öffentlichen Container oder Runtimeaktivierung.

## Fortsetzung

IP-069 bleibt offen: wirtschaftliches Profil, vollständige native historische
Funding-/Kontraktprovenienz und langes Replayprotokoll sind nicht abgeschlossen.
Der begrenzte Signalwrapper benötigt für lange Ereignisfolgen zusätzlich
einen geeigneten Journalvertrag;1024er IDs nicht periodisch verwerfen.
Ein eigenständiger Vergleich auf einer anderen Börse darf erst als eigener
Daten-/Kosten-/Ergebniskontext vorbereitet werden; keine stillschweigende
Venue- oder Fundingersetzung. Nutzerpräferenz zu einem zusätzlich getrennten
kostenlosen Binance-Forschungsvergleich wurde optional erfragt.
Bitget bleibt das bestätigte Tradingziel; es gibt noch keine neuen
wirtschaftlichen Futures-Nettoergebnisse.
