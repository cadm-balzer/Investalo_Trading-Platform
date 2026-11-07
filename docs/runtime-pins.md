# Runtimepins und lokaler Nachweis

Stand 2026-11-07. Offizielle Release-/Registryquellen geprüft; keine `latest`-
Tags. Unveränderliche Manifestdigests stehen in [images.env](../infra/images.env).
Funktionstests und zulässiger Umfang stehen im [Ticketboard](tasks/board.md).

| Runtime | Exakter Stand | Grundlage |
|---|---|---|
| Python | 3.14.10, slim-bookworm | Python-Downloads, aktuelle Bugfixlinie |
| Node | 24.22.2, bookworm-slim | Node 24 LTS, Sicherheitswartung |
| PostgreSQL | 18.6, bookworm | Unterstützte stabile Majorlinie 18 |
| Authelia | 4.39.28 | GitHub-Release vom 2026-09-17 |
| Caddy | 2.11.9, alpine | GitHub-Release vom 2026-11-05 |
| Docker Engine/CLI | 29.9.3, Ubuntu-Paket `5:29.9.3-1~ubuntu.26.04~resolute` | Signierter offizieller Ubuntu-26.04-APT-Index |
| containerd.io | `2.4.2-3~ubuntu.26.04~resolute` | Gleicher offizieller Paketindex |
| Buildx | `0.38.1-1~ubuntu.26.04~resolute` | Gleicher offizieller Paketindex |
| Compose | `5.7.0-1~ubuntu.26.04~resolute` | Gleicher offizieller Paketindex |
| Host venv-Metapaket | `python3-venv=3.14.3-0ubuntu2` | Ubuntu-26.04-Paketquelle, Runtime im Container separat gepinnt |

Docker/Compose wurden installiert und ihre Versionsausgabe geprüft.
PostgreSQL und Authelia starten als Nonroot und verwenden verschlüsselte
DB-Verbindungen. Lokale HTTPS-OIDC-Discovery prüft die CA, richtigen Issuer
und PKCE `S256`; der Host veröffentlicht nur `127.0.0.1:8443`.
Der tatsächliche HTTPS-Passwort-/TOTP-/OIDC-BFF-Durchlauf ist lokal bestanden,
einschließlich frischem Login, Mandantenzugriff und Abmeldung.
CLI-Testfaktorregistrierung ersetzt keine normale Registrierung, Recovery-,
WebAuthn- oder Pilotabnahme.

Direkte Python-/JavaScript-Abhängigkeiten und transitive Locks liegen bei ihren
Anwendungen. Builds verwenden ausschließlich Hash-/Lockmodus. Host-Python
3.14.4 und Host-Node 26.13.0 sind Entwicklungstools; Containerpins sind die
Releasegrundlage. Auf 2 vCPU/1,9 GiB RAM Builds/Research serialisieren.

Neue Releases erfordern bewusste Pinänderung, Digestauflösung und relevante
Regressionstests. Ein Pin darf notwendige Sicherheitsupdates nicht unbegrenzt
verhindern. Betrieb/Supporttermine vor jedem Pilotupgrade erneut prüfen.

Offizielle Quellen:

- [Docker auf Ubuntu](https://docs.docker.com/engine/install/ubuntu/)
- [Python Releases](https://www.python.org/downloads/)
- [Node Releases und Wartung](https://nodejs.org/en/about/previous-releases/)
- [PostgreSQL-Versionierung](https://www.postgresql.org/support/versioning/)
- [Authelia 4.39.28](https://github.com/authelia/authelia/releases/tag/v4.39.28)
- [Caddy 2.11.9](https://github.com/caddyserver/caddy/releases/tag/v2.11.9)
- [Authelia OIDC-Clientpolicy](https://www.authelia.com/configuration/identity-providers/openid-connect/clients/)
- [Authelia PostgreSQL](https://www.authelia.com/configuration/storage/postgres/)
