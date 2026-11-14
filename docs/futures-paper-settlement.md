# Eigene Futures-Paper-Fundingabrechnung

IP-090, lokaler Zwischenstand vom2026-11-14. PR60 (`0bda3e4`) ist in
Main `7cc6848` gemerged; GitHub und Git-Ancestry bestätigt.

Der eigene `settlement`-Journalbefehl verarbeitet native Fundingraten mit
ausdrücklich eingespeisten Marks zum ursprünglichen Settlementzeitpunkt.
Wissens-/Commitzeit und finanzieller Ereigniszeitpunkt bleiben getrennt:
bis zu einer Stunde Publikationsverzug ist zulässig, sofern der Paperzustand
noch nicht über das Settlement hinausgegangen ist. Ältere Ereignisse werden
nicht rückwirkend zwischen bereits gespeicherte Trades geschoben.

## Buchung und Wiedereinstieg in den Quellenfluss

`PaperSettlement` enthält eine eigene Input-ID, Settlementzeit, vollständige
kanonische Markachse, SHA256 des unabhängigen Bewertungsbelegs, ein bis sieben
native Fundingzeilen und höchstens eine neue geschlossene H1-Stunde.
Alle Fundingzeilen haben exakt denselben Zeitpunkt. Native IDs werden
unabhängig von Paket-IDs gespeichert. Gemischte Zeiten, doppelte oder fremde
Assets, veraltete Revisionen und fehlende Stundenbelege werden verworfen.

Die Bewertung erfolgt vor Funding. Am UTC-Tageswechsel steht die eigene
Tagesbasis zwischen Bewertung und Funding, mit den gleichen exakten Marks.
Positive Raten belasten, negative Raten erhöhen den eigenen isolierten Saldo:
`Zahlung = −offene Menge × Settlementmark × native Rate`.
Eigenkapitalstaffel, Hebel, Walletcash, manuelle Reserve und echte Fills
bleiben durch diesen Befehl unverändert. Der bestehende Q45-Cashvertrag gilt
weiter; eine spätere zulässige Kostenrestoration benötigt einen Handelsbatch.

Der Befehl erzeugt keine Modellorders oder Liquidationsfills. Neue H1-Kerzen
aktualisieren RSI/Schutz, ersetzen aber keinen frisch empfangenen Bid/Ask:
der vorherige Handelsquote samt Uhr bleibt erhalten. Die Assetanzeige meldet
bis zu einem frischen Handelsbatch veraltete Quotes. Falls Bewertung/Funding
Liquidation erfordern, bleibt die Sperre bestehen; neuere erholte Kurse dürfen
sie nicht löschen. Die tatsächliche Liquidationsreconciliation folgt separat.

`FuturesMarketObservation.paper_settlement` verbindet die veröffentlichte
native History mit separat eingespeister Settlementbewertung und dem letzten
bestätigten Quellenbeleg. Frühere native oder erwartete Termine dürfen nicht
ausgelassen werden. Noch fehlende erwartete Raten stoppen die Übergabe.
Ein bloß berechneter Abrechnungskandidat berechtigt nicht zur Fortsetzung.

Nach dem fsync-bestätigten Commit trägt der Zustand zusätzlich die Identität
des gesamten Abrechnungsbefehls. `paper_batch(..., settlement=...)` prüft
diesen Beleg, den vorherigen Handelsquote-/Quellencheckpoint und die weiterhin
vorhandenen unveränderten nativen Zeilen. Geänderte Bewertungsbelege, fehlende
oder revidierte History, verspätet sichtbare frühere Settlements und der nächste
Fundingtermin bleiben gesperrt. Der nächste bestätigte Handelsbatch bindet
wieder seinen eigenen aktuellen Quellenbeleg.

## Persistenz und Grenze dieses Zwischenstands

Der eigene Paperjournalvertrag wird um einen expliziten Command ergänzt.
Genesis, Config-/Statedigests und bisherige Befehle bleiben unverändert.
Ein eingefrorener PR60-Referenzreceipt prüft die ursprüngliche Hashidentität.
Vollständiger Restore verarbeitet auch die neuen Abrechnungen; CAS, exklusiver
Writer, Mindestack und Unknown-fsync-Stop gelten weiterhin. Kein Retry.
`FuturesPaperWorker.settle_once` bestätigt einen eigenen Fundingzyklus mit
null Käufen und null Abschlüssen; Archiv-/Singletonguards laufen vor Commit.

**Die bestehende Classic-Fundingquelle liefert weiterhin keinen Settlementmark.**
Der unabhängige zeitlich passende Bewertungsbeleg wird hier ausschließlich
eingespeist und synthetisch geprüft. Es gibt noch keinen realen Collector dafür;
weder spätere Tickerquotes noch Forecastraten oder H1-Approximationen werden
automatisch eingesetzt. Ohne diesen Beleg bleibt der normale Feed gesperrt.
Dieser Zwischenstand behauptet daher keinen laufenden vollständigen
Fundingdienst oder Abgleich mit tatsächlich berechneten Brokergebühren.

18 neue Fälle prüfen Vorzeichen/exakte Bewertung, tatsächliche Quoteuhren,
Mitternacht, eigene Kostenrestoration, Liquidationssperre, Deduplizierung,
Revision/Zeit/Achsen, unveränderte alte Identität, vollständigen Restore,
verlorenen fsync-Ack sowie Quellenbeleg/Publikationsverzug/Historyrevision.
Gepinnte gezielte Regression einschließlich Paper/API/Signal-/Quellenfälle:
93 Fälle/57 Subtests grün unter Python3.14.10. Eine zunächst falsch benannte
Forecast-Fixturespalte wurde korrigiert, anschließend die gesamte gezielte
Regression erneut geprüft. Synthetische Daten, keine Marktrendite.

Weiter: geeignete Settlementmarkquelle und geschützter Bewertungscollector,
dauerhafter Quellen-/Journalcursor mit Archivierung, lokaler Launcher und
State-Readerpublikation an die Assetanzeige,013 Settings-/Kapitaladapter,
Q36-Gewinnetappen und IP-088-Recovery. Kein DB-/Dependency-/Public-/Live-/
AI-Wechsel; laufende Dienste und Opt-ins bleiben unverändert.
