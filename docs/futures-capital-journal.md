# Vollständiger Wiederanlauf des neuen Futures-Basketprofils

IP-076 ergänzt den eigenen Wiederanlaufvertrag für Q41–Q43. Der
H4-RSI-/H1- oder H4-Supertrendadapter und seine Kapitalrechnung werden aus
allen bestätigten Inputs vollständig wieder aufgebaut. IP-075`fd99018`
ist in Main`d0fa375` verifiziert. Keine Marktperformance oder Aktivierung.

## Eigene Genesis und erhaltene Identitäten

`CapitalReplayJournal` verwendet
`isolated-usdt-capital-replay-journal/1`. Sein create-only Header bindet
den vollständigen Kapital-/Kosten-/Marginplan, Schutzintervall, Slippage,
Annahmendigest, ursprüngliche Trade-/Markpreise, exakten UTC-Mitternachtsstart,
Evidenz sowie Protokoll- und sortierte eindeutige Dataset-SHA256s.
`CapitalPlan.capital_policy` wird ausdrücklich geprüft; der allgemeine
Snapshotdecoder erhält keine Änderung für diesen init=False-Discriminator.

Genesis ist stets flat. Es gibt keinen Restore aus einem Rootreceipt oder
einem bereits fortgeschrittenen Ledger und kein Löschen alter IDs.
Die spätere Integration muss ihren eigenen wirtschaftlichen Protokolldigest
und die tatsächlichen fünfzehn Quellen-Datasetdigests binden.

`CapitalIdentityHistory` hat eine eigene Version/Hashdomäne, persistent
balancierte Knoten und den bestehenden Membership-/Primitivecodec-Vertrag.
Default250000, ausdrücklich1..1000000 IDs; die alte Identitätspolitik
bleibt bei ihrem bisherigen Maximalwert100000. Namespace, Kapazität,
Anzahl und Root binden alle behaltenen IDs. Alte Präfixe bleiben immutable.
Die größere Politik wird ausschließlich bei einer neuen Journalgenesis
verwendet; bestehende Kapital-/Legacyzustände werden nicht konvertiert.

Für26304 Stunden sind vier feinere Preisbeobachtungen plus Kerzenschluss
131520 Commands. Mit1096 Tagesbasen und zwei wirtschaftlichen Inputs je
16515 Fundingevents wären165646 Ereignis-IDs erforderlich, noch ohne
Käufe, Hebelentscheidungen, Marginrestoration und Exits. Das erklärt die
neue Kapazität. Diese Rechnung ist eine Ressourcenplanung, kein tatsächlich
durchgeführter Dreijahres-Nettojob oder Beleg eines Intrabarpreiswegs.

## Vollständiges Journal und wirtschaftliche Wahrheit

Jeder Command enthält Revision, UTC-Zeit und typisierten vollständigen
Input. Unterstützt:

- native vollständige H1-Trade-/Markframes;
- ausdrücklich erklärte feinere Trade-/Markbeobachtungen;
- feste Baskethebelentscheidung vor dem Erstkauf;
- gebundene Signal-/Kapitalassessment und synthetischen vollständigen Kauf;
- Mark-only-Bewertung, signed Funding, ausdrückliche Kostenrestoration,
  Teil-/Vollverkauf und terminalen Liquidationsbeleg.

JSON-Feldreihenfolge beeinflusst die Aufrufreihenfolge nicht. Ein Kaufassessment
wird erneut an aktuelle RSI-/Staffel-/Kapitalbedingungen gebunden; das Journal
verleiht keine zusätzliche Signal- oder manuelle Reserveautorität.
Stufe6 bleibt manuell und kann nicht als automatische Performance erscheinen.

Sequence, vorheriger Head/Zustandsdigest und neuer Zustand/Head bilden die
Kette. Restore faltet die gesamte Datei durch dieselben Reducer. H4-Puffer,
Wilderindikatoren, Rearm, tatsächliche Stufen, Hebelzyklen, Trailingstopps,
Fundingzeiten/-kosten, ursprüngliches Kontokapital, Tagesbasen, Warnungen,
Halts und terminale Verluste bleiben erhalten. Eine bereits beobachtete
Liquidationspflicht verschwindet auch nach zwischenzeitlicher Erholung nicht.

Nach normalem Abschluss sind die vorherigen Kosten und Indikatorzustände
weiter vorhanden; der neue Zyklus braucht seine eigene feste Hebelentscheidung.
Nach Liquidation bleiben der Slot gesperrt und die ungestellten Stufen getrennt
belegt. Es gibt keine automatische Rettungsüberweisung oder Wiederbelegung.

## Commit, unbekannte Bestätigung und Kapazität

Eigene0600-Regular-Datei mit Ownerprüfung, kein Leaf-Symlink/Hardlink,
exklusiver kooperativer Writerlock. Write und `fsync` erfolgen vor Übernahme
des neuen Zustands; die Parentdirectory wird nach Create ebenfalls synchronisiert.
Abgewiesene/stale/doppelte Inputs schreiben keinen Record. Auch eine
Kapazitätsüberschreitung beim zweiten Teil einer Mitternachtstransition
übernimmt keinen halben In-Memory-Zustand.

`JournalCommitUnknown` sperrt nach Kurzwrite oder unbekanntem `fsync` alle
weiteren Reads/Appends. Schließen und vollständiger Readback sind erforderlich;
kein automatischer Retry oder Reparieren eines unvollständigen Tails.
Ein vollständig vorhandener unbekannter Record wird beim Readback rekonstruiert.

Ein separat behaltener `minimum_receipt` bindet den zuletzt bestätigten
Kontext/Head/Sequence/Zustand. Er erkennt auch den Verlust ganzer letzter
Records. Ohne diesen Anker beweist eine gültige Dateipräfixversion nicht den
zuletzt bestätigten Stand. Die lokale Hashkette ist kein Herkunfts-/Broker-
oder Manipulationsnachweis gegen einen Administrator mit Schreibrechten.

256KiB pro Record,512MiB Datei und maximal250000 Commands; jede Erschöpfung
stoppt ohne Eviction. Ein späterer Researchjob muss Ressourcen und Annahmen
vorher binden und darf Kapazitätsabbrüche nicht als vollständiges Ergebnis melden.
Kein SQL-/Worker-/Broker-/Cockpit-/Paper- oder öffentlicher Runtimecaller.

## Prüfung und nächster Schritt

23 neue Fälle; erster gepinnter Lauf22 Fälle/28 Subtests, direkt angrenzende
Regression77 Fälle/45 Subtests einschließlich des ergänzten Fundingfalls,
abschließend dessen Mark-only-Variante allein auf Host und gepinnt geprüft.
**99 unterschiedliche gepinnte Fälle**, Überlappungen nicht addiert.
Eigenreview, keine Agentdelegation oder breite DB-/Credential-/UI-Suiten.
Keine Dependencies, Migrationen, bestehenden Modul- oder Runtimeänderungen.

Die gezielten Fälle prüfen vollständige fünf echte RSI-Nachkäufe und
manuelle Restreserve, signed Funding mit Millisekundenzeiten, explizite
Kostenrestoration, Teilverkäufe, beide Schutzintervalle, normale neue
Hebelzyklen und terminale Liquidationen. Zusätzlich unveränderte frühere
Identitäts-/Journal-/Kapital-/Signalverträge.

Ein synthetischer Fünf-Coin-Lauf mit1200 Stunden und vier feineren
Beobachtungen je Stunde schreibt6000 Commands und6050 wirtschaftliche IDs.
Vollständiger Restore und separat bestätigter Anker ergeben exakt denselben
Zustand und Receipt; die erste Preisbeobachtung bleibt vorhanden.
Ein eigener Baumtest behält und prüft alle100005 IDs jenseits des alten Limits.
Diese Tests belegen Mechanik, keine native Marktrendite.

IP-074/IP-069 benötigen nun das vor Leistungsauswertung eingefrorene
wirtschaftliche Profil: Fundingnominalreferenz für fehlende native
Settlement-Marks, Gebühren/Slippage/Intrabarweg, Maintenance- und
Liquidationsabrechnung samt Kostenstress. Danach gleicher H1-/H4-Schutzvergleich
auf derselben nativen Quelle; Holdout und AI bleiben aus.
