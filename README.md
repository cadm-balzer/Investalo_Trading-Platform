# Investalo Trading Platform

Mandantenfähiges Trading-Cockpit mit Portfolio, Journal, Backtests und
automatisiertem Handel über Bitget und MetaTrader 5.

**Stand: 2026-11-07 — M1-Implementierung gestartet, Q31 bestätigt.**
Das lokale Fundament läuft über Docker Compose: Cockpit, FastAPI, PostgreSQL,
Authelia und zentraler HTTPS-Proxy. Versionen, Imagedigests und Paketlocks sind
festgelegt. Der deterministische Crypto-Kern und ein isolierter Offline-
Researchworker sind implementiert. Backtests verwenden unveränderliche H4-
Snapshots und zeigen gespeicherte Nettoergebnisse, Kosten und Equitykurven.
Der vollständige erste Release mit beiden Brokerpfaden bleibt in Umsetzung.
Crypto startet mit BTC/ETH Spot ohne Hebel auf H4; MT5 mit XAUUSD Trend/Pullback.
RSI-/Supertrend-Regeln sowie Paper-/Demolimits sind bestätigt.
Die sechste Crypto-Tranche bleibt ausschließlich für einen manuellen Einstieg
reserviert: nach fünf Stufen, 5%-Preisabstand, Vorschau/MFA/Risk Gate;
Cockpitmeldung mit optionaler E-Mail. MT5 läuft laut Nutzer
auf einem separaten Heimnetzserver und wird über eine ausgehende HTTPS-Bridge
angebunden. Öffentlicher zentraler HTTPS-Einstieg für private Nutzer und
administratives E-Mail-Recovery sind bestätigt, ebenso Validierungsmaßstab,
Pilotbackupziele und M1-Umfang.
Alle Entscheidungen Q1–Q31 sind bestätigt.
Bestätigt sind privater Start, Cockpit/Backtests/Paper vor Echtgeld,
verbindliche Risikolimits, kontrollierte KI und zunächst kostenlose externe Dienste.

## Einstieg

- [Originaler Projektauftrag](docs/project-info.md)
- [Gesamtkonzept](docs/concept.md)
- [Bestätigter M1-Umfang und Umsetzung](docs/implementation-brief.md)
- [Lokaler Start](infra/README.md) und [Runtimepins](docs/runtime-pins.md)
- [Architektur und Technologieauswahl](docs/architecture.md)
- [Handelslogik und Validierung](docs/trading.md)
- [Sicherheit](docs/security.md) und [Betrieb](docs/operations.md)
- [Compose-/Authelia-Plan für den Privatpilot](docs/deployment-plan.md)
- [MT5-Bridge zum Heimnetzserver](docs/mt5-bridge.md)
- [Roadmap](docs/roadmap.md), [Ticketboard](docs/tasks/board.md) und
  [Backlog](docs/backlog.md)
- [Interview und offene Entscheidungen](docs/interview.md)
- [Bestandsaufnahme](docs/inventory.md) und [offizielle Quellen](docs/sources.md)

## Projektstruktur

| Pfad | Verantwortung |
|---|---|
| `apps/cockpit/` | Dashboard und Bedienoberfläche |
| `services/api/` | Autorisierte API und fachliche Anwendungsfälle |
| `services/workers/` | Datenimport, Backtests, Execution und Abgleich |
| `packages/trading/` | Gemeinsamer deterministischer Strategie- und Risikokern |
| `packages/marketdata/` | Validierte H4-Snapshots, öffentlicher Bitget-Import und CSV |
| `packages/contracts/` | Versionierte API-, Ereignis- und Bridgeverträge |
| `integrations/` | Bitget-Adapter und nutzereigene MT5-Bridge |
| `infra/` | Lokale Composeumgebung, TLS, Bootstrap und Werkzeugprofile |
| `tests/` | Fachliche, Integrations-, Isolations- und Recoverytests |
| `strategies/` | Bereits vorhandene Strategieabbildungen |
| `docs/`, `memory/` | Planung, Tickets, Entscheidungen und Arbeitsnotizen |

Cockpit zeigt tatsächlich gespeicherte Konten, Positionen, Journal und
Backtestaufträge und deren Ergebnisse; fehlende Daten bleiben leer. Die API
prüft signierte Identität, Mitgliedschaft und RLS und friert Daten-/Kostenstand
bei idempotenter Jobannahme ein. Ein echter 90-Tage-BTC-Import prüft den lokalen
Researchablauf; wirtschaftliche Validierung bleibt offen. Brokeradapter,
manuelle MFA-Reservefreigabe und Pilotbetrieb sind weitere M1-Aufgaben.
Öffentlicher Rollout und Echtgeld benötigen eigene
Abnahmen. Der lokale Einstieg bindet ausschließlich `127.0.0.1:8443`.

## Arbeitsregeln

Siehe [AGENTS.md](AGENTS.md). Geheimnisse und private Kontodaten gehören nicht in
Git. Neue externe Dienste, wesentliche Architekturentscheidungen und
Produktionsdeployments brauchen die dort festgelegte Abstimmung.

Dauerhafte Profitabilität und absolute Sicherheit sind Zielvorstellungen, keine
garantierbaren Eigenschaften. Abnahmen prüfen nachvollziehbare Nettoergebnisse,
Risikobegrenzung und konkrete Sicherheitskontrollen.
