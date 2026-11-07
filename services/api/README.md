# Lokales API-Fundament

FastAPI mit PostgreSQL, signiertem BFF-Kontext und erzwungenen RLS-Regeln.
Live-Ausführung ist deaktiviert; es gibt keinen Broker-Dispatch und keine Route
zur manuellen Reservefreigabe. Das Fundament enthält echte persistente
Backtest-Aufträge, noch keinen Job-Worker oder erfundene Ergebnisdaten.

Start: `python -m uvicorn investalo_api.main:app --host 0.0.0.0 --port 8000`.
Compose ergänzt interne TLS-Zertifikate; `PYTHONPATH` enthält `services/api/src`.
Die Lockfiles enthalten exakte Releases und SHA256-Wheelhashes für CPython 3.14.
Projekt-Metadaten erlauben Python 3.13–3.14; Python 3.13 ist hier nicht getestet.

Konfiguration: `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD_FILE`,
`PGSSLMODE`, `PGSSLROOTCERT`, `API_INTERNAL_AUTH_SECRET_FILE`, `API_OIDC_ISSUER`.
TLS bleibt über libpq konfiguriert. Passwörter und der mindestens 32 Byte lange
interne Schlüssel kommen aus Dateien; es gibt keine Entwicklungs-Standardwerte.

Migration: `python -m investalo_api.migrate` ausschließlich als
`investalo_migration`. Die SQL-Dateien werden nach Anwendung per Prüfsumme
geschützt. Runtime ist ausschließlich `investalo_runtime`, ohne DDL, RLS-Bypass,
UPDATE, DELETE oder TRUNCATE. Tenant-Kontext entsteht aus einer aktiven
DB-Mitgliedschaft in derselben Transaktion und verschwindet nach Commit.

Einladungsbindung nach bestätigtem Authelia-Subject:
`python -m investalo_api.provision --issuer <HTTPS-Issuer> --subject <OIDC-sub>
--tenant-name "Lokaler Test" --role owner`.
Dieser Operator-Befehl benötigt die Migrationsidentität. Wiederholung erzeugt
keine Duplikate. `--tenant-id <UUID>` bindet eine weitere ausdrücklich eingeladene
Identität an einen bestehenden Tenant; Name und bestehende Rolle müssen passen.
Der Befehl erzeugt weder Kontostände noch Broker-Verbindungen.

Öffentlich minimale Liveness/Readiness unter `/health/live` und `/health/ready`,
sowie bestätigte Paper-Regeln unter `/v1/trading-config`.
Authentifizierte Endpunkte sind `/v1/me`, `/v1/overview`, `/v1/jobs` und
`POST /v1/backtests` mit `Idempotency-Key: <UUID>`. Backtests erlauben
`{"symbol":"BTC/USDT","timeframe":"4h"}` bzw. ETH/USDT; fremde Felder werden
abgelehnt. Geldbeträge werden als Dezimalzeichenfolgen ausgegeben.

Interne Assertions: HS256, `iss=investalo-bff`, `aud=investalo-api`, bestätigtes
`oidc_iss`/opaques `sub`, `oidc_auth_time`, `iat`, höchstens 60 Sekunden `exp`,
einmaliges UUID-`jti`, `htm`, exaktes `htu` inklusive Query und
`body_sha256` über unveränderte Bytes. Tenant-Aufrufe benötigen `tenant_id` und
aktuelles `auth_epoch` aus `/v1/me`. Browser-Identitätsheader haben keine Wirkung.
DB-Replay-Schutz, Epoch und Reauth-Schwelle gelten pro Transaktion.
Die API begrenzt Bodies vor der Framework-Validierung auf 16 KiB und entfernt
eingereichte Werte aus Validierungsfehlern.

Tests: `PYTHONPATH=services/api/src python -m pytest tests/api`.
PG-Tests benötigen isoliertes lokales PostgreSQL und zusätzlich
`API_TEST_ADMIN_USER=investalo_migration` sowie
`API_TEST_ADMIN_PASSWORD_FILE`. Sie erzeugen Testdatensätze ohne destruktives
Aufräumen. Nonce-Aufbewahrung, Worker-Privilegien, Recovery-Operatorablauf und
Rategrenzen bleiben gesonderte Betriebsarbeit vor einem öffentlichen Pilot.
