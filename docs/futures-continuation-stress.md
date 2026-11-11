# Kausaler Stress für ausstehende Futures-Teilfills

2026-11-11, IP-067. IP-066`40d8ba6` in Main`1d06dd3` verifiziert.
Neues reines Offline-Modul `futures_continuation.py`,
Version `isolated-usdt-long-continuation/1`. Die bestehenden Risk-,
Ledger-/Pending-, Spot-/Paper-Versionen und Exporte bleiben unverändert.

## Was der neue Befund prüft

Ein `ContinuationScenario` bindet Tenant/Konto/Plan, erwartete Revision,
ausstehenden Intent und Orderidentität. Vollständige kanonische Mindestmarks
für alle3–7 Plansymbole beschreiben die zu prüfende abwärts gerichtete
Gapspanne; sie dürfen nicht über den aktuell belegten Marks liegen.
Das ist eine deklarierte Forschungsannahme, kein künftiger Marktnachweis.

Nach vorhandenem tatsächlichem First Fill gilt je offener Position:
`Stressmark = min(aktueller Mark, 50% erster tatsächlicher Fill, Gapminimum)`.
Ein günstigeres späteres Fragment setzt den ersten Fill nicht neu.
Ist schon das erste Fragment günstig, wird dessen niedrigerer Stressanker
sofort für die noch nicht gebuchte Restmenge verwendet.

Die Restmenge ist die ursprüngliche Ordermenge minus alle tatsächlich
gebuchten eigenen Fillfragmente. Ihr maximaler Preis und die Hebeleinstellung
bleiben im ursprünglichen Intent eingefroren. Die verbleibende Feehülle
ergibt sich aus Restmenge × Maximalpreis × eingefrorenem Entryfeemodell.
Sie muss in der noch vorhandenen Intent- und Basketkostenreserve liegen.
Mindestordergröße wird nicht auf einzelne Restfragmente umgedeutet.

**Nur tatsächlich gestellter signed isolierter Nettostand zählt als Deckung.**
Reservierte, aber noch nicht transferierte eigene Margin zählt nicht;
spätere Kostenwiederauffüllung oder andere Baskets retten keine Gapposition.
Bereits gebuchtes Funding und ausdrücklich belegte eigene Postings zählen
mit ihren aktuellen Werten. Margin-/Kostenbudget und ursprüngliche
Kontorisikobasen werden dadurch nicht größer.

## Endpunkte und konservative Reihenfolge

Geprüft werden vorhandene Menge vor jedem weiteren Fill und die gesamte
Restmenge zum maximalen Fillpreis. Beide verwenden bereits vorhandene
Collateralwerte, die adverse Gapuntergrenze und konservative volle
Maintenancestufe über das größte betrachtete Nominal.
Die volle verbleibende Entryfee wird vorsichtshalber bereits am Null-Restfill-
Endpunkt von Cash abgezogen. `gap_equity_before` ist deshalb ein konservativer
Rechenendpunkt, keine neue tatsächliche Tagesbewertung.

Bei festem tatsächlichem First Fill, keinem angenommenen Nachschuss und
Fillpreisen höchstens am eingefrorenen Limit sind die unteren Equity- und
Marginüberschussgrenzen linear in der zusätzlichen Menge. Die beiden
Endpunkte decken damit auch die Zwischenmengen innerhalb dieser Hülle.
Die volle Maintenancestufe verhindert eine zu günstige Zwischenstufenrechnung;
Kapitaldeckung sowie positive Preis-/Feeabweichungen bleiben gesonderte Gates.

Der Rechner prüft:

- aktuelle und vor jedem Restfill gestresste isolierte Deckung;
- gestresste volle Restfüllung und verbleibende Initialmargin;
- gemeinsame6%-Tages-/8%-Originalkontogrenze mit allen offenen Baskets;
- korrelierten Preisstress plus noch freie Kostenreserven;
- eigene Bruttomargin, gebuchte und künftige Kosten sowie gedeckte
  ungepostete Budgets einschließlich unbelegter Fundingprincipal-Restoration;
- frische komplette Marks, UTC-Tagesbasis, Kontext/Revision, latched Halts,
  verbleibendes Mengenraster und Kapazität der gespeicherten IDs.

Freie Kostenreserven werden ausdrücklich an **beiden** Gapendpunkten geprüft.
Liegt das eingefrorene Entrylimit unter dem Stressmark, wäre der volle
Restkauf bei diesem Mark hypothetisch profitabel. Dieser Gewinn darf eine
Kostendeckungslücke am Endpunkt ohne weitere Fills nicht verdecken.
Ein eigener kausaler Tageswechsel-/Mark-/Restlimit-Grenzfall sichert das ab.

Fehlt eine offene tatsächliche Position, wird der erste Stressanker nicht aus
dem geplanten Maximalpreis erfunden. `risk_covered=false`; Mindest-/Zusatzmargin
bleiben in diesem Fall unbelegt. Die notwendige rechtzeitige Pufferwirksamkeit
vor dem allerersten Brokerfill bleibt ein separates Gate.

## Beispiel und Grenzen

Synthetisch: geplant1 Einheit bis100 und Margin60, zunächst0,5 zu100 gefüllt.
Sind die60 bereits vollständig gestellt, ist die Restmenge bei Stresspreis50
gedeckt: strikte Mindestdeckung50,30000001 bei Quantum0,00000001.
Sind erst30 gestellt, bleibt die Restmenge gesperrt; die bloße Restreservierung30
ist kein Nachweis von Collateral. Eine später tatsächlich gebuchte eigene
Margin30 kann den aktuellen Rechenbefund verbessern, ohne verlorene Equity,
Budgets oder vorhandene Halts zu verändern.

Ein weiteres Beispiel weist die bisherige Vollfillgrenze nach: geplante
10 Einheiten bis100/Margin600; erstes Fragment0,0001 zu1. Der tatsächliche
Stressanker0,5 sperrt nun die restlichen9,9999 am Preislimit100 schon vor ihrer
Buchung. Die frühere Projektion „alles100, Stress50“ wird nicht wiederverwendet.

`risk_covered` bezeichnet ausschließlich diese ökonomische Forschungsdeckung.
`requires_reconciliation=true` und `execution_enabled=false` bleiben zwingend.
Auch ein positiver Befund beendet keine unbekannte Order, gibt keine Reserven
frei und erlaubt weder Fortsetzung noch erneuten Versand.
Zusätzliche erforderliche Margin ist eine Anzeige, kein Postingauftrag.
Eine schlechte hypothetische Deckung mutiert keinen Ledger und setzt keinen
neuen permanenten Halt; tatsächliche bekannte Fills bleiben unabhängig
weiter wahrheitsgemäß buchbar.

Die Hülle beweist keine beliebigen zukünftigen Markpfade oberhalb der
betrachteten Referenzen, Fundingzahlungen oder Kosten-/Kontraktänderungen.
Nach neuen echten Events ist der alte State-/Szenariobefund veraltet.
Proportionale Teilclosefreigabe und Maintenancestufen bleiben explizite
Forschungsannahmen. Der Mengen-/Positionsguard ersetzt keine beim Intent
eingefrorene Strategie-/Basketzyklusautorität; diese gehört in den kommenden
Signaladapter. ID-Dedupe ist weiterhin auf den bewahrten begrenzten State
beschränkt, kein persistenter Restart-/Brokerbeweis.

## Abnahme und nächste Aufgabe

31 neue Fälle;277 unterschiedliche Host-Tradingfälle und281 gepinnte Trading-/
Workerfälle mit219 Subtests bestanden: Vollsuite276/280, danach ergänzte
Endpunkt-Kostenprüfung mit allen31 Modulchecks gezielt erneut grün.
Endpunktprüfung umfasst45 Kombinationen aus
Zwischenmenge, niedrigerem Fillpreis und Feezeitpunkt; außerdem3/5/7 Slots,
strikte Gleichheit, Tiergrenzen, signed Fundingdefizite, echte Marginpostings,
andere Basketgaps, Revision/Tagesbasis und dauerhaft gebuchte Halts.
Eigenprüfung; keine neue Agentdelegation und keine unveränderten
Credential-/DB-/Publicregressionen wiederholt.

IP-068 verbindet als Nächstes RSI14/Wilder, bestätigte Nachkaufstaffel und
exakte Basket-/Intentzyklusbindung mit einem begrenzten Futures-Replayadapter.
Ein erstes Replay braucht explizit eingefrorene Margin-/Kosten-/Regimeannahmen
und eine deklarierte First-fill-Pufferannahme; vollständige historische
Funding-/Kontraktregeln bleiben für belastbare Nettoleistungsläufe
IP-055/063/BL-030. Keine neuen Daten/Dependencies/Migrationen, Holdoutabfragen
oder Runtime-/Broker-/Publicaktivierung.
