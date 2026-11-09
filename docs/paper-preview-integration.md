# Paperstand in der öffentlichen Entwicklungsvorschau

IP-054,2026-11-09. Merge03fee1e in Mainb0827ba verifiziert.
Übersicht, Portfolio und Journal zeigen den bestätigten Paperstand des
angemeldeten Entwicklungstenants. Neues eigenes simuliertes Konto
„Crypto-Paper · Entwicklung“, tatsächlicher öffentlicher BTC-/ETH-Kurslauf
mit Revision82 und null Fills. Anfangskapital10.000USDT nach bestätigtem
Q17-Profil. RSI14/Wilder, Q32-Modellbasis, Risk und Kosten unverändert.
Dies ist ein gespeicherter Stand aus einem begrenzten Kurslauf; der
eingeschränkte Einmal-Launcher bestätigt keinen dauerhaften Workerbetrieb.

## Schema und eigene Identität

Die normale Entwicklungsdatenbank `investalo` ist jetzt001–012.
`prepare-paper-preview-schema.py` prüft zuerst beide unveränderten Ledger.
Vollständige008–012-DDL und Runtimeprüfungen für eigenen/fremden Tenant,
Epoch, alte OIDC-Zeit und entzogene Mitgliedschaft werden zurückgerollt.
Nur `--apply-reviewed-development` übernimmt alle fünf Migrationen und
Ledgerzeilen atomar. Keine Dateien geändert oder Migration übersprungen;
Fixture bleibt001–012. Kein Default-Migrate/Up.

008/009 erweitern private Credentialfunktionen; deren HTTP-/Dienstaktivierung
ist weiterhin gesperrt. Tatsächliche Containerflags und sensitive Routen
sind nach der Aktualisierung geprüft. Keine Schlüsselannahme oder Brokerorder.

`provision-paper-preview.py` verifiziert die geschützte öffentliche
Entwicklungsidentität und aktive Owner-Mitgliedschaft vor Provisionierung.
Fester LOGIN `investalo_paper_preview`, genau ein eigenes neues Paperkonto.
Prepared/Bound-Manifest, Passwort und Env unter ignoriertem `infra/local/`;
UID/Modes, Symlink-/Hardlinkschutz und exklusive Anlage wie IP-053.
Vorhandene Rollen/Bindungen prüfen oder ablehnen, auch im Prepared-Recovery;
kein Reparieren, Passwortrotieren oder Unpause. Keine Kopie von Fixture-
Checkpoints/Fills/Journals, keine neue Benutzer-/Tenant-/Researchbindung.

Nur drei Paperfunktionen, keine direkten Tabellen, Credential-/Research-
Funktionen oder Fixture-CONNECT. Exakte normale HBA-Regel mit TLS/SCRAM;
bestehende Fixture-Paperrollen bleiben für die normale DB gesperrt.
Der neue `paper_preview_once` verlangt festen DB-/Rollen-/CA-/Secretpfad,
explizite Aktivierung und `--once`; zusätzliche PG-Variablen abgewiesen.
Kein Listener/Hostport/Auto-Retry/Neustart. Unknowncommit: Readback erforderlich.

## Bedienung und Rückfall

```bash
# Vorprüfung; explizite Anwendung nur bei passendem bisherigen007-Ledger
python3 infra/scripts/prepare-paper-preview-schema.py --apply-reviewed-development
python3 infra/scripts/provision-paper-preview.py
python3 infra/scripts/check-paper-preview.py
# Ein ausdrücklich begrenzter Kurslauf
bash infra/scripts/compose.sh --env-file infra/local/paper_preview.env \
  --file infra/compose.public-preview.yaml --file infra/compose.paper-preview.yaml \
  --profile paper-preview run --rm --no-deps -T paper-preview-once
# Lesende Entwicklungsvorschau
bash infra/scripts/compose.sh --env-file infra/local/paper_preview.env \
  --file infra/compose.public-preview.yaml --file infra/compose.paper-preview.yaml \
  up -d --no-deps api cockpit
python3 infra/scripts/check-paper-preview.py --active
python3 tests/infra/check_local_auth.py --public-preview --paper-preview
```

Beide Overlays sind für weitere API-/Cockpitaktualisierungen nötig.
Rückfall auf ausgeschaltete Anzeige: nur Public-Preview-Overlay mit
`up -d --no-deps api cockpit`. Angewendete Migrationen bleiben unveränderlich;
kein Schema-Downgrade. Caddy/Auth/Postgres/Research und öffentliche
Issuer-/Session-/Datenbindungen wurden nicht neu erstellt.

## Abnahme und weitere Arbeit

34 gezielte gepinnte Pythonfälle, fünf stdlib-Provisionierungsfälle und
17 Cockpit-Vertrags-/SSR-Fälle grün; gepinnte API-/Cockpitbuilds bestanden.
Wiederholte Provisionierung unverändert, vier tatsächliche Rechte-/Bindungs-
drifts zurückgerollt; realer eingeschränkter TLS-LOGIN, abgewiesener
Fixture-/Tabellenzugriff und eigene Wiederherstellung geprüft.
Scoped Review ohne offenen Blocker.29 tatsächliche HTTPS-/OIDC-/MFA-/BFF-
Prüfpunkte: eigenes Panel auf drei Seiten, kein Cache, sensitive Routen503
und Logout nur der Prüfsitzung. Der Modus erzeugt keinen Researchjob.

API-/Cockpit-Anzeigeflags nur im zusätzlichen Overlay aktiviert; Default
Compose und bloßes Public-Preview-Overlay behalten ausgeschaltete Anzeige.
Echtgeld, Kontoveränderungen und Credentialdienst bleiben gesperrt.
IP-047/BL-028: eigener begrenzter Beobachtungsworker für den Previewtenant,
echte Mitternachtsbeobachtung, Quoten/Egress/Retention/Monitoring/Recovery.
Der getrennte Fixture-Beobachtungslauf IP-053 ist kein Feed dieses Kontos.
Holdout bleibt gesperrt; null Fills liefern keinen Profitabilitätsnachweis.
