# Native Quellen für den Workerstart

Stand 24.11.2026. PR127/main`e28075e` verifiziert.

Die [Worker-Initialisierung](bitget-demo-worker-bootstrap.md) bekommt eigene
Producer für den aktuellen Kontobeleg und die historische H1-Serie. Bestehende
Trading-AEAD, signierte Demo-GETs, UID-/Parent-/Rechteprüfungen und der
RSI-Kerzenparser werden wiederverwendet. Keine neue Datenbank oder Abhängigkeit.

`NativeStartAccountSource` führt genau drei private GETs aus: Identität,
USDT-Futures-Wallet und vollständige Positionen. Der originale aktuelle
Actor-/Keyguard ist obligatorisch; gemeinsame Accountmutex, PIDprüfung,
eine Sekunde Startabstand, 110ms GET-Pacing und unverlängerter Fünf-Sekunden-
Kohortschutz. Aktuelle Trading-Snapshots und Klartextfingerprints werden vor
und nach jedem GET und vor Veröffentlichung geprüft. Keine HTTP-Wiederholung.

UID/Parent/native Rechte und erlaubter IP-Zustand müssen zur bestehenden
privaten Trading-Identität passen. Einzelnes USDT-/Single-Konto, bekannte
Eigenkapitalbeträge, keine Positionen und bekannte null Sicherheiten sind
Voraussetzung für einen `BrokerFlatAccount`. Unbekannte Bonus-/Sicherheiten-
oder Geldbeträge bleiben benannte Blocker und erzeugen keinen Kontobeleg;
fehlende Werte werden nicht null. Bestehende Positionen werden nicht adoptiert.
Der Hash bindet originale Replybytes und Wallet-/Positionszeiten. Keine raw
UIDs, Keys oder Replies im Ergebnis. Dies ist keine vollständige Orderzulassung:
offene Auftragsfamilien, Coinprofile, Kosten und Marketmaxima sind weiter
unabhängig zu prüfen. Der Producer gewährt keine Orderfreigabe.

`DemoWarmupSource` lädt für dieselben geordneten Kandidaten jeweils 300
abgeschlossene H1-Handels- und Markpreiskerzen. Beide Preisarten stammen aus
separaten nativen Abrufen gemäß
[Classic-Markt-API](https://www.bitget.com/docs/catalog/classic-contract-market/classic-contract-market).
Nur feste Demo-URLs und `paptrading: 1`; kein API-Key. Maximal drei parallele
Abrufe, 110ms Startabstand, 4,5s Sammlung und begrenzte Antwortgrößen.
Die laufende Kerze wird ausgeschlossen. Fehler, Lücken, doppelte oder fremde
Kerzen veröffentlichen kein Teilfenster.

Das Fenster behält ursprüngliches Ende, Abrufzeit und Quellenhash. Die
Workerübergabe liefert höchstens 24 Stunden je Slice; der gleiche Cache
benötigt keine erneuten HTTP-Abrufe während des 300-Stunden-Warmups. Nach
Neustart darf ein älteres originales Fenster neu geladen werden, ohne es
durch die heutige Stunde zu ersetzen. Der öffentliche Cache enthält keine
Actor-/Credentialautorisierung; der Worker prüft diese weiterhin unabhängig.
Die vorhandene Dashboard-RSI-Auswertung behält ihr bisheriges aktuelles
Stundenfenster und ihre Wilderwerte.

13 neue Fälle mit tatsächlicher Trading-AEAD/HMAC sowie tatsächlichem
Quellen-/Worker-/Journalablauf über synthetische Native-/Actorports.
133 betroffene gepinnte Fälle grün in Gesamtabdeckung: breiter132-Fall-Lauf
plus finaler35-Fall-Lauf mit zusätzlicher unabhängiger Actorrevokation/HMAC-
Prüfung. Finaler Executorbuild, vier Paketquellhashes/Imports ohne Netz/
Quellmounts/Keys grün; Dispatcher standardmäßig aus.

Echte öffentliche Probe aus dem finalen Executorpaket: 14 schlüssellose
Demo-GETs, sieben Coins, 300 vollständige Stundenpaare/4.200 native Kerzen,
Fensterende 24.11.2026 21:00 UTC. Alle Daten validiert; keine Privatkonto-
oder Orderabnahme aus dieser öffentlichen Probe abgeleitet.

Producer sind verpackt, aber noch nicht operativ an eine ursprüngliche
dauerhafte Startzustimmung angeschlossen. Nächster Schritt: eigener
Strategie-Consumer und laufende Handelskoordination über den gespeicherten
Dashboard-Wunsch. Kein Deployment, keine tatsächlichen privaten Kontoabrufe,
keine Kontoänderung oder Order in diesem Implementierungsschritt.
Lesender Abschlussaudit: alle sieben laufenden Dienste/Images, ursprüngliche
private Datei-Hashes und technisches BTC-Testjournal Revision8 unverändert.
