# Längere Crypto-Backtests

Nutzerpriorität2026-11-08: nach dem verifizierten IP-045-Merge zurück zu
Daten, Tradingkern, Backtests und anschließend Paper. Weitere Credential-
Betriebsaktivierung wird dafür zurückgestellt. Private Brokerkeys sind für
historische Marktpreise und den vorhandenen Offlineworker nicht erforderlich.

## Technischer Forschungsdurchlauf IP-046

Der öffentliche Bitget-V3-Importer kann bereits mehrere Jahre rückwärts
paginieren. Die dokumentierten90 Tage begrenzen eine einzelne Anfrage, nicht
die Gesamthistorie. Verfügbarkeit wird mit tatsächlicher lückenloser Abdeckung
geprüft; fehlende Daten werden weder interpoliert noch als vollständig bezeichnet.
Vier Jahre H4 passen mit8.766 Kerzen in die bestehende10.000-Kerzen-Grenze.

Die folgende konkrete Aufteilung wurde vor dem ersten neuen Leistungsdurchlauf
im [maschinenlesbaren Protokoll](research-protocols/crypto-h4-20261108.json)
mit Daten-/Contentdigests, Provenienz und vollständiger Kernspezifikation
festgehalten. Sie ist ein technisches Forschungsprotokoll dieses Checkpoints,
keine Änderung der Strategie und keine als Q26 ausgegebene Fensterquote:

| Zweck | UTC-Fenster, Ende exklusiv | H4-Kerzen je Asset |
|---|---|---|
| Abruf/Provenienz | 2022-08-01 bis2026-08-01 | 8.766 |
| Forschung im Cockpit | 2022-08-01 bis2025-08-01 | 6.576 |
| Reservierter Holdout | 2025-08-01 bis2026-08-01 | 2.190 |

BTC/USDT und ETH/USDT verwenden dieselben Grenzen. Der bereits getestete
BTC-Demosnapshot2026-08-09 bis2026-11-07 liegt außerhalb dieses Protokolls.
Der zusätzliche Verfügbarkeitsabruf2023-11-08 bis2026-11-08 wird nicht als
unberührter Holdout ausgegeben und nicht als vollständiges Forschungsdataset
neben dem reservierten Fenster importiert.

Nur die ersten drei Jahre werden als `purpose=research` importiert und
ausgeführt. Der letzte Jahresabschnitt erhält ausschließlich `purpose=holdout`.
Bestehende API-/RLS-/Jobclaim-/Workergrenzen sperren seine gewöhnliche Auflistung,
Jobannahme und Berechnung. Der vollständige Vierjahressnapshot wird ebenfalls
nicht als auswertbares Dataset importiert. Reservierung beweist noch keinen
wirtschaftlichen Erfolg; Holdoutleistung bleibt ungeprüft.

Die neue `window`-Funktion verlangt exakte UTC-H4-Abdeckung ihres expliziten
Fensters. Sie übernimmt Preise, Quelle, Abrufzeit und Instrumentmetadaten
unverändert, erstellt einen eigenen Digest und überschreibt keine Dateien.
Ein vollständig verfügbares Teilfenster behauptet keine Vollständigkeit eines
größeren, nur teilweise verfügbaren Ausgangsfensters.

```bash
PYTHONPATH=packages/marketdata/src:packages/trading/src \
python3 -m investalo_marketdata window full.json \
  --start 2022-08-01T00:00:00Z --end 2025-08-01T00:00:00Z \
  --output research.json

python3 infra/scripts/stage-research-snapshot.py \
  --file research.json --name btc-research-three-year.json \
  --purpose research --import-local
```

Holdoutstaging erfordert ausdrücklich `--purpose holdout`. Es importiert mit
der vorhandenen administrativen Rolle; es öffnet keine neue Runtimeberechtigung.
Keine SQL-Migration, Brokercredentials oder Strategieparameteränderung.

## Bedienung im Cockpit

Unter `/backtests` zuerst BTC/USDT oder ETH/USDT wählen, dann den echten
Bitget-Snapshot mit6.576 Kerzen (2022-08-01–2025-08-01) auswählen. Beide
Dreijahresläufe sind bereits gespeichert; die Ergebnisansicht zeigt
Netto-PnL, Drawdown, Profitfaktor, geschlossene Baskets und Equitykurve.
Der ältere90-Tage-BTC-Snapshot bleibt als separater Funktionsnachweis bestehen.

## Aussagegrenzen der ersten Ergebnisse

Der vorhandene deterministische Kern verwendet fünf reguläre Einstiege,
unangetastete manuelle Reserve, Kostenmodell und unabhängige Risikogrenzen.
Jeder Assetlauf startet mit eigenen10.000 USDT, wärmt Indikatoren innerhalb
seines Eingabefensters auf und schließt Positionen am Datenende nicht künstlich.
BTC- und ETH-Ergebnisse sind getrennte Simulationen; ihre PnLs sind kein
gemeinsames Portfolio. Netto-PnL enthält die markierte Bewertung offener
Bestände, Profitfaktor und Basketanzahl beschreiben abgeschlossene Baskets.

Gefrorene Jobs binden Daten-, Konfigurations- und Kostendigest. Ein erneuter
Lauf derselben Eingaben muss dieselben wirtschaftlichen Ergebnisse liefern.
Angezeigte Kurven können auf2.000 Punkte ausgedünnt werden; Kennzahlen werden
aus der vollständigen Simulation berechnet.

Kosten und Instrumentregeln sind weiterhin ausdrücklich Modellannahmen.
Separates Trainings-/Validierungsprotokoll, eingefrorene Auswahl, Kosten-
kalibrierung und die später genehmigte unabhängige Holdoutauswertung bleiben
weitere Arbeit. Dieser Schritt behauptet weder Walk-forward mit übernommenen
Positionen noch positiv validierte Strategie oder Echtgeldreife.
Q26-Maßstab bleibt: mindestens drei Jahre Crypto, positiver Netto-Holdout,
PF≥1,2 und30 geschlossene Baskets je Crypto-Asset.

Danach folgt technische Paperausführung mit denselben Strategie-/Risikoregeln,
Journal und nachvollziehbaren Fills. Bitget-Echtgeld und MT5-Demo benötigen
weiterhin ihre jeweiligen Integrations- und Freigabegrenzen.


## Zwischenabnahme2026-11-08

| Forschung, je eigenes10.000-USDT-Konto | Netto-PnL (USDT) | Max. Drawdown | Geschlossene Baskets |
|---|---:|---:|---:|
| BTC/USDT | +132,63 | 0,3339% | 24 |
| ETH/USDT | +96,09 | 0,3814% | 32 |

Diese Zahlen gelten für das eingefrorene Forschungsfenster und Kostenmodell.
Profitfaktoren21,3950 bzw.8,2361 betreffen nur die geschlossenen Baskets;
kleine Exposition und geringe Stichprobe begrenzen ihre Aussagekraft.
Es wurde kein Holdoutresultat berechnet und keine Auswahl anhand davon getroffen.

- 35 Marktdatentests, einschließlich15 neuer Fensterfälle, bestanden; gepinnter
  Markt-/Tradinglauf66 Tests mit33 Subtests grün.
- Fünf neue ETH-Clientmetadaten-Fixturetests bestanden; unabhängiger Review
  ohne Blocker. Keine physische Browser-/Hydrationsabnahme behauptet.
- 572 API-/Workerfälle gegen die Fixture-DB bestanden. Ein anfänglich falsch
  gegen normal007 gestarteter Lauf scheiterte an fehlenden008-Funktionen;
  anschließend mit Fixture-DB-Override korrigiert, ohne Migration.
- BTC und ETH jeweils48 tatsächliche Entwicklungs-HTTPS/MFA/BFF/Worker-
  Prüfpunkte bestanden: reale6576-Kerzenjobs, gespeicherte Nettokennzahlen,
  Equitykurven und unveränderte Datasetdigests.
- `python3 tests/infra/check_long_research.py` bestätigt beide repräsentativen
  gespeicherten Workerresultate durch erneute deterministische Simulation:
  Daten-/Config-/Kostenhash, PnL, Drawdown, PF und Basketzahl exakt gleich.
  Read-only-DB-Audit: vier importierte Fenster, kein Vollquellenimport,
  null Jobs für die zwei reservierten Holdouts. Keine Holdoutdatei simuliert.
- NormalDB001–007 und Fixture001–009 mit unveränderten Prüfsummen; sechs
  bestehende Dienste unverändert, fünf vorhandene Healthchecks gesund,
  Cockpit/Auth mit regulärem TLS HTTP200. Nur das Checkimage wurde gebaut;
  keine öffentliche Containerneuerstellung oder Flagaktivierung.

Die540 Cockpittests und die übrigen Credential-/Integrationsprüfungen aus
IP-045 wurden nicht wiederholt; Frontend-/Credentialcode ist unverändert.
Nächste Umsetzung ist IP-047:
Paperzustand, simulierte Fills, Risikogates und Journal mit bestehendem Kern.

Quelle erneut geprüft2026-11-08:
[Bitget V3 History-Candles](https://www.bitget.com/docs/catalog/market/market-data#get-klinecandlestick-history).
