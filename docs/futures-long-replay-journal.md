# Langes Futures-Replay mit vollständigem Forschungsjournal

IP-070`0ebb98b` in Main`629901b` verifiziert. IP-071 ergänzt die technische
Langlauf-/Wiederanlaufbasis für IP-069. **Noch kein Markt-Nettoleistungslauf.**
Bestehende RSI-/Staffel-/Reserve-/6%/8%/−50%-Regeln bleiben unverändert.

## Vollständiger Langlaufbeleg

Ein ausdrücklich **synthetischer Mechaniktest** verarbeitet6576 aufeinanderfolgende
H4-Schritte vom2022-08-01 bis2025-08-01 und sämtliche1096 Mitternachtsbasen.
Drei synthetische Assets, alternierende Preise100/101, keine Orders/Fills,
keine historische Marktdaten-/Funding-/Kostenperformance.

Das lokale Journal enthält **7672 vollständig behaltene Ereignis-IDs**,
9.544.108 Bytes. Alle6576 Inputs werden nach Schließen vollständig erneut
abgespielt: exakt derselbe Zustand, Head und Receipt; die erste Ereignis-ID
ist weiterhin vorhanden, ebenso die aufgebauten Wilder-Indikatorzustände.
Ein zusätzlicher Wiederanlauf mit der zuvor bestätigten Receipt als Mindestanker
prüft die vollständige vorhandene Datei ebenfalls.

Messung auf diesem Host: ursprünglicher Schreibdurchlauf59,228s,
vollständiger ursprünglicher Restore62,707s. Keine Leistungs-/Produktions-SLA;
ein Zusatzlauf prüft den nach Eigenreview ergänzten bestätigten Mindestanker.
[Synthetische Abnahmereceipt](research-protocols/futures-long-journal-receipt-20261111.json).
Ignorierte vollständige Datei:
`infra/local/futures-long-journal-checks/20261111-complete/journal.jsonl`.

```bash
python3 tests/infra/check_futures_long_journal.py NEW_OUTPUT_DIRECTORY
```

Die Abnahme definiert den synthetischen Testvertrag vor Verarbeitung und bindet
ihn als Protokolldigest. Sie importiert explizit Testfixtures, ist kein Launcher/
Backtestjob und wertet die echten Binance- oder geschützten Holdoutdaten nicht aus.

## Identitäten ohne Eviction

Der bisherige Pendingmodus`isolated-usdt-long-pending/1` mit1024 immutable
Tuple-IDs bleibt Standard und stoppt weiterhin an seiner Grenze.
Ein ausdrücklicher neuer Start erzeugt`isolated-usdt-long-pending/2`
mit vier getrennten immutable Historien für Intent/Order/Fill/Event.
Default50000 IDs je Historie, explizit1..100000; kein automatisches Wachstum.
Bestehende Ledger mit Ereignissen/Fills können nicht durch einen frischen
Start ihre Vorgeschichte verlieren: Longstart verlangt Revision0/flat/genesis.

Die Historien behalten jede ID in einem persistenten balancierten Baum.
Einfügen und Membership benötigen logarithmisch viele Knoten; alte Präfixe
bleiben immutable. Struktur-/Inhalts-/Anzahlhashes binden sämtliche IDs.
Der allgemeine Snapshot-Primitivecodec schreibt ausschließlich für diesen
expliziten Typ einen kleinen Receipt mit Namespace/Kapazität/Count/Root.
Bestehende Typen und Tuple-Snapshots werden identisch codiert.
**Dieser Rootreceipt allein ist keine Restorequelle.**
Die Reihenfolge der Inserts gehört zum kausalen Replay; der Baumhash ist
kein unabhängiger sortierter Setdigest und keine Herkunftsauthentifizierung.

Die bestehenden Kauf-/Teilfill-/Terminal-/Quarantänefunktionen nutzen die
neuen Historien, ohne ihre ökonomischen Prüfungen zu ersetzen. Mischungen
der Modi, falsche Namespaces oder unterschiedliche Kapazitäten scheitern.
Kapazitätserschöpfung bleibt terminal; kein ID-Verwerfen oder Reset.

## Dauerhafter Wiederanlauf

Eigenes lokales`isolated-usdt-long-replay-journal/1`: create-only JSONL,
genesis Profile/Ledger/Protokoll-/Dataset-SHA256s/Identitäts-/Commandkapazität.
Jeder Input erhält Sequence, vorherigen Head/Zustandsdigest, typisierten
vollständigen Input, resultierenden Zustandsdigest und neuen Kettenhead.
Unterstützt H4-Frame, Reserve, Attempt, Unattempted-Cancel, tatsächlichen
Entry/Exit, abgeglichenen Terminalstatus und explizites Funding/Marginposting.

Vor jedem Append läuft derselbe reine RSI-/Ledgerkern; erst nach bestätigtem
vollständigem Write und `fsync` gilt der neue In-Memory-Zustand.
Weder ungültige/stale Inputs noch doppelte Frames schreiben einen neuen Record.
Restore beginnt ausschließlich mit genesis und faltet alle Inputs vollständig.
Actor/Account/Kosten-/Risikoplan/Profil, Protokoll und Datasetdigests bleiben
gebunden. Counters, offene Signal-/Orderbindungen, Teilfill-VWAPs, Halts,
Quarantäne und alle alten IDs werden reproduziert; keine frische Wrapperinstanz
über einem bereits fortgeschrittenen Ledger als angeblicher Restore.

`minimum_receipt` prüft bei Restore einen separat behaltenen bestätigten
Head/Zustands-/Sequence-/Kontextanker. Das erkennt auch den Verlust ganzer
letzter Records; ein zusätzlicher unbekannter vollständiger Record nach dem
alten Anker wird erst nach echtem Replay akzeptiert. Ohne solchen separat
behaltenen Anker kann eine gültige frühere Dateipräfixversion nicht als
Rollback erkannt werden. Deshalb in Wiederanlaufabläufen den letzten
bestätigten Receipt als Mindestanker mitgeben. Ungeankertes Lesen ist nur
lokale Forschungsinspektion, kein Nachweis des zuletzt bestätigten Heads.

Kurzwrite/fehlende `fsync`-Bestätigung sperrt das Journal mit
`JournalCommitUnknown`: keine Wiederholung, kein State-/Receipt-Read als
angeblich aktueller Stand; schließen und vollständig zurücklesen.
Abgebrochene/überlange/beschädigte Records, Duplicate-JSON-Member, falsche
Sequence/Hashbindung/Typed Inputs scheitern. Keine automatische Tailreparatur.
Ein vollständig vorhandener unbestätigter Record kann durch Readback
nachgewiesen werden; ohne vollständigen Record bleibt die Datei gesperrt.

Eigene0600-Regular-Datei/Owner, kein Leaf-Symlink/Hardlink, exklusiver
kooperativer Linux-Writerlock über die gesamte Lebensdauer; `fsync` der
Parentdirectory nach Create.256KiB je Record,128MiB Gesamtdatei, maximal100000
Commands, aufgebrauchte Kapazität ohne Eviction. Lokale Dateirechte/Hashkette
sind keine Broker-/MFA-/Signatur-/Administrator-Manipulationsnachweise.
Keine SQL-/Credential-/Netzwerk-/Worker-/Dispatch-/Cockpit-/Publicaktivierung.

## Prüfung und nächster Schritt

24 neue Fälle plus Ankerprüfung: insgesamt25 neue Fälle. Zuerst337 gepinnte
Trading-/Workerfälle/253 Subtests grün, anschließend finale25 Journalfälle/
26 Subtests grün. Nach abschließender Halt-Typprüfung53 Pending-/Journalfälle/
37 Subtests grün; **342 unterschiedliche gepinnte Fälle** über die
überlappenden Auswahlen. Zusätzlich voller tatsächlicher synthetischer
6576-Frame-Lauf und dessen Wiederanlauf/Ankerprüfung.

Zwölftausend retained IDs/alte Präfixe/Balancierung, Kapazitätsstop,
ursprüngliche ökonomische Gleichheit, echte Teilfills/Unknownorder/Terminal,
Funding/Exit/Cancel, bekannte unerwartete Fills/Quarantäne, Foreignbindings,
Dateimodes/Locks, Stale/Truncation/Writeackfehler und unveränderte alte
Trading-/Worker-Snapshotverträge geprüft. Eigenreview, keine Agentcalls,
Dependencies, PostgreSQL-/Migrationsänderungen oder breite Credential/UI-Suiten.

IP-069 bleibt wirtschaftliches Forschungsprotokoll/Fundingnominalreferenz/
Kohorten-/Ausführungsannahmen und tatsächlicher Nettovergleich.
Die vorhandenen echten Binance-Daten sind BTC/ETH; das3–7-Symbol-Profil
benötigt vor einem nativen Portfoliovergleich eine passende echte Kohorte.
Keine synthetische dritte Coinreihe als native Binanceperformance ausgeben.
Broker-Atomicität/Puffertiming, realer Globalfill-/Recoverybetrieb und
Gewinnetappen-/Regimeintegration bleiben getrennte Abnahmen.
