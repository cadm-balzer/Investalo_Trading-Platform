# Offline-Researchworker

IP-049 ergänzt `paper_store.py`: eigene LOGIN-Prüfung, frische Transaktionen, atomarer Checkpoint-/Journalcommit und Readback bei unbekanntem Commit.29 tatsächliche PostgreSQL-Fälle bestanden;010 nur Testdatenbank. Der gestartete Worker bleibt Offline-Research; Paperfeed/Daemon folgt in IP-047. [Vertrag](../../docs/paper-postgres-store.md).

Start: `python -m investalo_workers.main`, einmaliger Zyklus mit `--once`.
`PYTHONPATH` enthält `services/workers/src`, `services/api/src`,
`packages/trading/src` und `packages/marketdata/src`. Der Worker verwendet die
bestehenden exakten API-Hashlocks; es gibt keine neuen Abhängigkeiten.
Die importierte API-Spezifikation ist rein und liest keine App-Secrets.

Nur PostgreSQL-Zugang konfigurieren: `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`,
`PGPASSWORD_FILE`, `PGSSLMODE=verify-full`, `PGSSLROOTCERT`.
Keine BFF-, IdP- oder Broker-Secrets mounten; kein Internetzugang ist erforderlich.
Jeder Tenant erhält eine eigene begrenzte LOGIN-Rolle, Mitglied der NOLOGIN-
Gruppe `investalo_research_worker`. Der Administrator bindet sie über
`platform.research_role_bindings(database_role,tenant_id)`.

Die Datenbank verwendet das unveränderbare `SESSION_USER` zur Tenantbindung.
Ein gesetzter Tenant-GUC oder `SET ROLE` kann keinen anderen Tenant freigeben.
Der Worker erhält nur ausgewählte SELECT- und Funktionsrechte, keine direkten
Tabellenwrites, Mitgliedschaftsdaten, DDL oder RLS-Bypassrechte.
Security-Definer-Funktionen haben einen festen Suchpfad und keinen PUBLIC-Zugriff.
Forschungszugang schützt nicht gegen kompromittierte Host-/DB-Administratoren.

Claim erfolgt atomar über `SKIP LOCKED`, UUID-Attempttoken und begrenzte Lease.
Ein separater Heartbeat hält die Lease; Verlust verwirft die Berechnung.
Heartbeat, Abschluss und Fehlerveröffentlichung prüfen Tenant, aktuellen Token
und Ablauf erneut. Abgelaufene Leases können mit neuer Fence übernommen werden;
höchstens drei Attempts, danach `attempts_exhausted`. Bekannte Daten-/Configfehler
beenden den Auftrag direkt. Terminale Aufträge und Snapshots sind unveränderlich.

Berechnet wird ausschließlich `PaperSimulator.run(to_trading_candles(snapshot))`
mit überprüftem Snapshot-/Contentdigest und exakt eingefrorener Strategie,
Präzision und Kosten. Keine künstlichen manuellen Reservefills, kein terminales
Zwangsschließen, keine Broker-Ausführung. Holdout-Snapshots werden weder gelesen
noch geclaimed. Synthetische Daten behalten ihre Kennzeichnung; wirtschaftliche
Validierung bleibt `not_evaluated`.

Health: `python -m investalo_workers.health`. Erfolgreiche gebundene DB-Zyklen
und Heartbeats aktualisieren `WORKER_HEALTH_FILE` (Default `/tmp/worker-health`).
Nach 120 Sekunden ohne Fortschritt schlägt Health fehl. Die Datei enthält
keine Tenant-/Account-/Credentialdaten. Abfragen haben fünf Sekunden Statement-
und drei Sekunden Locktimeout; Logs enthalten keine freien Exceptiontexte.

Tests: mit den vier oben genannten Pythonpfaden `python -m pytest tests/workers`.
Echte PG-Tests brauchen zusätzlich zur API-Migrations-Testidentität
`API_TEST_RESEARCH_USER` und `API_TEST_RESEARCH_PASSWORD_FILE`.
Sie benutzen eine tatsächliche separate LOGIN-Rolle und ändern ausschließlich
deren Testbindung, niemals die laufende lokale Workerbindung.
Execution-/Reconciliationworker und Marketdata-Ingestprozesse folgen separat.
