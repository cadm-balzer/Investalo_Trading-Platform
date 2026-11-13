# Getrennter Futuresvergleich mit aktuellen Brokerrastern

IP-085 ist ein eigener Rastervergleich auf der bestehenden nativen
Binance-Kohorte2022-08-01..2025-08-01, fünf feste Slots/10000 USDT,
H1-RSI/H1-Supertrend und festes2× je Basket. Referenz ist der vollständig
restaurierte Q45-Lauf IP-082, nicht ein erneut berechneter Baselinejob.
PR53 headfa993f5 ist Vorfahr von main174ac6f; GH/Fetch geprüft.

## Vor der Performance eingefrorene Achse

[Protokoll](research-protocols/futures-capital-current-grid-20261113.json),
SHA256 `8f24a3f0d9a7ba0af3daf497bf5ed2925a5478db35da138ed96a2b95afe84a8d`.
[Aktuelle Bitget-Quelle](futures-broker-calibration.md) vom2026-11-13,
ausgewählte Metadaten-SHA256
`2fd4704081bdf1df22d45b56780cfd7c1ffc6c18cb8dac97b9a6c83e331091f6`.
Die Quelle ist ausdrücklich keine historische Binance-Orderzulassung.

Die neue `CapitalGridPlan`-Policy
`isolated-usdt-capital-current-grid/5` bindet alle Mengen-/Preisschritte,
aktuelle Market-Ordermaxima und den Quellendigest in die Plan-/Profilidentität.
Die vorhandene H1-Journaldomäne erhält einen explizit getrennten
Plan-Discriminator und vollständige Genesisfelder. Alte Policies1–4,
Defaultprofile und deren Digests bleiben erhalten.

Neue Preis-/Mengenannahmen:

- Kaufpreis: `ceil(Trade ×1,0005 /Tick) ×Tick`. Der bisherige adverse
  Slippagepreis wird um höchstens einen weiteren Tick verschlechtert.
- Kaufmenge: `floor(min(Eigenkapitalstufe ×Hebel /Kaufpreis,
  Market-Maximum) /Mengenstep) ×Mengenstep`.
  Aktuelle Mindestmenge und Mindestnominal gelten; keine Budgetaufrundung.
- Verkaufspreis: bisheriger normaler/Liquidationspreis einschließlich
  Slippage, zum nächsten Tick abgerundet. Kein günstigerer Fill.
- Alle Modellfills werden erneut gegen Preis-/Mengenraster und Market-Maximum
  geprüft. Ein übergroßer vollständiger Ausstieg stoppt den Forschungsjob:
  Aufteilung in mehrere Orders ist noch kein Bestandteil dieses Full-Fill-Modells.

Die **Eigenkapitalbeträge jeder Stufe bleiben exakt identisch**.
Auch der vom Mengenfloor ungenutzte Nominalrest bleibt Bestandteil der eigenen
gebuchten isolierten Margin. Er wird nicht als neuer Gewinn oder freie
Kontogutschrift erfunden. Alle fünf regulären Nachkäufe haben weiterhin
RSI-Rearm und mindestens5% Abstand zur letzten tatsächlichen Kaufstufe;
die sechste Stufe bleibt der ausschließlich manuelle, nicht simulierte Puffer.

Unverändert bleiben0,1% Entry-/Exitgebühr,0,5% deklarierte Maintenance/
Liquidationsgebühr, Tiercap1M, native Fundingtimestamps und Marks,
eigene Q45-Restoration mit vollständigem regulärem Fee-Backing, Q44 für den
eigenen vollständig profitablen Abschluss, tatsächliche Cash-/Budget-/
Liquidationsgrenzen und−55%-Notausstieg.6%/8% bleiben Warnungen.
Keine Wiederanlage/Slotexpansion/AI/anderen Hebel oder Holdoutauswahl.

Der statische Rasteranker IP-084 isolierte19 XRP-Nanoreste. Dieser Job
prüft ihre tatsächliche Wirkung in einem vollständigen kausalen Replay;
er entfernt **keine** Preis- oder Marginregel:
`fill_bound_below_mark` sowie
`max(gesamtes Basisnominal, Marknominal) /eingefrorener Hebel`
bleiben deklariert. Die vollständige Classic-Orderfreeze-/Marginabbildung und
der Markguard-Abgleich folgen separat. Der öffentliche0,06%-Takertarif
wird hier nicht zugleich als Renditeoptimierung eingesetzt.
Das Geldquantum1E−8 bleibt eine Forschungsannahme; Broker-USDT-Präzision
und Rundungsrichtung werden nicht behauptet.

## Reproduzierbarer Ablauf

```bash
python3 infra/scripts/backtest-futures-capital.py --h1-current-grids NEW_OUTPUT_DIRECTORY
```

Der explizite Flag verlangt alle gefrorenen Protokoll-/Metadaten- und
Referenzreceipthashes. Alle15 nativen Quelldateien werden erneut geprüft,
ohne neue GETs oder Holdoutdaten. Ein Cohort/ein Szenario auf dem2-GB-Host.
Elf tatsächlich verwendete Implementationsdateien werden vor und nach
dem vollständigen Marktjob/Restore verglichen. Bei Abweichung entsteht
kein Erfolgsreceipt. Änderungen an diesen Dateien während des Jobs sind verboten.

Alle tatsächlichen Inputs einschließlich Funding, Tagesbasis, Quotes,
Restoration, fünf Stufen, Exits und terminaler Liquidation werden vollständig
von Genesis gefaltet. Offene Endbaskets bleiben zum Markkurs bewertet;
kein erfundener profitabler Endexit. Vier Ausgabeartefakte werden hashgebunden
gesichert. Lauf- und Prüfergebnis folgen nach abgeschlossenem Restore.

Gezielte Prüfung: zwölf neue Fälle/18 Subtests, insgesamt121 unterschiedliche
Fälle/88 Subtests im gepinnten Python3.14.10-Container grün, verteilt auf
den ursprünglichen Lauf und gezielte Korrekturprüfungen.
109 bestehende Kapital-/Cash-/Signal-/Journal-/Markt-/Wirtschaftsfälle
bestanden;24 nach korrigierter Genesis-Whitelist erneut geprüft.
Die neuen Fundingfixtures benötigen wie jeder echte Input einen
zeitgleichen Markbeleg; dieser wurde ergänzt, die Schutzregel unverändert.
Vollständiger synthetischer Markt-/Journalrestore, fünf volle Eigenkapitalstufen,
konstanter Hebel, manual-only sechste Stufe, Nano-Funding und tatsächliche
Unterdeckung, Tick-/Mengenchecks und übergroße Exits sind geprüft.
Das alte IP-082-Profil besitzt weiterhin exakt denselben gespeicherten Digest;
alle vier Originalausgaben wurden unverändert rehashed.
