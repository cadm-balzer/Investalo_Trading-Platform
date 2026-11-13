# Native H1- gegen H4-RSI-Einstiege

IP-080: fünf feste Slots, 10000 USDT, BNB/BTC/ETH/SOL/XRP,
2022-08-01 bis 2025-08-01 exklusiv. Beide Varianten nutzen die korrigierte
volle Eigenkapitalstaffel, festes 2× pro Basket, H1-Supertrend und identische
Gebühren/Funding-/Margin-/Preisablaufannahmen. Nur RSI-Einstiegstimeframe
ändert sich; keine Parameteroptimierung, Reinvestition oder KI.

| Kennzahl | H4-RSI-Referenz | H1-RSI |
|---|---:|---:|
| Netto USDT | 2507.71 | 2643.89 |
| Rendite % | 25.08 | 26.44 |
| Max. Ereignisdrawdown % | 9.86 | 17.62 |
| Geschlossene Baskets | 107 | 43 |
| Gewinnbaskets | 95 | 36 |
| Verlustbaskets | 12 | 7 |
| Liquidationen | 1 | 0 |
| Mittlere gestellte Eigenmargin USDT | 605.87 | 383.02 |
| Maximale gestellte Eigenmargin USDT | 3437.91 | 5396.64 |
| Gebühren USDT | 141.19 | 93.57 |
| Funding netto USDT | -33.13 | 525.93 |

Tatsächliche Käufe Stufe1/2/3/4/5:

- H4: 107/38/16/6/2.
- H1: 43/23/15/9/7.

H1-Endzustand: 0 offene Baskets,
Halts `["basket_budget_breach"]`.
Letzter Basketabschluss: 2023-01-16T08:20:00Z.
Ein Halt oder terminal liquidierter Slot beendet künftige Käufe trotz weiterer
RSI-Signale; ein Dreijahresfenster beweist daher keinen durchgehenden Handel.

Der Halt ist exakt dem profitablen BTC-Zyklus4 zugeordnet. Er hält vom
2022-11-07 bis 2023-01-16 alle fünf tatsächlichen Käufe; Preisgewinn
468,93650847 USDT minus Gebühren6,24275219 und Funding15,85439330 ergibt
446,83936298 USDT Nettogewinn. Die Cashkosten beim vollständigen Exit
betragen22,09714550 statt19,80198020 USDT Reserve. Bereits nach dieser
Überschreitung von2,29516530 USDT sperrt die bisherige Policy das Konto
dauerhaft und erzwingt den Abschluss der anderen offenen Baskets.
Auslöser ist der vollständige `ExitFill` bei Journalcommand17473,
Kettenkopf `e0ebd47d36eef70f01da4e5ebb353ef395c4f19d4e5f7568bbe0e72425733adb`.
Diese aus den gebundenen Inputs gefaltete Kostenrechnung deckt sich mit
dem gespeicherten BTC-Abschluss; es ist kein offener Funding-/Cashmangel.

H1 erreicht häufiger große Stufen, aber nur etwa fünfeinhalb Monate aktiven
Handel. Die geringere mittlere Margin über drei Jahre enthält danach den
Stillstand. Maximaler Marginbedarf und Drawdown sind höher. Daraus folgt
keine allgemeine Überlegenheit oder Renditehochrechnung für H1.

Nächster in Q44 bestätigter separater Vergleich: ausschließlich
beim vollständig geschlossenen profitablen Basket eine Kostenreserve-
Überschreitung aus dessen eigenem realisiertem Gewinn decken. Alle Kosten
bleiben im Nettoergebnis. Keine Finanzierung aus anderen Baskets, keine
Freigabe zusätzlicher Nachkäufe und keine Änderung offener Kosten-/Margin-/
Liquidationsgrenzen. Das neue Profil wird vor seinem eigenen Lauf eingefroren;
dieses Resultat und die bisherige Policy bleiben unverändert.

Finanzielle Ablehnungen H1:
`{"account_halted": 2837, "fill_bound_below_mark": 58, "initial_margin_requirement": 53}`.
Signalfilter H1:
`{"first confirmation or actual-fill rearm missing": 1855, "maximum fill exceeds last actual stage five-percent drop": 346, "no regular entry signal; manual sixth has no automatic authority": 126359}`.

| Coin | Abschlüsse | Netto USDT | Liquidationen |
|---|---:|---:|---:|
| BNBUSDT | 7 | 424.28 | 0 |
| BTCUSDT | 4 | 516.89 | 0 |
| ETHUSDT | 13 | 348.83 | 0 |
| SOLUSDT | 9 | 1253.52 | 0 |
| XRPUSDT | 10 | 100.36 | 0 |

Vollständiger H1-Journalrestore und Dezimalabgleich geprüft:
46212 Commands, vier erneut geprüfte Artefakthashes.
Der Dezimalrest `−1E−32` USDT liegt unter dem gebundenen Quantum1E−8.
Erfolgsreceipt SHA256 `3c6fdfb5b1c5ec6129f9bc7e4c4f1368ec19761f06e0d628707f8b72f12ed130`.
85 unterschiedliche gezielte gepinnte Tests/57 Subtests bestanden,
sieben neue Fälle; Eigenreview ohne Agentdelegation.

Offene Endpositionen bleiben zum Markkurs bewertet. Sechste manuelle Tranche
bleibt reserviert und unsimuliert. Liquidierte Slots benötigen ausdrückliche
Recovery. Discrete OHLC-Preisfolge und Gapfills sind Modellannahmen;
historische Brokerregeln/Kostenkalibrierung bleiben offen. Holdout,
Cockpit-/Paperprofilwechsel, AI und Liveausführung bleiben aus.

[Eingefrorener Vergleichsvertrag](futures-h1-entry-comparison.md),
[vollständige H4-Einstiegsvarianten](futures-cash-results-20261112.md).
