# HTTPS-Einstieg: aktive Entwicklungsvorschau

Stand 2026-11-07. Der Nutzer hat nach Einrichtung der Anmeldedomain ausdrücklich
die Freischaltung der Entwicklungsvorschau genehmigt. Sie ist erreichbar:

- Cockpit: https://cockpit.investalo.de
- Anmeldung: https://auth.cockpit.investalo.de
- Beide DNS-Namen zeigen auf `5.45.96.83`; beide Zertifikate stammen von
  Let’s Encrypt und laufen am 2027-02-05 ab.
- 48 tatsächliche öffentliche HTTPS-Prüfpunkte bestanden: Passwort/TOTP,
  OIDC/BFF, Mandanten-API, Backtestausführung, Ergebnisdiagramm, Enrollmentgrenzen
  und Logout. Systemvertrauen prüft die Zertifikate ohne Entwicklungs-CA.

Der ursprüngliche Hostaudit fand ausschließlich Loopback8443 mit lokaler CA und
noch keine auflösbare Anmeldedomain. Das separate Overlay ersetzt jetzt diesen
Einstieg für die freigegebene Vorschau. Der Registrymerge `6a18102` ist auf
`origin/main` bei `f422a90` verifiziert. Eine vollständige Privatpilot- oder
Produktionsabnahme bleibt separat.

## Konfiguration und Bedienung

[Caddyfile.public-preview](../infra/caddy/Caddyfile.public-preview) und
[Compose-Overlay](../infra/compose.public-preview.yaml) bereiten einen zentralen
HTTPS-Einstieg mit automatischer Ausstellung und Erneuerung ausschließlich durch
Let’s Encrypt vor. Das Standardprofil von `compose.sh` bleibt lokal; bei
Änderungen am laufenden öffentlichen Einstieg immer das Overlay angeben.

Das Overlay veröffentlicht ausschließlich Caddy auf `5.45.96.83:80/443`.
API, PostgreSQL, Authelia und Worker erhalten keine eigenen Hostports.
Caddy bleibt UID10001, ohne Capabilities und mit schreibgeschütztem
Rootdateisystem. Sein Low-Port-Sysctl gilt ausschließlich im Containernetzraum.
Öffentliche ACME-Daten und Cockpitsitzungen erhalten separate geschützte Ordner.
Interne Authelia-TLS-Prüfung verwendet weiterhin die vorhandene CA.

Cockpit-Origin, API-/BFF-Issuer, Authelia-Cookiedomain, exakter OIDC-Callback
und Passkey-RP passen zu den öffentlichen Namen. Interne Caddy-Aliasse erlauben
BFF-Discovery/JWKS ohne öffentliche Netzwerkfreigabe für das Cockpit.
Die RP `cockpit.investalo.de` braucht eigene Passkeyregistrierung.

Der [Vorbereitungshelper](../infra/scripts/prepare-public-preview.py) akzeptiert
nur die unveränderte synthetische lokale Konfiguration. Er übernimmt vorhandene
Signatur-/Clientwerte in eine neue geschützte Datei, gibt keine Werte aus und
verändert weder DNS, Ports, Dienste, Nutzer noch Datenbanken.
Abweichende Quellen, Symlinks, Hardlinks, Dateirechte und überschreibende
Ausgaben werden abgewiesen. Vorhandene identische Ausgabe wird nur verglichen.

```sh
# Ausschließlich Dateien vorbereiten und Syntax prüfen, kein Start:
sudo python3 infra/scripts/prepare-public-preview.py --development-preview
sudo bash infra/scripts/compose.sh --file infra/compose.public-preview.yaml config --quiet
sudo bash infra/scripts/compose.sh --file infra/compose.public-preview.yaml \
  run --rm --no-deps authelia authelia config validate --config /config/configuration.yml
```

Geprüft: sechs Helpertests, zusammengeführte Compose-Port-/Mount-/Origin-/
Issuer-/RP-Verträge, gepinnter Caddyvalidator ohne Netzwerk und gepinnter
Autheliavalidator. Unabhängiger Review ohne Restblocker nach Korrektur eines
zu großzügigen PEM-Platzhalters. Diese Vorbereitung erfolgte vor der Freigabe;
Ausstellung und Start folgten erst nach ausdrücklicher Nutzerzustimmung.

Zusätzlich sechs Provisionierungstests prüfen Autorität, eindeutige vorhandene
Tenantbindung, Operatorrolle, Fehlerausgabe und geschützte Manifestdateien.

## Öffentliche Identität und laufender Betrieb

Beide DNS-Namen sind jetzt aufgelöst. HTTP-01 benötigt extern80,
TLS-ALPN-01 extern443. Während der DNS-Verteilung schlug die erste Ausstellung
für die Anmeldedomain fehl; Caddys automatische Wiederholung war erfolgreich.

Eine neue Issuer-URL ist eine neue Plattformidentität:
`platform.users` bindet Nutzer an `(oidc_issuer, oidc_subject)`.
Die vorhandene lokale Nutzer-/Tenantbindung wird nicht umgeschrieben.
Der [Provisionierungshelper](../infra/scripts/provision-public-preview.py)
hat die synthetische öffentliche Identität ausdrücklich als weiteren Owner
an denselben vorhandenen Entwicklungstenant gebunden. Er verlangt genau einen
aktiven lokalen Owner und verwendet dessen konkrete Tenant-ID. Die ursprüngliche
Identität, Workerbindung, Datasets und bisherigen Faktoren bleiben erhalten.
Credential-/Passkey-Eigentum wird nicht übertragen; die öffentliche RP benötigt
eigene Registrierung.

Der Testnutzer heißt `pilot`. Bestehendes Passwort und TOTP-Einrichtungsadresse
liegen ausschließlich in den geschützten, ignorierten Dateien
`infra/local/pilot-access.txt` und `infra/local/pilot-totp.txt`.
Werte nicht in Git, Logs oder öffentliche Nachrichten übernehmen.

Nach der bereits erteilten Freigabe verwendete Befehle:

```sh
sudo python3 infra/scripts/provision-public-preview.py --development-preview
sudo bash infra/scripts/compose.sh --file infra/compose.public-preview.yaml \
  up -d api cockpit authelia caddy
curl --head --fail --silent --show-error https://cockpit.investalo.de/
curl --fail --silent --show-error \
  https://auth.cockpit.investalo.de/.well-known/openid-configuration
sudo python3 tests/infra/check_local_auth.py --public-preview
```

Zertifikatskette/Hostname/Ablauf, HTTP-Weiterleitung und der komplette
Anwendungsablauf sind geprüft. Nach Proxyneustart bleiben Zertifikate und
Vertrauen erhalten. Nur Caddy veröffentlicht Hostports; interne Rollen- und
Dateirechte bleiben beschränkt. Bei unbekanntem Provisionierungsergebnis zuerst
den Istzustand abgleichen. Erneuerungsnachweis, Ablaufalarm und externe
Wiederherstellung folgen unter BL-026. Keine Zertifikatsprüfung abschalten.

Rückkehr zum bestehenden lokalen Profil mit beibehaltenen Daten:

```sh
sudo bash infra/scripts/compose.sh up -d api cockpit authelia caddy
```

Das startet die betroffenen Dienste neu; Authelia-In-Memory-Sitzungen enden.
Die ursprünglichen lokalen Konfigurationen und Zustandsordner bleiben erhalten.

Reale Einladungen, SMTP/Recovery, externe Sicherung, Raten-/Speicherlimits und
öffentliche Betriebsabnahme bleiben eigene Gates. Die Vorschau verwendet noch
den synthetischen Entwicklungsnutzer mit File-Notifier. Kontoänderungen,
echte Brokerkeyannahme und Echtgeldhandel bleiben gesperrt.

Grundlagen: [Caddy Automatic HTTPS](https://caddyserver.com/docs/automatic-https),
[Let’s Encrypt Challenges](https://letsencrypt.org/docs/challenge-types/),
[Authelia Cookies](https://www.authelia.com/configuration/session/introduction/),
[Compose Merge](https://docs.docker.com/reference/compose-file/merge/).
