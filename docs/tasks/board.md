# Git-basiertes Ticketboard

Stand 2026-11-07. Dieses Board ist das initiale Task-/Ticketsystem ohne
zusätzliche Tools oder externe Veröffentlichung.

Status: `READY` ausführbar, `IN_PROGRESS` aktiv, `WAITING_DECISION` benötigt
konkrete Nutzerentscheidung, `BLOCKED` benötigt Voraussetzung, `DONE` geprüft.
Ein Ticket wird mit Ergebnis, Prüfbeleg und gegebenenfalls Commit abgeschlossen.
Priorität `P0` ist kritisch, `P1` Kernumfang, `P2` Ausbau.

| ID | Prio / Phase | Status | Aufgabe | Abhängigkeit / Abnahme |
|---|---|---|---|---|
| IP-001 | P0 / P0 | DONE | Originalauftrag, Skills, Host und Referenzrepos inventarisieren | Vollständig gelesen; read-only Quellenstände in inventory.md |
| IP-002 | P0 / P0 | DONE | grill-me-Interview und gemeinsames Verständnis | Q1–Q31 bestätigt, Nutzer beauftragt Umsetzung |
| IP-003 | P0 / P0 | DONE | Struktur, Konzept und Projektdokumentation | Vollständiger Entwurf; Links/Tickets/Beispiele/Diff geprüft, im Planungsbranch gesichert |
| IP-004 | P0 / P0 | DONE | Git-Containment für Credentialpfad | Ignore + aus Tracking entfernt, lokale Datei erhalten; Resthistory dokumentiert |
| IP-005 | P0 / P0 | WAITING_DECISION | Credentialrotation und Historyremediation koordinieren | Inhalte nicht ausgeben; Rotation falls echte Keys; Rewrite/Force-Push nur explizit |
| IP-006 | P0 / P1 | IN_PROGRESS | Runtimepins und bestätigten Betriebsentwurf konkretisieren | Pins/Locks/Digests und lokaler Lauf geprüft; SMTP/Recovery/Backup/Pilot noch offen |
| IP-007 | P1 / P1 | IN_PROGRESS | Gepinntes Bootstrap und reproduzierbarer privater Start | Fünf Basisdienste plus Researchprofil aufgebaut; unabhängiger Clean-Checkout-Nachweis vor Pilot |
| IP-008 | P0 / P1 | IN_PROGRESS | Auth, Tenants, RBAC und DB-Isolation | OIDC/MFA, BFF, Einladungsprovisionierung und FORCE RLS getestet; Recovery/Registrierung/Streams folgen |
| IP-009 | P0 / P1 | BLOCKED | Credentialverschlüsselung und minimale Serviceidentitäten | IP-006/008; kein Secret in Browser/Logs/Research, Rotation/Restore geprüft |
| IP-010 | P1 / P2 | IN_PROGRESS | Crypto- und MT5-Strategien vollständig spezifizieren | Sachentscheidungen bestätigt; Regeln dokumentiert, technische Kern-/Broker-/Kausalitätsabnahme folgt |
| IP-011 | P1 / P2 | IN_PROGRESS | Marktdatenimport, Instrumentmetadaten und Snapshots | Strikte H4-Snapshots/CSV/Bitgetpagination und 90-Tage-BTC-Import geprüft; Dreijahresumfang, Datenrechte und historische Instrumentregeln offen |
| IP-012 | P0 / P2 | IN_PROGRESS | Tradingkern und unabhängige Risk Engine | Crypto-Core: 31 Tests; Offlineworker nutzt denselben Kern; MT5, Broker-/Paper-Riskintegration folgen |
| IP-013 | P1 / P3 | IN_PROGRESS | Kosten-/Fillmodell und reproduzierbare Backtests | Gefrorene Daten/Config/Kosten und echte Workerresultate geprüft; Kostenkalibrierung, Dreijahresdaten und unabhängige Holdoutabnahme offen |
| IP-014 | P1 / P3 | IN_PROGRESS | Cockpit, Portfolio und Journal | MFA/Portfolio/Journal plus Datasetwahl, tatsächliche Nettoergebnisse und Equitykurven; visuelle Browserabnahme und Paperbedienung folgen |
| IP-015 | P0 / P4 | BLOCKED | Bitget-Anbindung für Paper/Demo | IP-009/012; Capabilityvertrag, Modustrennung und Kontobindung |
| IP-016 | P0 / P4 | BLOCKED | Outbox, Executionjournal und Reconciliation | IP-015; Crash/Timeout/Doppelzustellung/Teilfill ohne Blind-Resend |
| IP-017 | P0 / P4 | BLOCKED | Kill-Switch, Schutz und Fachalarmierung | IP-016; neue Exposition, Cancel und Flatten getrennt nachweisen |
| IP-018 | P0 / P4 | BLOCKED | Backup/Restore und Betriebsabnahme | IP-007/016; extern/offline verschlüsselt, Schlüssel getrennt, RPO 24h/RTO 4h, Restore isoliert mit Brokerabgleich |
| IP-019 | P0 / P5 | BLOCKED | Livepilot vorbereiten und Freigabe einholen | IP-013/017/018; vorher vereinbarte Nettonachweise, Konto/Budget/Production konkret |
| IP-020 | P0 / P4 | BLOCKED | MT5-Heimnetzbridge und Legacyportierung im MVP | Ausgehendes HTTPS, Demo-/Gerätebindung; Auth/Risk/Lotsizing/Zeitkausalität, ein Writer/Konto |
| IP-021 | P2 / P7 | BLOCKED | Makro, Kalender und News integrieren | Rechte/Quoten/Provider geklärt; Point-in-time und Datenalter |
| IP-022 | P2 / P7 | BLOCKED | KI im Shadow Mode und Kandidatenpromotion | IP-013; Gratisprovider/Datenschutz geklärt, Wirkung/Latenz/Kosten gemessen |
| IP-023 | P2 / P8 | WAITING_DECISION | Öffentliches Kundenprodukt definieren | Privatpilot; neue Scope-, Rechts-, Lizenz- und Betriebsentscheidung |
| IP-024 | P0 / P3–P4 | IN_PROGRESS | Manuellen Crypto-Paperpuffer und Nutzerinformation umsetzen | Domainvorschau/Bestätigung/Risk implementiert; echte MFA-Schrittbestätigung, UI/Worker/optionale E-Mail folgen |
| IP-025 | P1 / P1–P3 | DONE | Lokales Fundament zur Zwischenabnahme bereitstellen | Gepinnte Builds, 82 automatisierte Tests und 28 reale HTTPS-/MFA-/BFF-Prüfpunkte bestanden; kein fertiger M1-Pilot |
| IP-026 | P1 / P2–P3 | DONE | Lokalen Daten-/Research-/Ergebnisablauf schließen | 540 reale BTC-H4-Kerzen importiert; 132 Tests und 32 reale HTTPS-Prüfpunkte bestanden, einschließlich Offlineworker und Equitykurve |

## Abschlussbelege

- **IP-001:** [inventory.md](../inventory.md), [sources.md](../sources.md);
  Auftrag und beide lokalen Skills vollständig gelesen, Referenzrepos unverändert.
- **IP-002:** [interview.md](../interview.md) ist die alleinige Übersicht der
  bestätigten und noch offenen Nutzerentscheidungen.
- **IP-004:** `git rm --cached` entfernt den Credentialpfad aus dem Index,
  die lokale Datei bleibt erhalten und ist ignoriert. Inhalte wurden nicht gelesen.
  Historien-/Rotationsarbeit bleibt IP-005.
- **IP-003:** 28 Projekt-Markdown-Dateien und 23 Tickets geprüft:
  keine defekten lokalen Links oder unbekannten Ticketreferenzen.
  Basketanteile, Durchschnitt, +5%-Marke und −50%-Stress unabhängig nachgerechnet.
  Architektur-/Tradingreview eingearbeitet; `git diff --check` sauber.
  Lokaler Planungsbranch: `docs/project-foundation`.
- **IP-006, 2026-11-07:** [deployment-plan.md](../deployment-plan.md)
  konkretisiert Compose/Authelia. Offizieller Quellenabgleich und Architekturreview
  ohne weitere Befunde; keine Installation oder Laufzeitabnahme.
  Aktueller Check: 32 Projekt-Markdown-Dateien inklusive Agentpointer,
  keine defekten Links/Ticketreferenzen; damaliger Stand Q9–Q14 bestätigt,
  Q15–Q22 offen, inzwischen durch Runde 4 beantwortet.
- **Runde 4, 2026-11-07:** Signale/Schutz und Risikoprofile übernommen;
  Notfallreserve, öffentlicher HTTPS-Pilot und E-Mail-Recoverypräferenz ausdrücklich
  als Abweichungen dokumentiert. Offizieller Authelia-Abgleich: administrative
  Faktorresets möglich, Mail-only-Selbstservice/Logout nicht pauschal zusagen.
  Q23–Q28 bleiben Vorschläge; keine Dienste, Orders oder Nachrichten ausgeführt.
  Architektur-/Tradingreview eingearbeitet; 32 Markdown-Dateien/23 Tickets ohne
  defekte Links/Referenzen. Antwortstatus und Notfallbudget-/Stress-/Cashvergleich
  unabhängig geprüft, `git diff --check` sauber.
- **Runde 5, 2026-11-07:** Q23 ersetzt automatischen Puffer durch manuellen
  Einstieg mit Nutzerinformation. Q24/Q26–Q28 bestätigt, Q25 Heimnetzhost
  laut Nutzer; [mt5-bridge.md](../mt5-bridge.md) konkretisiert ausgehendes HTTPS,
  Demo-/Gerätebindung und Fehlerszenarien. Q29/Q30 bleiben offen.
  Die bisherigen Offenstatus in den historischen Rundennotizen sind überholt.
- **Runde 6, 2026-11-07:** Q29/Q30 bestätigt. M1-Sachentscheidungen vollständig,
  [implementation-brief.md](../implementation-brief.md) bündelt den Reviewstand.
  Q31 Abschlussbestätigung ausstehend; keine Implementierung freigegeben.
  Architektur-/Tradingreview ohne weitere Befunde. 34 Markdown-Dateien/24
  eindeutige Tickets, lokale Links, Antwortstatus und Fünferstaffel-/Cashstress
  geprüft; `git diff --check` sauber. Keine Anwendungs-Laufzeitabnahme.

- **Runde 7 / IP-025, 2026-11-07:** Q31 und autonome lokale Umsetzung bestätigt.
  Branch `feat/m1-foundation`. Docker/Compose exakt gepinnt installiert;
  API/Cockpit mit Locks gebaut, Migration/IdP-Provisionierung ausgeführt.
  Alle fünf Dienste laufen; Anwendungsgesundheit geprüft und ausschließlich
  `127.0.0.1:8443` veröffentlicht. Momentaufnahme nach Login: rund 408 MiB
  Container-RAM insgesamt, keine Last-/Produktionsabnahme.
  31 Crypto-, 39 API-/echte PG-Isolations- und 12 Cockpit-Sicherheitstests
  bestanden. 28 zusätzliche reale HTTPS-Prüfpunkte einschließlich
  Passwort/TOTP, frischem OIDC, BFF/Mandant, Callback-Replay, CSRF,
  idempotenter Jobannahme und Logout bestanden.
  Unabhängige Architektur-/Tradingreviews eingearbeitet. Lokale Tests erzeugen
  ausschließlich `.invalid`-Identität; Erstregistrierung/Recovery bleiben offen.
  [Startanleitung](../../infra/README.md), [Tests](../../tests/README.md).
  Queued bedeutet persistiert, nicht verarbeitet; Worker/Daten/Broker fehlen.
  Foundationcommit `5fe3a2e` auf GitHub-Branch `feat/m1-foundation` gesichert.
  Zwischenstand-Pushes ausdrücklich autorisiert; Remote-Historie vor Push
  abgeglichen. Credential-Historienarbeit bleibt IP-005, kein Force-Push.

- **IP-026, 2026-11-07:** Öffentlicher Bitget-V3-SPOT-Import für
  2026-08-09 08:00 bis 2026-11-07 08:00 UTC: 540 abgeschlossene H4-Kerzen,
  ohne Lücken im gewählten Fenster. Dataset immutable, Daten-/Contenthash
  getrennt; Job friert Strategie und Kosten bei Annahme ein.
  Eigener Researchworker mit `SESSION_USER`-Tenantbindung, begrenzten
  DB-Funktionen und Lease/Attempttoken; Testfixtures nutzen eine separate Rolle.
  Migration 002 angewendet, 001 unverändert. Broker- und BFF-Secrets bleiben
  unerreichbar. Sechs lokale Dienste geprüft, nur `127.0.0.1:8443` veröffentlicht.
  31 Trading-, 20 Marktdaten-, 56 API-/Worker-, 21 Cockpit- und 4
  Provisionierungstests bestanden; Typecheck und gepinnte Containerbuilds grün.
  32 reale HTTPS-Prüfpunkte umfassen MFA, Datasetwahl, idempotente Annahme,
  tatsächliche Berechnung, persistierten Datenhash und Equitydarstellung.
  Ergebnis bleibt ausdrücklich nicht wirtschaftlich validiert; Dreijahresziel,
  Kostenkalibrierung und unabhängiger Holdout nicht erfüllt.
  Implementierungscommit `3a73c12` auf `origin/feat/m1-foundation` gepusht.
  [Startanleitung](../../infra/README.md), [Tests](../../tests/README.md).

## Routine

Vor Beginn Status setzen, relevante Entscheidungs-/Pitfallnotizen lesen.
Nach fachlichem Abschluss passende Prüfungen einmal ausführen, Ergebnis
dokumentieren, betroffene Generaldocs aktualisieren und Arbeit in Git sichern.
Neue Findungen als Backlogpunkt erfassen; kritische Punkte sofort als Ticket.
