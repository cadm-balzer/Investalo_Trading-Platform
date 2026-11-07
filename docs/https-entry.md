# HTTPS-Einstieg: Befund und vorbereitete Vorschau

Stand 2026-11-07. Der Nutzer meldet einen erreichbaren Browserzugang unter
`https://cockpit.investalo.de` mit SSL-Fehler. Die unabhängige Hostprüfung zeigt:

- `cockpit.investalo.de` löst auf die Hostadresse `5.45.96.83` auf.
- Port80 und443 weisen die Verbindung derzeit ab. Auf dem Host lauscht nur
  der lokale Caddy-Einstieg `127.0.0.1:8443`.
- `auth.cockpit.investalo.de` ist derzeit nicht auflösbar.
- Der lokale Caddy verwendet eine Entwicklungs-CA, lokale Namen und
  `auto_https off`. Das ist keine Let’s-Encrypt-Konfiguration.

Der gemeldete Browserweg ist noch zu klären. Ein tatsächlich ausgeliefertes
öffentliches Zertifikat konnte bei diesem Befund nicht untersucht werden.
Der Registrymerge `6a18102` ist auf `origin/main` bei `f422a90` verifiziert.

## Geprüfte, noch nicht aktivierte Konfiguration

[Caddyfile.public-preview](../infra/caddy/Caddyfile.public-preview) und
[Compose-Overlay](../infra/compose.public-preview.yaml) bereiten einen zentralen
HTTPS-Einstieg mit automatischer Ausstellung und Erneuerung ausschließlich durch
Let’s Encrypt vor. Der Standardlauf von `compose.sh` bleibt lokal.

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
zu großzügigen PEM-Platzhalters. Keine ACME-Anfrage und kein öffentlicher Start.

## Voraussetzungen für eine konkrete Aktivierung

Die öffentliche Entwicklungsvorschau braucht eine ausdrückliche Freigabe nach
[AGENTS.md](../AGENTS.md). Sie ersetzt keine Privatpilot-/Produktionsabnahme.
Vorher müssen beide öffentlichen Namen kontrolliert auf diesen Server zeigen.
Für `auth.cockpit.investalo.de` fehlt derzeit ein A-Eintrag auf `5.45.96.83`
oder ein entsprechender CNAME. Keine falschen AAAA-Einträge veröffentlichen;
gegebenenfalls bestehende CAA-Regeln müssen Let’s Encrypt zulassen.
HTTP-01 benötigt extern80, TLS-ALPN-01 extern443.

Eine neue Issuer-URL ist eine neue Plattformidentität:
`platform.users` bindet Nutzer an `(oidc_issuer, oidc_subject)`.
Die vorhandene lokale Nutzer-/Tenantbindung wird nicht umgeschrieben.
Vor erfolgreichem Cockpitlogin muss die bestätigte öffentliche Testidentität
bewusst provisioniert werden. Ohne diese Bindung bleibt die API403.
Der Helper erledigt diese Berechtigungsentscheidung nicht.
Researchdaten/-worker und Passkeys werden ebenfalls nicht automatisch übertragen.

Nach konkreter Freigabe, DNSprüfung und bewusster Identitätsprovisionierung:

```sh
# Öffentlichkeitsänderung: erst nach ausdrücklicher Aktivierungsfreigabe!
sudo bash infra/scripts/compose.sh --file infra/compose.public-preview.yaml \
  up -d api cockpit authelia caddy
curl --head --fail --silent --show-error https://cockpit.investalo.de/
curl --fail --silent --show-error \
  https://auth.cockpit.investalo.de/.well-known/openid-configuration
```

Dann zusätzlich Zertifikatskette/Hostname/Ablauf, HTTP-Weiterleitung,
OIDC-/MFA-/CSRF-/Logoutablauf, tatsächliche externe Portgrenzen und
persistenten ACME-Zustand nachweisen. Bei unbekanntem Ergebnis zunächst den
Istzustand abgleichen. Keine Zertifikatsprüfung abschalten.

Rückkehr zum bestehenden lokalen Profil mit beibehaltenen Daten:

```sh
sudo bash infra/scripts/compose.sh up -d api cockpit authelia caddy
```

Das startet die betroffenen Dienste neu; Authelia-In-Memory-Sitzungen enden.
Die ursprünglichen lokalen Konfigurationen und Zustandsordner bleiben erhalten.

Reale Einladungen, SMTP/Recovery, externe Sicherung, Raten-/Speicherlimits und
öffentliche Betriebsabnahme bleiben eigene Gates. Der Entwurf verwendet noch
den synthetischen Entwicklungsnutzer mit File-Notifier. Kontoänderungen,
echte Brokerkeyannahme und Echtgeldhandel bleiben gesperrt.

Grundlagen: [Caddy Automatic HTTPS](https://caddyserver.com/docs/automatic-https),
[Let’s Encrypt Challenges](https://letsencrypt.org/docs/challenge-types/),
[Authelia Cookies](https://www.authelia.com/configuration/session/introduction/),
[Compose Merge](https://docs.docker.com/reference/compose-file/merge/).
