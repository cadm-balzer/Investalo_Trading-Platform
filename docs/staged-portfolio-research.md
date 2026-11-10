# Forschungsadapter mit vollständiger Nachkaufstaffel

Stand2026-11-10, IP-058. Ausgangscheckpoint IP-057 (`d31dcf3`) ist in
Main`1f44b7f` verifiziert.
Der Nutzer bestätigt das Forschungsprofil aus IP-057 („danke das passt so“):
gleiche3–5 Slots,1% Kostenreserve auf Principal, zusätzliche gemeinsame
−50%-Stressprüfung und weiterhin unabhängige6%/8%-Kontolimits.
Er erinnert ausdrücklich an Nachkäufe zur Senkung des Durchschnittspreises.
Coinauswahl, Zykluswiederbelegung und Betriebsaktivierung bleiben getrennt.

## Nachkäufe verwenden den vorhandenen Strategiekern

`investalo_trading.staged_research` verbindet den Allokator mit
`CryptoEngine`, `PaperSimulator` und dem synchronen `PortfolioSimulator`.
Es kopiert keine RSI-, Fill-, Durchschnittspreis- oder Schutzlogik.

- Stufe1: zwei aufeinanderfolgende geschlossene H4-Kerzen mit RSI14/Wilder<30.
- Stufen2–5: erneute Aktivierung durch RSI>30, danach RSI<30 und mindestens
  5% unter dem letzten tatsächlichen regulären Einstieg; Quote-/Orderpreislimit
  und die üblichen Schutzbedingungen müssen ebenfalls passen.
- Quotevolumen steigt je regulärer Stufe um25%; Instrument-/Geldrundung nach
  unten. Die vorgesehenen Beträge werden beim Allokator vollständig geprüft,
  ohne kleinere Ersatzorders zu erzeugen.
- Stufe6 bleibt ausdrücklich manuell, nach fünf regulären Stufen und mit
  Preisbedingung/Vorschau/Bestätigung. Kein Backtest erfindet diese Freigabe.

Tatsächliche Fillprincipal und Menge bestimmen den durchschnittlichen
Einkaufspreis. Die gemeinsame Risikoprüfung steht zusätzlich vor **jedem**
regulären oder bestätigten manuellen Kauf. Auch ein korrektes RSI-Nachkaufsignal
kann am gemeinsamen Verlustspielraum scheitern; die Staffel ist kein
Anspruch auf alle Käufe unabhängig von den bestätigten6%/8%-Grenzen.

## Zwei Prüfgrenzen und tatsächliche Ausgaben

Nach den ursprünglichen Entrychecks wird ein vollständiger Kaufkandidat
vor Aufnahme in die Orderliste beurteilt. Der simulierte Dispatch prüft erneut
mit aktuellen Quotes/Cash/Holdings und allen anderen offenen Restbeträgen.
Die eigene Order wird dabei als Kandidat gerechnet und nicht doppelt reserviert.
Ein erster Einstieg verwendet den aktuellen synthetischen Ask einschließlich
Slippage als endlichen Modellpreis; weitere Käufe behalten ihr strengeres
reguläres Limit. Der Simulator prüft den tatsächlichen modellierten Fillpreis.

Die neue immutable `ResearchState` führt verbrauchtes Principal und alle
tatsächlich bezahlten Buy-/Sellfees über Teilverkäufe und Basketabschluss
hinweg. Doppelte Fills verändern diese Beträge nicht erneut.
Unklare, teilweise gefüllte oder Storno-angeforderte Käufe bleiben reserviert
und sperren andere Einstiege bis zum autoritativen Abgleich.
Unklare/partielle Sellorders sperren ebenfalls neue Käufe. Schutz- und
Notausstiege werden durch diese zusätzliche Kaufprüfung nicht aufgehalten.

Creationassessments und Allokationsablehnungen beim Dispatch bleiben als
strukturierte Events mit Grenze/Zeit/Intent/Asset/Stufe/Principal, Plan-/
Viewdigest und vollständiger Stress-/Budgetdiagnose im Report.
Erfolgreiche Dispatches führen weiter zu den normalen Fillbelegen; ein
vollständiges persistentes Dispatchaudit gehört später zur Ausführungsintegration.

## Eigene Version, eindeutiger Forschungsumfang

`allocated-rsi-research/1` leitet die bestätigten unveränderten Signal-/
Schutzparameter aus v1 ab und verwendet das gebundene Allokationsprofil.
`StrategyConfig` v1 akzeptiert weiterhin nur BTC/ETH. Neue Reports tragen
eigene Strategie-/Schema-/Policy-/Plan-/Config-/Cost-/Datadigests.
Policy friert kanonische Symbolreihenfolge, H4-Phasen, Kaufgrenzen,
Stufen-/Manualvertrag und deaktivierte Wiederbelegung ein.

Alle ausgewählten Instrumentregeln und identische vollständige H4-Fenster
müssen vorliegen. Policy, Daten und Kosten werden vor späteren Leistungsläufen
eingefroren; heutige Ausgabe ist ein synthetischer Integrationsnachweis.
Der vorhandene Lauf bleibt im Tageswechsel-/Quote-/Fillablauf erhalten.
Normale Runtime-Snapshotloader lehnen diese eigene ResearchState ab; kein
Worker, API-/Paperdaemon oder Brokeradapter registriert dieses Profil.
Der Adapter akzeptiert explizite Plansymbole als technische Eingaben;
die aktuellen Caller/Tests nutzen ausschließlich synthetische Assets.
Das ist keine Marktfreigabe zusätzlicher Coins.

Der erste Adapter erlaubt **einen vollständigen Basketzyklus je Slot**:
erster Einstieg, erlaubte Nachkäufe, Schutz/Exit. Nach Abschluss bleibt der
Slot für weitere Zyklen gesperrt; Ausgaben werden nicht automatisch erneuert.
Das ist eine Implementierungsgrenze bis zum folgenden Zyklusvertrag,
keine Änderung der bisher wiederholenden v1-Strategie.
Noch kein erweiterter Mehrjahreslauf oder neuer Profitabilitätsnachweis.

## Abnahme und folgende Entscheidungen

12 neue synthetische Integrationstests plus bisherige Trading/Paper/
Portfolio-/Allokator-/Workerregression. Ein kontrollierter Test mit bereits
vorhandenem synthetischem Gewinn schafft genügend Riskspielraum und führt
alle fünf regulären Stufen aus: wachsende Beträge, fallender Durchschnitt,
RSI-Rearm und5%-Abstand. Anschließend bestätigt er die manuelle sechste
Stufe separat und prüft ihren tatsächlichen Fill/Lifetime-Fees.
Dieses Testszenario ist keine erzielte Forschungsrendite und belegt nicht,
dass alle fünf Stufen in jedem realen Marktszenario zulässig werden.
Andere Fälle prüfen konkurrierende Reservierungen, abgelehnte Nachkäufe,
Dispatchprüfung, Teil-/Doppelfills, Notausstiege, Version/Identität und UTC.
Prüfbelege: [Taskboard](tasks/board.md).

Vorschlag für den nächsten Zyklusvertrag: nach normalem vollständig
abgeglichenem Gewinn-/Trailingexit denselben Slot mit demselben nominalen
Principal-/Kostenbudget erneut nutzen. Keine Erhöhung durch Gewinne,
keine Freigabe nach Teilverkauf, unbekannter Order oder Risk-Stop;
frischer RSI-Ersteinstieg und alle aktuellen Kontogates bleiben erforderlich.
Kosten je Zyklus neu aus tatsächlichem Cash reservieren, Gesamtausgaben als
Audit weiterführen. Noch nicht umgesetzt/aktiviert. Dafür und für die
zusätzlichen Coins ist die genaue Forschungsentscheidung noch offen.
[Kapitalrechnung](portfolio-allocation.md), [Gesamtplan](multi-basket-ai-plan.md).
