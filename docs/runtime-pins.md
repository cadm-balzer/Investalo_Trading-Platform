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
Der optionale Offlineworker verwendet denselben Python-/Hashlockstand.
Ein öffentlicher H4-Snapshot wurde vom tatsächlichen Worker berechnet und
als Nettoergebnis/Equitykurve im Cockpit geprüft; keine neue Paketabhängigkeit.
CLI-Testfaktorregistrierung ersetzt keine normale Registrierung, Recovery-,
WebAuthn- oder Pilotabnahme.

Direkte Python-/JavaScript-Abhängigkeiten und transitive Locks liegen bei ihren
Anwendungen. Builds verwenden ausschließlich Hash-/Lockmodus. Host-Python
3.14.4 und Host-Node 26.13.0 sind Entwicklungstools; Containerpins sind die
Releasegrundlage. Auf 2 vCPU/1,9 GiB RAM Builds/Research serialisieren.

Neue Releases erfordern bewusste Pinänderung, Digestauflösung und relevante
Regressionstests. Ein Pin darf notwendige Sicherheitsupdates nicht unbegrenzt
verhindern. Betrieb/Supporttermine vor jedem Pilotupgrade erneut prüfen.

Der isolierte Credentialkern besitzt einen separaten
[Hashlock](../packages/credentials/requirements.lock): `cryptography==50.0.2`,
`cffi==2.1.1`, `pycparser==3.12`. Offizielle PyPI-Wheelhashes für CPython
3.13/3.14 auf Linux x86-64, glibc >=2.34. Der tatsächliche Nonroot-Checkcontainer
nutzt Python 3.14.10 mit diesem Lock; API-/Researchabhängigkeiten sind unverändert.
Der getrennte [Credentialstore-Lock](../services/credentials/requirements.lock)
ergänzt `psycopg[binary]==3.3.8` aus dem bestehenden API-Lock. Der Testlock nutzt
die bereits festgelegten pytest9.2.0-Pins und Wheelhashes. Sein Nonroot-
PostgreSQL-Checkimage baut ebenfalls auf Python3.14.10 mit festem Digest.
Keine neue CI/CD-Abhängigkeit oder Paketversion eingeführt.

Offizielle Quellen:

- [Docker auf Ubuntu](https://docs.docker.com/engine/install/ubuntu/)
- [Python Releases](https://www.python.org/downloads/)
- [Node Releases und Wartung](https://nodejs.org/en/about/previous-releases/)
- [PostgreSQL-Versionierung](https://www.postgresql.org/support/versioning/)
- [Authelia 4.39.28](https://github.com/authelia/authelia/releases/tag/v4.39.28)
- [Caddy 2.11.9](https://github.com/caddyserver/caddy/releases/tag/v2.11.9)
- [Authelia OIDC-Clientpolicy](https://www.authelia.com/configuration/identity-providers/openid-connect/clients/)
- [Authelia PostgreSQL](https://www.authelia.com/configuration/storage/postgres/)
