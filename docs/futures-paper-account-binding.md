# Eigenes Paperkapital und gespeicherte Basket-Einstellungen

IP-090,2026-11-14. PR65 (`a22199a`) ist in Main `f7fb8c6` gemerged,
GH/Fetched-Ancestry bestätigt. Dieser Checkpoint verbindet ein vorhandenes
eigenes Plattform-Paperkonto mit einer expliziten Futures-Paperallokation,
Migration013 und dem archivierten Quellenworker. Laufende Dienste und
Cockpitopt-ins bleiben unverändert.

## Private Allokation und einmalige Initialisierung

`PaperBootstrapSpec` enthält eine vollständige eigene `FuturesPaperConfig`
mit deklarierter anfänglicher Paperkapitalmenge, anfangs3–5 finanzierten
Ranges, Kosten-/Margin-/Mengen-/Preisregeln, Handelsbeginn und festem2×.
Die Regeln sind Paper-Modellannahmen; dieser Schritt kalibriert keine
Brokerorder oder Gebührenstufe. Der bestehende `paper_pool_plan` erzeugt
aus dem expliziten Eigenkapital die unveränderliche vollständige Staffel.
Fünf reguläre Käufe plus sechste manuelle Reserve bleiben erhalten.

Die `PaperAccountBinding` legt eigene Tenant-/Account-/User-UUID, OIDC-
Issuer/-Subject, Auth-Epoche und administrative Autorisierungszeit fest.
Sie ist eine private administrative Workerdelegation, keine Browserangabe
und keine erzeugte API-/OIDC-Sitzung. Aktueller Benutzerstatus, Reauthgrenze,
Epoche und Owner-/Trader-Mitgliedschaft werden aus der Datenbank geprüft.

`save_spec(path, PaperBootstrapSpec(binding, config))` schreibt den expliziten
Plan create-only/owned0600/fsync/readback in einen vorhandenen absoluten
owned0700-Root. Den zurückgegebenen SHA256 hält der Administrator separat.
`load_spec(path, sha256)` prüft Rechte, Scope, Vollständigkeit und exakt diese
kanonische Identität. Die Datei enthält keine Börsenkeys oder DBpasswörter.
Sie übernimmt keine Spotbalance oder historischen Backtestendstände.
Das Startkapital ist eine eigenständige erklärte Paperallokation.

`initialize_paper` prüft zuerst das vorhandene eigene ready/Bitget/paper/USDT-
Konto und die gespeicherte Obergrenze. Diese muss dem Plan entsprechen und
mindestens die anfänglich finanzierten Plätze erlauben. Ein vorhandenes
Journal oder ein bereits publizierter eigener Stand verbietet Neuanlage,
auch unter einem anderen Journalpfad. Kein Zurücksetzen und keine zweite
Kapitalgutschrift.

Vor Journalerzeugung werden native Quellen archiviert und der vollständige
Warmup rein validiert. Die bestehende Genesis bleibt exakt UTC-Mitternacht;
je nach erklärtem H1-Handelsbeginn werden16–39 geschlossene native Stunden
ab der passenden Mitternacht verwendet. Initiale Trade-/Markpreise stammen
aus den jeweiligen ersten nativen Stunden-Opens. Vor dem Warmup entstehen
keine historischen Käufe. Konto/Einstellung werden vor Erzeugung nochmals
abgeglichen. Erst danach folgen eigenes create-only-Journal, gebundener
Warmupcommit und private Publikation. Unbekannte Commits erfordern Readback;
erneutes `--initialize` überschreibt nichts.

## Readonly Datenbankanbindung und Settingscommit

`FuturesPaperAccountReader` verwendet den bestehenden eingeschränkten
`investalo_runtime`-LOGIN ohne Superuser/BYPASSRLS/Role-/DB-Erstellungsrechte.
Jeder Abruf hat eine eigene READ ONLY-Transaktion, lokale eigene OIDC-/User-/
Tenant-RLS-Kontexte sowie3s Statement-/1s Locktimeout. Es gibt keine neuen
Rollen oder Grants und keine APIassertion, Nonce- oder Auditschreibaktion.
Nur das exakt gebundene aktuelle Konto und dessen013-Einstellung werden
gelesen. Pause, falscher Broker/Modus/Währung, Foreignscope, inaktiver User,
entzogene Rolle, Auth-Epochenwechsel oder neue Reauthgrenze stoppen.
SQL-/Verbindungs-/Identitätsdetails bleiben aus Fehlermeldungen heraus.

`FuturesAccountWorker` liest vor jedem Zyklus einen frischen eigenen Stand
und prüft ihn erneut unmittelbar vor Journalcommits. Eine während der
Quellenerfassung erkannte Kontosperre oder Einstellungsänderung verhindert
den anschließenden Quote-/Fundingcommit; archivierte Originalbelege bleiben.
DB und Dateijournal bilden keine gemeinsame Transaktion: Änderungen nach
dieser Vorprüfung werden beim folgenden Zyklus berücksichtigt.
Bestehende externe Commit-/Abbruchguards bleiben zusätzlich wirksam.

Der additive eigene `account_settings`-Befehl übernimmt die tatsächlich
gelesene neueste gespeicherte DBrevision. Wenn während eines Workerstopps
mehrere Revisionen gespeichert wurden, werden keine Zwischenwerte erfunden.
Scope, Bindinghash, Wissenszeit, Frische und strikt höhere Revision sind
im gehashten Befehl enthalten. Regressionen oder ein anderer Wert zur
gleichen Revision stoppen vor HTTP. Der alte contiguous `settings`-
Vertrag und historische Journalgoldenidentitäten bleiben unverändert.

Absenken erzwingt keine Schließung. Offene Budgets, Kaufstaffeln, Kosten,
manuelle Reserven und eingefrorener Hebel ändern sich nicht. Erhöhen auf7
finanziert keine zusätzlichen Plätze: ohne Q36-Gewinnetappe begrenzt weiter
die ursprüngliche Anzahl3–5. Nach unbekanntem Settingscommit rekonstruiert
der vollständige Restore die bereits gespeicherte Revision einmalig.

## Gebundener begrenzter Launcher und Abnahme

`python -m investalo_workers.futures_account_main` verlangt
`FUTURES_PAPER_ACCOUNT_WORKER_ENABLED=1`, `--spec`, separat gehaltenen
`--spec-digest`, `--journal`, `--archive-root` und `--status-root`.
`--initialize` ist ausschließlich für die einmalige eigene Allokation;
weitere Aufrufe stellen das Journal mit dem publizierten Mindestreceipt
wieder her. `--cycles`1–100/Default1 und `--interval`5–300s/Default15.
Zusätzlich zu Trading/Marketdata/Workers gehört `services/api/src` zum
PYTHONPATH; bestehende PG*-Parameter und `PGPASSWORD_FILE` konfigurieren
den eingeschränkten LOGIN. Keine Börsenkeys oder internen APIkeys benötigt.
Das Modul erstellt keine Plattformkonten, Rollen oder Tabellen und wendet
keine Migration an. Fehler stoppen ohne automatische Wiederholung.

22 neue Fälle: neun Domain-/Dateisystem-/Launcherfälle und13 tatsächliche
Runtime-LOGIN/PostgreSQL-Fälle. Geprüft sind native Initialisierung, echte
eigene10.000-USDT-Paperallokation, UTC-Genesis, gebundener CLI-Neustart,
aktuelle/übersprungene Settingsrevisionen, unveränderte offene Ranges,
einmaliger Unknown-write-Readback, Foreignscope, erhöhte LOGINs,
Benutzer-/Rollen-/Kontorevocation und Kontopause während nativer Erfassung.
Die bestehenden Quellen-, Funding-, Signal-, API- und Goldenverträge bleiben
im gezielten gepinnten Regressionslauf geprüft. Native HTTP-Antworten in
diesen Integrationstests sind synthetisch; SQL und private Dateien sind real.

013 bleibt ausschließlich in der vorhandenen Fixture-Datenbank angewendet;
die Entwicklungsmigrationsmenge bleibt unverändert. Kein laufender Dienst,
neuer Performancejob, Public-/Live-/AI-Rollout oder neue Abhängigkeit.
Nächster Schritt ist die konkrete lokale Lauf-/Cockpitabnahme mit eigenem
privatem Profil und Statusmount. Kalibrierter Minimum-Range-/Kapazitätsreader,
Q36-Gewinnetappen und IP-088-Recovery bleiben weitere Schritte.
Die Planungs-API liefert bis zur Kapazitätsanbindung weiterhin
`runtime_ready=false`, `recommendation=null`.
