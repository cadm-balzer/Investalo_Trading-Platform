# Aktuelle Classic-Futuresquelle für Paper

IP-090, lokaler Zwischenstand vom 2026-11-14. PR58 (`cd79977`) ist in
Main `2cdb9b7` gemerged; GH und Git-Ancestry wurden geprüft.
Der eigene Collector und die begrenzte Übergabe an den Paperkern sind
implementiert. Der dauerhafte Dienst bleibt noch aus.

## Quellenvertrag

`packages/marketdata/src/investalo_marketdata/futures_paper_feed.py`
liest ausschließlich öffentliche, unsignierte GETs auf `api.bitget.com`.
Feste Classic-V2-Endpunkte, `productType=USDT-FUTURES`, keine Credentials,
Redirects oder automatischen Wiederholungen. Der geprüfte erste Quellenkorb
enthält BNB/BTC/ETH/SOL/XRP. Neue Kandidaten brauchen eigene Instrument- und
Quellenprüfung. Kein zusätzlicher kostenpflichtiger Dienst.

Pro Durchlauf erfolgen25 Aufrufe: je Coin Trade-H1, Mark-H1, Fundinghistorie,
aktueller Fundingforecast und zuletzt ein frischer Bid-/Ask-/Markquote.
Trade und Mark verwenden ausdrücklich unterschiedliche History-Endpunkte.
Die exakte Achse umfasst1–72 geschlossene native H1-Kerzen; Lücken, doppelte
Zeitstempel, widersprüchliche OHLC und fehlende Achsen werden verworfen.
Die dokumentierte vorherige Randkerze wird nicht in die gewählte Achse kopiert.

Jede kanonische Antwort erhält einen SHA256-Beleg, URL, Request-, Empfangs-
und native Serverzeit. Jeder Quote behält seine eigene native Uhr.
Die gemeinsame Paperbewertung verwendet die Empfangs-/Wissenszeit des
fertigen Quellenkorbs; sie behauptet keine gleichzeitigen Providerquotes.
Gesamterfassung maximal25 Sekunden, Quotealter maximal30 Sekunden,
kein Wechsel der UTC-Stunde während der Erfassung.
Ein späterer Journalcommit muss weiterhin die30-Sekunden-Frist prüfen.

Fundinghistorie erhält sämtliche einzelnen nativen Zeitstempel, IDs und
signierten Raten im gewählten Fenster. Die letzte100er-Seite muss bis zum
Checkpoint zurückreichen; andernfalls Abbruch. Keine Zusammenfassung in
angenommene Achtstundenblöcke. Der aktuelle Forecast mit1/2/4/8-Stundenintervall
und `nextUpdate` ist separat; seine Rate ersetzt keine historische Abrechnung.
Ein neuer Fundingtermin während der Erfassung verlangt einen neuen Abruf.
Eine einzelne Historyseite beweist keine vollständige historische
Abrechnungskalenderachse bei verzögerter Veröffentlichung.

Providervertrag:
<https://www.bitget.com/docs/catalog/classic-contract-market/classic-contract-market>.
Generisches `candles?kLineType=MARK` hat bei der realen Probe still Tradepreise
geliefert; die dokumentierten Werte sind kleingeschrieben. Der Collector nutzt
stattdessen `history-mark-candles`. Bestehende Quellen bleiben unverändert.

## Begrenzte Übergabe und Neustart

`FuturesMarketObservation.paper_batch` akzeptiert ausschließlich den eigenen
gewärmten Paperkern mit vollständiger `BITGET:`-Kandidatenachse.
Historische `BINANCE:`-Quellen oder Spotpreise passen nicht zu dieser Genesis.
Ein revidiertes bereits gespeichertes H1-Stundenende wird abgewiesen.
Der bestehende Kern prüft weitere Kerzenlücken, Liquidation vor neueren Quotes,
Kosten, Margin, Kaufstaffel, RSI und die fest eingefrorenen2×.

Mit offenem Kapital verlangt die Übergabe den letzten bestätigten
Quellenbeleg: dessen Erfassungszeit muss zum Signalcheckpoint passen und
sein Digest bereits als Input-ID im Paperjournal stehen.
Das bewahrt den vorherigen Fundingforecast auch beim Wiederanlauf.
Das Quellenartefakt muss **vor** dem Papercommit geschützt gespeichert werden.
Der getestete Ablauf enthält zwei Quellenübergaben, volle Genesis-/Journal-
wiederherstellung und den zurückgelesenen originalen Quellenbeleg.
Ein autonomer Feedcursor-/Archivadapter ist damit noch nicht implementiert.

Die Classic-Fundinghistorie enthält **keinen Settlement-Markpreis**.
Bei offenem Basket sperrt die Übergabe deshalb sowohl einen überschrittenen
vorherigen `nextUpdate` als auch tatsächlich beobachtetes Funding nach dem
Checkpoint. Die Sperre gilt auch bei verzögerter Veröffentlichung der History.
Es gibt keine stille Auslassung, Verschiebung auf einen neueren Quote oder
Substitution durch eine Forecast-Rate. Der aktuelle Paperkern verlangt für
Funding die passende Settlementzeit und Bewertung; der dafür notwendige
eigene Bewertungs-/Reconciliationbefehl bleibt als nächster Schritt offen.
Vergangene Fundingtermine vor dem ersten Einstieg eines flachen Kontos sind
keine Kosten dieses Kontos.

## Realer Quellenbeleg

`python3 infra/scripts/capture-futures-paper-feed.py NEW_DIRECTORY`
erzeugt einen neuen0700-Ordner unter einem vorhandenen eigenen geschützten
Parent.25 kanonische Antwortdateien, `observation.json` und ein abschließender
`receipt.json` sind create-only0600, fsync-bestätigt und zurückgelesen.
Alle25 Antwortdigests sowie der vollständige typisierte Observation-Roundtrip
werden vor dem Receipt geprüft. Ein Quellen-/Prüffehler hinterlässt Teilbelege
ohne Erfolgsreceipt. Eine verlorene finale Schreibbestätigung verlangt
Readback des vorhandenen Verzeichnisses; kein automatischer Retry und kein
Überschreiben früherer Captures.

Realer erfolgreicher Abruf:
`infra/local/futures-paper-source/20261114-current-1`.
Fenster2026-11-12T00:00Z bis2026-11-14T10:00Z,
Erfassung2026-11-14T10:04:58.304091Z.
58 geschlossene Stunden je Trade-/Markachse,580 einzelne Kerzen,
fünf frische Quotes,40 native Fundingereignisse, fünf Forecasts.
Quotestempel10:04:56.620Z bis10:04:58.188Z; alle Forecasts nennen
16:00Z als nächsten Termin. Dies ist eine aktuelle Quellenprobe.

Observation-SHA256:
`69609e22be7b41abaf016e16a5687d4e359e385ded125765fe8f641c32fd82da`.
Receipt-SHA256:
`dabfaf047fc545357e095670190c1b1df28dcb300375417639c351ee9cfebfeb`.

15 neue synthetische Quellen-/Übergabefälle prüfen getrennte Trade/Markpreise,
native Uhren, Funding-/Forecasttrennung, Fremd-/Privat-URLs vor I/O,
HTTP-Grenzen, fehlerhafte/fehlende Kerzen, Fundingtruncation/-duplikate,
Stalequotes/Spread/Clock/Deadline, keine Retries, Eigenkapital/Ask/2×,
verbindlichen Vorgängerbeleg, Settlementbarriere, Candle-Revisionsschutz
und vollständigen Quellen-/Journalrestore.
Gezielte gepinnte Regression einschließlich des bestehenden Paperkerns,
Kapital-/Signal-/Grid-/Kapazitäts- und Fundingverträgen:
111 Fälle/100 Subtests bestanden unter Python3.14.10.

Keine neue Performanceberechnung, DBmigration, Dependency, öffentliche
Flagaktivierung oder reale Order. `runtime_ready=false` und
`recommendation=null` bleiben korrekt. Weiter: Settlementbewertung,
dauerhafter Quellen-/Journalcursor und Archivierung, Launcher, aktuelle
Instrumentkalibrierung,013 Status-/Settingsadapter, Q36-Gewinnetappen,
IP-088-Recovery und Cockpit.
