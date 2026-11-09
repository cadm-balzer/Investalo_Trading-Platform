# Gemeinsames Basketportfolio und spätere KI-Signalprüfung

Stand2026-11-09. Q33 bestätigt das Planungsziel: drei bis fünf verschiedene
Coins gleichzeitig, das Kontokapital vollständig in der Kapitalplanung
berücksichtigen und später RSI-Signale durch Marktanalyse prüfen.
Der Nutzer bestätigt anschließend ausdrücklich: **6% Tagesverlust und8%
Verlust zum Startkapital bleiben verbindlich.**

## Kapital und gemeinsames Risiko

Alle Baskets teilen ein Konto, eine Equity und dieselben Kontolimits.
Kapitalzuordnung ist keine sofortige Investition. Kaufprincipal, Kostenreserve,
reservierte spätere Stufen, verfügbare Liquidität, tatsächliche Positionen und
verbleibender Verlustspielraum werden getrennt geführt. Kapital darf nicht
gleichzeitig mehreren Baskets zugesagt werden; offene Kaufaufträge zählen mit.

Als reine Rechenillustration würden10.000 USDT bei gleich großen Slots für
drei Coins rund3.333,33 USDT, für fünf Coins2.000 USDT je Slot ergeben.
Diese Beträge enthalten noch keine Kostenaufteilung und sind **keine
freigegebenen Kaufbudgets**. Volle Kontoplanung bedeutet weiterhin, dass
Risikogates einen Teil der geplanten Einstiege sperren können.

Der Konflikt ist konkret: Bei gemeinsamem −50%-Rückgang vom jeweils ersten
Fill und der bisherigen beispielhaften5%-Preisstaffel ergäben vollständig
zugeordnetes Kontokapital und fünf reguläre Stufen etwa31,49% Kontoverlust
vor Kosten. Einschließlich der manuellen sechsten Stufe wären es41,08%.
Die Aufteilung auf drei statt fünf Coins ändert diesen korrelierten
Beispielverlust nicht. Tatsächliche RSI-Signale, Fills, Gaps und Kosten können
andere Pfade erzeugen; dies ist weder eine Prognose noch eine Verlustgarantie.
Die6%/8%-Gates greifen bei regulärer Beobachtung vorher ein; ein Gap kann
die Schwellen überschreiten. Ein Limit garantiert keinen maximalen Verlust.

Ein Portfolioallocator muss daher Kaufbudgets und reservierte Exposition
gemeinsam vor jedem Kauf prüfen, statt einfach das bisherige500-USDT-Profil
hochzuskalieren. Kein Anspruch, jeden Slot zu belegen oder jede Staffel
vollständig auszuführen. Korrelationsstress und bisherige Verluste gehören
in diese Prüfung. Die manuelle Reserve bleibt bewusst manuell.

## Nächster Forschungscheckpoint IP-055

IP-056 bereitet ihn mit einer gemeinsamen unveränderten BTC-/ETH-Baseline
vor: synchronisierte H4-Quotes, ein Konto und messbare Kapitalnutzung.
[Offlinekern, Kennzahlen und Abnahme](portfolio-reference.md).
Die Auswahl zusätzlicher Coins ist erfragt; die größere Allokation bleibt
vor ihrem ersten Leistungslauf genau festzulegen.

Die bisherigen BTC-/ETH-Läufe mit je eigenem10.000-USDT-Konto bleiben
unverändert. Ihre Gewinne dürfen nicht als gemeinsames Portfolio addiert werden.
Geplant ist ein neuer versionierter Portfolio-Researchlauf:

- Ein gemeinsames Konto und chronologische Ereignisverarbeitung über alle Coins.
- Konfigurierbare Kapazität von drei bis fünf unterschiedlichen Coins; keine
  erzwungenen Einstiege ohne Signal.
- Gemeinsame Reservierungen, Kosten, Equity, Kontorisikogates und Schutzaktionen.
  Regelmäßige RSI-Einstiege und der vorhandene deterministische Handelskern bleiben.
- Nachvollziehbare Auswahl bei mehr gleichzeitigen Signalen als freien Slots;
  stabile Reihenfolge und vollständig protokollierte verworfene Signale.
- Auswertung von Kontorendite, Kapitalbindung, Drawdown, korreliertem Stress,
  Kosten und vergleichbarem Buy-and-hold-Benchmark.

Vor Leistungsläufen festlegen: zusätzliche zulässige Coins neben BTC/ETH,
verfügbare Historien und Instrumentregeln, exakte Budget-/Kostenverteilung,
Ablehnungsregel bei korreliertem Stress/fehlendem Verlustspielraum,
Resizing-/Wiederbelegungsregeln und Signalpriorität. Gleiche Slotgewichte sind
ein Vorschlag, keine bestätigte Strategieentscheidung. Kandidaten und
Auswahlregeln werden vor der Auswertung eingefroren; der vorhandene Holdout
bleibt reserviert. Forschung und Paper erhalten eigene Versionsnachweise.
Das laufende Entwicklungsprofil bleibt bis zur geprüften Umsetzung unverändert.

## Spätere KI-Prüfung IP-021/IP-022

Vorgesehener Ablauf:

`geschlossenes H4-RSI-Signal → Marktanalyse → erlaubte Strategievariante
→ unabhängiges Portfolio-Risk-Gate → Ausführung`

Die KI liefert eine begründete Bewertung des Einstiegs und kann später zwischen
vorab validierten Varianten innerhalb eines genehmigten Risikoprofils wählen.
Sie kann Kontolimits weder anheben noch Schutzaktionen verzögern.
Zunächst werden Bewertungen ausschließlich im Shadow Mode protokolliert und
mit der unveränderten Referenz verglichen.

| Kontext | Geplante Behandlung |
|---|---|
| Marktphase / Wall Street Cheat Sheet | Beschreibendes Modell; Phasen anhand messbarer Trend-/Volatilitätsmerkmale und Unsicherheit operationalisieren, keine nachträglichen perfekten Phasenlabels |
| Fear & Greed | Quelle, Veröffentlichungszeit und Datenalter festhalten; der Alternative.me-Index bezieht sich auf Bitcoin, keine eigenständige Altcoinmessung |
| News / Makro | Nur zu diesem Zeitpunkt verfügbare Informationen mit Quelle, Publikations-/Abrufzeit und Nutzungsrecht; Texte sind Daten, keine Agentenanweisungen |
| Crypto-Vierjahreszyklus | Hypothese zum Bitcoin-Halving-Kontext, kein verlässlicher Kalender für Auf-/Abwärtstrends aller Coins; Zusatznutzen unabhängig prüfen |
| Coinspezifischer Markt | Trend, Volatilität, Liquidität, Spread und Portfolioüberschneidung als strukturierte Daten |

Entscheidung, Eingabestand, Modell-/Promptversion, gewählte Variante und
Begründung werden nachvollziehbar gespeichert. Heutige News oder ein
heutiges Modell mit Wissen über spätere Kurse beweisen keine historische
Signalqualität; bei nicht rekonstruierbarem Wissensstand zählt die prospektive
Shadow-/Paperbeobachtung. Fehlende/veraltete Daten oder Zeitüberschreitung
sperren einen KI-pflichtigen neuen Einstieg; Schutz und Verkäufe warten
nicht auf die KI.

Tokenkosten bleiben begrenzt: gemeinsamer Marktcontext wird wiederverwendet,
Analysen werden an relevante Signale statt an Quote-Polling gebunden.
Strukturierte kleine Eingaben, Caching mit Datenalter und ein festes
Aufruf-/Kostenbudget werden vor Aktivierung festgelegt. Keine Brokerkeys
oder privaten Nutzerinformationen in KI-Eingaben; kein neuer kostenpflichtiger
Dienst ohne Entscheidung.

## Spätere Varianten und offene Freigaben

Weniger Einstiegsstufen bei klarem Aufwärtstrend und variabler Hebel sind
Forschungsideen des Nutzers. Sie benötigen exakte versionierte Regeln und
unabhängige Validierung. Bei veränderter Stufenzahl sind Volumenverteilung,
manuelle Reserve und Schutzregeln neu festzulegen.

Hebel erfordert zudem ein eigenes Derivate-/Marginprofil mit Liquidation,
Funding, Brokerregeln und Stressprüfung für jedes Füllstadium. Die6%/8%-Limits
gelten auch dann; die KI erteilt keine eigene Risikofreigabe. Das bestätigte
Startprofil bleibt Spot ohne Hebel. Provider, Datenrechte, genaue KI-Autorität
und tatsächliche Aktivierung werden später konkret abgenommen.

Geprüfte Herstellerquelle2026-11-09:
[Alternative.me: Methodik, Bitcoinbezug und API-Nutzungsregeln](https://alternative.me/crypto/fear-and-greed-index/).
Kommerzielle Nutzung erfordert Quellenangabe direkt an der Anzeige; der
API-Zeitstempel allein beweist keinen historischen Veröffentlichungszeitpunkt.
