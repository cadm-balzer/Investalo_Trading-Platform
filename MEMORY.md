# Langfristiger Projektkontext

Nur in direkter Hauptsession laden. Keine Credentials oder privaten Kontodaten.

- 2026-11-09: IP-050af65c51 in Mainb9d4b41 verifiziert. IP-051 auf
  feat/m1-paper-status-readmodel liefert eigenen Paperstatus/Journal via
  restricted011/API und gated Cockpitpanel.170 Tests/48Subtests inkl37PG/API,
  16 Cockpit-Vertrags-/SSR-Fälle, Typecheck/Build/Review grün.
  Normal007/Fixture011 und Prüfsummen verifiziert;011 immutable.
  Publiccontainer unverändert/gesund/TLS200; beide Flags aus.
  Q32 offen: H4-Modellpreis nur für00UTC-Tagesbasis erfordert Entscheidung;
  keine Risikoregel geändert. Betriebs-/Anzeigeaktivierung weiter IP-047.
  Kostenpräferenz: gezielte Checks, knappe Reads, ein scoped Review.

- 2026-11-09: IP-049e0cfb45 in Main1a805e5 verifiziert. IP-050 auf
  feat/m1-paper-market-worker: öffentliche echte BTC/ETH-Quotes/H4, begrenzter
  Worker/Fixture010, reale Zyklen82/84/86 und Restart88 (keine Fills).
  151Tests/48Subtests,30 echtePG; Review grün nur begrenzt. Exakte
  Mitternachtsbaseline nicht zuverlässig per REST; Dauerbetrieb gesperrt,
  neue Käufe ohne Tagesbaseline weiter gesperrt. BL-028/Nächstes IP-047:
  sicheres Tagesverfahren, permanente Entwicklungsidentität/Cockpit.
  Keine Migration/Build/Dependencies, normal007/Fixture010 unverändert.

- 2026-11-09: IP-048fe6309a in Maindc60c19 verifiziert. IP-049 auf
  feat/m1-paper-postgres-journal: atomarer PostgreSQL-Paperstore mit eigener
  SESSION_USER-Kontobindung, Revision-/Checksum-CAS, Unknowncommit-Readback.
  78 gepinnte Tests/15 Subtests,29 echte PG-Fälle, Review grün.010 nur Fixture,
  normal007/Fixture010 unveränderlich geprüft. Nie defaultmigrate/up.
  Testpasswort nach synthetischem Verbindungstrace rotiert, Fehler sanitisiert.
  Keine echten Credentials oder neue Dienste; PostgreSQL-HBA configreload,
  öffentliches Cockpit TLS200. Nächstes IP-047: Feed/Worker/Cockpitanzeige.

- 2026-11-09: User fordert LLM/API-Kosten sparen: Kontext/Ausgaben klein,
  passende gezielte Tests, keine Routine-Subagents oder wiederholten Komplettläufe.
  IP-046eb62176 in Main dd1903b verifiziert. IP-048 auf feat/m1-persistent-paper-core:
  schrittweiser PaperRunner, Restore-/Journalvertrag;84 pinnedTests/48 Subtests,
 14 neue Runnerfälle. Keine DB-Persistenz/Feeds/UI aktiviert. IP-047 bleibt
  aktiv: PostgreSQL-CAS und atomarer Journalwriter, dann Feedworker/Cockpit.


- 2026-11-08: Nutzer bestätigt IP-0450a0751b gemerged; Main073c474 verifiziert.
  Explizite Priorität nun eigentlicher Trading-/Backtestkern, danach Paper.
  Weitere Credentialbetriebsaktivierung zurückgestellt; private Brokerkeys
  für Forschung/Paper nicht nötig. IP-046 feat/m1-long-history-backtests:
  reale BTC/ETH-H4 je8766 Quellkerzen2022-08-01..2026-08-01, vor Performance
  gefroren:6576 Forschung bis2025-08-01 plus2190 reservierter Jahres-Holdout.
  Bereits ausgewertetes90-Tage-Demo liegt außerhalb. Kein Vollquellimport,
  null Holdoutjobs/-performance. Beide realen öffentlichen Entwicklungsjobs
  gespeichert, direkter deterministischer Replay exakt. BTCnet132,63/24baskets,
  ETHnet96,09/32baskets, je eigene10000USDT; keine Portfolio-/Livevalidierung.
 66 gepinnte Coretests/33 Subtests,5 ETH-Metadatenfixturetests,572 API/worker,
  je48 reale HTTPS-Punkte und Review grün. Voller API-Prüflauf braucht explizit
  PGDATABASE=investalo_credentials_checks (Fixture009); defaultnormal007
  NICHT migrieren. Öffentliche sechs Dienste unverändert/TLS200, Checksums
  normal007/Fixture009. IP-047 READY: persistentes Paper/Orders/Fills/Risk/
  Journal mit gleichem Kern und Crash/Replaytests. Kosten/holdout/MT5 offen.


- 2026-11-08: Nutzer bestätigt IP-044-Merge9555624 in Maindcb9feb, verifiziert.
  IP-045 auf feat/m1-credential-browser-flow implementiert Eingabecontroller
  mit drei Phasen, Passkey plus ausdrücklichem Änderungsconsent. Begrenzte
  Prozessfortsetzungen halten Original-Core/Ports, keine Credentialbytes.
  Private Seitenspeicherreferenzen bei Abort/Ablauf/Pagehide verwerfen,
  späte Antworten generationgebunden, unbekannte Commits nie automatisch retry.
  540 Cockpittests (100 neu), Typecheck, gepinnte Cockpit-/Nodebuilds,
  481 synthetische Controller-/HTTPS-/Dienstpunkte,460 bestehende Dienstpunkte
  und6 tatsächliche gesperrte Next-Routenchecks bestanden. Review grün.
  HTTP-Origin zuerst lesen und letzte Sitzungsassertion synchron unmittelbar
  vor Dispatch/Antwort; async Asserthelper hinterlassen eine Microtasklücke.
  Öffentliche Next-Routen wegen fehlender provisionierter BFF-Provider gesperrt.
  Aktivierte Fixture hat synthetischen Cookieresolver; reale Next-Sitzungen/
  physische Geräte und Provider-/Schlüssel-/Quota-/Recovery-/Brokerbetrieb offen.
  Keine Dependencies/SQL geändert;419/572 Python/API-Suites nicht rerun.
  DB-Prüfsummen normal007/Fixture009 unverändert, alle Testcontainer beendet,
  öffentliche sechs Dienste unverändert/gesund und reguläres Cockpit/Auth TLS200.

- 2026-11-08: IP-042 `94fb73b` in Main `6300971` verifiziert; Nutzer
  beauftragt Fortsetzung. IP-043 trennt synthetischen Credentialdienst
  von administrativem Setup/Audit. Runtime hat ausschließlich gebundenen
  Fixture-LOGIN und eigene0400-Dateien; Adminchecker hat kein LOGIN-Passwort.
  Feste Identität/008-/009-Rechte vor Listener, PG-Umgebung abgewiesen,
  exakte synthetische Guard vor Consume, create-only UUID-Ablagen.
  Neuer Branch `feat/m1-credential-development-service`.
  401 gepinnte Credentialtests/52 Subtests,10 Host-Vorbereitungstests und
  440 tatsächliche isolierte Dienstprüfpunkte bestanden; gepinnte Builds
  und unabhängiger Review grün. Image ohne Entwicklungsoption beendet
  sich vor Listener. Keine neue Migration oder Dependency; echter Broker,
  Browser-Keyannahme, Produktionsserver und Schlüsselbetrieb bleiben offen.
  Historische HTTPS-/Pipeabläufe387/329 erneut bestanden; keine additive
  Zählung überlappender Prüfpunkte. Beide DB-Ledgerprüfsummen unverändert;
  Fixturecontainer beendet, sechs öffentliche Dienste unverändert/gesund,
  Cockpit/Auth mit regulärem TLS200.

- 2026-11-08: IP-041 `cd66c3a` in Main `c573ab3` verifiziert.
  Nutzer beauftragt Fortsetzung der besprochenen Bitget-Anbindung und betont
  längere Bitcoin-Backtests. Drei Jahre BTC/ETH plus unabhängiger Holdout bleiben
  IP-011/IP-013/BL-018;90 Tage sind nur der Funktionsnachweis.
  IP-042 ergänzt private Entwicklungs-HTTPS-Adapter mit gegenseitigem TLS,
  eigenem Clientpin und separat übergebenem ursprünglichem Sitzungskontext.
  Kein Produktionslauncher, Betriebsschlüsselprovider, Browser-Keyeingang
  oder öffentlicher Aktivierungsflag. Featurebranch
  `feat/m1-credential-private-transport`; angewendete001–009 unverändert.
  376 gepinnte Credentialtests,440 Cockpittests/Typecheck,346 reale mTLS-
  Integrationsprüfpunkte bestanden, bestehende Pipevariante306 erneut geprüft.
  Unabhängiger Review ohne Blocker. Keine neue öffentliche Funktion aktiviert;
  Fixture-APIs gestoppt, sechs Vorschau-Dienste gesund und reguläres TLS200.
  Gepinnte Python-/Node-Fixture- und Cockpitbuilds bestanden.

- 2026-11-06: Neues Projekt startet ausdrücklich mit Planung und grill-me-Interview.
  Originalauftrag: `docs/project-info.md`; aktueller Stand: `docs/interview.md`.
- Q1–Q5 bestätigt: privater Pilot, Cockpit/Backtests/Paper vor Echtgeld,
  unabhängige harte Risikogrenzen, kontrollierte KI-Optimierung,
  vorhandener Server und zunächst kostenlose externe Tools/Accounts.
  TradingView Essentials ist bereits bezahlt.
- Q6–Q8 bestätigt: beide Broker im ersten Release planen; Python/FastAPI,
  Next.js/TypeScript, PostgreSQL, modularer Monolith mit getrennten Workern;
  eigene MFA-Anmeldung.
- 2026-11-07, Q9–Q14: BTC/ETH Spot ohne Hebel H4, vorhandenes XAUUSD
  Trend/Pullback H1/M15, schriftlicher Prompt maßgeblich, 25% Quote-Staffel,
  Preisabstand zum letzten Fill und −50% zum ersten Fill bestätigt.
  Docker Compose ausdrücklich gewählt, lokales Authelia/MFA bestätigt.
- 2026-11-07, Q15–Q22: RSI14/Wilder H4 und Supertrend ATR10/Wilder ×3 bestätigt.
  Sechste Tranche als Reserve; in Q23 später auf manuellen Einstieg konkretisiert.
  Crypto Paper: 10.000 USDT, je 500 Kaufprincipal +5 Kostenreserve, 6 % täglich/
  8 % Startkapitalverlust, −55%-Notausstieg zum ersten Fill. MT5 getrenntes
  Brokerdemo: 0,25 % Ideenrisiko, maximal eine Idee, 1 % täglich/5 % initial.
  Öffentlicher zentraler HTTPS-Einstieg schon für eingeladenen Privatpilot,
  bestehender kostenloser SMTP und E-Mail als gewünschter Recoverynachweis.
- 2026-11-07, Q23–Q28: Puffer manuell behalten und Nutzer informieren;
  automatischer −40%-Vorschlag verworfen. Administratives E-Mail-Recovery bestätigt.
  MT5 laut Nutzer auf anderem Server im Heimnetz; ausgehende HTTPS-Bridge planen.
  Validierungsmaßstab, RPO 24h/RTO 4h, verschlüsselte externe/offline Backups
  und abgegrenzter erster Release bestätigt.
- Q29–Q30 bestätigt: einmaliger manueller Puffer nach fünf Stufen,
  ohne RSI, weiter 5%-Preisabstand, Vorschau/MFA und unveränderte Schutzgates;
  einmalige Cockpitmeldung plus optionale E-Mail.
- Q31 bestätigt: gemeinsames Verständnis und ausdrücklicher Auftrag,
  mit lokaler M1-Implementierung zu beginnen. Branch `feat/m1-foundation`.
- Anschließend ausdrücklich: lokale Tasks/Kommandos selbstständig umsetzen,
  nicht auf Routinegenehmigungen warten; konkrete Zwischenabnahmen melden.
- Zwischencommits und GitHub-Pushes ausdrücklich beauftragt; vorhandenen
  Host-Deploy-Key verwenden. Foundationcommit `5fe3a2e` auf
  `origin/feat/m1-foundation` gepusht. Kein Force-Push/Historyrewrite;
  historischer Credential-Commit war bereits auf remote main.
- 2026-11-07: fünf lokale Compose-Dienste mit gepinnten Images/Locks,
  ausschließlich `127.0.0.1:8443`. Crypto-Core/Papersimulator, Tenant-/RLS-API,
  persistente Jobannahme und OIDC-MFA-Cockpit implementiert. Noch kein fertiger
  M1-Pilot: Worker/Daten/Broker, UI-Schritt-MFA, SMTP/Recovery/Restore fehlen.
- 2026-11-07, nächste Zwischenabnahme: immutable H4-Snapshots, öffentlicher
  Bitget-V3-Import, tenantgebundener Offlineworker und persistierte Nettoresultate/
  Equitycharts implementiert. 90 Tage BTC mit 540 lückenlosen Kerzen als
  Funktionsnachweis, kein Dreijahres-/Holdout-/Profitabilitätsnachweis.
  132 Tests +32 echte HTTPS-Prüfpunkte bestanden. Sechs lokale Dienste,
  nur Loopback8443. Migration002 angewendet; niemals nachträglich editieren.
  Broker/MT5, Paperbedienung/Step-up und Betriebsgates bleiben offen.
- Authelia 4.39.28: `max_age=0` Consentloop; offizielles Äquivalent
  `prompt=login` plus signierte Authzeit ab Flowstart. Passwort-/TOTP-Testnutzer
  sind ausschließlich generierte lokale `.invalid`-Daten.
- Referenzsysteme liegen lokal unter `/opt/investalo-trading-system` und
  `/opt/investalo-autotrader`. Read-only Wiederverwendungsprüfung, keine Änderung
  laufender Systeme. Befunde: `docs/inventory.md`.
- Produktionsdeployment und Echtgeldfreigabe nicht aus Konzeptzustimmung ableiten.
- 2026-11-07, Ergänzung nach Q31: Nutzeraccount bei Bitget ist Classic mit
  getrennten Spot-/Futures-Wallets und Guthaben. Jeder Plattformnutzer erstellt
  eigenen APIKey+Secret+Passphrase im eigenen Bitget-Konto. Classic V2 zuerst,
  zunächst lesende echte Kontodaten/Paper; keine Budgetvermischung,
  Wallettransfers oder Futures-/Livefreigabe. `docs/bitget-connection.md`.
- 2026-11-07: isolierter Classic-V2-Readkern mit UID-Lernprobe und gebundenen
  Walletabfragen implementiert. 24 Offline-Tests plus unabhängiger Review grün.
  Keine tatsächliche Verbindung; Vault/API/UI und Egress-/DB-/Quotaabnahme offen.
- 2026-11-07: Nutzer akzeptiert Classic-Bitget-Zwischenabnahme `3052560`
  und übernimmt den Hauptbranchmerge selbst. Tatsächlicher GitHub-Hauptbranch
  heißt `main`; Mergezusage nicht als bereits erfolgten Merge behandeln.
- 2026-11-07: Nutzer bestätigt Merge und Fortsetzung. `3fd95b1` als Vorfahr von
  `origin/main` bei `d3b31e2` verifiziert; Branch `feat/m1-credential-envelope`.
  Isolierter AES-GCM-Envelopekern mit 20 Tests, unabhängiger Review und gepinntem
  Offline-Container geprüft. Keine echte Keyannahme; DB/Service-/Rootkeybetrieb,
  aktuelle Revisionsquelle und externer Restore bleiben IP-009/BL-022.
- Git-getrackter Credentialpfad bei Projektstart gefunden, Inhalte nicht gelesen.
  Historien-/Rotationsarbeit bleibt gesondert; siehe `docs/security.md`.
- 2026-11-07: Envelopecheckpoint `7f83b33` auf main71e57f1 verifiziert.
  Neuer Branch `feat/m1-credential-storage`: private gebundene LOGINs,
  aktuelle DB-AAD, CAS, authentifizierter Rewrap und terminaler Widerruf.
  19 Client +18 echte PG-Tests, vier Provisionierungstests und zurückgerollte
  Driftprobe bestanden. 003 ausschließlich in investalo_credentials_checks
  angewendet; gewöhnliche investaloDB bleibt002. Checkprofil besitzt bewusst
  Migrationscredentials, kein Betriebsdienst. Noch kein Provider/HTTP/MFA-
  Keyeingang oder echter Brokerkey. IP-029 abgeschlossen, IP-009 bleibt aktiv.
- 2026-11-07: Nutzer bestätigt Storemerge; `46860ab` auf mainb3030de verifiziert.
  Branch `feat/m1-bitget-onboarding`: private Classic-Probe mit Triplecodec,
  Store und einmaliger body-/actiongebundener Assertion verbunden.
  JTI vor Probe konsumiert; Actor/Epoch/Reauth/Konto/Zeit/Versionen werden
  vor Write/Audit in gleicher Transaktion erneut geprüft. UID/Parent bleiben
  bei Keywechsel fest; Widerruf ohne Probe/alten KEK. Expliziter Entwicklungs-
  Dateiprovider mit unabhängig vertrauenswürdigen festen Fingerprints.
  120 Tests bestanden (19 Client, 41 Units, 60 echte PG), unabhängige Reviews.
  004 nur Fixture-DB angewendet und unveränderlich, gewöhnliche DB bleibt002.
  SQL prüft keine JWTs; direkte003-Funktionen sind Trusted-Service-Primitiven.
  Kein echter BFF-MFA-Schrittflow, HTTP-Keyeingang, Betriebsprovider oder
  Brokerkontakt. IP-030 abgeschlossen; BL-021/022 und BL-024 bleiben offen.
- 2026-11-07: Onboardingmerge69a1f8b auf main56070ba verifiziert;
  Branch `feat/m1-credential-step-up`. Additive005 bietet autorisierte
  eigene Konto-/Verbindungsmetadaten ohne UID/Envelope/Keymaterial.
  001–005 jetzt in beiden lokalen DBs angewendet und unveränderlich.
  112 API-/Worker- und erneut120 Credentialtests bestanden.
  Vorbereitete Sitzung-/CSRF-/Actor-/Epoch-/Target-/CAS-Bindung und eigener
  Grant-Previewtoken; alle sensitiven Server-/UI-Schritte bleiben gesperrt.
- Authelia4.39.28 erhält beim Passwort-Reauth den alten zweiten Faktor.
  `auth_time`/`amr=mfa` beweisen keine frisch verwendete MFA; D-027 gilt nur
  für frische Anmeldung. Nutzer hat zusätzlichen kostenlosen Cockpit-Passkey
  ausdrücklich bestätigt. Isolierter SimpleWebAuthn14.1.0-Verifier mit19
  echten synthetischen P256-Signaturtests; volle Cockpitsuite78 grün.
  Dauerhafte Faktorregistrierung/CAS/Counter/Widerruf/Audit und Browserflow
  folgen IP-033. Session-TTL-Store nicht als Passkeyregistry verwenden;
  lokale Prüfzeit niemals als IdP-Claim ausgeben. Keine echte Keyannahme.
- Abschließend310 automatisierte Prüfungen und40 echte HTTPS-Prüfpunkte grün;
  letztere belegen dedizierte Passwort-Reauth mit altem zweiten Faktor.
  Typecheck, gepinnte Builds, Migrationsprüfsummen und sechs gesunde lokale
  Dienste geprüft; weiterhin nur127.0.0.1:8443. IP-031/032 abgeschlossen,
  dauerhafte Passkeyverwaltung und Browserflow bleiben IP-033.
- 2026-11-07: Schrittflowcheckpoint d57bd56 auf mainb6198f7 verifiziert;
  Branch feat/m1-passkey-registry. Additive006 und lokales BFF/UI-Enrollment
  mit administrativ E-Mail-bestätigtem Einmalticket implementiert. Claim vor
  Crypto committed, session-/CSRF-/Origin-/Actor-/Epoch-/RP-gebundene Versuche,
  dauerhafte FORCE-RLS-Registry/CAS/Audit. Widerruf invalidiert globale Epoch.
  Beide DBs001–006 immutable.528 Tests und48 HTTPS-Prüfpunkte grün,
  Typecheck/Builds/Migrationsprüfung und zwei Reviews bestanden.
  fmt=none bleibt Kandidat; Kontoänderungen gesperrt. Positiver kompletter
  BFF-Enrollmentablauf, echte Browser-/Geräteabnahme und frische zielgebundene
  Assertions/Grants folgen IP-033; terminales Recovery bleibt BL-025.
- 2026-11-07: Registrymerge6a18102 auf mainf422a90 verifiziert.
  Nutzer meldet public-domain SSL-Fehler; Hostaudit findet nurLoopback8443,
  DNS cockpit→eigene5.45.96.83,80/443 verweigert und auth-DNS fehlt.
  Geprüftes inaktives HTTPS-Overlay/Renderer auf feat/m1-https-entry vorbereitet.
  Keine ACME-/DNS-/Port-/Identitätsänderung. IP-035 wartet auf Aktivierung/
  auth-DNS und öffentliche Issuer-Nutzerbindung; keine automatische Migration.
- 2026-11-07, anschließende ausdrückliche Nutzerfreigabe: öffentliche
  Entwicklungsvorschau aktiviert. Beide Domains zeigen auf5.45.96.83 und haben
  gültige LE-Zertifikate bis2027-02-05; zentral ausschließlich80/443.
  Zwölf Helpertests und48 öffentliche HTTPS-/MFA-/Backtestprüfpunkte bestanden,
  Zertifikate nach Neustart und alte Identitäts-/Worker-/Datasetbindung bestätigt.
  Öffentlicher synthetischer Nutzer explizit im bestehenden Entwicklungstenant.
  Laufende Dienste immer mit `--file infra/compose.public-preview.yaml` bedienen;
  Defaultprofil bleibt lokal. IP-035 erledigt, IP-033/BL-026 und vollständige
  Pilot-/Produktionsabnahme bleiben offen; Kontoänderungen/Echtgeld gesperrt.
- 2026-11-07, Fortsetzung nach Browserabnahme: Nutzer bestätigt Login mit
  Google Authenticator und Merge. HTTPS35960f3 in Maine741c6b verifiziert,
  Branch feat/m1-passkey-action-proof. IP-036 implementiert internen dauerhaften
  zielgebundenen Nachweis007: Claim vor Crypto committed, einmalige RP-Challenge,
  Counter/CAS und Grant atomar, Vorschauhash vor einmaligem Confirm geprüft.
  Originale OIDC-Zeit bleibt unverändert, Passkey checked_at getrennt.
  724 Tests, Typecheck, gepinnte Builds und unabhängige Reviews grün.
  Beide DBs001–007 angewendet/immutable; Vorschaucontainer nicht neu erstellt.
  Browserrouten/003/004-Credentialausführung bleiben off. Vollständiges
  BFF-Enrollment, physische Geräteabnahme und Browserintegration IP-033;
  Betriebsretention/-limits BL-017, Recovery BL-025.
- 2026-11-08, erneute Fortsetzung nach bestätigtem Merge:9b47ae1/4c9f63f in
  Main2c996d5 verifiziert, Branch feat/m1-passkey-browser-proof. IP-037 ergänzt
  ausdrücklich gated Prüfseite mit Vorschau/Assertion/einmaliger Bestätigung.
  HTTP-CSRF-autorisierten Session-Snapshot bis zum Adapter erhalten, Originalclaims
  und Frist nach Awaits erneut prüfen. Enrollment nach Speicherung autoritativ
  lesen; vollständiger positiver Ablauf jetzt synthetisch belegt.
  265 Cockpittests, Typecheck/Build,90+9 tatsächliche isolierte HTTPS/BFF/API/PG-
  Prüfpunkte und8 Dateivorbereitungstests grün; unabhängiger Review ohne Restblocker.
  Eigene Testkeys/Fixture-DB/fester tmp-State, keine öffentlichen Ports.
  Testdienste angehalten, öffentliche Vorschau unverändert/gesund/TLS200.
  Default/public Proofflag off, Credentialrouten503/003/004 gesperrt. Physischer
  Geräteaufruf, echte E-Mail-Attestierung, öffentliche Aktivierung und Credential-
  integration weiter IP-033; Recovery BL-025, Betriebsgrenzen BL-017.
- 2026-11-08, Fortsetzung nach erneutem Nutzermerge:84f7633 in Main512c096
  verifiziert; Branch feat/m1-passkey-credential-handoff. IP-038 isoliert neuen
  TS-/Python-Passkey-Credentialvertrag mit eigenem Zweckreceipt/Audience und
  exakter Actor-/Session-/Ziel-/CAS-/Metadaten-/Bodybindung. Ursprüngliche OIDC-
  Zeit bleibt erhalten; frische Passkey-/Autorisierungszeiten getrennt, kein AMR
  erfunden.007-Prüfbestätigung ist keine Credentialzustimmung.
  333 Cockpittests,77 Offline-Onboardingtests auf Host/gepinntem Python3.14.10,
  109 reale TS/Jose-/Python-Interopprüfpunkte, Typecheck/Build und Review grün.
  Optionales Offlineprofil ohne Netzwerk/Secrets/Mounts/DB; sechs laufende
  öffentliche Dienste unverändert/gesund/TLS200, Nachweisflag weiter off.
  Keine neue Migration/DB-Ausgabe/Consume/HTTProute/Broker-/Credentialausführung.
  Künftige008 muss explizite Zweckfreigabe global einmalig vor Probe konsumieren
  und aktuelle Bindungen bei Annahme/Write prüfen. Physische Abnahme,
  echte E-Mail, Integration/Recovery/Betriebsgrenzen bleiben eigene Gates.
- 2026-11-08, Fortsetzung nach bestätigtem Merge:8bb64db in Main13ba2e2
  verifiziert; Branch feat/m1-passkey-credential-authorization. Nutzer erneuert
  ausdrücklich autonome lokale Befehle ohne wiederholte Genehmigungsfragen.
  IP-039 implementiert008 mit Zweck/Origin/Bodydigest vor Passkey, ausdrücklichem
  Consentreceipt, globalem Einmalverbrauch und separatem finalem Transaktionslock.
  Privater Pythonclient prüft JWT vor DB und liefert Handle erst nach bestätigtem
  Consumecommit; unbekannte Commits niemals automatisch wiederholen.
  Aktuelle Actor/Epoch/Faktor/Metadaten/CAS/Original-OIDC/Frist an beiden Grenzen.
  271 Credential- und461 API-/Workertests, gepinnte Builds und Review grün.
  008 nach zurückgerollter Vorprüfung ausschließlich Fixture-DB; investalo001–007.
  Angewendete Migrationen immutable. Öffentliche sechs Dienste unverändert/
  gesund, reguläres TLS HTTPS200. Kein HTTP-/Broker-/003/004-Executor.
  Nächster Schritt private Credentialwriterintegration; physische Geräteabnahme,
  echte E-Mail/Keyeingabe, öffentliche Aktivierung, Recovery/Betrieb weiter offen.
- 2026-11-08, Fortsetzung nach bestätigtem Merge:389082a in Mainbe13145
  verifiziert; Branch feat/m1-passkey-credential-execution. IP-040 verbindet
  private Passkeyfreigabe mit synthetisch geprüftem Classicprobe/AEAD-Writer:
  committed008-Consume vor Read/Probe, separate008-Lock+003-Write+009-Abschluss-TX.
  009 immutable FORCE-RLS-Terminalaudit prüft exactsameclaims/LOGIN/Lock-XID,
  aktuellen Actor/Faktor/Account und erlaubten neuen Connection-CAS-Zustand.
  Deadline nach letztem Auditwartepunkt prüfen. Fehler rollen finale TX zurück,
  Consume bleibt. Verlorene Commitantworten niemals automatisch wiederholen;
  erfolgreicher Abschluss wird nicht durch best-effort failed überschrieben.
  009 nach vollständig zurückgerollter DDL/echtem failedfinish-Preflight nur in
  investalo_credentials_checks angewendet; investalo weiter001–007,001–008unverändert.
  Keine HTTP-/öffentliche/echte Brokeraktivierung. Physische Geräteabnahme,
  echte E-Mail/Browser-Keyeingabe, eigene Signatur-/Betriebsidentität,
  Egress/Quota, Recovery und Pilotbetrieb bleiben gesondert.
  356 gepinnte Credentialtests (19 Client,116 Offline,221 tatsächliche PG;
  64 neue PG) und461 API-/Workertests gegenFixture009 bestanden, insgesamt817.
  Gepinnte Builds und unabhängiger Review ohne Restblocker. Öffentliche sechs
  Dienste unverändert/gesund/TLS200. Nächster Schritt Cockpit-/Browseranbindung.
- 2026-11-08, Fortsetzung nach bestätigtem Merge3476f74 in Main0fd25b6:
  IP-041 auf feat/m1-passkey-credential-cockpit verbindet privaten BFF-Kern,
  default-off008 API-Zweckrouten und privaten Credentialexecutor.
  Vollständige ursprüngliche Session/CSRF/Origin/OIDC nach Await prüfen;
  eigene Credentialzustimmung, exakter privater Body nur im Aufruferspeicher,
  separate Signaturidentität und strikte Receipt-/Target-/CAS-Bindung.
  572 API-/Workertests (111 neue),385 Cockpittests (52 neue),299 tatsächliche
  integrierte TS/WebAuthn/HTTPS/API/PG/Jose/Python/AEAD/009-Prüfpunkte grün.
  Typecheck, gepinnte Builds und unabhängige Reviews bestanden.
  Relative Zeitparameter eines bestehenden Tests erst bei Testaufruf berechnen;
  API-/SQL-Regeln unverändert. Erstlauf Container-DNS vorübergehend ausgefallen.
  Nutzer rebootete Host; /tmp-Fixtureablage verschwunden und mit vorhandenem
  geschützten Prepare-Script neu erzeugt. Alle öffentlichen Dienste wieder gesund;
  reguläres TLS HTTPS200 bestätigt. Nur Fixture-APIs mit neuen synthetischen
  Secrets neu erstellt, nach Abschluss gestoppt. DBstände001–007/001–009 geprüft.
  Keine neue Migration, Dependency oder öffentliche Credentialaktivierung.
  Historische356 Credentialtests nicht neu gezählt. Nächste Arbeit:
  tatsächliche Browser-Keyannahme, physische Geräteabnahme, eigener
  Credentialdienst/Signingprovider und realer Transport/Egress; kein Live.
- 2026-11-08, Nutzer bestätigt Merge des isolierten Dienstes IP-043:
  998bb90 in Main9f2a9a5 verifiziert. IP-044 auf
  feat/m1-credential-asgi-transport ersetzt dessen stdlib HTTP durch die
  bestehenden Uvicorn0.54.0/h110.16.0/click8.5.1-Pins samt Hashes.
  Kontrollierte asyncio-Socketübergabe, Clientpin vor Parser, Rawframing
  vor h11-Normalisierung und absolute20s seit Socketannahme.
  Vier Verbindungen inkl. Handshake und vier Executorarbeiten getrennt begrenzt;
  laufende Futures halten den Arbeitsslot trotz Disconnect/Timeout/Shutdown.
  Kein Retry bei unbekanntem Commit; debug=False/workers=1 ausdrücklich gesetzt.
  419 gepinnte Credentialtests/52 Subtests mit18 neuen TLS-/ASGI-Fällen und
  451 tatsächliche getrennte TS/WebAuthn/API/PG/Python/mTLS-Prüfpunkte bestanden.
  Beide Pythonbuilds und unabhängiger Review grün; Launcher ohne
  --development abgewiesen. Nur synthetische Keys/Broker, keine Migration/
  öffentliche Aktivierung/Produktionsabnahme. Alte440 Cockpit/572 APIfälle
  und zusätzliche historische HTTPS-/Pipeläufe nicht erneut gezählt.
  Testcontainer gestoppt, sechs öffentliche Dienste unverändert/gesund/TLS200;
  alle Migrationsprüfsummen normal007/fixture009 geprüft.
  Schlüsselbetrieb, provisionierte Identitäten, Quoten/Reconciliation/Recovery,
  echter Broker und Browser-/physische Abnahme bleiben offene M1-Gates.
