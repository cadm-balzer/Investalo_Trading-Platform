# Privater Demo-Orderkern und BTC-Testvorschau

Der Orderkern verbindet den vorhandenen registrierten Demo-Writer mit dem
echten Trading-AEAD-Provider. Er ist noch nicht in die operative HTTP-/BFF-
Runtime eingebaut. Ohne ausdrückliche Installation und eigenen dauerhaften
Order-Consumer bleibt `dispatch` vor jedem Zugriff gesperrt. Der bestehende
Read-/Key-Write-Purpose kann keinen Auftrag autorisieren.

Die Installation verlangt zwei getrennte vertrauenswürdige Adapter:
`authorize_once` muss eine echte, dauerhafte einmalige Freigabe für exakt
Intent, Outboxbeleg, Keyrevision und Speicherversion verbrauchen;
`account_guard` muss den aktuellen nativen Konto-/Order-/Reservierungsstand
gegen die eigene ursprüngliche Basis prüfen. Die strukturelle Klasse
`DemoOrderApproval` ist ausschließlich ein internes Consumerresultat.
Ihr Konstruktor, ein aktiv gespeicherter Key oder ein Startbericht sind
kein Beleg einer tatsächlich erteilten Freigabe. Diese operative Verdrahtung
und ihre Abnahme fehlen noch; es gibt keine öffentliche Orderroute.
Der [dauerhafte Orderconsumer](bitget-demo-order-consumer.md) implementiert
jetzt den tatsächlichen einmaligen Dateiverbrauch einer genauen Freigabe.
Ein operativer eigener Zustimmungsissuer und nativer Accountguard bleiben
vor Installation erforderlich.

## Ablauf

1. Ursprüngliche Registry-/UID-Lease, Konto, Owner und Outbox-CAS prüfen.
2. Konto-/Budgetguard und eigene genaue, maximal15s-Freigabe.
3. Frischer Trading-Provider, native Demo-UID/Parent/Rechte/IP und5s-Zeit prüfen.
4. `submission_unknown` über die bestehende Outbox append/fsync/readback
   **vor** dem POST dauerhaft bestätigen.
5. Genau einmal die vorhandenen isolierten2×-Long-Limit-IOC-Bytes senden:
   unveränderte Menge, Preis, stabile `clientOid` und vollständiger Intentdigest.
6. Aktuelle Credentials/Freigabe/Frische erneut prüfen; ACK ausschließlich
   über die vorhandene Outbox-CAS buchen.

Eigener HTTPS-Transport: nur feste Place-/Detailziele, Demoheader, exakte
HMAC-Bytes, CA/Hostname/TLS1.2, keine Proxys, Redirects oder Wiederholungen,
begrenzte Antwortgröße. Alte Readtransporte lehnen seinen Requesttyp ab.
Private Pakete/Grants sind unveränderlich, redigiert und nicht serialisierbar.
Ein Paket wird bereits vor Transportöffnung einmalig verbraucht. Der
Dispatcher bindet PID und gemeinsamen UID-Mutex; kein Request bestimmt Pfad,
Provider, Registry, Identität, Mode oder Transport.

Unklare Sendung oder lokaler Publish-ACK-Verlust behalten den ursprünglichen
durablen Präfix; weder fehlgeschlagen umschreiben noch erneut senden.
`outcome_unknown` enthält nur den bekannten Mindestbeleg: ein nachfolgender
ACK kann trotz verlorener lokaler Bestätigung bereits auf Disk stehen.
Vollrestore über den vorhandenen Writer bleibt maßgeblich.

`observe` liest ausschließlich native Identität, Detail der ursprünglichen
`clientOid` und Positionen. Bestätigte kumulative Teilfills/Kostenfelder werden
über vorhandene Schema-/Mengen-/Zeitprüfer im Journal behalten. Ein misslungener
Positionsvergleich löscht kein bestätigtes Orderdetail. ACK ist kein Fill;
unbekannte Gebühren bleiben unbekannt. Kein Cash-/Netto-PnL-Ledger und keine
automatische Wiederbelebung.

## Öffentliche Testvorschau

Der explizite Aufruf
`python -m investalo_bitget.futures_demo_preview --demo-btc-preview`
liest nur zwei öffentliche Demo-GETs: BTC-Kontrakt und BTC-Ticker.
Keine Keys, Kontositzung oder privaten Mounts nötig; ohne Opt-in keine Anfrage.

Die unverbindliche BTC-Long-Limit-IOC-Vorschau verwendet bekannte native
Mindestmenge, Mengen-/Preisraster, Mindestensnotional und frisches Bid/Ask.
Eigenes Positionswertlimit20 USDT,2×-Initialmargin höchstens10 USDT vor Kosten,
höchstens0,1% Limitaufschlag zum Ask, immer abrunden. Unzureichende native
Mindestmengen werden nicht durch Budgeterhöhung passend gemacht.
Diese kleine technische Testvorschau verändert keine Basketstrategie.

Der tatsächliche öffentliche Demoabruf am20261122 liefert `maxOrderQty=""`.
Die Vorschau weist deshalb Maximum **null/unverifiziert** aus und benutzt
einen eigenen Previewrastertyp, der nicht als vollständiges `DemoGrid` oder
Orderfreigabe verwendet werden darf. `account_verified`, `fees_verified` und
`submission_enabled` bleiben false. Tatsächlicher erster Auftrag braucht
native Konto-/Limitklärung und die gesonderte konkrete Freigabe.

Primärquelle:
[Bitget Classic-Kontrakte und Ticker](https://www.bitget.com/docs/catalog/classic-contract-market/classic-contract-market),
geprüft am20261122. Öffentliche Quoten belegen keine private Kontokonfiguration.

## Rollout und Prüfung

PR106 ist auf main30ccdbe gemergt und der Startprüfungsrollout vom Nutzer
freigegeben. Nur Cockpit und Demo-Executor erneuert; fünf andere laufende
Dienste unverändert, Cockpit gesund, privates echtes mTLS405, öffentliches
TLS200 und beide anonymen Readvarianten401. Key bleibt active/revision1/storage1.
Private Vorher-/Aktivbelege in `infra/local/demo-startup-check/rollout-*`.

Der erste Nutzer-Startabruf scheitert noch. Eigene rein technische private
Stage-/Count-/Timing-/Statusdiagnose im bestehenden Executor-tmpfs ausgerollt;
keine Sitzung, Keydaten, native Rohantwort oder Konto-UID darin.
Der neue echte Abruf belegt native200/00000 und5265ms nach zehn GETs:
serielle Kohorte zu langsam. [Begrenzte Überlappung](bitget-demo-startup-check.md)
behebt die Laufzeit bei unveränderten Guards. Weitere native Diagnose belegt
null/null-Pending-Leerantwort in4371ms; eigener Startupadapter ergänzt diese
exakte Endseite mit Originalclock. Gemeinsame Queue entfernt weitere Barriere.
Originaler Startabruf vollständig erfolgreich:15 GETs/4551ms/200/00000,
private Abschlussdiagnose ohne Fehler; Browserbericht vom Nutzer bestätigt.
Tatsächliche Cross/Hedge/10×-Einstellungen benötigen separate
Demo-Konfigurationsvorbereitung für isoliert/one-way/2×.
Normaler Konto-Sync und originale Schutzgrenzen bleiben erhalten.

Tests: tatsächliche private Registry/Outbox, reale AEAD mit synthetischen
Keys sowie mocked native Replies/Approvalconsumer/Accountguard. Native
Orderverbindung oder tatsächliche Freigabe wird damit nicht behauptet.
149 gepinnte Fälle grün, einschließlich echter Kindprozessabbrüche,
Registry-/Outboxrestore, once-before-send, ACK-/Revocationfehler, reiner
GET-Teilfillabnahme und der unvollständigen Vorschau. Finale gepinnte
Executorverpackung und paketierter Offlineimport ebenfalls grün; Cockpitcode
unverändert, kein weiterer Frontendbuild nötig.
