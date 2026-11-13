# H1-Futures nach bestätigter eigener Abschlusskostendeckung

IP-081/Q44: derselbe native Dreijahresbestand, 10000 USDT, fünf feste Slots,
2× pro Basket und H1-RSI/H1-Supertrend. Nur die eigene Kostendeckung beim
vollständigen profitablen Abschluss ändert sich. Alle Kosten bleiben netto
verbucht; keine Reinvestition, AI oder Änderung offener Grenzen.

| Kennzahl | H1 bisher | H1 mit Q44 |
|---|---:|---:|
| Netto USDT | 2643.89 | 3928.28 |
| Rendite % | 26.44 | 39.28 |
| Max. Ereignisdrawdown % | 17.62 | 17.62 |
| Abgeschlossene Baskets | 43 | 98 |
| Liquidationen | 0 | 0 |
| Mittlere Eigenmargin USDT | 383.02 | 931.48 |
| Maximale Eigenmargin USDT | 5396.64 | 6444.36 |
| Gebühren USDT | 93.57 | 192.01 |
| Funding netto USDT | 525.93 | 552.98 |

Tatsächliche Stufen1/2/3/4/5:

- Bisher: 43/23/15/9/7.
- Q44: 98/48/30/16/13.

Ein vollständiger profitabler Abschluss weist eigene Kosten über
der Reserve und ausreichend eigenen Nettogewinn auf. Der ursprüngliche
BTC-Zyklus4 schließt mit unverändert 446,84 USDT netto; dessen 2,30 USDT
Kostenüberhang beendet den Handel im neuen Profil nicht.

Endzustand: 0 offene Baskets,
Halts `["basket_budget_breach"]`.
Letzter Abschluss: 2023-10-02T08:00:00Z.

Der nächste strikte Kostenhalt ist aus den gebundenen Inputs gefaltet:
BINANCE:XRPUSDT, Zyklus21,
2023-10-02T08:00:00+00:00, Command43858 (funding_batch).
Kostenverbrauch 19.941014711546755565868399 bei Reserve 19.80198020 USDT;
Gebühren 2.8869085190269969650, Funding netto -17.054106192519758600868399,
Restoration 16.83637222 USDT.
Kettenkopf `674e628a2e3b6de2c97c5c9bf4987cc793460713a4e237c203f5f9f458eb4d20`.
Q44 gibt offene Kostenüberschreitungen ausdrücklich nicht frei.
Ein Dreijahresfenster beweist deshalb weiterhin keinen durchgehenden Handel.

Die Überschreitung beim offenen XRP-Basket beträgt 0,13903451 USDT.
Die unveränderte 1%-Kostenreserve bleibt damit ein enger Kostenrahmen für
längere Futures-Haltedauern. Vor einem nächsten Variantenlauf müssen
Fundingreserve, erwartete Haltedauer und vollständige eigene Budgetdeckung
zusammen dimensioniert werden. Diese Auswertung erhöht keine offenen Limits.

Finanzielle Ablehnungen: `{"account_halted": 1942, "fill_bound_below_mark": 42, "initial_margin_requirement": 42}`.

Vollständiger Journalrestore: 64277 Commands,
vier erneut geprüfte Artefakthashes, acht unveränderte Implementationshashes.
Erfolgsreceipt SHA256 `893bfedeb260b9f4b44589c2719a9135e4876ceda72c87f6285a5294b0c952db`.
174 unterschiedliche gezielte gepinnte Tests/103 Subtests bestanden,
14 neue Fälle über IP-080/081; Eigenreview ohne Agentdelegation.
Dezimalrest 0E-32 USDT unter Quantum1E−8.

Netto enthält offene Endpositionen zum Markkurs. Die sechste manuelle Stufe
bleibt reserviert und unsimuliert. Liquidierte Slots benötigen Recovery.
Diskrete OHLC-Fills und historische Kosten-/Marginregeln bleiben Modelle.
Holdout, AI, Paper-/Cockpitprofilwechsel und Liveausführung bleiben aus.

[Bestätigter Vertrag](futures-realized-exit-costs.md),
[H1-Referenz und ursprünglicher Auslöser](futures-h1-entry-results-20261112.md).
