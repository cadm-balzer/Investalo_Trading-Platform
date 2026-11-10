# Gewinnverwendung in Etappen

2026-11-10, Q36. IP-060 `22534b7` ist in Main`ab928ee` verifiziert.
Der Nutzer erweitert die bisherige feste Budgetplanung: Gewinne geschlossener
Baskets sollen gesammelt und begrenzt für neue Baskets nutzbar werden, sobald
sie eine vollständige Basketstaffel finanzieren können. Drei gewinnbringende
Abschlüsse sind sein Beispiel, keine verbindliche Anzahl. Verwendung entweder
für zusätzliche parallele Baskets oder höhere Budgets bei maximal3–5 Baskets.

**Richtung bestätigt; genaue Schwelle, Prüfrhythmus und Verwendung noch
Entscheidungsvorschlag.** Der bestehende Offlinekern bleibt
`candidate-pool-rsi-research/1` mit festen Budgets. Kein Compounding aktiviert.

## Konkreter Vorschlag zur Entscheidung

- Nach jeweils drei vollständig abgeglichenen Basketabschlüssen prüfen.
  Verluste mitzählen; kein Filter ausschließlich auf Gewinner.
- Verwendbar ist der kumulierte realisierte Nettoüberschuss aller abgeschlossenen
  Baskets nach sämtlichen Buy-/Sellkosten, abzüglich bereits zugeordneten
  Gewinnkapitals. Keine Buchgewinne, kein dreifaches Wiederverwenden derselben
  Gewinne. Spätere realisierte Verluste mindern den verbliebenen Überschuss.
- Schwelle ist das **ursprüngliche** Gesamtbudget eines Slots: alle fünf
  regulären Stufen, manuelle sechste Reserve und Kostenreserve. Eine volle
  Etappe je Prüfung; Rest bleibt gesammelt. Eine feste Ursprungsschwelle
  vermeidet, dass die Schwelle während des Sparens mitwächst.
- Empfohlene Verwendung: bei weniger als fünf Slots zunächst einen weiteren
  finanzieren; ab fünf Slots eine Etappe gleichmäßig auf die Zielbudgets
  künftig gestarteter Baskets verteilen. Alternative: Slotanzahl festhalten
  und ausschließlich künftige Budgets erhöhen. Auswahl ist ausdrücklich erfragt.
- Offene Baskets behalten Principal-, Kosten- und Stufenbudgets ihres Starts.
  Kein nachträglicher Wechsel der Staffel mitten im Kursrückgang.
- Freigabe verlangt aktuelle vollständige Equity-/Cash-/Orderbelege. Offene
  Verluste dürfen bereits verbrauchten Überschuss nicht erneut als zusätzliches
  Kapital erscheinen lassen. Account-/Basketstop oder unklare Orderausgänge
  sperren Freigabe. Jede tatsächliche Order bleibt separat riskgeprüft.
- Die6% Tagesverlust gegenüber der bestätigten Mitternachtsbasis und8% gegenüber
  dem ursprünglichen Startkapital bleiben bestehen. Gewinnkapital ist keine
  Neueinzahlung und setzt Startkapital-/Verlusthistorie nicht zurück.
  RSI, Staffel, manueller Puffer, Spot ohne Hebel und Schutzregeln bleiben.

## Rechenbeispiele des empfohlenen Modus

10.000 USDT Ursprungskapital,1% Principal-Kostenreserve, Geldraster10⁻⁸ USDT.
Zahlen aus dem bestehenden `PoolPlan.slot_plan`, keine Leistungsprognose:

| Anfangskapazität | Ursprüngliches Gesamtbudget je Slot / Gewinnschwelle | Erste Etappe | Danach Gesamtbudget je neuem Basket |
|---|---:|---|---:|
| 3 | 3333,33333333 | vierter Slot | 3333,33333333 |
| 4 | 2500 | fünfter Slot | 2500 |
| 5 | 2000 | höheres Volumen, weiterhin fünf Slots | 2400 |

Beim Fünf-Slot-Beispiel verteilen sich2400 USDT auf
2376,23762376 Principal und23,76237624 Kostenreserve. Alle sechs Stufen behalten
die Gewichte1,25⁰ bis1,25⁵; sechste Stufe bleibt manuell. Rundungsreste bleiben
Cash. Drei abgeschlossene Baskets reichen allein nicht: ihr bereinigter
Überschuss muss die volle Schwelle tatsächlich erreichen.

## Umsetzung nach Entscheidung

Eigene immutable Gewinn-/Budgetepochen und einmalige Etappenzuordnung,
gebunden an Tenant/Konto, abgeschlossene Zyklusbelege und Policyversion.
Slotkapazität/Zielbudget und jedes gestartete Basketbudget getrennt speichern.
Aktive ältere Baskets müssen bei Kosten-/Stressberechnung ihre eigene
Budgetepoche behalten; mixed budgets dürfen nicht über eine globale
StrategyConfig nachträglich geändert werden.

Die bisherige Allokation verwendet `initial_capital` sowohl für Slotbudgets
als auch die8%-Startkapitalgrenze. Gewinnstaffeln brauchen diese Größen
getrennt. Erhöhtes Planungskapital nicht durch fiktiv erhöhtes initial_equity
oder einen Kontoneustart modellieren. Ebenso braucht die gemeinsame
Kostenbindung freie Slots mit ihren künftigen Reserven und belegte Slots
mit ihrer ursprünglichen Reserve.

Vergleichsläufe zuerst mit identischen chronologischen Forschungsdaten und
Kosten, getrennte Versionen für festes und abgestuftes Budget. Keine Nutzung
des reservierten Holdouts zur Modus-/Schwellenauswahl. Größere Gesamtbudgets
heben die6%/8%- oder50%-Stressprüfung nicht auf. Daten-/Kohortenarbeit und
echte größere Netto-Backtests bleiben IP-055; Paper/Live separat.
