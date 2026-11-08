# Lokale Compose-Entwicklung

Q31 bestätigt den Implementierungsstart. Diese Konfiguration ist für lokale
Testnutzer vorgesehen. Ausschließlich Caddy veröffentlicht **127.0.0.1:8443**.
PostgreSQL, IdP und Anwendungen veröffentlichen keine Hostports.
Der öffentliche Privatpilot benötigt eine eigene geprüfte Konfiguration und
Rolloutfreigabe.

**Aktiver Hostbetrieb:** Der Nutzer hat die öffentliche Entwicklungsvorschau
freigegeben. Beide Domains haben gültige Let’s-Encrypt-Zertifikate.
Bei Änderungen am laufenden Einstieg ausdrücklich
`--file infra/compose.public-preview.yaml` verwenden; die untenstehenden
Standardbefehle starten das lokale Profil. Der öffentliche Anwendungsablauf
ist mit `python3 tests/infra/check_local_auth.py --public-preview` geprüft
(48 Prüfpunkte). Identitätsprovisionierung, geschützte Testlogin-Dateien und Rückfall:
[HTTPS-Einstieg](../docs/https-entry.md).

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
und deren vollständigen Transaktionsrollback nach. Mit dem Aktionsnachweis007
sind001–007 in beiden lokalen Datenbanken angewendet und unveränderlich.
Bei vorhandener Entwicklung nach dem Credential-Gruppenhelper auch
`sudo bash infra/scripts/compose.sh --profile tools run --rm --no-deps migrate`
für die gewöhnliche Datenbank ausführen.005 ergänzt ausschließlich eine
autorisierte öffentliche Metadatenprojektion für den Runtime-LOGIN;
direkter Tabellen-/Credentialfunktionszugriff bleibt gesperrt.
461 API-/Worker-Tests und erneut alle120 Credentialprüfungen bestanden;
darunter67 tatsächliche Passkey-Registry-/API-Fälle nach006 und70 neue
tatsächliche Aktionsnachweis-PG-Fälle nach007. 143 Cockpitprüfungen, Typecheck
und gepinnte Containerbuilds ebenfalls grün.007 ist additiv in beiden DBs
angewendet; die laufenden Vorschaucontainer wurden dafür nicht neu erstellt.
[Interner Ablauf und Browsergates](../docs/passkey-action-proofs.md).

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
ablauf im BFF ist inzwischen synthetisch in IP-037 geprüft; die reale
Browser-/Geräteabnahme bleibt offen.

## Isolierte Passkey-Browserprüfung

IP-037 prüft vollständiges Enrollment und den zielgebundenen Nachweis007
über tatsächliches HTTPS/BFF/API/PostgreSQL mit synthetischen P256-Schlüsseln.
Voraussetzungen: vorhandenes lokales TLS-Fundament, provisionierte
`investalo_credentials_checks` mit001–007 und aktuelle API-/Cockpitimages.
Die additive Datei `compose.passkey-browser-checks.yaml` überschreibt keinen
Vorschaudienst und veröffentlicht keine Hostports. Das interne Testcockpit
aktiviert ausdrücklich `COCKPIT_PASSKEY_PROOF_PREVIEW=1`; Default und öffentliche
Vorschau lassen das Flag aus. Alle Ergebnisse bleiben `execution_enabled:false`.

Die Vorbereitung ist auf `/tmp/investalo-passkey-browser-state` festgelegt.
Sie erstellt eine geschützte Fixturemarkierung und drei eigene synthetische
Secrets. Root-/Sessionverzeichnisse gehören UID10002/10003, GID10010 mit2770.
Secretdateien haben0440 und ermöglichen keine Sitzungen oder Dienstassertions
der öffentlichen Vorschau. Abweichende Besitzer/Rechte und Symlinks werden
abgewiesen; keine automatische Reparatur vorhandener Zustände.
Alle privilegierten Pfadoperationen arbeiten über gehaltene Deskriptoren.

Builds nacheinander durchführen; bestehende Vorschaucontainer dabei nicht
neu erstellen. Bei fehlendem aktuellem API-Image zuerst den API-Build ausführen.

```sh
sudo python3 infra/scripts/prepare-passkey-browser-checks.py
sudo bash infra/scripts/compose.sh build cockpit
sudo bash infra/scripts/compose.sh --file infra/compose.passkey-browser-checks.yaml \
  --profile passkey-browser-checks build browser-proof-checks
sudo bash infra/scripts/compose.sh --file infra/compose.passkey-browser-checks.yaml \
  --profile passkey-browser-checks up -d --no-deps \
  browser-proof-api browser-proof-cockpit browser-proof-edge
sudo bash infra/scripts/compose.sh --file infra/compose.passkey-browser-checks.yaml \
  --profile passkey-browser-checks run --rm --no-deps -T browser-proof-checks
# Auf dem kleinen Host die beiden Testcockpits nacheinander betreiben.
sudo bash infra/scripts/compose.sh --file infra/compose.passkey-browser-checks.yaml \
  --profile passkey-browser-checks stop browser-proof-cockpit
sudo bash infra/scripts/compose.sh --file infra/compose.passkey-browser-checks.yaml \
  --profile passkey-browser-checks --profile passkey-browser-disabled-checks \
  up -d --no-deps browser-proof-cockpit-disabled
sudo bash infra/scripts/compose.sh --file infra/compose.passkey-browser-checks.yaml \
  --profile passkey-browser-checks --profile passkey-browser-disabled-checks \
  run --rm --no-deps -T browser-proof-checks \
  python /app/check_passkey_browser.py --disabled-only
sudo bash infra/scripts/compose.sh --file infra/compose.passkey-browser-checks.yaml \
  --profile passkey-browser-checks --profile passkey-browser-disabled-checks \
  stop browser-proof-api browser-proof-cockpit browser-proof-cockpit-disabled browser-proof-edge
```

Nur die benannten Prüfdienste stoppen; `compose down` würde das gemeinsame
Projekt einschließlich Vorschau treffen. Der Checkcontainer hat bewusst
Migrationscredentials für eigene Fixtures; er ist kein eingeschränkter
Betriebsdienst. Er prüft feste Fixture-DB und geschützte Ablage vor Schreibzugriff.
Synthetische Audit-/Faktor-/Proofzeilen bleiben erhalten; erzeugte Nutzer werden
nach Abschluss deaktiviert. Keine echten Nutzerkeys, Brokeraufrufe oder
E-Mail-Attestierung. `navigator.credentials` auf einem physischen Gerät und
öffentliche Aktivierung bleiben eigene Abnahmen.

Geprüft:265 Cockpittests, Typecheck/Build,90 aktivierte und9 deaktivierte
HTTPS/BFF/PG-Prüfpunkte sowie8 Vorbereitungstests. Die laufende öffentliche
Vorschau blieb unverändert und gesund. [Ablauf/Gates](../docs/passkey-browser-proof.md).

## Isolierter Passkey-Credential-Vertrag

IP-038 ergänzt einen getrennten TS-Signer/Python-Verifier mit ursprünglicher
OIDC-Zeit und frischer Passkey-/Freigabezeit. Der Zweckvertrag besitzt keinen
dauerhaften Aussteller/Consumer, keine HTTP-Anbindung und keine Kontoausführung.
Die Bestätigung der007-Prüfseite ist keine Schreibfreigabe.
[Vertrag/Gates](../docs/passkey-credential-assertions.md).

Das explizite Profil `credential-assertion-checks` verwendet das vorhandene
gepinnt gebaute Storage-Prüfimage, aber nur Offline-Onboardingtests
(77 in IP-038, inzwischen95 mit IP-039).
Es läuft als UID10003 mit schreibgeschütztem Dateisystem, ohne Netzwerk,
Secrets, Mounts, Ports oder DB-Abhängigkeiten. Die bestehenden Dienste/
Prüfprofile bleiben unverändert. Builds auf dem kleinen Host nacheinander:

```bash
sudo bash infra/scripts/compose.sh --profile credential-assertion-checks \
  build credential-assertion-checks
sudo bash infra/scripts/compose.sh --profile credential-assertion-checks \
  run --rm --no-deps -T credential-assertion-checks
```

Die sprachübergreifende Offlineprüfung benötigt die dokumentierten lokalen
Node-/Pythonversionen und die bestehenden installierten Cockpitabhängigkeiten/
Credential-Venv. Sie startet den echten TS-Signer mit ausschließlich
synthetischen Fixtures und prüft109 Vertragsfälle in Python:

```bash
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=services/credentials/src:packages/credentials/src:integrations/bitget/src \
packages/credentials/.venv/bin/python tests/infra/check_passkey_assertion_interop.py
```

Diese Prüfungen brauchen keine laufenden Dienste. Sie belegen keine
DB-Autorität, persistente Replayabwehr, physische Geräteabnahme oder Broker-
ausführung. Public-Overlay/Nachweisflag und Migrationen001–007 bleiben erhalten.
Geprüft:333 Cockpittests,77 Offline-Onboardingtests auch im gepinnten
Python3.14.10-Container,109 Interopprüfpunkte, Typecheck und gepinnter
Cockpitbuild; unabhängiger Review ohne Blocker. Öffentliche Dienste unverändert/
gesund und HTTPS200. Frühere461/120/99 Integrationsprüfungen nicht erneut ausgeführt.

## Dauerhafte Passkey-Credentialfreigabe

IP-039 ergänzt008 mit eigenem Zweck ab Vorbereitung, ausdrücklicher Zustimmung,
globalem Einmalverbrauch und erneuter aktueller Bindungsprüfung in einer
separaten finalen Transaktion. Der private Pythonclient verbindet den
IP-038-Verifier mit diesen Funktionen. Kein HTTP-/Broker-/Credentialexecutor;
öffentliche Vorschau und Nachweisflag bleiben unverändert.
[Ablauf und Grenzen](../docs/passkey-credential-authorizations.md).

008 wurde nach vollständig zurückgerollter DDL-/Runtime-Vorprüfung
ausschließlich in `investalo_credentials_checks` angewendet. Der Checksum ist
`9328008652ad697a306093301d9488fe3e0b184a3ffd8333f7beda5924712c57`.
Die laufende Entwicklung nutzt weiterhin investalo001–007. Nicht ohne eigene
Integration/Abnahme den Defaultmigrator oder `up` ausführen.

```bash
sudo bash infra/scripts/compose.sh --profile tools --profile checks \
  build migrate credential-storage-checks api-checks
sudo bash infra/scripts/compose.sh --profile tools run --rm --no-deps -T \
  -e PGDATABASE=investalo_credentials_checks migrate
sudo bash infra/scripts/compose.sh --profile checks run --rm --no-deps -T \
  credential-storage-checks
sudo bash infra/scripts/compose.sh --profile checks run --rm --no-deps -T \
  -e PGDATABASE=investalo_credentials_checks api-checks
```

Die IP-039-Abnahme umfasst19 Client-,95 Offline-Onboarding- und157 tatsächliche
PG-Fälle; davon97 neue008-Fälle. Nur synthetische Receipts, Keys und Fixtures.
SQL vertraut dem verpflichtenden privaten JWT-Verifier und BFF-WebAuthnverdict.
Der administrative Checkcontainer besitzt Fixture-/Migrationscredentials,
der spätere Betriebsdienst darf sie nicht erhalten. Diese Suiten nacheinander
ausführen: dedizierte Fixture-Rollenbindungen werden je Fall neu gesetzt.
Angewendete001–008 und terminale Audit-/Zweckzeilen bleiben unveränderlich.
Abnahme IP-039: alle271 Credentialtests und461 API-/Workertests bestanden;
gepinntes Migrate-/Credential-/API-Checkbuild und unabhängiger Review ohne
Blocker. Öffentliche sechs Dienste unverändert/gesund, reguläres TLS HTTPS200.

## Private Passkey-Credentialausführung

IP-040 ergänzt die [private Credentialausführung](../docs/passkey-credential-execution.md).
008-Consume committed vor Probe;008-Lock,003-Write und009-Abschluss in einer
separaten finalen Transaktion.009 wurde nach vollständig zurückgerollter
DDL-/echter Failure-Abschlussvorprüfung nur in `investalo_credentials_checks`
angewendet. Unveränderliche Prüfsumme:
`435d658458c6be7359ab19ad575421fb843c8756975710cc651eff41c4d62b75`.
Die obigen Migrate-/Prüfkommandos verwenden weiterhin ausschließlich diese
Fixture-DB; investalo bleibt001–007. Gepinnte Migrate-/Storage-/API-Checkbuilds
bestanden. Der neue Executor wird durch Tests mit synthetischen Keys/Antworten
aufgerufen; öffentliche Dienste/Flags bleiben unverändert.
IP-040: vollständige356 Credentialtests bestanden (19 Client,116 Offline,
221 tatsächliche PostgreSQL-Fälle).64 neue PG-Fälle prüfen Abschluss und
Executor, darunter alle drei Aktionen und Ablauf nach Audit-Sperrwartezeit.
Kein Source-/SQLfix nach Anwendung, nur eine Replay-Testerwartung korrigiert.
461 API-/Workertests gegen Fixture009 erneut bestanden. Insgesamt817 Tests;
beide DB-gebundenen Suiten nacheinander ausführen, da sie Fixture-Rollenbindungen
setzen. Die administrative Prüfumgebung bleibt vom späteren Runtimeclient getrennt.

## Privater Cockpit-Credentialablauf

IP-041 verbindet den privaten BFF-Kern über standardmäßig deaktivierte
008-API-Routen mit dem privaten Pythonexecutor. Das zusätzliche Profil
`passkey-credential-checks` legt eigene interne Fixture-APIs an und aktiviert
die Zweckrouten ausschließlich für eine davon. Die zweite beweist den
deaktivierten Standard. Kein Hostport, keine öffentliche Flagänderung und
keine neue Migration; Voraussetzung ist die bereits vorbereitete Fixture-DB
001–009 sowie der geschützte synthetische Browsercheck-Secretbestand.

```bash
sudo bash infra/scripts/compose.sh --file infra/compose.passkey-credential-checks.yaml \
  --profile passkey-credential-checks build credential-flow-node credential-flow-checks
sudo bash infra/scripts/compose.sh --file infra/compose.passkey-credential-checks.yaml \
  --profile passkey-credential-checks up -d --no-deps credential-flow-api credential-flow-disabled-api
sudo python3 tests/infra/check_passkey_credential_cockpit.py --orchestrate
sudo bash infra/scripts/compose.sh --file infra/compose.passkey-credential-checks.yaml \
  --profile passkey-credential-checks stop credential-flow-api credential-flow-disabled-api
```

Der Hostrelay verwendet nur die Standardbibliothek und verbindet begrenzte
private Pipes zweier gepinnter Checkcontainer. Nur der administrative
Pythonchecker erhält Fixture-DB-Credentials. Node führt echtes
SimpleWebAuthn/Jose und interne HTTPS-Anfragen aus; Python prüft den Token,
008-Verbrauch, AEAD-Mutation und009-Abschluss mit synthetischem Broker.
Schlüssel/Bodys/JWTs verbleiben im Prozessspeicher; Logs sind ausgeschaltet.
Keine Pipes oder Treiberausgaben in öffentliche Logs übernehmen.

Dieser Check und DB-Regressionssuiten werden nacheinander ausgeführt:
die dedizierte Fixture-Credentialrollenbindung wird neu gesetzt.
Nur eigene Fixture-APIs stoppen; kein `down` oder `--remove-orphans`.
Der Prüfaufbau provisioniert keinen Runtime-Credentialdienst.
[Ablauf, Belege und verbleibende Arbeit](../docs/passkey-credential-cockpit.md).
Abnahme:299 integrierte Prüfpunkte,572 API-/Worker- und385 Cockpittests,
Typecheck/gepinnte Builds und unabhängige Reviews bestanden. Fixture-APIs
gestoppt; öffentliche Dienste gesund, reguläres TLS HTTPS200. Nach Hostneustart
die geschützte synthetische `/tmp`-Ablage bei Bedarf mit dem vorhandenen
Prepare-Script neu erzeugen und nur Fixture-APIs mit frischen Mounts neu erstellen.

## Isolierter Credential-HTTPS-Transport

IP-042 ergänzt die opt-in Entwicklungs-HTTPS-Prüfung derselben Fixture:

```sh
bash infra/scripts/compose.sh --file infra/compose.passkey-credential-checks.yaml --profile passkey-credential-checks build credential-flow-checks
bash infra/scripts/compose.sh --file infra/compose.passkey-credential-checks.yaml --profile passkey-credential-checks build credential-flow-node
bash infra/scripts/compose.sh --file infra/compose.passkey-credential-checks.yaml --profile passkey-credential-checks up -d --no-deps credential-flow-api credential-flow-disabled-api
python3 tests/infra/check_passkey_credential_cockpit.py --orchestrate --https
bash infra/scripts/compose.sh --file infra/compose.passkey-credential-checks.yaml --profile passkey-credential-checks stop credential-flow-api credential-flow-disabled-api
```

Die kurzlebige synthetische TLS-CA, Server-/Clientidentitäten und Pflichtpin
werden ausschließlich in der Fixture erzeugt. Der Checker erhält im internen
Testnetz den Alias `credential-flow-executor.cockpit.local.test`, keine Hostports.
Sein migrationsberechtigter Prüfaufbau ist kein Runtime-Credentialdienst.
Nur benannte Fixture-APIs starten/stoppen; kein Default-`up`, `down` oder
`--remove-orphans`. Die vorhandene Pipevariante ohne `--https` bleibt prüfbar.
[Vertrag und Produktionsgrenzen](../docs/passkey-credential-https.md).

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
