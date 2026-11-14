# Kapitalempfehlung für eigene Futures-Paperbaskets

IP-090, 2026-11-14. PR67 (`0488d14`) ist in `main9dc351e` enthalten;
GH/Fetch/Ancestry bestätigt. Dieser Schritt verbindet die bestehende
Basketplanung mit dem tatsächlich bestätigten eigenen Paperkapital.

## Berechnung und Grenzen

`futures_paper_capacity.py` projiziert ausschließlich den eigenen bestätigten
Journalstand. Verfügbares Cash ist der echte ungebuchte Paperbestand nach
bereits gebuchter Margin und Kosten. Davon werden Planrest, sämtliche noch
offenen regulären und manuellen Eigenkapitalstufen, übrige eigene Kostenreserve
und konservativ unbezahlte isolierte Kapitalwiederherstellung abgezogen.
Liquidierte Assets behalten ihre ungenutzten reservierten Stufen; sie zählen
nicht als geeignete neue Kandidaten.

Das unveränderliche Budget je vollständiger sechsstufiger Range und die
tatsächlich finanzierten Plätze begrenzen die Empfehlung zusätzlich zur
gespeicherten Obergrenze und zur Zahl geeigneter Assets. Freies Cash allein
vergrößert weder das Rangebudget noch die bestätigte Finanzierung. Ein Konto
mit drei finanzierten Ranges empfiehlt auch bei gespeicherter Grenze sieben
höchstens drei Baskets. Q36-Gewinnetappen bleiben separat umzusetzen.

`futures_capacity_source.py` liest die bestätigte archivierte native
Quotekohorte vollständig erneut und führt einen zusätzlichen unsigned Classic-
Contracts-GET aus. Aktuelle Mindestmenge, Mindestnotional, Mengenraster,
Preisraster, maximale Marketmenge, Instrumentstatus und 2×-Verfügbarkeit werden
für die fünf bestehenden Kandidaten geprüft. Die aktuellen Grids müssen den
eingefrorenen Ausführungsgrids entsprechen. Änderungen nehmen den betroffenen
Kandidaten aus der Empfehlung; offene Ausführungsprofile werden nicht geändert.

Die kleinste vollständig finanzierbare Range wird am aktuellen Ask inklusive
deklarierter Slippage und adverser Tickrundung, Mark-Margin und allen sechs
25%-Stufen berechnet. Deklarierte Geldquantums decken verschachtelte Rundungen;
kein Margin-Epsilon. Dies ist eine aktuelle Planungsschätzung, keine Zusage
für zukünftige Nachkaufkurse, Maintenance oder Brokerorderannahme. Gebühren und
Paperfills bleiben die erklärten bestehenden Modellannahmen.

Der Vertragsabruf ist begrenzt, ohne Credentials, Redirects oder automatische
Wiederholung. Sein Rohantwort-SHA und die abgeleiteten Werte gehören zur
Publikation; diese Erweiterung archiviert die zusätzliche Rohantwort nicht
als neue native Quellenkohorte. Originale Quotes bleiben im bestehenden Archiv.

## Publikation, API und Cockpit

Die optionale Kapazität wird mit Assets und Journalreceipt gemeinsam in der
privaten atomaren/fsync/readback-Statusdatei veröffentlicht. Der neue
Statusvertrag `/2` ergänzt Kapazität; `/1` bleibt lesbar und wird ohne aktivierten
Reader weiterhin geschrieben. Gleiche Journalrevisionen lösen keinen
erneuten GET und keine künstliche Frische aus. Ein unbekannter Statuswrite
stoppt weiterhin und benötigt den vollen Mindestreceipt-Restore.

Ein fehlgeschlagener zusätzlicher Instrumentabruf hält die Empfehlung zurück,
ohne eine neue finanzielle Handelssperre einzuführen. Funding-only-Stände ohne
passende bestätigte Quotes erzeugen ebenfalls keine aktuelle Empfehlung.
Nach dem Abruf wird der Journalhead vor der gemeinsamen Publikation erneut
geprüft.

Die normale authentifizierte Planungs-API liest erst nach eigener RLS-
Kontoprüfung die private Publikation. Bei jedem Abruf prüft sie Konto,
Settingsrevision, aktuelle geschlossene H1-Grenze und die echten Quote- und
Instrumentuhren mit maximal 30 Sekunden Alter. Kontopause, ausstehende
Workerübernahme, fehlende/veraltete Instrumente, Reservedefizit oder zu wenige
geeignete/finanzierte Ranges haben konkrete Gründe. Eine beschädigte Empfehlung
verhindert keinen bestätigten Settings-CAS samt Audit.

Der Cockpitvertrag akzeptiert ausschließlich gebundene, begrenzte Werte.
Das Portfolio zeigt Empfehlung, finanzierte/offene Plätze, vollständiges
Rangebudget, freie Mittel nach Reserven und beide Datenzeiten. Bestehender
Refresh übernimmt neue Lesestände; unbekanntes Speichern wird weiterhin nicht
automatisch wiederholt.

`FUTURES_PAPER_CAPACITY_ENABLED=1` aktiviert den zusätzlichen Workerreader
explizit. Normale/API-/BFF-Opt-ins bleiben standardmäßig aus. Nur das isolierte
lokale Abnahmeoverlay aktiviert ihn. Keine Migration, neuen Grants,
Abhängigkeiten, laufenden öffentlichen Dienste, finanziellen Journalcodecs,
historischen Performanceartefakte oder Live-/AI-Freigaben geändert.

## Prüfung

Acht neue Domain-/Quellen-/Dateisystemfälle und zwei tatsächliche PG-/HTTP-
Fälle prüfen Reserven, Fundingdefizit, aktuelle Mindestorders, geänderte Grids,
Status/2×, falschen Scope, fehlende/veraltete Daten, Settings7 bei drei
finanzierten Ranges, atomare Publikation und Unknown-write. Der gezielte
gepinnt ausgeführte Gesamtrun besteht mit 89 Fällen und 18 Subtests.

Zwei neue Cockpitfälle prüfen strikten Vertrag und tatsächliches SSR-Markup;
alle 574 Frontendtests und der Typecheck bestehen. Die native lokale
Cockpitabnahme besteht mit 60 Prüfungen einschließlich echter aktueller
Empfehlung, Settings-Pending, Neustartübernahme und veralteter Instrumentdaten.
Der gepinnte Cockpitbuild besteht. Der vorherige
[43-Punkt-Abnahmebeleg](futures-local-cockpit-acceptance.md) bleibt erhalten.

Neuer Lauf:
`/tmp/investalo-futures-local-acceptance/fcc6b5c4c6cb4ac6aa9e79ba44a74422`.
Create-only Abnahmereceipt-SHA:
`5e3cb1378e4d729d40d040056936483563e7d0a5487ffbc90d634b670a7f347f`.
Der gespeicherte Kapazitätssnapshot hat SHA
`7e221a8bdd65366d9968107b9a37ed4a547836224b47fd408ab7130f56ba08f2`.
Beide Bytes/SHA nach Abschluss nochmals lesend verifiziert.

Drei native Quellenkohorten, Journalrevision2→4; Empfehlung3 bei drei
finanzierten Ranges und fünf geeigneten Assets. Eigencash10000 USDT,
Planrestreserve0.00000001, freie Mittel9999.99999999,
festes Rangebudget3333.33333333 und aktuelle minimale volle Range100.79019975.
Keine offenen Baskets, Entries oder Closures in diesem kurzen Lauf;
keine Performance- oder physische Browser-/MFA-Abnahme behauptet.
Nur die drei isolierten Prüfdienste wurden gestartet und anschließend gestoppt;
die öffentliche Vorschau blieb unverändert.

Q36-Gewinnetappen und Q46/IP-088 manuelle Recovery folgen, anschließend
separat kalibrierte Bitget-Demoausführung.
