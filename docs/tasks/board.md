# Git-basiertes Ticketboard

Stand 2026-11-06. Dieses Board ist das initiale Task-/Ticketsystem ohne
zusätzliche Tools oder externe Veröffentlichung.

Status: `READY` ausführbar, `IN_PROGRESS` aktiv, `WAITING_DECISION` benötigt
konkrete Nutzerentscheidung, `BLOCKED` benötigt Voraussetzung, `DONE` geprüft.
Ein Ticket wird mit Ergebnis, Prüfbeleg und gegebenenfalls Commit abgeschlossen.
Priorität `P0` ist kritisch, `P1` Kernumfang, `P2` Ausbau.

| ID | Prio / Phase | Status | Aufgabe | Abhängigkeit / Abnahme |
|---|---|---|---|---|
| IP-001 | P0 / P0 | DONE | Originalauftrag, Skills, Host und Referenzrepos inventarisieren | Vollständig gelesen; read-only Quellenstände in inventory.md |
| IP-002 | P0 / P0 | IN_PROGRESS | grill-me-Interview und gemeinsames Verständnis | Q1–Q8 bestätigt; Strategie-/Betriebsdetails und Abschlussbestätigung offen |
| IP-003 | P0 / P0 | DONE | Struktur, Konzept und Projektdokumentation | Vollständiger Entwurf; Links/Tickets/Beispiele/Diff geprüft, im Planungsbranch gesichert |
| IP-004 | P0 / P0 | DONE | Git-Containment für Credentialpfad | Ignore + aus Tracking entfernt, lokale Datei erhalten; Resthistory dokumentiert |
| IP-005 | P0 / P0 | WAITING_DECISION | Credentialrotation und Historyremediation koordinieren | Inhalte nicht ausgeben; Rotation falls echte Keys; Rewrite/Force-Push nur explizit |
| IP-006 | P0 / P1 | WAITING_DECISION | Runtime-/Identity-/Betriebswahl bestätigen | Grundstack Q7 angenommen; konkrete Auswahl, Support-/Kompatibilitätsprüfung |
| IP-007 | P1 / P1 | BLOCKED | Gepinntes Bootstrap und reproduzierbarer privater Start | IP-006; exakte Locks/Hashes/Digests, dokumentierter Clean-Checkout-Start |
| IP-008 | P0 / P1 | BLOCKED | Auth, Tenants, RBAC und DB-Isolation | IP-007; unautorisierte Requests/Jobs/Streams/Relations abgewiesen |
| IP-009 | P0 / P1 | BLOCKED | Credentialverschlüsselung und minimale Serviceidentitäten | IP-006/008; kein Secret in Browser/Logs/Research, Rotation/Restore geprüft |
| IP-010 | P1 / P2 | WAITING_DECISION | Crypto- und MT5-Strategien vollständig spezifizieren | Beide im MVP; Parameter, Budget, Rearm, Schutz und Notausstieg geklärt |
| IP-011 | P1 / P2 | BLOCKED | Marktdatenimport, Instrumentmetadaten und Snapshots | IP-010; Lizenz/Quota, Lücken, Zeit-/Preisquelle und Provenienz geprüft |
| IP-012 | P0 / P2 | BLOCKED | Tradingkern und unabhängige Risk Engine | IP-010; harte Grenzen inkl. Reservierungen/Teilfills/Zeitwechsel getestet |
| IP-013 | P1 / P3 | BLOCKED | Kosten-/Fillmodell und reproduzierbare Backtests | IP-011/012; keine Future-Leaks, reale Lots/Fees/Spread/Slippage |
| IP-014 | P1 / P3 | BLOCKED | Cockpit, Portfolio und Journal | IP-008/013; responsive Flows, Datenalter, Cashflows, Charts und Detailoverlays |
| IP-015 | P0 / P4 | BLOCKED | Bitget-Anbindung für Paper/Demo | IP-009/012; Capabilityvertrag, Modustrennung und Kontobindung |
| IP-016 | P0 / P4 | BLOCKED | Outbox, Executionjournal und Reconciliation | IP-015; Crash/Timeout/Doppelzustellung/Teilfill ohne Blind-Resend |
| IP-017 | P0 / P4 | BLOCKED | Kill-Switch, Schutz und Fachalarmierung | IP-016; neue Exposition, Cancel und Flatten getrennt nachweisen |
| IP-018 | P0 / P4 | BLOCKED | Backup/Restore und Betriebsabnahme | IP-007/016; Restore isoliert, Brokerabgleich vor Execution |
| IP-019 | P0 / P5 | BLOCKED | Livepilot vorbereiten und Freigabe einholen | IP-013/017/018; vorher vereinbarte Nettonachweise, Konto/Budget/Production konkret |
| IP-020 | P0 / P4 | BLOCKED | MT5-Anbindung und Legacyportierung im MVP | Auth/Risk/Lotsizing/Zeitkausalität validiert, ein Writer/Konto |
| IP-021 | P2 / P7 | BLOCKED | Makro, Kalender und News integrieren | Rechte/Quoten/Provider geklärt; Point-in-time und Datenalter |
| IP-022 | P2 / P7 | BLOCKED | KI im Shadow Mode und Kandidatenpromotion | IP-013; Gratisprovider/Datenschutz geklärt, Wirkung/Latenz/Kosten gemessen |
| IP-023 | P2 / P8 | WAITING_DECISION | Öffentliches Kundenprodukt definieren | Privatpilot; neue Scope-, Rechts-, Lizenz- und Betriebsentscheidung |

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

## Routine

Vor Beginn Status setzen, relevante Entscheidungs-/Pitfallnotizen lesen.
Nach fachlichem Abschluss passende Prüfungen einmal ausführen, Ergebnis
dokumentieren, betroffene Generaldocs aktualisieren und Arbeit in Git sichern.
Neue Findungen als Backlogpunkt erfassen; kritische Punkte sofort als Ticket.
