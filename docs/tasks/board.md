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
| IP-002 | P0 / P0 | IN_PROGRESS | grill-me-Interview und gemeinsames Verständnis | Q1–Q30 beantwortet; Sachfrontier leer, Abschlussbestätigung Q31 offen |
| IP-003 | P0 / P0 | DONE | Struktur, Konzept und Projektdokumentation | Vollständiger Entwurf; Links/Tickets/Beispiele/Diff geprüft, im Planungsbranch gesichert |
| IP-004 | P0 / P0 | DONE | Git-Containment für Credentialpfad | Ignore + aus Tracking entfernt, lokale Datei erhalten; Resthistory dokumentiert |
| IP-005 | P0 / P0 | WAITING_DECISION | Credentialrotation und Historyremediation koordinieren | Inhalte nicht ausgeben; Rotation falls echte Keys; Rewrite/Force-Push nur explizit |
| IP-006 | P0 / P1 | IN_PROGRESS | Runtimepins und bestätigten Betriebsentwurf konkretisieren | Compose/Authelia/HTTPS/SMTP/administratives Recovery/Backupziele bestätigt; Pins und konkrete Zielabnahme vor Bootstrap/Pilot |
| IP-007 | P1 / P1 | BLOCKED | Gepinntes Bootstrap und reproduzierbarer privater Start | IP-002/006; exakte Locks/Hashes/Digests, dokumentierter Clean-Checkout-Start |
| IP-008 | P0 / P1 | BLOCKED | Auth, Tenants, RBAC und DB-Isolation | IP-007; unautorisierte Requests/Jobs/Streams/Relations abgewiesen |
| IP-009 | P0 / P1 | BLOCKED | Credentialverschlüsselung und minimale Serviceidentitäten | IP-006/008; kein Secret in Browser/Logs/Research, Rotation/Restore geprüft |
| IP-010 | P1 / P2 | IN_PROGRESS | Crypto- und MT5-Strategien vollständig spezifizieren | Sachentscheidungen bestätigt; Regeln dokumentiert, technische Kern-/Broker-/Kausalitätsabnahme folgt |
| IP-011 | P1 / P2 | BLOCKED | Marktdatenimport, Instrumentmetadaten und Snapshots | IP-010; Lizenz/Quota, Lücken, Zeit-/Preisquelle und Provenienz geprüft |
| IP-012 | P0 / P2 | BLOCKED | Tradingkern und unabhängige Risk Engine | IP-010; harte Grenzen inkl. Reservierungen/Teilfills/Zeitwechsel getestet |
| IP-013 | P1 / P3 | BLOCKED | Kosten-/Fillmodell und reproduzierbare Backtests | IP-011/012; keine Future-Leaks, reale Lots/Fees/Spread/Slippage |
| IP-014 | P1 / P3 | BLOCKED | Cockpit, Portfolio und Journal | IP-008/013; responsive Flows, Datenalter, Cashflows, Charts und Detailoverlays |
| IP-015 | P0 / P4 | BLOCKED | Bitget-Anbindung für Paper/Demo | IP-009/012; Capabilityvertrag, Modustrennung und Kontobindung |
| IP-016 | P0 / P4 | BLOCKED | Outbox, Executionjournal und Reconciliation | IP-015; Crash/Timeout/Doppelzustellung/Teilfill ohne Blind-Resend |
| IP-017 | P0 / P4 | BLOCKED | Kill-Switch, Schutz und Fachalarmierung | IP-016; neue Exposition, Cancel und Flatten getrennt nachweisen |
| IP-018 | P0 / P4 | BLOCKED | Backup/Restore und Betriebsabnahme | IP-007/016; extern/offline verschlüsselt, Schlüssel getrennt, RPO 24h/RTO 4h, Restore isoliert mit Brokerabgleich |
| IP-019 | P0 / P5 | BLOCKED | Livepilot vorbereiten und Freigabe einholen | IP-013/017/018; vorher vereinbarte Nettonachweise, Konto/Budget/Production konkret |
| IP-020 | P0 / P4 | BLOCKED | MT5-Heimnetzbridge und Legacyportierung im MVP | Ausgehendes HTTPS, Demo-/Gerätebindung; Auth/Risk/Lotsizing/Zeitkausalität, ein Writer/Konto |
| IP-021 | P2 / P7 | BLOCKED | Makro, Kalender und News integrieren | Rechte/Quoten/Provider geklärt; Point-in-time und Datenalter |
| IP-022 | P2 / P7 | BLOCKED | KI im Shadow Mode und Kandidatenpromotion | IP-013; Gratisprovider/Datenschutz geklärt, Wirkung/Latenz/Kosten gemessen |
| IP-023 | P2 / P8 | WAITING_DECISION | Öffentliches Kundenprodukt definieren | Privatpilot; neue Scope-, Rechts-, Lizenz- und Betriebsentscheidung |
| IP-024 | P0 / P3–P4 | BLOCKED | Manuellen Crypto-Paperpuffer und Nutzerinformation umsetzen | Q29/Q30 bestätigt; IP-012/014/016, Vorschau/MFA, Budget/Risk/Schutz, Idempotenz, keine Order durch Meldung |

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

## Routine

Vor Beginn Status setzen, relevante Entscheidungs-/Pitfallnotizen lesen.
Nach fachlichem Abschluss passende Prüfungen einmal ausführen, Ergebnis
dokumentieren, betroffene Generaldocs aktualisieren und Arbeit in Git sichern.
Neue Findungen als Backlogpunkt erfassen; kritische Punkte sofort als Ticket.
