# Worker — geplanter Bereich

Getrennte Prozesse für Ingest, Signale, Backtests, Execution und Reconciliation.
Researchprozesse haben keine Brokercredentials; Liveausführung erhält eigene
Identität und Ressourcengrenzen. Dauerhafte Jobs/Outbox zunächst über PostgreSQL
sind als Grundansatz bestätigt; Ausführungsverträge werden noch spezifiziert.

Details: `docs/architecture.md`, `docs/operations.md`.
