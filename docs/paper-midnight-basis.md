# Freigegebene Paper-Tagesbewertung

IP-052,2026-11-09. [Q32](interview.md#q32-paper-tagesbasis) bestätigt:
Paper-Tagesbasis00:00UTC = vorheriges virtuelles Cash + offene BTC-/ETH-Mengen
zum Schlusskurs der um Mitternacht abgeschlossenen H4-Kerzen.
Ausdrücklich Modellbewertung;6% Tages- und8% Startkapitallimit unverändert.

## Reihenfolge und Wiederherstellung

`PaperRunner.day` ist ein eigener deterministischer Input mit Policy
`paper-h4-close/1`. Beide exakten Grenzkerzen werden benötigt; andere Assets,
Zeitgrenzen und fehlende Kerzen werden abgewiesen. Cash/Bestände stammen aus
dem letzten bestätigten Zustand **vor** Mitternacht. Wurde der alte Tagesstand
bereits nach Mitternacht verändert, wird keine neue Basis daraus erfunden:
Käufe bleiben für diesen Tag gesperrt. Ein späterer Tag kann wieder eine
belegte Basis erhalten.

Der Worker validiert zuerst den ganzen Feedbatch und committed dann die
Tagesbasis vor aktuellen Quotes, Verkäufen oder Kerzenverarbeitung. Bei
Offlinezeiten sind die unveränderten gespeicherten Mengen verwendbar; keine
historischen Fills werden erzeugt. Tageswechsel während Fetch/Commit wird
abgewiesen. Die bestehende CAS-Transaktion speichert Basis und Journal
zusammen; derselbe Tag wird nach Neustart nicht erneut bewertet.
Unbekannte Commitantworten bleiben terminal bis frischem Readback.

Der Journaleintrag enthält eingefrorenes Cash, Mengen, beide OHLC-Kerzen,
Fingerprints, Ergebnis und Policy. SQL012 vergleicht spätere gespeicherte
Mitternachtskerzen mit diesen Fingerprints, auch nach einem Crash vor
Indikatorverarbeitung. Eine geänderte Kerze kann so nicht stillschweigend zur
RSI-Berechnung übernommen werden. SQL vertraut dem gebundenen Pythonwriter
für Berechnung/Strategie; keine unabhängige SQL-Risk-Engine.

Modellpreise werden nie als Quotes eingespielt: keine Schutzaktivierung,
Order oder Fill aus der Bewertung. Cash, Mengen, Orders, RSI-Zustand,
Schutzflags und gelatchte Risikohalts bleiben unverändert. Der konkurrierende
automatische Paperreset über einen exakt zeitgleichen Quote entfällt.
Bestehender historischer Simulator und eingefrorene Researchresultate bleiben
unverändert; dieser Checkpoint liefert keinen neuen Profitabilitätsnachweis.

## RSI und Ausführung

Weiterhin derselbe CryptoEngine: RSI14/Wilder aus abgeschlossenen H4-Kerzen.
Der erste automatische Einstieg verlangt zwei aufeinanderfolgende Kerzen
unter RSI30. Weitere reguläre Stufen brauchen das bestätigte RSI-Rearming
und5% Abstand zum letzten tatsächlichen Fill. Bewertungsinputs zählen nicht
als Kerzen oder Einstiegssignale. Verspätete Signale werden weiter gesperrt.
Ein Intent wartet auf einen späteren frischen tatsächlichen Ask/Bid samt
bestehendem Gebühren-/Slippagemodell. Manuelle sechste Tranche Q29 unverändert.

## Persistenz und Anzeige

Additive012 erweitert die bestehenden Funktionen um Journalkind `day` und
verifiziert die eingefrorene Grenzkerze. Ein partieller Journalindex hält die
Belegsuche begrenzt. Keine neuen Rollen/Tabellenrechte oder Checkpointfelder;
001–011 und bestehende Checkpointbytes bleiben unverändert.
Die API liefert nur feste Meldung und `day_basis_model`; der Cockpitstatus
kennzeichnet „H4-Schlusskurse · Modellbewertung um 00:00 UTC“ und
„Tagesbewertung“. Rohbelege/Fingerprints bleiben privat. Das Label bleibt auch
erhalten, wenn der Tageseintrag außerhalb der letzten20 angezeigten Inputs liegt.

012 nach vollständig zurückgerolltem tatsächlichem Writer-/Replaypreflight
und gezieltem unabhängigem Review ausschließlich Fixture-DB angewendet.
Unveränderliche SHA256:
`b79857a01fa9eba1dbac5d9d46a10432723b4bd97e2b9ad89ca47c1198b2fa0a`.
Normale DB007, Fixture012. Keine normale Migration/öffentliche Aktivierung.

## Abnahme und verbleibende Arbeit

190 unterschiedliche gezielte Python-/PG-Fälle und48 Subtests bestanden:
43 tatsächliche PG/API,22 Paperworker,10 Tagesbasis,12 Statusprojektion,
54 Marktdata,45 Trading und vier Workerberechnungen. Vollauf189 grün,
ein neuer Test hatte inkonsistente OHLC-Testdaten; korrigierter Neustartfall
und zwei geänderte CLI-Fälle separat grün (3/187 abgewählt).
Held-Bestand/sofortiger Verkauf, Tagescommit vor Quote, Crash/Replay,
Commitverlust/Rollback, fehlende/revidierte Grenzkerzen und unveränderliche
Basismarkierung geprüft. Positiver RSI-Fall erzeugt erst einen Intent und
dann genau einen späteren echten Quote-Fill; Bewertung allein erzeugt keinen.

17 Cockpit-Vertrags-/SSR-Fälle, Typecheck und gepinnter Cockpitbuild bestanden.
Normale DB007/Fixture012 und alle angewendeten Ledgerprüfsummen geprüft.
Bestehende öffentliche Container unverändert/gesund, Cockpit gültiges
TLS/HTTP200. Keine neuen Dependencies oder breite Credentialchecks.

```bash
python3 infra/scripts/prepare-paper-day-checks.py
bash infra/scripts/check-paper-storage.sh
# Nach einer gezielten Korrektur nur betroffene Fälle wählen:
bash infra/scripts/check-paper-storage.sh -k restart_same_day
```

IP-047/BL-028: permanente Entwicklungsidentität, Quote-/Egress-/Retentionbetrieb,
laufender Dienst und gesonderte Betriebs-/Anzeigeabnahme bleiben offen.
CLI weiterhin `--once` oder `--cycles 1..100`. API/Cockpit-Anzeigeflags
standardmäßig aus; Default Compose und öffentliche Dienste unverändert.
