# Operativer Demo-Key-Zugang

Die vorhandene Seite `/security/credentials/demo-trading` ist jetzt mit dem
privaten Handelskey-Executor verbunden. Der Benutzer gibt API-Key, Secret und
Passphrase ein, bestätigt den Passkey und anschließend die Einrichtung.
Der Executor liest einmal fest Bitgets Classic-Kontoinfo mit `paptrading: 1`,
prüft UID/Parent/Rechte und speichert über den vorhandenen019/018-Pfad.
Die Einrichtung startet keine Orders.

## Aktueller Betrieb

Der anschließende [Demo-Konto-Sync](bitget-demo-account-sync.md) ergänzt
eine getrennte lesende Autorisierung und Anzeige im Dashboard. Er verwendet
den aktiven verschlüsselten Key; die Passkey-Einrichtung bleibt unverändert.
Das zusätzliche Sync-Overlay wird separat freigeschaltet.

2026-11-21: Der erste tatsächliche Demo-Handelszugang ist **aktiv, Revision1,
Stand1**. Rechte `coow/cpow/stow`, native UID und Parent stimmen mit der
privaten Konfiguration überein. Native Prüfung HTTP200/00000 accepted;
verschlüsselter Datensatz vorhanden und sein entsprechender019-Abschlussbeleg
ist completed. Benutzer bestätigt dieselbe erfolgreiche Dashboardmeldung.
Die sechs vorherigen fehlgeschlagenen Belege bleiben unverändert erhalten.
Private Statusquittung: `infra/local/demo-trading-runtime/registration-active.json`.
Keine Entschlüsselung für die Statusprüfung und keine Orders ausgeführt.

Zwei Einrichtungsursachen sind behoben: Das Positionsrecht heißt bei Bitget
**Futures → Holdings**; benötigt werden **Futures → Orders**, **Futures →
Holdings**, **Spot → Trade**, jeweils Read/Write, ohne **Margin → Trade**.
Außerdem liefert Bitget eine eigene native Demo-UID; die vom Nutzer bestätigte
angezeigte Konto-UID erscheint als deren Parent. In der Vorbereitung war
stattdessen die angezeigte UID mit parent0 eingetragen.

Ein frischer streng geprüfter nativer Beleg verknüpfte den Demo-Parent exakt
mit der bestätigten Konto-UID und demselben Actor/Tenant/Konto. Eigene
Kontoverbindung und Ziel-UID waren noch unbesetzt; ursprünglicher Versuch
nachweislich failed. Operator sicherte die Originaldatei und änderte nur
`broker_uid`/`parent_uid` im privaten Manifest. Backup, native Evidenz und
Applybeleg liegen unter dem ignorierten `identity-corrections`-Verzeichnis.
Signing/KEK/TLS und DB-/Benutzer-/Kontobindung blieben erhalten. Nur Executor
gestoppt/neu gestartet; tatsächliches privates mTLS405 und gesunde API/Cockpit
mit restarts0 geprüft. Kein automatischer Rebind oder alter Command wiederholt;
der Nutzer erteilte eine neue Passkeyfreigabe für die erfolgreiche Registrierung.
Dieser Schritt änderte keinen Runtimecode oder Migrationen.

PR97 ist gemerged; der Nutzer hat den öffentlichen Rollout ausdrücklich
freigegeben. Frisches privates Backup, Migrationen013–019 und exakte
Kontobindung sind durchgeführt. API/Cockpit sind gesund, der eigene Executor
antwortet über seine tatsächliche private mTLS-Verbindung. Paper-Anzeige und
vorhandene öffentliche Netze bleiben erhalten.

Öffentliche Seite: HTTPS200 bei gültigem TLS. Der tatsächliche Next-Eingang
liefert ohne Anmeldung401 statt der bisherigen Runtime-Sperre503. Alle sechs
Demo-API-Endpunkte wurden über tatsächliches HTTPS auf Anmeldesperre geprüft;
die öffentliche Passkey-Origin stimmt. Private Belege liegen unter dem
ignorierten `infra/local/demo-trading-runtime/rollout-active.json`.

## Verlauf der Einrichtungsdiagnose

SMTP/E-Mail-Bestätigung und erstes Ticket sind durchgeführt,
der Nutzer bestätigt erfolgreiche Passkeyregistrierung. Vier tatsächliche
Registrierungsversuche endeten2026-11-21 als `failed`; für genau sein Konto
existiert keine gespeicherte Verbindung. Keine Orders.

Die bisherige native Prüfung gab nur einen generischen Fehler zurück.
Public HTTPS/Bitget-Zeit aus dem Executor funktionieren (200,132ms Zeitdelta).
Eine eigene Diagnose erfasst ausschließlich festen Prüfschritt/lokalen
Fehlerenum/numerischen HTTP-Status und fünfstelligen Providercode, keine
Nachricht/UID/Antwort/Headers/Zugangsdaten. Neuer tatsächlicher Versuch:
HTTP200/Code00000, anschließend `identity/permission_rejected`. Bitget nimmt
die API-Daten an; die eigene Rechteprüfung lehnt die Rückmeldung ab.
Ergänzte Diagnose nennt nur endliche bekannte Rechte, fehlende Pflichtrechte,
Anzahl unbekannter Rechte und UID/Parent-Matchbooleans; unbekannte Werte
bleiben verborgen. Keine Änderung der Rechtepolicy. Opt-in Callback, readonly Runtime
mit eigener0600-Datei `/tmp/demo-trading-native-diagnostic.json` im flüchtigen
privaten Tmpfs. Sie ist keine Autorisierung oder Ausführungsbestätigung;
verbindlich bleibt der unveränderte Completionledger.
Callback-/Dateifehler erlauben keine Fortsetzung oder Wiederholung.

Konkrete Rechte: `coow/cpow/stow` sind vorhanden, zusätzlich `smow`
(Margin-Handel) ist außerhalb des freigegebenen Profils. UID- und
Parent-Match sind ebenfalls false. Es wird keine Kontozuordnung automatisch
übernommen. Ein separates privates0600-Tmpfs-File
`/tmp/demo-trading-native-identity.json` hält ausschließlich streng geparste,
zeitlich frische native Identität nach bestandener Rechteprüfung für den
Operatorabgleich. Kein Key/Secret/Passphrase; `registration_authorized=false`.
37 gezielte gepinnte Offlinefälle und Executorbuild bestanden. Nur der
private Executor wurde aktualisiert; keine Logs/Hostports, bestehende
API/Cockpit gesund und Demo-Start ohne Anmeldung401/TLS gültig.
Ursprüngliches Image privat in `native-diagnostics-before.json` erhalten.
Ein neuer expliziter Dashboardversuch durch den Nutzer ist für die konkrete
Diagnose erforderlich: vorherige Bodies/Keys bleiben nicht erhalten,
verbrauchte Commands/fehlgeschlagene Auditbelege werden niemals zurückgesetzt.

Der Nutzer hatte die Arbeit vertagt und anschließend einen neuen Key
angelegt: ausschließlich im Demo-Modus, Futures-Orders/Futures-Positionen
und Spot-Handel Read/Write, Margin-Handel und weitere Schreibrechte aus.
API-Key/Secret/Passphrase nur im Dashboard eingeben. Danach native Demo-UID/
Parent gegen die bisherige private Zuordnung abgleichen und gegebenenfalls
die oben belegte Setupkorrektur durchführen.

Nach Fortsetzung ist PR102/20e3885 gemerged. Der neue eingeschränkte Key
liefert `coow/stow`; fünfter Versuch als failed abgeschlossen, keine
gespeicherte Verbindung. `cpow` fehlt. Bitget nennt die benötigte Auswahl
**Futures → Holdings**; die anderen beiden sind **Futures → Orders** und
**Spot → Trade**, jeweils Read/Write. **Margin → Trade** bleibt aus.
„Positions“ war eine ungenaue Bezeichnung für Holdings. Nutzer richtete diese
drei Rechte ein; danach native Demo-UID/Parentzuordnung wie oben korrigiert.
Hochgeladene Screenshots sind von Git und Docker-Buildkontext ausgeschlossen.

Der Nutzer hat seine UID privat angegeben und berichtet, dass sein Demo-Key
keine IP-Bindung erlaubt. Dafür gibt es die ausdrücklich installierte Variante
`unavailable_in_demo`: nur fehlende/leere native Whitelist wird akzeptiert.
Eine spätere vorhandene Whitelist gilt als Konfigurationsänderung. Der normale
`single_ip`-Pfad bleibt streng. Die Herkunft bleibt die bestätigte Erstellung
im Demo-Modus; der Header allein zertifiziert sie nicht.
[Bitget-Dokumentation](https://www.bitget.com/docs/classic/demo-trading/rest-api).
Die Quelle bestätigt Demo-Key und Header; die fehlende IP-Option ist eine
Nutzerangabe. Dieser Pfad übernimmt keine Lockerung für Live oder alte Readprofile.

## Private Einrichtung

`setup-demo-trading-runtime.py --broker-uid … --created-in-demo-mode
--demo-without-ip-binding` erzeugt einmalig unter dem ignorierten
`infra/local/demo-trading-runtime`:

`--broker-uid` bezeichnet die native Demo-UID aus der tatsächlichen
API-Identität. `--parent-uid` muss zu deren tatsächlichem Parent passen;
die angezeigte Konto-UID darf nicht ungeprüft als native Demo-UID übernommen
werden. Eine Korrektur erfordert native Evidenz, bestätigten Eigentümerbezug,
unbesetztes Konto/Ziel-UID, Originalbackup und neuen Benutzer-Versuch.

- Browseridentität UID10002 mit eigenen Signing-/mTLS-Dateien und privater
  Konfiguration für genau den vorhandenen öffentlichen Owner.
- Executoridentität UID10003 mit eigenem KEK, DB-Passwort, TLS und exakter
  Konto-/UID-Zuordnung. Keine Brokerkeys in Dateien oder Environment.
- Separate private CA/Erneuerungsdateien. Originaldateien bleiben erhalten;
  keine automatische Rotation oder Übernahme eines vorhandenen Setups.

Die konkreten Dateien sind bereits vorbereitet. Die Runtime lädt sie unter
der Dienst-UID; ein bloßer Cockpit-Schalter genügt nicht. Next-Routen teilen
einen prozessweiten, begrenzten Ablaufstore. Neustart verliert nur flüchtige
Handles; durable019 verhindert Wiederholung. Änderungen am Manifest sperren
die installierte Runtime, TLS/Signing werden erneut geprüft.

Die native Prüfung erhält bekannte erlaubte Leserechte zusätzlich zu
`coow/cpow/stow`, verbietet weitere Schreib-/Transfer-/Withdraw-/UTA-Rechte
und prüft fünf Sekunden Aktualität. Ein Prozess/UID, lokaler Mutex und
Mindestintervall, keine Retries. Mehrere Executorinstanzen und eine global
verifizierte UID-Quota sind damit nicht freigegeben.

## Konkreter Rollout nach Merge und Freigabe

Vor dem inzwischen genehmigten Rollout hatten normale Dienste001–012.
013–019 wurden zuvor gegen die vorhandenen Daten erfolgreich getestet und
vollständig zurückgerollt. Reproduzierbarer Rollout mit frischem privatem Backup:

```bash
python3 infra/scripts/setup-demo-trading-runtime.py --backup-database
bash infra/scripts/compose.sh run --rm --no-deps -T migrate
python3 infra/scripts/setup-demo-trading-runtime.py --bind-account
bash infra/scripts/compose.sh --file infra/compose.public-preview.yaml \
  --env-file infra/local/paper_preview.env --file infra/compose.paper-preview.yaml \
  --file infra/compose.demo-trading-runtime.yaml up -d --no-deps \
  demo-trading-executor api cockpit
```

`--bind-account` verlangt sämtliche Originalchecksums, bindet einen eigenen
minimalen LOGIN und erstellt genau ein Demo-Konto im Status `ready`.
Die PostgreSQL-HBA-Regel erlaubt ausschließlich diesem LOGIN SCRAM/TLS auf
`investalo`; nach Änderung `pg_reload_conf()` ausführen und die geladene Regel prüfen.
`API_PASSKEY_ORIGIN` muss zum öffentlichen Cockpit passen; der explizite
Demo-Overlay setzt sie für den bestehenden Purpose-Prüfer.
Vorhandene fremde Bindungen werden abgelehnt. API-Schalter sind ausschließlich
im expliziten Overlay gesetzt. Der Executor hat keinen Hostport, kein Logging,
kein PG-Environment, readonly/cap-drop und mTLS mit dem SHA des **DER**-Peers.
Nur er erhält Broker-Egress; der Transport erlaubt nur seinen festen HTTPS-GET.

Nach Rollout: Dienstzustand und geschützte Seite prüfen, dann der Nutzer seinen
Key im Dashboard. Erst diese Registrierung kann native UID/Rechte belegen.
Bei unbestätigtem Ergebnis den Status neu lesen, keine automatische Wiederholung.
Native Konto-/Position-/Order-/Kostenabnahme und Demo-Dispatcher folgen danach;
es gibt bisher keine Aussage über echte Brokerfills oder Handelsfreigabe.

## Prüfung

81 gepinnte Nodefälle für Runtime, Dashboard, HTTP und Browserablauf grün;
10 neue operative Pythonfälle/21 Unterfälle grün.37 bestehende tatsächliche
Executor-/PG-/mTLS-Fälle zusätzlich grün. Typecheck und gepinnter Cockpit-/
Executorbuild bestanden. Private Browserdateien unter tatsächlicher UID10002
ohne API-/Brokerzugriff geladen. Zusammengesetzte Rolloutcompose gültig.
Die native Antwort in Tests ist synthetisch; keine echten API-Keys aufgenommen.
Die Betriebskonfiguration benötigte zusätzlich eine exakte HBA-Zugangsregel und
`API_PASSKEY_ORIGIN`; beide sind im laufenden Dienst geprüft.
