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
- Git-getrackter Credentialpfad bei Projektstart gefunden, Inhalte nicht gelesen.
  Historien-/Rotationsarbeit bleibt gesondert; siehe `docs/security.md`.
