# Gemeinsamer BTC-/ETH-Portfolio-Referenzlauf

IP-056,2026-11-09. Plancheckpoint9455bfe in Mainef18d74 verifiziert.
Dieser Offlinecheckpoint bereitet IP-055 vor: ein10.000-USDT-Konto,
unveränderte500-USDT-Kaufbudgets plus5 Kostenreserve je BTC-/ETH-Basket,
Spot ohne Hebel und dieselben RSI-/Schutzregeln. Die größere3–5-Coin-
Allokation aus Q33 ist damit noch nicht implementiert.

## Deterministischer Ablauf

`PortfolioSimulator` verlangt vollständige H4-Historien aller konfigurierten
Assets mit identischen Anfangs-/Endgrenzen. Fehlende Assets, Doppelkerzen,
Gaps und mehr als10.000 Kerzen je Asset werden abgewiesen. Eingaben werden
nach UTC-Zeit und eingefrorener Config-Symbolpriorität normalisiert;
Tenant/Konto bleiben an den gemeinsamen Zustand gebunden.

`CryptoEngine.on_quotes` validiert vollständige gleichzeitige Quotes und
installiert alle Kurse vor der gemeinsamen Risikoprüfung. Gegenläufige Preise
erzeugen keinen falschen Kontostopp aus halb aktualisierter Equity.
Diese Semantik behauptet keine Gleichzeitigkeit asynchroner Livekurse.

Die historische OHLC-Annahme lautet gemeinsames `Open → Low → High → Close`,
mit synthetischen Zwischenzeiten nach einer beziehungsweise zwei Stunden.
Gemeinsame Tiefs modellieren korrelierten Stress, keine rekonstruierte
Intrabarreihenfolge. Geschlossene H4-RSI-Signale kaufen frühestens am nächsten
bekannten Open. Endsignale werden storniert, Restpositionen bleiben bewertet
offen. Keine erfundenen manuellen Fills.

Mitternacht prüft zuerst den alten Tagesverlust gegen gemeinsame Schluss-Bids.
Danach wird die neue Basis vor Fills einmal übernommen; ein Open-Gap zur
gleichen Uhrzeit ersetzt sie nicht. Halts bleiben gelatcht. Diese historische
Bid-/Spread-Policy verändert weder Q32-Paperbewertung noch den bisherigen
Einzelquote-/Paper-/Researchpfad.

Ausführungs-/Benchmarkpolicy, Symbolpriorität, Config-/Kostendigest und
Datengrenze sind in `portfolio-reference/1` und eigenem Policydigest gebunden.
[Protokoll vor erstem Leistungsdurchlauf](research-protocols/crypto-portfolio-reference-20261109.json).

## Kapital und Benchmark

Die Kurve zeigt Cash, Anschaffungskosten noch gehaltener Mengen, Bid-Marktwert,
offene Kaufprincipalreservierungen, aktive Baskets und manuelle Principalreserve
aktiver Baskets. Letztere ist keine Gesamtliquiditätszusage aller Slots.
Teilverkauf verringert den gehaltenen Einstand, eröffnet aber kein neues
Kaufbudget desselben Zyklus. Zeitgewichteter Einstand verwendet die expliziten
synthetischen Phasenzeiten statt eines Mittels über doppelte Grenzzeitpunkte.

Buy-and-hold kauft am ersten Open maximal500 USDT je Asset auf demselben Konto.
Gebühren, Ask-Spread, Slippage, Quote-/Mengenrundung und Mindestmengen verwenden
dasselbe Modell; übriges Kapital bleibt Cash. Beide Endwerte markieren Bestände
zum Bid ohne erfundene Endliquidation/Exitkosten. **Die passive Referenz hat keine
Strategierisikostopps und ist nicht auf gleiche tatsächliche Exposition begrenzt.**
Ihr Mehrertrag belegt keine zulässige Strategievariante.

## Reale Dreijahresforschung

Nur die zuvor eingefrorenen6576-Kerzen-Forschungsfenster je Coin
2022-08-01–2025-08-01 wurden gemeinsam berechnet:

| Kennzahl | Gemeinsame RSI-Basketreferenz | Passive Referenz |
|---|---:|---:|
| Anfangskapital | 10.000 USDT | 10.000 USDT |
| Maximale geplante Kaufprincipalzuordnung | 1.000 USDT | 1.000 USDT |
| Netto-PnL einschließlich offener Bewertung | +228,72 USDT | +2.577,90 USDT |
| Kontorendite über drei Jahre, nicht jährlich | +2,2872% | +25,7790% |
| Maximaler Kontoequitydrawdown | 0,6144% | 12,1145% |
| Geschlossene Baskets | 56 (BTC24 / ETH32) | Keine Verkäufe |
| Zeitgewichtetes gehaltenes Kaufprincipal | 72,56 USDT /0,7256% Startkapital | Nicht expositionsgleich |
| Maximal gehaltenes Kaufprincipal | 512,10 USDT | Rund1.000 USDT |

Der geringe durchschnittliche Kapitaleinsatz erklärt einen Teil der kleinen
Kontorendite. Peakdrawdown ist nicht Verlust zum Startkapital; die8%-Grenze
verwendet ausdrücklich die zweite Basis. Im ausgewerteten Fenster lagen die
passiven Startkapital-/Tagesverluste bei maximal3,4806%/3,1921%, unter8%/6%;
die12,1145% vom zwischenzeitlichen
Hoch beweisen keine Verletzung dieser Kontolimits. Die passive Referenz ersetzt keine
validierte, mit Risikostopps ausgeführte Strategie. Kostenkalibrierung und
unabhängiger Holdout bleiben offen. Es wurde kein größeres Budgetprofil anhand
dieser Leistung ausgewählt.
Die aggregierte Basketzahl ersetzt nicht das Q26-Ziel von30 je Asset im
unabhängigen Holdout; alle angegebenen Zahlen stammen ausschließlich aus Forschung.
[Exakte Ergebnisse/Digests](research-protocols/crypto-portfolio-reference-result-20261109.json).

## Abnahme und Bedienung

```sh
PYTHONPATH=packages/trading/src python3 -m unittest discover -s tests/trading -q
python3 -m unittest discover -s tests/infra -p test_portfolio_research.py -q
python3 infra/scripts/check-portfolio-research.py
```

Der Checker braucht den Hostowner für die zwei geschützten vorhandenen
Researchdateien. Er prüft Protokoll, Content-/Datendigest, Provenienzbindung,
exakte Grenzen und gespeicherte Ergebniskonstanz. Er öffnet keine Holdoutdatei,
DB- oder Brokerverbindung und überschreibt keinen Befund.

61 Trading-/Paperfälle, darunter16 neue Portfolio-/Batchfälle, sowie vier
Input-/Protokollguards auf dem Host bestanden.65 gezielte gepinnte Fälle
(61 Trading/Paper plus vier Worker-Compute) mit26 Subtests bestanden;
vollständiger tatsächlicher Ergebnisreplay und Abschlussreview ohne Blocker.
Syntax/JSON/Dokumentverweise/Diff geprüft. Keine Migration, neue Abhängigkeit,
Worker-/API-/Cockpitaktivierung oder öffentliche Containerneuerstellung.
IP-055 setzt mit zusätzlichen Coins, exakten Budget-/Reservierungsregeln und
validierter Priorität fort; KI bleibt eine spätere Shadow-/Promotionsstufe.
