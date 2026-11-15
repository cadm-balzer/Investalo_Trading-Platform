# Demo-Konto: gebundener Snapshotabgleich

Stand 2026-11-15, IP-015/IP-016. PR74 (`45bf348`) ist in
`main8e6a98a` enthalten; GH/Fetch/Ancestry bestätigt.

`futures_demo_account.py` prüft einen begrenzten eigenen Classic-USDT-
Kontosnapshot gegen eine erklärte eigene Cash-/Positionsbasis und den
tatsächlichen [Outboxstand](bitget-demo-outbox.md). Das Ergebnis erkennt
Abweichungen und enthält private native Mengen/Balances sowie Responsehashes.
Es ist **keine Versand-, Basket-, Gewinn- oder Recoveryfreigabe**.
`execution_ready`, `cash_ledger_ready` und `pending_scope_verified` bleiben
ausdrücklich false.

## Feste Anfragebereiche

`DemoReadPlan` erzeugt ausschließlich unsignierte GET-Ziele mit
`paptrading: 1`. Keine URLs, Schlüssel, Modeänderungen, Cancel oder Orders.

| Bereich | Pfad / Parameter |
|---|---|
| USDT-Wallet | `/api/v2/mix/account/accounts`, USDT-FUTURES |
| Alle Produktpositionen | `/api/v2/mix/position/all-position`, USDT-FUTURES/USDT |
| Sieben Symbolkonfigurationen | `/api/v2/mix/account/account`, jeweils AVAX/BNB/BTC/ETH/LINK/SOL/XRP-USDT |
| Reguläre Liveorders | `/api/v2/mix/order/orders-pending`, explizit `status=live` |
| Reguläre Teilfills | gleicher Pfad, explizit `status=partially_filled` |
| Triggerfamilien | `/api/v2/mix/order/orders-plan-pending`, jeweils `normal_plan`, `track_plan`, `profit_loss` |

Damit sind14 ursprüngliche Bereiche erforderlich. Reguläre Pendingabfragen
nutzen beide dokumentierten Statuswerte: Der Default garantiert laut Anbieter
nicht die Teilfill-Abdeckung. Triggerfamilie `profit_loss` umfasst die
dokumentierten Profit/Loss/Moving/Positionsschutz-Varianten.
Pendingabfragen erhalten **keinen Symbol-/Order-ID-/Client-ID-/Zeitfilter**.
Ein enger Coinabruf würde fremde Produktorders verbergen.

Jede Seite ist auf100 Orders begrenzt. Ein nichtleerer `endId` verlangt
den exakt folgenden `idLessThan`-Abruf. Erst eine leere Seite ohne weiteren
Cursor erschöpft die über diesen Abruf erreichbare Achse. Kurze oder
nichtleere Seiten ohne Cursor beweisen keine Vollständigkeit.
Doppelte/regressive IDs, falsche Statusachsen, ausgelassene Seiten und
wiederholte Cursors werden abgewiesen. Maximal10 Seiten je Pendingachse,
insgesamt höchstens59 Pakete; keine unbeschränkte Pagination.

**Native Abfrageabdeckung bleibt gesondert offen:** Die offizielle Dokumentation
beschreibt Zeitfenster/Defaultgrenzen für Pendingabfragen. Erschöpfte Pagination
beweist keine Sichtbarkeit aller möglicherweise älteren manuellen/GTC-/Trigger-
Orders und keine atomare Brokeraufnahme. Deshalb
`pending_scope_verified=false`; vor echter Ausführung ist die native
Abdeckung im gebundenen Demo-Konto separat nachzuweisen.

## Eigene Erwartung und Outboxbindung

`AccountExpectation` benötigt sieben sortierte ursprüngliche eigene Longmengen,
einen bekannten erwarteten aktuellen Availablewert oder ausdrücklich unbekannt,
und die vollständige erklärte übrige Cashreservierung. Diese Werte müssen aus
dem eigenen ursprünglichen Konto-/Kosten-/Budgetplan kommen. Sie werden nicht
aus demselben gerade geprüften Snapshot abgeleitet, aus Paper übernommen oder
auf das verfügbare Cash verkleinert. Der Kern allokiert kein Kapital.

`DemoOutbox.check_account` liest Receipt und Traces unter einem gemeinsamen
lokalen Writer-/Threadlock und erwartet die aktuelle Gesamtrevision.
Der pure Reader bindet die gesamte Traceprojektion wieder an das bestätigte
State-/Bindingdigest. Andere Owner, Konten, Keys oder Tracekombinationen
werden abgewiesen. `check_current` erkennt inzwischen geänderte Receipts
und abgelaufene/frühere Uhren. Ein neuer Snapshot erzeugt keine neue Revision.

Für Positionserwartungen bleiben Prepared-Intents ungebucht.
Chronologisch versandte Intents müssen an die jeweils tatsächliche vorige
Menge anschließen; gleiche Dispatchuhr desselben Coins ist mehrdeutig.
Es zählt ausschließlich beobachtete kumulierte Fillmenge:
Buy erhöht, Reduce-only-Close senkt die eigene Menge. Ein Teilfill mit
anschließendem IOC-Storno bleibt Exposure. Keine Beobachtung ist ausdrücklich
unbekannt, kein erfundener Nullfill. Unklare oder offene Orders bleiben offen,
auch wenn die Pendingliste leer ist. Der Reader ruft keine Resends auf.

Der aktuelle native Gesamtbestand wird inklusive Peers geprüft; fremde Coins,
Short/Cross/Hedge, falscher Hebel, doppelte Positionen oder inkonsistente
Available/Locked/Total-Mengen werden nicht normalisiert.
Eine leere Position bei weiterhin belegter isolierter Margin/unrealisiertem
PnL bleibt eine Abweichung.

## Cash, Konfiguration und Quellen

Alle sieben Konfigurationen müssen USDT/single/isolated/one-way/Long2×
bestätigen. Native Leveragedarstellung als Integer2 oder String `"2"` wird
akzeptiert; Booleanwerte zählen nicht als Hebel.
Das Produktwallet muss einzig USDT/single sein. Crossmargin, Bonus/Voucher,
Mehrcoin-Collateral oder unbekannte benötigte Beträge verhindern einen
abweichungsfreien Prüfbericht.

Available, Account-Equity und unrealisierter PnL bleiben verschiedene native
Fakten. **Account-Equity enthält bereits unrealisierten PnL**; keine erneute
Addition. Negative Availablewerte bleiben erhalten. Fehlende Casherwartung,
Abweichung vom erklärten eigenen Cash oder unterschrittene erklärte
Reservierung werden angezeigt; keine Budget-/Stageänderung und kein
neuer Gate im bestehenden Paperworker.

Bekannte eigene Pendingorders werden über `clientOid`/Order-ID/Symbol/Size
zugeordnet; fremde/manuelle Orders bleiben separat sichtbar. Pendingorders
und jede Triggerfamilie bleiben Abgleichbedarf; keine automatische Löschung.
Ein bekannter Client-ID-Treffer ersetzt noch keinen vollständigen Detailabruf.

`DemoPacket` ist die trusted Verbindung zwischen ursprünglichem Readplan
und Antwort. Der spätere Transport muss deren tatsächlichen Ursprung sichern;
dieses Objekt beweist weder UID, Demo-Key-Provenienz noch Brokerauthentizität.
Alle Antwortuhren müssen aktuell, maximal5s alt und nicht zukünftig sein;
kein Bereich darf den jüngsten gespeicherten Orderbelegen vorausgehen.
SHA256 der jeweiligen ursprünglichen Antwortbytes bleibt im Ergebnis;
kein raw HTTParchiv oder Providertext wird persistiert.

`matched=true` bedeutet nur: keine erkannte Abweichung innerhalb dieser
erklärten Basis und dieses abgefragten Snapshots. Bereits bekannte Gebühren
werden nicht erneut gebucht; fehlende Fillfees bleiben unbekannt. Native
Funding-/Fill-/Cashabrechnung, dedizierte Kontopfadregistry, tatsächliche
UID/Parent/IP/Rechte, Trigger-/ältere Orderabdeckung und Transportabnahme
stehen weiter aus. Classic `fill-history` ist laut Anbieter nicht im Demo
unterstützt; keine Ersatzkosten oder angeblichen Nettoerträge.

Der [registrierte Zugang](bitget-demo-account-registry.md) ergänzt inzwischen
lokale ursprüngliche UID-/Kontopfadbindung. Der Bericht bleibt advisory;
keine native Demo-Identität wird dadurch bewiesen.

## Prüfung

22 neue synthetische Accountfälle plus70 bestehende Demo-/Outbox-/Readfälle:
**92 grün** auf Host-Python3.14.4. Alle14 Bereiche, Cash/Config/Peers,
Sequential Ladder/Teilfill/Storno, unbekannte Orders/Kosten, Native-Cursorfolgen,
Fremdorders/Trigger, Stale/CAS/Owner und der tatsächliche private Outboxrestore
sind geprüft. Keine nativen Brokerrequests, Keys, Finanzbuchungen,
Dienste/DB/Migrationen/Dependencies/Frontendbuilds/Backtests/Public/Live/AI.

Offizielle Bitget-Dokumentation, geprüft am2026-11-15:

- [Classic Account: Wallet, Konfiguration und Equity](https://www.bitget.com/docs/catalog/classic-contract-account/classic-contract-account)
- [Classic Trade: Pendingstatus und Pagination](https://www.bitget.com/docs/catalog/classic-contract-trade/classic-contract-trade)
- [Classic Trigger: drei Pendingfamilien](https://www.bitget.com/docs/catalog/classic-contract-plan/classic-contract-plan)
