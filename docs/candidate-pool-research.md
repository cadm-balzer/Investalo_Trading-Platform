# Kandidatenpool mit festen wiederbelegbaren Slots

2026-11-10, Q35/IP-060. Bestätigte Kandidaten: BTC, ETH, SOL, BNB, XRP,
ZEC, HYPE, XMR, LINK, XLM, NEAR, BCH, LTC, UNI, jeweils USDT Spot ohne Hebel.
Poolgröße14; unabhängig davon3–5 gleichzeitig finanzierte Baskets.
Ein gültiges RSI-Signal belegt einen freien Slot. Keine Mindestanzahl
erzwungener Positionen. Gleiche feste Budgets aus dem Startkapital,1%
Principal-Kostenreserve,6% Tages-/8% Startkapitalverlust und zusätzliche
korrelierte50%-Stressprüfung bleiben erhalten.

`candidate-pool-rsi-research/1` in
`packages/trading/src/investalo_trading/pool_research.py` verwendet denselben
deterministischen RSI-/Fill-/Schutzkern wie die bisherigen Versionen.
Fünf reguläre Stufen mit RSI-Rearm,5% Abstand vom letzten tatsächlichen
Einstieg und25% wachsenden Kaufbeträgen; sechste Stufe ausschließlich manuell.

## Slotvertrag

Ein angenommenes erstes Intent reserviert sofort einen Slot, auch vor dem
Fill. Weitere Stufen bleiben darin. Bei gleichzeitigen Signalen gilt eine
eingefrorene alphabetische Symbolreihenfolge als technischer Forschungsdefault;
abgelehnte Signale stehen im Report. Slotbudget wird durch Kapazität geteilt,
niemals durch die Anzahl beobachteter Kandidaten. Vollständige zeitgleiche
Kurse aller für einen Lauf konfigurierten Kandidaten sind Voraussetzung.

Der Allokator projiziert Positionen und verbleibende Kauforders auf genau3–5
technische Slots. Freie Slots halten ihre Kostenreserve vor. Jeder Kauf wird
vor Aufnahme und Dispatch vollständig geprüft, ohne stilles Verkleinern.
Bereits bezahlte Fees stecken in Cash/Equity; die nächste Kostenreserve muss
erneut aus tatsächlichem Cash finanzierbar sein. Realisierte Gewinne erhöhen
die nominalen Budgets nicht.

Teilfüllungen, unbekannte Outcomes, angeforderte Stornos und offene Exits
halten den Slot. Ein ungefülltes Kaufintent gibt ihn erst nach autoritativem
Stornoabgleich frei. Ein gefüllter Basket gibt ihn erst nach vollständigem,
abgeglichenem Trailing-/Gewinnschutzexit frei. Die endgültige Sellfee gehört
zum alten Zyklus und darf kein Kontolimit übersehen lassen.

Risiko- und nicht klassifizierte Exits quarantänisieren den Slot. Keine
automatische Wiederaufnahme; `resume_slot` verlangt explizite Autorisierung,
flache Position, abgeglichene Orders und gültige Kontolimits. Die Anwendung
muss Nutzerbindung/frische MFA beweisen; der Domain-Auditverweis allein
authentifiziert niemanden. Nach Freigabe braucht derselbe Coin zwei neue
geschlossene RSI-Signale. Andere Coins können den freien Slot übernehmen.

Aktuelle Zyklusausgaben begrenzen den Slot. Immutable Abschlussbelege und
Lifetime-Principal/Buy-/Sellfees bleiben getrennt erhalten; doppelte Fills
verändern sie nicht. Alte Versionen, Digests und Runtime-Loader unverändert.
Das Modul hat keine API-, Worker-, Broker- oder Cockpitaktivierung.
`PoolPlan` erlaubt begrenzte technische Symbolmengen für synthetische Tests/
eingefrorene Forschungskohorten; der bestätigte Marktpool steht separat in
`APPROVED_CANDIDATES`. Das ist keine automatische Zulassung anderer Marktassets.

## Öffentliche Datenverfügbarkeit

[Messrecord](research-protocols/portfolio-candidate-pool-preflight-20261110.json):
13 der14 Kandidaten liefern aktuelle Bitget-V3-Spotmetadaten als `online`.
XMRUSDT liefert bei Metadata und History `40034`, „Parameter … does not exist“.
XMR bleibt Kandidat, derzeit ohne nachgewiesenen ausführbaren Spotpfad.

| Zusätzlicher Kandidat | Aktuelle Spotmetadaten | Gemeldetes launchTime UTC | Zwei H4-Proben am2022-08-01 |
|---|---|---|---|
| ZEC | online | 2025-12-03 | keine |
| HYPE | online | 2024-12-18 | keine |
| XMR | nicht gefunden | — | nicht gefunden |
| LINK | online | 2021-04-15 | vorhanden |
| XLM | online | 2023-08-24 | keine |
| NEAR | online | 2022-04-29 | vorhanden |
| BCH | online | 2018-08-22 | vorhanden |
| LTC | online | 2018-08-06 | vorhanden |
| UNI | online | 2021-04-20 | vorhanden |

Metadaten sind heutige Providerangaben, keine damaligen Regeln und kein
Beweis der ursprünglichen Coinexistenz/ersten Börsennotierung. Kein
vollständiger Dreijahresnachweis aus zwei Kerzen. Die fünf älteren Beobachtungen
stammen unverändert aus IP-059; die neun neuen aus IP-060. Insgesamt20 geprüfte
Kerzen für zehn Kandidaten, drei leere Samples und eine explizite Fehlerantwort.
Der alte Record bleibt als damaliger Vorcheck unverändert.

`PoolInstrumentRules` ergänzt Mindestmenge separat von den v1-Regeln.
Dispatch prüft Mindestmenge und Mindestquote nach Mengenrundung und Slippage.
Heute beobachtete Regeln müssen als Modellannahmen eingefroren werden.
Offizielle Referenz:
[Bitget Instruments/History](https://www.bitget.com/docs/catalog/market/market-data).
Öffentliche V3-Marktmetadaten ändern keine private Classic-V2-Adapterbindung.

## Abnahme und nächste Arbeit

114 gezielte gepinnte Trading-/Paper-/Workerfälle und65 Subtests bestanden,
darunter17 neue Poolfälle; unabhängiger Code-Review ohne Blocker.
Ein natürlicher synthetischer H4-Test erzeugt15 Käufe über drei RSI-Zyklen,
zehn vollständige Trailingexits und wiederbelegt dieselben fünf festen Slots.
Weitere Fälle prüfen Nachkaufstaffel/manuellen Fill, konkurrierende Signale,
Teil-/unklare Orders, Stornos, Kosten, Mindestmengen und finalen
Sellfee-Kontolimitübertritt. Synthetische Daten beweisen keine Profitabilität.

Der separate Report enthält Netto-PnL, Kosten/Fills, Kapital- und
Slotbelegungskurven sowie Plan-/Policy-/Config-/Daten-/Kostendigests.
Geplantes Kapital verwendet Kapazität. `benchmark_status=not_computed`:
Die alte passive Referenz würde bei14 Vollbudgets das Konto überziehen.
Vergleichbaren Benchmark vor echten erweiterten Leistungsläufen einfrieren.

Als Nächstes eigene erweiterte Daten-/Snapshotverträge und vollständige
Historienabdeckung prüfen. Ein historischer Lauf muss vor Auswertung seine
datenberechtigte Teilmenge und gemeinsame Zeitfenster einfrieren; jüngere/
fehlende Kandidaten dürfen nicht durch erfundene Daten oder rückblickende
Auswahl aufgefüllt werden. Zusätzliche Kohorten separat ausweisen.
Das reservierte Holdoutfenster bleibt unangetastet. Dauerhafte Reservierung,
Brokerabgleich, Paperintegration und sichtbare Marktresultate folgen in IP-055.
