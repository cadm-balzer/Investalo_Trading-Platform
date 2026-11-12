# H4-RSI mit H1- oder H4-Gewinnschutz

IP-074,2026-11-12: `futures_capital_signals.py` verbindet den bestätigten
Q41–Q43-Kapitalkern mit den Einstiegs-/Nachkaufsignalen und einem getrennten
Schutzindikator. Eigene Version `isolated-usdt-capital-signals/1`.
IP-073`b9a9c0e` ist in Main`452c9d8` verifiziert.
Reines Forschungsmodell; bestehende Spot-, Paper- und Legacy-Futuresprofile
bleiben unverändert. Kein Broker, AI-Aufruf oder Runtimewechsel.

## Gemeinsame Preisachse, getrennte Indikatoren

`CapitalSignalProfile` bindet den vollständigen Kapitalplan, den
Schutztimeframe1h/4h, Slippage und einen ausdrücklich erklärten Annahmendigest.
`CapitalHour` benötigt alle3–7 Plansymbole in kanonischer Reihenfolge,
je eine geschlossene native H1-Trade- und Markkerze auf identischer UTC-Achse.
Preisarten, offene/revidierte/alte Kerzen, Lücken und unvollständige Achsen
werden abgewiesen. Die exakt letzte unveränderte Kerze ist idempotent,
auch nach einem Fill; kein rückwirkender Gewinnschutz aus dem alten Close.

Vier vollständige H1-Trade-Kerzen ergeben einen geschlossenen H4-Eingang.
RSI14/Wilder und Erstkaufbestätigung/Rearm aktualisieren nur alle vier Stunden.
Der Schutzindikator verwendet wahlweise jeden geschlossenen H1-Trade-Eingang
oder denselben aggregierten H4-Eingang: Supertrend ATR10/Wilder×3.
Tradepreise steuern die Strategie; Markpreise steuern Equity und Liquidation.

`observe_capital_prices` verarbeitet ausdrücklich erklärte feinere Trade-/
Markbeobachtungen. Es prüft den zuletzt bekannten Stop, ohne zukünftige
Indikatorwerte zu nutzen. Beim Stundenabschluss wird zuerst der alte Stop
geprüft, danach der geschlossene neue Schutzindikator berücksichtigt.
OHLC alleine legt keine Reihenfolge von High/Low und keinen Stopfillpreis fest.
Der spätere Marktjob muss dieselbe deklarierte feinere Achse für beide
Schutzvarianten verwenden. Dieser Adapter erzeugt keine Intrabarfills.

## Tatsächliche Staffel und fester Baskethebel

Erstkauf nach zwei geschlossenen H4-RSI-Werten strikt unter30.
Nachkauf erst nach RSI strikt über30 seit dem vorherigen tatsächlichen Kauf,
anschließend wieder unter30 und Maximalfillpreis höchstens95% des letzten
tatsächlichen Stufenpreises. Genau30 ist weder Einstieg noch Rearm.
Das Fullfill-Modell setzt Rearm und Unter30-Zähler nach jedem Kauf zurück.
Alle fünf automatischen Stufen verwenden das bestätigte Eigenkapitalbudget;
die sechste bleibt manuell und erhält nur einen Informationsstatus.

Vor dem ersten Einstieg friert `declare_signal_leverage` eine ausdrücklich
erklärte2×–10×-Forschungsentscheidung für den ganzen Basket ein.
`assess_capital_signal` bindet Closed-H4-Signalzeit, Profil und vollständigen
Zustand an die Kapitalprüfung. `simulate_signal_entry` prüft diese Bindung
erneut vor dem synthetischen Vollfill. Signal/Marks müssen aktuell bleiben;
kein reservierter Brokerauftrag, Teilfill- oder Unknownorder-Abgleich.
Die spätere AI-Regimeentscheidung wird dadurch noch nicht simuliert.

## Schutz, Liquidation und Kosten

Ein neu beobachteter Tradepreis ab105% des tatsächlichen Durchschnittspreises
aktiviert Schutz und sperrt weitere Käufe. Der Stop steigt ausschließlich:
bestehender Stop, zulässiger bullish Supertrend und Ganzzyklus-Nettofloor.
Dieser berücksichtigt Entry-/Exitfees, signed Funding, bereits realisierte
Teilverkaufs-PnL und deklarierte Exitfee-/Slippagehülle. Ein Gap kann trotzdem
unter dem Floor ausgeführt werden; kein garantierter Profit.

Mark-only-Ereignisse ermöglichen die genaue Bewertung vor Funding, ohne
einen erfundenen Tradepreis oder Gewinnschutz auszulösen. Funding hebt bei
Bedarf einen bereits aktiven Nettofloor an. Zusätzliche Margin aus reservierten
Stufen bleibt gesperrt; nur ausdrücklich belegte Kostenrestoration ist möglich.

−55% vom ersten tatsächlichen Kauf bleiben Tradepreis-Notausstieg.
Eine zuvor eintretende modellierte Markpreis-Liquidation hat Vorrang und
verlangt ihre volle terminale Abrechnung. Der beobachtete Abrechnungsbedarf
bleibt auch bei anschließender Preiserholung bestehen; ein normaler Verkauf
oder neue Einstiege dürfen ihn nicht umgehen. Nach expliziter Abrechnung
bleibt der liquidierte Slot gesperrt, andere korrekt finanzierte Slots nutzbar.
6%/8% bleiben Warnungen und erzeugen keine Konto-Zwangsexits.
Echte Budget-/Order-/Kapitalfehler bleiben verbindlich.

Normale vollständige Exits starten einen neuen Basketzyklus mit neuer
Hebelentscheidung, behalten die Wilder-Historie und löschen keine Kapital-
oder Integritätshalts. Alle Gebühren bleiben im Cash/Nettoergebnis.
`start_capital_signals` akzeptiert ausschließlich eigene flache Genesis:
ein fortgeschrittener Zustand kann keine neue Signalfassade als Restore erhalten.

## Prüfung und verbleibender Marktvergleich

27 neue synthetische Fälle auf dem Host und im gepinnten Python3.14.10.
105 gezielte Kapital-/Legacy-Signal-/Timeframefälle und46 Subtests bestanden.
Tatsächlicher inkrementeller RSI-Rearm durch alle fünf Stufen; drei parallele
Baskets über den Warnschwellen; engerer H1-Stop bei gleichen H4-Einstiegen;
Liquidation vor−55%, Erholung ohne Liquidationsumgehung, Funding/Teilverkaufs-
Nettofloor und volle ursprüngliche Kontostart-/Mitternachtsbasis geprüft.
Eigenreview; keine Agentdelegation, Dependencies, Migrationen oder Publicänderungen.

**Noch kein neuer Futures-Nettoleistungsbefund.** IP-075 ergänzt inzwischen
die [gemeinsame H1-Kohorte](futures-hourly-history.md) für fünf echte Coins.
Es fehlen ein erklärter
Nominalpreisbezug für ältere Fundingabrechnungen ohne Settlement-Markpreis,
gefrorene Kosten-/Margin-/Liquidations-/Intrabarannahmen.
IP-076 ergänzt inzwischen den [eigenen vollständigen Journalrestore](futures-capital-journal.md)
mit ausreichender erklärter Ereigniskapazität. Das alte Legacyjournal bleibt
getrennt. Das wirtschaftliche Profil und der Leistungslauf bleiben
IP-074/IP-069; Holdout unverändert gesperrt.
