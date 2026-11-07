# Verifikation

Schwerpunkte: deterministische Handelsregeln und Kostenrechnung, Tenantisolation,
Brokeradapterverträge, unklare Orderantworten, Crash/Replay, Risikogrenzen,
Zeitwechsel, Credentialrotation und Restore vor erneutem Handelsstart.

Das lokale Fundament besitzt ausführbare Tests:

- `tests/trading`: deterministische Signale, Kosten/Budgets, Teilfills,
  Unsicherheit/Replay, Schutz, Tageswechsel und manuelle Reserve.
- `tests/api`: API-Authentifizierung, Payloadgrenzen und echte PostgreSQL-
  Integration für Rollen, FORCE RLS, Relationstrennung, Jobidempotenz,
  immutable Snapshots und Holdoutschutz.
- `tests/marketdata`: Zeit-/OHLC-/Digest-/Coveragevalidierung, sichere CSV-
  Kennzeichnung und deterministische öffentliche Bitget-Pagination.
- `tests/bitget`: 24 Offline-Tests für Classic-V2-Signaturen, feste GET-Pfade,
  TLS/Redirect-/Antwortgrenzen, Nutzer-/UID-/Parent-/Rechte-/IP-Prüfungen und
  getrennte Walletdaten. Erfundenes Keymaterial und gemockter HTTPS-Transport;
  kein tatsächlicher Brokeraufruf. [Testkommando](../integrations/bitget/README.md).
- `tests/workers`: gemeinsamer Simulatorkern, Provenienz und Lease-/Fencing-
  Negativfälle mit eigener tatsächlicher Research-Testrolle.
- `apps/cockpit/tests`: OIDC-Token/Freshness, Cookies/Sitzungen, CSRF,
  Mandantenantworten, Ergebnis-/Datasetverträge und requestgebundene Assertions.
- `tests/infra/check_local_auth.py`: tatsächlicher HTTPS-Passwort-/TOTP-/
  OIDC-Durchlauf einschließlich BFF, Mandanten-API und Abmeldung.
  Jobannahme/Wiederholung, Parameterkonflikt und frischer Login trotz bestehender
  IdP-Sitzung werden ebenfalls geprüft.
  Ein importierter öffentlicher BTC-Snapshot wird ausgewählt und vom tatsächlichen
  Worker verarbeitet; Ergebnisdigest, Nettoauswertung und SVGkurve werden geprüft.
  Ausschließlich generierte lokale `.invalid`-Identität; keine Faktorwerte ausgeben.
- `tests/infra/test_research_provisioning.py`: atomare Rollenprovisionierung,
  Eingabegrenzen und sichere SQL-/Passwortbehandlung.

Start- und Testkommandos: [infra/README.md](../infra/README.md).
Integrationstests verwenden separate Testfixtures und echte Runtime-/Migrationsrollen.
Die separat provisionierte Research-Testrolle verändert ausschließlich ihre
Fixturebindung, niemals die Identität des laufenden Researchworkers.
Recovery, WebAuthn-Erstregistrierung, Broker-Crashfälle und
verschlüsselter externer Restore sind damit noch nicht abgenommen.
Abnahmekriterien: [Roadmap](../docs/roadmap.md), [Ticketboard](../docs/tasks/board.md).
