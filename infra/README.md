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
sudo bash infra/scripts/compose.sh --profile tools --profile checks build api migrate api-checks
sudo bash infra/scripts/compose.sh build cockpit
sudo bash infra/scripts/compose.sh up -d postgres authelia
sudo bash infra/scripts/compose.sh --profile tools run --rm migrate
# Nur generierten .invalid-Testnutzer samt TOTP und Tenant anlegen.
sudo python3 infra/scripts/provision-local-test.py
sudo bash infra/scripts/compose.sh up -d api cockpit caddy
sudo python3 tests/infra/check_local_auth.py
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

Verifikation und Betrieb:

```sh
sudo bash infra/scripts/compose.sh ps
sudo bash infra/scripts/compose.sh --profile checks run --rm api-checks
PYTHONPATH=packages/trading/src python3 -m unittest discover -s tests/trading
npm --prefix apps/cockpit test
npm --prefix apps/cockpit run typecheck
```

Cockpitmeldungen zeigen fehlende Konten/Positionen ausdrücklich als leeren
Datenbestand. Backtestanforderungen werden dauerhaft eingereiht; Datenimport und
ausführender Worker folgen. Es gibt noch keine nutzbaren Brokerverbindungen.
Lokale BFF-Abmeldung löscht die Cockpitsitzung; die IdP-Sitzung bleibt bestehen.
Jeder neue Cockpitlogin erzwingt dennoch eine frische Anmeldung.
