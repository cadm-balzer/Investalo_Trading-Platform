# Lokales API-Fundament

FastAPI mit PostgreSQL, signiertem BFF-Kontext und erzwungenen RLS-Regeln.
Live-Ausführung ist deaktiviert; es gibt keinen Broker-Dispatch und keine Route
zur manuellen Reservefreigabe. Persistente Backtest-Aufträge werden durch einen
getrennten, fest an einen Tenant gebundenen Offline-Researchworker verarbeitet.

Start: `python -m uvicorn investalo_api.main:app --host 0.0.0.0 --port 8000`.
Compose ergänzt interne TLS-Zertifikate; `PYTHONPATH` enthält `services/api/src`,
`packages/trading/src` und `packages/marketdata/src`.
Die Lockfiles enthalten exakte Releases und SHA256-Wheelhashes für CPython 3.14.
Projekt-Metadaten erlauben Python 3.13–3.14; Python 3.13 ist hier nicht getestet.

Konfiguration: `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD_FILE`,
`PGSSLMODE`, `PGSSLROOTCERT`, `API_INTERNAL_AUTH_SECRET_FILE`, `API_OIDC_ISSUER`,
`API_PASSKEY_RP_ID` (lokal `cockpit.local.test`, Hostname ohne Port).
TLS bleibt über libpq konfiguriert. Passwörter und der mindestens 32 Byte lange
interne Schlüssel kommen aus Dateien; es gibt keine Entwicklungs-Standardwerte.

Migration: `python -m investalo_api.migrate` ausschließlich als
`investalo_migration`. Die SQL-Dateien werden nach Anwendung per Prüfsumme
geschützt. Vor `002_research` muss der Administrator die NOLOGIN-Gruppe
`investalo_research_worker` anlegen. `001_foundation` bleibt unverändert.
Vor `003_credentials` benötigt PostgreSQL zusätzlich die NOLOGIN-Gruppe
`investalo_credentials_worker`. Neuinitialisierung legt beide Gruppen an;
für vorhandene lokale Entwicklung provisioniert der Credential-Testhelper die
zweite Gruppe. Lokal sind001–007 in `investalo` und
`investalo_credentials_checks` angewendet und unveränderlich. Die normale
API benötigt mindestens002; der additive Metadatenendpunkt benötigt005 und
bricht ohne diese Migration geschlossen ab. Passkeyendpunkte benötigen006
und einen festen RP-Hostnamen; der interne Aktionsnachweis benötigt007.
Fehlende Konfiguration wird abgewiesen.
Kein Brokerkeyeingabeendpunkt.
Alte Aufträge ohne eingefrorene Daten werden als `dataset_missing` beendet;
es erfolgt keine automatische Zuordnung neuer oder synthetischer Daten.
Runtime ist ausschließlich `investalo_runtime`, ohne DDL, RLS-Bypass,
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
Authentifizierte Endpunkte sind `/v1/me`, `/v1/overview`, `/v1/datasets`,
`/v1/jobs`, `/v1/jobs/{UUID}` und
`POST /v1/backtests` mit `Idempotency-Key: <UUID>`. Backtests erlauben
`{"symbol":"BTC/USDT","timeframe":"4h"}` bzw. ETH/USDT; fremde Felder werden
abgelehnt. Optionales `dataset_id` bindet eine ausdrückliche Snapshotversion.
Ohne ID wird die neueste nichtsynthetische Researchversion gewählt.
Fehlt sie, lautet der Fehler `409 dataset_unavailable`. Synthetische Daten
erfordern Zweck `test` und eine ausdrückliche ID; Holdout ist gesperrt.
Wiederholte Idempotenzschlüssel behalten ihre ursprüngliche Version, auch nach
einem neueren Import. Strategie, Präzision und Kosten werden zugleich eingefroren.

Operatorimport: `python -m investalo_api.import_dataset --tenant-id <UUID>
--purpose research|test|holdout --file <snapshot.json>`.
Nur die Migrationsidentität darf validierte, unveränderliche Snapshots importieren.
Der identische Import ist idempotent. Abweichende Provenienz oder Abdeckung bei
gleichem Kerzendigest wird verweigert; ein bestehender Snapshot wird nie umgedeutet.
Die API gibt Metadaten mit Herkunft, Digest, Zeitraum und nullable
`coverage_complete` aus, keine Rohkerzen oder privaten CSV-URLs.

`GET /v1/credential-actions/{UUID}` veröffentlicht nur Konto-ID/-name/-modus/
status, eigene opaque Verbindungs-ID, Credentialrevision und Speicherversion.
Aktive owner/trader und aktuelle Identität/Epoch werden in derselben Transaktion
erneut geprüft. Fremde Konten und Verbindungen anderer Nutzer bleiben403, auch
im selben Tenant; pausierte eigene Konten bleiben für späteren Widerruf sichtbar.
Die feste005-Funktion erlaubt nur dem Runtime-LOGIN diese Projektion.
Broker-UID, Parent, Envelope und KEK-ID werden nicht gelesen oder veröffentlicht.
Private Tabellen und die003/004-Credentialfunktionen bleiben für API/Research
gesperrt; diese Metadaten sind keine MFA- oder Schreibfreigabe.

`GET /v1/passkeys/context` liefert nur die eigene Publickeyregistrierung mit
autoritativer Nutzer-/Tenant-/Epochbindung. Die internen BFF-POST-Endpunkte
`/v1/passkeys/enrollment/claim` und `/v1/passkeys/enrollment/finish` verlangen
strenge, begrenzte Bodies ohne doppelte JSON-Felder. Claim wird vor der Antwort
committed; Abschluss prüft aktuelle Identität, Sitzungshash, Frist und RP und
speichert Registry und Audit atomar. Die API vertraut der WebAuthn-Prüfung
des BFF. Kein HTTP-Assertion-CAS oder sensitive Actionfreigabe.
Adminmodul `investalo_api.passkey_admin` stellt nach manueller E-Mail-Prüfung
Tickets aus und widerruft Passkeys mit globaler Sitzungssperre.
[Bedienung und Grenzen](../../infra/README.md#passkey-enrollment-und-widerruf).

Die internen POST-Routen unter `/v1/passkey-action-proofs/`
(`prepare`, `claim`, `finish`, `grant`, `confirm`) benötigen additive007.
Sie frieren ausschließlich sichere005-Metadaten, Ziel, Actor/Epoch,
Faktorversion und gehashte Sitzung-/Vorschau-Bindungen ein.
Claim committed vor BFF-Kryptoprüfung; Finish verbindet Registry-CAS und
Grant atomar. Confirm prüft genau Grant und Vorschaukennung vor einmaligem
Verbrauch und liefert `status:verified, execution_enabled:false`.
Die tatsächliche Passkeyprüfzeit ersetzt niemals die ursprüngliche OIDC-Zeit.
SQL/API vertrauen dem Kryptoverdict des geprüften BFF.
IP-037 verwendet diese unveränderten API-Routen aus einer ausdrücklich
aktivierbaren BFF-Browservorschau. Diese007-Routen erteilen weiterhin keine
Credentialfreigabe oder Brokerausführung;003/004 bleiben gesperrt.
[Vertrag und Gates](../../docs/passkey-action-proofs.md).
[BFF-Browservorschau](../../docs/passkey-browser-proof.md).

IP-041 ergänzt ausschließlich bei `API_PASSKEY_CREDENTIAL_AUTHORIZATIONS=1`
die internen POST-Routen `/v1/passkey-credential-authorizations/prepare`
und `/authorize`. `API_PASSKEY_ORIGIN` muss kanonisches HTTPS mit exakt
passendem `API_PASSKEY_RP_ID` sein. Die Vorbereitung nimmt einen Bodydigest,
die Zustimmung Authorization-/Grant-ID und gehashte Session-/Vorschaubindung.
Actor, ursprüngliche OIDC-Zeit, RP und Origin bleiben serverseitig gebunden.
008 friert den Credentialzweck vor dem Nachweis ein und bestätigt ihn einmalig;
eine bisherige007-Prüfbestätigung lässt sich nicht umwidmen. Keine Rohschlüssel,
privaten Credentialbodys oder Credential-JWTs an diesen Routen.
Der Receipt erhält `execution_enabled:false`; der private Fixtureexecutor ist
über injizierte BFF-Ports erreichbar. Default/API/öffentliche Vorschau bleiben
ohne diese Aktivierung. [Privater Cockpitablauf und Prüfungen](../../docs/passkey-credential-cockpit.md).

Für IP-037 bestanden 90 isolierte tatsächliche HTTPS/BFF/API/PG-Prüfpunkte
mit synthetischen P256-Daten und eigener Fixture-DB sowie neun Prüfungen
mit ausgeschalteter Vorschau ohne Faktor-/Nachweismutation. SQL, API und
Migrationen wurden dabei nicht geändert. Die 461 API-/Worker- und 120
Credentialregressionen stammen aus IP-036 und wurden für IP-037 nicht erneut
ausgeführt; physische Geräte- und Credentialabnahme bleiben offen.

Jobdetail liefert `result` oder `null` und einen begrenzten `failure_code`.
Listen liefern `result_summary` ohne Equitykurve. Ergebnisbeträge sind
Dezimalzeichenfolgen; vollständige Provenienz, getrennte Snapshot-/Simulator-
Digests, Kostenannahmen und Coverage bleiben sichtbar. Die Anzeige enthält
höchstens 2000 Kurvenpunkte mit Endpunkten, globalen Extrema und dem größten
Drawdown-Paar; die Metriken entstehen aus der vollständigen Kurve.
`validation.status` bleibt ausdrücklich `not_evaluated`. Synthetische Fixtures,
kurze Datenproben und noch offene Baskets liefern keinen Profitabilitätsnachweis.

Interne Assertions: HS256, `iss=investalo-bff`, `aud=investalo-api`, bestätigtes
`oidc_iss`/opaques `sub`, `oidc_auth_time`, `iat`, höchstens 60 Sekunden `exp`,
einmaliges UUID-`jti`, `htm`, exaktes `htu` inklusive Query und
`body_sha256` über unveränderte Bytes. Tenant-Aufrufe benötigen `tenant_id` und
aktuelles `auth_epoch` aus `/v1/me`. Browser-Identitätsheader haben keine Wirkung.
DB-Replay-Schutz, Epoch und Reauth-Schwelle gelten pro Transaktion.
Die API begrenzt Bodies vor der Framework-Validierung auf 16 KiB und entfernt
eingereichte Werte aus Validierungsfehlern.

Tests: `PYTHONPATH=services/api/src:packages/trading/src:packages/marketdata/src
python -m pytest tests/api`.
PG-Tests benötigen isoliertes lokales PostgreSQL und zusätzlich
`API_TEST_ADMIN_USER=investalo_migration` sowie
`API_TEST_ADMIN_PASSWORD_FILE`. Sie erzeugen Testdatensätze ohne destruktives
Aufräumen. Nonce-Aufbewahrung, Recovery-Operatorablauf und
Rategrenzen bleiben gesonderte Betriebsarbeit vor einem öffentlichen Pilot.
