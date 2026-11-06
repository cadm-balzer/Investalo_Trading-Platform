# Handelskonzept, Risiko und Nachweis

Stand: 2026-11-07. Der Originalauftrag beschreibt Strategieideen.
Folgende Formalisierung ist ein **prüfbarer Vorschlag**, keine bestätigte
Strategieänderung. Q3/Q4 bestätigen unabhängige Risikogrenzen und kontrollierte
Optimierung; konkrete Parameter bleiben offen. Q6 plant beide Broker im MVP.
Q9/Q10 bestätigen BTC/ETH Spot H4 ohne Hebel und XAUUSD Trend/Pullback H1/M15.

Die Crypto-Abbildung ist keine identische Fassung des schriftlichen Auftrags:
Sie nennt unter anderem drei/fünf Einstiege und vereinfachte Exitregeln.
Q11 bestätigt den schriftlichen Prompt als maßgebliche Vorlage.

## Crypto Basket

Bestätigt für den Start: BTC/USDT und ETH/USDT Spot ohne Hebel auf H4.
Long-Basket mit fünf regulären Einstiegen
und einem separat definierten Puffereinstieg.

Vorgeschlagene Zustände: `FLAT → FIRST_ENTRY_PENDING → ACCUMULATING →
PROFIT_PROTECTION → EXIT_PENDING → FLAT`, ergänzt um `PAUSED` und
ungeklärte Orderzustände. Nur bestätigte Fills verändern Mengen und Einstieg.
Teilfüllungen werden mit tatsächlichem Fill-VWAP verbucht.

| Regel aus Auftrag | Noch zu bestätigende Formalisierung |
|---|---|
| Erster Kauf bei zweiter Kerze mit RSI unter 30 | Zwei unmittelbar aufeinanderfolgende abgeschlossene Kerzen mit RSI strikt `<30`; Ausführung erst danach |
| RSI kurz über 30, danach wieder unter 30 | Mindestens eine geschlossene Kerze `>30` seit letztem Fill; Verhalten bei genau 30 offen |
| Weiterer Kauf nach mindestens 5 % Preisrückgang | Q12 bestätigt letzten tatsächlichen Fill als Referenz; Schlusskurs/intrabar und Bestätigungskerzen offen |
| Jeweils 25 % mehr Volumen | Q12 bestätigt Quote-Beträge; Gebührenreserve innerhalb des Gesamtbudgets |
| Fünf Käufe plus Puffer | Pufferbudget reservieren; eigene Auslöseregel noch offen |
| Schutz ab +5 % vom Durchschnitt | Kursrendite vorgeschlagen, nicht Margin-ROI; netto/brutto und erster Stop offen |
| Supertrend-Trailing | Nur nach oben verschieben bei Long; ATR-Verfahren, Länge/Faktor und Flipregel offen |
| −50 % Kursrückgang abfangen | Q12 bestätigt ersten Fill als Referenz; erlaubter Kontoverlust offen, jedes Füllstadium stresstesten |

Pro abgeschlossenem Signalereignis höchstens ein neuer Einstieg vorgeschlagen.
Rearm-Zustand, Strategieversion und Fillstand müssen Neustarts überleben.
Bei dauerhaft RSI `<30` entsteht nach dieser Rearm-Regel kein weiterer Einstieg.

### Budgetberechnung

Für sechs **Quote-Beträge**, Gesamtbudget `B` vor gesonderter Gebührenreserve:

`b_i = B × 1,25^(i−1) / Σ(k=0..5) 1,25^k`, für `i = 1..6`.

| Einstieg | Anteil am Budget |
|---|---:|
| 1 | 8,88195 % |
| 2 | 11,10244 % |
| 3 | 13,87805 % |
| 4 | 17,34756 % |
| 5 | 21,68445 % |
| 6 / Puffer | 27,10556 % |

Die Anteile sind gerundet; exakte Berechnung, Lot-/Notionalregeln und
Gebührenreserve gehen vor Darstellung. Nicht handelbare Restbeträge bleiben
Reserve. Marginbudget und Positionsnominal sind gesonderte Größen.

Der tatsächliche Einstand ist `A = Σ(Kaufkosten) / Σ(Basisassetmenge)`.
Ein arithmetischer Durchschnitt der Einstiegspreise ist falsch.
Nettobreakeven berücksichtigt Gebühren, Funding/Swap und erwartete Exitkosten.

**Illustration, kein prognostizierter Signalpfad:** sechs Fills bei
`100; 95; 90,25; 85,7375; 81,450625; 77,37809375`.
Das ganze Budget ist bereits nach −22,62 % gegenüber Einstieg 1 investiert.
Ohne Kosten beträgt `A ≈ 84,86642`, die +5%-Kursmarke etwa `89,10974`.
Beim Stresspreis 50 entsteht ein Buchverlust von rund **41,08 % des
eingesetzten Quote-Budgets/Einstiegsnominals**. Mit ungehebeltem Basketbudget von 10 % der Kontoequity
wären das etwa 4,11 % Kontoverlust vor Kosten.

„Sechs Einstiege“ und „5 % Abstand“ sichern daher keinen maximalen Drawdown.
Ein Asset kann weiter fallen, Reserve kann bereits verbraucht sein, und spätere
RSI-Einstiege können ausbleiben.

### Hebel und Liquidation

Ein −50%-Szenario verträgt sich nicht automatisch mit hohem Hebel.
Für einen vereinfachten linearen Long mit Einstand `A`, Menge `Q`,
Einstiegsnominal `N=Q×A`, hinterlegter Margin `M` vor Stressverlusten,
effektivem Hebel `L=N/M` und Maintenance-Rate `m`:

`P_liq ≈ A × (1−1/L)/(1−m)`.

Für Stressverlustanteil `d` gegenüber dem Durchschnitt wäre mindestens
`M/N > d + m(1−d) + Kostenreserve/N + Sicherheitsreserve/N` erforderlich.
Mit rein beispielhaftem `m=0,5 %` liegt die theoretische Hebelgrenze bei
50 % Rückgang gegenüber dem Durchschnitt bereits unter `1,99005×`, ohne
Gebühren oder Sicherheitspuffer. **Das ist kein empfohlener Hebel.**

Nach allen sechs Beispielkäufen könnte die vereinfachte Grenze höher liegen,
aber ohne Nachkäufe bleibt der ursprüngliche Einstand maßgeblich.
Jedes Zwischenstadium, ausbleibendes Rearm und ein sofortiger Sprung müssen
überleben. Tatsächliche Bitget-Marginstufen, Markpreis, Funding, Gebühren,
Cross-/Isolated-Modus und weitere Positionen ersetzen diese Näherung.
Reserve zählt nur, soweit sie tatsächlich verfügbar ist; Nachschießen darf
die bestätigte Kapitalgrenze nicht umgehen.

**In Q9 bestätigt:** zuerst ungehebeltes Spot-Papertrading.
Derivate sind späterer Ausbau mit separat bestätigtem Marginmodell.

### Schutz und Exit

Supertrend allein sichert keine Gewinne: Seine Linie kann bei Aktivierung
unter dem Nettobreakeven oder auf der ungültigen Seite liegen.
Erster Schutzstop, Netto-Untergrenze, Trendflip, Mindestabstände,
Gapverhalten und Nachkäufe nach Schutzaktivierung müssen festgelegt werden.
Ein Long-Trailingstop darf nicht durch Nachkäufe stillschweigend sinken.

Der Auftrag definiert keinen Notausstieg vor +5 %. Das ist eine offene
Risikofrage; ein konventioneller enger Stop würde die Idee des Abfangens großer
Rückgänge verändern und wird deshalb nicht ungefragt ergänzt.
Die unabhängigen Kontolimits bleiben trotzdem verbindlich.
Brokerseitige Stops schützen bei Plattformausfall, können aber bei Gaps und
Liquiditätsmangel keinen Ausführungspreis garantieren.

## Forex, Gold und FTMO

Vorhandene StrategyPlugins und EAs werden fachlich übernommen, nachdem Regeln,
Brokerlots und Kostenmodelle unabhängig geprüft sind. Der dokumentierte
RiskGuard-Fehler wird nicht in das neue System übernommen; siehe
[inventory.md](inventory.md).

Im inventarisierten Registrycode ist XAUUSD mit `trend_pullback` freigeschaltet
(H1-Trendregime, M15-Einstieg/ATR); die betrachteten Forexensembles sind leer.
Das ist ein Codebefund, kein Nachweis aktueller Gewinne oder Kontoperformance.
Die Gold-CBS-Bilder zeigen andere Basketregeln und haben kein entsprechendes
Plugin. Q10 bestätigt Trend/Pullback ausdrücklich als erste MT5-Strategie.

Die H1-Zeitindexverschiebung im vorhandenen Trend/Pullback-Plugin kann historische
Information vorziehen. Timestampsemantik und strikte Kausalität müssen vor
Übernahme mit abgeschnittenen Zukunftsbars nachgewiesen werden.

MT5-Adapter validieren Kontraktgröße, Tickwert, Konto-/Quote-Währung,
Mindestlot/Lotschritt, Stops-/Freeze-Level, Handelszeit und Fillpolicy.
`OrderSend=true` ist keine Fillbestätigung. Retcodes, Tradeevents, Deals und
Positionsabgleich gehören zum Ausführungsjournal.

FTMO-Regeln werden je Kontotyp, Phase und Vertragsstand versioniert.
Offizielle Regeln unterscheiden aktuell 1-Step und 2-Step bei Tages- und
Gesamtverlust sowie Berechnungsmethode. Kein globales „5 %/10 %“-Default.
Equity inklusive offener Ergebnisse, Gebühren und Swap ist zu überwachen.
Tageswechsel wird mit `Europe/Prague` und Sommerzeit behandelt; UTC intern.

Newsrestriktionen und längere Marktschließungen unterscheiden sich zwischen
Kontoprofilen. Auch SL-/TP-Ausführung kann in eingeschränkten Zeitfenstern
problematisch sein; Schutzorders deshalb abzuschalten ist kein tragfähiger Plan.
Exposition wird vorher passend begrenzt oder geschlossen.

Zentraler Handel auf fremden FTMO-Konten ist nach den aktuellen
Personal-Use-Vorgaben nicht automatisch zulässig. Nutzerbetrieb, konkreter
Vertrag und gegebenenfalls Anbieterzustimmung müssen geklärt werden.
Die Crypto-Basket-Logik wird nicht pauschal auf FTMO angewendet.
Quellen: [sources.md](sources.md).

## Unabhängige Risk Engine

Bestätigt: Strategie und AI können Limits nicht überschreiben.
Die konkreten Grenzen werden vor Livefreigabe je Profil beschlossen:

- Maximaler Tages-/Gesamtverlust, Equitydrawdown und Sicherheitsabstand.
- Risiko je Handelsidee/Basket, offene und reservierte Exposition.
- Gesamtbudget je Konto und tenantübergreifend nur bei passender Berechtigung.
- Asset-/Sektor-/Korrelationslimits sowie maximale Kapitalbindung.
- Hebel, Marginreserve und Liquidationsabstand je Zustand.
- Datenalter, Spread-/Slippagegrenze, Handelsfenster und Brokerregeln.

Gate bei Signal und erneut unmittelbar vor Dispatch. Teilfills, Pending Orders,
manuelle Trades und externe Cashflows werden berücksichtigt.
Kill-Switch-Aktionen unterscheiden „keine neue Exposition“, „Orders stornieren“
und „Positionen schließen“. Fail-closed für neue Exposition darf notwendige
Schutz-/Reduce-only-Aktionen nicht blockieren.

## Reproduzierbare Backtests

Ein Ergebnis bindet Strategie-/Parameter-/Riskversion, Codecommit,
Datensnapshot, Instrumentmetadaten, Zeitfenster, Zufallsseed und Kostenmodell.
Brokeridentische Signalquelle, Bid/Ask, Spread, Kommission, Slippage, Funding,
Swap, Liquidation und Mindestmengen gehören zum Modell.

Signale aus abgeschlossenen Kerzen werden frühestens danach ausgeführt.
Wenn Eintritt und Stop in derselben OHLC-Kerze möglich sind, wird die
Reihenfolge mit höherer Auflösung oder konservativer Annahme behandelt.
Keine heutige News-/COT-/Makroversion rückwirkend als damaliges Wissen verwenden.
Bei Aktien zusätzlich Survivorship Bias und Corporate Actions berücksichtigen.

Chronologische Train-/Validierungs-/Testfenster mit Walk-forward-Prüfung.
Überlappende Positionen an Fenstergrenzen und Informationsleckage behandeln.
Der letzte Holdout wird erst nach eingefrorener Auswahl geöffnet.
Mehrfachtests, Parameterräume und verworfene Kandidaten werden protokolliert.

Auswertungen: Netto-PnL, Equitydrawdown, Verlustserien, Profitfaktor mit
Stichprobenkontext, risikobereinigte Kennzahlen, Exposure, Kapitalbindung,
Kostenanteil, Liquidationen und Regelverletzungen.
Buy-and-hold beziehungsweise einfachere Strategien mit vergleichbarer
Kapitalbasis dienen als Referenz.

Stressmatrix: −50 % als Sprung/langer Trend, −70/−90 %, keine weiteren
RSI-Signale, korrelierte Baskets, Spread-/Fundinganstieg, fehlende Daten,
Teilfills, verpasste Stops, Neustart, Doppelzustellung und Tageswechsel.
Resampling/Monte-Carlo ersetzt keinen strukturellen Marginstress.

## Aktuelle Entscheidungsrunde: nur Vorschläge

Q15–Q19 sind gestellt, noch nicht bestätigt. Sie konkretisieren den Start mit
RSI14/Wilder, geschlossenem H4-Rearm, einem regulär ausgelösten sechsten Einstieg
und Supertrend ATR10/Wilder ×3. Schutzbeginn am verkaufbaren +5%-Kurs,
Nettoeinstand-Untergrenze und keine weiteren Nachkäufe nach Schutzaktivierung
werden ausdrücklich als Entscheidungen geführt, nicht vorweg implementiert.

| Profil | Vorgeschlagene Basis und Limits | Abgrenzung |
|---|---|---|
| Crypto Paper | 10.000 virtuelle USDT; BTC/ETH je 500 Kaufprincipal +5 Kostenreserve; täglich 6 %, insgesamt 8 %, Preisnotausstieg −55 % zum ersten Fill | Tagesbasis Equity 00:00 UTC, Gesamtbasis Startkapital; offene PnL/Kosten inklusive, keine automatische Budgeterhöhung |
| MT5 Demo | 0,25 % modelliertes Risiko pro Idee, höchstens eine Idee, täglich 1 %, insgesamt 5 % | Tagesbasis Equity 00:00 Europe/Prague, Gesamtbasis ursprüngliche Demoequity; Brokervertrag und Stopabstand erforderlich |

Mit 1.000 USDT gemeinsamem Kaufprincipal und 10 USDT Kostenreserve bleiben
8.990 USDT ungebunden. Bei beiden vollständigen 5%-Beispielleitern beträgt der
−50%-Stress etwa 410,84 USDT Principalverlust, vor Kosten.
Konservativ verliert ein Kauf bei einem Preis höchstens gleich dem ersten Fill
im Stresszustand `0,5 × erster Fill` höchstens 50 % seines Principals.
Für beide Baskets: maximal 500 USDT in diesem Zustand plus angenommene
10 USDT Kostenreserve, also 5,1 % des frischen Startkapitals.

Das ist keine maximale Verlustgarantie. Vorherige Verluste, höhere Kosten,
Gaps und USDT-Abweichungen verändern die Rechnung. Ein enger 2%-Tagesstop würde
einen abrupten Stresspfad vorzeitig abbrechen, wenn genügend Verlust innerhalb
desselben Tages entsteht. Bei einem langsamen Rückgang über mehrere Tage muss
er nicht auslösen. Deshalb wird 6 % als
**Paper-Vorschlag** zur Entscheidung gestellt; Livewerte sind davon getrennt.

Die −55%-Preisregel wäre eine zusätzliche Verkaufsregel und bleibt ausdrücklich
offen. Auch die Wirkung ausgelöster Kontogrenzen auf Positionen und Wiederaufnahme
bedarf Q18/Q19. „Modelliertes Risiko“ bei MT5 garantiert bei Gaps keinen Fillpreis.

## Kontinuierliche Verbesserung

Bestätigter Modus: zunächst offline Kandidaten erzeugen, keine unkontrollierten
Änderungen im Echtgeldpfad. Jeder Kandidat erhält Daten-, Code-, Parameter- und
gegebenenfalls Modell-/Promptversion.

Promotion: festgelegte Netto-/Risikoschwellen → unabhängiger Test →
Stressprüfung → Shadow/Paper → dokumentierte Freigabe → kleiner Livepilot.
Rollbackversion und Umgang mit bereits offenen Positionen gehören zur Freigabe;
ein Software-Rollback macht Fills nicht rückgängig.

KI bewertet strukturierte Signalinformation und erlaubte News im Shadow Mode.
Kein Brokerkey, keine Ordertools, keine Budget-/Hebelerhöhung.
Timeout-/Fehlerpolicy und Veto-Wirkung sind pro Strategie offen.
Erklärungen und Outcomes fließen ins Journal; Wirkung wird gegen einen
deterministischen Vergleich ohne KI gemessen, inklusive Kosten und Latenz.
Gratisverfügbarkeit eines Modells ist kein Beleg für Datenschutz oder
zuverlässige Antworten.
