# Verifikation

IP-054:34 gezielte gepinnte Pythonfälle, fünf stdlib-Provisionierungsfälle,
17 Cockpit-Vertrags-/SSR-Fälle und29 tatsächliche HTTPS-/OIDC-/MFA-/BFF-Prüfpunkte
grün. Vollständige normale008–012-Preflights zurückgerollt; danach atomar
angewendet und beide012-Ledger bestätigt. [Vertrag](../docs/paper-preview-integration.md).

IP-053:44 gezielte gepinnte Runtime-/Workerfälle, drei stdlib-Dateischutztests
und tatsächliche stabile Provisionierungs-/Drift-/TLS-/Sessionprüfungen grün.
Wiederholung bei angehaltenem Dienst: `python3 infra/scripts/check-paper-development.py`;
Workerfälle: `bash infra/scripts/check-paper-storage.sh -k 'runtime or test_worker'`.
[Vertrag](../docs/paper-development-runtime.md).

IP-052:190 unterschiedliche gezielte Fälle/48 Subtests grün, davon43 tatsächliche PG/API. Vollauf189 grün; ungültige Test-OHLC korrigiert und Neustart-/CLI-Fälle gezielt3 grün. Tagesbewertung vor sofortigem Verkauf, Restart/Commitverlust, fehlende/revidierte Grenzkerzen und tatsächlicher RSI-Intent/späterer Quote-Fill geprüft.17 Cockpit-Vertrags-/SSR-Fälle, Typecheck und gepinnter Build grün. Keine breite Credential-/HTTP-Wiederholung. [Vertrag](../docs/paper-midnight-basis.md).

IP-046:15 neue Fenster-/CLI-Tests prüfen Mehrjahrespartition, Leap Year,
Lücken, Zeitgrenzen, unveränderte Preise/Provenienz und Create-only-Ausgaben.
Fünf Fixturetests prüfen ETH-Dataseterkennung aus begrenzten gepinnten JSON-
Clientprops. Das ist keine Browser-Hydrationsabnahme. Der HTTPS-Checker kann
jetzt BTC oder ETH prüfen; `check_long_research.py` vergleicht ausschließlich
Forschungsresultate mit deterministischem Replay und kontrolliert reservierte
Holdoutmetadaten/null Holdoutjobs in einer Read-only-Transaktion.

Der vollständige API-/Workersatz braucht die Fixture-DB mit008/009:

```bash
bash infra/scripts/compose.sh --profile checks run --rm --no-deps -T \
  -e PGDATABASE=investalo_credentials_checks api-checks
python3 -m unittest discover -s tests/infra -p test_research_client_metadata.py -v
python3 tests/infra/check_long_research.py
```

Das normale `investalo` bleibt001–007; niemals für einen Testfehler migrieren.
Aktuelle Prüfergebnisse: [IP-046](../docs/long-history-backtests.md).

IP-042: `tests/credential_onboarding/test_private_http.py` prüft den privaten
Entwicklungsadapter mit tatsächlichen lokalen mTLS-Sockets, unabhängigen
Kontext-/Body-/Framingnegativfällen, Pflichtpin und Ressourcenlimits.
`apps/cockpit/tests/passkey-credential-executor.test.ts` prüft den TS-Client
mit Transportfehlern, strikten Antworten und fehlendem automatischem Retry.
`check_passkey_credential_cockpit.py --orchestrate --https` verbindet diese
Grenze mit tatsächlichem WebAuthn/Jose/HTTPS/API/PG/AEAD/009 in der synthetischen
Fixture. Keine realen Nutzerkeys, Browsergeräte oder Broker.
[Ausführung und Grenzen](../docs/passkey-credential-https.md).

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
- `tests/credential_onboarding`: 116 Offline-Tests für gesonderte Actionassertions,
  Ziel-/Body-/MFA-Zeitbindung, strikten Triplecodec und Entwicklungsdateiprovider.
  IP-038 ergänzt36 Fälle für den getrennten Passkeyvertrag: unveränderte OIDC-
  Zeit, frische Passkey-/Freigabezeit, exakter Zweck, Actor/Sitzung/Ziel/CAS/Body,
  strikte JSON-/UTF8-/Integergrenzen und Ablehnung des alten Vertrags.
  IP-039 ergänzt18 Clientfälle für bestätigten Consumecommit, Bindungs-/Rollen-
  prüfung, dieselben Claims in separater finaler Transaktion, Fehlerredaktion,
  unbekannte Commits und fehlende automatische Wiederholungen.
  IP-040 ergänzt21 private Executorfälle: Consume vor Read/Probe, gemeinsamer
  Lock/Write/Abschluss, Rollback, echte Unterscheidung unbekannter Commitantwort,
  Fehlerredaktion und Widerruf ohne Schlüssel/Probe.
  Diese synthetischen Freigaben beweisen keinen echten BFF-Schrittflow.
- `tests/credentials_storage`: ursprüngliche60 PostgreSQL-Fälle aus IP-030 in
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
- `tests/credentials_storage/test_passkey_{completion_postgres,onboarding_flow}.py`:
  IP-040 ergänzt48 Abschlussfälle und16 tatsächliche private Executorflows.
  Echte008-Receipts, synthetisches HS256, tatsächliche AEAD-Storeänderungen und
  injizierte Classicantworten prüfen alle drei Aktionen, Konkurrenz, Recoveryepoch,
  geänderte Metadaten/CAS, verlorene Commitantworten und atomaren009-Abschluss.
  Gezielte Audit-Sperrwartezeit prüft die Frist nach Mutation und vollständigen
  Rollback von Write/Lock/Abschluss bei erhaltenem Consume.
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
IP-040: vollständige356 Credentialtests bestanden,19 Client+116 Offline+221
tatsächliche PG.64 neue PG-Fälle (48 Abschluss+16 Executor) und21 neue
Offlinefälle. Reproduktion: [private Ausführung](../infra/README.md#private-passkey-credentialausführung).
461 API-/Workertests gegen Fixture009 erneut bestanden; insgesamt817 Tests.
Gepinnte Builds/Review und reguläres öffentliches TLS200 grün, Runtime unverändert.
Abnahmekriterien: [Roadmap](../docs/roadmap.md), [Ticketboard](../docs/tasks/board.md).

IP-041 ergänzt52 Cockpit-Orchestrierungsfälle mit echtem synthetischem P256
und Jose: vollständige ursprüngliche Session, eigener Credentialzweck,
unveränderte Bodybytes, strikter Receipt/Target/CAS, asynchrone Drift und sichere
Ergebnisprojektion. Die gesamte Cockpitsuite umfasst385 bestandene Tests;
Typecheck bestanden.111 neue API-Fälle (87 Unit,24 tatsächliche PG) prüfen
deaktivierte Defaults, strikte Eingabe-/Receiptgrenzen, eigenen Actor,
Original-OIDC, Replay, CAS, Rollback und proof-only-Ablehnung.

`tests/infra/check_passkey_credential_cockpit.py --orchestrate` verbindet zwei
isolierte gepinnte Checkcontainer über begrenzte private Prozesspipes.
299 tatsächliche TS/WebAuthn/HTTPS/API/PG/Jose/Python-Prüfpunkte bestanden:
Register, Replace und Revoke mit AEAD-/009-Abschluss sowie Bodydrift-/Replay-
Ablehnung. Nur synthetische Keys und Brokerantworten; keine physische
Geräteabnahme. Prüfanleitung: [privater Cockpitablauf](../infra/README.md#privater-cockpit-credentialablauf).
Die vollständige abschließende API-/Workerregression umfasst572 bestandene Tests.
Gepinnte API-/Cockpit-/Fixturebuilds und unabhängige Reviews bestanden.
Historische356 Credentialtests aus IP-040 werden nicht erneut gezählt;
private Python-/SQL-Implementierung und001–009 bleiben unverändert.
