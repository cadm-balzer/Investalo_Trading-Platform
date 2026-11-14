# Gewinnetappen im eigenen Futures-Paperkern

IP-090/Q36, 2026-11-14. PR68 (`70c93cb`) ist in `main763717b` enthalten;
GH/Fetch/Ancestry bestätigt. Die bestehende Kapitalempfehlung nutzt jetzt
auch tatsächlich im eigenen Journal bestätigte Gewinnetappen.

## Eigene Policy und Freigabe

`CapitalPaperProfitPlan` verwendet die gesonderte Policy
`isolated-usdt-capital-paper-profit/2`. Anfängliche3–5 finanzierte Ranges,
volle sechs Eigenkapitalstufen, manuelle Reserve, feste2×, H1-RSI,
H1-Supertrend, aktuelle Grids und die bestehenden tatsächlichen Cash-/
Margin-/Liquidationsregeln bleiben erhalten. Historische feste Paperpläne
und Spot-Gewinnforschung behalten ihre eigenen Identitäten.

Eine Etappe braucht mindestens drei weitere **vollständig** geschlossene
Baskets seit der letzten Freigabe. Alle Abschlüsse zählen; Verluste werden
nicht ausgefiltert. Maßgeblich sind der tatsächliche kumulierte
`realized_net_pnl` und `closed_baskets` des eigenen Ledgers nach Einstiegskosten,
Ausstiegskosten, Funding und Liquidationsabrechnung. Teilverkäufe oder
unrealisierte Gewinne geben keine Etappe frei.

Je Freigabe wird genau das ursprüngliche vollständige Rangebudget zugeordnet.
Der gesamte realisierte Nettoüberschuss muss auch sämtliche bisherigen
Zuordnungen und die neue Etappe decken. Überschüsse bleiben gesammelt;
eine weitere Freigabe braucht erneut drei zusätzliche Abschlüsse. Das
ursprüngliche Gesamtbudget bleibt auch bei späterer Volumenerhöhung die Schwelle.

Bis sieben wird ein zusätzlicher Platz finanziert; dafür müssen Kandidatenpool
und gespeicherte Obergrenze ausreichen. Fehlende Kandidaten bewirken keine
vorzeitige Volumenerhöhung. Ab sieben erhöht eine Etappe gleichmäßig die
Zielbudgets künftig gestarteter Ranges. Eine später niedrigere Obergrenze
begrenzt neue Einstiege, entzieht aber keine bestätigte Finanzierung.

Für jeden Schritt müssen tatsächliche aktuelle gemeinsame Quotes/Marks,
geschlossene aktuelle H1-Daten und maximal30 Sekunden Alter vorliegen.
Aktuelles Eigenkapital muss Originalkapital plus sämtliche zugeordneten
Gewinnetappen decken. Liquides Cash muss alle offenen verbleibenden regulären/
manuellen/Kosten-/Restorationreserven, sämtliche freien finanzierten Ranges
und aufgeschobene Erhöhungen decken. Ungeklärte Liquidationen, gestoppte
Assets und bestehende Kontohaltes verlangen Abgleich statt Gewinnfreigabe.
Die6%/8%- und−50%-Diagnostik des Q41-Futuresprofils wird nicht aus dem
historischen Spotprofil als neue harte Eintrittssperre übernommen.

Eine Freigabe verändert weder Cash, gebuchte Gewinne/Verluste, Positionen,
Hebel noch Tages-/Originalrisikobasis. Sie erzeugt keine Order oder Recovery.
Eine nicht mögliche Etappe blockiert keine bestehende Kaufstaffel.

## Eingefrorene offene Budgets

Jeder Kandidat trägt die Epoche seines tatsächlichen Budgets. Offene und
gestoppte Baskets behalten diese Beträge und sämtliche Nachkaufstufen.
Nur flache wiederverwendbare Kandidaten übernehmen das aktuelle Zielbudget.
Auch nach einem späteren vollständigen normalen Exit erfolgt diese Übernahme
vor einem neuen Basket, ohne historischen Gewinn neu zuzuordnen.

Noch nicht nutzbare Erhöhungen alter offener Ranges bleiben im Planrest
gesondert gebunden. Beispiel mit drei Startplätzen zu3333,33333333 USDT:
vier Etappen finanzieren sieben Plätze; die fünfte erhöht zukünftige Budgets
auf3809,52380952. Bei der sechsten beträgt das Ziel4285,71428571.
Ein noch offener Basket behält3809,52380952 und seine tatsächlichen Stufen;
476,19047619 zusätzlich bleiben bis zu seinem Abschluss gebunden.
Geldrundungsreste bleiben ebenfalls erhalten.

## Journal, Worker und eigene API

Der additive eigene Paperbefehl `profit_epoch` akzeptiert keine vom Client
behaupteten Cash-/Gewinn-/Budgetwerte. Unter dem bestehenden Journal-CAS-Lock
wird die Berechtigung erneut vollständig berechnet. Immutable Epochen speichern
Zeit, Kapazität, Zielbudget, zugeordneten Gewinn, tatsächlichen Abschlusszähler,
Nettoergebnis, Cash/Equity und Hash des vorherigen Finanzzustands.
Die vollständige Wiederholung eigener Journalbefehle beweist diese Werte;
ein Snapshot allein ist keine Broker-/Abgleichautorität.

Nach einem vollständig bestätigten archivierten Quotedurchlauf prüft der
gebundene Kontoworker höchstens eine Etappe. Kontoberechtigung und aktuelle
Settings werden unmittelbar vor deren Commit erneut geprüft. Funding-only-/
ausstehende Quellenstände geben nichts frei. Der Quellencursor bleibt durch
die reine Gewinnzuordnung unverändert. Publikation erfolgt anschließend mit
dem tatsächlichen neuen Journalreceipt.

Unknown-write stoppt weiterhin: vollständiger Restore mit publiziertem
Mindestreceipt vor Readback/Reparatur, keine automatische Wiederholung.
Neustart übernimmt bereits zugeordnete Gewinne und erzeugt keine zweite
Etappe ohne neue Abschlüsse. Die Geschichte ist auf256 Gewinnetappen begrenzt;
keine stille Eviktion oder Kontorücksetzung.

Der normale scoped APIreader und das bestehende Portfolio zeigen bestätigte
finanzierte Plätze und das aktuelle Budget zukünftiger Ranges. Der tatsächliche
PG-/HTTP-Test bestätigt Empfehlung4 bei Obergrenze7 und vier finanzierten
Ranges, ohne Finanzmutation durch APIlesen oder zusätzliches Settingsaudit.

## Explizite Allokation und Grenzen

`paper_profit_plan` und `local_profit_config` erzeugen ausschließlich ein
explizites neues eigenes Profil. Neue Genesis darf keine alten Gewinnetappen
importieren. Private SHA-Allokationsdatei und bisherige Bootstrapprüfungen
bleiben erforderlich; keine automatische Umdeutung vorhandener fester Journale,
Reinitialisierung, Zweitallokation oder Spot-/Backtestkapitalübernahme.
`local_config` und bestehende normale/public Dienste bleiben unverändert.

Der reale Classic-Collector umfasst weiterhin fünf Kandidaten. Der neue
private Fünf-Coin-Gewinnplan kann somit bis fünf finanzierte Plätze wachsen;
sechs und sieben benötigen eine gesonderte echte Poolerweiterung.
Die vollständige3→7-/Volumenfolge ist mit sieben synthetischen Kandidaten
und tatsächlichen Paperreducern geprüft, keine neue native Marktperformance.
Keine neue Migration, Rolle, Abhängigkeit, Brokerorder oder Live-/AI-Freigabe.

## Prüfung und nächste Schritte

Zwölf neue Fälle: neun Domain-/Finanz-/Journalfälle, ein tatsächlich archivierter
Quellen-/Worker-/Publikations-/Restartfall, ein echter PG-/HTTP-Fall und ein
privater Allokations-/Profilrundlauf. Große Fixturegewinne dienen ausschließlich
der deterministischen Prüfung der Schwellen.

224 gezielte gepinnte Fälle/118 Subtests im breiten Lauf grün; nach finalen
Ergänzungen37 gezielte Fälle/11 Subtests erneut grün, einschließlich aller
zwölf neuen Fälle. Alte feste Paper-/Futures-Replaypfade bestehen.
Im Portfolio ist das Budgetlabel als Betrag für neue Ranges präzisiert;
offene alte Budgets bleiben unverändert. Sechs gezielte Cockpitvertrags-/
SSR-Fälle und Typecheck grün; kein erneuter Frontendbuild.
Kein neuer nativer Backtest-/Performancejob.

Als Nächstes: echte Classic-Kandidaten auf mindestens sieben erweitern,
danach Q46/IP-088 manuelle Liquidationsfreigabe integrieren und die getrennte
Bitget-Demoausführung kalibrieren.
