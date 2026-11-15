# Classic Futures Demo: Auftragsvertrag und Abgleich

Stand 2026-11-15, IP-015/IP-016. PR72 (`b956064`) ist in
`main4d3b326` enthalten; GH/Fetch/Ancestry bestätigt.

Der separate Offlinekern erzeugt präzise, **unsignierte** Auftragspläne und
prüft native kumulierte Orderdaten gegen die geplante Order und Positionsmenge.
Er enthält keinen HTTP-Dispatcher, keine Schlüssel,
keine Ledgerbuchung und keine Aktivierung im Cockpit oder Worker.
Der folgende [eigene Outboxcheckpoint](bitget-demo-outbox.md) ergänzt
dauerhafte private Orderpersistenz und vollständigen Crashrestore.
Der bestehende Classic-Realkonto-Readadapter behält seine drei GET-Pfade.

## Eigenes Konto und begrenztes Profil

`DemoBinding` bindet den serverseitigen Tenant/User, Plattformkonto,
Credentialreferenz und erwartete Broker-UID an die erklärte Demo-/Classic-Familie.
Das ist eine vertrauenswürdige Executor-Deklaration, **kein** Nachweis,
dass ein Key tatsächlich zu diesem Demo-Konto gehört. Native Order-/Positions-
antworten liefern diesen UID-/Keynachweis nicht. Der spätere Provider muss die
geschützte Einrichtung, eigene Demo-Key-Provenienz, UID/Parent/IP/Rechte,
Account-/Writerbindung und synchronisierte Brokeruhr separat belegen.
Browserangaben oder ein gesetztes Header reichen dafür nicht.

Laut offizieller Classic-Dokumentation wird ein eigener **Demo API Key** in
Bitgets Demo-Modus erstellt. Requests tragen `paptrading: 1` am gleichen
API-Host. Ein vorhandener lesender Realkontokey wird nicht umgewidmet.
Demo-Einrichtung benötigt laut Anbieter KYC.

Der erste vorgeschlagene Adaptervertrag beschränkt sich auf USDT-Futures,
isolierte Longs und bestehende 2×-Konfiguration für die sieben Kandidaten
AVAX/BNB/BTC/ETH/LINK/SOL/XRP. **One-way mode und Limit-IOC sind zunächst
Implementierungsvarianten für die spätere Demoabnahme**, keine Erlaubnis zum
Ändern eines bestehenden Brokerkontos oder einer Handelsstrategie.
Kein Mode-/Leveragewechsel, Short, Cross, Transfer, UTA-Fallback,
Cancel-all, Triggerauftrag oder Market-Fallback wird erzeugt.

## Präzise Auftragsbytes

`futures_demo.py` prüft explizite aktuelle Quantity-/Preisgrids,
Mindestmenge/-notional und maximale Limitmenge. Decimal-Arithmetik bleibt auch
bei verändertem Aufruferkontext exakt. Ungültige Größen werden abgewiesen;
kein stilles Runden, Verkleinern eines reservierten Budgets oder Ersetzen
von Eigenkapital durch Ordernotional.

`DemoIntent.quantity` ist **Basismünzenmenge**, nicht USDT-Eigenkapital.
Die vorgelagerte Größenplanung muss weiterhin das volle reservierte
Basketbudget, reguläre/manuelle Kaufstaffel, Kosten, tatsächliches Cash und
Margin berücksichtigen. Dieser Kern berechnet keine Basketallokation.
Der 2×-Hebel ist eine Konto-Voraussetzung, kein Place-order-Feld.
`before_quantity` benötigt später bestätigte eigene Positions-/Orderdaten.

| Plan | Feste Semantik |
|---|---|
| `place` | POST `/api/v2/mix/order/place-order`, Limit/IOC, USDT/isolated; Buy/NO öffnet Long, Sell/YES reduziert Long |
| `detail` | GET `/api/v2/mix/order/detail`, Symbol/USDT-FUTURES und dieselbe `clientOid` |
| `positions` | GET `/api/v2/mix/position/all-position`, gesamtes USDT-FUTURES/USDT-Produkt |

Die Closemenge darf die bestätigte vorherige Longmenge nicht überschreiten.
Buy-Limit begrenzt den Kaufpreis; Sell-Limit bildet eine Preisuntergrenze.
Die wirtschaftliche Netto-Break-even-Grenze und Notausstieg/Supertrend werden
hier noch nicht berechnet. Eine spätere Ausführungsentscheidung benötigt
deren gesonderte Integration und tatsächliche Kosten.

`clientOid` bleibt für Tenant/Konto/Command stabil; das gesamte eigene
Intentdigest bindet zusätzlich Nutzer, Credentialreferenz, Profil, Grid,
Menge, Preis und vorherige Position. Geänderte Payload bei gleicher Command-ID
behält die Kennung, verändert aber das Digest: Die spätere Outbox muss diesen
Konflikt atomar ablehnen. Das ist **keine** Zusicherung einer globalen
Bitget-Idempotenz oder einer Wiederholbarkeit von Place-order.

## Unklare Antworten und Teilfüllungen

`futures_demo_reconcile.py` bildet ausschließlich reine immutable Kandidaten:
Prepared → vor Versand Submission-unknown → Acknowledged oder native
Live/Partially-filled/Filled/Canceled. Ein bereits versandter Kandidat erlaubt
keinen erneuten Versand. Der Übergang muss **vor** jedem echten HTTP-Send
dauerhaft unter eigener Konto-/Command-CAS bestätigt sein.
Ein neu erzeugtes In-memory-Objekt ersetzt keine Wiederanlauf-/Outboxprüfung.

Ein erfolgreicher Place-ack zählt niemals als Fill. Laut Dokumentation können
Reduce-only-Acks die `orderId` auslassen. Lookup mit derselben `clientOid`
löst eine verlorene Antwort oder fehlende ID auf. Timeout, HTTPfehler und
Provider-Not-found bleiben unklar; sie beweisen keine Nichtexistenz und
berechtigen nicht zum Blind-Resend.

Native Orderdetails müssen Scope, Kennung, Symbol, Longrichtung, One-way,
isolierte 2×-Margin, Ordertyp, Force, Größe und Preis bestätigen.
Kumulierte Menge darf nicht sinken; Order-ID/Erstellungszeit bleiben konstant.
Gleiche Fillmenge darf ihren Durchschnitt nicht ändern. Terminaldaten dürfen
nicht wieder öffnen. Frische Antwortuhr: maximal5s alt, niemals zukünftig;
Erstellungs-/Updateuhren werden gesondert erhalten.

Ein IOC kann **teilweise gefüllt und dann storniert** werden. Die tatsächlich
gefüllte Menge bleibt Exposure, und der Rest gilt nicht als ausgeführte
Kaufstaffel. Der Positionsabgleich erwartet ausschließlich vorherige Menge
plus/minus kumulierte tatsächliche Füllung. Ein älterer Positionssnapshot,
abweichende Menge, inkonsistente Available/Locked/Total-Daten, fremdes Asset,
Short-/Cross-/Hedgeprofil oder doppelte Position stoppt diesen engen Vertrag.
Zulässige Peer-Kandidaten werden nicht gelöscht.

Ein erfolgreicher Mengenvergleich ist **keine neue Handelsfreigabe**:
Offene reguläre Orders, Trigger-/TPSL-Orders, Fremdaktivität, Accountcash,
Liquidationen und Kosten benötigen zusätzlich eigenen vollständigen Abgleich.
Ein leerer Positionssnapshot beweist weder Orderfreiheit noch abgeschlossene
Abrechnung oder ein volles neues Recoverybudget.

## Kosten und weitere Abnahme

`fee` wird als gemeldeter signierter Wert erhalten, fehlend bleibt unbekannt.
Keine erfundenen Einzel-Fill-IDs, Gebühren, Fundingwerte oder Nettoerträge.
Die offizielle Classic-Abfrage **Historical Transaction Details / fill-history**
ist laut Dokumentation im Demo-Modus nicht unterstützt. Kumulierter Orderstand
und Position ersetzen deshalb kein kalibriertes Fill-/Funding-/Kostenledger.
Paper-Vollfills, Paperliquidationen und historische Binanceökonomie werden
nicht als tatsächliche Demoabrechnung übernommen.

Die eigene dauerhafte Outbox/Executionjournal mit Command-CAS,
Unknown-write-/Crashrestore ist separat implementiert.
Als Nächstes gebundene Transportgrenze und vollständige
Account-/Normalorder-/Triggerorder-Reconciliation samt Kostenquelle.
Der [eigene Accountcheck](bitget-demo-account-check.md) verbindet inzwischen
14 abgefragte Bereiche mit dem tatsächlichen Outboxstand. Native Konto-/
Zeitfenster-/Kostenprovenienz und echte Transportabnahme bleiben ausstehend.
Erst danach eigene sichere Demo-Keyeinrichtung und konkrete native Abnahme.
Bestehende Paperjournale und deren Budgets/Ergebnisse bleiben unverändert.

## Prüfbeleg und Quellen

24 neue synthetische Offlinefälle, zusammen mit24 unveränderten Readadapter-
fällen **48 grün** auf Host-Python3.14.4. Prüfen Owner/Profil/Grids,
Commandkonflikt, feste Requests, Unknown/fehlende ID, Teilfill/Storno,
Preisgrenzen, monotone/terminale Daten, unbekannte Gebühren und Positionen.
Keine Brokerrequests, Dienste, Datenbank/Migrationen, Dependencies,
Frontendbuilds, neuen Backtests oder Public/Live/AI-Aktivierung.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=integrations/bitget/src \
  python3 -m unittest discover -s tests/bitget -v
```

Offizielle Bitget-Dokumentation, geprüft am2026-11-15:

- [Classic Demo-Key und REST-Header](https://www.bitget.com/docs/classic/demo-trading/rest-api)
- [Classic Trade: Place, Detail und Demo-Fill-History-Grenze](https://www.bitget.com/docs/catalog/classic-contract-trade/classic-contract-trade)
- [Classic Position: All-positions und Mengen](https://www.bitget.com/docs/catalog/classic-contract-position/classic-contract-position)

Die offiziellen Beispiele variieren bei Symbol-/Margincoin-/Reduce-only-Case
und zeigen One-way-Positionen als `net` beziehungsweise `long`.
Nur diese ASCII-Casevarianten werden akzeptiert; unbekannte Profile sperren.
Reale Schema-/Kosten-/Accountkalibrierung bleibt ausdrücklich ausstehend.
