# Operativer einzelner BTC-Market-Demotest

PR114/main563d49c ist verifiziert. Der Nutzer verlangt den Start des
genehmigten kleinen Demotests. Drei eigene Next-/mTLS-POSTs verbinden
Vorbereitung, genau einmaligen Versand und lesenden Statusabgleich.
Die Installation wird nur durch die beiden expliziten Markettestflags
und `compose.demo-market-test.yaml` aktiviert; Standardinstallationen
behalten ihre bisherigen Routen.

Vorbereitung und Status haben eigene kurze HMAC-Domains. Der Versand
verwendet den bereits geprüften exakten Market-Consentvertrag. Tatsächliche
Originalsitzung, Same-origin/CSRF, aktueller API-Actor/Owner-Trader und
aktive Demometadaten werden im BFF vor und nach allen Awaitgrenzen
geprüft. Private Identitätsdateien/Keys/TLS behalten ihre ursprünglichen
Pfad-/UID-/Inode-/Fingerprint-/Zeitprüfungen. Kein Token oder Brokerkey
wird an den Browser zurückgegeben. Ein bestehender Dashboard-Login ist
deshalb für den Start erforderlich; Chatbestätigung wird nicht in einen
OIDC-Kontext oder eine neue Session umgewandelt.

Der interne native Quelladapter teilt den ursprünglichen Guardpfad mit
dem Kontoleser. Eigenständige Marketzweckprüfung erfolgt davor, ohne
Lese- oder Keytokenkonvertierung. Die Quelle enthält alle11 festen GETs,
UID/Parent/Rechte/IP, aktuelle Trading-Snapshots/AEAD, vollständige
Positionen und fünf Pendingfamilien, BTC-Profil und zwei öffentliche
Markt-GETs. Maximal3 Worker/110ms-Startabstände und5s-Quellen/Kohorte
bleiben erhalten. Die Quelle wird mit Originalzeit vor dem Versand erneut
validiert, auch nach dem abschließenden Transportabstand; eine verspätete
Quelle darf keinen POST senden. Der erste source-only GET-Abgleich nutzt
den autorisierten verschlüsselten Key; der dauerhafte Consentverbrauch
erfolgt vor der POST-gebundenen Dispatcherlease.

Private persistente Registry/Outbox/Consumer unter
`/var/lib/investalo-demo-market-test` sind fest installiert und gehören
UID10003. Originale0700-Verzeichnisse, create-only0600-Manifest/Journal/
Marker und fsync/readback bleiben verbindlich. Unvollständiger Bootstrap
wird erhalten und nicht automatisch repariert. Die erste Vorbereitung
reserviert die ursprüngliche Bindung; maximal16 Vorbereitungen. Sobald
ein Test versucht wurde, gibt es keinen weiteren neuen Test-POST.

Die Oberfläche zeigt Menge und Margin vor dem separaten Sendebutton.
Bei Timeout bleibt ausschließlich Statusprüfung möglich; Backendjournal
und Consumer verhindern Wiederholung auch über Tabs und Neustarts.
`latest` liest nur den einen bereits versuchten, dauerhaft gespeicherten
Testcommand desselben Accounts. Es erlaubt keinen frei gewählten nativen
Auftrag. ACK ist keine Ausführung. Tatsächlicher Fillpreis/Menge, gemeldete
Ordergebühr und Positionsabgleich werden getrennt dargestellt; unbekannte
Kosten bleiben unbekannt. Automatische Basket-/Echtgeldausführung und
automatisches Schließen sind nicht Bestandteil dieses Schritts.

Abnahme2026-11-23:134 betroffene gepinnte Pythonfälle,72 gepinnte Nodefälle
und volle Cockpit-Typprüfung grün. Eigene echte ASGI-/mTLS-Kette
Prepare→Submit→Observe mit realen Quotenabständen, tatsächliche private
Dateien/AEAD/Restore und verlorenes ACK geprüft; Actor, DB-Port und
Brokerantworten dabei synthetisch. Bestehende private Identität, Runtime,
Kontoleser und Consent-/Dispatchregressionen geprüft. Gepinnte Produktions-
builds und anschließender autorisierter Rollout werden separat belegt.

Rollout erhält Public/Paper/Demo-Trading/Admin-Mail/Konto-Sync-Overlays.
Nur Cockpit und eigener Executor werden erneuert. Originalbilder,
numerische Keyzustände und Dienst-IDs werden vor und nach der Änderung
privat abgelegt. Der Market-Statusdiagnosepfad enthält nur feste Stage,
Laufzeit, Error-Klasse und native numerische Codes; keine Keys/UIDs/
Anmeldedaten oder native Orderdaten.

Die tatsächliche private Konto-/Orderabnahme erfolgt anschließend über
die ursprüngliche angemeldete Dashboard-Sitzung. Eine erfolgreiche
synthetische Abnahme oder ein gesundes Deployment beweist keine echte
Bitget-Ausführung.

Autorisierter Rollout2026-11-23 abgeschlossen, Code199b1fc. Beide gepinnten
Images geprüft, tatsächlicher Paket-/Sourcehash des Executors verifiziert.
Nur Cockpit und Demo-Executor erneuert; fünf andere Dienst-IDs unverändert.
Originale Images und numerische Vorher-/Nachherbelege liegen privat unter
`infra/local/demo-market-test/rollout-*`. Alle bisherigen fünf Overlays
sowie der neue Markettestoverlay sind aktiv. Beide Testflags1, Executor
readonly/UID10003/kein Hostport/Logging none, keine Restarts; Cockpit gesund.
Demo-Key weiterhin active/revision1/storage1. Öffentliches TLS200,
anonyme Konto-/Marketvorschau und alle drei neuen POSTs401, tatsächliches
privates mTLS405 geprüft. Kein Brokerauftrag durch den Rollout.

Der Nutzer wurde gebeten, die Vorbereitung und den einzelnen Versand aus
seiner ursprünglichen Dashboard-Sitzung zu starten und anschließend den
Status zu lesen. Tatsächliche private Broker-/Fillabnahme ist bis zu
diesem Originalaufruf offen. Der Rollout ist nicht mit einer Fillbestätigung
gleichzusetzen.

Nach PR115/main3ae310e meldet der erste Nutzeraufruf einen Fehler. Die
private Marketdiagnose fehlt, alle drei Zustandsverzeichnisse sind leer,
Journalzählung0. Der letzte originale Vorschauabruf ist erfolgreich:
11GETs/3641ms/native200/00000. Somit wurde kein Orderversand begonnen.

Ursache im tatsächlich installierten Next16.4.5: `attachRequestMeta`
erzeugt die Request-URL aus dem internen Listenerhostname und Port,
auch hinter dem öffentlichen Caddy-Proxy. Orderroute und Consentsigner
verglichen diesen internen URL-Origin fälschlich mit dem öffentlichen
Cockpit-Origin. Beide verwenden nun die feste Browser-Originprüfung
mit Same-origin und CSRF sowie den exakten Pfad ohne Query/Fragment.
Session-/Actor-/Metadatenguards bleiben erhalten; der signierte Origin
bleibt ausschließlich `https://cockpit.investalo.de`.
Ein Regressionstest reproduziert503 vor der Korrektur und prüft danach
Vorbereitung, Versand und Status unter der internen Proxy-URL einschließlich
Ablehnung gefälschter Origin-/CSRF-/Fetch-Site-Header.73 betroffene gepinnte
Nodefälle und vollständige Typprüfung grün. Finaler Produktionsbuild
mit768MiB Heap abgeschlossen; Next-Typprüfung23,5s, keine parallele
schwere Prüfung. Der vorherige512MiB-Build mit parallel gestarteter
Typprüfung blieb94min in seiner Typprüfung und meldete noch den bereits
korrigierten Testtyp. Künftige Builds auf dem kleinen Host sequenziell.

Proxy-Fix861091d im bestehenden Demo-Testauftrag live geschaltet:
nur Cockpit erneuert, sechs andere Dienst-IDs und Demo-Key active1/1
unverändert. Alle sechs Overlays erhalten. TLS200, alle drei anonymen
Order-POSTs401 und tatsächliches privates mTLS405 geprüft.
Private Vorher-/Nachher-/Rollbackbelege unter `rollout-*` erhalten.
Alle Testverzeichnisse weiterhin leer; keine Order durch Fehlversuch
oder Deployment. PR116 erstellt. Originale Dashboard-Vorbereitung
erneut angefragt; native Fillabnahme weiterhin offen.

## Erste tatsächliche Eröffnungsabnahme

Am2026-11-24 bestätigt der Nutzer nach Merge von PR116/mainc336f86
die originale Cockpit-Vorbereitung, den einmaligen Versand und den
Status-/Positionsabgleich. Bitget-Screenshot zeigt dieselbe Position:
BTCUSDT Long,0,0003BTC,2× isoliert, Ø61.425,7USDT.
Der bestätigte Positionswert beträgt18,42771USDT; die gemeldete
Ordergebühr bleibt mit nativem Vorzeichen−0,01105662USDT erhalten.
Der Positionsabgleich im Cockpit ist bestätigt.

Unabhängige lesende Kontrolle des vorhandenen privaten Journals:
kanonische Hashkette und aktueller Checkpoint stimmen überein, Revision4,
genau prepare1/dispatch1/ack1/observation1 und ein verbrauchter Consent.
Gespeicherte Beobachtung `filled`, Menge, Durchschnittspreis und Gebühr
stimmen mit dem Nutzerbericht überein. Letzte private Diagnose:
`market_observe/completed`,2132ms, HTTP200/native00000, kein Fehler.
Dieser Audit sendet keine Brokeranfrage und verändert weder Journal
noch Dienste. Die Eröffnung des einzelnen Demo-Testauftrags ist
damit tatsächlich abgenommen.

Als Nächstes wird genau diese bestätigte Testposition per Reduce-only-
Marketorder geschlossen. Dafür ist ein eigener Abschlussablauf nötig:
frische Originalposition und Eigentums-/Mengenabgleich, separate
Dashboardbestätigung, einmaliger persistenter Versand, danach echte
Nullposition sowie Abschlussgebühren und Kontostand prüfen.
Der aktuelle Eröffnungsablauf wird dafür nicht wieder freigeschaltet.
Die operativen Signale/Nachkäufe/Exits für H1-Demobaskets folgen nach
diesem vollständigen Eröffnungs-/Abschlusstest.
