# H1/H4 mit vollständiger Basket-Kapitalplanung

IP-072,2026-11-11. Nutzer beauftragt H1-Forschung und einen H4-Vergleich mit
dem bestätigten größeren Basketprofil. IP-071`32fd13c` ist in Main`d749081`
verifiziert. Die vorherigen228,72 USDT waren die alte BTC-/ETH-Spotreferenz
mit500 USDT Principal je Basket.

## Vorab eingefrorener Vergleich

Ein gemeinsames10.000-USDT-Konto, dieselben fünf bestätigten Kandidaten
BNB/BTC/ETH/SOL/XRP, vollständige Kapitalplanung auf drei beziehungsweise
fünf wiederbelegbare Slots. Je Slot1% Principal-Kostenreserve. Alle sechs
wachsenden Beträge sind geplant; Stufe6 bleibt manuell und wird nicht erfunden.
Kein Zwang, alle Slots zu belegen. Normale vollständig abgeglichene Exits
erlauben Wiederbelegung; Risk-Stopps bleiben gesperrt. Gewinnetappen bis sieben
Slots sind eine separate Variante, hier gelten feste ursprüngliche Budgets.

2022-08-01..2025-08-01 exklusiv. Eigene native Binance-Spot-H1-Quelle;
H4 ist die OHLC-Aggregation derselben vier Stunden. Keine Bitgetidentität
oder Futuresrendite behauptet. Vier Grundläufe: H1/H4 mit drei/fünf Slots;
zwei weitere vorab bestimmte Kostenstressläufe: fünf Slots mit verdoppelter
Fee, Spread und Slippage. Alle sechs Fälle berichten, keine Parametersuche,
kein Zugriff auf den reservierten Holdout.

RSI14/Wilder: zwei geschlossene Kerzen<30 für Stufe1; nach tatsächlichem
Kauf erst RSI>30, anschließend<30 und mindestens5% unter dem letzten
tatsächlichen Fill-VWAP für Stufen2–5. Beträge wachsen25%.
Supertrend ATR10/Wilder×3 verwendet ebenfalls den jeweiligen Zeitrahmen,
kein H4-Regime/H1-Einstiegsmix. Aktivierung ab+5%, Nettofloor und Kaufstopp.
−55%-Exit,6% UTC-Tages-/8% ursprünglicher Startkapitalverlust und zusätzliche
gemeinsame−50%-Kaufstressprüfung bleiben unverändert.

## Deklarierte native Unterbrechung

2023-03-24 fehlt die13-Uhr-Kerze; die12-Uhr-Kerze wurde vorzeitig geschlossen.
Der erste strikt lückenfreie Import scheiterte vor jeder Marktleistungsrechnung.
Sein Protokoll mit SHA256
`cabb7d57814f974086dcacc78dab412f62669988ad03fa6fd419508dbbd574e5`
bleibt im ignorierten lokalen Fehlversuchsverzeichnis erhalten.
Vor dem ersten Leistungslauf wurde12:00–16:00 UTC für sämtliche Assets und
beide Zeitrahmen ausgeschlossen. Kein Ersatzpreis/Forwardfill/Lookahead.
Native verkürzte Schlusszeiten bleiben separat im Quellenbeleg. Jede andere
Datenlücke, Doppelkerze oder Zeitachsenabweichung bricht ab.

An der Unterbrechung Kaufaufträge stornieren und Wilder/RSI-Bestätigung
neu starten. Cash, Mengen, Einstand, Stufen, Schutzstopps, Halts und sämtliche
alten Kerzenbelege erhalten. Das nächste bekannte Open bewertet Positionen
und prüft Schutz/Risiko vor neuen Käufen. Keine Rekonstruktion der Kursbewegung
innerhalb der Unterbrechung.

Phasen: synchrones Open→Low→High→Close; Low nach¼, High nach½ der jeweiligen
Kerzendauer. Kauf aus geschlossenem Signal frühestens am nächsten Open.
Mitternacht prüft den alten Tagesverlust am vorherigen Schluss-Bid und setzt
die neue Basis vor dem Open-Gap. Endsignale stornieren; offene Bestände am
letzten Bid bewerten, keine erfundene Schlussliquidation. Die Phasen sind
Modellannahmen, keine historische Tickreihenfolge.

## Implementierung und Wiederholung

`timeframe_spot.py`: kanonische unsigned GETs am festen öffentlichen Endpoint,
ohne API-Schlüssel/Redirects/Retry;1000 Stunden je Seite,30000 je Asset,
15s Timeout,512KiB Antwort,8MiB Snapshot. Vor Leistung create-only Manifest
mit Quellen-/Datei-/Datasetdigests versiegeln.

`TimeframeReplay` verwendet den vorhandenen Pool-/RSI-/Fill-/Allokatorkern.
Normaler `Candle` und normaler Enginepfad bleiben H4. Nur der eigenständige
Offlineadapter akzeptiert H1. Default-Hooks für Dauer/Fingerprint/Belegablage
erhalten die bisherigen Werte. Sämtliche Kerzen-IDs/Digests bleiben je Asset
in einer immutable begrenzten Historie; auch alte Duplikate sind idempotent,
Revisionen werden abgewiesen. Kein Verwerfen oder Runtime-/DB-/Paper-Restore.

```sh
python3 infra/scripts/research-timeframes.py freeze
python3 infra/scripts/research-timeframes.py import NEW_SOURCE_DIRECTORY
python3 infra/scripts/research-timeframes.py seal SOURCE_DIRECTORY
python3 infra/scripts/research-timeframes.py run SOURCE_DIRECTORY NEW_RESULT_DIRECTORY
```

Freeze/import/seal/output sind create-only; vor Auswertung gesamte Policy
und versiegelte Dateien erneut prüfen. Rohdaten, Kurven und Fehlversuche sind
ignorierte lokale Artefakte. Keine Migration/neue Runtimeabhängigkeit,
private Brokerverbindung oder Paper-/Cockpit-/Publicaktivierung.
Spotkosten/Präzision sind Modelle; Futuresfunding/Liquidation, kalibrierte
reale Kosten und unabhängiger Holdout bleiben getrennte Abnahmen.

## Tatsächliche Dreijahresergebnisse

Netto einschließlich Bewertung offener Bestände, nicht jährlich.
Nachkäufe zählen ausgeführte reguläre Stufen2–5; Stufe6 wurde nie erfunden.

| Zeitrahmen / Slots | Netto USDT | Kontorendite | Max. Drawdown | Geschlossene Baskets | Nachkäufe | Mittlerer Einstand / Konto |
|---|---:|---:|---:|---:|---:|---:|
| H1 /3 | +725,04 | 7,25% | 6,75% | 72 | 27 | 9,48% |
| H4 /3 | +1.251,79 | 12,52% | 4,16% | 59 | 28 | 6,33% |
| H1 /5 | +985,30 | 9,85% | 5,26% | 136 | 66 | 9,64% |
| H4 /5 | +1.064,30 | 10,64% | 3,81% | 87 | 47 | 6,99% |

Fünfte reguläre Stufe in keinem Fall ausgeführt. H1/fünf erreichte Stufen
1/2/3/4 jeweils137/49/14/3-mal, H4/fünf87/34/10/3-mal. Die zusätzliche
Stressprüfung lehnte1740 H1- beziehungsweise186 H4-Kaufversuche ab.
Das sind wiederholte Versuche, keine unabhängigen Signale oder Baskets;
H1 hat auch viermal so viele Kerzen. H1 führt mehr Nachkäufe/mehr mittleres
Kapital aus, erzielt hier dennoch weniger Nettoertrag und höheren Drawdown.
Im Drei-Slotprofil sind Nachkäufe nahezu gleich häufig.

H4/drei zeigt in den drei August-Jahresabschnitten+182,87/+433,75/+635,16
USDT; H1/drei+200,13/+666,81/−141,90 USDT. Diese Teilfenster sind derselbe
Forschungslauf, keine unabhängige Validierung. Peakdrawdown ist weder
UTC-Tagesverlust noch Verlust zum ursprünglichen Startkapital.
Kein Lauf löste einen Kontohalt aus.

| Fünf Slots mit doppelten Modellkosten | Netto USDT | Max. Drawdown | Geschlossene Baskets |
|---|---:|---:|---:|
| H1 | +1.015,72 | 5,91% | 131 |
| H4 | +1.554,99 | 5,08% | 79 |

Höhere Kosten verändern tatsächliche Kaufpreise,5%-Nachkauflimits,
+5%-Schutzaktivierung, Nettofloor und dadurch die folgenden Zyklen.
Hier entsteht trotz höherer Kosten ein höherer Endgewinn; das ist kein
wirtschaftlicher Vorteil höherer Gebühren, sondern deutliche Pfadsensitivität.
Der zusätzliche isolierte Filltest bestätigt tatsächliche0,2%-Gebühren,
verdoppelten Spread/Slippage und niedrigere Equity bei identischem kurzem
Positionspfad. Deshalb keine reine Gebühren-Subtraktion oder Kostenrobustheit
aus positivem Endgewinn behaupten. Vor Promotion Ausführungs-/Stoppsensitivität,
einschließlich H4-Signalen auf feinerer Ausführungszeitachse, separat prüfen.

Die alte228,72-USDT-Referenz verwendet zwei Coins, kleinere Budgets und eine
andere Venuequelle. Die Differenz zu diesen neuen Werten ist deshalb nicht
allein der Kapitaländerung zuzuschreiben. Nur H1/H4 innerhalb desselben
Slot-/Kostenprofils ist der hier kontrollierte Vergleich.

Vorläufig H4 als Referenz behalten; H1 liefert im untersuchten Modell keinen
Netto-/Drawdownvorteil. Kein automatisch promoviertes Betriebsprofil.
[Alle exakten Ergebnisse/Digests](research-protocols/h1-h4-baskets-result-20261111.json)
und [37 monatliche Equitystände](research-protocols/h1-h4-baskets-monthly-20261111.csv).
Monatsdaten verwenden den vorherigen Schluss vor dem gleichzeitigen Open-Gap;
Drawdown/Kennzahlen stammen aus sämtlichen modellierten Phasen.

## Abnahme

135 öffentliche GETs; je Coin26303 native Stundenkerzen, dieselbe eine
fehlende/verkürzte Stunde dokumentiert. Evaluierung je26300 H1/6575 H4;
sämtliche Kerzenbelege erhalten. Sechs tatsächliche Marktläufe vollständig,
jede volle Kurve gegen Policy/Dataset/Phasenanzahl/Netto-Endwert geprüft.
Protokoll-SHA256:
`d4e61007ada5b9916fa96a0a9e3c60346881562cf9e4a5cf977444c1a73ba218`.

18 neue Prüfungen,356 unterschiedliche gepinnte Fälle insgesamt:
355 Trading/neue Quelle, abschließende64 betroffene Fälle und ein zusätzlicher
Kosten-Fillfall; Überschneidungen nicht addieren. Synthetische H4-Parität
mit bestehendem Pool sowie echte alte Dreijahresbaseline exakt reproduziert
(228,71690900701892163585 USDT,56 Abschlüsse; Config/Cost/Datadigests identisch).
Eigenreview, Syntax/Diff grün; keine weiteren Agents oder breiten
Credential-/PostgreSQL-/Cockpitwiederholungen. Laufende Dienste unverändert.
