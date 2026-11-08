# Langfristiger Projektkontext

Nur in direkter Hauptsession laden. Keine Credentials oder privaten Kontodaten.

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
