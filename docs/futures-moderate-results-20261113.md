# H1-Futures: feste 2×/3×/4×/5×/10× im Vergleich

Gleiche deklarierte Modellregeln,10000 USDT/fünf Slots,2022-08-01 bis2025-08-01 exklusiv.
H1-RSI/H1-Supertrend, fünf reguläre Nachkaufstufen mit eigenem Kapital,
manuelle sechste Reserve nicht automatisch ausgeführt. Keine AI oder Recovery im Test.

| Hebel | Netto USDT | Rendite | Ereignis-Drawdown | Abschlüsse | Liquidationen |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2× | +9596.82 | +95.97% | 18.01% | 273 | 0 |
| 3× | +8523.18 | +85.23% | 23.54% | 208 | 2 |
| 4× | +9464.20 | +94.64% | 29.65% | 163 | 3 |
| 5× | +6434.15 | +64.34% | 29.44% | 116 | 4 |
| 10× | -1151.95 | -11.52% | 18.15% | 19 | 5 |

2× bleibt in dieser Kohorte die stärkste Referenz.4× liefert fast das gleiche
Netto wie2×, aber etwa11,63 Prozentpunkte zusätzlichen Drawdown und drei
Liquidationen.3× hat etwa5,53 Prozentpunkte mehr Drawdown und weniger Netto.
Das ist kein Beweis für eine universell optimale oder sichere Hebelwahl.

Empfehlung für die **nächste Forschungsplanung**, keine geänderte Freigabe:
2× als Basis,3×/4× als gesondert zu validierende Regimekandidaten;5×/10×
vorerst kein Standardprofil. Eine spätere AI-Auswahl braucht kausale damalige
Marktphasen, eingefrorene Kriterien und unabhängige Validierung. Der bisherige
genehmigte Forschungsrahmen2×–10× wird damit nicht still geändert.

## Neue tatsächlich ausgeführte Käufe und Liquidationen

| Hebel | Stufen 1/2/3/4/5 | Letzter tatsächlicher Einstieg (UTC) | Verfügbare Slots am Ende |
| --- | --- | --- | ---: |
| 3× | 209/100/51/23/14 | 2025-07-24 06:00:02 | 3 |
| 4× | 164/76/38/17/10 | 2025-07-15 07:00:02 | 2 |

3×: SOL-Zyklus6 am2022-11-09, eine Stufe,−176,41 USDT;
ETH-Zyklus52 am2025-04-06, fünf Stufen,−1458,93 USDT.
4×: SOL-Zyklus6 am2022-11-09, eine Stufe,−176,58 USDT;
XRP-Zyklus23 am2023-08-17, drei Stufen,−681,48 USDT;
ETH-Zyklus44 am2024-08-05, drei Stufen,−673,85 USDT.

Nach Liquidation bleiben betroffene Slots terminal.3× handelt am Ende noch
BNB/BTC/XRP,4× BNB/BTC. Beide haben zuletzt einen offenen BTC-Basket zum Mark
bewertet; kein profitabler Zwangsausgang und kein globaler Kontohalt.
10× hat schon seit Oktober2022 keinen verfügbaren Slot mehr; dessen18,15%
Drawdown bestätigt daher keinen drei Jahre aktiven risikoarmen Handel.

## Wiederherstellung und Beleg

Vorabprotokollsha79308ab0b727f848ec1c446b096a1c501392ab8592ae6d67fbbc39a0669b760e.
Original3×106752 Commands vollständig restauriert. Original4×-Marktinput
vollständig; Exit137 während Restore, Ursache unbestätigt. Originalausgabe
bleibt unverändert ohne Erfolgsreceipt. Ein nur lesender Beobachter restauriert
anschließend alle102760 vorhandenen4×-Commands ohne wiederholten Marktjob.
Insgesamt209512 Commands, acht neu exportierte Artefakte,13 unveränderte
Abschlussimplementationshashes; elf ursprüngliche native Dateien zusätzlich
gegen Checkpointada2029 geprüft. Alle zwölf2×-/5×-/10×-Originalartefakte und
sämtliche15 Quellen vor/nach Abschluss erneut gehasht.

[Unverändert exportierter Abschlussreceipt](research-protocols/futures-capital-grid-moderate-market-receipt-20261113.json),
SHA256 `0b382391c2fedb92d1c32a3094992a976f049c77b5dd09d769381066d8ad1b7c`.
Lokale Abschlussausgabe: `infra/local/futures-capital-research/20261113-h1-grid-moderate-completed`.

4×-Finanzkennzahlen stammen aus jedem bestätigten Journalereignis. Nicht
gespeicherte abgelehnte Versuche/Signalfilter/Warnungsstunden sind im4×-Bericht
ausgelassen, nicht als0 rekonstruiert.3× hat zwei deklarierte Margin- und22
Preisguardablehnungen; Einzelursachen wurden nicht zusätzlich auditiert.
Die Netto-/End-MTM-Reconciliationreste sind1E−32/4E−32.

38 fokussierte gepinnte Fälle/66 Subtests für Grundvergleich plus zusätzliche
Normal-/Gap-Finanzparität und fünf Recoveryfälle/13 Subtests bestehen.
Fünf Cockpitfälle, Typecheck und Next.js-Build bestehen.
Aktuelle2026-Bitget-Raster auf historischen Binance-Daten sind weiterhin
keine vollständige historische Classic-Brokerzulassung. Keine Live-/AI-/
Holdout-/Public-/DB-/Dependencyaktivierung.

[Recovery-Prüfkern und noch ausstehende Runtime-Anbindung](futures-manual-recovery.md).
