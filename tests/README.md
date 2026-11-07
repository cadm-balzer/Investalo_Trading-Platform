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
  Zusätzlich36 reine und20 tatsächliche PG-Fälle für die005-Metadatenprojektion:
  fremde Nutzerbindung/Role/Epoch/GUC, Projection und unveränderte private ACLs.
  Additive006 ergänzt dauerhafte Passkeyregistry, Ticketclaim, CAS, Widerruf
  und Audit: insgesamt293 API-/Workerprüfungen grün, darunter67 tatsächliche
  Registry-/Passkey-API-PG-Fälle.
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
  115 Tests grün, einschließlich25 vorbereiteter Actionzustände,
  13 Contract-/Signerfälle,19 echter synthetischer P256-Passkeyprüfungen
  und37 Enrollmentzustands-/Registrierungsfälle.
  Die Tests prüfen Zustand und Kryptografie getrennt; ein erfolgreicher
  vollständiger BFF-Enrollmentablauf und reale Browser-/Geräteabnahme fehlen.
- `tests/infra/check_local_auth.py`: tatsächlicher HTTPS-Passwort-/TOTP-/
  OIDC-Durchlauf einschließlich BFF, Mandanten-API und Abmeldung.
  Jobannahme/Wiederholung, Parameterkonflikt und frischer Login trotz bestehender
  IdP-Sitzung werden ebenfalls geprüft.
  Ein importierter öffentlicher BTC-Snapshot wird ausgewählt und vom tatsächlichen
  Worker verarbeitet; Ergebnisdigest, Nettoauswertung und SVGkurve werden geprüft.
  Ausschließlich generierte lokale `.invalid`-Identität; keine Faktorwerte ausgeben.
  Erweiterte Prüfungen zeigen gesperrte Credentialrouten und belegen,
  dass die bestehende IdP-MFA durch Passwort-Reauth wiederverwendet werden kann.
  Enrollmentseite, Sitzung/Origin/CSRF, unbekanntes Ticket, doppelte Felder
  und fehlender Versuch sind ebenfalls geprüft.
  Insgesamt48 tatsächliche HTTPS-Prüfpunkte bestanden. `--public-preview`
  prüft dieselben Abläufe über tatsächliches DNS und System-TLS-Vertrauen
  an den öffentlichen Domains; auch dort alle48 bestanden.
- `tests/infra/test_research_provisioning.py`: atomare Rollenprovisionierung,
  Eingabegrenzen und sichere SQL-/Passwortbehandlung.
- `tests/infra/test_credentials_provisioning.py`: vier Tests für feste
  Testidentitäten, sichere Secretübergabe und abweichende DB-Owner.
- `tests/infra/test_public_preview_preparation.py`: sechs Tests gegen
  Konfigurationsdrift, YAML-Injektion nach PEM-Footer, Symlinks/Hardlinks,
  Dateirechte/-größe und Überschreiben. Gepinnte Caddy-/Autheliavalidatoren
  und zusammengeführte Compose-Grenzen geprüft.
- `tests/infra/test_public_preview_provisioning.py`: sechs Tests für die
  synthetische Ausgangsidentität, Operatorrolle, eindeutigen bestehenden Tenant,
  unterdrückte private Fehlerausgabe und geschützte Manifestdateien.
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
Echter BFF-MFA-Schrittflow, Recovery, Browser-/Geräte-Erstregistrierung, Broker-Crashfälle und
verschlüsselter externer Restore sind damit noch nicht abgenommen.
Abnahmekriterien: [Roadmap](../docs/roadmap.md), [Ticketboard](../docs/tasks/board.md).
