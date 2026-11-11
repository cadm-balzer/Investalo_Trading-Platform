# Handelskonzept, Risiko und Nachweis

IP-068 verbindet RSI14/Wilder und fünf Nachkaufstufen mit tatsächlichen
Teilfills und Basketzyklen. Manuelle Reserve/Puffer getrennt, 2×-Basis
mit deklarierter First-fragment-Marginannahme; keine Hebelsteigerung je Stufe.
Fundingbereinigter Gewinnschutz, keine erfundenen Stopfills.
[Vertrag](futures-signal-replay.md).

IP-067 beurteilt Restfills am wirklichen First Fill und ausschließlich schon
gestellter Nettomargin. Fehlendes Polster wird nicht als zukünftiger Transfer
angenommen; Kontogaps schließen alle Baskets ein. RSI-/Staffeladapter jetzt
IP-068. [Vertrag](futures-continuation-stress.md).

IP-066 prüft neue Futures-Käufe direkt am tatsächlichen Brutto-/Nettobuchungsstand.
Teilfills und terminaler Abgleich erhalten Reservierungen bis zur Klärung;
ein unklarer Auftrag sperrt weitere Käufe.
[Vertrag](futures-pending-research.md).

IP-065 bucht Teilfills, signed Funding und Gapdefizite getrennt von Kauf-
autorisierung.2× bleibt Mindestwert des Forschungs-Brokersettings; rechtzeitig
gestellter Zusatzpuffer muss vor spätem Dispatch belegt sein. Keine automatische
Hebelleiter. [Ledgervertrag](futures-event-ledger.md).

IP-064 bindet Futures-Handels-, Mark- und Indexpreise ausdrücklich getrennt.
Funding hat eigene signed Raten/Zeitpunkte; vollständige Funding-/historische
Marginregeln und Ereignisledger stehen vor Nettoleistungsläufen noch aus.
Keine automatische Hebelsteigerung je Kaufstufe. [Datenvertrag](futures-marketdata.md).

IP-063: eigene Offline-Futuresökonomie und Kontostressprüfung implementiert,
ohne Ereignisledger/Regimecaller. −50% vom ersten Fill erfordert anfänglich
effektiven Hebel unter2×, auch bei eingestelltem10×; übrige Baskets, Costs
und gestellte/ungepostete Margin separat prüfen. [Rechenvertrag](futures-economics.md).

Q37 bestätigt als späteres Handelsziel isolierte USDT-M-Long-Futures,
2×–10× nur bei starken, kausal belegten Uptrends und ausreichender Deckung.
Eigenes echtes Basketkapital inklusive Marginpuffer, keine automatischen
Nachschüsse aus anderen Baskets. −50%-Stress und6%/8% bleiben; Hebel reduzieren
oder Einstieg sperren. Spotreferenzen bleiben unverändert; Futuresmodell und
exakte Regimeregeln folgen. [Datenvorcheck/Vertrag](futures-research.md).

Q36/IP-061 bestätigt und implementiert begrenzte Gewinnverwendung im separaten
Offlineprofil: mindestens drei weitere abgeglichene Abschlüsse und eine
ursprüngliche volle Basketstaffel pro Freigabe. Zuerst Slots bis sieben,
danach höhere neue Budgets; offene Staffeln und6%/8%-Risikobasen erhalten.
Bestehender fester Kern bleibt Vergleichsbasis. [Vertrag](profit-etapes.md).

IP-052 implementiert die freigegebene Q32-Paper-Tagesbasis aus Mitternachts-H4-Schlusskursen und vorherigen Mengen/Cash.6%/8%, RSI14/Wilder-Einstiege und echte Quote-Fills unverändert. Fehlende Belege sperren Käufe; Dauerbetrieb/Anzeigeaktivierung bleiben IP-047. [Vertrag](paper-midnight-basis.md).

IP-046: Drei Jahre BTC/ETH-H4 werden im vorhandenen deterministischen
Researchworkflow ausgewertet; ein weiterer Jahresabschnitt ist ausschließlich
als Holdout reserviert. Fensterbildung verändert keine Preise/Strategieregeln
und braucht keine neue Migration oder Brokerkeys. Die beiden Simulationen
führen jeweils eigene10.000-USDT-Konten. Ein gemeinsames Portfolio und
wirtschaftliche Validierung werden daraus nicht abgeleitet. Nächster Schritt:
Paperausführung mit demselben Kern und unabhängigem Risk Gate.
[Protokoll und Grenzen](long-history-backtests.md).

IP-058 nutzt das Q34-bestätigte größere Forschungsprofil mit allen regulären
RSI-Nachkäufen und gemeinsamer Kaufprüfung. Durchschnitt/Fills und manuelle
Reserve bleiben im vorhandenen Kern; normale Paper-/Liveprofile unverändert.
[Nachkaufadapter](staged-portfolio-research.md).

Q35/IP-060 trennt14 Kandidaten von3–5 finanzierten Slots. Feste Budgets dürfen
nach vollständigem normalem abgeglichenem Exit erneut mit RSI-Signal belegt
werden; Riskexits bleiben manuell gesperrt. Offlinepool/Mindestmengenvertrag
implementiert; erweiterte Marktleistung und Paperaktivierung folgen separat.
[Zyklus-, Daten- und Reportvertrag](candidate-pool-research.md).

Stand: 2026-11-10. Der Originalauftrag beschreibt Strategieideen.
Q3/Q4 bestätigen unabhängige Risikogrenzen und kontrollierte Optimierung.
Q6 plant beide Broker im MVP; Q9/Q10 bestätigen BTC/ETH Spot H4 ohne Hebel
und XAUUSD Trend/Pullback H1/M15. Q15/Q17–Q19 bestätigen Signale,
Gewinnschutz und Paper-/Demoprofile. Q23 reserviert die sechste Tranche
für einen manuellen Einstieg mit Nutzerinformation. Q26 bestätigt den
Validierungsmaßstab; Q29/Q30 bestätigen manuelle Freigabe und Meldekanal.

Q33 ergänzt das Planungsziel von3–5 gleichzeitigen Coinbaskets mit vollständiger
Kontokapitalzuordnung und späterer KI-Prüfung der RSI-Signale. Der Nutzer
bestätigt6%/8% weiterhin als verbindliche Kontolimits. Gemeinsame Reservierungen
und Risk Gates begrenzen tatsächliche Käufe; volle Zuordnung erlaubt keine
vollständige Staffel unabhängig vom Risiko. Startprofil und gespeicherte
Einzelassetläufe bleiben bis zur geprüften Umsetzung unverändert.
Hebel/variable Einstiegszahlen sind spätere Kandidaten, keine aktivierten Regeln.
[Portfolio- und KI-Plan](multi-basket-ai-plan.md).

IP-056 berechnet die gemeinsame unveränderte BTC-/ETH-Researchbaseline auf
einem Konto mit atomaren gleichzeitigen Kursbewertungen und Kapitaldiagnose.
Der neue historische Portfolio-Pfad prüft vor der Mitternachtsbasis auch den
abgeschlossenen Tagesverlust. Einzelquote-/Paperpfade bleiben unverändert.
[Policy, Benchmark und Grenzen](portfolio-reference.md).

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

| Regel aus Auftrag | Bestätigte Formalisierung / offene Grenze |
|---|---|
| Erster Kauf bei zweiter Kerze mit RSI unter 30 | Q15: RSI14/Wilder; zwei unmittelbar aufeinanderfolgende abgeschlossene H4-Kerzen strikt `<30`; Ausführung erst danach |
| RSI kurz über 30, danach wieder unter 30 | Q15: mindestens eine geschlossene H4-Kerze `>30` seit letztem Einstieg, dann eine `<30`; genau 30 weder Rearm noch Trigger |
| Weiterer regulärer Kauf nach mindestens 5 % Preisrückgang | Q12/Q15: H4-Schlusskurs ≤95 % des letzten tatsächlichen Einstiegsfills, zusätzlich Rearm/RSI; maximal fünf reguläre Stufen |
| Jeweils 25 % mehr Volumen | Q12 bestätigt Quote-Beträge; Gebührenreserve innerhalb des Gesamtbudgets |
| Fünf Käufe plus Puffer | Q23/Q29: sechste Tranche ausschließlich manuell nach fünf Stufen, ohne RSI, aber weiterhin 5%-Preisabstand; Vorschau/MFA/Risk Gate |
| Schutz ab +5 % vom Durchschnitt | Q17: verkaufbarer Kurs ≥1,05× tatsächlichem Durchschnitt; erster Stop mindestens Nettobreakeven |
| Supertrend-Trailing | Q17: ATR10/Wilder ×3 aus abgeschlossenen H4-Kerzen; nur gültige bullische Linie; monotones Long-Trailing, kein zusätzlicher Flipexit |
| −50 % Kursrückgang abfangen | Q12: erster tatsächlicher Fill als Referenz; jedes Füllstadium stresstesten; Q18: unabhängige Paperkontolimits und zusätzlicher −55%-Notausstieg |

Q15 bestätigt höchstens einen neuen Einstieg pro abgeschlossenem Kerzenereignis.
Rearm-Zustand, Strategieversion und Fillstand müssen Neustarts überleben.
Bei dauerhaft RSI `<30` entsteht nach dieser Rearm-Regel kein weiterer regulärer Einstieg.
Orderannahme ohne Fill schaltet keine Stufe frei.

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

**Vergleichsillustration, keine zulässige reguläre Sechserstaffel:** sechs Fills bei
`100; 95; 90,25; 85,7375; 81,450625; 77,37809375`.
Das ganze Budget ist bereits nach −22,62 % gegenüber Einstieg 1 investiert.
Ohne Kosten beträgt `A ≈ 84,86642`, die +5%-Kursmarke etwa `89,10974`.
Beim Stresspreis 50 entsteht ein Buchverlust von rund **41,08 % des
eingesetzten Quote-Budgets/Einstiegsnominals**. Mit ungehebeltem Basketbudget von 10 % der Kontoequity
wären das etwa 4,11 % Kontoverlust vor Kosten.

Nach Q16 bleiben regulär fünf Stufen: **72,89444 %** Kaufprincipal,
also rund **364,47 USDT** je 500-USDT-Basket. Die **135,53 USDT**
Reserve bleibt ausschließlich für einen bewussten manuellen Einstieg erhalten.
Q29 bestätigt ihre Freigaberegeln. Sie darf weder als sechster regulärer Kauf noch zur
automatischen Erhöhung des Gesamtbudgets verwendet werden.

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

Q17 bestätigt: Schutz aktivieren, sobald der verkaufbare Kurs mindestens
`1,05 × tatsächlicher Durchschnitt` erreicht. ATR10 nutzt Wilders Glättung;
Supertrend-Faktor 3, Standardbasis `(high + low) / 2`, geschlossene H4-Daten.
Nur eine gültige bullische Linie für einen Longstop verwenden.

`neuer Stop = max(alter Stop, Nettobreakeven, gültige Supertrend-Linie)`.

Nettobreakeven enthält tatsächliche Einstiegskosten und modellierte Exitkosten.
Bei fehlender/ungültiger Linie bleibt die Netto-Untergrenze beziehungsweise
der bisherige Stop bestehen. Keine Lockerung des Stops, keine Nachkäufe
nach Aktivierung und kein zusätzlicher Ausstieg allein wegen Trendflip.
Broker-Mindestabstände, Tickrundung und Platzierbarkeit prüfen; eine nicht
platzierbare Schutzabsicht darf nicht als bestätigter Brokerstop angezeigt werden.

Q18 ergänzt ausdrücklich den Preisnotausstieg: verkaufbarer Kurs
`≤0,45 × erster tatsächlicher Fill`. Kontogrenzen und dieser Ausstieg werden
laufend geprüft, nicht erst zum H4-Schluss. Exit und Risikosperre gehen vor
jeder regulären oder Notfall-Kaufabsicht.
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

Q26 bestätigt Datenziele und einen wirtschaftlichen Forschungsfilter:
mindestens drei Jahre Crypto beziehungsweise zwei Jahre brokerpassendes Gold
anstreben; im unabhängigen Holdout positiven Nettoertrag, PF ≥1,2 und mindestens
30 geschlossene Baskets je Crypto-Asset beziehungsweise 100 Goldtrades.
Fehlende Daten/Stichprobe verhindern den
wirtschaftlichen Nachweis, nicht technische Paperbeobachtung zur Datensammlung.
Trainingszahlen ersetzen den Holdout nicht. Vor Optimierung werden Fenster,
Warm-up, Kosten-/Fillmodell und Vergleichsprotokoll eingefroren.
Diese Schwellen sind kein statistischer Gewinnbeweis.

Der deterministische Referenzbacktest umfasst **fünf reguläre Einstiegsstufen
mit unangetasteter manueller Reserve**. Er darf keine rückblickend günstig
gewählten manuellen Käufe erfinden. Tatsächliche Paperentscheidungen werden
mit Nutzer, Zeitpunkt, damaliger Quote, Riskentscheidung und Fill journalisiert.
Ein Replay dieser Ereignisse ist eine gesonderte diskretionäre Auswertung,
kein Nachweis automatischer Strategieperformance. Gleiche Daten-/Kostenbasis
und Auswahlwirkung bei Vergleichen offenlegen.

## Bestätigte Paper-/Demoprofile

Q18/Q19 sind bestätigt. Zahlen gelten ausschließlich für die beschriebenen
simulierten beziehungsweise getrennten Demokonten, nicht für Echtgeld.

| Profil | Bestätigte Basis und Limits | Abgrenzung |
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
**Paperwert** in Q18 bestätigt; Livewerte sind davon getrennt.

Ausgelöste Crypto-Kontolimits schließen simulierte Positionen und sperren neue
Käufe bis zu bewusster Wiederaufnahme. Keine automatische Budgeterhöhung oder
Kompensation früherer Verluste. MT5-Lots werden unter Einbeziehung modellierter
Kosten abgerundet; unter Broker-Mindestlot wird die Idee ausgelassen, niemals
über das bestätigte Risiko aufgerundet.
„Modelliertes Risiko“ bei MT5 garantiert bei Gaps keinen Fillpreis.

## Manuelle Reserve und Nutzerinformation

**Bestätigt, Q23:** Puffer ausschließlich für manuellen Einstieg behalten und
den Nutzer informieren. Die automatische −40%-Regel ist verworfen; keine
automatische Order und keine daraus abgeleitete Alarmgrenze.

**Bestätigt, Q29:** Freigabe erst nach fünf abgeschlossenen regulären Stufen;
höchstens eine manuell bestätigte zusätzliche Stufe je Basket; kein RSI-Signal
erforderlich, aber Kaufpreis höchstens 95 % des letzten regulären Fill-VWAP.
Die vorhandene 5%-Regel bleibt damit ausdrücklich erhalten.

Unverändertes Maximum: ursprüngliche sechste Quote-Tranche von rund
135,53 USDT im 500-USDT-Kaufprincipal. Tatsächliche Rundung, Teilfills und
Restbudget gehen vor Anzeige; 5 USDT Kostenreserve für den **ganzen Basket**.
Reservierter Betrag ist kein zusätzliches Kontokapital.

Vorgesehener Bedienablauf: berechtigter Owner/Trader → Vorschau mit Konto,
Asset, Reserve, Quote, Preislimit, Menge, Gebühren und Risikowirkung →
frische MFA-Bestätigung → kurz gültige, an die Vorschau gebundene Freigabe →
idempotenter Orderintent → erneute Risikoprüfung vor Dispatch.
Eine veraltete Vorschau muss aktualisiert werden; Preis/Budget nicht still erhöhen.

Der manuelle Weg beginnt im bestätigten Crypto-Papermodus. Kontolimits,
−55%-Exit, aktiver Gewinnschutz, Datenfehler oder ungeklärte Orders sperren
den Kauf. Schutz und Exit haben Vorrang. Teilfills verbuchen, Restreserve
während offener Order sperren; Doppelbestätigung/Neustart erzeugen keinen
zweiten Einstieg. Keine automatische Reserveauffüllung.

**Bestätigt, Q30:** einmalige Cockpitmeldung nach Abschluss der fünften Stufe,
ergänzt um vom Nutzer einschaltbare E-Mail. Meldung: „Fünf Einstiegsstufen
abgeschlossen; Reserve zur manuellen Prüfung verfügbar.“ Dazu aktuellen
Risikostatus und Sperrgründe zeigen. Verfügbare Reserve bedeutet nicht, dass
ein Kauf gerade zulässig ist; Meldung ist keine automatische Kaufentscheidung.

Stressvergleich ohne Kosten bei fünf regulären Fills
`100; 95; 90,25; 85,7375; 81,450625`: Beide Baskets verlieren bei Preis 50
zusammen rund **314,93 USDT**, während die Reserve Cash bleibt.
Ein möglicher manueller Kauf senkt den Einstand, erhöht aber Verlustexposition
gegenüber Cash. Dieser Vergleich ist eine Rechenillustration, kein
rückblickend ausgewählter manueller Signalpfad.

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
