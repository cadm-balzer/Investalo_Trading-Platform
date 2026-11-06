# Investalo Trading Platform

Mandantenfähiges Trading-Cockpit mit Portfolio, Journal, Backtests und
automatisiertem Handel über Bitget und MetaTrader 5.

**Stand: 2026-11-07 — Planung und Interview.** Es gibt noch keine lauffähige
Anwendung. Der grundlegende Stack und beide Broker im ersten Release sind
bestätigt, ebenso Docker Compose und lokales Authelia für MFA.
Crypto startet mit BTC/ETH Spot ohne Hebel auf H4; MT5 mit XAUUSD Trend/Pullback.
Detailregeln, Paper-Risikolimits und Zugangs-/Recoveryabläufe bleiben offen.
Bestätigt sind privater Start, Cockpit/Backtests/Paper vor Echtgeld,
verbindliche Risikolimits, kontrollierte KI und zunächst kostenlose externe Dienste.

## Einstieg

- [Originaler Projektauftrag](docs/project-info.md)
- [Gesamtkonzept](docs/concept.md)
- [Architektur und Technologieauswahl](docs/architecture.md)
- [Handelslogik und Validierung](docs/trading.md)
- [Sicherheit](docs/security.md) und [Betrieb](docs/operations.md)
- [Privater Compose-/Authelia-Plan](docs/deployment-plan.md)
- [Roadmap](docs/roadmap.md), [Ticketboard](docs/tasks/board.md) und
  [Backlog](docs/backlog.md)
- [Interview und offene Entscheidungen](docs/interview.md)
- [Bestandsaufnahme](docs/inventory.md) und [offizielle Quellen](docs/sources.md)

## Geplante Struktur

| Pfad | Verantwortung |
|---|---|
| `apps/cockpit/` | Dashboard und Bedienoberfläche |
| `services/api/` | Autorisierte API und fachliche Anwendungsfälle |
| `services/workers/` | Datenimport, Backtests, Execution und Abgleich |
| `packages/trading/` | Gemeinsamer deterministischer Strategie- und Risikokern |
| `packages/contracts/` | Versionierte API-, Ereignis- und Bridgeverträge |
| `integrations/` | Bitget-Adapter und nutzereigene MT5-Bridge |
| `infra/` | Nach Freigabe: private Deployment- und Betriebskonfiguration |
| `tests/` | Fachliche, Integrations-, Isolations- und Recoverytests |
| `strategies/` | Bereits vorhandene Strategieabbildungen |
| `docs/`, `memory/` | Planung, Tickets, Entscheidungen und Arbeitsnotizen |

Die Verzeichnisse enthalten zunächst Aufgabenbeschreibungen; es werden noch
keine Frameworks oder Dienste installiert. Vor dem Bootstrap sind alle
Abhängigkeiten exakt zu pinnen und Lockdateien zu erzeugen.

## Arbeitsregeln

Siehe [AGENTS.md](AGENTS.md). Geheimnisse und private Kontodaten gehören nicht in
Git. Neue externe Dienste, wesentliche Architekturentscheidungen und
Produktionsdeployments brauchen die dort festgelegte Abstimmung.

Dauerhafte Profitabilität und absolute Sicherheit sind Zielvorstellungen, keine
garantierbaren Eigenschaften. Abnahmen prüfen nachvollziehbare Nettoergebnisse,
Risikobegrenzung und konkrete Sicherheitskontrollen.
