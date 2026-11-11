# Isolierte Futuresökonomie und Kaufstressprüfung

2026-11-10, IP-063. `f6617b6` und `54d2a7d` sind in Main`168219f`
verifiziert. Zwei neue, separat versionierte Offline-Rechner:
`isolated-usdt-long-economics/1` und `isolated-usdt-long-stress/1`.
Keine neuen Abhängigkeiten oder Änderungen an alten Spotkernen/-Records.

IP-065 ergänzt inzwischen den reinen Buchungsledger für abgeglichene Teilfills,
signed Funding und Gap-/Close-Ergebnisse.222 gepinnte Fälle/157 Subtests grün.
IP-066 verbindet jetzt die ledgerbasierte Brutto-/Netto-Kaufprüfung mit
begrenzten Intents/Teilfillabgleich. [Vertrag](futures-pending-research.md).
[Ledgervertrag](futures-event-ledger.md).

## Ökonomische Größen

`futures_economics.py` rechnet lineare USDT-Longpositionen:

- Nominal am Markpreis: `quantity × mark`.
- Unrealisierter PnL: `quantity × (mark − average_entry)`.
- Isolierte Equity: bereits gestellte Nettomargin plus unrealisierter PnL.
- Funding-Cashänderung je angegebenem Ereignis: `−quantity × mark × rate`;
  positives Funding kostet Longkapital, negatives schreibt es gut.
- PnL einer vollständigen Schließung: Preisergebnis minus Entry-/Exitfees
  plus gebuchtes signed Funding. Nettobreakeven berücksichtigt dieselben Größen.

Gebuchte Fees/Funding müssen bereits in Cash oder Nettomargin stecken.
Nicht nochmals von Positionsequity abziehen. Ein Margintransfer vermindert
unposted Cash und erhöht gestellte Margin; er verändert keine Kontoequity.
Eingestellter Brokerhebel multipliziert nicht den PnL einer festen Menge.

Maintenance nutzt ausdrücklich ein **konservatives Forschungsmodell**:
Nominal mal Rate der ganzen jeweiligen Stufe. Vollständige monoton geordnete
Stufengrenzen, Maintenance-Raten und maximale Hebel sind Pflicht; Gleichheit
an einer Grenze wählt konservativ die nächste Stufe. Keine Deckung oberhalb
des letzten Caps, kein stiller Standardwert für unbekannte Stufen.
Dies ist keine Replik der historischen Bitget-Liquidation oder progressiver
Margintarife. Historische Broker-/Positionsregeln fehlen weiterhin.

Die konservative Liquidationsgrenze verwendet die höchste Maintenance-Rate
im betrachteten Abwärtspfad und eine explizite Schutzreserve für Closefees.
Gleichheit von isolierter Equity und Schutzbedarf ist bereits unsicher.
Die Schutzrate ist ein Modellparameter, keine gemessene Liquidationsgebühr.

## Gemeinsame Kaufprüfung

`futures_risk.py` nimmt eine gebundene `FuturesPlan` mit3–7 vollständigen
Kontrakten/Basketbudgets, `FuturesView` und `FuturesPurchase` entgegen.
Budget ist echtes Kapital; Costreserve und Marginkapital sind getrennt.
Die weitere Aufteilung reguläre Stufen/manuelle Stufe/Marginpuffer wählt
dieser Rechner nicht. Budgetberechtigung/Gewinnepochen sind vertrauenswürdige
Eingaben des späteren Aufrufers, keine durch den Rechner bewiesene Autorisierung.

`assess_futures_purchase` projiziert einen einzelnen vollständigen Fill
zum angegebenen Höchstpreis und liefert Diagnose ohne Zustandsmutation:

- Exakte Tenant-/Konto-/Plan-/Revisionbindung und vollständige gemeinsame
  Markbewertung, höchstens30s alt; passende UTC-Mitternachtsbasis.
- Kontohalt, bereits gerissene6%/8%-Grenze und aktuell liquidationsgefährdete
  Positionen vor der Projektion prüfen. Ein neuer Kauf darf sie nicht heilen.
- Mengenraster, Mindestmenge/-nominal, eigene Margin-/Costgrenzen sowie
  Initialmargin und größenabhängige Kontrakthebelgrenze prüfen.
- Gestellte Margin einmal übertragen, neue Entryfee einmal buchen.
  Verbleibendes Marginkapital **aller** Slots, Pendingmargin, übrige Costs
  und Zuordnungsrest weiterhin gegen unposted Cash reservieren.
- Stressmark pro Position: kleinerer Wert aus aktuellem Mark und50% des
  **ersten tatsächlichen Fills**. Kein Durchschnittspreis als neue Stressbasis;
  kein vorausgesetzter weiterer RSI-Nachkauf.
- Nur gestellte Margin schützt isoliert. Größter Maintenancebedarf im
  untersuchten Pfad plus Closefeeschutz muss bei Stress gedeckt bleiben.
- Summe der Markverluste bis Stress plus übrige Costreserven darf den kleineren
  Spielraum gegen94% Tagesbasis/92% ursprüngliches Startkapital nicht übersteigen.

Diese erste Prüfung blockiert **alle** offenen/ungeklärten Orders, auch
Pendingorders eines anderen Baskets. Ein Preisbound unter dem aktuellen Mark
wird ebenfalls abgelehnt, statt hypothetischen Sofortgewinn als Riskspielraum
zuzulassen. Gleichzeitig laufende Orders, Teilfills, Funding-/Liquidations-
buchungen und Gapreihenfolge benötigen erst einen eigenen Ereignisledger.
Ein positives Ergebnis ist keine persistente Reservierung, Regimeentscheidung
oder Dispatchfreigabe; `execution_enabled=false` bleibt immer erhalten.

## Was −50%-Stress für den Hebel bedeutet

Am ersten Fill, ohne bisherigen Buchgewinn, braucht eine Longposition mehr
als50% ihres Nominals als gestellte Margin: Verlust bei−50% plus Maintenance
und Schutzkosten. Effektiver Entryhebel `entry_nominal / posted_margin`
liegt dann **unter2×**, unabhängig von einer Brokerhebeleinstellung10×.
Das folgt aus dem bestätigten Stressziel; Uptrends beseitigen keinen Gap.
Bestehende Gewinne und spätere Staffeln verändern die konkrete Rechnung,
nicht die verankerte First-fill-Stressbasis.
Kein fester2×-Start und keine automatische Hebelsteigerung je Nachkauf.
Jeder neue Fill braucht eine Prüfung der gesamten vergrößerten Position und
aller parallelen Baskets. Ein niedrigerer Durchschnitt kann mehr Exposition
erlauben; er garantiert sie nicht. Die konkrete Regime-/Hebelregel bleibt offen.

Synthetischer Vergleich:10.000-USDT-Konto, fünf Budgets je2.000 inklusive
20 Costreserve, Entry/Closefees je0,1%, Maintenance0,5%, Einstieg/Mark100:

| Nominal | Gestellte Margin | Brokerhebel | Effektiver Entryhebel | Diagnose |
|---:|---:|---:|---:|---|
| 100 | 10 | 10× | 10× | isolierter Stress nicht gedeckt |
| 100 | 50 | 2× | 2× | Maintenance-/Closefeeschutz fehlt |
| 100 | 60 | 10× | 1,667× | Riskprüfung bestanden |
| 1000 | 600 | 10× | 1,667× | gemeinsamer Stress genau am Forschungsgrenzwert |

Keine Freigabe eines Budgetprofils oder Performanceprognose aus diesen
Fixtures. Bereits ein weiterer kleiner Kauf im letzten Fall wird durch das
gemeinsame Konto abgelehnt; ungenutztes Cash anderer Baskets hilft nicht.

## Abnahme und nächster Schritt

44 neue Fälle:22 Ökonomie,22 Kaufstress.187 Hostfälle und191 gepinnte
Python3.14.10-Trading-/Workerfälle mit135 Subtests bestanden. Unabhängiger
fachlicher Review ohne verbleibenden wirtschaftlichen/Accountingblocker.
Decimal-Kontext, signed Funding, Breakeven, Tiergrenzen/fehlende Deckung,
Liquidationsequality, sieben gemischte Budgets, mehrere korrelierte Positionen,
Kosten-/Cashbindung, First-fill-Referenz und aktuelle Vorabhalts geprüft.

Unveränderte alte Trading-/Workerpfade mitgeprüft; alter realer
Dreijahresreplay wurde diesmal nicht wiederholt, da keine alten Module
geändert sind. Keine Historien-/Holdoutauswertung, DB-/Runtime-/Broker-/
Cockpit-/Publicaktivierung. Exakte Regime-/Hebelwahl bleibt offen.
IP-063 bleibt für Ereignisledger/Teilfills/Funding-/Gapablauf in Arbeit.
IP-064 ergänzt ausdrücklich Futures-/Preisart gebundene Historienverträge und
erste vollständige BTC-/ETH-Dreijahresstreams. Fundingarchive und historische
Kosten-/Marginannahmen stehen vor längeren Nettoleistungsläufen in IP-055 aus.
[Datenvertrag](futures-marketdata.md).

Offizielle Modellgrundlagen:
[Markpreis/isolierte Margin](https://www.bitget.com/support/articles/360058821652),
[Classic-Positionsstufen](https://www.bitget.com/docs/catalog/classic-contract-position/classic-contract-position).
