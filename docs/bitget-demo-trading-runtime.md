# Operativer Demo-Key-Zugang

Die vorhandene Seite `/security/credentials/demo-trading` ist jetzt mit dem
privaten Handelskey-Executor verbunden. Der Benutzer gibt API-Key, Secret und
Passphrase ein, bestätigt den Passkey und anschließend die Einrichtung.
Der Executor liest einmal fest Bitgets Classic-Kontoinfo mit `paptrading: 1`,
prüft UID/Parent/Rechte und speichert über den vorhandenen019/018-Pfad.
Die Einrichtung startet keine Orders.

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

Normale Dienste und Datenbank sind bisher unverändert. Sie haben001–012;
013–019 wurden gegen die vorhandenen Daten erfolgreich getestet und vollständig
zurückgerollt. Vor dem Rollout frisches privates Backup:

```bash
python3 infra/scripts/setup-demo-trading-runtime.py --backup-database
bash infra/scripts/compose.sh run --rm --no-deps -T migrate
python3 infra/scripts/setup-demo-trading-runtime.py --bind-account
bash infra/scripts/compose.sh --file infra/compose.public-preview.yaml \
  --file infra/compose.demo-trading-runtime.yaml up -d --no-deps \
  demo-trading-executor api cockpit
```

`--bind-account` verlangt sämtliche Originalchecksums, bindet einen eigenen
minimalen LOGIN und erstellt genau ein Demo-Konto im Status `ready`.
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
