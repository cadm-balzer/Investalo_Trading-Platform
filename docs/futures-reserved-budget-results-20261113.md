# H1-Futures mit reserviertem eigenen Budget

IP-082/Q45: gleicher nativer Dreijahresbestand, 10000 USDT, fünf feste Slots,
2× pro Basket, H1-RSI/H1-Supertrend. Funding bleibt vollständig im isolierten
Saldo und Nettogewinn. Nur tatsächliche Walletgebühren/Restoration verbrauchen
die Barreserve; Restoration hält reguläre Restkauf-/deklarierte Ausstiegsgebühren
zurück. Alle sechs Eigenkapitalstufen bleiben identisch.
Historische IP-081-Policy und Ergebnis bleiben eingefroren.
Die Referenz beendet Handel am2023-10-02; im neuen Profil liegt der letzte
tatsächliche Einstieg am2025-07-29. Der Unterschied ist Budgetverhalten,
keine Parameteroptimierung oder unabhängige Holdoutbestätigung.

| Kennzahl | Q44-Referenz | Reserviertes Budget |
|---|---:|---:|
| Netto USDT | 3928.28 | 9579.93 |
| Rendite % | 39.28 | 95.80 |
| Max. Ereignisdrawdown % | 17.62 | 17.62 |
| Abgeschlossene Baskets | 98.00 | 269.00 |
| Liquidationen | 0.00 | 0.00 |
| Mittlere Eigenmargin USDT | 931.48 | 1792.52 |
| Maximale Eigenmargin USDT | 6444.36 | 6444.36 |
| Gebühren USDT | 192.01 | 481.72 |
| Funding netto USDT | 552.98 | 333.28 |
| Tatsächlich gezahlte Restoration USDT | 106.44 | 327.74 |

Tatsächliche Kaufstufen1/2/3/4/5:

- Q44: 98/48/30/16/13.
- Reserviertes Budget: 271/126/72/37/24.

Letzter tatsächlicher Einstieg: 2025-07-29T01:00:02+00:00.
Letzter vollständiger Abschluss: 2025-07-28T13:20:00Z.
Endzustand: 2 offene Baskets,
Halts `[]`.
Finanzielle Ablehnungen: `{"fill_bound_below_mark": 32, "initial_margin_requirement": 29}`.
Ausstiegsgründe: `{"first_fill_emergency_exit": 1, "net_breakeven_floor_crossed": 268, "protective_stop_crossed": 268}`.

Funding wird nicht kostenlos und keine Margin erfunden. Nach aufgebrauchter
zulässiger Restoration können neue Käufe an tatsächlicher deklarierter
Initialmargin scheitern. Andere/unverbrauchte reguläre und manuelle
Eigenkapitalreserven ersetzen diese Margin nicht. Liquidierte Slots bleiben
terminal bis Recovery; neu gestartete vollständige Ranges benötigen echte
Gelddeckung. Auch ein ungehalteter Datensatz beweist keine fünf ausgeführten
Käufe in jedem Basket.

Vollständiger Journalrestore: 109440 Commands.
Vier Artefakte erneut gehasht, acht Implementationshashes sowohl gegen
Startmanifest als auch aktuellen Code geprüft. Receipt SHA256 `4e7d902c7127b317932c75e3b3878ffcaa3971c7863f077f477d2ca490713cec`.
183 unterschiedliche gezielte gepinnte Fälle/108 Subtests bestehen,
neun neue. Keine Agentdelegation oder breite Wiederholung unveränderter
Credential-/DB-/UI-Suites. Dezimalrest 4E-32
USDT unter Quantum1E−8.

Netto enthält offene Endpositionen zum Markkurs; keine erzwungenen
Profitabschlüsse am Forschungsende. Sechste Stufe bleibt manuell und
unsimuliert. Kosten/Marginschedules und diskrete OHLC-Fills sind deklarierte
Modelle; historische Brokerannahme und unabhängiger Holdout bleiben offen.
Keine Reinvestition, AI, Paper-/Cockpitprofiländerung oder echten Orders.

[Budgetvertrag](futures-reserved-budget.md),
[eingefrorene Referenz](futures-realized-cost-results-20261112.md).
