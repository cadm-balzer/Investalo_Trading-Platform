# Native Marketanbindung für H1-Baskets

Stand2026-11-24. PR119/main`e6e5b46` verifiziert.
Die eigene `BasketOrderDispatcher` verbindet das
[Basketjournal](bitget-demo-basket-journal.md) mit dem vorhandenen
verschlüsselten Trading-Schlüsselspeicher und eigenen signierten
Bitget-Classic-Demo-Marketpaketen.

## Auftrag und Ausführung

Der Auftrag übernimmt unverändert die feste Menge aus der H1-Kaufvorbereitung:
Kaufmargin×2, auf das native Mengenraster abgerundet. Native Mindestmenge,
Mindestnotional und bestätigtes Marktmaximum bleiben verbindlich; eine
Kaufstufe wird nicht verkleinert. Unterstützt werden die sieben bisherigen
Kandidaten AVAX/BNB/BTC/ETH/LINK/SOL/XRP. Automatische Stufen bleiben1–5,
Long/isoliert/One-way/2×.

Die tatsächliche POST-Payload enthält `size` als Basismenge, `orderType=market`,
`side=buy`, `reduceOnly=NO`, USDT und isolierte Margin. Sie enthält weder
Limitpreis noch IOC-Parameter. Die eigene stabile `ivb`-Clientkennung bindet
Journal-UUID, ursprüngliche Command-ID und Kontobindung; der separate
20USDT-BTC-Test bleibt in seiner bisherigen Domäne.

Vor der POST-bezogenen Entschlüsselung stehen die vollständige externe native
Zulassungsprüfung und der durable eigene Basketconsumer. Seine eigene
Approval-Klasse bindet Intent, exakten Journalreceipt, Requestdigest,
Credentialrevision/Storage und15s-Fenster. Aktuelle Actor-/Credential-/UID-/
Parent-/Rechte-/IP- und Quellenprüfungen werden vor und nach den nativen
Operationen wiederholt. Die Journal-Versandmarke liegt vor POST auf Platte.
ACK bedeutet keinen Fill; ein unbestätigter Ausgang bleibt GET-only.

Die gesonderte GET-Seite akzeptiert nur Identitätsabfrage sowie eigene
Orderdetail-/Gesamtpositionspakete und lehnt POST-Pakete ab. Bestehende
Read-/Limit-/BTC-Testpakete und Approval-Klassen akzeptieren die neue
Basketdomäne nicht; die Basketdomäne akzeptiert sie ebenfalls nicht.

## Abgleich

Der native Orderdetailparser prüft ursprüngliche Clientkennung, Symbol,
USDT-/Margin-/Positionsprofil, Seite, Markettyp, Hebel, feste Ordergröße und
Zeiten. Kumulative Menge, tatsächlicher gewichteter Fillkurs und signierte
Gebühr bleiben erhalten, einschließlich unbekannter Gebühr, Teilfill und
schlechterem Marketfill.

Der Positionsabgleich prüft den gesamten USDT-Produktbestand gegen die eigenen
Baskets: keine fremde Menge und kein anderes Profil. Beim Nachkauf wird der
gemittelte Positionskurs aus vorherigem Bestand und tatsächlichem Fill
abgeglichen. Die Rundungsabweichung ist auf die letzte gemeldete native
Dezimalstelle und höchstens den eingefrorenen Preistick begrenzt.
Eine Positionsantwort vor der Orderantwort bestätigt keinen Abschluss.

Native Order-ID und Erstellungszeit werden als Digest zusammen mit der nativen
Updatezeit im ausstehenden Journalbeleg gebunden. Ein anderer Auftrag,
zurücklaufende Updatezeit oder widersprüchliche bekannte Gebühr zum selben
Update kann nach Neustart nicht still übernommen werden.

Bitget bezeichnet `marginSize` als Positionsmargin im
[Classic-Positionsabruf](https://www.bitget.com/docs/catalog/classic-contract-position/classic-contract-position).
Die Schlussfolgerung für diese Anbindung: Dieser Gesamtwert belegt allein
keinen einzelnen Kaufdebit. Ein eigener vertrauenswürdiger Marginnachweis
bindet deshalb ursprüngliche Order, kumulative Fillmenge, native Quelle und
Frische. Ein solcher Producer ist noch nicht installiert. Ohne ihn bleibt
die ausgeführte Order ausstehend; es wird weder `marginSize` übernommen noch
eine berechnete Menge×Preis/2 als bestätigter Kontodebit ausgegeben.

## Prüfstand und Restumfang

18 neue gepinnte Pythonfälle verwenden echte Trading-AEAD, echte HMAC-Pakete,
eigene Originaljournaldateien und Vollrestore; Broker-/Actor-/Consumer-/
Marginnachweise sind synthetisch. Einschließlich der bestehenden H1-, Kapital-,
Paper-, Journal- und Demoorderregressionen sind263 verschiedene Fälle grün.
Der erste breite Lauf hatte allein einen fehlenden Worker-Quellpfad im
Prüfcontainer; dieser Fall und die finale Native-/Workergruppe sind danach
vollständig grün. Kein fehlgeschlagener Produktfall bleibt offen.

Geprüft sind insbesondere zwei tatsächliche Buchungsstufen im synthetischen
nativen Ablauf mit echtem RSI-Rearm,25% größerer zweiter Kaufmargin und
gemittelter Position, verlorenes ACK/GET-only-Restart, Teilfill, fehlende
Gebühr/Margin, Orderidentität, Token-/Packetdomänen und Widerruf nach POST.

Das gepinnte Executorimage enthält jetzt auch die Tradingmodule. Build und
Import ohne Quellmounts/Schlüssel/Netzwerk geprüft. Keine Abhängigkeits- oder
Migrationsänderung, kein Frontendbuild und keine Dienste neu gestartet.

Die Anbindung ist eine standardmäßig deaktivierte private Komponente.
Es fehlen noch die operativen native Quellen-/Zulassungs-/Margindebit-Producer,
eigener Strategieconsumer/-issuer sowie Worker und originale Dashboard-
Startfreigabe. Die injizierten Prüfports werden nicht für Produktion verwendet.
Keine tatsächliche neue Brokerorder oder tatsächliche native Abnahme dieses
Basketablaufs. Das technische Revision8-Journal und die sechs bisherigen
Rolloutoverlays bleiben separat erhalten. Basketjournal`/2` bindet die neuen
nativen Beobachtungsfelder; `/1` wird nicht automatisch adoptiert oder umgeschrieben.
