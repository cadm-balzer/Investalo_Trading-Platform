# Gewinnverwendung in Etappen

2026-11-10, Q36/IP-061. Nutzer bestätigt Option1: **zuerst zusätzliche Slots
bis maximal sieben gleichzeitige Baskets, danach größere zukünftige Budgets**.
Anfangskapazität bleibt3–5. Der separate Offlinekern
`seven-slot-profit-rsi-research/1` implementiert diese Entscheidung.
Der feste Poolkern `candidate-pool-rsi-research/1` bleibt Vergleichsbasis.

## Freigaberegeln

- Mindestens drei zusätzliche vollständig abgeglichene Basketabschlüsse seit
  der letzten Freigabe. Verluste mitzählen; kein Filter nur auf Gewinner.
- Kumulierte realisierte Nettoergebnisse aller abgeschlossenen Baskets nach
  sämtlichen Buy-/Sellkosten, abzüglich bereits zugeordneten Gewinnkapitals.
  Keine Buchgewinne oder mehrfache Zuordnung derselben Gewinne.
- Schwelle ist das **ursprüngliche** Gesamtbudget eines Slots: fünf reguläre
  Stufen, manuelle sechste Reserve und Kostenreserve. Pro Freigabe eine volle
  Etappe; überschüssige Gewinne bleiben gesammelt. Für die nächste Freigabe
  sind erneut mindestens drei weitere Abschlüsse erforderlich.
- Unter sieben Slots einen weiteren finanzieren. Ab sieben eine Etappe
  gleichmäßig auf die Zielbudgets künftig gestarteter Baskets verteilen.
- Offene Baskets behalten Principal-, Kosten- und Stufenbudgets ihres Starts.
  Freie Slots übernehmen die neue Budgetepoche. Noch durch ältere aktive
  Budgets gebundene Erhöhungsbeträge bleiben gesondert reserviert.
- Vollständige aktuelle gemeinsame Kursbewertung, Eigenkapitaldeckung und
  liquide Cashdeckung nach Reserven sind erforderlich. Ungeklärte Orders,
  Kontohalt oder Basketquarantäne blockieren. Die gemeinsame50%-Stressprüfung
  und jede spätere Intent-/Dispatchprüfung bleiben verbindlich.
- **6% Tagesverlust und8% gegenüber ursprünglichem Startkapital** bleiben
  bestehen. Gewinnfreigabe schreibt kein Cash gut, setzt keine Risikobasis
  zurück und startet keine gestoppten Baskets automatisch neu.
  RSI14/Wilder,5%-Preisabstand,25% wachsende Stufen, manueller Puffer,
  Spot ohne Hebel und Schutzregeln gelten weiter.

## Rechenbeispiel

10.000 USDT Ursprungskapital, zunächst fünf Slots zu je2.000 USDT
inklusive Kostenreserve. Die Tabelle zeigt **Budgetplanung**, keine
Leistungsprognose; jede Zeile benötigt neue Abschlüsse und reale Deckung:

| Freigegebene Gewinnetappen | Kapazität | Zielgesamtbudget je neuem Basket | Zugeordnetes Gewinnkapital |
|---|---:|---:|---:|
| keine | 5 | 2000 | 0 |
| erste | 6 | 2000 | 2000 |
| zweite | 7 | 2000 | 4000 |
| dritte | 7 | 2285,71428571 | 6000 |

Jedes Budget teilt sich in Principal und1% Principal-Kostenreserve.
Die sechs Stufen behalten die Gewichte1,25⁰ bis1,25⁵; die sechste bleibt
manuell. Geldraster10⁻⁸ USDT, Rundungsreste bleiben gebundenes Cash.
Bei drei Anfangsslots beträgt die feste Etappenschwelle3333,33333333 USDT,
bei vier2500 USDT. Auch hier zuerst Slots bis sieben ergänzen.

## Vertrag und Grenzen

`ProfitPlan`, `ProfitEngine` und `ProfitResearchSimulator` in
`packages/trading/src/investalo_trading/profit_research.py` verwenden denselben
RSI-/Nachkauf-/Fill-/Schutzkern. Neue defaultneutrale Budgethooks lassen
bestehende feste Konfigurationen unverändert. Immutable `BudgetEpoch`-Belege
binden Tenant/Konto/Policy, Zeitpunkt, Abschlusspräfixhash, Nettoüberschuss,
zugeordneten Gewinn, damaliges Cash/Equity und Zielbudget. Jeder Slot und
Abschlussbeleg trägt seine eigene Budgetepoche. Keine manuelle Reserve im
historischen Simulator künstlich ausfüllen.

`variable_budget.py` prüft3–7 auch unterschiedlich budgetierte Slots,
gemeinsame Cash-/Fee-/Pending-/Stressbindung und die getrennte ursprüngliche
Risikobasis. Der Allokator vertraut dem übergebenen Budgetplan; die
Gewinnberechtigung entsteht erst im darüberliegenden Epochenvertrag.
Die lokalen immutable Zustände sind keine dauerhafte Datenbankreservierung
oder Brokerabgleichbestätigung. Runtime-Restore akzeptiert diesen
Forschungszustand nicht als alten Paperzustand.

Gezielte Tests führen echte synthetische Buy-/Sellfills mit Kosten aus:
Verlustanrechnung,3-Abschluss-Rhythmus, einmalige Zuordnung, sieben simultane
Baskets, blockierter achter Kandidat, größere künftige Staffel einschließlich
expliziter manueller Reserve, gemischte offene Budgets und fehlende Cash-/
Equity-/Stressdeckung. Große Fixturegewinne sind keine Marktleistungsnachweise.
Der Report weist seine eigene Version und Budgetepochen aus; Benchmark
bleibt ausdrücklich nicht berechnet.

Abnahme:143 Hostfälle und147 gezielte Fälle im gepinnten Python3.14.10-
Container mit87 Subtests bestanden;33 neue Fälle für Gewinnprofil und
variablen Allokator. Unabhängiges Review ohne wirtschaftlichen/kausalen
Blocker; ergänzte Cash-/Stressdeckungsfälle bestanden. Bestehende gemeinsame
BTC-/ETH-Dreijahresbaseline gegen alle eingefrorenen Ergebnisfelder exakt
reproduziert (Netto228,71690900701892163585 USDT,56 Abschlüsse).
Das belegt Rückwärtskompatibilität, keine Rendite des neuen Gewinnprofils.

Vollständige erweiterte Historien, vorab eingefrorene Kohorten und vergleichbare
Netto-Backtests bleiben IP-055. Zuerst feste und Gewinnprofile auf identischen
chronologischen Forschungsdaten vergleichen; keinen reservierten Holdout zur
Optimierung verwenden. Keine neuen Abhängigkeiten, DB-Migrationen,
Runtime-/Cockpit-/Broker-/Public- oder Liveaktivierung in diesem Checkpoint.
