# Native Funding- und Mark-Minutenbelege

IP-090,2026-11-14. PR61 (`56c1d41`) ist in Main `50a1fa6` gemerged;
GitHub und Git-Ancestry bestätigt. Die neue öffentliche Quelle erfasst echte
Fundingraten und die Mark-Minutenkerze am selben nativen Settlementzeitpunkt.
Die Verwendung des Minuten-Eröffnungskurses im Paperprofil ist Q49,
bis zur Bestätigung ausdrücklich **nicht aktiviert**.

## Quellenvertrag

`futures_settlement_source.py` liest zehn feste unsignierte Classic-V2-GETs:
je BNB/BTC/ETH/SOL/XRP die Fundinghistorie und `history-mark-candles`,
`USDT-FUTURES`, `granularity=1m`. Nur der exakt angefragte native Fundingtermin
und die genau dort beginnende abgeschlossene Markminute werden ausgewählt.
Kein Runden der Fundingzeit, keine Tradepreise, Forecastraten oder neueren
Tickerpreise. Der eigene `MarkMinute`-Typ hält H1/H4-Forschungsachsen unverändert.

UTC-Minutenachse, OHLC, signierte Rate, kanonische native IDs, Vollständigkeit,
Duplikate, native Serveruhren und Antwortgröße werden geprüft. Der Zieltermin
muss1 Minute bis72 Stunden zurückliegen; maximal25 Sekunden für den gesamten
Abruf. Keine Keys, Redirects, Retries, privaten Endpunkte oder neue Dependencies.
Quelle: [Classic Contract Market API](https://www.bitget.com/docs/catalog/classic-contract-market/classic-contract-market).
Der dort dokumentierte Candle-Eröffnungskurs ist kein belegter tatsächlicher
Funding-Abrechnungskurs. Das Flag `exact_settlement_mark_available=false`
bleibt deshalb wahrheitsgemäß. Die Referenzpolicy `native-minute-mark-open/1`
beschreibt nur den vorgeschlagenen Kurs, `reference_enabled=false`.
Es gibt keine automatische Übergabe dieses Belegs an den exakten
`PaperSettlement`-Befehl.

`capture-futures-settlement-source.py OUTPUT --settled-at UTC_TIME` erstellt
einen neuen owned0700-Ordner unter geschütztem bestehendem Parent.
Zehn kanonische Antworten und typed Observation werden create-only0600,
fsync-bestätigt und vollständig zurückgelesen. Antwort-/Observationhashes
werden vor dem letzten Erfolgsreceipt geprüft; Parent und Ordner werden
ebenfalls fsync-bestätigt. Quellen-/Validierungsfehler bleiben mit Teilbelegen
ohne Erfolgsreceipt erhalten. Verlorene finale Schreibbestätigung verlangt
Readback des vorhandenen Verzeichnisses. Keine Überschreibung oder Retry.

## Reale Probe und offene Modellentscheidung

Native Fundingzeit2026-11-14T16:00Z; erfolgreiche Erfassung
2026-11-14T18:38:33.982475Z:
`infra/local/futures-paper-source/20261114-settlement-1600-2`.
Zehn native Antworten, fünf signierte Fundingraten und fünf Mark-Minutenkerzen.

| Asset | Native Rate | Minuten-Open | Minuten-Low | Minuten-High |
| --- | ---: | ---: | ---: | ---: |
| BNB | 0,000041 | 598,07 | 597,90 | 598,31 |
| BTC | 0,000057 | 65.713,5 | 65.662,0 | 65.719,3 |
| ETH | 0,000025 | 1.840,39 | 1.838,87 | 1.841,19 |
| SOL | −0,000058 | 73,841 | 73,801 | 73,902 |
| XRP | −0,000054 | 0,9714 | 0,9709 | 0,9725 |

Minuten-High/Low-Spanne relativ zum Open:6,86–16,47 Basispunkte
(etwa0,07–0,16 %). Diese Spanne ist eine Minutendiagnose, keine bewiesene
Abweichungsgrenze zur tatsächlichen Brokerabrechnung. Keine Auswahl eines
günstigen späteren Kurses. Die Probe ist über2h alt und damit ausdrücklich
kein zulässiger verzögerter Paper-Settlementcommit (dessen Grenze1h bleibt).

Observation-SHA256:
`99c448af6e632bf8b2d63f061e9210e99229edfabd157090d08608682db39dab`.
Receipt-SHA256:
`84dd622a8905a00351f4ac191654f0f6efdc9a916b8f51bdefe1bf7ee681a9b0`.
Der erste Probeordner `20261114-settlement-1600-1` bleibt ohne Erfolgsreceipt:
der bestehende ResearchCandle-Typ akzeptiert nur H1/H4; eigener Minuten-Typ
behebt das, ohne historische Module zu verändern.

Zehn neue Offlinefälle prüfen Transport, native Zuordnung, vollständigen
typed Roundtrip, fehlende/verschobene Rates, Minuten-/Preisfehler,
Clock/Deadline und tatsächlichen Archiv-Readback/Fehlerpfad.
Gezielte gepinnte Paper-/Funding-/API-/Quellenregression:103 Fälle/82 Subtests
grün unter Python3.14.10; zehn neue Collector-/Archivfälle enthalten.

Q49 offen: Minuten-Open als deklarierte **Paper-Modellreferenz** verwenden
oder exakte Fundingbewertung weiter verlangen. Erst eine bestätigte Entscheidung
erlaubt einen eigenen expliziten Modellvertrag und dessen Journalanbindung;
der exakte bisherige Vertrag wird nicht still umgedeutet.
Weiter: bestätigte Bewertungsanbindung, Cursor/Archiv/Launcher/Statepublikation,
013 Settings/Kapital, Gewinnetappen und Recovery. Laufende Dienste, Dashboard-
Opt-ins, Live/AI und historische Performance bleiben unverändert.
