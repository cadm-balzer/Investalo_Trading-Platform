# Aktuelle Bitget-Vertragsregeln und XRP-Rundungsreferenz

IP-084 ergänzt einen isolierten, nur lesenden Classic-USDT-Futures-Vertrag.
PR52 ist gemerged: head8d71aeb ist Vorfahr von main5a89712; GH/Fetch geprüft.
Die bestehenden zehn Implementationshashes aus IP-083 bleiben identisch.
Das native Binance-Referenzergebnis wird nicht neu berechnet oder verändert.

## Gesicherte aktuelle Quelle

Ein unsigned GET am2026-11-13T12:50:52Z:
`https://api.bitget.com/api/v2/mix/market/contracts?productType=USDT-FUTURES`.
Die vollständigen685029 Antwortbytes liegen lokal; SHA256:
`c2f2d85ab6dcec2a3e26be6ad62d8b26f22acf35b96cb0eb32d442adcd87edd6`.
Die fünf unveränderten ausgewählten Vertragsobjekte und der Responseumschlag
sind [im Repository gesichert](research-protocols/futures-bitget-classic-contracts-20261113.json).
Es wurden keine privaten Kontodaten abgefragt.

| Coin | Mengenraster | Preisraster in USDT | Mindestmenge | Mindestnominal in USDT |
|---|---:|---:|---:|---:|
| BNB | 0,01 | 0,01 | 0,01 | 5 |
| BTC | 0,0001 | 0,1 | 0,0001 | 5 |
| ETH | 0,01 | 0,01 | 0,01 | 5 |
| SOL | 0,1 | 0,001 | 0,1 | 5 |
| XRP | 1 | 0,0001 | 1 | 5 |

Alle fünf haben Status `normal`. Der öffentliche Maker-/Takertarif ist
0,02%/0,06%; `openCostUpRatio=0.01`, `feeRateUpRatio=0.005`.
Das belegt weder den tatsächlichen individuellen Kontotarif noch
Liquidationskosten, historische Maintenance-Tiers oder die genaue
Zuordnung dieser Felder zur vollständigen Marginformel.
Das venue-seitige Hebelminimum1 verändert das bestätigte Strategieprofil2×–10×
nicht. Die Quelle stammt aus2026, die Researchpreise dagegen aus2022–2025
von Binance. Beide Zeit- und Venueachsen bleiben ausdrücklich getrennt.

Der Parser verwendet `sizeMultiplier` zusammen mit `volumePlace`;
der Preistick ist `priceEndStep ×10^−pricePlace`. Fehlende Felder,
inkonsistente Raster, doppelte/fehlende Coins, andere Wallet-/Produkttypen
und ungültige Zahlen werden abgelehnt. Markierte Öffnungssperren bleiben
sichtbar; die Offline-Mengenberechnung verlangt Status `normal`.
Limit- und Market-Maximalmengen bleiben getrennt.

## Statische Prüfung der vorhandenen Ablehnungen

Alle51 IP-083-Ablehnungszeilen wurden gegen das aktuelle Mengenraster geprüft.
Keine vorgeschlagene Menge liegt bereits exakt darauf. Das ist eine
aktuelle Gegenprüfung ausgewählter Modellkandidaten, kein Nachweis
historischer Orderablehnungen oder eine Aussage über alle530 tatsächlichen Käufe.

Die Prüfung reduziert ausschließlich die vorgeschlagene Menge auf das nächste
volle Rastervielfache. Bestehende Basis-/Mark-/Preisannahmen, verfügbares
isoliertes Kapital und die alte exakte Marginformel bleiben konstant;
es wird kein zusätzliches Geld verbucht.
Bei allen19 reinen XRP-Marginablehnungen reicht diese Mengenreduktion aus:
der alte Modell-Marginfehlbetrag wird zu einer Deckung von
**0,0037758872 bis1,1089281855 USDT**.
Damit ist ein gröberes Mengenraster ein konkreter Kandidat gegen die
diagnostizierten Rundungsreste. Ein pauschales Geld-Epsilon ist nicht belegt.

Die Probe wendet das Preisraster nicht an und berücksichtigt keine
neuen Fee-/Orderfreeze-/Tier-/Liquidationsregeln. Sie erzeugt keine Fills,
keine Zustandsänderung und keine zusätzliche Gewinnrechnung.
[Alle51 Einzelproben](research-protocols/futures-bitget-quantity-grid-probe-20261113.json)
enthalten Zeitpunkt, Sequenz, Coin, Zyklus, Stufe und ursprüngliche Gründe.
Das Journal wurde hierfür nicht erneut gefaltet; die vollständige,
hashgebundene IP-083-Evidence ist der Referenzanker.

## Markpreis und Geldpräzision

Der offizielle [Classic-Marginguide vom2026-04-02](https://www.bitget.com/asia/support/articles/12560603881482)
beschreibt für Long den Eröffnungsverlust als
`Menge ×max(0, Orderpreis −Markpreis) /Margincoin-Indexpreis`.
Der neue reine Rechner bildet nur diese Komponente ab.
Bei Markpreis über Orderpreis ergibt sie null.
Die bisherigen32 Treffer `Mark >Trade ×1,0005` sind damit weiterhin
deklarierte Forschungsguards, keine durch diese Quelle bestätigten
Bitget-Ablehnungen. Andere Preis- und Marginprüfungen können weiterhin gelten.

Der Guide beschreibt zusätzlich Leverage-, Gebühren- und Freeze-Komponenten
für die Classic-Orderprüfung. Seine getrennten UTA-Formeln werden nicht auf
den bestätigten Classic-Account übertragen. Das öffentliche Vertragsobjekt
belegt keine USDT-Buchungspräzision oder Rundungsrichtung für Margin,
Restoration, Fees und Funding. `volumePlace` und `pricePlace` sind dafür
kein Ersatz. Deshalb bleiben `money_quantum` und `money_rounding_mode`
im Receipt ausdrücklich unbekannt.

Weitere Primärquellen:

- [Classic-Vertragskonfiguration](https://www.bitget.com/docs/catalog/classic-contract-market/classic-contract-market):
  Feldsemantik, Mindestgrößen, Status und Ordermaxima.
- [Ältere offizielle Bitget-Dokumentation](https://bitgetlimited.github.io/apidoc/en/mix/):
  Rechenbeispiel `pricePlace=1`, `priceEndStep=5` ergibt Tick0,5.
- [Binance Exchange Information](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data):
  `quantityPrecision` und `pricePrecision` dürfen nicht als Step-/Ticksize
  verwendet werden. Binance-Instrumentregeln wurden in diesem Schritt
  nicht abgerufen oder als Bitget-Regeln übernommen.

## Abnahme und Wiederholung

16 unterschiedliche fokussierte Fälle/20 Subtests im bestehenden
Python3.14.10-Testcontainer bestanden: Rastergrenzen, Mindest-/Maximalmengen,
Preis-/Mengenpräzision, periodische Division bei kleinem Caller-Decimalcontext,
Long-Eröffnungsverlust, echte XRP-Referenzpräzision, harte Unterdeckung,
create-only Capture, Fehler ohne Erfolgsreceipt und begrenzter unsigned GET.
Der erste statische Export lehnte die größere Dezimalpräzision des
Audit-Marginwerts ab. Ein eigener begrenzter Auditcodec und der konkrete
XRP-Test beheben das, ohne den bestehenden Preiscodec zu ändern.
Fehlgeschlagene lokale Ordner bleiben ohne Erfolgsreceipt erhalten.

```bash
python3 infra/scripts/capture-futures-broker-rules.py NEW_CAPTURE_DIRECTORY
python3 infra/scripts/probe-futures-broker-grids.py CAPTURE_DIRECTORY NEW_PROBE_DIRECTORY
bash infra/scripts/check-paper-storage.sh -k FuturesBrokerCalibrationTests
```

Capture ist ein bewusster neuer Snapshot, ohne automatische Retries oder
Redirects. Probe liest nur lokale Dateien und verlangt die eingefrorenen
IP-083-Evidence-/Receipthashes sowie unveränderte zehn Referenzmodule.
Die Offline-Limitmengenfunktion rundet weder Nominalbudget noch Preisgrenze
auf; sie setzt einen ausdrücklich rastergerechten Limitpreis voraus und
beweist keine Marginzulassung.

Gesicherte Receipts:

- [Metadatenreceipt](research-protocols/futures-bitget-classic-contracts-receipt-20261113.json),
  SHA256 `61c50ac6bc85b86ee176f1c7d926153d899f16c4b4cbeec35437a1a1a37d6e5c`.
- [Probereceipt](research-protocols/futures-bitget-quantity-grid-probe-receipt-20261113.json),
  SHA256 `d95eb94d18a46e67f67fd6e0f31de59cfd6186905715028de4be5cba64a22ab1`.

Nächster Schritt IP-085: eigener eingefrorener Forschungsvariant mit
rastergerechten Mengen und ausdrücklich deklarierten Margin-/Kostenannahmen,
einschließlich Preisguard-Abgleich, bevor weitere Hebel verglichen werden.
Historische Brokerregeln und individuelle Kontotarife bleiben eigene
Validierungsvoraussetzungen. Keine Änderung an Kapitalstaffel oder
bestehenden wirtschaftlichen Policies; keine AI-/Live-/Holdout-/Public-/
DB-/Dependencyaktivierung.
