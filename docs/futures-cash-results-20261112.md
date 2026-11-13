# Korrigierter Futures-Budgetvergleich

IP-079: gleiche fünf native Coins, 10000 USDT, 2022-08-01 bis 2025-08-01
exklusiv. H4-RSI-Einstiege; H1/H4 bezeichnet den Supertrend-Schutz.
Alle zehn Wirtschaftsfälle unverändert. Korrigiert sind eigene Cashkosten
und volle aktive/neu beantragte Ranges. Keine KI, Reinvestition,
Gebührenkalibrierung, privaten Orders oder Holdoutauswertung.

| Variante | Vorher netto USDT | Korrigiert netto USDT | Differenz USDT | Max. DD % | Abschlüsse | Liquidationen | Käufe Stufen 1/2/3/4/5 |
|---|---:|---:|---:|---:|---:|---:|---|
| base-h1-2x | 687.70 | 2507.71 | +1820.01 | 9.86 | 107 | 1 | 107/38/16/6/2 |
| base-h4-2x | -7.28 | 2410.79 | +2418.07 | 11.03 | 106 | 1 | 106/38/16/6/2 |
| base-h1-5x | 1670.50 | 1372.91 | -297.58 | 17.96 | 59 | 3 | 59/20/9/4/1 |
| base-h4-5x | -213.35 | 3117.54 | +3330.89 | 13.52 | 47 | 2 | 47/15/6/1/1 |
| base-h1-10x | -625.65 | -1142.74 | -517.08 | 12.59 | 14 | 5 | 14/2/0/0/0 |
| base-h4-10x | -725.44 | -1080.99 | -355.55 | 12.53 | 12 | 5 | 12/2/0/0/0 |
| stress-h1-2x | 406.00 | 826.58 | +420.57 | 7.29 | 48 | 1 | 48/19/9/1/1 |
| stress-h4-2x | -11.88 | 487.74 | +499.62 | 5.96 | 24 | 1 | 24/10/5/0/0 |
| order-h1-2x | 659.81 | 1894.15 | +1234.34 | 11.34 | 107 | 1 | 107/38/16/6/2 |
| order-h4-2x | -7.28 | 2065.65 | +2072.93 | 11.00 | 106 | 1 | 106/38/16/6/2 |

Netto enthält gebuchte Gebühren, Funding und offene Endpositionen zum Markkurs.
Offene Baskets werden nicht für ein besseres Ergebnis zwangsweise geschlossen.
Preisablauf und Gapfills bleiben diskrete Modellannahmen, keine beobachteten
Ticks oder garantierten Stoppreise. Liquidierte Slots bleiben bis expliziter
Recovery gesperrt. Profite und niedrige Drawdowns sind keine Livefreigabe.

- **base-h1-2x:** letzte Schließung 2025-07-01T04:20:00Z; mittlere gestellte Eigenmargin 605.87 USDT; 0 offene Endbaskets; Halts keine.
  Finanzielle Ablehnungen: `{"fill_bound_below_mark": 6, "initial_margin_requirement": 13}`.
  Funding netto -33.13, Gebühren 141.19, Costrestoration 78.35 USDT.
- **base-h4-2x:** letzte Schließung 2025-07-01T20:20:00Z; mittlere gestellte Eigenmargin 701.74 USDT; 0 offene Endbaskets; Halts keine.
  Finanzielle Ablehnungen: `{"fill_bound_below_mark": 6, "initial_margin_requirement": 13, "insufficient_unposted_cash": 3}`.
  Funding netto -50.71, Gebühren 140.40, Costrestoration 124.66 USDT.
- **base-h1-5x:** letzte Schließung 2024-07-10T00:00:00Z; mittlere gestellte Eigenmargin 389.95 USDT; 0 offene Endbaskets; Halts ['basket_budget_breach'].
  Finanzielle Ablehnungen: `{"account_halted": 128, "fill_bound_below_mark": 6, "initial_margin_requirement": 3}`.
  Funding netto -33.74, Gebühren 213.61, Costrestoration 97.95 USDT.
- **base-h4-5x:** letzte Schließung 2024-03-02T08:00:00.001000Z; mittlere gestellte Eigenmargin 390.83 USDT; 0 offene Endbaskets; Halts ['basket_budget_breach'].
  Finanzielle Ablehnungen: `{"account_halted": 233, "fill_bound_below_mark": 6, "initial_margin_requirement": 3, "insufficient_unposted_cash": 3}`.
  Funding netto -15.18, Gebühren 148.53, Costrestoration 126.46 USDT.
- **base-h1-10x:** letzte Schließung 2022-12-17T02:20:00Z; mittlere gestellte Eigenmargin 16.13 USDT; 0 offene Endbaskets; Halts keine.
  Finanzielle Ablehnungen: `{"fill_bound_below_mark": 1, "initial_margin_requirement": 1}`.
  Funding netto 28.05, Gebühren 104.14, Costrestoration 0.22 USDT.
- **base-h4-10x:** letzte Schließung 2022-12-17T02:20:00Z; mittlere gestellte Eigenmargin 16.28 USDT; 0 offene Endbaskets; Halts keine.
  Finanzielle Ablehnungen: `{"fill_bound_below_mark": 1, "initial_margin_requirement": 1, "insufficient_unposted_cash": 4}`.
  Funding netto 30.23, Gebühren 97.16, Costrestoration 0.22 USDT.
- **stress-h1-2x:** letzte Schließung 2023-11-11T08:00:00Z; mittlere gestellte Eigenmargin 376.30 USDT; 0 offene Endbaskets; Halts ['basket_budget_breach'].
  Finanzielle Ablehnungen: `{"account_halted": 324, "fill_bound_below_mark": 1, "initial_margin_requirement": 1}`.
  Funding netto -48.19, Gebühren 130.29, Costrestoration 68.37 USDT.
- **stress-h4-2x:** letzte Schließung 2023-01-25T16:00:00.010000Z; mittlere gestellte Eigenmargin 115.83 USDT; 0 offene Endbaskets; Halts ['basket_budget_breach'].
  Finanzielle Ablehnungen: `{"account_halted": 589, "fill_bound_below_mark": 1, "initial_margin_requirement": 1, "insufficient_unposted_cash": 3}`.
  Funding netto -10.34, Gebühren 64.83, Costrestoration 41.42 USDT.
- **order-h1-2x:** letzte Schließung 2025-07-01T04:40:00Z; mittlere gestellte Eigenmargin 603.38 USDT; 0 offene Endbaskets; Halts keine.
  Finanzielle Ablehnungen: `{"fill_bound_below_mark": 6, "initial_margin_requirement": 13}`.
  Funding netto -31.16, Gebühren 140.57, Costrestoration 78.30 USDT.
- **order-h4-2x:** letzte Schließung 2025-07-01T20:40:00Z; mittlere gestellte Eigenmargin 694.60 USDT; 0 offene Endbaskets; Halts keine.
  Finanzielle Ablehnungen: `{"fill_bound_below_mark": 6, "initial_margin_requirement": 13, "insufficient_unposted_cash": 3}`.
  Funding netto -48.00, Gebühren 140.05, Costrestoration 124.09 USDT.

Alle zehn vollständigen Journalrestores erfolgreich: 666180 Commands,
40 geprüfte Artefakthashes. Erfolgsreceipt SHA256
`979880a5b9fdcadc1a8aa8f11f23e7e1af158c86b68d4ea3d27c2b282470476e`.
Host Python 3.14.4; gezielte Checks gepinnt auf Python3.14.10.
160 unterschiedliche gezielte Tests/101 Subtests bestanden; Eigenreview,
keine Agentdelegation oder breite Credential-/DB-/Frontend-Wiederholungen.

[Budgetvertrag](futures-cash-budgets.md),
[Ausgangsergebnisse](futures-market-results-20261112.md).
