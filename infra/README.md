# Lokale Compose-Entwicklung

Q31 bestätigt den Implementierungsstart. Diese Konfiguration ist für lokale
Testnutzer vorgesehen. Ausschließlich Caddy veröffentlicht **127.0.0.1:8443**.
PostgreSQL, IdP und Anwendungen veröffentlichen keine Hostports.
Der öffentliche Privatpilot benötigt eine eigene geprüfte Konfiguration und
Rolloutfreigabe.

Vom Repositoryroot auf dem überprüften Ubuntu-26.04-amd64-Host:

```sh
# Einmalig, falls Docker noch fehlt; installiert ausschließlich genaue Pins.
sudo bash infra/scripts/install-docker.sh
# Erst bei absichtlichem Runtimeupdate: python3 infra/scripts/resolve-images.py
sudo python3 infra/scripts/bootstrap-local.py
sudo bash infra/scripts/compose.sh --profile tools --profile checks --profile research build api migrate api-checks research
sudo bash infra/scripts/compose.sh build cockpit
sudo bash infra/scripts/compose.sh up -d postgres authelia
# Eigene Researchrolle und ausschließlich für Fixtures verwendete Testrolle.
sudo python3 infra/scripts/provision-local-research.py
sudo python3 infra/scripts/provision-local-research.py --test-role
sudo bash infra/scripts/compose.sh --profile tools run --rm migrate
# Nur generierten .invalid-Testnutzer samt TOTP und Tenant anlegen.
sudo python3 infra/scripts/provision-local-test.py
sudo python3 infra/scripts/provision-local-research.py --bind-local-test
sudo bash infra/scripts/compose.sh up -d api cockpit caddy
```

Builds auf diesem kleinen Host nacheinander ausführen. Migrationen haben
Prüfsummen und laufen mit einer eigenen Rolle. Runtime und BFF erhalten diese
Rolle nicht. Das Provisionierungsskript akzeptiert ausschließlich das unveränderte
lokale Testnutzerformat und überschreibt keine Faktoren.

Die Image-Digests in `images.env` sind committed. Bootstrap erzeugt zufällige
Testcredentials, eigene CA und 90-Tage-Servicezertifikate unter dem ignorierten
`infra/local/`. Eine vorhandene vollständige Initialisierung bleibt erhalten;
eine teilweise Initialisierung führt zum Abbruch. Kein automatisches Löschen,
Überschreiben oder Rotieren vorhandener Daten. Nur konkrete Secretdateien
werden in die jeweiligen Dienste gemountet. Der gesamte lokale Ordner bleibt
für Hostadministratoren geschützt; er darf niemals als Ganzes gemountet werden.

Für den Browser beide Testnamen lokal auf `127.0.0.1` auflösen und die öffentliche
CA aus `infra/local/local_ca_cert` im Entwicklungsbrowser vertrauen. Bei Zugriff
von einem anderen Rechner kann der lokale Port über SSH weitergeleitet werden.
Keine Zertifikatsprüfung abschalten. Testzugang steht ausschließlich in der
geschützten `infra/local/pilot-access.txt`; der lokale Testfaktor in
`infra/local/pilot-totp.txt`. Die CLI-Provisionierung ist ein Testshortcut,
kein Nachweis der normalen MFA-Erstregistrierung oder des Recoveryablaufs.
File-Notifier und `.invalid`-Adresse
senden keine externe Mail; dies ist kein Recovery-/SMTP-Pilotnachweis.

TLS-Discovery ohne Änderung der Hostauflösung prüfen:

```sh
curl --noproxy '*' --resolve auth.cockpit.local.test:8443:127.0.0.1 \
  --cacert infra/local/local_ca_cert \
  https://auth.cockpit.local.test:8443/.well-known/openid-configuration
```

Alle Laufzeitcontainer starten mit expliziter Nonroot-UID, ohne Linux-
Capabilities oder Docker-Socket und mit begrenztem RAM. PostgreSQL verwendet
TLS/SCRAM und separate Migration-, Runtime- und IdP-Rollen. Die Runtime erhält
keine DDL-/Superuserrechte; der IdP migriert ausschließlich seine eigene DB.
Anwendungsnetze sind intern; allein Caddy besitzt zusätzlich ein Bridge-Netz
für den veröffentlichten Loopbackport. Dateien sind
dienstbezogen berechtigt, Compose-Dateisecrets ersetzen keine Hostverschlüsselung.

`compose.sh stop` stoppt die lokale Umgebung und behält ihre Daten. Kein
`down --volumes` oder Löschen des lokalen Ordners als Routine verwenden.
Backup/Restore, realer SMTP, administratives Recovery und MT5-Demobridge bleiben
eigene Abnahmen. Runtimequellen: [runtime-pins.md](../docs/runtime-pins.md).

## Öffentliche Forschungsdaten und Offlineworker

Ein Snapshot muss vor Jobannahme importiert sein. Der folgende lokale
Funktionsnachweis verwendet 90 Tage BTC-H4, keine Kontocredentials. Datumsgrenzen
müssen bereits geschlossene H4-Intervalle sein; vorhandene Ausgaben werden nicht
überschrieben. Für spätere Testläufe das Intervall und einen neuen Dateinamen
bewusst wählen.

```sh
PYTHONPATH=packages/marketdata/src:packages/trading/src python3 -m investalo_marketdata \
  bitget --symbol BTC/USDT --start 2026-08-09T08:00:00Z \
  --end 2026-11-07T08:00:00Z --output /tmp/btc-research.json
sudo python3 infra/scripts/stage-research-snapshot.py \
  --file /tmp/btc-research.json --name btc-research.json --import-local
sudo bash infra/scripts/compose.sh --profile research up -d research
sudo python3 tests/infra/check_local_auth.py
```

Das geprüfte Intervall enthält 540 lückenlose Kerzen. Vollständigkeit bezieht sich
nur auf dieses Intervall, nicht auf das Dreijahresziel. Jedes Ergebnis bleibt
**nicht wirtschaftlich validiert**; der unabhängige Holdout ist nicht ausgewertet.
Gebühren/Spread/Slippage sind sichtbare Modellannahmen, noch keine kalibrierten
Brokerkosten. CSV und synthetische Fixtures: [marketdata](../packages/marketdata/README.md).
Synthetische Daten dürfen ausschließlich als `--purpose test` importiert werden.

Der Staginghelper validiert und kopiert create-only in den ignorierten
`infra/local/research-data/`-Ordner. Nur der Migrationscontainer erhält ihn
schreibgeschützt. Importidentität, Tenant und Zweck sind ausdrücklich festgelegt;
gleicher Datenhash mit geändertem vollständigem Snapshot wird abgewiesen.
Kein Import erfolgt automatisch durch Cockpit oder Worker.

Research läuft als UID10005 mit 192 MiB/0,3 CPU, ausschließlich im internen
DB-Netz. Eine eigene LOGIN-Rolle ist über `SESSION_USER` fest einem Tenant
zugeordnet; keine API-/BFF-/IdP-/Brokersecrets. Snapshots und Jobinputs sind
unveränderlich, Claims besitzen Attempttoken, Lease und Heartbeat. Alte
Jobabschlüsse werden abgewiesen. Holdouts sind vom gewöhnlichen Researchpfad
ausgeschlossen. Details: [Worker](../services/workers/README.md).

Für einen anderen ausdrücklich autorisierten Tenant:
`sudo python3 infra/scripts/provision-local-research.py --bind-tenant UUID`.
Eine vorhandene andere Bindung wird nicht überschrieben. Eine Researchrolle
ist keine allgemeine Mehrtenant-Workeridentität.

Verifikation und Betrieb:

```sh
sudo bash infra/scripts/compose.sh --profile research ps
sudo bash infra/scripts/compose.sh --profile checks run --rm api-checks
PYTHONPATH=packages/trading/src python3 -m unittest discover -s tests/trading
PYTHONPATH=packages/marketdata/src:packages/trading/src python3 -m unittest discover -s tests/marketdata
python3 -m unittest discover -s tests/infra -p 'test_*.py'
npm --prefix apps/cockpit test
npm --prefix apps/cockpit run typecheck
```

Der isolierte Credentialkern hat einen eigenen Hashlock und ein eigenes
Checkimage; API-/Researchlocks bleiben davon unabhängig:

```sh
sudo bash infra/scripts/compose.sh --profile checks build credentials-checks
sudo bash infra/scripts/compose.sh --profile checks run --rm --no-deps credentials-checks
```

Das Checkprofil läuft als UID 10006, ohne Netzwerk, Secrets oder Diensteabhängigkeit,
mit schreibgeschütztem Rootdateisystem und ohne Linuxcapabilities. 20 echte
AES-GCM-Tests mit erfundenen Schlüsseln bestanden. Es stellt keinen Vaultdienst
bereit; tatsächliche Nutzerkeys werden noch nicht angenommen.

Die persistente Speicherung hat ein separates administratives Prüfprofil.
Vorher müssen PostgreSQL und die Research-Testrolle wie oben eingerichtet sein.
Bei einer vorhandenen Entwicklungsdatenbank vor003 zunächst den Helper ausführen:
Er legt die neue Credentialgruppe und drei ausschließlich für die Fixture-DB
zugelassene Testlogins an. Neuinitialisierung legt die NOLOGIN-Gruppe bereits an.

```sh
sudo python3 infra/scripts/provision-local-credentials-tests.py
# HBA-Datei ist gemountet; vorhandenen PostgreSQL-Prozess neu laden.
sudo bash infra/scripts/compose.sh exec -T postgres psql --username investalo_admin \
  --dbname postgres --no-psqlrc --command 'SELECT pg_reload_conf();'
sudo bash infra/scripts/compose.sh --profile tools build migrate
sudo bash infra/scripts/compose.sh --profile tools run --rm --no-deps \
  -e PGDATABASE=investalo_credentials_checks migrate
sudo bash infra/scripts/compose.sh --profile checks build credential-storage-checks
sudo bash infra/scripts/compose.sh --profile checks run --rm --no-deps credential-storage-checks
# Nach obigen Tests: gültige Fixturebindung für den Drift-Test vorhanden.
sudo python3 tests/infra/check_credentials_role_drift.py
```

Geprüft: 120 Tests im Storage-Checkcontainer: 19 Client-, 41 Onboarding-Offline-
und 60 echte PostgreSQL-Fälle (18 Store, 30 Actionautorisierung, 12 synthetische
Bitget-/AEAD-Abläufe). Einrichtung, Keywechsel und Widerruf, Replay, Ablauf
während Sperrwartezeiten/Probe/Write, geänderte Rechte und CAS sind abgedeckt.
Vier Helpertests und die Rollen-Driftprobe waren im vorigen Storecheckpoint grün.
Der Drift-Test weist erlaubten Ausgangszustand, Ablehnung von Delegationsrechten
und deren vollständigen Transaktionsrollback nach. Mit diesem Registrycheckpoint
sind001–006 in beiden lokalen Datenbanken angewendet und unveränderlich.
Bei vorhandener Entwicklung nach dem Credential-Gruppenhelper auch
`sudo bash infra/scripts/compose.sh --profile tools run --rm --no-deps migrate`
für die gewöhnliche Datenbank ausführen.005 ergänzt ausschließlich eine
autorisierte öffentliche Metadatenprojektion für den Runtime-LOGIN;
direkter Tabellen-/Credentialfunktionszugriff bleibt gesperrt.
293 API-/Worker-Tests und erneut alle120 Credentialprüfungen bestanden;
darunter67 tatsächliche Passkey-Registry-/API-Fälle nach006.

Das Prüfprofil läuft als UID10003 mit TLS im internen DB-Netz, ohne veröffentlichte
Ports und ohne Broker-/BFF-/IdP-/KEKsecrets. Es besitzt bewusst administrative
Migrationscredentials für Testfixtures; diese können auch die gewöhnliche
Entwicklungsdatenbank erreichen. Das Profil ist kein eingeschränkter
Betriebsdienst. Die drei Credential-Testlogins selbst dürfen nur in die
Fixture-DB. Generierte Testpasswörter behalten Modus0400 und bleiben ignoriert.
Entwicklungsschlüsseldateien werden ausschließlich im temporären Testverzeichnis
erzeugt; synthetische Assertions und gemockte Brokerantworten. Kein HTTP-Keyeingang,
echter BFF-MFA-Schrittflow oder Betriebsschlüsselprovider vorhanden.

Cockpitmeldungen zeigen fehlende Konten/Positionen ausdrücklich als leeren
Datenbestand. Backtestanforderungen frieren Dataset, Strategie und Kosten ein;
der Offlineworker speichert Nettoergebnisse und begrenzte Equitykurven.
Der HTTPS-Test prüft tatsächliche Ausführung und Darstellung eines importierten
öffentlichen BTC-Snapshots. Abweichender Pfad: `--snapshot-file PATH`.
Es gibt noch keine nutzbaren Brokerverbindungen.
Lokale BFF-Abmeldung löscht die Cockpitsitzung; die IdP-Sitzung bleibt bestehen.
Jeder neue Cockpitlogin erzwingt dennoch eine frische Anmeldung. Authelia kann
dabei den alten zweiten Faktor erhalten; dies ist keine frische sensitive
Actionfreigabe. Der erweiterte HTTPS-Test prüft diese Grenze und die gesperrten
Credentialrouten. Dauerhafte Passkeyregistry und lokales Browser-Enrollment
sind implementiert; Kontoänderungen bleiben gesperrt:
[Passkeyplan](../docs/passkey-step-up.md). Kein neuer OIDC-Callback registriert.
48 tatsächliche HTTPS-Prüfpunkte bestanden, einschließlich Enrollmentgrenzen;
alle sechs lokalen Dienste gesund. Der erfolgreiche vollständige Enrollment-
ablauf im BFF und die reale Browser-/Geräteabnahme stehen noch aus.

## Passkey-Enrollment und Widerruf

Nach006 und aktuellem API-/Cockpitbuild ist `/security/passkeys` der lokale
Enrollmentweg. Eine tatsächliche Browser-/Geräteabnahme steht noch aus.
Nur der Migrationsoperator stellt nach manuell geprüfter E-Mail-Bestätigung
ein Ticket aus; `--email-confirmed` attestiert diese Prüfung und versendet
keine Nachricht. Die Bestätigungsreferenz ist eine opake UUID ohne Mailinhalt.
Tenant-/Nutzer-ID und Auth-Epoch zuvor in geschütztem administrativem Kontext
prüfen. Keine Tickets in URLs, stdout, Logs oder Git übernehmen.

Beispiel mit bewusst gesetzten IDs/Epoch/Bestätigungsreferenz und einer neuen
privaten Ausgabeablage; das Ticket ist standardmäßig höchstens600 Sekunden
gültig. Der Ordner gehört dem Containeroperator und hat Modus0700, die CLI
erzeugt die Datei einmalig mit0600 und überschreibt keine vorhandene Datei.

```sh
sudo install -d -m 0700 -o 10003 -g 10003 /tmp/investalo-passkey-enrollment
sudo bash infra/scripts/compose.sh --profile tools run --rm --no-deps \
  --volume /tmp/investalo-passkey-enrollment:/passkey-output migrate \
  python -m investalo_api.passkey_admin issue \
  --tenant-id "$PASSKEY_TENANT_ID" --user-id "$PASSKEY_USER_ID" \
  --rp-id cockpit.local.test --auth-epoch "$PASSKEY_AUTH_EPOCH" \
  --ttl-seconds 600 --output-file /passkey-output/ticket.json \
  --email-confirmed --confirmation-reference "$PASSKEY_CONFIRMATION_ID"
```

Das geschützte Artefakt enthält den kurzlebigen Bearertoken; nur dessen Hash
liegt in der DB. Token kontrolliert dem bestätigten Nutzer übergeben, der ihn
im Enrollmentformular eingibt. Der committed Claim gilt höchstens120 Sekunden;
Fehler oder Abbruch erlauben keine Ticketwiederverwendung. Ein unbekannter
Commitausgang benötigt Abgleich vor einem neuen Versuch.

Administrativer Widerruf mit aktueller Registry-ID und erwarteter Version:

```sh
sudo bash infra/scripts/compose.sh --profile tools run --rm --no-deps migrate \
  python -m investalo_api.passkey_admin revoke \
  --passkey-id "$PASSKEY_ID" --expected-storage "$PASSKEY_STORAGE_VERSION" \
  --email-confirmed --confirmation-reference "$PASSKEY_CONFIRMATION_ID"
```

Widerruf erhöht die globale Nutzer-Auth-Epoch und setzt `reauth_after`;
alle Tenant-Sitzungen werden ungültig. Der terminale Registryeintrag bleibt
reserviert; Recovery/erneutes Enrollment ist noch nicht verfügbar.
Registrierung öffnet keine Brokerkeyeingabe oder sensitive Kontoaktion.
Pilot-RP `cockpit.investalo.de` erfordert später eigene Registrierung und
öffentliche Rolloutabnahme; lokale RP wird nicht automatisch übertragen.

Mit laufendem Researchprofil stoppt
`sudo bash infra/scripts/compose.sh --profile research stop` alle sechs Dienste
und behält Daten. Der Standardbefehl ohne Profil umfasst nur die Basisdienste.
