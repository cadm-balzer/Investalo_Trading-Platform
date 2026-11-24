# Startbasis für den Demo-Worker

Stand 24.11.2026. PR126/main `69dffe6` verifiziert.

Der Forschungsledger startet um 00:00 UTC. Ein Demo-Start am Nachmittag darf
heutiges Guthaben nicht als Mitternachtsbestand eintragen. Historische Kerzen
dürfen keine alten Käufe, Gebühren, Gewinne oder Guthaben erzeugen.

`BrokerFlatAccount` beschreibt unabhängig zu bestätigende aktuelle Beträge
und die originale Wallet-/Positionsuhr. Equity/verfügbare Margin gleich und
positiv; UPL, belegte Margin, Sperrbetrag und Positionszahl bestätigt null.
Unbekannte Werte, Positionen, anderes Startkapital oder über fünf Sekunden
alte Quellen erlauben keine Initialisierung. Der native Producer ist noch
zu installieren; Datentypen ersetzen seine Prüfungen nicht.

`BrokerCurrentLedgerState` beginnt am tatsächlichen Snapshotzeitpunkt.
Die erste Tagesbasis gilt nur ab dort. Folgende Tagesbasen brauchen die normale
frische UTC-Mitternachtsbewertung. Forschungs-/Paper-Startregeln und alte
Ledgerlayouts bleiben unverändert. Die Kaufbewertung akzeptiert ausschließlich
die geprüfte erste native Teil-Tagesbasis am selben Kalendertag. Ein fehlender
Folgetagsschluss bleibt ungültig. 6-%-/8-%-Warnungen, Kaufbeträge und Kosten-/
Marginprüfungen bleiben erhalten. Menge: Eigenkapital-Margin × 2 vor Mengenfloor.

Basketjournal `/7` speichert den originalen aktuellen Kontobeleg im Header.
Fundingcursor ist die letzte Wallet-/Positionsquellenzeit, nicht die spätere
Verarbeitung. Keine automatische Adoption alter `/2`–`/6`-Journale; operative
Basketjournale existieren noch nicht. Technisches BTC-Journal8 unverändert.

`DemoBootstrapWorker` verarbeitet 300 zusammenhängende abgeschlossene native
H1-Trade-/Markframes bis zum letzten Schluss vor dem ursprünglichen Start.
Maximal 24 Stunden pro Journaländerung, insgesamt 13 Änderungen.
Originalfenster, Fortschritt, Werte, Hashkette und Indikatoren werden vollständig
restauriert. Ein aktueller unabhängiger Actor-/Keyguard ist vor/nach Quellabruf
und nach Verarbeitung obligatorisch. Unterbrechungen setzen am nächsten fehlenden
Originalabschnitt fort; verlorener ACK wiederholt keinen gespeicherten Abschnitt.

Wilder-RSI/H1-Supertrend nutzen bisherige Funktionen. Finanzledger, heutige
Quotes und Guthaben ändern sich beim Warmup nicht; gemeinsames H4-Scratchpad
bleibt kalendergerecht. Historische RSI-Bedingungen starten keine Order.
Erst ein neuer bestätigter H1-Schluss kann einen aktuellen Einstieg liefern.
Finanzielle Journalaktionen bleiben vor Warmupende gesperrt.

13 neue Fälle mit tatsächlichen Journaldateien, Vollrestore und Workerablauf.
Konto-, Candle- und Actorports synthetisch. 295 betroffene gepinnte Fälle grün
in zwei Läufen: 269 Order-/Margin-/Funding-/Kapital-/Paperfälle sowie 26
zusätzliche Cash-/Reserve-/Fundingfälle. Finaler Executorbuild und fünf
Paketquellhashes/Kernel-/Workerimporte ohne Netz, Quellmounts oder Credentials
geprüft. Dispatcher standardmäßig aus; keine native Kontoabnahme aus Fixtures.

Der Bootstraphelper ist verpackt; kein operativer Handelsdaemon gestartet.
Die [nativen Konten-/Kerzenproducer](bitget-demo-native-start-source.md)
sind implementiert und separat geprüft. Als Nächstes: ursprünglicher
Strategie-Consumer und laufende Kauf-/Ausstiegs-/Fundingkoordination. Unbekannte native
Maximalmengen, Sicherheiten oder Kosten werden hier nicht freigegeben.

Die gemergte [Dashboard-Steuerung](bitget-demo-dashboard-control.md) ist separat
live. „Start angefordert“ bleibt gespeicherter Wunsch; noch kein automatischer Handel.
