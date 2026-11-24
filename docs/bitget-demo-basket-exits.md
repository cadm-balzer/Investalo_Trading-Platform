# Native H1-Basket-Ausstiege

Weiterführung nach PR123: [tatsächliche Fundingbuchungen](bitget-demo-basket-funding.md)
ergänzen die eigene read-only Quelle und die tatsächliche Wallet-/Marginzuordnung
im aktuellen neuen Basketjournalformat `/5`. Frühere `/4`-Angaben unten
beschreiben den Ausstiegsbaustein bei dessen ursprünglicher Implementierung.

Stand 2026-11-24, nach verifiziertem PR122/main`eada41c`.

Die private Anbindung kann eigene Strategieausstiege als
Reduce-only-Marketorders vorbereiten und tatsächliche Bitget-Fills abrechnen.
Standardmäßig deaktiviert; operativer Worker und Dashboard-Startfreigabe
bleiben nächste Schritte. Das technische BTC-Testjournal bleibt getrennt.

## Eigene Position und Freigabe

Der gemeinsame Basketzustand hält höchstens eine offene Kauf-/Verkaufsorder.
Der Ausstieg verwendet die gesamte bestätigte Restmenge und den ursprünglichen
Zyklus. Er benötigt vollständige Kursbewertung von höchstens fünf Sekunden
und einen Strategiegrund: Schutz-/Netto-Break-even-Stopp, −55%-Notausstieg oder
wirtschaftliche Integritätsprüfung. Liquidation benötigt eine separate Abrechnung.
RSI-Kaufzulassung und freies Kaufbudget sind keine Voraussetzung für Verkäufe.
Restmenge, Margin, Zyklus und Stoppevidenz werden vor der Versandmarke erneut
geprüft; Vorbereitung maximal30s. Native Raster-/Mengenlimits bleiben verbindlich;
eine größere Position benötigt später eigene geprüfte Orderaufteilung.

`BasketExitIntent` bindet Account, Journal, Kommando, Raster und Zyklus.
Separater Client-Präfix `ivx` und Zweck `bitget-demo-h1-basket-exit/1`;
Market-POST mit `side=sell`, `reduceOnly=YES`, isolierter USDT-M-Margin.
ACK bestätigt keinen Fill. Fehlende ACK-Order-ID wird über den originalen
Client-Identifier aufgeklärt. Siehe
[offizieller Bitget-Ordervertrag](https://www.bitget.com/docs/catalog/classic-contract-trade/classic-contract-trade).

## Tatsächliche Abrechnung

Originales Wallet-/Gesamtpositionsabbild wird vor POST fsync-bestätigt
gespeichert. Native Margin/Funding/Gebühren/realisierter Gewinn und
Kontokapital ohne UPL müssen mit dem eigenen Ledger übereinstimmen.
Keine Übernahme einer unverbuchten Einzahlung oder Marginänderung.

Danach: originale Orderdetails, vollständige Produktpositionen, Wallet und
alle Bills des ursprünglichen begrenzten Fensters. Nur leere Endseite beweist
Abrufabschluss; maximal8 Seiten/30Tage/110ms GET-Abstand, Quellen-/Kohorten5s.
Sell-Bills, signierte Ordergebühr, PnL, Kontoänderung ohne UPL, freigegebene
Margin und Restmenge müssen übereinstimmen. Andere Baskets bleiben unverändert.
Teilpositionen benötigen auch kumulative Gebühren-/Funding-/PnL-Abgleiche.
Bei vollständigem Abschluss dürfen Positionszähler verschwinden: Bills und
vollständiger Konto-/Margin-/Nullpositionsabgleich belegen die Abrechnung.
Berechneter PnL oder proportionale Margin allein bestätigen nichts.

Bitget dokumentiert Sell-Bills und separate Betrags-/Gebührenfelder im
[Account-Vertrag](https://www.bitget.com/docs/catalog/classic-contract-account/classic-contract-account).
Bills haben keine dokumentierte Order-ID; Zuordnung erfolgt nur über den
vollständigen ökonomischen Abgleich, ohne erfundene Identitätsfelder.

## Teilfills und Wiederherstellung

Laufende Teilfills bleiben ausstehend. Terminale Teilfills buchen einmal die
tatsächliche Menge, Gebühren, Margin und PnL; der Rest bleibt im selben Basket.
Eine spätere neue Order benötigt neue Vorbereitung und eigene Freigabe.
Ungefüllter Abbruch benötigt bestätigte Nullbeträge. Unknowns, Cashback,
Funding während Abrechnung, Transfers und fremde Aktivität bleiben ausstehend.
Auch Verlustausstiege werden tatsächlich gebucht. Nur vollständiger
bestätigter Abschluss erhöht den Abschlusszähler und setzt RSI-Bestätigung
für den neuen Zyklus zurück.

Journalformat `/4`, keine automatische Übernahme älterer `/2`-/`/3`-Journale.
Vollrestore spielt Kauf, Ausstieg, native Vorzustände und kumulative
Beobachtungen erneut ab. Nach markiertem Versuch bleibt Wiederherstellung
GET-only; Verwerfen oder Wiederholen eines versuchten POST ist ausgeschlossen.

20 neue/351 betroffene gepinnte Pythonfälle grün: reale Dateien/Restore/
AEAD/HMAC/finanzielle Reducer, synthetische Actor-/Brokerantworten.
Finaler Executorbuild sowie Paketimport und sechs Quellhashes ohne
Netzwerk, Quellmounts oder Zugangsdaten bestätigt; Versand standardmäßig aus.
Lesender Audit: ursprüngliche private Hashes und sieben laufende Dienste/
Image-IDs unverändert, technisches Journal8. Noch zu installieren: ursprünglicher dauerhafter
Start-/Pause-Consumer, native Zulassung und H1-Worker samt Funding.
Echtgeld bleibt deaktiviert.
