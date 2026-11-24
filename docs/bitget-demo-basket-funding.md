# Tatsächliche Demo-Fundingbuchungen

Weiterführung nach PR124: [gemeinsamer Order-/Fundingabschluss](bitget-demo-order-funding-settlement.md)
ergänzt belegte parallele Vorgänge im neuen Basketjournalformat `/6`.
Die folgenden `/5`-Angaben dokumentieren den ursprünglichen Fundingbaustein.

Stand2026-11-24, PR123/main`8d78526` verifiziert.

Die private Basketanbindung liest gebuchte `contract_settle_fee`-Bills und
verbindet sie atomar mit Wallet, vollständigen Produktpositionen und dem
eigenen Journal. Es gibt keine aus einer Rate erfundene Zahlung.
Der Dispatcher bleibt standardmäßig aus; operative Start-/Pause-Freigabe
und Workerinstallation sind noch offen.

## Kapital und Kosten

Native Billbeträge bestimmen den Nettozufluss; der bestätigte Unterschied
der isolierten Guthaben bestimmt die Kapitalzuordnung. Der Rest verändert
freies Kontoguthaben. Mengen, Kaufstufen, fest zugesagtes Stufenkapital und
Hebel bleiben unverändert. Zahlungen und Gutschriften sowie deren Kombination
werden unterstützt. Bruttozahlungen bleiben getrennt vom Nettofunding sichtbar.

`BrokerFundingPayment` verwendet tatsächlichen Betrag und native Zeit statt
Markpreis/Rate. Sein native-only `BrokerFundingBasket` erfasst zusätzlich die
noch nicht durch Wallet-Gutschriften gedeckten Fundingkosten aus freiem Cash.
Diese tatsächlichen Ausgaben zählen zur eigenen Kostenreserve; sie erhalten
keine zusätzliche fiktive Marginrestaurierungsreserve. Historische
LedgerBasket-Layouts und simulierte FundingSettlement-Berechnungen bleiben erhalten.

## Vollständiger nativer Abgleich

Der eigene `BasketFundingIntent` bindet Account, Journal, Originalzustand und
letzten bestätigten Zeitraum. Nur feste Wallet-/Positions-/Bill-GETs sind
zulässig; weder Order-POST noch Orderfreigabe passen zu diesem Scope.
Originale aktuelle Identität, Trading-AEAD, Actor-/Credentialprüfungen,
gemeinsamer UID-Mutex und fünf Sekunden Kohorten-/Quellenfrist bleiben erhalten.

Alle Positionen müssen zu eigenen Mengen, Durchschnittspreisen, Gebühren,
realisierter Preis-PnL und Zyklen passen. Kumulatives Funding muss genau zum
eigenen bisherigen Funding plus Bills passen; Kontoänderung ohne UPL und
isolierte Margin werden ebenfalls abgeglichen. Transfer, Marginanpassung,
fremde Order/Position, unbekannte Beträge oder unvollständige Pagination
bestätigen keinen neuen Prüfstand. Jede nichtleere Seite wird fortgesetzt,
maximal8 Seiten/30Tage/110ms GET-Abstand.

Die [Bitget-Accountdokumentation](https://www.bitget.com/docs/catalog/classic-contract-account/classic-contract-account)
beschreibt Funding-Bills und die separaten Betrags-/Gebührenfelder;
die [Positionsdokumentation](https://www.bitget.com/docs/catalog/classic-contract-position/classic-contract-position)
beschreibt kumulatives `totalFee` und Transaktionsgebühren `deductedFee`.
Die Kapitalzuordnung wird aus passenden nativen Quellen belegt, nicht allein
aus einer vermuteten Börsenregel.

## Zeit, Wiederherstellung und weitere Integration

Journalformat `/5` speichert Fundingfenster, vollständige gehashte Bill-IDs,
Originalquellen und Buchungen in einer einzelnen bestätigten Änderung.
Auch eine belegte leere Seite darf den Prüfzeitraum fortführen. Derselbe
Bill kann nach Restore nicht erneut bezahlt werden. Frühere `/2`–`/4`-Journale
werden nicht automatisch übernommen; technisches BTC-Journal bleibt separat.

Nach bestätigter Kauf-/Verkaufsabrechnung wird ausschließlich deren
ursprünglicher finanzieller Snapshot-Endzeitpunkt übernommen. Die spätere
Pagination-/Ledger-Bestätigung darf das Fundingfenster nicht künstlich
verlängern. Native Buchungszeit und tatsächliche spätere Erkennungszeit
bleiben verschieden; keine verschobenen Funding-/Mitternachtsereignisse.

Offene Orderversuche werden zuerst geklärt. Funding während eines noch
ungeklärten Ordersatzes benötigt einen gemeinsamen Order-/Fundingabgleich;
die Einzelquellen dürfen diese Unsicherheit nicht durch Teilbuchungen verdecken.
Diese Recovery und der vollständige H1-Worker mit ursprünglichem dauerhaftem
Start-/Pause-Consumer gehören zur nächsten operativen Integration.

Tests verwenden echte Journaldateien, Restore, Trading-AEAD/HMAC und
finanzielle Reducer mit synthetischen Actor-/Brokerantworten.
22 neue/434 verschiedene betroffene gepinnte Fälle grün in Gesamtabdeckung:
breite433-Fall-Regression, finale68-Fall-Gruppe. Lesender Audit bestätigt
Originalhashes/sieben laufende Dienste und Images unverändert, technisches
Journal8. Finaler Executorbuild/Paketimport/elf Quellhashes ohne Netzwerk,
Quellmounts oder Zugangsdaten grün. Keine tatsächliche
Order, Kontoänderung oder automatische Aktivierung durch diese Implementierung.
