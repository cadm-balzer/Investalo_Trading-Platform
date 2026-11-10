# Öffentlicher Vorcheck der vorgeschlagenen Coins

Stand2026-11-10, IP-059. Ausgangscheckpoint IP-058 (`4f56024`) ist in
Main`7ec9b41` verifiziert. Die Auswahl zwischen fünf Coins
(BTC/ETH/SOL/BNB/XRP) und drei Coins (BTC/ETH/SOL) sowie feste
Slotwiederbelegung sind dem Nutzer erneut erläutert; Antworten stehen aus.
Dieser Vorcheck wählt kein Handelsprofil und berechnet keine Performance.

Öffentliche Bitget-V3-GETs ohne Konto/Keys bestätigen alle fünf vorgeschlagenen
USDT-Spotpaare als `online`. Für jeden Coin sind die beiden geschlossenen
H4-Kerzen2022-08-01 um00:00/04:00 UTC tatsächlich abrufbar und mit dem
vorhandenen bounded Decimal-/OHLC-Parser geprüft. Zehn Kerzen beweisen keine
lückenlose Dreijahreshistorie. Kein Holdoutabruf, keine Simulation oder
Änderung von Whitelist/Runtime/DB/Strategie.

## Aktuelle Instrumentdaten

| Spotpaar | Mengenraster | Quoteraster | Mindestquote USDT | Mindestmenge |
|---|---:|---:|---:|---:|
| BTCUSDT | 0,000001 | 0,00000001 | 1 | 0 |
| ETHUSDT | 0,0001 | 0,000001 | 1 | 0,0005 |
| SOLUSDT | 0,0001 | 0,000001 | 1 | 0 |
| BNBUSDT | 0,0001 | 0,000001 | 1 | 0 |
| XRPUSDT | 0,0001 | 0,00000001 | 1 | 0 |

Diese Werte sind heutige Metadaten, kein Nachweis historischer Handelsregeln.
Sie werden nicht still in die gefrorenen alten Backtests übernommen.
Insbesondere ETH hat eine positive Mindestmenge; der bisherige
`InstrumentRules`-Vertrag bildet nur Mengen-/Quoteraster und Mindestquote ab.
Ein späterer modellierter Researchdispatch muss Mindestmengen ausdrücklich
berücksichtigen oder seine Modellgrenze benennen. Alte Konfigurationsdigests
nicht durch ein zusätzliches Defaultfeld in v1 verändern.

## Belege und nächster Schritt

[Öffentlicher Messrecord](research-protocols/portfolio-candidates-preflight-20261110.json)
speichert abgefragte Metadatenfelder, Providerzeiten, Responsehashes und die
geprüften Kerzenzeitpunkte. `complete_three_year_history_verified=false`,
`performance_evaluated=false`, `holdout_evaluated=false`.
JSON-Roundtrip, fünf Providerantworten/Identitäten/Precisionfelder und zehn
UTC-/OHLC-Kerzen geprüft. Keine neuen Abhängigkeiten oder Tests für die
reine Dokumentationsänderung.

Nach Coinauswahl: exaktes gemeinsames Forschungsfenster vollständig abrufen,
Lücken/Abdeckung/Provenienz validieren, eigene erweiterte Daten-/Metadaten-
verträge vorbereiten und Policy/Kosten/Zyklusregeln vor Leistungslauf einfrieren.
Bestehende v1-Snapshots/Importer und Worker akzeptieren weiterhin nur BTC/ETH.
Gleiches Budget-/Stressprofil ist bereits bestätigt; die zwei offenen
Entscheidungen werden nicht aus einer bloßen Mergemeldung abgeleitet.

Offizielle Referenz:
[Bitget Instruments und History](https://www.bitget.com/docs/catalog/market/market-data).
V3 öffentliche Marktmetadaten ändern keine Classic-V2-Privatadapterbindung.
