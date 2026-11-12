# Nativer Futures-Nettovergleich: eingefrorenes Ausgangsmodell

2022-08-01..2025-08-01, fünf feste Slots BNB/BTC/ETH/SOL/XRP,
10000 USDT Startkapital. H4-RSI-Einstiege; H1/H4 bezeichnet den Schutz.
Alle zehn vorab erklärten Fälle vollständig journalisiert und restauriert.
Die Renditen enthalten Modellstillstand durch Budget-/Kapitalablehnungen;
sie belegen keinen ununterbrochenen Dreijahreshandel.

| Variante | Netto USDT | Rendite | Ereignis-Drawdown | Geschlossen | Liquidationen | Käufe Stufe1/2/3/4/5 |
|---|---:|---:|---:|---:|---:|---|
| base-h1-2x | 687,70 | 6,88 % | 6,83 % | 51 | 1 | 51/18/7/1/1 |
| base-h4-2x | -7,28 | -0,07 % | 2,69 % | 5 | 0 | 5/2/0/0/0 |
| base-h1-5x | 1.670,50 | 16,70 % | 9,53 % | 43 | 2 | 43/12/4/1/0 |
| base-h4-5x | -213,35 | -2,13 % | 6,63 % | 5 | 1 | 5/2/0/0/0 |
| base-h1-10x | -625,65 | -6,26 % | 7,26 % | 5 | 2 | 5/1/0/0/0 |
| base-h4-10x | -725,44 | -7,25 % | 8,25 % | 5 | 2 | 5/1/0/0/0 |
| stress-h1-2x | 406,00 | 4,06 % | 7,29 % | 46 | 1 | 46/19/9/1/1 |
| stress-h4-2x | -11,88 | -0,12 % | 2,66 % | 5 | 0 | 5/2/0/0/0 |
| order-h1-2x | 659,81 | 6,60 % | 6,85 % | 51 | 1 | 51/18/7/1/1 |
| order-h4-2x | -7,28 | -0,07 % | 2,69 % | 5 | 0 | 5/2/0/0/0 |

| Variante | Letzter Abschluss | Zeitgewichtete Margin USDT | Gebühren | Funding netto | Modellversicherung | Endhalt |
|---|---|---:|---:|---:|---:|---|
| base-h1-2x | 2023-10-27T08:00:00Z | 343,04 | 63,75 | 38,15 | 29,04 | basket_budget_breach |
| base-h4-2x | 2023-01-30T19:20:00Z | 39,47 | 5,28 | -2,38 | 0,00 | kein terminaler Halt |
| base-h1-5x | 2023-07-30T16:00:00Z | 150,26 | 123,54 | 84,03 | 52,20 | basket_budget_breach |
| base-h4-5x | 2022-11-08T19:20:00Z | 26,15 | 15,66 | 1,37 | 31,54 | kein terminaler Halt |
| base-h1-10x | 2022-08-26T22:20:00Z | 6,15 | 41,91 | 14,31 | 26,06 | basket_budget_breach |
| base-h4-10x | 2022-08-26T22:20:00Z | 6,20 | 41,81 | 14,42 | 26,06 | basket_budget_breach |
| stress-h1-2x | 2023-09-19T16:00:00Z | 275,02 | 126,48 | 24,37 | 3,01 | basket_budget_breach |
| stress-h4-2x | 2023-01-21T10:20:00Z | 37,95 | 10,57 | -10,36 | 0,00 | kein terminaler Halt |
| order-h1-2x | 2023-10-27T08:00:00Z | 342,97 | 63,72 | 37,56 | 29,04 | basket_budget_breach |
| order-h4-2x | 2023-01-30T19:40:00Z | 39,49 | 5,28 | -2,38 | 0,00 | kein terminaler Halt |

Einzelbelege, offene Endpositionen, Warnungen, Kapitalablehnungen und
Artefakthashes: [Erfolgsreceipt](research-protocols/futures-capital-market-receipt-20261112.json).
Endbestände sind MTM; keine erzwungenen Gewinnabschlüsse. Drawdown enthält
Zwischenbewertungen vor modellierter isolierter Versicherungsdeckung.
Keine bestätigten historischen Brokergebühren/Order-/Margin-/Versicherungsregeln;
fehlende native Funding-Marks bleiben ausdrücklich H1-Open-Näherungen.
Die diskreten OHLC-Ausführungspfade sind Modelle, keine beobachteten Tickfolgen.
Kein Holdout, keine aktiven AI-Entscheidungen, keine echte Ausführung.

Budgetbremsen und nächster Schritt: [Marktjob und Diagnose](futures-market-backtest.md).
