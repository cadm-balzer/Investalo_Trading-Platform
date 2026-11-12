# Separater Binance-Futuresvergleich: Dreijahresdaten

Q38 bestätigt am2026-11-11 den zusätzlichen kostenlosen Forschungsvergleich
mit **eigenen Binance-Kursen und Fundingraten**. Bitget bleibt Handelsziel.
IP-069`57b2858` ist in Main`f37be4b` verifiziert. IP-070 liefert die Datenbasis;
wirtschaftliches Protokoll und Nettoleistungslauf folgen weiterhin IP-069.

## Tatsächlicher Import

Gefrorenes Quellenfenster **2022-08-01T00:00Z bis2025-08-01T00:00Z, Ende exklusiv**.
Der reservierte Holdout2025-08-01..2026-08-01 wurde nicht angefragt.

| Native USDT-M-Perpetual-Reihe | BTCUSDT | ETHUSDT |
| --- | ---: | ---: |
| H4-Handelspreiskerzen | 6576 | 6576 |
| H4-Markpreiskerzen | 6576 | 6576 |
| H4-Indexpreiskerzen | 6576 | 6576 |
| Tatsächliche signed Fundingabrechnungen | 3288 | 3288 |
| Fehlende8h-Buckets, deklarierte Kalenderdiagnose | 0 | 0 |
| Fundingabrechnungen ohne nativen Settlement-Markpreis | 1369 | 1369 |

Alle sechs H4-Reihen sind vollständig, lückenlos und auf derselben UTC-Achse.
39.456 Kerzen und6576 Fundingereignisse über52 öffentliche GETs: je Preisreihe
sieben Pages, je Fundingreihe vier nichtleere und eine leere Abschlussseite.
Zwei vorausgehende kleine Quellenproben zählen nicht zu diesen52 GETs.

Originale Fundingtimestamps bleiben unverändert; maximaler beobachteter
Versatz zur vollen8h-Grenze **29 Millisekunden**. Erste Abrechnung bei beiden
Symbolen2022-08-01T00:00:00.010Z, letzte2025-07-31T16:00Z.
Keine Rundung, kein Ersetzen fehlender Raten durch Null; eine tatsächlich
gemeldete Nullrate ist ein vorhandener Datenpunkt.
Die8h-Bucketdiagnose ist eine ausdrücklich deklarierte Prüfannahme.
Passende3288 Ereignisse beweisen keine unabhängige historische Kalenderattestation.

## Herkunft und Artefakte

Offizielle [Binance-Marktdokumentation](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data):
`/fapi/v1/klines`, `/markPriceKlines`, `/indexPriceKlines`, `/fundingRate`.
Nur `https://fapi.binance.com`; Index verwendet `pair`, andere `symbol`.
Funding liefert aufsteigend mit inklusivem Start/Ende, maximal1000 Zeilen.

[Quellenprotokoll](research-protocols/binance-futures-history-20261111.json),
SHA256`158efdde024bf3856cf23fc6b6c324727c0b66cb2e23c2c00c052b257ee35bbf`,
steht vor dem Import fest. [Receipt](research-protocols/binance-futures-history-receipt-20261111.json)
enthält acht Dateihashes/Datasetdigests und52 Hashes der kanonisch decodierten
nativen Antworten. Vollständige API-Antworten sind nicht separat archiviert;
Snapshots erhalten validierte OHLC-/Fundingfelder, keine Volumen-/Zählungsdaten.
Alle acht gespeicherten Artefakte nach Import erneut geladen und ihre Hashes,
Achsen und Diagnosen geprüft.

Rohdaten bleiben unter dem ignorierten
`infra/local/binance-futures-research-data/20261111-native-network/`.
Ein erster sandboxbedingt fehlgeschlagener DNS-Lauf hinterließ `20261111-native/`
ohne Receipt. Autorisierter neuer Netzwerkimport, kein automatischer Retry.

```bash
python3 infra/scripts/import-binance-futures-history.py NEW_OUTPUT_DIRECTORY
```

## Datenvertrag und Grenzen

Eigenes immutable `binance-usdt-futures-research/1`, eigene Venue/Markt/
Preisart/Quellen-/Fensteridentität und Kerzensymbole
`BINANCE:BTCUSDT:USDT-M:trade` beziehungsweise mark/index.
Bestehende Bitget-/Spotformate akzeptieren diese Artefakte nicht.
Funding erhält Originalzeit, signed Decimalrate, optionalen nativen Markpreis
und optionalen nativen `Regular`/`Special`-Typ. Fehlender Markpreis bleibt
`None`; nativer inklusiver Kerzenschluss wird exakt zu exklusivem H4-Schluss.

Unsigned GET ohne Keys, Cookies, Redirects oder Retry; Timeout15s,512KiB,
1000 Zeilen/Page,21 Pages/Stream,10000 Zeilen/H4-Intervalle, mindestens0,1s
Pageabstand. Exakte kanonische Query prüft Host/Path/Parametermenge/Fenster.
Private/duplizierte/zusätzliche Parameter scheitern vor Netzwerkzugriff.
Ungültige, überlappende, unsortierte, fremde oder außerhalb des Fensters liegende
Antworten scheitern. Ein H4-Loch verhindert das Artefakt; Fundinglücken bleiben
sichtbar. Kurze Fundingseiten führen bis zur leeren Endseite weiter;
Kapazitätserschöpfung ist kein erfolgreicher Abschluss.
CLI prüft Protokollhash vor Verzeichnis-/Netzwerkzugriff; bestehende Ziele
bleiben erhalten, Fehler liefern keine abschließende Erfolgsreceipt.

**Noch keine Futuresrendite berechnet.** Bei1369 älteren Abrechnungen je Symbol
fehlt der native Settlement-Markpreis, die Fundingrate ist vorhanden.
Für die Nominalbasis muss das wirtschaftliche Protokoll einen benannten
Markpreisbezug oder konservative Kostenhülle festlegen; H4-Kerzen beweisen
keinen exakten Millisekundenpreis. Historische Gebühren, Precision/Maintenance/
Liquidation, Fill-/Gap-/Puffertiming und Budgetprofil benötigen eigene
Forschungsannahmen beziehungsweise Quellen. Binancefunding nicht in angeblich
native Bitgetperformance mischen.

Das lange Replayjournal muss vor dem Leistungslauf vollständige Ereignisse
ohne ID-Verwerfen/Restarts zur Limitumgehung beherrschen. IP-071 belegt dies
für das alte Profil; das neue Q41–Q43-Kapital-/Signalprofil braucht einen
eigenen vollständigen Restore. RSI/Nachkauf/manuelle Reserve bleiben erhalten;
6%/8% sind im neuen Profil Warnungen und−50% ist eine Diagnose.
IP-075 ergänzt die [native gemeinsame H1-Kohorte](futures-hourly-history.md).
Wenige Unterschiede zur älteren H4-Quelle sind ausdrücklich dokumentiert;
beide neuen Schutzvarianten müssen dieselbe H1-Quelle aggregieren.
Receipt meldet `net_backtest_ready=false`, `performance_evaluated=false`,
`execution_enabled=false`.

## Prüfung

25 neue Hostfälle zunächst grün. Gepinnte Marktdata-Gesamtauswahl127 Fälle/
229 Subtests grün. Final28 Binancefälle/44 Subtests nach zusätzlichen
Transportfenster-/Payload-/Kalenderprüfungen grün; Gesamtfenster und einzelne
Pagegrenze dabei getrennt. **130 unterschiedliche gepinnte Marktdatafälle**
über beide erfolgreichen Auswahlen, keine Addition überlappender Läufe.
Eigenprüfung von Quellenbindung, Grenzen, Fundingoffsets, Null/Missing,
Gaps, Fehler-/Replay-/Ressourcenverhalten und tatsächlichen Artefakten.
Nur zwei readonly Testmounts; keine Dependencies, Migrationen, privaten Calls,
Runtime-/Paper-/Publicaktivierung. Unveränderte breite Suiten nicht wiederholt.
