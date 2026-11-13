# Vergleich fester Baskethebel auf identischem Rastermodell

IP-086 setzt die Nutzerpriorität nach dem Merge von PR54 um: direkte
Vergleiche von2×,5× und10× unter derselben deklarierten Forschungsökonomie.
PR54 head0bcdcd2 ist Vorfahr von main9999671; GH/Fetch verifiziert.
Die vollständige Classic-Brokerkalibrierung bleibt ein eigener späterer
Vergleich und wird hier nicht zugleich als neue wirtschaftliche Regel eingeführt.

## Vorab eingefrorener Vergleich

[Protokoll](research-protocols/futures-capital-grid-leverage-20261113.json),
SHA256 `c2d458f9a62331e94c96865fa7bc4a78039a3996e7de89180abc716edc2a2ac3`.
Neue explizite `grid_leverage_comparison=True`-Auswahl;
`--h1-grid-leverage` startet ausschließlich die zwei nativen Fälle
`base-h1-5x` und `base-h1-10x` nacheinander auf dem2-GB-Host.
Die vollständig restaurierte2×-IP-085-Referenz wird mit allen vier
Originalartefakthashes wiederverwendet und nicht erneut berechnet.

Gleich bleiben2022-08-01..2025-08-01 exklusiv, native Binance-Preise/Funding,
10000 USDT, fünf feste Coins/Slots, H1-RSI/H1-Supertrend, alle sechs
Eigenkapitalbeträge und manuelle sechste Stufe. Nur der vor dem ersten Kauf
festgelegte Hebel ändert sich; er gilt für alle regulären Nachkäufe dieses
Baskets. Größere Nominalpositionen bedeuten echte höhere Gebühren/Funding
und frühere mögliche Liquidation, kein erfundener Cashzufluss.
Keine AI, Wiederanlage, Slotexpansion oder zusätzliche Kursquellen.

Aktuelle2026-Bitget-Raster/minima/Marketmaxima, adverse Preisticks,
0,1%-Entry-/Exitkosten,0,5%-Maintenance-/Liquidationskosten und die bisherige
exakte Margin-/Preisguardformel bleiben identisch. Funding debitiert eigenes
isoliertes Kapital; Restoration wahrt reguläres Entry-/Exitgebührenbacking.
Liquidation bleibt terminal, unverbrauchte reguläre/manuelle Stufen werden
nicht in Positionen hineingerechnet. Offene Endbaskets werden zum Mark bewertet;
kein profitabler Zwangsausgang.6%/8% bleiben Warnungen,−55%-Notexit erhalten.

Die neue Protokollachse wird zusätzlich zum Szenariodigest in die eigene
Gridplan-/Profilidentität gebunden. Alte2×-Griddefaults und deren Digest
`8bb5c87b6f42cd3ff5729eba0aa21e34316b812eba24081d75e239e34ade54d7`
bleiben unverändert;5×/10× ohne die neue explizite Auswahl werden weiterhin
abgelehnt. Das vollständige Journal enthält den tatsächlichen Hebel jeder
Kauf-/Leverageentscheidung und restauriert ausschließlich die eigene Genesis.

## Lauf und Abnahme

```bash
bash infra/scripts/check-paper-storage.sh -k 'GridLeverageResearchTests or CurrentGridResearchTests or EconomicProfileTests'
python3 infra/scripts/backtest-futures-capital.py --h1-grid-leverage NEW_OUTPUT_DIRECTORY
```

Gefrorene Protokoll-/Quellen-/Referenzreceipts werden vor dem Job geprüft.
Elf Implementationsdateien bleiben zwischen Start und vollständigem Restore
unverändert; bei Abweichung entsteht kein Erfolgsreceipt. Alle acht neuen
Artefakte sowie die vier ursprünglichen2×-Ausgaben werden danach erneut gehasht.
Die2×-Referenz wird im neuen Receipt ausdrücklich als wiederverwendet markiert.

Sechs neue/35 unterschiedliche fokussierte gepinnte Fälle und58 Subtests
bestehen: gleiche Kapital-/Kostenraster, unveränderter alter2×-Digest und
Flagschutz, konstantes Basketleverage, synthetische5×/10×-Marktjobs mit
vollständigen Restores und je fünf terminalen Gapliquidationen. Die zwei
Markt-/Gapfälle wurden nach ergänzter Fremdgenesis-Ablehnung gezielt erneut
geprüft (vier Subtests); keine breite Wiederholung unveränderter Suites.

Beide nativen Jobs/Restores und Hashabgleiche sind abgeschlossen:
130889 Commands/acht neue Artefakte/elf unveränderte Start-End-Hashes.
2× bleibt bei+95,97%/DD18,01%;5×+64,34%/DD29,44% mit vier Liquidationen,
10×−11,52%/DD18,15% mit fünf terminalen Liquidationen bis Oktober2022.
[Vollständige Ergebnisse und tatsächliche Handelsdauer](futures-grid-leverage-results-20261113.md).
Historische Brokerregeln, individuelle Kosten/USDT-Geldrundung sowie komplette
Classic-Orderfreeze-/Margin-/Preisguard-Abbildung sind weiterhin unbestätigt.
Dieser direkte Hebelvergleich beansprucht nur dieselbe deklarierte Modellachse;
keine Bitget-Orderzulassung, Holdout- oder Livefreigabe.

[2×-Referenzergebnis](futures-current-grid-results-20261113.md),
[Rastervertrag](futures-current-grid-comparison.md),
[Brokerkalibrierung](futures-broker-calibration.md).
