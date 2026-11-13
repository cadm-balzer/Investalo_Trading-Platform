# Feste2×/5×/10×-Baskethebel auf gleicher H1-Rasterökonomie

IP-086: **Im deklarierten festen Hebelvergleich erzielt2× das beste Netto.**
5× schließt positiv, hat aber vier Liquidationen und einen deutlich höheren
Drawdown.10× verliert alle fünf Slots bis Oktober2022. Terminale Slots
werden im bisherigen Modell nicht automatisch wieder belegt; deshalb ist
10× ausdrücklich kein durchgehend aktiver Dreijahreshandel.

Verglichen werden dieselben nativen Binance-Preise und Fundings von
2022-08-01..2025-08-01 exklusiv,10000 USDT, fünf feste Coins/Slots,
H1-RSI/H1-Supertrend, aktuelle2026-Bitget-Raster und dieselben deklarierten
Kosten-/Margin-/Preisguards. Der vor dem ersten Kauf festgelegte Hebel
bleibt für das ganze Basket und sämtliche Nachkäufe konstant. Alle sechs
Eigenkapitalbeträge bleiben identisch; die sechste Stufe bleibt manuell
und unsimuliert. Keine AI, Gewinnwiederanlage oder Slotexpansion.

## Kontovergleich

| Kennzahl |2×-Referenz|5×|10×|
|---|---:|---:|---:|
| Netto einschließlich End-MTM USDT |9596,82|6434,15|−1151,95|
| Rendite % |95,97|64,34|−11,52|
| Maximaler Ereignisdrawdown % |18,01|29,44|18,15|
| Vollständige Abschlüsse einschließlich Liquidationen |273|116|19|
| Positive / negative Abschlüsse |233 / 40|97 / 19|11 / 8|
| Liquidationen |0|4|5|
| Noch verfügbare nichtliquidierte Slots am Ende |5|1|0|
| Offene Baskets am Ende |2|1|0|
| Globale Kontohaltes |0|0|0|
| Profitfaktor abgeschlossener Baskets |6,70|2,91|0,51|
| Gebühren USDT |481,35|530,06|194,61|
| Funding netto USDT |330,14|−48,00|71,44|
| Tatsächlich bezahlte Restoration USDT |323,55|226,45|0,00|
| Initialmarginablehnungen |0|105|4|
| Alte Modellpreisguard-Ablehnungen |28|15|0|
| Zeitgewichtete gebuchte Eigenmargin USDT |1799,45|786,27|32,16|

Die kleinere10×-Drawdownzahl gegenüber5× bedeutet keine bessere
Weiterhandelsfähigkeit: alle fünf Slots sind bereits früh terminal,
spätere Marktbewegungen haben im flachen Konto keine Positionswirkung mehr.
7592,56 USDT unverbrauchtes reguläres/manuelles Stufenkapital werden bei
10× nicht als Liquidationsverlust verbucht. Das verbleibende Kontokapital
wird ohne validierte Recoveryregel nicht automatisch neu zugeteilt.
Bei5× bleiben4960,37 USDT unverbrauchtes Stufenkapital der vier
liquidierten Baskets erhalten; ab August2024 handelt nur noch BTC.
Es gibt keinen globalen Budgethalt, dennoch einen terminalen Slotstillstand.

Die105/4 Initialmarginablehnungen entstehen unter derselben unveränderten
exakten Modellformel und eigenen Restoration-/Gebührenbackinggrenze.
Größere Positionen verbrauchen mehr Funding/Kosten. Ihre Einzelursachen
wurden hier nicht erneut mit einem vollständigen Admissionaudit zerlegt;
keine pauschale Geldtoleranz oder zusätzliche Kapitalquelle wurde eingeführt.
Der bisherige unkalibrierte Preisguard bleibt erhalten. Damit ist die
Hebelachse isoliert; vollständige Classic-Brokerannahme bleibt separat.

## Nachkäufe, tatsächliche Handelsdauer und Coinbeiträge

| Tatsächliche Kaufstufe |2×|5×|10×|
|---|---:|---:|---:|
|1|275|117|19|
|2|128|60|7|
|3|72|28|3|
|4|37|11|0|
|5|24|7|0|
|Gesamt|536|223|29|

Bei5× nutzen sieben Baskets alle fünf regulären Käufe. Bei10× kommt
keines bis zur vierten Stufe. Die nicht ausgeführten regulären und manuellen
Käufe werden weder als virtuelle Margin noch als spätere Rettung verbucht.

| Coin | Realisiertes Netto2× USDT | Realisiertes Netto5× USDT | Realisiertes Netto10× USDT |
|---|---:|---:|---:|
|BNB|2048,95|30,09|−677,24|
|BTC|1766,37|4165,35|−358,25|
|ETH|597,52|2644,85|−140,70|
|SOL|4017,34|18,48|−256,87|
|XRP|1193,62|−408,79|281,12|

Höherer Hebel steigert einige Coinbeiträge, etwa BTC/ETH bei5×.
Dem stehen direkte Liquidationsverluste und fehlender späterer Handel
gegenüber. Die kleineren Gebühren bei10× folgen vor allem der frühen
Einstellung des Handels; sie sind keine günstiger angenommene Kostenachse.

Letzte tatsächliche Käufe:

- 2×:2025-07-29T01:00:02+00:00; BTC und SOL am Ende zum Mark bewertet offen.
- 5×:2025-07-15T07:00:02+00:00; nur BTC-Zyklus42 am Ende offen.
- 10×:2022-10-11T04:00:02+00:00; letzte Liquidation2022-10-13T10:20:00+00:00.

5×:6449,98 realisiertes Netto plus−15,83 offenes Netto =6434,15 USDT.
10×:−1151,95 USDT vollständig realisiert, keine Endposition.
Kein erzwungener profitabler Endexit.

## Terminale Liquidationen

| Hebel | Coin / Zyklus | Abschluss UTC | Ausgeführte Stufen | Nettoverlust USDT |
|---|---|---|---:|---:|
|5×|XRP10|2022-11-08 19:20|3|−674,07|
|5×|SOL6|2022-11-09 08:20|1|−176,76|
|5×|BNB15|2023-08-21 10:20|5|−1450,66|
|5×|ETH44|2024-08-05 01:20|3|−674,65|
|10×|SOL2|2022-08-19 06:20|2|−399,68|
|10×|BTC2|2022-08-28 23:20|2|−399,68|
|10×|BNB1|2022-09-06 18:20|3|−677,24|
|10×|ETH6|2022-09-18 21:20|3|−677,22|
|10×|XRP8|2022-10-13 10:20|1|−177,64|

Liquidationsnetto gesamt−2976,15 USDT bei5× und−2331,47 bei10×,
bereits vollständig im Kontonetto enthalten. Das bestehende diskrete
OHLC-/isolierte Versicherungsmodell begrenzt negative Settlementrückzahlungen
mit deklariertem Insurancecredit:568,82/270,10 USDT bei5×/10×.
Dies ist kein historischer Brokerbeleg. Liquidationsgebühren werden im
isolierten terminalen Settlement abgezogen; eine verbrauchte Position
oder deren Slot wird dadurch nicht wieder eröffnet. Normale Q44-Profit-
Kostenfreigabe ist keine Liquidations-Recovery.

## Reproduktion und nächste getrennte Varianten

Implementationscheckpoint vor nativer Performance: `8e440e2`.
Lokaler Job `infra/local/futures-capital-research/20261113-h1-grid-leverage`:
5×96344 und10×34545 Commands, insgesamt130889 vollständig restauriert;
110592/48793 gespeicherte Ereignis-IDs. Acht neue Ausgabehashes und elf
unveränderte Start-/Endimplementationshashes erneut bestätigt. Alle252
neuen tatsächlichen Käufe sowie112/14 normalen und4/5 Liquidationsausstiege
wurden zusätzlich direkt gegen Mengen-/Preisraster/Marketmaximum geprüft;
sämtliche Leverageentscheidungen und Kaufanfragen tragen den festen Szenariohebel.

Die2×-Referenz wird unverändert aus IP-085 wiederverwendet. Ihr früherer
vollständiger Restore ist durch das eingefrorene Receipt belegt. Receipt und
alle vier Originalartefakte wurden vor/nach dem neuen Job geprüft;
keine erneute native2×-Simulation.35 fokussierte gepinnte
Fälle/58 Subtests bestehen, sechs neue. Zwei ergänzte Restorefälle nochmals
gezielt geprüft; keine breite Wiederholung unveränderter Suites oder Agenten.
Dezimalabgleichreste−3E−32/0E−32 USDT liegen unter Modellquantum1E−8.

- [Vorabprotokoll](research-protocols/futures-capital-grid-leverage-20261113.json):
  SHA256 `c2d458f9a62331e94c96865fa7bc4a78039a3996e7de89180abc716edc2a2ac3`.
- [Unverändert exportiertes Erfolgsreceipt](research-protocols/futures-capital-grid-leverage-market-receipt-20261113.json):
  SHA256 `a1c7c03a0e6487f22024edf586d5a0378e88fe16beed764e4af4de1e00786dde`.
- [2×-Referenz](futures-current-grid-results-20261113.md):
  Receipt-SHA256 `727911a2f49e9814c9aa488ad365a4e451dc7ae86bd933d0d522acb9f95debfd`.

Dieser Vergleich validiert keinen selektiven Marktphasen-/AI-Hebel.
Die feste Erhöhung auf jedem RSI-Signal ist im vorhandenen Modell schlechter
als2×. Ein eigener kausaler Regimevergleich benötigt vorab festgelegte
Kriterien; eine Wiederbelegung nach Liquidation benötigt eine separate
Reconciliation-/Recovery- und reale Kapitaldeckungsregel. Beide Achsen
bleiben getrennt von der vollständigen Classic-Margin-/Kostenkalibrierung
und einem unabhängigen Holdout. Keine aktuelle Policy/Terminalregel geändert,
keine DB-/Dependency-/Paper-/Public-/AI-/Live-/Holdoutaktivierung.

[Vergleichsvertrag](futures-grid-leverage-comparison.md),
[2×-Rastervertrag](futures-current-grid-comparison.md),
[Brokerquelle und offene Kalibrierung](futures-broker-calibration.md).
