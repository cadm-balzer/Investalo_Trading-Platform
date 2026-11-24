# Abschluss der bestätigten BTC-Demotestposition

Nach PR116/mainc336f86 ist die tatsächliche Eröffnung abgenommen:
0,0003BTC,2× isoliert, Ø61.425,7USDT, Gebühr−0,01105662USDT.
Das vorhandene Journal enthält genau eine Vorbereitung, einen Versand,
ein ACK und eine vollständige Beobachtung, Revision4.
Der Nutzer verlangt den nächsten Schritt: dieselbe Testposition schließen.

## Verhalten

Im Cockpit wird der Abschluss ausdrücklich vorbereitet und anschließend
mit „BTC-Testposition einmal schließen“ bestätigt. Die feste Menge
stammt aus der vollständig ausgeführten ursprünglichen Eröffnung im
privaten Journal. Eine frische vollständige native Position muss Menge,
Einstand, BTCUSDT, Long,2× und isoliertes Profil bestätigen.
Die fünf Pendingfamilien müssen vollständig und leer sein; ursprüngliche
Actor-/Key-/UID-/Parent-/IP-/Zeit-/Quotaprüfungen bleiben erhalten.

Der Auftrag ist Market, `side=sell`, `reduceOnly=YES`; kein price/force
oder Hedge-tradeSide. Die neue Zustimmung hat eigene Kind/Audience/URI
und eine eigene Bestätigungsphrase. Eröffnungs-, Lese- oder Keytokens
erteilen keine Abschlussautorität. 30s Vorschau und15s signierte
Zustimmung verlängern nicht die tatsächliche5s-Quellenfrische.
Unmittelbar vor POST wird die ursprüngliche native Quelle erneut geprüft.

Ein Kursanstieg über den technischen20USDT-Eröffnungswert darf das
Reduzieren der vorhandenen Menge nicht verhindern. Deshalb gilt dieser
Notionaldeckel nur für die Eröffnung. Die vollständige Abschlussmenge
bleibt exakt die bestätigte Testmenge; native Mengen-/Vertragsraster
bleiben verbindlich. Die allgemeine Basketregel bleibt Kaufmargin×Hebel.

Der Abschluss verwendet dieselbe Registry/Outbox und eigene persistente
Consentverbrauchsdatei. Es gibt höchstens einen Abschlussversuch.
Vorbereitung reserviert im bestehenden16-Befehle-Journal genügend Platz
für Versuch/ACK/Beobachtung; kein Reset, Rewrap, Registryumzug oder
Journalumschreiben. Eröffnung wird nicht wieder freigeschaltet.
Unknown vor POST bleibt dauerhaft erhalten; kein automatischer Retry
oder zweiter Auftrag nach Teilfill, Storno oder verlorenem ACK.

Bitget kann bei Reduce-only das orderId im ACK weglassen. Die vorhandene
GET-Reconciliation nutzt deshalb weiterhin den ursprünglichen clientOid.
„latest“ wählt den jüngsten eindeutig datierten Versuch einschließlich
des Abschlusses. Nach Neustart ist dieselbe lesende Klärung möglich.

Nach der Abschlussbeobachtung erfolgt ein separater frischer ursprünglicher
Kontoabruf mit drei festen GETs. Angezeigt werden Ein-/Ausstiegsgebühren
mit nativem Vorzeichen, tatsächlicher Kontowert/freie Margin, Positionsanzahl
und Quellenzeit. „Nullposition bestätigt“ benötigt vollständigen Fill,
Positionsabgleich, keine Positionen sowie bestätigte Nullbeträge für
Locked/UPL/isolierte/gekreuzte Margin. Unbekannte Felder bleiben unbekannt.
Ein Teilabschluss zeigt die verbleibende Position und behauptet keinen
vollständigen Abschluss. Kontowert ist kein erfundener Trade-PnL:
Funding und andere Zahlungsströme sind noch nicht einzeln zugeordnet.

## Prüfung und Betrieb

Gepinnte Offlineprüfungen umfassen tatsächliche ASGI-/Node-mTLS-Verbindungen,
AEAD, Registry, Consentverbrauch, Journalrestore, fehlendes Reduce-only-ACK,
Unknown/Teilfill, falsche Menge/Zweck/Actor und steigenden Notionalwert.
Die Actor-/DB-Ports und nativen Brokerantworten dieser Tests sind synthetisch.
Es werden keine realen Brokeraufträge aus Test-/Operator-Kontexten erzeugt.
173 unterschiedliche betroffene Pythonfälle und75 gepinnte Nodefälle
bestanden. Vollständige Typprüfung und beide finalen Produktionsbuilds
grün; Next-Produktions-Typprüfung18,3s. Vor Rollout ist das tatsächliche
Eröffnungsjournal weiterhin Revision4 mit genau einem Versuch/ACK/Fill.
Die abschließende Launcherprüfung fand die noch auf drei Eröffnungsaktionen
begrenzte Weiterleitung. Die produktive Closure verwendet jetzt dieselbe
exakte Market-Actionliste wie der HTTP-Adapter. Der tatsächliche ASGI-/mTLS-
Abschlusstest läuft durch diese Launcher-Closure; fehlende Installation und
unbekannte Aktionen werden vor Weiterleitung abgewiesen.70 betroffene
Launcher-/HTTP-/Marktfälle anschließend grün, finaler Executor neu gebaut.

Beide Produktionsimages werden auf dem kleinen Host nacheinander gebaut.
Der bestehende einzelne Demo-Testumfang und die ursprünglichen sechs
Composeoverlays bleiben erhalten. Nur Cockpit und Demo-Executor benötigen
eine Aktualisierung. Originale Images/Keyzustände/Dienst-IDs und privater
Journalbestand werden vor/nach dem Rollout geprüft. Der tatsächliche
Abschluss erfolgt ausschließlich nach der ursprünglichen Cockpitbestätigung.
Rollback auf alte Images ist nur vor der ersten Abschlussvorbereitung
geeignet; danach müssen die neuen Abschlussbefehle erhalten und von einer
kompatiblen Version gelesen werden. Keine Rücksetzung des Journals.

Die [offizielle Bitget-Orderdokumentation](https://www.bitget.com/docs/catalog/classic-contract-trade/classic-contract-trade)
bestätigt One-way `reduceOnly`, Market ohne Limitpreis und mögliche
fehlende orderId; geprüft2026-11-24.
