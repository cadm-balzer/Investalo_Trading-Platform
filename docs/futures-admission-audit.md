# Diagnose der nativen Futures-Kaufablehnungen

IP-083 liest ausschließlich den vollständigen, bereits bestätigten IP-082-
Journalbestand. Es gibt keinen neuen Backtest und keine Änderung an Kapital,
Funding, Kaufstaffel, Hebel oder Preis-/Margingrenzen.

`infra/scripts/audit-futures-admissions.py NEW_OUTPUT_DIRECTORY` prüft den
eingefrorenen Receipt, das Forschungsprotokoll, die Quellen-Datasetbindung,
alle vier Ergebnisdateien und acht ursprünglichen Implementationsdateien.
Die eigenen zwei Diagnoseimplementationshashes werden vor und nach dem Lauf
verglichen. Ausgabe entsteht ausschließlich in einem neuen Verzeichnis;
bei Fehlern wird kein Erfolgsreceipt ausgestellt.

Der eigene Leser öffnet das Journal nur lesend, ohne Symlinks, mit gemeinsamem
nicht blockierendem Dateilock. Eigentümer, Modus0600, einzelner Hardlink und
die bestehende512-MiB-Grenze sind verbindlich. JSON-Zeilen bleiben begrenzt,
doppelte Schlüssel und unvollständige Zeilen werden verworfen. Das verhindert
eine Diagnose während eines kooperierenden exklusiven Journalwriters.

Jede tatsächliche Transition wird vom unveränderten Kapitaljournaldecoder
und Reducer restauriert. Sequenz, vorheriger Zustand, Kettenhash und der
vollständige abschließende Receipt müssen exakt übereinstimmen. Nach der
expliziten Open+2s-Ausführungsbewertung wird die originale Symbolreihenfolge
rekonstruiert: zuerst tatsächlich erforderliche eigene Restoration, dann
geschlossene RSI-Signale, eingefrorene Hebelentscheidungen und Käufe.
Erlaubte Käufe müssen als tatsächliche Commands vorhanden sein.
Abgelehnte Assessments verändern keinen Zustand und erfinden keine Fills.
Die rekonstruierten Ablehnungszähler, tatsächlichen Kaufzahlen und gesamten
Einstiegskandidaten müssen exakt dem eingefrorenen Bericht entsprechen.

Jeder Ablehnungsversuch erhält Zeitpunkt, vorherigen Kettenanker/Zustandsdigest,
Coin, Basketzyklus und Kaufstufe sowie Trade-/Markpreis, Kaufgrenze,
Eigenkapital, isolierten Saldo, Funding, bezahlte Restoration, verbleibende
Kostenkapazität und ungenutztes reguläres/manuelles Kapital.
Die deklarierte Initialmargin wird zusätzlich nach Kaufbasis und Marknominal
aufgeschlüsselt. Unrealisierte PnL bleibt ausdrücklich separat.

Ein Versuch kann mehrere Ablehnungsgründe besitzen. Wiederholte Versuche
desselben Coins/Zyklus/Stufe sind keine zusätzlichen Baskets.
Marginfehlbeträge dürfen daher nicht zu einem Geldbedarf addiert werden.
Eine Diagnose der Forschungsregel ist keine Bestätigung einer historischen
Binance-/Bitgetregel oder einer tatsächlich akzeptierten Brokerorder.
Das Modell berücksichtigt bei der Initialmargin den isolierten Saldo plus
neues Stufenkapital gegenüber dem größeren Basis-/Marknominal geteilt durch
den Hebel. Es beweist nicht, dass ein Broker exakt diese Bestandsmarginregel
verwendet. Ein alternatives Modell benötigt getrennte belegte Annahmen.

Neun unterschiedliche gepinnte Tests und zehn Subtests prüfen den vollständigen
synthetischen Restore, echte Fundingdepletion vor einem zweiten RSI-Kauf,
überlappende Markpreisablehnungen, Wiederholungszählung, Quellenunveränderlichkeit,
Receipt-/Counter-/Profilbindungen, Kettenmanipulation, ausgelassene erlaubte
Fills, unvollständiges JSON sowie Dateimodus/Symlink/Hardlink/Writerlock.
Die Fundingprüfung wurde nach Korrektur einer Assertion zum Restbetrag unter
dem1E−8-Quantum gezielt wiederholt. Die183 historischen Prüfungen wurden nicht
erneut ausgeführt; ihre Implementationsdateien sind unverändert.

Der erste Lauf wurde durch einen Daemonneustart unterbrochen. Der zweite
restaurierte den vollständigen Endzustand und die Zähler, scheiterte aber
beim JSON-Export: der bestehende `primitive`-Helper rekursiert nicht über
Dictionaries, und der bisher verwendete JSON-Helper liefert Text statt Bytes.
Eigene Evidencewerte werden jetzt einzeln normalisiert; ein expliziter
UTF-8-Byteencoder und ein zusätzlicher vollständiger Evidence-Exporttest
sichern beide Grenzen. Drei betroffene gepinnte Tests bestehen nach dem Fix.
Fehlgeschlagene Verzeichnisse bleiben ohne Erfolgsreceipt erhalten.

Historische Performance, aktive Paper-/Cockpitprofile, Datenbanken,
Abhängigkeiten und AI-/Brokeraktivierung bleiben unverändert.

[Vollständige native Ergebnisse](futures-admission-results-20261113.md).
