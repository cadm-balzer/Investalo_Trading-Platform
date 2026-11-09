# Atomarer PostgreSQL-Paperstore

Fortsetzung IP-050: [öffentlicher Feed und begrenzter Worker](paper-market-worker.md)
sind tatsächlich in der Fixture-DB geprüft. IP-051 ergänzt die ausgeschaltete
[Status-/Journalanzeige](paper-status-readmodel.md) und Fixture011;
Dauerbetrieb/Anzeigeaktivierung noch offen.

IP-049,2026-11-09: privater `PaperStore` verbindet den vorhandenen
[PaperRunner](paper-runner.md) mit PostgreSQL. Feedworker und Cockpitanzeige
folgen in IP-047; dieser Checkpoint startet keinen laufenden Paperdienst.

Der Writer prüft erwartete Revision und SHA256 des vorherigen Checkpoints.
Neuer Zustand und append-only Journaleintrag werden in derselben Transaktion
geschrieben. Eine Bestätigung folgt erst nach erfolgreichem Commit.
Ein konkurrierender Writer erhält einen Konflikt. Die exakte Wiederholung
des zuletzt committed Updates erzeugt keinen zweiten Journaleintrag.
Bei unbekanntem Commitresultat gibt es keinen automatischen Retry:
frische Verbindung öffnen, gespeicherten Zustand lesen und abgleichen.

Der Client verlangt eine frische Verbindung ohne Autocommit oder bereits
laufende Transaktion. Restore prüft Checksumme, Revision, Tenant/Konto,
Strategie, Instrumentregeln und Kosten mit demselben Domainkern.
SQL prüft Bindung, Paperkontomodus, Kontostatus, CAS, Konfiguration,
Kosten und monotone Zeit. Strategie- und Wirtschaftsberechnungen bleiben
Vertrauensaufgabe des Pythonworkers; SQL berechnet keine Trades nach.

## Identität und Rechte

`investalo_paper_worker` ist eine NOLOGIN-Gruppe. In der Testdatenbank
verwendet ausschließlich der synthetische LOGIN `investalo_paper_tests`
die drei festen Funktionen `paper_read`, `paper_initialize`, `paper_commit`.
Die Bindung wird durch den privaten Helfer `paper_actor` geprüft.
`SESSION_USER` bindet genau ein aktives Bitget-Paperkonto in USDT.
Kontobindung und Konto werden während des Zugriffs gesperrt.
Ein pausiertes Konto bleibt lesbar; neue Writes sind gesperrt.

Neue Tabellen haben FORCE-RLS. Der Worker hat keine direkten Tabellenrechte
oder Credentialrechte; Runtime und Research erhalten keine neuen Rechte.
Privilegierte Funktionen verwenden festen Suchpfad und qualifizierte Objekte.
Die HBA-Ergänzung erlaubt dieser Gruppe nur TLS/SCRAM zur Fixture-DB.
Der Verbindungstest zur normalen Entwicklungsdatenbank wird abgewiesen.

## Migration und Prüfbeleg

010 wurde nach vollständig zurückgerolltem DDL-/Worker-/Fehlerpreflight
ausschließlich auf `investalo_credentials_checks` angewendet.
SHA256: `812a0a1f1702f09ef3b9410640eae7b60498320326888a86c494a83f8f3f5797`.
Angewendete Migrationen sind unveränderlich. `investalo` bleibt001–007,
Fixture001–010; sämtliche Ledgerprüfsummen stimmen mit den SQL-Dateien überein.
Nicht default `migrate`/`up` ausführen, um Tests zu reparieren.

78 gepinnte Tests und15 Subtests bestanden:29 echte PostgreSQL-Fälle,
45 Tradingfälle und vier Workerberechnungsfälle. Geprüft sind atomarer
Rollback auch nach Journalinsert, konkurrierende Writes, verlorene
Commitantwort vor/nach Commit, Rechte-/Kontomodusgrenzen und genau ein
simulierter Fill nach Datenbank-Restore und identischem Input.
Unabhängiger Review ohne verbleibenden Blocker.

Vorbereitung und gezielter Lauf:

```bash
python3 infra/scripts/prepare-paper-storage-checks.py
bash infra/scripts/check-paper-storage.sh
```

`--apply-reviewed` ist ausschließlich für die geprüfte Fixturemigration;
`--rotate-test-secret` rotiert ausschließlich den synthetischen Paper-LOGIN.
Ein anfänglicher Verbindungstrace enthielt dessen Testpasswort: es wurde
rotiert, der lokale Trace bereinigt und der Testverbindungsfehler sanitisiert.
Keine Nutzer-/Brokercredentials betroffen.

Vorhandenes Checkimage mit readonly Quell-/Testmounts, keine neuen
Dependencies oder Builds. Breite HTTP-/Credentialläufe wurden nicht erneut
ausgeführt. PostgreSQL-Konfiguration wurde neu geladen; öffentliche
Container wurden nicht neu erstellt. Bestehendes Cockpit weiterhin TLS/HTTP200.
Marktfeed, laufender Worker, Anzeige und Betriebsabnahme bleiben offen.

Referenzen: [Funktionsprivilegien und Suchpfad](https://www.postgresql.org/docs/18/sql-createfunction.html),
[SHA256 auf Bytes](https://www.postgresql.org/docs/18/functions-binarystring.html).
