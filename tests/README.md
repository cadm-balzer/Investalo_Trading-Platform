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
  und Audit;007 ergänzt den zielgebundenen Aktionsnachweis.
  Insgesamt 461 API-/Workerprüfungen grün, darunter 67 tatsächliche
  Registry-/Passkey-API-PG-Fälle und 70 neue Aktionsnachweis-PG-Fälle.
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
- `tests/credential_onboarding`: 95 Offline-Tests für gesonderte Actionassertions,
  Ziel-/Body-/MFA-Zeitbindung, strikten Triplecodec und Entwicklungsdateiprovider.
  IP-038 ergänzt36 Fälle für den getrennten Passkeyvertrag: unveränderte OIDC-
  Zeit, frische Passkey-/Freigabezeit, exakter Zweck, Actor/Sitzung/Ziel/CAS/Body,
  strikte JSON-/UTF8-/Integergrenzen und Ablehnung des alten Vertrags.
  IP-039 ergänzt18 Clientfälle für bestätigten Consumecommit, Bindungs-/Rollen-
  prüfung, dieselben Claims in separater finaler Transaktion, Fehlerredaktion,
  unbekannte Commits und fehlende automatische Wiederholungen.
  Diese synthetischen Freigaben beweisen keinen echten BFF-Schrittflow.
- `tests/credentials_storage`: 60 tatsächliche PostgreSQL-Fälle in
  `investalo_credentials_checks`: 18 Storefälle, 30 Actionautorisierungsfälle
  und 12 synthetische Bitget-/AEAD-End-to-End-Fälle.
  Drei eigene Testlogins; API/Research, fremde Nutzer, Viewer, deaktivierte
  Mitgliedschaften und manipulierte Bindungen werden abgewiesen. Replay,
  gesperrte/abgelaufene Freigaben, Recoveryepoch, veränderte UID/Parent/IP/Rechte
  und konkurrierende Speicherversionen sind abgedeckt. Insgesamt 120 Tests im
  Credential-Storage-Checkcontainer bestanden; kein echter Brokerkontakt.
- `tests/credentials_storage/test_passkey_authorization_{flow,postgres}.py`:
  IP-039 ergänzt97 tatsächliche PostgreSQL-Fälle:92 Lifecycle-/Scope-/Schema-/
  Replay-/Sperr-/Zeit-/Auditfälle und fünf private Clientdurchläufe.
  Alle drei Aktionen mit echten008-Receipts und synthetischem HS256 geprüft;
  der WebAuthnverdict bleibt synthetisch. Keine Broker-/HTTP-/Credentialausführung.
  Ein003-Registrierungsversuch prüft die Kontosperre in einem zurückgerollten
  Savepoint; der gespeicherte Kontostand wird dabei nicht verändert.
- `tests/workers`: gemeinsamer Simulatorkern, Provenienz und Lease-/Fencing-
  Negativfälle mit eigener tatsächlicher Research-Testrolle.
- `apps/cockpit/tests`: OIDC-Token/Freshness, Cookies/Sitzungen, CSRF,
  Mandantenantworten, Ergebnis-/Datasetverträge und requestgebundene Assertions.
  333 Tests grün, einschließlich25 vorbereiteter Actionzustände,
  13 Contract-/Signerfälle,19 echte synthetische P256-Passkeyprüfungen,
  37 Enrollmentzustands-/Registrierungsfälle und28 Aktionsnachweisfälle.
  IP-037 ergänzt64 HTTP-Grenzfälle,44 komplette synthetische Enrollmentabläufe
  und14 Browserprojektion-/P256-Fälle. IP-038 ergänzt68 Vertrags-/Signerfälle.
  Die physische Geräteabnahme bleibt offen.
- `tests/infra/check_passkey_assertion_interop.py`:109 Offline-Prüfpunkte mit
  echten TS/Jose-Signaturen und Pythonprüfung für drei Aktionen, Unicode,
  unveränderte Bodybytes, kurze Frist, sichere Integergrenzen und gegenseitige
  Ablehnung des alten Vertrags. Nur synthetische Receipts/Keys; keine dauerhafte
  DB-Ausgabe, Einmalverwendung oder Broker-/Browserausführung.
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
- `tests/api/test_passkey_action_api.py`:98 strenge Vertragsfälle für007;
  `test_passkey_action_api_postgres.py` und `test_passkey_action_postgres.py`:
  24+46 tatsächliche PG-Fälle mit synthetischen Identitäten/Keys, allen drei
  Aktionen, committed Claim, Originalclaims, Replay/Parallelität,
  Fristablauf während Sperren und Registrierungs-Slotrace.
- `apps/cockpit/tests/passkey-action-proof.test.ts`:28 echte synthetische
  P256-Registrierungs-/Assertion-/Orchestrierungsfälle, Vorschau-/Session-/
  Metadata-/Faktorbindung und erhaltene OIDC-Zeit. Keine physische Geräteabnahme.
- `apps/cockpit/tests/passkey-action-proof-http.test.ts`:64 Fälle für
  Default-Off, Origin/Fetch-Metadata/CSRF, duplicatefreies begrenztes JSON,
  sichere Projektion und unveränderliche autorisierte Sitzung über Body-/API-Awaits.
- `apps/cockpit/tests/passkey-enrollment-flow.test.ts`:44 komplette synthetische
  Abläufe mit tatsächlichem atomarem verschlüsseltem Versuchsspeicher,
  Originalfrist, committed Claim, einmaligem Consume und Faktorlesebestätigung.
- `apps/cockpit/tests/passkey-browser-proof.test.ts`:14 Fälle für native
  ArrayBuffer-/Base64-Umwandlung, P256-Signatur, Vorschau-/Grantbindung,
  RP/UV und begrenzte Projektion ohne private Felder.
- `tests/infra/check_passkey_browser.py`:90 tatsächliche isolierte
  HTTPS/BFF/API/PG-Prüfpunkte für vollständiges Enrollment, drei Aktionen,
  Originalclaims, Replay/Parallelität, sichere Antworten und gesperrte
  Credentialausführung;9 weitere mit ausgeschalteter Prüfseite ohne Mutation.
  Eigene synthetische Sitzungsschlüssel und administrativ bestätigte Testtickets,
  keine echte E-Mail, Authelia-Anmeldung oder Hardwareinteraktion.
  [Isolierter Start](../infra/README.md#isolierte-passkey-browserprüfung).
- `tests/infra/test_passkey_browser_preparation.py`:8 tatsächliche
  Dateirechte-/UID-/GID-Fälle gegen Symlinks, Hardlinks, Modusdrift und
  umbenannte Elternpfade. Auf eigenen temporären Verzeichnissen als root:
  `sudo python3 -m unittest discover -s tests/infra -p test_passkey_browser_preparation.py -v`.
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
Der vollständige Passkey-BFF-Durchlauf ist synthetisch geprüft. Physische
Browser-/Geräte-Erstregistrierung, öffentliche Aktivierung, Credentialintegration,
Recovery, Broker-Crashfälle und verschlüsselter externer Restore sind offen.
Die461 API-/Worker- und120 Credentialtests stammen aus IP-036; IP-037 änderte
weder SQL/API noch diese Prüfungen und hat sie nicht erneut gezählt.
IP-038 prüfte den isolierten Vertrag mit333 Cockpittests,77 Offline-Onboardingtests
und109 Interopprüfpunkten; historische PG-/HTTPS-Belege wurden nicht erneut
ausgeführt. Der neue Offlinecontainer besitzt keine Secrets oder DB-Anbindung.
Reproduktion: [isolierter Vertrag](../infra/README.md#isolierter-passkey-credential-vertrag).
IP-039 ergänzt dauerhafte Zweckfreigaben in008 und einen privaten Consume-/Lock-
Client. Migration nur in der Fixture-DB, investalo bleibt001–007.
Aktuelle Abnahme:271 Credentialtests (19 Client,95 Offline,157 tatsächliche PG;
97 neue PG) und erneut461 API-/Workertests bestanden, ebenso gepinnte
Migrate-/Credential-/API-Prüfbuilds. Kein neuer Cockpitlauf:333/109 bleiben
historische IP-038-Belege. Öffentliche Dienste unverändert/gesund/TLS200.
Neue Prüfanleitung: [dauerhafte Freigabe](../infra/README.md#dauerhafte-passkey-credentialfreigabe).
Abnahmekriterien: [Roadmap](../docs/roadmap.md), [Ticketboard](../docs/tasks/board.md).
