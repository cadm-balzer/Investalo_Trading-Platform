# Nativer Stufenmargin-Abgleich

Weiterführung nach PR122: [native Basket-Ausstiege](bitget-demo-basket-exits.md)
nutzen dieselben originalen Vorzustände und vollständigen Quellen.
Das aktuelle neue Basketjournalformat ist `/4`; die folgenden `/3`-Angaben
beschreiben den ursprünglichen Marginbaustein.

Stand 24.11.2026. PR121/main `7f69226` verifiziert. Nutzer möchte mit der
operativen automatischen Demo-Anbindung fortfahren.

Die eigene `BasketNativeMarginSource` ersetzt den bisher allein injizierbaren
Marginnachweis durch feste signierte native GETs und konkrete Parser. Sie ist
ein privater Producer für den Basketdispatcher; weder eine Startfreigabe noch
ein installierter automatischer Worker.

## Ursprünglicher Zustand vor Versand

Vor dem POST werden die native USDT-Kontoliste und sämtliche Positionen gelesen
und gegen den vorhandenen eigenen Basketbestand abgeglichen. Nur bekannte
Single-/USDT-/Long-/isolierte-/One-way-/2×-Positionen ohne automatische
Marginzuführung oder offene Positionsmenge werden angenommen. Gemeldete
Positionsmargin und belegte isolierte Kontomargin müssen zusammenpassen.
Coupon, Grant, Crossmargin und gesperrte Mittel müssen bekannt null sein;
fehlende Felder werden nicht als null interpretiert.

Der Vorzustand enthält native Zeiten, Equity/UPL, isolierte Margin und
Menge/Einstand/Margin/Funding/Gebühren/realisierten Gewinn je Position,
sowie ursprünglichen Order-/Intent- und Quelldigest. Er wird gemeinsam
mit der bereits vorhandenen Once-only-Versandmarke geschrieben, fsync-
bestätigt und beim vollständigen Journalrestore wiederhergestellt.
Ein verlorenes ACK oder Neustart erzeugt keine zweite Order und ersetzt
den ursprünglichen Vorzustand nicht durch einen späteren Kontostand.

Das Basketjournal hat dafür die eigene Version `/3`. `/2` wird nicht
automatisch adoptiert oder verändert. Tatsächliche operative Basketjournale
sind noch nicht installiert; das abgeschlossene technische BTC-Journal
Revision8 bleibt in seiner bisherigen separaten Domäne.

## Bestätigte zusätzliche Margin

Nach einer terminalen Order werden tatsächliche Menge, gewichteter Fillkurs
und gemeldete Gebühr wie bisher geprüft. Der gesamte Positionsbestand muss
mit dem eigenen Bestand plus dieser Ausführung übereinstimmen. Zusätzlich
werden eine frische Kontoliste und Kontobuchungen im festen ursprünglichen
Zeitfenster abgefragt.

Bitget beschreibt `marginSize` als Positionsmargin und `isolatedMargin` als
belegte isolierte Kontomargin im
[Positionsabruf](https://www.bitget.com/docs/catalog/classic-contract-position/classic-contract-position)
und [Kontoabruf](https://www.bitget.com/docs/catalog/classic-contract-account/classic-contract-account).
Der Producer übernimmt nicht den gesamten Positionswert als Kaufdebit:
Er verwendet die Differenz zum gespeicherten Vorzustand, bestätigt diese
mit der belegten Kontomargin und prüft alle anderen Baskets unverändert.

Equity minus native UPL dient als abgeleiteter Kollateralwert für den
Gebührenabgleich, nicht als angeblich direkt gemeldeter freier Kontostand.
Die Veränderung muss zu den bekannten Buy-Buchungsgebühren und der
kumulativen Ordergebühr passen. Der native kumulative Transaktionskostenwert
der Position wird ebenfalls abgeglichen.

Nur One-way-Buy-Buchungen des eigenen Assets mit null Principalbetrag werden
in diesem engen Kaufabgleich angenommen. Die Buchungen haben laut
Dokumentation keine Order-ID; es wird deshalb keine erfunden. Die Zuordnung
erfolgt über den einzigen eigenen Kauf, vollständigen Mengen-/Bestandsabgleich,
festes Zeitfenster und übereinstimmende Gebühren/Kollateraländerung.

`onlyFunding=no` schließt laut Bitget auch Marginänderungen ein. Jede
nichtleere Seite mit Cursor wird weiterverfolgt, einschließlich kurzer
Seiten; nur eine leere terminale Seite bestätigt das Zeitfenster. IDs und
Cursor müssen monoton sein, Duplikate und zusätzliche Seiten werden
abgelehnt. Höchstens8 Seiten, höchstens30 Tage Fenster, frische Antworten;
das ist keine Abnahme einer älteren vollständigen Kontohistorie.

Funding, Transfers, manuelle/automatische Marginänderungen, fremde Aktivität,
abweichende Gebühren oder fehlende Quellen bleiben ausstehend. Sie werden
nicht als Kaufprincipal gebucht. Der bestätigte native Fill bleibt dabei
mit unbekannter Margin sichtbar. Der Endabgleich der aktuellen Credentials/
Actorautorität bleibt nach allen Reads verbindlich.

Der Vergleich mit tatsächlicher Fillmenge×VWAP/2 ist allein eine
Plausibilitätsprüfung gegen nicht erklärte Nachschüsse. Gebucht wird die
korroborierte native Margindifferenz, nicht dieses berechnete Ersatzdebit.
Bei nicht ausgeführter Stornierung müssen null Gebühr, unveränderter Bestand,
keine Buchungen und unverändertes Kollateral bekannt sein.

Die dokumentierte leere `totalFee` bedeutet, dass noch keine Fundinggebühr
angefallen ist. Nur dieses ausdrücklich dokumentierte Feld wird so
normalisiert. Leere Beträge/Gebühren/Grant/Kontomargin bleiben unbekannt.
Eine leere `feeByCoupon` ist kein separater Nullnachweis; der enge Abgleich
setzt bereits bekannte null Couponbestände und keine Couponbewegungen voraus.

## Prüfstand und nächste Integration

16 neue Fälle verwenden echtes Journal, tatsächlichen Vollrestore,
Trading-AEAD und signierte Pakete; native Antworten und Actor-/Consentports
sind synthetisch. Geprüft werden Erstkauf, Teilfill, null Stornierung,
Nachkaufdifferenz bei bestehendem und weiterem Basket, verlorenes ACK,
Widerruf, fehlende Felder, Cashdrift, Funding/Margin/Transferabweichungen,
vollständige Pagination und keine Wiederholung nach Restore.

331 verschiedene betroffene gepinnte Pythonfälle grün: Der breite Lauf
prüfte330 Fälle; allein die geänderte Other-Basket-Fixture widersprach
ihrem eigenen Wallet-Marginbetrag. Die korrekte Ablehnung wurde mit einer
konsistenten Fixture geprüft. Die finale77-Fall-Gruppe einschließlich
zusätzlicher versetzter Wallet-/Positionszeiten ist vollständig grün.
Dabei deckt das Bill-Zeitfenster beide nativen Quellenzeiten ab.
Finaler gepinnter Executorbuild und Import ohne Netzwerk/Quellmounts/
Schlüssel grün; verpackte Quellhashes entsprechen den geprüften Dateien,
Versand bleibt standardmäßig aus.
Keine neue Migration/Dependency, keine neue operative HTTP-Route,
keine tatsächliche Brokerorder oder Änderung laufender Dienste.
Lesender Abschlussaudit bestätigt sämtliche ursprünglichen privaten
Dateihashes und alle sieben laufenden Container-/Image-IDs unverändert;
technisches Originaljournal weiterhin Revision8.

Nächster Restumfang: native Zulassung/Höchstmenge/aktuelle Coins,
ursprüngliche dauerhafte Strategie-Start-/Pause-Freigabe, vollständiger
Worker mit Käufen/Nachkäufen/Ausstiegen und tatsächlich gebuchtem Funding.
Die neue Quelle wird bei dieser Installation explizit über `margin_source`
verdrahtet; der alte synthetische Callback ist keine operative Quelle.
Automatischer Demohandel ist weiterhin nicht gestartet.
