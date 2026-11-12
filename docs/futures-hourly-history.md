# Gemeinsame native H1-Futuresquelle

IP-075 ergänzt die für IP-074 fehlende H1-Quellenbasis. Der H4-RSI-/H1-Schutz-
Checkpoint`2d7878f` ist in Main`507cb87` verifiziert. Bitget bleibt Handelsziel;
Binance ist die separat bestätigte kostenlose Forschungsquelle.

## Vorab festgelegtes Fenster

[Quellenprotokoll](research-protocols/futures-h1-history-20261112.json),
SHA256`3b3ecdd1b9c630a59e0b5f33f1255b0012c73dce7274bba81ee3435224336c57`.
BNB, BTC, ETH, SOL und XRP stammen aus der zuvor erklärten Fünf-Coin-Kohorte;
keine neue Auswahl nach erzielten Profiten.

Exaktes Forschungsfenster2022-08-01T00:00Z..2025-08-01T00:00Z, Ende exklusiv.
Erwartet je Coin26304 vollständige H1-Trade- und26304 H1-Markkerzen:
1096 Tage beziehungsweise6576 H4-Signalgruppen. Der reservierte Holdout
2025-08-01..2026-08-01 wird nicht angefragt. Keine Spotpreise als Futurespreise.
Indexkerzen sind für diesen Trade-/Markvergleich nicht erneut importiert.

## Datenvertrag und Import

Eigene Version `binance-usdt-futures-hourly/1` in `binance_futures_hourly.py`.
Der bestehende H4-Vertrag und dessen BTC/ETH-Artefakte bleiben unverändert.
Die H1-Dateien binden eigene Venue, USDT-M-perpetual, Symbol, Preisart,
Intervall, exakte UTC-Achse und Digest. Legacy-H4-/Bitget-/Spotloader können
sie nicht als ihr Datenformat übernehmen.

Nur feste unsigned öffentliche GETs an `https://fapi.binance.com`:
`/fapi/v1/klines`, `/markPriceKlines`, `/fundingRate`. Keine Keys, Cookies,
Redirects oder automatischen Retries.15s Timeout,512KiB Antwort,1000 Zeilen
pro Page und mindestens0,1s Abstand. Explizite Grenzen30000 Stunden,
10000 Fundingevents und40 Pages pro Stream; keine stille Trunkierung.
Zehn vollständige H1-Streams benötigen270 GETs; Fundings separat.

Originale inklusive Kline-Schlusszeit muss exakt H1−1ms entsprechen.
Verkürzte, fremde, überlappende, unsortierte oder lückenhafte Kerzen verhindern
das Quellenartefakt. Funding behält signed Decimalraten, Millisekundenoffsets
und fehlende native Settlement-Markpreise als `None`. Keine Zeitrundung,
Nullersetzung oder Vermischung mit Bitgetfunding.
Die8h-Bucketdiagnose ist eine erklärte Diagnose, keine attestierte historische
Änderungsliste des Börsenkalenders.

```bash
python3 infra/scripts/import-futures-h1-history.py NEW_OUTPUT_DIRECTORY
```

CLI prüft den vorab festgelegten Protokollhash vor Ausgabe/Netzwerk.
Create-only Ziel und Dateien; jede gespeicherte Datei wird vor Aufnahme in
die abschließende Receipt vollständig zurückgelesen, decodiert und verglichen.
Die Receipt bindet alle Dateihashes, Datasetdigests und kanonischen nativen
Page-Antworthashes. Die Antworten sind nicht zusätzlich als Rohpages archiviert.
Ein abgebrochener Lauf erzeugt keine Erfolgsreceipt und überschreibt keine
bereits geschriebenen Quellen.

Lokales Ziel: ignoriertes
`infra/local/futures-h1-research-data/20261112-native-network/`.
Der erste sandboxgesperrte DNS-Versuch hinterließ nur`20261112-native/`;
der ausdrücklich autorisierte Netzwerkimport nutzt ein neues Ziel.

## Prüfungen und Leistungsgrenzen

22 neue Hostfälle und50 unterschiedliche gezielte gepinnte Quellen-/Importfälle
bestanden: zunächst49/78 Subtests, nach dem realen SOL-Befund17 H1-Fälle
mit34 Subtests einschließlich eines zusätzlichen Kalenderfalls.
Überschneidungen nicht addieren. Enthalten tatsächliche26304 synthetische Stunden über27 Pages,
native Zeitschranken, exakte komplette Fenster, Create-only/Fehlerzustände,
Fundingtimestamps, Missing-versus-zero sowie vollständiger Dateireadback.
Python3.14.10, vorhandenes Checkimage, zwei zusätzliche readonly Testmounts.
Keine neuen Dependencies, Migrationen, Broker-/Privatecalls oder Publicänderungen.

Die Quellenreceipt meldet weiterhin `net_backtest_ready=false` und
`performance_evaluated=false`. Fehlende ältere Settlement-Markpreise brauchen
einen erklärten wirtschaftlichen Nominalpreisbezug. Historische Kosten-/
Maintenance-/Liquidationsannahmen und die feinere Ausführungsreihenfolge
müssen für beide Schutzvarianten gleich eingefroren werden. Der neue
Kapital-/Signaladapter benötigt vor dem Marktvergleich vollständigen
Journalrestore und ausreichende Ereigniskapazität. AI bleibt aus.

## Tatsächlicher Import und Quellenabweichungen

15 Dateien, zehn identische lückenlose Stundenachsen:
**263040 native H1-Kerzen**, **16515 Fundingevents**, **295 öffentliche GETs**.
[Importreceipt und unabhängiger Artefaktabgleich](research-protocols/futures-h1-history-receipt-20261112.json)
binden die fünfzehn Dateihashes/Datasetdigests, Pagehashes und Legacyvergleich.

| Symbol | H1-Trade | H1-Mark | Native Fundingevents | Fehlende native Settlement-Marks |
| --- | ---: | ---: | ---: | ---: |
| BNBUSDT | 26304 | 26304 | 3288 | 1369 |
| BTCUSDT | 26304 | 26304 | 3288 | 1369 |
| ETHUSDT | 26304 | 26304 | 3288 | 1369 |
| SOLUSDT | 26304 | 26304 | 3363 | 1444 |
| XRPUSDT | 26304 | 26304 | 3288 | 1369 |

Alle erklärten8h-Buckets enthalten Ereignisse. SOL besitzt zusätzlich
75 originale Abrechnungen innerhalb dieser Buckets, vom2022-11-09T20:00Z
bis2022-11-18T06:00Z, mit nativen Millisekundenoffsets und `Regular`-Typ.
Das sind verschiedene native Timestamps, keine doppelt importierten Ereignisse.
Die Receipt meldet deshalb `all_funding_windows_match_declared_buckets=false`.
Diese Abrechnungen bleiben vollständig erhalten; die8h-Diagnose darf keine
native Frequenzänderung wegfiltern oder fehlende Zwischenraten erfinden.

BTC/ETH-Funding ist exakt identisch zur alten H4-Quellenbasis. Je Coin weichen
zwei aus H1 aggregierte Trade-H4-Kerzen und eine Mark-H4-Kerze von den alten
nativen H4-Daten ab: Trade2023-11-10T12:00Z und2024-10-28T20:00Z,
Mark2023-07-31T00:00Z. Sechs Abweichungen insgesamt, vollständige Preise
und beide Quellendigest-/Dateihashbindungen in der Receipt. Die Ursache ist
nicht verifiziert; keine stillen Korrekturen an den alten Artefakten.
Beide neuen Schutzvarianten sollen dieselbe H1-Quelle und ihre identische
H4-Aggregation verwenden. Ein älterer H4-Lauf ist kein exakt gleicher
Quellenvergleich.
