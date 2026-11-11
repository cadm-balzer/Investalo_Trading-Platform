# Begrenzter Futures-Signalreplay

IP-068 verbindet den gemeinsamen RSI-/Supertrendindikator mit den bestehenden
Futures-Risk-, Ledger-, Pending- und Continuationkernen. Neue reine Version:
`isolated-usdt-long-signals/1` in `futures_signals.py`. Bestehende Module,
Spot-/Paper-Versionen und Packageexporte bleiben unverändert.

## Forschungsprofil und Eingaben

`ReplayProfile` friert den vollständigen Futuresplan, separate eigene
Marginpuffer für jedes Plansymbol, Slippage und einen expliziten
Annahmendigest ein. Es gibt keine automatisch gewählte Pufferaufteilung.
Diese Version verwendet konstant2× als begrenzte Forschungsbasis, keine
ausgedachte Marktphase oder ansteigende Hebel je Kaufstufe.
Regimeabhängige2×–10× bleiben ein separater Validierungsschritt.

Pro Basket: Kapital minus Kostenreserve minus eigener Puffer ergibt den
separaten Sechsstufenpool. Die Gewichte wachsen jeweils25%; Beträge werden
auf das Geldraster abgerundet. Fünf Stufen sind regulär, die sechste bleibt
eine **manuelle Reserve**. Abrundungsreste werden nicht zusätzlich verteilt.
Die geplante Ordermenge ergibt sich aus Stufenmargin ×2 / Maximalpreis,
abgerundet auf das Mengenraster. Tatsächlicher Kaufwert kann durch
Abrundung, bessere Preise oder Teilstorno abweichen.

Der Puffer gehört ausschließlich zum ersten Kaufintent des Basketzyklus.
Für jeden Intent gilt die ausdrücklich deklarierte Modellannahme:
`declared-full-intent-margin-with-first-fragment/research-only`.
Das erste tatsächlich gebuchte Fragment muss die gesamte eigene
Intentmargin enthalten; spätere Fragmente dürfen0 zusätzliche Margin buchen.
Das ist **kein Beleg rechtzeitiger oder atomarer Brokerdeckung**.
Fehlt diese deklarierte Margin, wird bekannte wirtschaftliche Wahrheit
dennoch gebucht und der Replayzustand dauerhaft quarantänisiert.
Keine automatische Nachschuss- oder Umwidmungsfunktion existiert.

`H4Frame` benötigt alle3–7 Plansymbole in kanonischer Reihenfolge, je eine
native `SYMBOL:USDT-M:trade`- und `SYMBOL:USDT-M:mark`-Kerze auf derselben
vollständigen H4-/UTC-Achse. RSI14/Wilder und Supertrend ATR10/Wilder ×3
verwenden ausschließlich Tradepreise; Margin/Equity verwenden Markpreise.
Offene, alte, revidierte, vertauschte, Spot-/Preisart-fremde oder lückenhafte
Frames werden verworfen. Wiederholung des exakt letzten Frames ist
idempotent und bewertet spätere Fills nicht rückwirkend neu.

Ein Frame wird erst nach seinem Close beobachtet. Käufe benötigen höchstens
30 Sekunden alte Signale und frische vollständige Marks. Bei UTC-Mitternacht
wird zuerst der vollständige Markbatch gebucht, einschließlich Prüfung der
bisherigen Tagesgrenze, danach die genaue H4-Tagesbasis vor neuen Fills.
Ein späterer Intradayframe ersetzt keine fehlende Mitternachtsbewertung.
Bei nichtpositiver Equity wird keine positive Tagesbasis erfunden; bekannte
Marks werden im bereits angehaltenen Konto weiter gebucht, die letzte
gültige Basis und sämtliche Halts bleiben erhalten.

## Kausale Staffel und Orderabgleich

Erstkauf: zwei aufeinanderfolgende geschlossene RSI-Werte strikt unter30.
Nachkauf: seit dem letzten tatsächlichen Fill RSI strikt über30 als Rearm,
anschließend wieder unter30; der maximale Fillpreis einschließlich Slippage
darf höchstens95% des VWAP der letzten abgeschlossenen regulären Kaufstufe
betragen. Genau30 ist weder Entry noch Rearm. Jeder tatsächliche neue
Kauffill setzt Rearm und Unter30-Zähler zurück.

`SignalBinding` friert Profil, Symbol, Basketzyklus, Stufe, Intent, kausalen
Frame-/Signaldigest, Zeit, Kaufmenge/-limit sowie Stufen-/Puffermargin ein.
Jede Pendingreservierung hat genau diese Bindung. Der Ledgerprüfer prüft
die vorhandenen eigenen Budget-, Kosten-, Margin- und6%/8%/−50%-Grenzen;
vor einem deklarierten Orderattempt wird der eingefrorene Intent erneut
am aktuellen Zustand geprüft.

Erst exakter terminaler Abgleich schließt eine Stufe ab. Teilgefüllte
bestätigte Stornos zählen mit ihrem tatsächlichen Mengen-/Preis-VWAP;
ungefüllte Stornos verbrauchen keine Stufe. Ein zwischen letztem Fill und
Terminalabgleich tatsächlich beobachteter RSI-Rearm bleibt erhalten.
Ein möglicherweise versandter Auftrag verliert Reserven niemals durch
Zeitablauf oder lokalen Storno. Es gibt höchstens einen ungeklärten
Kaufintent im Konto, jedoch mehrere gleichzeitig gehaltene Baskets.

Jeder bekannte eigene Kauffill wird zusätzlich gegen die tatsächliche
First-fill-/Restmengen-Gaphülle geprüft. Bei vollständigem Fill entfällt
nur der Hinweis `no_remaining_quantity`; alle wirtschaftlichen Fehler
bleiben Sperrgründe. Ungeplante, zyklusfremde oder nach Schutz-/Exitaktivierung
eintreffende Fills bleiben gebucht und quarantänisieren weitere Käufe.
Insbesondere darf eine alte Order nach vollständigem Verkauf ihren
verspäteten Fill nicht als reguläre Stufe des neuen Zyklus anrechnen.

Nach fünf abgeglichenen regulären Stufen entsteht ein einmaliger
Informationsstatus zur manuellen Reserve. Er ist **keine manuelle
Kaufgenehmigung**. Es gibt keinen sechsten Autoentry und in diesem Adapter
keinen Manualexecutor. Ein normal vollständig verkaufter und abgeglichener
Basket beginnt einen neuen Zyklus; Indikatorhistorie bleibt erhalten,
Entryzähler/Staffel/Schutz werden zurückgesetzt. Risikohalts und globale
Quarantäne lassen sich dadurch nicht löschen.

## Schutz und Grenzen

Ein neu beobachteter Tradeclose aktiviert ab105% des tatsächlichen
Durchschnittseinstands den Gewinnschutz. Der Stop steigt ausschließlich:
Maximum aus bestehendem Stop, zulässigem bullish Supertrend und Nettofloor.
Der lineare Ganzzyklusfloor berücksichtigt Entry-/Exitfees, signed Funding
und bereits realisierten Preis-PnL aus Teilverkäufen sowie die eingefrorene
Exitfee-/Slippagehülle. Funding oder Teilverkäufe können einen bereits
aktiven Floor anheben. Ein Fill ist keine neue Kursbeobachtung: sein
vorheriger H4-Close darf keinen erfundenen Gewinnschutz auslösen.

−55% des tatsächlichen First Fill, gekreuzter Schutzstop oder Kontohalt
erzeugen Exitpflichten. Positionen bleiben bis zu ausdrücklich gelieferten
Verkaufsfills bestehen. **Kein garantierter Intrabarstop oder Stopfillpreis
wird simuliert.** Funding und Marginpostings benötigen explizite Evidence;
fehlende Fundinghistorie wird nicht mit Null ersetzt.

Der Adapter verarbeitet begrenzte vorgegebene Ereignisfolgen, erstellt noch
keine wirtschaftlichen Dreijahresergebnisse. Er beweist weder Brokerstatus
noch persistentes CAS, Restore oder Dispatch. Die bestehenden1024er
Identitätslisten werden nicht geleert; volle Listen stoppen den Lauf.
`execution_enabled=false` bleibt fest. Die synthetische Testaufteilung ist
kein freigegebenes wirtschaftliches Forschungsprofil.

## Abnahme und Fortsetzung

36 neue Fälle einschließlich echter inkrementeller RSI-Bestätigung/Rearm,
fünf Stufen/manueller Reserve, tatsächlichem Teilfill-VWAP, spätem Fill nach
Zykluswechsel oder Gewinnschutz, Schutz-/Fundingfloor und drei gleichzeitig
gehaltenen Baskets.310 Hostfälle plus36 finale Modulchecks bestanden:
313 unterschiedliche Hostfälle. Gepinnte Python3.14.10-Trading-/Workerprüfung:
317 unterschiedliche Fälle/228 Subtests grün. Eigenprüfung; keine
Agentdelegation, Daten-/Holdoutabfragen, neuen Dependencies, Migrationen,
öffentlichen Container oder bestehenden Kernmodule geändert.

IP-069 prüft historische Fundingquelle und ein eingefrorenes langes
Futures-Replayprotokoll: ausreichende Kandidatenhistorien, Kosten-/Maintenance-
und Pufferannahmen sowie konservative Ausführungs-/Intrabarreihenfolge.
Lange Läufe benötigen zusätzlich einen geeigneten Ereignisspeicher;
die1024er Identitätsgrenze wird nicht durch periodisches Leeren umgangen.
Belastbare tatsächliche Nettovergleiche bleiben bis zu dieser Provenienz
IP-055/063/BL-030. Keine neue Live-/Produktionsfreigabe.

Der erste IP-069-[Quellencheckpoint](futures-funding-availability.md) belegt
die aktuelle90-Tage-Lücke der nativen Funding-API ausdrücklich.
