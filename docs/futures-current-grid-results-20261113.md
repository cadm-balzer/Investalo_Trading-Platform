# H1-Futuresvergleich mit aktuellen Mengen- und Preisrastern

IP-085: Der vollständige native Lauf und Genesisrestore ergeben **+9596,82
USDT (+95,97%) bei18,01% maximalem Ereignisdrawdown**. Alle29 bisherigen
Initialmarginablehnungen entfallen. Gegenüber der eingefrorenen IP-082-Referenz
steigt das Netto um16,90 USDT und der Drawdown um0,40 Prozentpunkte.
Der wesentliche Fortschritt ist die gerasterte Orderberechnung; ein großer
Renditeoptimierungsgewinn ist daraus nicht abzuleiten.

Gleiche native Binance-Kohorte2022-08-01..2025-08-01 exklusiv,
10000 USDT, fünf feste Coinbaskets, H1-RSI/H1-Supertrend, festes2×
je Basket. Nur Mengen-/Preisraster, Mindestgrößen und Marketmaxima stammen
aus den aktuellen Bitget-Verträgen vom2026-11-13. Alle Eigenkapitalstufen,
manueller sechster Puffer,0,1%-Modellgebühren, Funding, Maintenance,
Liquidations-, Budget- und bisherige Preisguards bleiben unverändert.
Dies ist ein getrennter Rastervergleich; historische Binance-Zulassung oder
vollständige Bitget-Ökonomie sind nicht nachgewiesen.

| Kennzahl | IP-082-Referenz | Aktuelle Raster |
|---|---:|---:|
| Netto USDT einschließlich End-MTM | 9579,93 | 9596,82 |
| Rendite % | 95,80 | 95,97 |
| Maximaler Ereignisdrawdown % | 17,62 | 18,01 |
| Vollständig geschlossene Baskets | 269 | 273 |
| Positive / negative Abschlüsse | 229 / 40 | 233 / 40 |
| Liquidationen / globale Halts | 0 / 0 | 0 / 0 |
| Profitfaktor geschlossener Baskets | 6,59 | 6,70 |
| Gebühren USDT | 481,72 | 481,35 |
| Funding netto USDT | 333,28 | 330,14 |
| Marginablehnungen | 29 | 0 |
| Deklarierte Preisguard-Ablehnungen | 32 | 28 |

Der Wegfall der Marginablehnungen folgt aus Mengenfloor und gerasterten
Preisen unter derselben exakten Marginformel; keine Toleranz, Cashquelle oder
Grenzaufhebung wurde eingeführt. Referenzablehnungen überlappten teilweise;
die Zahlen sind Grundzählungen und dürfen nicht als unterschiedliche
entgangene Baskets addiert werden. Die vollständige IP-083-Diagnose zeigte,
dass fast alle verweigerten Stufen später ohnehin gefüllt wurden.

## Tatsächliche Einstiege und Abschlüsse

| Kaufstufe | Referenz | Aktuelle Raster |
|---|---:|---:|
| 1 | 271 | 275 |
| 2 | 126 | 128 |
| 3 | 72 | 72 |
| 4 | 37 | 37 |
| 5 | 24 | 24 |
| Gesamt | 530 | 536 |

24 Baskets nutzen alle fünf regulären Käufe; der manuelle sechste Einstieg
wird weiterhin nicht simuliert. Sämtliche536 tatsächlichen Käufe und273
Verkäufe wurden zusätzlich direkt im Journal gegen Mengenstep, Preistick
und Marketmaximum geprüft. Letzter Kauf2025-07-29T01:00:02+00:00,
letzter vollständiger Abschluss2025-07-28T13:20:00+00:00.
Maximal fünf Baskets gleichzeitig, maximale gebuchte Eigenmargin6444,36 USDT,
zeitgewichtete Eigenmargin1799,45 USDT.

| Coin | Abschlüsse | Positiv / negativ | Realisiertes Netto USDT |
|---|---:|---:|---:|
| BNB | 48 | 45 / 3 | 2048,95 |
| BTC | 42 | 37 / 5 | 1766,37 |
| ETH | 60 | 52 / 8 | 597,52 |
| SOL | 63 | 51 / 12 | 4017,34 |
| XRP | 60 | 48 / 12 | 1193,62 |

Realisiertes Netto9623,81 USDT plus offenes Netto−26,99 USDT ergibt
9596,82 USDT. BTC-Zyklus43 und SOL-Zyklus64 bleiben zum letzten Markkurs
bewertet offen. Es gibt keinen erzwungenen profitablen Endexit.
Fundingnetto+330,14 USDT ist im Ergebnis enthalten; tatsächlich aus der
eigenen Reserve bezahlte Restoration323,55 USDT erzeugt keinen Gewinn.

272 Abschlüsse tragen die gemeinsam gezählten Gründe
`protective_stop_crossed` und `net_breakeven_floor_crossed`; sie sind keine544
verschiedenen Exits.39 davon schließen zusammen mit−443,86 USDT netto,
da diskrete Kursbewegung und Ausführungskosten den Schutzpreis unterschreiten
können. Der verbleibende Verlust ist ETH-Zyklus52 mit fünf Käufen:
−1243,66 USDT beim−55%-Notausstieg am2025-04-07T06:20:00Z.
Die40 negativen Abschlüsse sind im Profitfaktor und Nettogewinn enthalten.

## Belege und weitere Kalibrierung

Der Job liegt unter
`infra/local/futures-capital-research/20261113-h1-current-grid`.
108427 Journalcommands und122675 gespeicherte Ereignis-IDs wurden vollständig
restauriert. Vier Ausgabehashes und elf Start-/Endimplementationshashes sind
verifiziert; das Erfolgsreceipt wurde erst danach unverändert exportiert.
Implementationscheckpoint vor Abschlussauswertung: `3e537c6`.

- [Vorab eingefrorenes Protokoll](research-protocols/futures-capital-current-grid-20261113.json):
  SHA256 `8f24a3f0d9a7ba0af3daf497bf5ed2925a5478db35da138ed96a2b95afe84a8d`.
- [Vollständiges Erfolgsreceipt](research-protocols/futures-capital-current-grid-market-receipt-20261113.json):
  SHA256 `727911a2f49e9814c9aa488ad365a4e451dc7ae86bd933d0d522acb9f95debfd`.
- [Unveränderte IP-082-Referenz](futures-reserved-budget-results-20261113.md):
  Receipt-SHA256 `4e7d902c7127b317932c75e3b3878ffcaa3971c7863f077f477d2ca490713cec`.

13 neue/122 unterschiedliche gezielte gepinnte Fälle und88 Subtests bestehen.
Das umfasst vollständige synthetische Restores, volle Eigenkapitalstaffel,
Nano-Funding/tatsächliche Unterdeckung und fünf terminale Gapliquidationen.
109 bestehende Fälle bestehen;24 nach der expliziten neuen Genesisfreigabe
nochmals gezielt geprüft. Keine breite Wiederholung unveränderter UI-/DB-Suites.
Dezimalabgleichrest−6E−32 USDT liegt unter dem Modellquantum1E−8.

Die28 verbleibenden `fill_bound_below_mark`-Ablehnungen sind weiterhin
unkalibrierte Modellguards. Als Nächstes folgt separat die vollständige
Classic-Orderfreeze-/Margin-/Preisguard-Abbildung vor einem weiteren
Hebelvergleich. Broker-Geldrundung, historische Tiers/Kosten und tatsächliche
Orderannahme bleiben offen. Gleiche deklarierte OHLC-Pfade und Quellen;
kein unabhängiger Holdout, keine Wiederanlage/Slotexpansion/AI oder
Paper-/Cockpit-/Liveaktivierung.

[Rechenvertrag](futures-current-grid-comparison.md),
[Brokerquelle und Grenzen](futures-broker-calibration.md),
[Referenzdiagnose](futures-admission-results-20261113.md).
