# Dauerhafter Verbrauch der Demo-Orderfreigabe

Der Nutzer möchte die kleine BTC-Demo-Testorder starten: Long, isoliert,
2×, höchstens20 USDT Positionswert gemäß vorhandener Vorschau.
Diese Anfrage autorisiert die Arbeit an diesem technischen Demotest;
automatischer Strategiehandel und Echtgeldhandel sind davon nicht umfasst.
Die operative Versandroute ist weiterhin nicht eingerichtet.

`DurableDemoOrderConsumer` ergänzt den vorhandenen
[Versandkern](bitget-demo-order-dispatch.md) um einen echten Dateiverbrauch.
Sein vertrauenswürdig installierter `issuer` muss zuvor die eigene gültige
Orderzustimmung und den aktuellen Actor verifizieren und die genaue
`DemoOrderApproval` liefern. Der Consumer stellt keine Tokens/Zustimmungen
aus und macht aus einer Konto-Leseassertion keine Orderfreigabe.
Ein konstruierbares internes Approvalobjekt ist weiterhin kein Nachweis
einer tatsächlich erfolgten Zustimmung.

## Reihenfolge

Der Consumer prüft Originalroot, Owner-/Kontobindung, Intent, Outboxbeleg,
Freigabe-ID, Revisionen und die bestehende15s-Gültigkeit. Frische Actor-
und Installationsprüfungen erfolgen vor/nach dem Issuer sowie nach dem
Schreiben. Ein eigener `consumed-<UUID>.json`-Marker wird mit `O_EXCL` erstellt,
vollständig geschrieben, Datei und Verzeichnis werden synchronisiert.
Die ursprüngliche Datei wird über einen separaten Descriptor nachgelesen.
Erst dann erhält der Dispatcher die Freigabe und darf Credentials öffnen.

Die Originalinstallation wählt den privaten0700-Root;0600-Dateien,
Originalinodes, keine Symlinks/Hardlinks und höchstens1024 Marker.
Ein anderer Prozess kann dieselbe ID nicht erneut verbrauchen.
Unvollständige, abgelaufene oder bei verlorener Schreibbestätigung
zurückgebliebene Marker werden nicht gelöscht oder erneut ausgestellt.
Es gibt keine automatische Wiederholung oder neue Freigabe nach Neustart.
Die vorhandene Outbox protokolliert weiterhin `submission_unknown` vor POST.

Die Marker enthalten nur IDs, Hashes, Beleg und Revision/Zeit, keine
API-Daten, JWTs, Sitzungsclaims oder nativen Orderantworten.
Issuer, Native-Accountguard, Registryinstallation und geschützter
Ordertransport müssen weiterhin ausdrücklich verdrahtet werden.
Die laufende Runtime installiert diesen Consumer noch nicht.
Der eigene [BTC-Zustimmungsbaustein](bitget-demo-btc-order-consent.md)
prüft jetzt tatsächliches BFF-HMAC, Originalkontext und aktuelle Trading-
Snapshots vor dem Dateiverbrauch. Er ist ebenfalls noch nicht operativ
installiert; fehlende Brokerangaben werden nicht dadurch freigegeben.

## Prüfung und tatsächlicher Stand

185 gepinnte Offline-Pythonfälle grün, darunter neun neue Tests mit echten
privaten Dateien, konkurrierenden Consumern, neuem Consumer nach Neustart,
unvollständigem Marker aus tatsächlich beendetem Kindprozess und
fsync-/Expiryfehlern. Tatsächlicher AEAD-/Dispatcherlauf mit synthetischer
Zustimmung und synthetischen Brokerantworten; kein nativer Ordernachweis.
Executorbuild grün, keine neue Dependency/Migration/Frontendänderung.

PR111/main `bf5ddbe` verifiziert und Bonusguthaben-Abgleich ausgerollt.
Nur der Demo-Executor erneuert; alle sechs anderen Dienste unverändert.
TLS200, drei anonyme Accountvarianten401, tatsächliches privates mTLS405,
Key active/revision1/storage1. Originale Overlays/Envdatei erhalten,
Rückweg und Vorher-/Aktivbelege unter `infra/local/demo-btc-grant-source`.
Neue originale Dashboard-Anfrage erfolgreich:elf GETs/3952ms/HTTP200/00000,
private Quellenklasse `unconfirmed`. Nutzer bestätigt weiterhin unbekanntes
Bonusguthaben und unbekannte maximale Ordermenge. Damit ist der Abgleich
tatsächlich ausgeführt, aber kein nativer Nullbetrag bestätigt.

Zwei neue öffentliche Demo-GETs bestätigen weiterhin leere native
`maxOrderQty`/`maxMarketOrderQty`, Maker0,0002/Taker0,0006,
`openCostUpRatio`0,01 und `feeRateUpRatio`0,005.
Dies sind Kontraktangaben, kein Nachweis kontospezifischer oder tatsächlich
berechneter Gebühren. Vorschau18,45933 USDT; kein Auftrag.
[Bitget-Kontraktfelder](https://www.bitget.com/docs/catalog/classic-contract-market/classic-contract-market),
[kontospezifische Trade Rate](https://www.bitget.com/docs/catalog/classic-common-public/classic-common),
geprüft2026-11-23. Native Höchstmenge, tatsächliche Kosten-/ältere
Auftragsabdeckung sowie die ursprüngliche operative Kontobasis bleiben offen.
