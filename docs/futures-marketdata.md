# Futuresdaten: Markt, Preisart und Funding getrennt

2026-11-10, IP-064. IP-063`0cf8a2b` in Main`6d06ec5` verifiziert.
Eigenes `futures-h4-snapshot/1` und `funding/1` statt Spotdaten umetikettieren.
Keine neuen Abhängigkeiten, Migrationen, Dienste oder Handelsfreigaben.

## Datenvertrag

`FuturesSnapshot` bindet Bitget Classic V2, USDT-M-Perpetual, Venue-Symbol,
UTC-H4 und Preisart `trade`/`mark`/`index`. Der SHA256 enthält diese Identität,
den festen öffentlichen Quellendpunkt und sämtliche begrenzten Decimal-OHLC.
Abrufzeit und angefragte Coverage stehen im vollständigen Dateirecord; sie
ändern wie bei Spot den inhaltlichen Datendigest nicht.

Die unveränderlichen Candles tragen beispielsweise
`BTCUSDT:USDT-M:mark`. Damit bleiben Markt/Preisart auch am alten Symbolkonverter
erhalten; der Spotkern lehnt diese Identität ab. Keine neuen Spotexports oder
Runtimewhitelist. Die20 bestätigten Kandidaten sind mögliche Dateninstrumente,
keine endgültige Performancekohorte. Spätere Futuresstrategie-Aufrufer müssen
Trade/Mark/Index ausdrücklich zusammenführen und gleiche Zeitachsen prüfen.

Nur geschlossene positive OHLC, exakte UTC-Ausrichtung, sortierte lückenlose
Tuplefolgen und passende Coverage. Leere Historien, Duplikate, innere Lücken,
unbekannte JSON-Felder, Digestmanipulation und Zukunftswerte scheitern.
Führende/abschließende Verfügbarkeitslücken stehen ausdrücklich in Coverage.
Keine Interpolation und keine unbekannten historischen Kontraktregeln.

`FundingSnapshot` bindet eigene UTC-Ereignisse und signed Decimalraten
zwischen−1 und+1, feste Quelle und exklusives angefragtes Ende.
Zeitpunkte sind streng steigend/eindeutig; maximal10.000 Ereignisse.
Negative Raten bleiben negativ; leere oder dünne Folgen bleiben sichtbar.
Keine angenommene8h-Folge, kein Auffüllen mit Null und **kein Nachweis
vollständiger Fundingabdeckung** allein durch einen Snapshot.

## Begrenzter Import und echte Abnahme

`BitgetFuturesHistoryAdapter` erlaubt ausschließlich drei öffentliche V2-
H4-Endpunkte, USDT-FUTURES, höchstens200 Kerzen/Page,52 Pages,10.000 Kerzen,
256KiB/Antwort,10s Timeout und mindestens50ms Pause zwischen Requests.
Keine Signatur, privaten Pfade, Redirects oder automatischen Wiederholungen.
Exakte Intervallgrenzen statt `end−1ms`; alle Queryfenster unter90 Tagen.
Provider-Reihenfolge wird sortiert, doppelte oder unplausible Pagegrenzen
scheitern. Fehlende Historie bekommt keine erfundene Vollständigkeit.

[Vorher eingefrorenes Importprotokoll](research-protocols/futures-history-20261110.json):
BTC/ETH, alle drei Preisarten,2022-08-01 inklusive bis2025-08-01 exklusiv.
Nur Datenabnahme, keine Strategie-, Kosten-, Hebel- oder PnL-Auswahl.

| Instrument | Trade-H4 | Mark-H4 | Index-H4 | Coverage |
|---|---:|---:|---:|---|
| BTCUSDT | 6576 | 6576 | 6576 | alle drei Jahre vollständig |
| ETHUSDT | 6576 | 6576 | 6576 | alle drei Jahre vollständig |

198 öffentliche Requests,39.456 geprüfte Kerzen. Alle sechs Zeitachsen stimmen
exakt überein. Je Datei strict Roundtrip, Dateihash und Datendigest geprüft;
Protokollhash im [Messrecord](research-protocols/futures-history-receipt-20261110.json).
Pagebelege enthalten URL, Abruf-/Providerzeit, Zeilenzahl und Hash des
kanonischen **dekodierten** Antwortobjekts, keinen Rohbytehash.
Daten liegen ignoriert in `infra/local/futures-research-data/20261110-network/`;
Git enthält Protokoll und Messrecord. Das Script legt Verzeichnisse/Dateien
nur neu an und publiziert den Gesamtbeleg erst nach allen sechs Importen.
Bei einem Fehler gibt es keine erfolgreiche Gesamtquittung.

```bash
python3 infra/scripts/import-futures-history.py /absolute/new/directory
```

Fundingtransport bleibt offen: die dokumentierte Classic-V2-Fundinghistorie
paginiert mit `pageNo`/`pageSize`, ohne Datumsfilter. Ein sauber begrenzter,
belegter Archivweg ist noch erforderlich; heutige Raten ersetzen keine Historie.
Keine private Kontoverbindung und kein Holdout angefragt oder ausgewertet.
Der vorhandene reservierte Spot-Holdout bleibt unverändert.

## Abnahme und nächste Arbeit

23 neue Hostfälle,81 gepinnte Python3.14.10-Marktdaten-/Workerfälle mit147
Subtests bestanden; vorhandene Snapshot-, Window- und Paperfeedpfade grün.
Unabhängiger Review ohne Blocker. Create-only-Verhalten, Transportabbruch ohne
Retry/Erfolgsquittung, fehlende Coverage, Preisart-Digests, Fundingvorzeichen,
JSON-Manipulation, UTC/Gaps und Spotverwechslung geprüft.
Der vorhandene Testhelper bindet nur Script/Protokoll zusätzlich readonly ein.

IP-064 Datenvertrag und erster vollständiger Historienimport abgeschlossen.
Weitere Kandidaten-/Fundingarchive und historische Maintenance-/Fee-/Precision-
annahmen bleiben BL-030/IP-055 vor vollständigen Leistungsläufen.
IP-063 Ereignisledger, Teilfills, Funding-/Gapreihenfolge und exakte
Regime-/Budget-/Hebelregeln stehen aus. Kein automatischer2×-Start oder
Hebelsprung pro Nachkauf: die ganze neue Position muss die bestehenden Gates
bestehen. Diese Datenabnahme weist keine Strategieprofitabilität nach.

Quelle: [offizielle Classic-V2-Marktdokumentation](https://www.bitget.com/docs/catalog/classic-contract-market/classic-contract-market).
