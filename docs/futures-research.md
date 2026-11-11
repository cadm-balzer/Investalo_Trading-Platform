# Crypto-Futures: bestätigtes Ziel und Datenvorcheck

2026-11-10, Q37/IP-062. Der Nutzer plant die Basketstrategie später als Futures
mit marktphasenabhängigem Hebel2×–10× bei starken Uptrends. Bestätigtes erstes
Forschungsprofil: **USDT-M, nur Long, isolierte Margin**. Das Basketbudget ist
echtes Kapital für Einstiege, Kosten und ausdrücklich reservierte Marginpuffer;
keine automatischen Nachschüsse aus anderen Baskets.

**−50%-Stress und6% Tages-/8% ursprünglicher Startkapitalverlust bleiben
verbindlich.** Das Risikomodell darf Hebel reduzieren oder Einstiege sperren.
Stresspreis ist50% des **ersten tatsächlichen Einstiegfills**, nicht des
später abgesenkten Durchschnittspreises. Jeden Fillstand einschließlich
ausbleibender weiterer RSI-/Rearm-Signale prüfen.
Kein zugesicherter Mindesthebel bei fehlender Deckung. Maximal sieben Baskets
und die bestätigten Gewinnetappen bleiben Planungsziele; Futures-Gewinne müssen
zusätzlich Funding und alle Abschluss-/Liquidationskosten berücksichtigen.
Diese Richtung ersetzt das bisherige spätere Spotziel; laufende Spotmodelle
bleiben unveränderte Forschungsreferenz und Entwicklungspaper.

## Öffentliche Kontrakt- und Historienproben

AVAX, HBAR, TRX, BGB, BAT und RENDER sind erlaubte Alternativkandidaten zu
XMR/ZEC/HYPE/XLM. Noch keine endgültige Vier-gegen-Vier-Auswahl oder neue
Runtimewhitelist. Alle sechs Alternativen und alle14 bisherigen Coins haben
aktuell einen `normal` USDT-M-Perpetualkontrakt bei Bitget.

| Alternativkandidat | Kontrakt aktuell | Trade-H4-Probe2022-08-01 | Mark-H4-Probe2022-08-01 |
|---|---|---|---|
| AVAX | normal | 2 Kerzen | 2 Kerzen |
| TRX | normal | 2 Kerzen | 2 Kerzen |
| HBAR | normal | keine | keine |
| BGB | normal | keine | keine |
| BAT | normal | keine | keine |
| RENDER | normal | keine | keine |

Der frühere Spotbefund gilt nicht automatisch für Futures: XLM liefert hier
beide frühen Trade-/Markproben, XMR hat aktuell einen Futureskontrakt.
Frühe Proben fehlen auch für XMR/ZEC/HYPE. Insgesamt13 der20 geprüften
Kontrakte liefern je zwei Trade- und Markkerzen,52 geprüfte OHLC-Kerzen.
Dies beweist keine lückenlose Dreijahreshistorie oder damaligen Kontraktregeln.
Die leeren `launchTime`-Felder erlauben keine Aussage zum Listingbeginn.

[Messrecord](research-protocols/futures-candidates-preflight-20261110.json):
eine öffentliche Classic-V2-Kontraktinventur und40 kleine öffentliche
Historienabfragen, ohne Schlüssel, Konto, Trades oder Holdout. Exakte URLs,
Provider-/Abrufzeiten, Responsehashes, aktuelle vollständige Kontraktfelder
und tatsächlich zurückgegebene Kerzen gespeichert; bounded Decimal-/OHLC-/
UTC-Prüfung und JSON-Roundtrip bestanden. Alle aktuellen Kontraktgrenzen
umfassen den gewünschten Hebelbereich; das ist keine Risikofreigabe.
Aktuelle Fundingintervalle: RENDER4h, die fünf anderen Alternativen8h.
Nicht pauschal8h annehmen und heutige Werte nicht als historische ausgeben.

## Eigenes wirtschaftliches Modell vor dem Leistungslauf

Ein Spotbacktest multipliziert mit Hebel bildet Futures nicht ab:
Nominalexposition, tatsächlich gestellte Margin, freie Sicherheiten,
reservierte Kaufstufen/Marginpuffer und Kontoequity getrennt buchen.
Bei festem Nominal ändert ein höherer eingestellter Hebel zunächst die
Mindestmargin; mehr Gewinn entsteht erst durch mehr Nominalexposition.
Verluste steigen dann ebenfalls. Die aktuelle Position bewertet sich am
Markpreis; Ausführung braucht Trade-/Bid-/Askpreise.

Bei einer isolierten Longposition ohne zusätzliche Margin verbraucht eine
Gegenbewegung ungefähr1/Hebel die Anfangsmargin. Maintenance und Kosten
führen früher zur Liquidation. Ein sofortiger−50%-Sprung kann daher eine
ungepufferte10×-Position lange vor dem bisherigen−55%-Notausstieg schließen.
Nachkäufe oder ein späteres RSI-Rearm sind kein Schutz vor diesem Sprung.
Reservierte, noch nicht gestellte Margin zählt bei einem unmittelbaren Gap
nicht als Liquidationsdeckung. Nur bereits gestellte Margin oder belegbar
vor der Bewegung wirksam verfügbare Sicherheiten dürfen den Test tragen.
Jeder Fillstand, auch der erste, benötigt unabhängig:

- Kausale vollständige Trade-/Mark-/Indexhistorie und Fundingereignisse.
- Historische Kontraktpräzision, Mindestmenge/-nominal, Fee-/Liquidationskosten
  und größenabhängige Maintenance-/Marginstufen oder ausdrücklich belegte
  konservative Annahmen; unbekannte Daten nicht mit Null ergänzen.
- Prüfung von Liquidationsabstand, gestellter und verfügbarer eigener Margin,
  korreliertem Kontoverlust und Reserven vor Intent und erneut vor Dispatch.
- Konservative Intrabar-/Gapreihenfolge, Teilfills, Stornos und unklare Orders;
  keine Stops als garantierte Preise oder spätere Nachschüsse vorwegnehmen.
- Funding-/kostenbereinigten Breakeven für den bestehenden Gewinnschutz.
  Die manuelle sechste Kaufstufe bleibt manuell und wird nicht automatisch
  zum Liquidationspuffer umgewidmet.

## Nächster Implementierungsschritt

IP-066 ergänzt ledgerbasierte Kaufprüfung, begrenzte Pendingreservierungen,
Teilfill-Dedupe und genaue Terminalsummen. Fortsetzungsstress für die tatsächliche
First-fill-/Restfillfolge sowie kausaler Signal-/Replayadapter folgen IP-067.
[Vertrag und Grenzen](futures-pending-research.md).

IP-065 ergänzt den abgeglichenen Offlinebuchungsledger: Teil-/Vollfills,
Funding, Margintransfer und Gapdefizite.31 neue Fälle/222 gepinnte Fälle mit
157 Subtests grün. Keine Order-/Kaufgenehmigung.
[Vertrag und Brokerpuffergate](futures-event-ledger.md).

IP-063 implementiert separate Offline-Ökonomie und Kaufstressrechner:
44 neue Fälle,191 gepinnte Fälle/135 Subtests bestanden. Nominal, gestellte
Margin und Funding getrennt;−50%-Gap verlangt am ersten Fill effektiven
Hebel unter2×. Ereignisledger/Teilfills/Gaps bleiben IP-063, ausdrücklich
Futures-/Preisart gebundene Daten sind in IP-064 ergänzt: BTC/ETH besitzen
je6576 Trade-/Mark-/Indexkerzen für drei Jahre;81 gepinnte Daten-/Workerfälle
grün. Fundingformat vorhanden, echte Fundinghistorie/historische Marginregeln
offen. [Datenvertrag und Messrecord](futures-marketdata.md).
[Rechenvertrag und Beispiele](futures-economics.md).
Bestehende Spotdaten/-Digests/-Ergebnisse nicht umetikettieren.
Neue Futuresdatenverträge unterscheiden Markt und Preisart ausdrücklich.
Danach vollständige Historien/Kohorten und Kostenannahmen einfrieren und
feste Budgets gegen Gewinnetappen vergleichen, bevor Holdout/Paper folgen.

Noch zu spezifizieren: exakte messbare Uptrend-/Regimekriterien, Verhalten
außerhalb dieser Phase, Hebelauswahl, Aufteilung Kaufmargin/Marginpuffer/
Kosten sowie Behandlung eines Regimewechsels bei offenen Baskets.
„Definitiver Uptrend“ ist kein vorab verfügbares Wissen; nur zum damaligen
Zeitpunkt belegte Signale verwenden. KI darf Margin-/Kontogates nicht lockern.
Keine neuen Abhängigkeiten, Migrationen, Konto-/Hebeländerungen, Brokerorders,
öffentliche Dienständerungen oder Echtgeldaktivierung in IP-062.

Offizielle Referenzen:
[Classic-Kontraktmarkt](https://www.bitget.com/docs/catalog/classic-contract-market/classic-contract-market),
[Margin und Liquidation](https://www.bitget.com/support/articles/360058821652),
[Futuresbegriffe](https://www.bitget.com/support/articles/12560603809455).
