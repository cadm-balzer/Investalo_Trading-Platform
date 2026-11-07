# Verifikation

Schwerpunkte: deterministische Handelsregeln und Kostenrechnung, Tenantisolation,
Brokeradapterverträge, unklare Orderantworten, Crash/Replay, Risikogrenzen,
Zeitwechsel, Credentialrotation und Restore vor erneutem Handelsstart.

Das lokale Fundament besitzt ausführbare Tests:

- `tests/trading`: deterministische Signale, Kosten/Budgets, Teilfills,
  Unsicherheit/Replay, Schutz, Tageswechsel und manuelle Reserve.
- `tests/api`: API-Authentifizierung, Payloadgrenzen und echte PostgreSQL-
  Integration für Rollen, FORCE RLS, Relationstrennung, Jobidempotenz,
  immutable Snapshots und Holdoutschutz.
- `tests/marketdata`: Zeit-/OHLC-/Digest-/Coveragevalidierung, sichere CSV-
  Kennzeichnung und deterministische öffentliche Bitget-Pagination.
- `tests/bitget`: 24 Offline-Tests für Classic-V2-Signaturen, feste GET-Pfade,
  TLS/Redirect-/Antwortgrenzen, Nutzer-/UID-/Parent-/Rechte-/IP-Prüfungen und
  getrennte Walletdaten. Erfundenes Keymaterial und gemockter HTTPS-Transport;
  kein tatsächlicher Brokeraufruf. [Testkommando](../integrations/bitget/README.md).
- `tests/credentials`: 20 Tests mit echter AES-GCM-Bibliothek und ausschließlich
  erfundenen Schlüsseln. Referenzvektor, AAD-/Ciphertextmanipulation,
  Nutzer-/Kontobindung, KEK-Rotation, lokale Envelopewiederherstellung,
  Größen-/JSON-/Base64grenzen und Redaktion. Gepinnter Testcontainer ohne Netzwerk
  oder Secrets; kein externer Vault-/Backup-/Restorebeleg.
- `tests/credential_store`: 19 Clienttests für aktuelle DB-Bindung, frische
  Transaktionen, Versionskonflikte, Rotation, Widerruf und Fehlerredaktion.
- `tests/credential_onboarding`: 41 Offline-Tests für gesonderte Actionassertions,
  Ziel-/Body-/MFA-Zeitbindung, strikten Triplecodec und Entwicklungsdateiprovider.
  Diese synthetischen Freigaben beweisen keinen echten BFF-Schrittflow.
- `tests/credentials_storage`: 60 tatsächliche PostgreSQL-Fälle in
  `investalo_credentials_checks`: 18 Storefälle, 30 Actionautorisierungsfälle
  und 12 synthetische Bitget-/AEAD-End-to-End-Fälle.
  Drei eigene Testlogins; API/Research, fremde Nutzer, Viewer, deaktivierte
  Mitgliedschaften und manipulierte Bindungen werden abgewiesen. Replay,
  gesperrte/abgelaufene Freigaben, Recoveryepoch, veränderte UID/Parent/IP/Rechte
  und konkurrierende Speicherversionen sind abgedeckt. Insgesamt 120 Tests im
  Credential-Storage-Checkcontainer bestanden; kein echter Brokerkontakt.
- `tests/workers`: gemeinsamer Simulatorkern, Provenienz und Lease-/Fencing-
  Negativfälle mit eigener tatsächlicher Research-Testrolle.
- `apps/cockpit/tests`: OIDC-Token/Freshness, Cookies/Sitzungen, CSRF,
  Mandantenantworten, Ergebnis-/Datasetverträge und requestgebundene Assertions.
- `tests/infra/check_local_auth.py`: tatsächlicher HTTPS-Passwort-/TOTP-/
  OIDC-Durchlauf einschließlich BFF, Mandanten-API und Abmeldung.
  Jobannahme/Wiederholung, Parameterkonflikt und frischer Login trotz bestehender
  IdP-Sitzung werden ebenfalls geprüft.
  Ein importierter öffentlicher BTC-Snapshot wird ausgewählt und vom tatsächlichen
  Worker verarbeitet; Ergebnisdigest, Nettoauswertung und SVGkurve werden geprüft.
  Ausschließlich generierte lokale `.invalid`-Identität; keine Faktorwerte ausgeben.
- `tests/infra/test_research_provisioning.py`: atomare Rollenprovisionierung,
  Eingabegrenzen und sichere SQL-/Passwortbehandlung.
- `tests/infra/test_credentials_provisioning.py`: vier Tests für feste
  Testidentitäten, sichere Secretübergabe und abweichende DB-Owner.
- `tests/infra/check_credentials_role_drift.py`: tatsächliche Ablehnung von
  administrativen Delegationsrechten nach erfolgreichem Baselinezugriff;
  Änderung bleibt in einer zurückgerollten Transaktion.

Start- und Testkommandos: [infra/README.md](../infra/README.md).
Integrationstests verwenden separate Testfixtures und echte Runtime-/Migrationsrollen.
Die separat provisionierte Research-Testrolle verändert ausschließlich ihre
Fixturebindung, niemals die Identität des laufenden Researchworkers.
Das Credential-Prüfprofil besitzt bewusst Migrationscredentials; nur seine
Credential-Testlogins sind auf die Fixture-DB beschränkt. Synthetische
Testverbindungen bleiben dort append-only, Testrollenbindungen werden neu gesetzt.
Echter BFF-MFA-Schrittflow, Recovery, WebAuthn-Erstregistrierung, Broker-Crashfälle und
verschlüsselter externer Restore sind damit noch nicht abgenommen.
Abnahmekriterien: [Roadmap](../docs/roadmap.md), [Ticketboard](../docs/tasks/board.md).
