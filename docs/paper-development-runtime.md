# Lokaler Paper-Beobachtungslauf

IP-053,2026-11-09. Mergec1703c1 in Maina996bf2 verifiziert.
Ein eigener lokaler Dienst verarbeitet öffentliche BTC-/ETH-Kurse mit
PaperRunner, unverändertem RSI14/Wilder, Risk Gate und Q32-Tagesmodell.
Höchstens24 Stunden für neue Zyklusstarts; laufende begrenzte Fetch-/Commitarbeit
kann darüber hinaus enden. Öffentliche Anzeige und Pilotbetrieb bleiben offen.

## Identität und Startschutz

`provision-paper-development.py` legt ausschließlich in
`investalo_credentials_checks` einen synthetischen Tenant und ein Paperkonto
an. LOGIN `investalo_paper_development`, getrennt vom durch Tests neu gebundenen
`investalo_paper_tests`. Manifestzustand `prepared` hält IDs vor dem DB-Commit
fest; Wiederholung nach Abbruch verwendet dieselben IDs. Danach `bound`:
prüfen oder ablehnen, niemals neu binden, Passwort erneuern oder Konto aktivieren.
Manifest/Env root0600, Passwort UID10003/0400; reguläre Dateien mit einem
Hardlink, exklusive Erstellung, root0700-Verzeichnis. Dateien unter ignoriertem
`infra/local/`; keine Secrets in Git/Argumenten/Logs.

Provisionierung verlangt unveränderte Fixturemigrationen001–012, sichere
Rollen/Mitgliedschaften und ausschließlich die drei Paper-SECURITY-DEFINER-
Funktionen. Kein direkter Tabellenzugriff, normale DB, Research-/Credential-
funktionen oder Admin-LOGIN. Drift wird abgewiesen, kein automatisches Repair.
Keine neue Migration/Dependency; normal001–007 und Fixture001–012 unverändert.

`--development-loop` verlangt explizite Flags und exakt feste Rolle,
Fixture-DB, PG-Adresse, TLS-CA und Passwortdatei. Weitere `PG*`-Variablen
werden abgewiesen. CLI ohne Modus endet vor Verbindung. `--once` und
`--cycles 1..100` bleiben für begrenzte Checks verfügbar.

Eine Autocommit-Sitzung hält den konto-/tenantgebundenen Advisory-Lock, ohne
lange Rowlock-Transaktion. Doppelstart wird abgewiesen. Identität/Lock werden
vor Read/Initialisierung, vor jedem Write und vor Erfolgslebenszeichen geprüft.
Verbindungs-/Lockverlust ist terminal. Advisory-Locks sind kooperativ:
Checkpoint-CAS bleibt zwischen letzter Lockprüfung und Write maßgeblich.

Sechs aufeinanderfolgende Zyklusfehler beenden den Dienst; Erfolg setzt den
Zähler zurück. Unknowncommit bleibt sofort terminal, ohne Write-Retry.
Neuer Prozess liest bestätigten Zustand. SIGTERM/SIGINT wirken zwischen
begrenzten Arbeiten. Nur erfolgreicher Zyklus erneuert Health-Lebenszeichen.

## Bedienung

Das zusätzliche Composeprofil hat keine Hostports. UID10003, readonly
Quellmounts, nur eigenes Paperpasswort/CA, eigene Egressbridge,
192MiB/0,5CPU/64PIDs, begrenztes Tmpfs und zweimal5MiB Dockerlog.
Vorhandenes gepinntes Workerimage; `restart: "no"` erhält terminale Stopps.
Default Compose und öffentliche Dienste bleiben unverändert.

```bash
python3 infra/scripts/provision-paper-development.py
python3 infra/scripts/provision-paper-development.py --verify-only
# Bei angehaltenem Dienst: reale Identitäts-/Lock-/Driftabnahme
python3 infra/scripts/check-paper-development.py
bash infra/scripts/compose.sh --env-file infra/local/paper_development.env \
  --file infra/compose.paper-development.yaml --profile paper-development \
  up -d --no-deps paper-development
```

Für Status/Stop/Neustart dieselben Optionen und ausschließlich
`ps paper-development`, `stop paper-development` oder `restart paper-development`.
Bei unbekanntem Commit zuerst gespeicherten Zustand prüfen; kein blindes
Neustartsystem. Der Sessionchecker benötigt einen angehaltenen Dienst.
Öffentliche Dienste weiterhin mit ihrem Public-Preview-Overlay bedienen.

## Abnahme und Grenzen

44 gezielte gepinnte Runtime-/Workerfälle, drei stdlib-Dateischutz-/
Manifesttests grün. Tatsächliche wiederholte Provisionierung unverändert:
IDs, geschützte Dateien und Konto-/Checkpoint-/Journalanzahl gleich.
Vier echte Privileg-/Funktions-/Bindungsdrifts zurückgerollt und erneut
geprüft. Restricted TLS-LOGIN, Doppelstart, Lockfreigabe, Sitzungsverlust,
Ablehnung der normalen DB und Readback geprüft. Scoped Review ohne Blocker.
Reale Feedzyklen82/84/86, neuer Prozess88 ohne Fills. Lokaler Dienst
gesund; Doppelprozess vor Verarbeitung abgewiesen, kontrollierter Neustart
nach100 setzte mit102+ fort. Öffentliche sechs Dienste unverändert/gesund,
Cockpit gültiges TLS200; beide Ledgerprüfsummen erneut bestätigt.

Kein Profitabilitätsbeleg. Echtzeit-RSI kann länger keinen Einstieg liefern;
keine erzwungenen oder historischen Fills. Holdout bleibt gesperrt.
API/Cockpit-Anzeigeflags bleiben aus; Fixturekonto hat keinen öffentlichen Nutzer.

IP-047/BL-028: Nutzer-/Anzeigeprovisionierung, tatsächliche Mitternachts-
Betriebsbeobachtung, Produktions-Egress/Quoten, Monitoring/Recovery und
Speicherretention vor längerem Betrieb. Zwei neue Quotes je fünf Sekunden
ergeben ungefähr34.560 Journaleinträge/Tag. Keine automatische Löschung
unveränderlicher Journale oder stillschweigende Pollingänderung.
Unit-/PG-Tageswechselprüfungen ersetzen keinen beobachteten echten Tageswechsel.

Referenzen:
[PostgreSQL Advisory Locks](https://www.postgresql.org/docs/18/explicit-locking.html#ADVISORY-LOCKS),
[Compose restart](https://docs.docker.com/reference/compose-file/services/#restart).

Fortsetzung IP-054: [eigener gespeicherter Paperstand im öffentlichen
Entwicklungscockpit](paper-preview-integration.md). Normale DB jetzt012.
Fixture-Identität/-Journal/-Worker hier unverändert; keine Kontokopie oder
Umstellung dieses Launchers auf die normale Datenbank.
