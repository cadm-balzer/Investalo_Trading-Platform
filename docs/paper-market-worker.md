# Öffentlicher Feed und begrenzter Paperworker

IP-050,2026-11-09: öffentliche BTC-/ETH-Spotdaten erreichen denselben
`PaperRunner` und den [atomaren PostgreSQL-Store](paper-postgres-store.md).
Geprüft ist ein begrenzter Entwicklungslauf mit isolierter Kontorolle und
Fixture-DB; noch keine öffentliche Cockpitanzeige oder dauerhafte Runtime.

## Daten und Verarbeitung

Der Adapter verwendet ausschließlich unsignierte GETs auf
`https://api.bitget.com/api/v3/market/tickers` und `/api/v3/market/candles`,
jeweils `category=SPOT`. Feste Symbole/Origin/Pfade, keine Redirects,
Cookies oder Brokerkeys; Antwort maximal256KiB, Timeout fünf Sekunden.
Bid/Ask und Venue-Zeit stammen aus dem Ticker. Kurse älter als30 Sekunden,
zukünftige/ungültige Kurse oder falsches Asset/Kategorie werden abgewiesen.

Zum Start je40 geschlossene UTC-H4-Kerzen als Indikatorvorlauf.
Danach wird die letzte gespeicherte Kerze nochmals auf Revision geprüft,
anschließend ausschließlich lückenlos nachgeholt; maximal100 Intervalle.
Aktuelle ungeschlossene Kerzen werden herausgefiltert. Der aktuelle
SPOT-Kerzenendpunkt ließ im realen Abruf die Startkerze aus: Abfrage um ein
vorheriges Intervall erweitert, vollständige Sollabdeckung weiterhin zwingend.
Kein OHLC-Pfad wird als Quote oder historischer Fill verwendet.

Der Worker liest zuerst mit eigener LOGIN-/Kontobindung den gespeicherten
Zustand. Beide Datenfenster und Quotes werden vollständig geprüft, bevor
Initialisierung oder Updates gespeichert werden. Quotes kommen vor Signalen;
Käufe brauchen weiterhin einen späteren frischen Quote und das Risk Gate.
Jeder Input wird einzeln mit Zustand/Journaleintrag committed; ein kompletter
Pollingzyklus ist keine gemeinsame Datenbanktransaktion.
Bei Fehler/Konflikt liest der nächste Zyklus erneut und lädt frische Daten.
Ein unbekannter Commit beendet den Prozess unmittelbar, ohne Write-Retry.
Neustart liest den bestätigten Zustand; neue Inputs werden danach verarbeitet.

## Begrenzter Betrieb und Tageswechsel

`PAPER_WORKER_ENABLED=1`, vertrauenswürdig konfigurierte Tenant-/Konto-UUIDs,
eigener `investalo_paper_*` LOGIN und `PGSSLMODE=verify-full` sind erforderlich.
CLI erlaubt nur `--once` oder `--cycles 1..100` mit fünf Sekunden Pause.
Ohne Begrenzung wird vor Konfiguration/Verbindung abgewiesen.
Logs enthalten nur Revision/Update-/Fillanzahl oder feste Fehlerkategorien.

Die bestehende Risikologik verlangt exakte Mitternachtsquotes und passende
Verarbeitungszeit für eine neue Tagesbaseline. REST-Polling liefert das nicht
zuverlässig: Am nächsten UTC-Tag bleiben neue Käufe deshalb durch
`daily_baseline_required` gesperrt. Kein erfundener oder nachträglich mit
aktueller Equity ersetzter Tagesstart. Sicheres Tageswechselverfahren und
dessen Abnahme müssen vor Dauerbetrieb geklärt werden; Risikoregeln unverändert.

## Prüfbeleg und Wiederholung

151 gepinnte Tests/48 Subtests bestanden:30 tatsächliche PostgreSQL-Fälle,
18 Worker-/Start-/Tageswechseltests,54 Marktdatafälle,45 Trading und vier
Workerberechnungsfälle. Der neue integrierte Test verbindet echten Feedparser,
synthetische Antworten, eingeschränkten LOGIN und PostgreSQL: ein Fill bleibt
nach Neustart genau einmal gespeichert. Unabhängiger Review ohne Blocker für
den begrenzten Checkpoint; Dauerbetrieb bleibt ausdrücklich ausgeschlossen.

Reale öffentliche Prüfung: je40 lückenlose geschlossene H4-Kerzen,
letzter Close2026-11-09T08:00Z, beide Bid/Ask-Quotes ca.1,2 Sekunden alt.
Isolierter Drei-Zyklen-Lauf committed Revisionen82/84/86; neuer Prozess88,
jeweils ohne Fills. Das belegt Feed/Persistenz/Resume, keine Profitabilität.

```bash
python3 infra/scripts/check-public-paper-feed.py
bash infra/scripts/check-paper-storage.sh
python3 infra/scripts/prepare-paper-feed-check.py
# UUID durch die ausgegebene Fixturekennung ersetzen
bash infra/scripts/compose.sh --env-file infra/local/paper-feed-UUID.env \
  --file infra/compose.paper-checks.yaml --profile paper-checks \
  run --rm --no-deps -T paper-fixture
```

Für mehrere Versuche Command anhängen:
`python -m investalo_workers.paper_main --cycles 3`.
Vorbereitung bindet ausschließlich `investalo_paper_tests` an ein neues
synthetisches Konto. PG-Tests verändern dieselbe Testbindung: danach neu
vorbereiten, keine alte Konfiguration blind wiederverwenden.
Default Compose unverändert; Overlay hat keine Hostports, nur Paperpasswort
und CA, keine administrativen/Runtime-/Brokersecrets. Getrennte Entwicklungs-
Egressbridge; feste Endpunkte im Adapter, kein Produktions-Egressfilter.
Vorhandenes gepinntes Workerimage mit readonly Quellmounts, keine Builds/
Dependencies/Migrationen. Normale DB007/Fixture010 und Prüfsummen unverändert.
Alle Einmalcontainer beendet; sechs bestehende Dienste unverändert,
Cockpit weiterhin gültiges TLS/HTTP200.

Fortsetzung IP-051: [tenantgebundene Paperstatus-/Journalanzeige](paper-status-readmodel.md)
implementiert und standardmäßig ausgeschaltet. IP-052 ersetzt die
historisch beschriebene exakte Quote-Baseline durch die freigegebene
[H4-Mitternachtsmodellbewertung](paper-midnight-basis.md); Fixture inzwischen012.
Nächstes IP-047: eigene dauerhafte Entwicklungsprovisionierung und sichere
Betriebs-/Anzeigeaktivierung.
Referenzen: [Ticker](https://www.bitget.com/legacy-docs/uta/public/Tickers),
[aktuelle Kerzen](https://www.bitget.com/legacy-docs/uta/public/Get-Candle-Data).
